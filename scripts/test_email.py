"""Send one test email to yourself through Yahoo SMTP using YAHOO_EMAIL / YAHOO_APP_PASSWORD from .env.
Prints pass/fail only, never the password. Run: .venv/bin/python scripts/test_email.py"""
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

env = dict(l.split("=", 1) for l in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines()
           if "=" in l and not l.startswith("#"))
user, pw = env.get("YAHOO_EMAIL", "").strip(), env.get("YAHOO_APP_PASSWORD", "").replace(" ", "").strip()
if not user or not pw:
    sys.exit("FAIL: set YAHOO_EMAIL and YAHOO_APP_PASSWORD in .env")

msg = EmailMessage()
msg["From"], msg["To"], msg["Subject"] = user, user, "Adinkra Overseer: test email"
msg.set_content("If you can read this, email sending from the Adinkra ecosystem works.")
try:
    with smtplib.SMTP_SSL("smtp.mail.yahoo.com", 465, context=ssl.create_default_context(), timeout=30) as s:
        s.login(user, pw)
        s.send_message(msg)
    print("PASS: test email sent to", user)
except smtplib.SMTPAuthenticationError:
    sys.exit("FAIL: Yahoo rejected the login (use an app password, and check the address)")
except Exception as e:
    sys.exit(f"FAIL: {type(e).__name__}")
