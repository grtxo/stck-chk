#!/usr/bin/env python3
"""
Sonos Warehouse Deals Stock Checker

Checks the availability of Sonos certified refurbished products on the
German Sonos website and sends an email notification when a product
comes in stock.

Usage:
    # Single run (used by GitHub Actions)
    python check_stock.py

    # Continuous local mode (checks every CHECK_INTERVAL_MINUTES)
    python check_stock.py --loop
"""

import argparse
import json
import logging
import re
import smtplib
import sys
import time
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

import config

# ─────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("sonos-stock")


# ─────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────
@dataclass
class ProductStatus:
    url: str
    name: str
    price: str
    in_stock: bool
    detection_method: str  # which parsing method found the result


# ─────────────────────────────────────────────────────────
# Stock detection
# ─────────────────────────────────────────────────────────
def fetch_page(url: str) -> str:
    """Fetch the raw HTML of a Sonos product page."""
    log.info("Fetching %s", url)
    resp = requests.get(
        url,
        headers=config.REQUEST_HEADERS,
        timeout=config.REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.text


def _detect_via_json_ld(soup: BeautifulSoup, url: str) -> ProductStatus | None:
    """Try to extract stock status from JSON-LD structured data."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        # JSON-LD can be a single object or a list
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get("@type") != "Product":
                continue

            offers = item.get("offers", {})
            # offers can be a single dict or a list
            offer_list = offers if isinstance(offers, list) else [offers]
            for offer in offer_list:
                avail = offer.get("availability", "")
                in_stock = "InStock" in avail
                return ProductStatus(
                    url=url,
                    name=item.get("name", "Unknown Product"),
                    price=f'{offer.get("price", "?")} {offer.get("priceCurrency", "EUR")}',
                    in_stock=in_stock,
                    detection_method="JSON-LD",
                )
    return None


def _detect_via_next_data(soup: BeautifulSoup, url: str) -> ProductStatus | None:
    """Try to extract stock status from Next.js __NEXT_DATA__ JSON.

    Sonos uses this structure:
      props.pageProps.product.inventory.orderable  → bool (primary signal)
      props.pageProps.product.inventory.stockLevel → int
      props.pageProps.product.name                 → str
      props.pageProps.product.price                → int (EUR)
      props.pageProps.product.currency              → str ("EUR")
    """
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return None

    try:
        data = json.loads(script.string)
    except (json.JSONDecodeError, TypeError):
        return None

    in_stock = None
    name = "Unknown Product"
    price = "?"

    try:
        page_props = data.get("props", {}).get("pageProps", {})
        product_data = page_props.get("product", {})

        if not product_data:
            return None

        name = product_data.get("name", name)

        # Price — simple integer in EUR on the German store
        price_val = product_data.get("price")
        currency = product_data.get("currency", "EUR")
        if price_val is not None:
            price = f"{price_val} {currency}"

        # Primary signal: inventory.orderable
        inventory = product_data.get("inventory", {})
        if inventory:
            in_stock = inventory.get("orderable", False)
            stock_level = inventory.get("stockLevel", 0)
            log.info(
                "  inventory: orderable=%s, stockLevel=%s, ats=%s",
                inventory.get("orderable"),
                stock_level,
                inventory.get("ats"),
            )
        # Fallback: check variants for orderable inventory
        elif "variants" in product_data:
            variants = product_data["variants"]
            if isinstance(variants, list):
                in_stock = any(
                    v.get("inventory", {}).get("orderable", False)
                    for v in variants
                )
    except (AttributeError, TypeError, KeyError):
        pass

    if in_stock is not None:
        return ProductStatus(
            url=url,
            name=name,
            price=price,
            in_stock=in_stock,
            detection_method="__NEXT_DATA__",
        )
    return None


def _detect_via_button_text(soup: BeautifulSoup, url: str) -> ProductStatus | None:
    """Fallback: look for add-to-cart / sold-out button text."""
    name = "Unknown Product"
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        name = title_tag.string.split("|")[0].strip()

    # Find price on page
    price = "?"
    price_el = soup.find(attrs={"data-testid": re.compile(r"price", re.I)})
    if not price_el:
        # Look for a span/div that looks like a price (e.g. "149 €")
        price_match = re.search(r'(\d[\d.,]*)\s*€', soup.get_text())
        if price_match:
            price = f"{price_match.group(1)} EUR"
    else:
        price = price_el.get_text(strip=True)

    # Check for "In den Warenkorb" (add to cart) vs "Ausverkauft" (sold out)
    page_text = soup.get_text(separator=" ")

    cart_pattern = re.compile(r"In den Warenkorb", re.I)
    sold_out_pattern = re.compile(r"Ausverkauft|Nicht\s+verfügbar|Out\s+of\s+Stock|Sold\s+Out", re.I)

    has_add_to_cart = bool(cart_pattern.search(page_text))
    has_sold_out = bool(sold_out_pattern.search(page_text))

    # Also check for disabled buttons
    buttons = soup.find_all("button")
    add_to_cart_btn = None
    for btn in buttons:
        btn_text = btn.get_text(strip=True)
        if cart_pattern.search(btn_text) or sold_out_pattern.search(btn_text):
            add_to_cart_btn = btn
            break

    if add_to_cart_btn:
        is_disabled = add_to_cart_btn.get("disabled") is not None
        btn_text = add_to_cart_btn.get_text(strip=True)

        if is_disabled or sold_out_pattern.search(btn_text):
            in_stock = False
        else:
            in_stock = True
    elif has_sold_out and not has_add_to_cart:
        in_stock = False
    elif has_add_to_cart:
        in_stock = True
    else:
        # No clear signal — assume out of stock (conservative)
        log.warning("No clear stock signal found for %s — assuming out of stock", url)
        in_stock = False

    return ProductStatus(
        url=url,
        name=name,
        price=price,
        in_stock=in_stock,
        detection_method="button-text",
    )


def check_product(url: str) -> ProductStatus:
    """
    Check stock status for a single Sonos product URL.

    Tries multiple detection methods in order of reliability.
    """
    html = fetch_page(url)
    soup = BeautifulSoup(html, "html.parser")

    # Method 1: JSON-LD structured data (most reliable)
    result = _detect_via_json_ld(soup, url)
    if result:
        log.info("[JSON-LD]  %s — %s", result.name, "IN STOCK ✅" if result.in_stock else "out of stock ❌")
        return result

    # Method 2: __NEXT_DATA__ (Next.js page data)
    result = _detect_via_next_data(soup, url)
    if result:
        log.info("[NEXT]     %s — %s", result.name, "IN STOCK ✅" if result.in_stock else "out of stock ❌")
        return result

    # Method 3: Button text / page content (fallback)
    result = _detect_via_button_text(soup, url)
    if result:
        log.info("[BUTTON]   %s — %s", result.name, "IN STOCK ✅" if result.in_stock else "out of stock ❌")
        return result

    # Should never reach here since button-text always returns something
    return ProductStatus(
        url=url,
        name="Unknown Product",
        price="?",
        in_stock=False,
        detection_method="none",
    )


# ─────────────────────────────────────────────────────────
# Email notification
# ─────────────────────────────────────────────────────────
def send_notification(products: list[ProductStatus]) -> None:
    """Send an email notification for products that are in stock."""
    if not config.GMAIL_ADDRESS or not config.GMAIL_APP_PASSWORD:
        log.warning(
            "Email credentials not configured — skipping notification. "
            "Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD environment variables."
        )
        return

    subject = f"🔔 Sonos Warehouse Deal verfügbar! ({len(products)} Produkt{'e' if len(products) != 1 else ''})"

    # Build HTML email body
    product_rows = ""
    for p in products:
        product_rows += f"""
        <tr>
            <td style="padding: 12px 16px; border-bottom: 1px solid #eee;">
                <strong>{p.name}</strong>
            </td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #eee;">
                {p.price}
            </td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #eee;">
                <a href="{p.url}" style="color: #fff; background: #000; padding: 8px 16px;
                   border-radius: 4px; text-decoration: none; display: inline-block;">
                    Jetzt kaufen →
                </a>
            </td>
        </tr>
        """

    html_body = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                 max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
        <div style="background: #000; color: #fff; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
            <h1 style="margin: 0; font-size: 20px;">🔔 Sonos Warehouse Deal Alert</h1>
        </div>
        <div style="border: 1px solid #eee; border-top: none; border-radius: 0 0 8px 8px; padding: 20px;">
            <p>Die folgenden generalüberholten Sonos Produkte sind jetzt verfügbar:</p>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <thead>
                    <tr style="background: #f5f5f5;">
                        <th style="padding: 12px 16px; text-align: left;">Produkt</th>
                        <th style="padding: 12px 16px; text-align: left;">Preis</th>
                        <th style="padding: 12px 16px; text-align: left;">Link</th>
                    </tr>
                </thead>
                <tbody>
                    {product_rows}
                </tbody>
            </table>
            <p style="font-size: 12px; color: #999; margin-top: 20px;">
                Greif schnell zu — generalüberholte Produkte sind oft schnell vergriffen!
            </p>
        </div>
    </body>
    </html>
    """

    plain_body = "Sonos Warehouse Deal Alert!\n\n"
    for p in products:
        plain_body += f"✅ {p.name} — {p.price}\n   {p.url}\n\n"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.GMAIL_ADDRESS
    msg["To"] = config.NOTIFY_EMAIL
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    log.info("Sending notification email to %s", config.NOTIFY_EMAIL)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
            server.sendmail(config.GMAIL_ADDRESS, [config.NOTIFY_EMAIL], msg.as_string())
        log.info("✅ Notification email sent successfully!")
    except smtplib.SMTPException as e:
        log.error("❌ Failed to send email: %s", e)
        raise


# ─────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────
def run_check() -> list[ProductStatus]:
    """Run a single stock check across all configured product URLs."""
    log.info("=" * 60)
    log.info("Starting stock check for %d product(s)", len(config.PRODUCT_URLS))
    log.info("=" * 60)

    results: list[ProductStatus] = []
    for url in config.PRODUCT_URLS:
        try:
            status = check_product(url)
            results.append(status)
        except requests.RequestException as e:
            log.error("Failed to check %s: %s", url, e)
        except Exception as e:
            log.error("Unexpected error checking %s: %s", url, e)

    in_stock = [r for r in results if r.in_stock]

    log.info("-" * 60)
    log.info(
        "Summary: %d checked, %d in stock, %d out of stock",
        len(results),
        len(in_stock),
        len(results) - len(in_stock),
    )

    if in_stock:
        log.info("🎉 Products in stock:")
        for p in in_stock:
            log.info("   ✅ %s — %s — %s", p.name, p.price, p.url)
        send_notification(in_stock)
    else:
        log.info("No products in stock right now.")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Sonos Warehouse Deals Stock Checker")
    parser.add_argument(
        "--loop",
        action="store_true",
        help=f"Run continuously, checking every {config.CHECK_INTERVAL_MINUTES} minutes",
    )
    args = parser.parse_args()

    if not config.PRODUCT_URLS:
        log.error("No product URLs configured. Set SONOS_PRODUCT_URLS or edit config.py.")
        sys.exit(1)

    if args.loop:
        log.info(
            "Running in loop mode — checking every %d minute(s). Press Ctrl+C to stop.",
            config.CHECK_INTERVAL_MINUTES,
        )
        while True:
            try:
                run_check()
                log.info(
                    "Next check in %d minute(s)...\n",
                    config.CHECK_INTERVAL_MINUTES,
                )
                time.sleep(config.CHECK_INTERVAL_MINUTES * 60)
            except KeyboardInterrupt:
                log.info("Stopped by user.")
                break
    else:
        results = run_check()
        # Exit with code 0 even if nothing is in stock (success = check ran fine)
        sys.exit(0)


if __name__ == "__main__":
    main()
