#!/bin/zsh
set -euo pipefail

if (( $# != 1 )); then
  print -u2 'usage: note.sh "TEXT"'
  exit 64
fi

/usr/bin/osascript - "$1" <<'APPLESCRIPT'
on run argv
  set noteText to item 1 of argv
  tell application "Notes"
    set targetAccount to first account whose name is "iCloud"
    if not (exists folder "Jarvis" of targetAccount) then
      make new folder at targetAccount with properties {name:"Jarvis"}
    end if
    set targetFolder to folder "Jarvis" of targetAccount
    make new note at targetFolder with properties {body:noteText}
  end tell
end run
APPLESCRIPT
