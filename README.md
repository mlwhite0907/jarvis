
> ⚡ **See [CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md)** for the up-to-date system (2026-06-30) — the brain is now fast gpt-4o-mini (not the Hermes agent), plus life-context, voice-learning, Gmail email, and the Open WebUI app.
# Jarvis — home voice assistant (Hermes brain + Home Assistant)

A self-hosted, voice-controlled personal assistant for Michael's home. You talk to it
(iPhone now, ambient room mics later); it answers in a natural voice, controls the home
(Yamaha receiver, speakers), and takes actions (Apple Notes, email drafts) — backed by
**Hermes** (Michael's persistent agent, which knows his life) rather than a generic bot.

This repo documents the build and holds the source/specs so others (incl. Grok) can help.
**No secrets are committed** — tokens/keys/passwords live only on the machines.

## Architecture

```
 You speak ──► HA "Jarvis" Assist pipeline (Home Assistant)
                  │
                  ├─ STT:  Wyoming Whisper        (Pi :10300)        — "ears"
                  ├─ ROUTING (prefer-local):
                  │     • device control + actions ──► HA intents (DETERMINISTIC, reliable)
                  │            "turn on the receiver" → Yamaha MusicCast
                  │            "make a note / draft email" → Pi action-runner → Mac scripts
                  │     • open-ended chat ──► Hermes brain  (via shim, Pi :8642)
                  │            shim wraps:  hermes -p coder -z "<message>"
                  └─ TTS:  ElevenLabs (being wired) — replaces robotic local Piper — "voice"
```

Key design lesson: the free model behind Hermes is great at *talking* but unreliable at
*executing actions*, so **actions + device control are handled deterministically by Home
Assistant intents**, and only open conversation goes to Hermes.

## Where things live
- **Home Assistant**: Docker container `homeassistant` on the Pi, port 8123, onboarded. Config dir `~/homeassistant` (`/config` in container).
- **Voice engines (Pi)**: `wyoming-whisper` (:10300, STT), `wyoming-piper` (:10200, local TTS — being replaced by ElevenLabs).
- **Hermes→OpenAI shim (Pi)**: `~/hermes-openai-shim/shim.py`, systemd user service, :8642. Makes the Hermes *agent* usable as an OpenAI chat model (`hermes-agent`). Source: [`pi/hermes-openai-shim.py`](pi/hermes-openai-shim.py).
- **Action scripts (Mac)**: `~/jarvis-actions/note.sh` (Apple Note), `~/jarvis-actions/draft.sh` (Mail draft, never sends). Source in [`mac-scripts/`](mac-scripts/).
- **Action runner (Pi host, Phase 6)**: HTTP endpoint HA curls → runs the Mac scripts via `ssh macgrok`.
- **Home control**: Yamaha RX-V4A via `yamaha_musiccast` (`media_player.livingroom`); Google Cast (Nest Hubs/speakers).

## Status
- ✅ **Phase 1** — HA installed + onboarded.
- ✅ **Phase 3** — Whisper + Piper voice engines + Hermes shim (chat verified end-to-end).
- ✅ **Phase 4** — HA "Jarvis" Assist pipeline wired (STT→Hermes→TTS); verified Hermes reply.
- ✅ **Phase 5** — Yamaha + Cast added; Mac action scripts built & tested (note + draft work).
- 🔄 **Phase 6** — deterministic HA action/control layer (so notes/email/device control are reliable) — see `pi/phase6_report.txt`.
- ⏳ **Pending** — ElevenLabs TTS (replacing robotic Piper, awaiting API key); ambient room mics (HA Voice Preview Edition) as the later upgrade from iPhone-only.

## Access
- Pi (always-on host): `ssh mlwhite0907@100.91.48.99` (Tailscale).
- HA app: log in as `michael` (credentials stored locally, not in this repo).
- Build was executed largely by **Codex** (SSH executor) under Claude's orchestration.

## Repo contents
- `specs/` — the phase build specs handed to Codex.
- `mac-scripts/` — the Apple Notes / Mail-draft action scripts.
- `pi/` — the Hermes→OpenAI shim source + per-phase build reports.
