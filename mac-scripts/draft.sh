#!/bin/zsh
# Jarvis "draft an email" action → creates a GMAIL draft via IMAP (no Mail.app, no TCC).
# Called by the Pi action_runner as: draft.sh "SUBJECT" "BODY"
set -euo pipefail
SUBJECT="${1:-(no subject)}"
BODY="${2:-}"
exec "$HOME/.life-assistant/draft-email.sh" --to "YOUR_EMAIL@gmail.com" --subject "$SUBJECT" --body "$BODY"
