"""
SubZero Mobile Server
═════════════════════
HTTP server that serves the SubZero mobile PWA and bridges
phone messages to the local Ollama AI engine.

Run:  python sz_server.py
Then scan the QR code or open http://<your-ip>:8008 on your phone.
"""

import os
import sys
import json
import socket
import threading
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8008
OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
MOBILE_DIR = Path(__file__).parent / "mobile"

try:
    from sz_runtime import ToolRuntime
    HAS_RUNTIME = True
except ImportError:
    HAS_RUNTIME = False

_conversations: dict[str, list[dict]] = {}

def _get_history(sid):
    if sid not in _conversations:
        _conversations[sid] = []
    return _conversations[sid]

def _add_msg(sid, role, content):
    h = _get_history(sid)
    h.append({"role": role, "content": content, "ts": datetime.now().isoformat()})
    if len(h) > 40:
        _conversations[sid] = h[-40:]

def ollama_generate(prompt, model=None):
    model = model or DEFAULT_MODEL
    try:
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate", data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode())
        return data.get("response", "").strip() or "[No response]"
    except urllib.error.URLError:
        return "Ollama is offline. Run 'ollama serve' on your PC."
    except Exception as e:
        return f"Error: {e}"

def is_ollama_online():
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False

def _build_prompt(sid, user_msg, model):
    tp = ""
    if HAS_RUNTIME:
        tp = ToolRuntime().get_system_prompt() + "\n\n"
    system = (
        "You are Spine Rip, the SubZero AI assistant.\n"
        "You run LOCALLY using Ollama (" + model + "). No cloud, no API keys.\n\n"
        + tp + "Be concise and helpful. Format code with backticks.\n")
    hist = _get_history(sid)
    conv = []
    for m in hist[-10:]:
        who = "User" if m["role"] == "user" else "Spine Rip"
        conv.append(f"{who}: {m['content']}")
    conv.append(f"User: {user_msg}")
    return system + "\n\n" + "\n".join(conv) + "\n\nSpine Rip:"

class SubZeroHandler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(MOBILE_DIR), **kw)

    def log_message(self, fmt, *a):
        msg = fmt % a
        if "/api/" in msg:
            print(f"  [API] {msg}")

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/api/status":
            self._j({"ok": True, "ollama": is_ollama_online(), "model": DEFAULT_MODEL,
                      "tools": HAS_RUNTIME, "tool_count": 31 if HAS_RUNTIME else 0})
        else:
            if p == "/":
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self):
        p = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n).decode() if n else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}
        if p == "/api/chat":
            self._chat(data)
        elif p == "/api/clear":
            _conversations[data.get("session", "default")] = []
            self._j({"ok": True})
        else:
            self._j({"error": "Not found"}, 404)

    def _chat(self, data):
        msg = data.get("message", "").strip()
        sid = data.get("session", "default")
        model = data.get("model", DEFAULT_MODEL)
        if not msg:
            self._j({"error": "No message"}, 400)
            return
        _add_msg(sid, "user", msg)
        response = ollama_generate(_build_prompt(sid, msg, model), model)
        _add_msg(sid, "assistant", response)
        tools = []
        if HAS_RUNTIME:
            rt = ToolRuntime()
            calls = rt.parse(response)
            if calls:
                for r in rt.execute_all(calls):
                    tools.append({"tool": r.tool_name, "success": r.success, "output": r.output[:1000]})
        self._j({"ok": True, "response": response, "tools": tools, "model": model})

    def _j(self, data, code=200):
        b = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"

_server = None
_server_thread = None

def start_server(port=PORT):
    global _server, _server_thread
    if _server_thread and _server_thread.is_alive():
        return False, "Already running."
    try:
        _server = HTTPServer(("0.0.0.0", port), SubZeroHandler)
        _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
        _server_thread.start()
        return True, f"http://{get_local_ip()}:{port}"
    except Exception as e:
        return False, str(e)

def stop_server():
    global _server, _server_thread
    if _server:
        _server.shutdown()
        _server = None
        _server_thread = None

if __name__ == "__main__":
    ip = get_local_ip()
    url = f"http://{ip}:{PORT}"
    print("=" * 52)
    print("  S U B - Z E R O   M O B I L E   S E R V E R")
    print("=" * 52)
    print(f"\n  Phone:   {url}")
    print(f"  Local:   http://localhost:{PORT}")
    print(f"  Model:   {DEFAULT_MODEL}")
    print(f"  Ollama:  {'Online' if is_ollama_online() else 'OFFLINE'}")
    print(f"  Tools:   {'31 loaded' if HAS_RUNTIME else 'N/A'}")
    print(f"\n  Same WiFi -> type URL on phone or scan QR")
    print("  Ctrl+C to stop")
    print("=" * 52)
    try:
        HTTPServer(("0.0.0.0", PORT), SubZeroHandler).serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    except OSError as e:
        if "10048" in str(e) or "in use" in str(e).lower():
            print(f"Port {PORT} busy.")
        else:
            raise
