#!/usr/bin/env python3
import json
import shlex
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SSH_BASE = ["ssh", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes", "macgrok"]
MAX_BODY = 65536


def run_mac(script, *args):
    remote = "~/jarvis-actions/" + script
    if args:
        remote += " " + " ".join(shlex.quote(value) for value in args)
    completed = subprocess.run(
        SSH_BASE + [remote], capture_output=True, text=True, timeout=45, check=False
    )
    detail = (completed.stdout or completed.stderr or "completed").strip()[-2000:]
    if completed.returncode != 0:
        raise RuntimeError(f"Mac action failed ({completed.returncode}): {detail}")
    return detail


class Handler(BaseHTTPRequestHandler):
    server_version = "JarvisActions/1.0"

    def send_json(self, status, payload):
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > MAX_BODY:
                raise ValueError("invalid request size")
            data = json.loads(self.rfile.read(length))
            if self.path == "/note":
                text = data.get("text")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("text is required")
                detail = run_mac("note.sh", text.strip())
            elif self.path == "/draft":
                subject, body = data.get("subject"), data.get("body")
                if not isinstance(subject, str) or not subject.strip():
                    raise ValueError("subject is required")
                if not isinstance(body, str) or not body.strip():
                    raise ValueError("body is required")
                detail = run_mac("draft.sh", subject.strip(), body.strip())
            else:
                self.send_json(404, {"ok": False, "detail": "unknown route"})
                return
            self.send_json(200, {"ok": True, "detail": detail})
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {"ok": False, "detail": str(exc)})
        except subprocess.TimeoutExpired:
            self.send_json(504, {"ok": False, "detail": "Mac action timed out"})
        except Exception as exc:
            self.send_json(502, {"ok": False, "detail": str(exc)})

    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} - {fmt % args}", flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8765), Handler).serve_forever()
