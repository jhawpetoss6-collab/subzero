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
PAY_CONFIG_FILE = Path.home() / ".subzero" / "payments.json"
INCOME_LEDGER = Path.home() / ".subzero" / "income_ledger.json"

# Optional: Stripe for card payments (debit card link/withdraw stubs)
try:
    import stripe  # type: ignore
    HAS_STRIPE = True
except Exception:
    stripe = None  # type: ignore
    HAS_STRIPE = False

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

def _load_payments():
    """Load payments config from ~/.subzero/payments.json"""
    if PAY_CONFIG_FILE.exists():
        try:
            return json.loads(PAY_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "stripe_public_key": "",
        "stripe_secret_key": "",
        "stripe_connect_account": "",
        "fee_percent": 2.9,
        "fee_flat_cents": 30,
        "fee_label": "SubZero Processing Fee",
        "owner": {
            "crypto_wallet_eth": "",
            "crypto_wallet_sol": "",
            "crypto_wallet_tron": "",
            "cashapp": "",
            "venmo": "",
            "netspend_card": "",
        },
        "merchant_account": "",
    }


def _calc_fee(amount_cents: int, cfg: dict) -> dict:
    """Calculate SubZero platform fee from a transaction amount in cents."""
    pct = float(cfg.get("fee_percent", 2.9))
    flat = int(cfg.get("fee_flat_cents", 30))
    fee = int(round(amount_cents * pct / 100)) + flat
    fee = max(fee, 1)  # minimum 1 cent fee
    return {
        "amount_cents": amount_cents,
        "fee_cents": fee,
        "net_cents": amount_cents - fee,
        "fee_percent": pct,
        "fee_flat_cents": flat,
        "fee_label": cfg.get("fee_label", "SubZero Processing Fee"),
    }


