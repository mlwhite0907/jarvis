#!/usr/bin/env zsh
# One-time setup: store your Gmail App Password so Jarvis can create Gmail drafts.
# Writes BOTH a chmod-600 file (used headlessly by ssh + launchd) AND the macOS keychain.
# Usage: ./gmail-setup.sh <16-char-app-password>   (spaces are ignored)
set -euo pipefail

GMAIL_USER="YOUR_EMAIL@gmail.com"
KEYCHAIN_SERVICE="jarvis-gmail"
PWFILE="$HOME/.life-assistant/.gmail_app_pw"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <app-password>"
  echo "Get one at: https://myaccount.google.com/apppasswords  (app: Mail)"
  exit 1
fi

APP_PW="${1// /}"   # Google shows it with spaces; strip them
if [[ ${#APP_PW} -ne 16 ]]; then
  echo "WARNING: App Password should be 16 chars; got ${#APP_PW}. Continuing."
fi

# 1) chmod-600 file — this is what works from ssh/launchd (keychain does NOT)
printf '%s' "$APP_PW" > "$PWFILE"
chmod 600 "$PWFILE"

# 2) keychain too (for interactive use)
security delete-generic-password -a "$GMAIL_USER" -s "$KEYCHAIN_SERVICE" 2>/dev/null || true
security add-generic-password -a "$GMAIL_USER" -s "$KEYCHAIN_SERVICE" -w "$APP_PW"

echo "Stored App Password in $PWFILE (chmod 600) and macOS keychain."
echo "Testing IMAP connection..."
GMAIL_APP_PASSWORD="$APP_PW" python3 - <<'PYEOF'
import imaplib, os
pw = os.environ["GMAIL_APP_PASSWORD"]
try:
    m = imaplib.IMAP4_SSL("imap.gmail.com", 993); m.login("YOUR_EMAIL@gmail.com", pw); m.logout()
    print("SUCCESS: Gmail IMAP login worked.")
except Exception as e:
    print(f"FAILED: {e}"); raise SystemExit(1)
PYEOF
