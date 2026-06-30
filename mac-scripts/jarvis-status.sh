#!/bin/zsh
# jarvis-status — on-demand health check of Michael's whole AGI stack (Mac + Pi).
# Run:  ~/.life-assistant/jarvis-status.sh    (or add: alias jarvis-status="~/.life-assistant/jarvis-status.sh")
PI="mlwhite0907@100.91.48.99"
ok()  { print -P "%F{green}OK%f   $1"; }
bad() { print -P "%F{red}FAIL%f $1"; }
warn(){ print -P "%F{yellow}WARN%f $1"; }
print -P "%F{cyan}===== JARVIS STATUS  ($(date '+%a %b %d %I:%M %p')) =====%f"

# --- Mac launchd jobs ---
for L in com.life.assistant.brief com.life.assistant.watch com.life.assistant.reflect com.jarvis.context.push; do
  line=$(launchctl list | grep -F "$L")
  [[ -n "$line" ]] && { st=$(echo "$line" | awk '{print $2}'); [[ "$st" == "0" || "$st" == "-" ]] && ok "launchd $L (exit ${st})" || warn "launchd $L last exit=$st"; } || bad "launchd $L NOT loaded"
done

# --- Daily brief freshness (expect today) ---
bf="$HOME/.life-assistant/brief.txt"
if [[ -f "$bf" ]]; then
  age=$(( ($(date +%s) - $(stat -f %m "$bf")) / 3600 ))
  (( age <= 26 )) && ok "daily brief fresh (${age}h old)" || warn "daily brief is ${age}h old — did the 7am run fire?"
else bad "brief.txt missing"; fi

# --- Headless-claude token (brief auth) ---
[[ -f "$HOME/.life-assistant/claude_token.env" ]] && ok "headless-claude token present" || bad "claude_token.env MISSING (brief will 401)"

# --- Gmail draft credential ---
[[ -s "$HOME/.life-assistant/.gmail_app_pw" ]] && ok "gmail draft credential present" || warn "gmail app password file missing (email drafts off)"

# --- Reminders sync (count of open Life Admin) ---
n=$(/usr/bin/perl -e 'alarm shift; exec @ARGV' 20 osascript -e 'tell application "Reminders" to return count of (reminders of list "Life Admin" whose completed is false)' 2>/dev/null)
[[ "$n" == <-> ]] && ok "reminders: $n open in Life Admin" || warn "could not read Reminders"

# --- Daily Brief note ---
nd=$(/usr/bin/perl -e 'alarm shift; exec @ARGV' 18 osascript -e 'tell application "Notes" to return (modification date of note "Daily Brief" of account "iCloud") as string' 2>/dev/null)
[[ -n "$nd" ]] && ok "Daily Brief note updated: $nd" || warn "could not read Daily Brief note"

# --- Pi side ---
print -P "%F{cyan}--- Pi ---%f"
pi=$(ssh -o ConnectTimeout=12 -o BatchMode=yes "$PI" '
  for c in homeassistant open-webui wyoming-whisper wyoming-piper pihole; do
    s=$(docker inspect -f "{{.State.Status}}" "$c" 2>/dev/null || echo missing); echo "CONT $c $s"
  done
  echo "SHIM $(systemctl --user is-active hermes-openai-shim.service 2>/dev/null)"
  echo "LEARN $(systemctl --user is-active jarvis-learn.timer 2>/dev/null)"
  r=$(curl -s -m 20 -X POST http://localhost:8642/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"hermes-agent\",\"messages\":[{\"role\":\"user\",\"content\":\"reply with one short word\"}]}")
  echo "BRAIN $(printf "%s" "$r" | python3 -c "import sys,json;print(\"ok\" if json.load(sys.stdin).get(\"choices\") else \"bad\")" 2>/dev/null || echo bad)"
  curl -sk -m 12 -o /dev/null -w "OWUI %{http_code}\n" https://mikesraspberry.tail1de0e3.ts.net:8443
' 2>/dev/null)
echo "$pi" | while read -r tag a b; do
  case "$tag" in
    CONT) [[ "$b" == running ]] && ok "container $a ($b)" || bad "container $a: $b" ;;
    SHIM) [[ "$a" == active ]] && ok "brain shim active" || bad "brain shim $a" ;;
    LEARN) [[ "$a" == active ]] && ok "voice-learning timer active" || warn "learn timer $a" ;;
    BRAIN) [[ "$a" == ok ]] && ok "brain responds" || bad "brain not responding" ;;
    OWUI) [[ "$a" == "200" ]] && ok "app reachable (Tailscale :8443)" || bad "app HTTP $a" ;;
  esac
done
[[ -z "$pi" ]] && bad "could not reach the Pi over Tailscale"
print -P "%F{cyan}===== end =====%f"
