# Jarvis — CURRENT architecture (updated 2026-06-30)

> This supersedes the original README's "Hermes brain" description. The chat brain is now a
> fast hosted model, not the Hermes agent (the agent was ~15s/turn; this is ~2s). All code in
> `pi/` and `mac-scripts/` is the live current source. **No secrets are committed** — keys live
> only on the machines (see "Where secrets live" below). Personal email scrubbed to `YOUR_EMAIL`.

## What Jarvis is now
A self-hosted assistant on a Raspberry Pi that **(1)** talks by voice (Home Assistant Assist),
**(2)** has a polished iPhone+Mac app (Open WebUI), **(3)** knows the user's life (daily brief +
finances + reminders injected as context), **(4)** learns from what the user tells it, and
**(5)** takes real actions (notes, reminders, email drafts, receiver) deterministically.

## The brain — `pi/hermes-openai-shim.py`  (systemd `hermes-openai-shim.service`, port 8642)
- OpenAI-compatible server (`/v1/chat/completions`, model id `hermes-agent`). Both the HA voice
  pipeline AND the Open WebUI app point at it, so they share one brain.
- Calls **OpenRouter `openai/gpt-4o-mini`** directly (~2s). Reads the API key at runtime from
  `~/.hermes/profiles/coder/.env` (NOT in this repo).
- Builds the system prompt = `JARVIS_SYS` persona  +  life context (`~/jarvis-actions/context.txt`)
  +  voice-learned memory (`~/jarvis-actions/jarvis_learned.txt`). Logs every turn to
  `voice_log.jsonl`; instantly remembers anything matching a "remember/don't forget" cue.

## Knows-his-life context — `mac-scripts/push_jarvis_context.sh`  (Mac launchd `com.jarvis.context.push`, hourly)
- Bundles the Life Assistant's daily `brief.txt` (finances/email/calendar/packages) + open
  Reminders + learned `memory.txt`, and `ssh`-pushes it to the Pi as `context.txt`, which the
  shim injects. Daily-fresh for money/email, hourly for reminders.

## Voice learning — `pi/jarvis_learn.py`  (systemd timer `jarvis-learn.timer`, every 3h)
- Reads new `voice_log.jsonl` entries, uses gpt-4o-mini to extract durable facts, dedupes, and
  appends them to the shared `~/.life-assistant/memory.txt` (Mac) via `ssh macgrok` — so a fact
  learned by voice flows into the morning brief too. Prompt is tuned to learn ONLY from what the
  user says, not from the assistant's brief-derived answers.

## Actions (deterministic, not the LLM) — `pi/action_runner.py` + `pi/jarvis-intents.yaml`
- HA custom-sentence intents → Pi action-runner (`:8765`) → Mac scripts via `ssh macgrok`:
  - `mac-scripts/note.sh` → Apple Note. WORKS.
  - `mac-scripts/draft.sh` → Apple Mail draft. DEPRECATED (hangs + needs macOS Automation grant).
  - **Email now uses `mac-scripts/draft-email.py` / `.sh` (Gmail IMAP)** — no Mail.app, no TCC.
    One-time: `mac-scripts/gmail-setup.sh <gmail-app-password>` stores it in the macOS keychain.

## The app — Open WebUI
- Docker on the Pi (`open-webui`, port 3001), env `OPENAI_API_BASE_URL=http://host.docker.internal:8642/v1`,
  `DEFAULT_MODELS=hermes-agent`, `WEBUI_AUTH=false`. Exposed via `tailscale serve --https=8443`
  → `https://<tailnet-host>:8443`. TTS = ElevenLabs ("Hope" voice); STT = browser. Installs as a
  PWA on iPhone/Mac. Because it chats through :8642 it inherits the life-context + learning for free.

## Voice engines (HA Assist pipeline "Jarvis")
- STT: Wyoming Whisper (`:10300`). TTS: ElevenLabs (`tts.elevenlabs_text_to_speech`, voice "Hope",
  model `eleven_multilingual_v2`). IMPORTANT: the voice actually heard is the per-pipeline
  `tts_voice` in HA's `assist_pipeline.pipelines`, which overrides the integration default.

## Where secrets live (NOT in this repo)
- OpenRouter key → `~/.hermes/profiles/coder/.env`
- ElevenLabs key → HA `.storage` (config entry)
- Gmail App Password → macOS keychain (`jarvis-gmail` service)

## How to edit with a web AI (Grok / ChatGPT)
1. Point it at this repo URL, or paste the file you want to change from `pi/` or `mac-scripts/`.
2. Make the change. To deploy: copy the file to the right machine and restart its service:
   - shim: `scp` to `~/hermes-openai-shim/shim.py` on the Pi → `systemctl --user restart hermes-openai-shim.service`
   - learn: `~/jarvis-actions/jarvis_learn.py` on the Pi (timer picks it up)
   - context push: `~/.life-assistant/push_jarvis_context.sh` on the Mac (launchd picks it up)
   - intents: `~/homeassistant/custom_sentences/en/jarvis.yaml` (root-owned → edit via a root docker
     container) → restart Home Assistant.
3. Keep secrets out of any file you commit back here.
