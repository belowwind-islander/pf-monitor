# PF Signup Monitor

Monitors Saturday session signups on the PF organiser page and sends email alerts when the threshold is reached.

Runs every 10 minutes via GitHub Actions.

## Configuration

Edit `pf_monitor.py` to change:
- `SIGNUP_THRESHOLD` — alert when signups reach this number (default: 12)
- `SIGNUP_REFERENCE_DATE` / `SIGNUP_REFERENCE_NUMBER` — reference point for calculating signup links
