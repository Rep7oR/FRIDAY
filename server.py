#!/usr/bin/env python3
"""Serves the viewer/ folder and a POST /chat endpoint backed by an LLM.

Run: python3 server.py
Then open http://127.0.0.1:4700 in Chrome.

config.json (project root, NEVER inside viewer/) holds the provider/key/model.
It is not served to the browser — this handler only ever serves files under
viewer/, and /chat only ever returns the answer text + note indexes, never
the key. If config.json doesn't exist yet, one is created automatically with
"provider": "claude_cli", which shells out to the `claude` CLI so /chat runs
on your existing Claude Code subscription with zero extra setup and no
external API key. Other providers: "pollinations" (a free, no-key text API —
its shared anonymous quota can run dry) or "anthropic" (paste a real
api_key to call the Messages API directly).
"""
import http.server
import json
import os
import re
import secrets
import shutil
import socketserver
import subprocess
import urllib.error
import urllib.request

PORT = 4700
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
VIEWER_DIR = os.path.join(ROOT_DIR, "viewer")
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")
GRAPH_DATA_PATH = os.path.join(VIEWER_DIR, "graph-data.js")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
POLLINATIONS_API_URL = "https://text.pollinations.ai/openai"
TOP_N_NOTES = 6
MAX_HISTORY_TURNS = 6  # user+assistant pairs kept per session
PROVIDERS = ("claude_cli", "pollinations", "anthropic")

DEFAULT_CONFIG = {
    "provider": "claude_cli",
    "api_key": "PUT-YOUR-KEY-HERE",
    "model": "claude-opus-4-8",
    "free_model": "openai",
}

WORD_RE = re.compile(r"[a-z0-9']+")

# session_id -> list of {"role": "user"|"assistant", "content": str}
SESSIONS = {}


def load_config():
    if not os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"No config.json found — created one at {CONFIG_PATH} using provider={DEFAULT_CONFIG['provider']!r}.")
        return dict(DEFAULT_CONFIG)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    for key, value in DEFAULT_CONFIG.items():
        config.setdefault(key, value)
    return config


def load_graph():
    with open(GRAPH_DATA_PATH, "r", encoding="utf-8") as f:
        raw = f.read()
    raw = raw.strip()
    prefix = "const GRAPH ="
    if raw.startswith(prefix):
        raw = raw[len(prefix):]
    raw = raw.rstrip(";").strip()
    return json.loads(raw)


def tokenize(text):
    return WORD_RE.findall(text.lower())


def score_notes(question, nodes, note_bodies):
    q_words = set(tokenize(question))
    if not q_words:
        return []

    scored = []
    for node in nodes:
        title_words = set(tokenize(node["label"]))
        body_words = set(tokenize(note_bodies.get(node["id"], node.get("excerpt", ""))))

        score = 0
        for w in q_words:
            if w in title_words:
                score += 3
            if w in body_words:
                score += 1

        scored.append((score, node))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:TOP_N_NOTES]


def read_note_bodies(nodes):
    bodies = {}
    for node in nodes:
        path = node.get("path")
        if not path or not os.path.isfile(path):
            bodies[node["id"]] = node.get("excerpt", "")
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                bodies[node["id"]] = f.read()
        except OSError:
            bodies[node["id"]] = node.get("excerpt", "")
    return bodies


def build_system_prompt(top_notes, note_bodies):
    sections = []
    for _score, node in top_notes:
        body = note_bodies.get(node["id"], node.get("excerpt", ""))
        sections.append(f"### {node['label']}\n{body}")
    notes_blob = "\n\n".join(sections) if sections else "(no notes matched)"

    return (
        "You are answering questions using ONLY the notes provided below. "
        "Answer in 2-3 sentences. If the notes don't cover the question, "
        "say so plainly instead of guessing or using outside knowledge.\n\n"
        f"NOTES:\n\n{notes_blob}"
    )


