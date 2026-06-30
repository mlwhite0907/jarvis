#!/usr/bin/env zsh
# Standalone on-demand Gmail drafter — callable from the Pi via: ssh macgrok "~/.life-assistant/draft-email.sh ..."
# Creates a draft in Gmail using IMAP (no Mail.app, no macOS automation).
#
# Usage:
#   draft-email.sh --to 'email@example.com' --subject 'Subject' --body 'Body text'
#   draft-email.sh --to X --subject Y --body Z [--reply-to-id <gmail-message-id>]
#
# Pi integration:
#   ssh macgrok "~/.life-assistant/draft-email.sh --to 'addr' --subject 'Subj' --body 'Msg'"
#
# First-time setup (one-time, on the Mac):
#   ~/.life-assistant/gmail-setup.sh <your-16-char-gmail-app-password>

export PATH="/opt/homebrew/bin:$HOME/Library/Python/3.9/bin:/usr/bin:/bin:/usr/local/bin:$PATH"
cd "$(dirname "$0")"

exec python3 draft-email.py "$@"
