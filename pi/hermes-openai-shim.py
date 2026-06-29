#!/usr/bin/env python3
import json
import os
import subprocess
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = "0.0.0.0"
PORT = 8642
MODEL = "hermes-agent"
HOME = os.path.expanduser("~")
HERMES = os.path.join(HOME, ".local", "bin", "hermes")
KEY_FILE = os.path.join(HOME, "hermes-openai-shim", "key.txt")


def read_optional_key():
    try:
        with open(KEY_FILE, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except FileNotFoundError:
        return ""


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


def clean_reply(stdout):
    lines = stdout.replace("\r\n", "\n").split("\n")
    noise_prefixes = (
        "[hermes]", "hermes:", "profile:", "session:",
        "warning:", "debug:", "info:",
    )
    while lines and (not lines[0].strip() or lines[0].strip().lower().startswith(noise_prefixes)):
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip()


class Handler(BaseHTTPRequestHandler):
    server_version = "hermes-openai-shim/1.0"

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

        read_optional_key()  # Optional local key is deliberately not enforced.
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self.send_error_json(400, "Invalid JSON body")
            return

        messages = request.get("messages", [])
        user_messages = [m for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        if not user_messages:
            self.send_error_json(400, "A user message is required")
            return
        prompt = message_text(user_messages[-1].get("content", "")).strip()
        if not prompt:
            self.send_error_json(400, "The last user message is empty")
            return

        try:
            result = subprocess.run(
                [HERMES, "-p", "coder", "-z", prompt],
                capture_output=True, text=True, timeout=120, check=False,
            )
        except subprocess.TimeoutExpired:
            self.send_error_json(504, "Hermes timed out after 120 seconds")
            return
        except OSError as exc:
            self.send_error_json(502, "Could not start Hermes: %s" % exc)
            return

        reply = clean_reply(result.stdout)
        if result.returncode != 0:
            detail = clean_reply(result.stderr) or "Hermes exited with status %d" % result.returncode
            self.send_error_json(502, detail)
            return
        if not reply:
            self.send_error_json(502, "Hermes returned an empty reply")
            return

        created = int(time.time())
        completion_id = "chatcmpl-" + uuid.uuid4().hex
        if request.get("stream") is True:
            chunk = {
                "id": completion_id, "object": "chat.completion.chunk", "created": created,
                "model": MODEL,
                "choices": [{"index": 0, "delta": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
            }
            body = "data: %s\n\ndata: [DONE]\n\n" % json.dumps(chunk, ensure_ascii=False)
            encoded = body.encode("utf-8")
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