def call_anthropic(config, system_prompt, history, question):
    api_key = config.get("api_key", "")
    if not api_key or api_key == "PUT-YOUR-KEY-HERE":
        return None, "model not configured — paste your API key into config.json"

    messages = list(history) + [{"role": "user", "content": question}]
    payload = json.dumps(
        {
            "model": config.get("model", "claude-opus-4-8"),
            "max_tokens": 400,
            "system": system_prompt,
            "messages": messages,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=payload,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        return None, f"Anthropic API error {e.code}: {detail[:300]}"
    except urllib.error.URLError as e:
        return None, f"Could not reach Anthropic API: {e.reason}"

    try:
        answer = "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        ).strip()
    except (KeyError, TypeError):
        answer = ""

    if not answer:
        return None, "Anthropic API returned no answer text."

    return answer, None


def call_pollinations(config, system_prompt, history, question):
    messages = (
        [{"role": "system", "content": system_prompt}]
        + list(history)
        + [{"role": "user", "content": question}]
    )
    payload = json.dumps(
        {
            "model": config.get("free_model", "openai"),
            "messages": messages,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        POLLINATIONS_API_URL,
        data=payload,
        method="POST",
        headers={
            "content-type": "application/json",
            # Pollinations sits behind Cloudflare, which blocks the default
            # "Python-urllib/x.y" user agent (error 1010). A normal browser
            # UA gets through.
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        return None, f"Pollinations API error {e.code}: {detail[:300]}"
    except urllib.error.URLError as e:
        return None, f"Could not reach Pollinations API: {e.reason}"
    except TimeoutError:
        return None, "Pollinations API timed out — try again."

    try:
        answer = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        answer = ""

    if not answer:
        return None, "Pollinations API returned no answer text."

    return answer, None


def call_claude_cli(config, system_prompt, history, question):
    claude_path = shutil.which("claude")
    if not claude_path:
        return None, (
            "'claude' CLI not found on PATH. Install Claude Code, or switch "
            "config.json's \"provider\" to \"pollinations\" or \"anthropic\"."
        )

    transcript = [f"SYSTEM INSTRUCTIONS:\n{system_prompt}", ""]
    for turn in history:
        speaker = "User" if turn["role"] == "user" else "Assistant"
        transcript.append(f"{speaker}: {turn['content']}")
    transcript.append(f"User: {question}")
    full_prompt = "\n".join(transcript)

    try:
        # On Windows, `claude` is usually a .cmd shim that CreateProcess
        # can't launch directly without going through the shell; on POSIX
        # the resolved path runs fine without one. Either way the prompt
        # goes in via stdin, so there's no command-line quoting to worry
        # about.
        use_shell = os.name == "nt"
        result = subprocess.run(
            "claude -p" if use_shell else [claude_path, "-p"],
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=60,
            shell=use_shell,
        )
    except subprocess.TimeoutExpired:
        return None, "claude -p timed out after 60s."
    except OSError as e:
        return None, f"Failed to run claude CLI: {e}"

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        return None, f"claude -p failed: {detail[:300]}"

    answer = result.stdout.strip()
    if not answer:
        return None, "claude -p returned no output."

    return answer, None


def call_llm(config, system_prompt, history, question):
    provider = config.get("provider", "claude_cli")
    api_key = config.get("api_key", "")

    if provider == "anthropic" and api_key and api_key != "PUT-YOUR-KEY-HERE":
        return call_anthropic(config, system_prompt, history, question)

    if provider == "pollinations":
        return call_pollinations(config, system_prompt, history, question)

    return call_claude_cli(config, system_prompt, history, question)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=VIEWER_DIR, **kwargs)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")

    def _get_session_id(self):
        cookie = self.headers.get("Cookie", "")
        match = re.search(r"jarvis_session=([a-f0-9]+)", cookie)
        if match:
            return match.group(1), False
        return secrets.token_hex(16), True

    def _write_json(self, payload, status=200):
        body_bytes = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_GET(self):
        if self.path == "/provider":
            config = load_config()
            self._write_json(
                {"provider": config.get("provider", "claude_cli"), "options": list(PROVIDERS)}
            )
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/provider":
            self._handle_set_provider()
            return
        if self.path != "/chat":
            self.send_error(404, "Not found")
            return

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        question = (body.get("message") or "").strip()
        if not question:
            self.send_error(400, "Missing 'message'")
            return

        session_id, is_new = self._get_session_id()
        history = SESSIONS.setdefault(session_id, [])

        config = load_config()
        graph = load_graph()
        nodes = graph["nodes"]
        note_bodies = read_note_bodies(nodes)

        top_notes = score_notes(question, nodes, note_bodies)
        system_prompt = build_system_prompt(top_notes, note_bodies)

        answer, error = call_llm(config, system_prompt, history, question)

        if error:
            response_payload = {"answer": error, "nodes": []}
        else:
            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": answer})
            del history[: max(0, len(history) - MAX_HISTORY_TURNS * 2)]

            response_payload = {
                "answer": answer,
                "nodes": [node["id"] for _score, node in top_notes if _score > 0],
            }

        body_bytes = json.dumps(response_payload).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        if is_new:
            self.send_header("Set-Cookie", f"jarvis_session={session_id}; Path=/; HttpOnly")
        self.end_headers()
        self.wfile.write(body_bytes)

    def _handle_set_provider(self):
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        provider = body.get("provider")
        if provider not in PROVIDERS:
            self.send_error(400, f"Unknown provider {provider!r}; expected one of {PROVIDERS}")
            return

        # Only the provider field changes here -- api_key/model/free_model are never
        # touched by this endpoint, so switching providers in the UI can't clobber a
        # key you've already pasted in.
        config = load_config()
        config["provider"] = provider
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        print(f"Provider switched to {provider!r}.")
        self._write_json({"provider": provider})


def main():
    if not os.path.isdir(VIEWER_DIR):
        raise SystemExit(f"viewer/ folder not found at {VIEWER_DIR} — run build.py first.")

    config = load_config()

    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Serving {VIEWER_DIR} at http://127.0.0.1:{PORT}")
        print(f"POST /chat is live using provider={config.get('provider')!r}.")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
