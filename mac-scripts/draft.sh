#!/bin/zsh
set -euo pipefail

if (( $# != 2 )); then
  print -u2 'usage: draft.sh "SUBJECT" "BODY"'
  exit 64
fi

/usr/bin/osascript - "$1" "$2" <<'APPLESCRIPT'
on run argv
  set messageSubject to item 1 of argv
  set messageBody to item 2 of argv
  tell application "Mail"
    make new outgoing message with properties {subject:messageSubject, content:messageBody, visible:true}
  end tell
end run
APPLESCRIPT
