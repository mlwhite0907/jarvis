#!/usr/bin/env python3
"""jarvis_learn.py — promote durable facts from Jarvis voice logs into Michael's
shared long-term memory (~/.life-assistant/memory.txt on the Mac).

Runs on the Pi (systemd timer jarvis-learn.timer, ~every 3h). Reads new entries
from voice_log.jsonl since a cursor, asks gpt-4o-mini to extract lasting facts,
dedupes against existing memory, and appends them via `ssh macgrok`. The shared
memory.txt is read by the morning brief and curated by the weekly reflect loop,
so a fact Jarvis learns by voice flows into the whole assistant.
"""
import json
import os
import re
import subprocess
import urllib.request
import urllib.error
from datetime import date

HOME = os.path.expanduser("~")
VOICE_LOG = os.path.join(HOME, "jarvis-actions", "voice_log.jsonl")
CURSOR = os.path.join(HOME, "jarvis-actions", ".learn_cursor")
OPENROUTER_ENV = os.path.join(HOME, ".hermes", "profiles", "coder", ".env")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-4o-mini"
MAC = "macgrok"
MAC_MEMORY = "~/.life-assistant/memory.txt"
MAX_EXCHANGES = 50


def read_key():
    try:
        txt = open(OPENROUTER_ENV, encoding="utf-8", errors="ignore").read()
    except OSError:
        return ""
    m = re.search(r"OPENROUTER_API_KEY\s*=\s*[\"\x27]?(sk-or-v1-[A-Za-z0-9_\-]+)", txt)
    return m.group(1) if m else ""


def read_new_exchanges():
    if not os.path.exists(VOICE_LOG):
        return [], 0
    lines = open(VOICE_LOG, encoding="utf-8", errors="ignore").read().splitlines()
    try:
        done = int(open(CURSOR).read().strip())
    except (OSError, ValueError):
        done = 0
    exch = []
    for ln in lines[done:]:
        try:
            rec = json.loads(ln)
        except ValueError:
            continue
        u = (rec.get("user") or "").strip()
        a = (rec.get("assistant") or "").strip()
        if u:
            exch.append("Michael: " + u + (("\nJarvis: " + a) if a else ""))
    return exch[-MAX_EXCHANGES:], len(lines)


def mac_memory():
    try:
        out = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=12", "-o", "BatchMode=yes", MAC, "cat " + MAC_MEMORY],
            capture_output=True, text=True, timeout=30)
        return out.stdout or ""
    except Exception:
        return ""


def extract(exchanges, existing):
    k = read_key()
    if not k:
        raise SystemExit("no openrouter key")
    system = (
        "You maintain Michael's long-term memory. From these voice exchanges between Michael (user) "
        "and his assistant Jarvis, extract ONLY durable, lasting facts worth remembering for months: "
        "preferences, life facts, people, plans, decisions, standing instructions. "
        "CRITICAL: Learn ONLY from what MICHAEL himself says (his own statements, preferences, "
        "corrections, instructions) - NEVER from Jarvis's answers. Do NOT extract anything already "
        "tracked by his daily brief (his finances, bills, packages, deliveries, the dog/pet-import "
        "logistics) - those refresh daily elsewhere. IGNORE one-off "
        "questions, small talk, weather, and anything transient. PRIORITIZE anything he explicitly asked "
        "to remember. Do NOT repeat facts already known (listed below). Output each NEW durable fact on "
        "its own line as plain fact text ONLY - no date, no brackets, no bullets, no numbering. "
        "If nothing is new and durable, output exactly: NONE\n\n"
        "ALREADY KNOWN (do not repeat):\n" + (existing.strip() or "(none)"))
    body = json.dumps({
        "model": MODEL, "max_tokens": 400, "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": "VOICE EXCHANGES:\n" + "\n\n".join(exchanges)},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(OPENROUTER_URL, data=body, method="POST", headers={
        "Authorization": "Bearer " + k, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.load(resp)
    return (data["choices"][0]["message"]["content"] or "").strip()


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def main():
    exch, total = read_new_exchanges()
    if not exch:
        with open(CURSOR, "w") as f:
            f.write(str(total))
        print("no new exchanges")
        return
    existing = mac_memory()
    out = extract(exch, existing)
    facts = []
    for ln in out.splitlines():
        s = ln.strip()
        if not s or s.upper() == "NONE":
            continue
        s = re.sub(r"^[-*•\d.\)\s]+", "", s)          # leading bullets/numbering
        s = re.sub(r"^\[\d{4}-\d{2}-\d{2}\]\s*", "", s)     # a leading [date] the model may add
        s = s.strip()
        if s:
            facts.append(s)
    exist_norm = norm(existing)
    add = []
    for f in facts:
        nf = norm(f)
        if len(nf) < 8 or nf in exist_norm or any(norm(x) == nf for x in add):
            continue
        add.append(f)
    if add:
        today = date.today().isoformat()
        block = "".join("[%s] %s\n" % (today, f) for f in add)
        subprocess.run(
            ["ssh", "-o", "ConnectTimeout=12", "-o", "BatchMode=yes", MAC, "cat >> " + MAC_MEMORY],
            input=block, text=True, timeout=30)
        print("added %d fact(s):\n%s" % (len(add), block.strip()))
    else:
        print("nothing new durable")
    with open(CURSOR, "w") as f:
        f.write(str(total))


if __name__ == "__main__":
    main()