def _load_ledger() -> list:
    if INCOME_LEDGER.exists():
        try:
            return json.loads(INCOME_LEDGER.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_ledger(entries: list):
    INCOME_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    INCOME_LEDGER.write_text(json.dumps(entries[-500:], indent=2), encoding="utf-8")


def _record_income(method: str, amount_cents: int, fee_cents: int, detail: str = ""):
    """Log fee income to the ledger."""
    ledger = _load_ledger()
    ledger.append({
        "ts": datetime.now().isoformat(),
        "method": method,
        "amount_cents": amount_cents,
        "fee_cents": fee_cents,
        "net_cents": amount_cents - fee_cents,
        "detail": detail,
    })
    _save_ledger(ledger)


def _stripe_ok(cfg: dict) -> bool:
    return HAS_STRIPE and bool(cfg.get("stripe_secret_key")) and bool(cfg.get("stripe_public_key"))


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
            cfg = _load_payments()
            self._j({
                "ok": True,
                "ollama": is_ollama_online(),
                "model": DEFAULT_MODEL,
                "tools": HAS_RUNTIME,
                "tool_count": 31 if HAS_RUNTIME else 0,
                "payments": {
                    "has_stripe": HAS_STRIPE,
                    "configured": _stripe_ok(cfg),
                    "fee_percent": cfg.get("fee_percent", 0.0),
                    "fee_flat_cents": cfg.get("fee_flat_cents", 0),
                },
            })
        elif p == "/api/payments/config":
            cfg = _load_payments()
            owner = cfg.get("owner", {})
            self._j({
                "ok": True,
                "has_stripe": HAS_STRIPE,
                "configured": _stripe_ok(cfg),
                "public_key": cfg.get("stripe_public_key", ""),
                "fee_percent": cfg.get("fee_percent", 2.9),
                "fee_flat_cents": cfg.get("fee_flat_cents", 30),
                "fee_label": cfg.get("fee_label", "SubZero Processing Fee"),
                "owner_cashapp": owner.get("cashapp", ""),
                "owner_venmo": owner.get("venmo", ""),
                "owner_crypto_eth": owner.get("crypto_wallet_eth", ""),
                "owner_crypto_sol": owner.get("crypto_wallet_sol", ""),
                "owner_crypto_tron": owner.get("crypto_wallet_tron", ""),
            })
        elif p == "/api/payments/fee-calc":
            cfg = _load_payments()
            # amount in query string: ?amount_cents=1000
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            amt = int(qs.get("amount_cents", ["0"])[0])
            self._j({"ok": True, **_calc_fee(amt, cfg)})
        elif p == "/api/payments/income":
            ledger = _load_ledger()
            total_fee = sum(e.get("fee_cents", 0) for e in ledger)
            total_vol = sum(e.get("amount_cents", 0) for e in ledger)
            self._j({
                "ok": True,
                "total_fee_cents": total_fee,
                "total_volume_cents": total_vol,
                "tx_count": len(ledger),
                "recent": ledger[-20:][::-1],
            })
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
        elif p == "/api/payments/create-setup-intent":
            self._create_setup_intent(data)
        elif p == "/api/payments/create-payment-intent":
            self._create_payment_intent(data)
        elif p == "/api/payments/record-fee":
            self._record_fee(data)
        elif p == "/api/payments/withdraw":
            self._withdraw(data)
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

    def _create_setup_intent(self, data):
        cfg = _load_payments()
        if not _stripe_ok(cfg):
            self._j({"ok": False, "error": "Stripe not configured. Add keys to ~/.subzero/payments.json"}, 400)
            return
        try:
            stripe.api_key = cfg["stripe_secret_key"]
            intent = stripe.SetupIntent.create(payment_method_types=["card"])  # type: ignore
            self._j({"ok": True, "client_secret": intent["client_secret"]})
        except Exception as e:
            self._j({"ok": False, "error": str(e)}, 500)

    def _create_payment_intent(self, data):
        cfg = _load_payments()
        if not _stripe_ok(cfg):
            self._j({"ok": False, "error": "Stripe not configured."}, 400)
            return
        amount = int(data.get("amount_cents", 0))
        currency = (data.get("currency") or "usd").lower()
        if amount <= 0:
            self._j({"ok": False, "error": "amount_cents required"}, 400)
            return
        fee_info = _calc_fee(amount, cfg)
        try:
            stripe.api_key = cfg["stripe_secret_key"]
            params = {
                "amount": amount,
                "currency": currency,
                "automatic_payment_methods": {"enabled": True},
                "metadata": {"platform_fee": fee_info["fee_cents"]},
            }
            # If Stripe Connect is set up, route the fee to your account
            connect_acct = cfg.get("stripe_connect_account", "")
            if connect_acct:
                params["application_fee_amount"] = fee_info["fee_cents"]
                params["transfer_data"] = {"destination": connect_acct}
            intent = stripe.PaymentIntent.create(**params)  # type: ignore
            _record_income("stripe", amount, fee_info["fee_cents"], "PaymentIntent")
            self._j({"ok": True, "client_secret": intent["client_secret"], "fee": fee_info})
        except Exception as e:
            self._j({"ok": False, "error": str(e)}, 500)

    def _record_fee(self, data):
        """Record a fee from non-Stripe payments (Cash App, Venmo, crypto, Netspend)."""
        method = data.get("method", "unknown")
        amount = int(data.get("amount_cents", 0))
        if amount <= 0:
            self._j({"ok": False, "error": "amount_cents required"}, 400)
            return
        cfg = _load_payments()
        fee_info = _calc_fee(amount, cfg)
        _record_income(method, amount, fee_info["fee_cents"], data.get("detail", ""))
        self._j({"ok": True, "fee": fee_info})

    def _withdraw(self, data):
        # Stub for debit card/bank withdrawals — requires Stripe Connect and verification.
        cfg = _load_payments()
        needs_connect = not bool(cfg.get("connect_account"))
        if needs_connect:
            self._j({"ok": False, "error": "Withdrawals require Stripe Connect. Add 'connect_account' to ~/.subzero/payments.json and complete verification."}, 400)
            return
        self._j({"ok": False, "error": "Not implemented in demo."}, 501)

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
    cfg = _load_payments()
    print(f"  Fee:     {cfg.get('fee_percent', 2.9)}% + ${cfg.get('fee_flat_cents', 30) / 100:.2f} per tx")
    ledger = _load_ledger()
    total = sum(e.get('fee_cents', 0) for e in ledger)
    print(f"  Income:  ${total / 100:.2f} ({len(ledger)} transactions)")
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
