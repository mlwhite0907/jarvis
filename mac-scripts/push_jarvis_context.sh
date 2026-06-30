#!/bin/bash
# push_jarvis_context.sh — bundle the Life Assistant's current knowledge into a
# compact snapshot and push it to the Pi so the Jarvis VOICE assistant "knows
# what's going on" (today's brief, finances, reminders, packages, emails).
# Deterministic (no LLM, no new auth). Scheduled hourly via launchd
# com.jarvis.context.push; also safe to run by hand.
set -o pipefail
LA="$HOME/.life-assistant"
PI="mlwhite0907@100.91.48.99"
TS="$(date '+%A %B %-d %Y, %-I:%M %p')"

read_reminders() {
  /usr/bin/perl -e 'alarm shift; exec @ARGV' 25 osascript -e '
set out to ""
tell application "Reminders"
  repeat with L in lists
    set ln to name of L
    repeat with r in (reminders of L whose completed is false)
      set dd to ""
      try
        if due date of r is not missing value then set dd to " (due " & (due date of r as string) & ")"
      end try
      set out to out & "- [" & ln & "] " & (name of r) & dd & linefeed
    end repeat
  end repeat
end tell
return out' 2>/dev/null
}

CTX="$(mktemp)"
{
  echo "MICHAEL'S CURRENT LIFE CONTEXT — snapshot as of $TS (Kathmandu time)."
  echo "Use this to answer what is going on in his life: his day, money, bills, tasks, packages, deliveries, and emails. Speak naturally and answer ONLY what he asked - never read the whole thing aloud. If he asks something not covered here, say you do not have that detail yet."
  echo
  echo "===== DURABLE FACTS LEARNED ABOUT MICHAEL (shared long-term memory) ====="
  if [ -f "$LA/memory.txt" ]; then grep -vE '^#|^[[:space:]]*$' "$LA/memory.txt"; else echo "(none yet)"; fi
  echo
  echo "===== TODAY'S BRIEF ====="
  if [ -f "$LA/brief.txt" ]; then cat "$LA/brief.txt"; else echo "(no daily brief generated yet)"; fi
  echo
  echo "===== OPEN REMINDERS & TASKS ====="
  REM="$(read_reminders)"
  if [ -n "$REM" ]; then printf '%s\n' "$REM"; else echo "(no open reminders, or Reminders was unavailable)"; fi
  echo
  echo "===== URGENT (same-day flags) ====="
  if [ -f "$LA/urgent.json" ] && [ "$(tr -d '[:space:]' < "$LA/urgent.json")" != "[]" ]; then cat "$LA/urgent.json"; else echo "(nothing urgent right now)"; fi
} > "$CTX"

if cat "$CTX" | ssh -o ConnectTimeout=15 -o BatchMode=yes "$PI" 'cat > ~/jarvis-actions/context.txt'; then
  echo "pushed $(wc -c < "$CTX") bytes to Pi at $TS"
else
  echo "push FAILED at $TS" >&2
  rm -f "$CTX"; exit 1
fi
rm -f "$CTX"
