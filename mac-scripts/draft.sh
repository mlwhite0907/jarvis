#!/bin/zsh
# Jarvis "draft an email" action → creates a GMAIL draft via IMAP (no Mail.app).
# Called by the Pi action_runner as: draft.sh "SUBJECT" "BODY"
# If BODY leads with "To: <name>" (from the "draft an email to X about Y" intent),
# resolve <name> to a real address; otherwise draft to Michael himself.
set -euo pipefail
SUBJECT="${1:-(no subject)}"
BODY="${2:-}"
TO="YOUR_EMAIL@gmail.com"   # default: draft to self; he adds/changes recipient in Gmail

if [[ "$BODY" == "To: "* ]]; then
  firstline="${BODY%%$'\n'*}"
  who="${firstline#To: }"; who="${who## }"; who="${who%% }"
  rest="${BODY#*$'\n'}"; rest="${rest#$'\n'}"
  case "${who:l}" in
    *kayla*)                     TO="kayla@example.com" ;;
    *poole*|*collins*|*kp*)      TO="colleague@example.com" ;;
    (#b)*)                       TO="YOUR_EMAIL@gmail.com"; rest="(intended recipient: ${who})"$'\n\n'"${rest}" ;;
  esac
  BODY="$rest"
fi

exec "$HOME/.life-assistant/draft-email.sh" --to "$TO" --subject "$SUBJECT" --body "$BODY"
