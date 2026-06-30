#!/usr/bin/env zsh
# One-time setup: store your Gmail App Password in the macOS keychain.
# Usage: ./gmail-setup.sh <16-char-app-password>   (spaces are ignored)
#
# After running this once, draft-email.sh and draft-email.py will work
# without any further credential prompts.

set -euo pipefail

GMAIL_USER="YOUR_EMAIL@gmail.com"
KEYCHAIN_SERVICE="jarvis-gmail"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <app-password>"
  echo ""
  echo "Get an App Password at: https://myaccount.google.com/apppasswords"
  echo "  → Select app: Mail, device type: Mac → Generate"
  echo "  → Copy the 16-character password (remove spaces)"
  exit 1
fi

# Strip spaces from the password (Google shows it with spaces for readability)
APP_PW="${1// /}"

if [[ ${#APP_PW} -ne 16 ]]; then
  echo "WARNING: App Password should be 16 characters; got ${#APP_PW}. Continuing anyway."
fi

# Store in keychain (updates if already exists)
security delete-generic-password -a "$GMAIL_USER" -s "$KEYCHAIN_SERVICE" 2>/dev/null || true
security add-generic-password -a "$GMAIL_USER" -s "$KEYCHAIN_SERVICE" -w "$APP_PW"

echo "Stored Gmail App Password in keychain under '$KEYCHAIN_SERVICE'."
echo "Testing connection..."

python3 - <<PYEOF
import imaplib, subprocess, sys

pw = subprocess.run(
    ["security","find-generic-password","-a","YOUR_EMAIL@gmail.com","-s","jarvis-gmail","-w"],
    capture_output=True, text=True
).stdout.strip()

try:
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    imap.login("YOUR_EMAIL@gmail.com", pw)
    imap.logout()
    print("SUCCESS: Gmail IMAP login worked.")
except Exception as e:
    print(f"FAILED: {e}", file=sys.stderr)
    print("Check the App Password and that IMAP is enabled in Gmail settings.", file=sys.stderr)
    sys.exit(1)
PYEOF
