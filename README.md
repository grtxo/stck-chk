# 🔔 Sonos Warehouse Deals Stock Checker

Automatically checks Sonos Germany's certified refurbished products for availability and sends you an email the moment something comes in stock. Runs for **free** on GitHub Actions — no server or PC needed.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Setup Guide](#setup-guide)
  - [Step 1: Create a GitHub Account](#step-1-create-a-github-account)
  - [Step 2: Create a New Repository](#step-2-create-a-new-repository)
  - [Step 3: Upload the Code](#step-3-upload-the-code)
  - [Step 4: Create a Gmail App Password](#step-4-create-a-gmail-app-password)
  - [Step 5: Add Secrets to GitHub](#step-5-add-secrets-to-github)
  - [Step 6: Configure Product URLs](#step-6-configure-product-urls)
  - [Step 7: Enable GitHub Actions](#step-7-enable-github-actions)
  - [Step 8: Test It](#step-8-test-it)
- [Finding Product URLs](#finding-product-urls)
- [Changing the Check Interval](#changing-the-check-interval)
- [Monitoring & Troubleshooting](#monitoring--troubleshooting)
- [Running Locally (Optional)](#running-locally-optional)
- [Cost](#cost)

---

## How It Works

The checker parses Sonos product pages every 15 minutes and reads the embedded inventory data (`inventory.orderable`) to determine whether a product is available. When it detects stock, it sends you a styled HTML email with the product name, price, and a direct purchase link.

Three detection methods are used for reliability:
1. **JSON-LD** — `schema.org` structured data
2. **Next.js page data** — `__NEXT_DATA__` JSON with `inventory.orderable`
3. **Button text** — Searches for "In den Warenkorb" vs "Ausverkauft"

---

## Setup Guide

### Step 1: Create a GitHub Account

If you don't have one yet:

1. Go to [github.com](https://github.com)
2. Click **Sign up**
3. Follow the prompts to create a free account
4. Verify your email address

### Step 2: Create a New Repository

1. Log in to GitHub
2. Click the **+** button in the top-right corner → **New repository**
3. Fill in the details:
   - **Repository name**: `sonos-stock-checker` (or anything you like)
   - **Visibility**: Select **Public** (recommended — GitHub Actions is free and unlimited for public repos)
   - Leave everything else as default
4. Click **Create repository**

### Step 3: Upload the Code

You have two options:

#### Option A: Upload via the GitHub website (easiest)

1. On your new repository page, click **uploading an existing file** (or go to **Add file** → **Upload files**)
2. Drag and drop **all files and folders** from the `sonos_stock_checker` directory:
   ```
   check_stock.py
   config.py
   requirements.txt
   .gitignore
   README.md
   .github/              ← this entire folder (contains workflows/check_stock.yml)
   ```
   > ⚠️ **Important**: The `.github` folder might be hidden on your computer. In Windows Explorer, enable **View → Show → Hidden items** to see it.
3. Click **Commit changes**

#### Option B: Upload via Git (if you have Git installed)

Open a terminal in the `sonos_stock_checker` folder and run:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/sonos-stock-checker.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

### Step 4: Create a Gmail App Password

The checker sends notifications through Gmail. You need an **App Password** (a special 16-character password), not your regular Gmail password.

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. Click **Security** in the left sidebar
3. Under "How you sign in to Google", make sure **2-Step Verification** is turned **ON**
   - If it's off, click it and follow the steps to enable it
4. Go back to the **Security** page
5. Search for or navigate to **App passwords** (you can also go directly to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords))
6. Under "App name", type `Sonos Stock Checker`
7. Click **Create**
8. Google will show you a **16-character password** (e.g. `abcd efgh ijkl mnop`)
9. **Copy this password** — you'll need it in the next step. You won't be able to see it again.

### Step 5: Add Secrets to GitHub

Secrets are encrypted environment variables that GitHub Actions uses to store sensitive data like passwords. They are never shown in logs.

1. Go to your repository on GitHub
2. Click **Settings** (tab at the top of the repo, not your profile settings)
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. You're now on the **Secrets** tab. Click **New repository secret** for each of the following:

| Name | Value | Required? |
|:---|:---|:---|
| `GMAIL_ADDRESS` | Your full Gmail address, e.g. `max.mustermann@gmail.com` | ✅ Yes |
| `GMAIL_APP_PASSWORD` | The 16-character App Password from Step 4 (with or without spaces) | ✅ Yes |
| `NOTIFY_EMAIL` | The email address to receive notifications (if different from your Gmail) | Optional |

To add each secret:
1. Click **New repository secret**
2. Enter the **Name** exactly as shown above (e.g. `GMAIL_ADDRESS`)
3. Enter the **Value** (e.g. your email address)
4. Click **Add secret**
5. Repeat for the next secret

### Step 6: Configure Product URLs

Now tell the checker which products to monitor.

1. In your repository settings, go to **Secrets and variables** → **Actions**
2. Switch to the **Variables** tab (next to the Secrets tab)
3. Click **New repository variable**
4. Set:
   - **Name**: `SONOS_PRODUCT_URLS`
   - **Value**: A JSON array of product URLs, for example:
     ```json
     ["https://www.sonos.com/de-de/shop/one-sl-b-stock"]
     ```
     To monitor multiple products:
     ```json
     ["https://www.sonos.com/de-de/shop/one-sl-b-stock","https://www.sonos.com/de-de/shop/arc-b-stock","https://www.sonos.com/de-de/shop/beam-gen-2-b-stock"]
     ```
5. Click **Add variable**

> 💡 You can change this list at any time — no code changes needed. Just edit the variable.

Alternatively, you can edit the `_default_urls` list directly in `config.py` if you prefer.

### Step 6b: Filter by Color (Optional)

By default, the checker alerts you when **any** color variant comes in stock. If you only want a specific color, set up a color filter:

1. Still on the **Variables** tab (from Step 6), click **New repository variable**
2. Set:
   - **Name**: `SONOS_DESIRED_COLORS`
   - **Value**: A JSON array of color values (use English, lowercase), for example:
     ```json
     ["black"]
     ```
     To accept multiple colors:
     ```json
     ["black", "white"]
     ```
3. Click **Add variable**

Available colors depend on the product. Common values are:

| Color | Value |
|:---|:---|
| Schwarz (Black) | `black` |
| Weiß (White) | `white` |

> 💡 If you leave `SONOS_DESIRED_COLORS` empty or don't create it at all, you'll be notified about **all** colors — the old behaviour.

### Step 7: Enable GitHub Actions

GitHub Actions should be enabled by default, but verify:

1. Go to your repository on GitHub
2. Click the **Actions** tab at the top
3. If you see a banner saying "Workflows aren't being run on this repository", click **I understand my workflows, go ahead and enable them**
4. You should see the **Sonos Stock Checker** workflow listed

### Step 8: Test It

Run the checker manually to verify everything works:

1. Go to the **Actions** tab in your repository
2. Click **Sonos Stock Checker** in the left sidebar
3. Click the **Run workflow** dropdown button (on the right side)
4. Click the green **Run workflow** button
5. Wait a few seconds, then refresh the page
6. Click on the new workflow run to see its progress
7. Click on the **check-stock** job to see the detailed logs

You should see output like:
```
Starting stock check for 1 product(s)
Fetching https://www.sonos.com/de-de/shop/one-sl-b-stock
  inventory: orderable=False, stockLevel=0, ats=0
[NEXT]     Generalüberholter One SL — out of stock ❌
Summary: 1 checked, 0 in stock, 1 out of stock
No products in stock right now.
```

If a product **is** in stock, you'll receive an email within seconds. 🎉

The workflow will now automatically run **every 15 minutes**, 24/7.

---

## Finding Product URLs

1. Go to the Sonos refurbished section: [sonos.com/de-de/shop/certified-refurbished](https://www.sonos.com/de-de/shop/certified-refurbished)
2. Click on any product
3. Copy the URL from your browser's address bar

Refurbished product URLs typically end with `-b-stock`:

| Product | URL |
|:---|:---|
| One SL | `https://www.sonos.com/de-de/shop/one-sl-b-stock` |
| Arc | `https://www.sonos.com/de-de/shop/arc-b-stock` |
| Arc Ultra | `https://www.sonos.com/de-de/shop/arc-ultra-b-stock` |
| Beam (Gen. 2) | `https://www.sonos.com/de-de/shop/beam-gen-2-b-stock` |
| Sonos Ace | `https://www.sonos.com/de-de/shop/sonos-ace-b-stock` |

---

## Changing the Check Interval

The default is every 15 minutes. To change it:

1. Open `.github/workflows/check_stock.yml` in your repository
2. Click the pencil icon (✏️) to edit
3. Change the `cron` line:

```yaml
schedule:
  - cron: '*/15 * * * *'   # Every 15 minutes (default)
```

Common alternatives:

| Interval | Cron Expression |
|:---|:---|
| Every 5 minutes | `*/5 * * * *` |
| Every 10 minutes | `*/10 * * * *` |
| Every 15 minutes | `*/15 * * * *` |
| Every 30 minutes | `*/30 * * * *` |
| Every hour | `0 * * * *` |
| Every 2 hours | `0 */2 * * *` |

4. Click **Commit changes**

> ⚠️ GitHub does not guarantee exact timing. Scheduled runs may be delayed by a few minutes during periods of high load.

---

## Monitoring & Troubleshooting

### Checking workflow history

1. Go to the **Actions** tab in your repository
2. You'll see a list of all past runs with their status (✅ success, ❌ failure)
3. Click on any run to see detailed logs

### Common issues

| Issue | Solution |
|:---|:---|
| Workflow never runs | Check that Actions is enabled (Step 7). Workflows on inactive repos (no commits for 60 days) get paused — push a commit to re-enable. |
| Email not received | Check the workflow logs for email errors. Verify your `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` secrets are correct. Check your spam folder. |
| `smtplib.SMTPAuthenticationError` | Your App Password is wrong or expired. Create a new one (Step 4). |
| `requests.exceptions.HTTPError: 403` | Sonos may be rate-limiting. Try increasing the check interval. |
| Workflow shows ❌ failure | Click the failed run → click the job → read the error message in the logs. |

### Keeping the workflow active

GitHub **pauses scheduled workflows** on repositories with no activity for 60 days. To prevent this:
- Push a commit occasionally (even a small README edit works)
- Or manually trigger the workflow from the Actions tab — this also counts as activity

---

## Running Locally (Optional)

You can also run the checker on your own machine:

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (PowerShell)
$env:GMAIL_ADDRESS = "you@gmail.com"
$env:GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"
$env:SONOS_PRODUCT_URLS = '["https://www.sonos.com/de-de/shop/one-sl-b-stock"]'

# Single check
python check_stock.py

# Continuous monitoring (checks every 15 min, Ctrl+C to stop)
python check_stock.py --loop

# Custom interval (every 5 minutes)
$env:CHECK_INTERVAL_MINUTES = "5"
python check_stock.py --loop
```

---

## Cost

**Free.** GitHub Actions provides:
- **Unlimited minutes** for public repositories
- **2,000 minutes/month** for private repositories

This checker uses ~10 seconds per run × 96 runs/day ≈ **16 minutes/day** — well within any limit.

---

## License

MIT
