# PF Signup Monitor

Monitors Saturday session signups on the PF organiser page and sends email alerts when the threshold is reached.

Runs every 10 minutes via GitHub Actions.

## Setup

### 1. Create a new GitHub repository

Create a new **public** repo (e.g. `pf-monitor`) and push this code to it.

### 2. Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret name | Value |
|---|---|
| `ORGANISER_URL` | The full organiser page URL |
| `PAGE_PASSWORD` | The organiser page password |
| `GMAIL_ADDRESS` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | Your Gmail app password |
| `NOTIFY_EMAILS` | Comma-separated emails, e.g. `a@gmail.com,b@hotmail.com,c@gmail.com` |
| `SIGNUP_BASE_URL` | The signup URL prefix (without the session number) |

### 3. Test it

Go to **Actions → PF Signup Monitor → Run workflow** to trigger a manual test run.

### 4. Done

The workflow runs automatically every 10 minutes. It will email all recipients when the upcoming Saturday session reaches the signup threshold.

## Configuration

Edit `pf_monitor.py` to change:
- `SIGNUP_THRESHOLD` — alert when signups reach this number (default: 15)
- `SIGNUP_REFERENCE_DATE` / `SIGNUP_REFERENCE_NUMBER` — reference point for calculating signup links
