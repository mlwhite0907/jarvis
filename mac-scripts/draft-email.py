#!/usr/bin/env python3
"""
Standalone Gmail draft creator — uses IMAP APPEND to [Gmail]/Drafts.
No Google Cloud Console required; uses a Gmail App Password stored in macOS keychain.

Usage:
  python3 draft-email.py --to 'someone@example.com' --subject 'Hi' --body 'Body text'
  python3 draft-email.py --to X --subject Y --body Z [--reply-to-id <gmail-message-id>]

Setup (one-time):
  1. Enable 2-Step Verification on your Google account if not already:
       https://myaccount.google.com/security
  2. Create an App Password:
       https://myaccount.google.com/apppasswords
       → Select app: Mail, device: Mac → Generate
       Copy the 16-character password (spaces don't matter).
  3. Store it: ~/.life-assistant/gmail-setup.sh <app-password-without-spaces>
       OR manually: security add-generic-password -a YOUR_EMAIL@gmail.com -s jarvis-gmail -w '<app-pw>'
"""
import argparse
import imaplib
import os
import subprocess
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

GMAIL_USER = "YOUR_EMAIL@gmail.com"
KEYCHAIN_SERVICE = "jarvis-gmail"
DRAFTS_FOLDER = "[Gmail]/Drafts"
IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993


def get_app_password():
    """Read the App Password from macOS keychain."""
    r = subprocess.run(
        ["security", "find-generic-password", "-a", GMAIL_USER, "-s", KEYCHAIN_SERVICE, "-w"],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print("ERROR: Gmail App Password not found in keychain.", file=sys.stderr)
        print("Run:  ~/.life-assistant/gmail-setup.sh <your-app-password>", file=sys.stderr)
        print("See:  https://myaccount.google.com/apppasswords", file=sys.stderr)
        sys.exit(1)
    return r.stdout.strip()


def create_draft(to: str, subject: str, body: str, reply_to_id=None) -> str:
    """Append a draft to Gmail's Drafts folder via IMAP. Returns a status string."""
    password = get_app_password()

    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["From"] = GMAIL_USER
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    if reply_to_id:
        msg["In-Reply-To"] = reply_to_id
        msg["References"] = reply_to_id
    msg.attach(MIMEText(body, "plain"))

    raw = msg.as_bytes()

    imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    try:
        imap.login(GMAIL_USER, password)
        result = imap.append(DRAFTS_FOLDER, r"\Draft", None, raw)
        if result[0] != "OK":
            raise RuntimeError(f"IMAP APPEND failed: {result}")
        # Extract the UID from the append response if present (e.g. [APPENDUID 1 12345])
        uid_info = result[1][0].decode() if result[1] else ""
        return f"Draft created OK — {uid_info or 'no UID returned'}"
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser(description="Create a Gmail draft via IMAP")
    ap.add_argument("--to", required=True, help="Recipient email address")
    ap.add_argument("--subject", required=True, help="Email subject")
    ap.add_argument("--body", required=True, help="Email body text")
    ap.add_argument("--reply-to-id", default=None, help="Gmail Message-ID to reply to")
    args = ap.parse_args()

    result = create_draft(args.to, args.subject, args.body, args.reply_to_id)
    print(result)


if __name__ == "__main__":
    main()
