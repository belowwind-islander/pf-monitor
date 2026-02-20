#!/usr/bin/env python3
"""
PlayFit Organiser Page Monitor (GitHub Actions version)
========================================================
All sensitive configuration is read from environment variables (GitHub Secrets).

Required environment variables:
    ORGANISER_URL       - The organiser page URL
    PAGE_PASSWORD       - WordPress page password
    GMAIL_ADDRESS       - Gmail address to send from
    GMAIL_APP_PASSWORD  - Gmail app password
    NOTIFY_EMAILS       - Comma-separated list of recipient emails
    SIGNUP_BASE_URL     - Base URL for signup links (without the session number)
"""

import os
import re
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta

import requests
from bs4 import BeautifulSoup

# ─── CONFIGURATION (from environment variables) ──────────────────────────────
ORGANISER_URL = os.environ["ORGANISER_URL"]
PAGE_PASSWORD = os.environ["PAGE_PASSWORD"]
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
NOTIFY_EMAILS = [e.strip() for e in os.environ["NOTIFY_EMAILS"].split(",")]
SIGNUP_BASE_URL = os.environ["SIGNUP_BASE_URL"]

SIGNUP_THRESHOLD = 12
SIGNUP_REFERENCE_DATE = date(2026, 2, 21)
SIGNUP_REFERENCE_NUMBER = 59

ALERTED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alerted.txt")

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("playfit_monitor")


# ─── ALERT TRACKING ──────────────────────────────────────────────────────────

def get_alerted_dates():
    if not os.path.exists(ALERTED_FILE):
        return set()
    with open(ALERTED_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())


def mark_alerted(date_str):
    with open(ALERTED_FILE, "a") as f:
        f.write(date_str + "\n")
    log.info(f"  Marked {date_str} as alerted")


# ─── TARGET SATURDAY ──────────────────────────────────────────────────────────

def get_target_saturday():
    now = datetime.now()
    today = now.date()
    weekday = today.weekday()

    if weekday == 5:
        if now.hour < 14 or (now.hour == 14 and now.minute < 30):
            return today
        else:
            return today + timedelta(days=7)
    else:
        days_ahead = 5 - weekday
        if days_ahead <= 0:
            days_ahead += 7
        return today + timedelta(days=days_ahead)


def parse_session_date(text):
    match = re.search(r'Sat\s+(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', text, re.IGNORECASE)
    if not match:
        return None

    day = int(match.group(1))
    month_str = match.group(2)
    month_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    month = month_map[month_str.lower()]
    year = datetime.now().year

    try:
        return date(year, month, day)
    except ValueError:
        return None


def get_signup_link(target_date):
    weeks_diff = (target_date - SIGNUP_REFERENCE_DATE).days // 7
    session_number = SIGNUP_REFERENCE_NUMBER + weeks_diff
    return f"{SIGNUP_BASE_URL}{session_number}/"


# ─── PAGE FETCHING ────────────────────────────────────────────────────────────

def get_authenticated_page():
    session = requests.Session()

    postpass_url = ORGANISER_URL.rsplit("/w/", 1)[0] + "/w/wp-login.php?action=postpass"

    session.post(
        postpass_url,
        data={"post_password": PAGE_PASSWORD, "Submit": "Enter"},
        headers={
            "Referer": ORGANISER_URL,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
        allow_redirects=True,
    )

    page_resp = session.get(
        ORGANISER_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
    )

    soup = BeautifulSoup(page_resp.text, "html.parser")
    if soup.find("form", class_="post-password-form"):
        raise Exception("Authentication failed — password may be incorrect.")

    return page_resp.text


# ─── PARSING ──────────────────────────────────────────────────────────────────

def parse_saturday_sessions(html):
    soup = BeautifulSoup(html, "html.parser")
    sessions = []

    spoiler_titles = soup.find_all("div", class_="su-spoiler-title")

    for title_div in spoiler_titles:
        text = title_div.get_text(strip=True)

        if not re.search(r'\bSat(?:urday)?\b', text, re.IGNORECASE):
            continue

        booking_match = re.search(r'BOOKINGS:\s*(\d+)\s*/\s*(\d+)', text)
        if not booking_match:
            continue

        current = int(booking_match.group(1))
        total = int(booking_match.group(2))
        session_date = parse_session_date(text)

        sessions.append({
            "description": text.strip(),
            "current_signups": current,
            "max_signups": total,
            "date": session_date,
        })

    return sessions


# ─── EMAIL ────────────────────────────────────────────────────────────────────

def send_email_alert(session_info, signup_link):
    subject = f"🏀 PlayFit Alert: {session_info['current_signups']}/{session_info['max_signups']} signups!"

    body = f"""Hi,

A Saturday session on PlayFit has reached {session_info['current_signups']}/{session_info['max_signups']} signups:

{session_info['description']}

Signups: {session_info['current_signups']} / {session_info['max_signups']}

Sign up here: {signup_link}

— PlayFit Monitor
(Checked at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
"""

    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = ", ".join(NOTIFY_EMAILS)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, NOTIFY_EMAILS, msg.as_string())
        log.info(f"✅ Alert email sent for: {session_info['description'][:80]}...")
        return True
    except Exception as e:
        log.error(f"❌ Failed to send email: {e}")
        return False


# ─── MAIN CHECK ───────────────────────────────────────────────────────────────

def check_and_alert():
    target_sat = get_target_saturday()
    log.info(f"Checking PlayFit organiser page... (looking for Sat {target_sat.strftime('%d %b %Y')})")

    try:
        html = get_authenticated_page()
    except Exception as e:
        log.error(f"Failed to fetch page: {e}")
        return

    sessions = parse_saturday_sessions(html)

    if not sessions:
        log.warning("No Saturday sessions found on the page.")
        return

    target_session = None
    for s in sessions:
        log.info(f"  Found: {s['description'][:100]}... (date: {s['date']})")
        if s["date"] == target_sat:
            target_session = s

    if not target_session:
        log.warning(f"  No session found matching target date {target_sat.strftime('%d %b %Y')}.")
        return

    current = target_session["current_signups"]
    maximum = target_session["max_signups"]
    date_str = target_sat.isoformat()

    log.info(f"  📋 Target session: {current}/{maximum} signups")

    alerted_dates = get_alerted_dates()
    if date_str in alerted_dates:
        log.info(f"  ✓ Already alerted for {date_str} — skipping.")
        return

    if current >= SIGNUP_THRESHOLD:
        signup_link = get_signup_link(target_sat)
        log.info(f"  🚨 Threshold reached! Sending alert...")
        log.info(f"  🔗 Signup link: {signup_link}")
        if send_email_alert(target_session, signup_link):
            mark_alerted(date_str)
    else:
        log.info(f"  ✓ Below threshold ({current} < {SIGNUP_THRESHOLD})")


if __name__ == "__main__":
    check_and_alert()
