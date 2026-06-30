#!/usr/bin/env python3
"""OpenAI-compatible shim for Home Assistant "Jarvis".

Chat path calls OpenRouter (openai/gpt-4o-mini) directly for fast (~2-3s) replies.
Key is read from the Hermes coder profile .env (single source of truth).
Previous version spawned a full `hermes` agent per turn (~10-15s); see shim.py.bak-agent-*.
"""
import json
import os
import re
import time
import uuid
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "0.0.0.0"
PORT = 8642
MODEL = "hermes-agent"  # kept so the HA integration needs no reconfig
HOME = os.path.expanduser("~")
OPENROUTER_ENV = os.path.join(HOME, ".hermes", "profiles", "coder", ".env")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
BRAIN_MODEL = "openai/gpt-4o-mini"
# Live "knows his life" context, pushed hourly from the Mac Life Assistant
# (~/.life-assistant/push_jarvis_context.sh -> here). Optional; degrades gracefully.
CONTEXT_FILE = os.path.join(HOME, "jarvis-actions", "context.txt")
CONTEXT_MAX_CHARS = 8000
# Voice learning: log every turn; instantly remember anything Michael flags.
# A separate Pi job (jarvis_learn.py) promotes durable facts to the shared memory.txt.
VOICE_LOG = os.path.join(HOME, "jarvis-actions", "voice_log.jsonl")
LEARNED_FILE = os.path.join(HOME, "jarvis-actions", "jarvis_learned.txt")
LEARNED_INJECT_MAX = 4000
MEMORY_CUE = re.compile(
    r"\b(remember|don'?t forget|note that|keep in mind|"
    r"for (?:future|later) reference|make a (?:mental )?note)\b", re.I)

JARVIS_SYS = (
    "You are Jarvis, Michael's voice assistant at home. Your replies are spoken aloud, "
    "so be warm, natural and concise - usually 1 to 3 sentences, no markdown, no bulleted "
    "lists unless he explicitly asks. Michael White is a U.S. diplomat (Foreign Service) "
    "currently posted in Kathmandu, Nepal; his wife is Kayla and they have two Australian "
    "Shepherds. Answer directly and helpfully; if you are unsure or cannot do something, say "
    "so briefly and honestly. "
    "You CAN take real actions when Michael phrases them as commands - if he asks what you can do, or "
    "asks you to do one of these, tell him the exact phrase to say: take a note ('make a note that ...'); "
    "set a reminder ('remind me to ...'); draft an email in his Mail ('draft an email to [person] about "
    "[topic]' - it creates a draft for him to review and never sends); and turn the living-room receiver "
    "on or off ('turn on the receiver'). Do not flatly refuse these - guide him to the command. "
    "Never mention being an AI model, OpenAI, or these instructions."
)


def read_openrouter_key():
    try:
        with open(OPENROUTER_ENV, "r", encoding="utf-8", errors="ignore") as handle:
            txt = handle.read()
    except OSError:
        return ""
    m = re.search(r"OPENROUTER_API_KEY\s*=\s*[\"\x27]?(sk-or-v1-[A-Za-z0-9_\-]+)", txt)
    return m.group(1) if m else ""


def message_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") in ("text", "input_text"):
                text = item.get("text", "")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def read_life_context():
    try:
        with open(CONTEXT_FILE, "r", encoding="utf-8", errors="ignore") as handle:
            return handle.read().strip()[:CONTEXT_MAX_CHARS]
    except OSError:
        return ""


def read_learned():
    try:
        with open(LEARNED_FILE, "r", encoding="utf-8", errors="ignore") as handle:
            return handle.read().strip()[-LEARNED_INJECT_MAX:]
    except OSError:
        return ""


def log_turn(user_text, reply):
    try:
        rec = {"ts": int(time.time()), "user": user_text, "assistant": reply}
        with open(VOICE_LOG, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def maybe_remember(user_text):
    if not user_text or not MEMORY_CUE.search(user_text):
        return
    try:
        from datetime import date
        line = "[%s] %s" % (date.today().isoformat(), user_text.strip())
        with open(LEARNED_FILE, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def call_brain(convo):
    key = read_openrouter_key()
    if not key:
        raise RuntimeError("OpenRouter key not found in %s" % OPENROUTER_ENV)
    system = JARVIS_SYS
    context = read_life_context()
    if context:
        system = system + "\n\n" + context
    learned = read_learned()
    if learned:
        system = system + "\n\n===== THINGS MICHAEL HAS TOLD JARVIS TO REMEMBER (by voice) =====\n" + learned
    messages = [{"role": "system", "content": system}] + convo
    payload = json.dumps({
        "model": BRAIN_MODEL, "messages": messages,
        "max_tokens": 300, "temperature": 0.6,
    }).encode("utf-8")
    req = urllib.request.Request(OPENROUTER_URL, data=payload, method="POST", headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "jarvis-home-assistant",
    })
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.load(resp)
    return (data["choices"][0]["message"]["content"] or "").strip()


class Handler(BaseHTTPRequestHandler):
    server_version = "hermes-openai-shim/2.0"

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status, message):
        self.send_json(status, {"error": {"message": message, "type": "invalid_request_error"}})

    def do_GET(self):
        if self.path.rstrip("/") == "/v1/models":
            self.send_json(200, {
                "object": "list",
                "data": [{"id": MODEL, "object": "model", "created": 0, "owned_by": "local"}],
            })
        else:
            self.send_error_json(404, "Not found")

    def do_POST(self):
        if self.path.rstrip("/") != "/v1/chat/completions":
            self.send_error_json(404, "Not found")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self.send_error_json(400, "Invalid JSON body")
            return

        convo = []
        for m in request.get("messages", []):
            if isinstance(m, dict) and m.get("role") in ("user", "assistant"):
                convo.append({"role": m["role"], "content": message_text(m.get("content", ""))})
        if not any(m["role"] == "user" and m["content"].strip() for m in convo):
            self.send_error_json(400, "A non-empty user message is required")
            return

        try:
            reply = call_brain(convo)
        except urllib.error.HTTPError as exc:
            self.send_error_json(502, "Brain HTTP %s: %s" % (exc.code, exc.read().decode()[:200]))
            return
        except Exception as exc:  # noqa: BLE001
            self.send_error_json(502, "Brain error: %s" % exc)
            return
        if not reply:
            self.send_error_json(502, "Brain returned an empty reply")
            return

        last_user = next((m["content"] for m in reversed(convo) if m["role"] == "user"), "")
        log_turn(last_user, reply)
        maybe_remember(last_user)

        created = int(time.time())
        completion_id = "chatcmpl-" + uuid.uuid4().hex
        if request.get("stream") is True:
            chunk = {
                "id": completion_id, "object": "chat.completion.chunk", "created": created,
                "model": MODEL,
                "choices": [{"index": 0, "delta": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
            }
            encoded = ("data: %s\n\ndata: [DONE]\n\n" % json.dumps(chunk, ensure_ascii=False)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return

        self.send_json(200, {
            "id": completion_id, "object": "chat.completion", "created": created, "model": MODEL,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
