"""
SubZero Autonomous Tool Runtime
════════════════════════════════
Shared tool execution engine for all SubZero agents.
Import this module to give any agent autonomous capabilities:
  commands, files, web search, browser, HTTP, clipboard, trading.

Usage:
    from sz_runtime import ToolRuntime
    rt = ToolRuntime()
    # In your system prompt, include:
    rt.get_system_prompt()
    # After AI responds:
    calls = rt.parse(response_text)
    for call in calls:
        result = rt.execute(call)
"""

import os
import re
import sys
import json
import shlex
import subprocess
import tempfile
import ctypes
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Optional

# ── Optional imports (graceful degradation) ────────────────────
try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    HAS_DDG = False

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Browser and Trading are in separate modules to keep this lean
_browser_instance = None
_trading_instance = None

# ── Constants ──────────────────────────────────────────────────
DATA_DIR = Path.home() / ".subzero"
TRADING_CONFIG = DATA_DIR / "trading.json"
NO_WINDOW = 0x08000000  # subprocess.CREATE_NO_WINDOW

# Safety tiers
TIER_AUTO = "auto"           # No confirmation needed
TIER_LOG = "log"             # Auto-execute, but log prominently
TIER_CONFIRM = "confirm"     # Needs user confirmation

TOOL_TIERS = {
    "run_command": TIER_LOG,
    "run_python": TIER_LOG,
    "file_read": TIER_AUTO,
    "file_write": TIER_LOG,
    "file_append": TIER_LOG,
    "file_list": TIER_AUTO,
    "file_delete": TIER_CONFIRM,
    "web_search": TIER_AUTO,
    "web_get": TIER_AUTO,
    "web_post": TIER_CONFIRM,
    "browser_open": TIER_LOG,
    "browser_click": TIER_LOG,
    "browser_type": TIER_LOG,
    "browser_read": TIER_AUTO,
    "browser_screenshot": TIER_AUTO,
    "browser_wait": TIER_AUTO,
    "browser_close": TIER_LOG,
    "clipboard_copy": TIER_LOG,
    "clipboard_paste": TIER_AUTO,
    "open_app": TIER_CONFIRM,
    "trade_quote": TIER_AUTO,
    "trade_buy": TIER_CONFIRM,
    "trade_sell": TIER_CONFIRM,
    "trade_positions": TIER_AUTO,
    "trade_portfolio": TIER_AUTO,
    "trade_history": TIER_AUTO,
    "trade_cancel": TIER_CONFIRM,
    "trade_watchlist": TIER_AUTO,
    "deploy_to_usb": TIER_LOG,
    "download_subzero": TIER_LOG,
    "detect_usb": TIER_AUTO,
}


# ── Data Classes ───────────────────────────────────────────────

@dataclass
class ToolCall:
    """Parsed tool call from AI response."""
    name: str
    params: dict = field(default_factory=dict)
    raw: str = ""


@dataclass
class ToolResult:
    """Result from executing a tool."""
    success: bool
    output: str = ""
    data: Any = None
    tool_name: str = ""
    needs_confirm: bool = False


# ── Tool Call Parser ───────────────────────────────────────────

def parse_tool_calls(text: str) -> list[ToolCall]:
    """Parse @tool calls from AI response text.

    Format: @tool tool_name param1="value1" param2="value2"
    Also supports multi-line content with triple-backtick blocks.
    """
    calls = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("@tool "):
            raw_line = line
            rest = line[6:].strip()

            # Extract tool name
            parts = rest.split(None, 1)
            if not parts:
                i += 1
                continue
            name = parts[0]
            param_str = parts[1] if len(parts) > 1 else ""

            # Check if next lines have a content block (```...```)
            content_block = None
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith("```"):
                    # Collect until closing ```
                    block_lines = []
                    i += 2
                    while i < len(lines) and not lines[i].strip().startswith("```"):
                        block_lines.append(lines[i])
                        i += 1
                    content_block = "\n".join(block_lines)

            # Parse key="value" params
            params = _parse_params(param_str)
            if content_block is not None:
                params["content"] = content_block

            calls.append(ToolCall(name=name, params=params, raw=raw_line))

        i += 1
    return calls


def _parse_params(param_str: str) -> dict:
    """Parse key=\"value\" pairs from a parameter string."""
    params = {}
    if not param_str:
        return params

    # Match key="value" or key='value' patterns
    pattern = r'(\w+)\s*=\s*(?:"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'|(\S+))'
    for m in re.finditer(pattern, param_str):
        key = m.group(1)
        value = m.group(2) if m.group(2) is not None else (
            m.group(3) if m.group(3) is not None else m.group(4)
        )
        # Unescape
        value = value.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
        params[key] = value
    return params


# ── Tool Implementations ──────────────────────────────────────

def _tool_run_command(params: dict) -> ToolResult:
    cmd = params.get("cmd", "")
    if not cmd:
        return ToolResult(False, "No command provided", tool_name="run_command")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=120, encoding="utf-8", errors="replace",
            creationflags=NO_WINDOW,
        )
        output = ""
        if result.stdout:
            output += result.stdout[:4000]
        if result.stderr:
            output += ("\n[stderr] " + result.stderr[:2000])
        ok = result.returncode == 0
        return ToolResult(ok, output.strip() or "(no output)", tool_name="run_command")
    except subprocess.TimeoutExpired:
        return ToolResult(False, "Command timed out (120s)", tool_name="run_command")
    except Exception as e:
        return ToolResult(False, f"Error: {e}", tool_name="run_command")


def _tool_run_python(params: dict) -> ToolResult:
    code = params.get("code", "")
    if not code:
        return ToolResult(False, "No code provided", tool_name="run_python")
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
            creationflags=NO_WINDOW,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return ToolResult(
            result.returncode == 0,
            output.strip()[:4000] or "(no output)",
            tool_name="run_python",
        )
    except subprocess.TimeoutExpired:
        return ToolResult(False, "Python execution timed out (60s)", tool_name="run_python")
    except Exception as e:
        return ToolResult(False, f"Error: {e}", tool_name="run_python")


def _tool_file_read(params: dict) -> ToolResult:
    path = params.get("path", "")
    if not path:
        return ToolResult(False, "No path provided", tool_name="file_read")
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult(False, f"File not found: {path}", tool_name="file_read")
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > 10000:
            content = content[:10000] + f"\n... (truncated, {len(content)} total chars)"
        return ToolResult(True, content, tool_name="file_read")
    except Exception as e:
        return ToolResult(False, f"Error reading {path}: {e}", tool_name="file_read")


def _tool_file_write(params: dict) -> ToolResult:
    path = params.get("path", "")
    content = params.get("content", "")
    if not path:
        return ToolResult(False, "No path provided", tool_name="file_write")
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return ToolResult(True, f"Wrote {len(content)} bytes to {path}", tool_name="file_write")
    except Exception as e:
        return ToolResult(False, f"Error writing {path}: {e}", tool_name="file_write")


def _tool_file_append(params: dict) -> ToolResult:
    path = params.get("path", "")
    content = params.get("content", "")
    if not path:
        return ToolResult(False, "No path provided", tool_name="file_append")
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(content)
        return ToolResult(True, f"Appended {len(content)} bytes to {path}", tool_name="file_append")
    except Exception as e:
        return ToolResult(False, f"Error: {e}", tool_name="file_append")


def _tool_file_list(params: dict) -> ToolResult:
    directory = params.get("directory", params.get("path", "."))
    try:
        p = Path(directory).expanduser()
        if not p.is_dir():
            return ToolResult(False, f"Not a directory: {directory}", tool_name="file_list")
        entries = []
        for item in sorted(p.iterdir()):
            kind = "DIR" if item.is_dir() else f"{item.stat().st_size}B"
            entries.append(f"  {item.name}  ({kind})")
        output = f"Contents of {directory}:\n" + "\n".join(entries[:100])
        if len(entries) > 100:
            output += f"\n  ... ({len(entries)} total items)"
        return ToolResult(True, output, data=entries, tool_name="file_list")
    except Exception as e:
        return ToolResult(False, f"Error: {e}", tool_name="file_list")


def _tool_file_delete(params: dict) -> ToolResult:
    path = params.get("path", "")
    if not path:
        return ToolResult(False, "No path provided", tool_name="file_delete")
    try:
        p = Path(path).expanduser()
        if p.is_file():
            p.unlink()
            return ToolResult(True, f"Deleted {path}", tool_name="file_delete")
        elif p.is_dir():
            import shutil
            shutil.rmtree(p)
            return ToolResult(True, f"Deleted directory {path}", tool_name="file_delete")
        else:
            return ToolResult(False, f"Not found: {path}", tool_name="file_delete")
    except Exception as e:
        return ToolResult(False, f"Error: {e}", tool_name="file_delete")


def _tool_web_search(params: dict) -> ToolResult:
    query = params.get("query", "")
    if not query:
        return ToolResult(False, "No query provided", tool_name="web_search")
    try:
        if HAS_DDG:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
            if not results:
                return ToolResult(True, "No results found.", tool_name="web_search")
            lines = []
            for r in results:
                title = r.get("title", "")
                url = r.get("href", r.get("link", ""))
                body = r.get("body", r.get("snippet", ""))[:200]
                lines.append(f"• {title}\n  {url}\n  {body}")
            return ToolResult(True, "\n\n".join(lines), data=results, tool_name="web_search")
        else:
            # Fallback: use requests or urllib
            return _web_search_fallback(query)
    except Exception as e:
        return ToolResult(False, f"Search error: {e}", tool_name="web_search")


def _web_search_fallback(query: str) -> ToolResult:
    """Fallback web search using DuckDuckGo HTML."""
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # Simple extraction
        results = re.findall(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html)
        if results:
            lines = [f"• {title.strip()} — {url}" for url, title in results[:5]]
            return ToolResult(True, "\n".join(lines), tool_name="web_search")
        return ToolResult(True, "No results found.", tool_name="web_search")
    except Exception as e:
        return ToolResult(False, f"Fallback search error: {e}", tool_name="web_search")


def _tool_web_get(params: dict) -> ToolResult:
    url = params.get("url", "")
    if not url:
        return ToolResult(False, "No URL provided", tool_name="web_get")
    try:
        if HAS_REQUESTS:
            resp = _requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            text = resp.text[:8000]
            return ToolResult(resp.ok, text, data={"status": resp.status_code}, tool_name="web_get")
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8", errors="replace")[:8000]
            return ToolResult(True, text, tool_name="web_get")
    except Exception as e:
        return ToolResult(False, f"Error: {e}", tool_name="web_get")


def _tool_web_post(params: dict) -> ToolResult:
    url = params.get("url", "")
    data = params.get("data", "")
    if not url:
        return ToolResult(False, "No URL provided", tool_name="web_post")
    try:
        if HAS_REQUESTS:
            headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
            resp = _requests.post(url, data=data, timeout=15, headers=headers)
            return ToolResult(resp.ok, resp.text[:4000], data={"status": resp.status_code}, tool_name="web_post")
        else:
            req = urllib.request.Request(
                url, data=data.encode("utf-8"),
                headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8", errors="replace")[:4000]
            return ToolResult(True, text, tool_name="web_post")
    except Exception as e:
        return ToolResult(False, f"Error: {e}", tool_name="web_post")


# ── Browser Tools (delegated to sz_browser.py) ────────────────

def _get_browser():
    global _browser_instance
    if _browser_instance is None:
        from sz_browser import SeleniumBrowser
        _browser_instance = SeleniumBrowser()
    return _browser_instance


def _tool_browser_open(params: dict) -> ToolResult:
    url = params.get("url", "")
    if not url:
        return ToolResult(False, "No URL provided", tool_name="browser_open")
    try:
        browser = _get_browser()
        browser.open(url)
        title = browser.title()
        return ToolResult(True, f"Opened: {title} ({url})", tool_name="browser_open")
    except Exception as e:
        return ToolResult(False, f"Browser error: {e}", tool_name="browser_open")


def _tool_browser_click(params: dict) -> ToolResult:
    selector = params.get("selector", "")
    if not selector:
        return ToolResult(False, "No selector provided", tool_name="browser_click")
    try:
        browser = _get_browser()
        browser.click(selector)
        return ToolResult(True, f"Clicked: {selector}", tool_name="browser_click")
    except Exception as e:
        return ToolResult(False, f"Click error: {e}", tool_name="browser_click")


def _tool_browser_type(params: dict) -> ToolResult:
    selector = params.get("selector", "")
    text = params.get("text", "")
    if not selector or not text:
        return ToolResult(False, "Need selector and text", tool_name="browser_type")
    try:
        browser = _get_browser()
        browser.type_text(selector, text)
        return ToolResult(True, f"Typed into {selector}: {text[:50]}", tool_name="browser_type")
    except Exception as e:
        return ToolResult(False, f"Type error: {e}", tool_name="browser_type")


def _tool_browser_read(params: dict) -> ToolResult:
    selector = params.get("selector", "")
    try:
        browser = _get_browser()
        text = browser.read(selector)
        return ToolResult(True, text[:6000], tool_name="browser_read")
    except Exception as e:
        return ToolResult(False, f"Read error: {e}", tool_name="browser_read")


def _tool_browser_screenshot(params: dict) -> ToolResult:
    try:
        browser = _get_browser()
        path = browser.screenshot()
        return ToolResult(True, f"Screenshot saved: {path}", data={"path": path}, tool_name="browser_screenshot")
    except Exception as e:
        return ToolResult(False, f"Screenshot error: {e}", tool_name="browser_screenshot")


def _tool_browser_wait(params: dict) -> ToolResult:
    selector = params.get("selector", "")
    timeout = int(params.get("timeout", "10"))
    if not selector:
        return ToolResult(False, "No selector provided", tool_name="browser_wait")
    try:
        browser = _get_browser()
        browser.wait_for(selector, timeout)
        return ToolResult(True, f"Element found: {selector}", tool_name="browser_wait")
    except Exception as e:
        return ToolResult(False, f"Wait error: {e}", tool_name="browser_wait")


def _tool_browser_close(params: dict) -> ToolResult:
    global _browser_instance
    try:
        if _browser_instance:
            _browser_instance.close()
            _browser_instance = None
        return ToolResult(True, "Browser closed", tool_name="browser_close")
    except Exception as e:
        return ToolResult(False, f"Error: {e}", tool_name="browser_close")


# ── Clipboard Tools ───────────────────────────────────────────

def _tool_clipboard_copy(params: dict) -> ToolResult:
    text = params.get("text", "")
    if not text:
        return ToolResult(False, "No text provided", tool_name="clipboard_copy")
    try:
        subprocess.run(
            ["clip"], input=text.encode("utf-16le"), check=True,
            creationflags=NO_WINDOW,
        )
        return ToolResult(True, f"Copied {len(text)} chars to clipboard", tool_name="clipboard_copy")
    except Exception as e:
        return ToolResult(False, f"Error: {e}", tool_name="clipboard_copy")


def _tool_clipboard_paste(params: dict) -> ToolResult:
    try:
        result = subprocess.run(
            ["powershell", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=5,
            creationflags=NO_WINDOW,
        )
        return ToolResult(True, result.stdout.strip()[:4000], tool_name="clipboard_paste")
    except Exception as e:
        return ToolResult(False, f"Error: {e}", tool_name="clipboard_paste")


# ── App Launcher ──────────────────────────────────────────────

def _tool_open_app(params: dict) -> ToolResult:
    path = params.get("path", params.get("name", ""))
    if not path:
        return ToolResult(False, "No path/name provided", tool_name="open_app")
    try:
        os.startfile(path)
        return ToolResult(True, f"Launched: {path}", tool_name="open_app")
    except Exception as e:
        return ToolResult(False, f"Error launching {path}: {e}", tool_name="open_app")


# ── Trading Tools (Alpaca) ────────────────────────────────────

def _get_trading():
    global _trading_instance
    if _trading_instance is None:
        _trading_instance = _AlpacaTrader()
    return _trading_instance


class _AlpacaTrader:
    """Alpaca trading wrapper. Paper trading by default."""

    def __init__(self):
        self.config = self._load_config()
        self._client = None
        self._trading_client = None

    def _load_config(self) -> dict:
        if TRADING_CONFIG.exists():
            try:
                return json.loads(TRADING_CONFIG.read_text())
            except Exception:
                pass
        return {
            "api_key": "",
            "api_secret": "",
            "paper": True,
            "auto_trade": False,
        }

    def save_config(self):
        TRADING_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        TRADING_CONFIG.write_text(json.dumps(self.config, indent=2))

    def _ensure_client(self):
        if self._trading_client is not None:
            return
        key = self.config.get("api_key", "")
        secret = self.config.get("api_secret", "")
        if not key or not secret:
            raise RuntimeError(
                "Alpaca API not configured. Set your keys:\n"
                "  1. Sign up at https://alpaca.markets (free)\n"
                "  2. Get API key + secret from dashboard\n"
                "  3. Tell me your key and secret, or edit ~/.subzero/trading.json"
            )
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.data.historical import StockHistoricalDataClient
            paper = self.config.get("paper", True)
            self._trading_client = TradingClient(key, secret, paper=paper)
            self._data_client = StockHistoricalDataClient(key, secret)
        except ImportError:
            raise RuntimeError("alpaca-py not installed. Run: pip install alpaca-py")

    def quote(self, symbol: str) -> ToolResult:
        try:
            self._ensure_client()
            from alpaca.data.requests import StockLatestQuoteRequest
            req = StockLatestQuoteRequest(symbol_or_symbols=symbol.upper())
            quotes = self._data_client.get_stock_latest_quote(req)
            q = quotes.get(symbol.upper())
            if q:
                return ToolResult(True, (
                    f"{symbol.upper()}: Ask ${q.ask_price} | Bid ${q.bid_price} | "
                    f"Ask Size {q.ask_size} | Bid Size {q.bid_size}"
                ), data={"ask": float(q.ask_price), "bid": float(q.bid_price)}, tool_name="trade_quote")
            return ToolResult(False, f"No quote for {symbol}", tool_name="trade_quote")
        except Exception as e:
            return ToolResult(False, str(e), tool_name="trade_quote")

    def buy(self, symbol: str, qty: str, order_type: str = "market") -> ToolResult:
        try:
            self._ensure_client()
            from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            if order_type == "market":
                req = MarketOrderRequest(
                    symbol=symbol.upper(), qty=float(qty),
                    side=OrderSide.BUY, time_in_force=TimeInForce.DAY,
                )
            else:
                return ToolResult(False, "Only market orders supported for now", tool_name="trade_buy")
            order = self._trading_client.submit_order(req)
            mode = "PAPER" if self.config.get("paper", True) else "LIVE"
            return ToolResult(True, (
                f"[{mode}] BUY {qty} {symbol.upper()} — Order ID: {order.id} "
                f"Status: {order.status}"
            ), data={"order_id": str(order.id)}, tool_name="trade_buy")
        except Exception as e:
            return ToolResult(False, str(e), tool_name="trade_buy")

    def sell(self, symbol: str, qty: str, order_type: str = "market") -> ToolResult:
        try:
            self._ensure_client()
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            req = MarketOrderRequest(
                symbol=symbol.upper(), qty=float(qty),
                side=OrderSide.SELL, time_in_force=TimeInForce.DAY,
            )
            order = self._trading_client.submit_order(req)
            mode = "PAPER" if self.config.get("paper", True) else "LIVE"
            return ToolResult(True, (
                f"[{mode}] SELL {qty} {symbol.upper()} — Order ID: {order.id} "
                f"Status: {order.status}"
            ), data={"order_id": str(order.id)}, tool_name="trade_sell")
        except Exception as e:
            return ToolResult(False, str(e), tool_name="trade_sell")

    def positions(self) -> ToolResult:
        try:
            self._ensure_client()
            pos = self._trading_client.get_all_positions()
            if not pos:
                return ToolResult(True, "No open positions.", tool_name="trade_positions")
            lines = []
            for p in pos:
                pnl = float(p.unrealized_pl)
                sign = "+" if pnl >= 0 else ""
                lines.append(
                    f"  {p.symbol}: {p.qty} shares @ ${p.avg_entry_price} "
                    f"| Current: ${p.current_price} | P&L: {sign}${pnl:.2f}"
                )
            return ToolResult(True, "Open positions:\n" + "\n".join(lines), data=len(pos), tool_name="trade_positions")
        except Exception as e:
            return ToolResult(False, str(e), tool_name="trade_positions")

    def portfolio(self) -> ToolResult:
        try:
            self._ensure_client()
            acct = self._trading_client.get_account()
            mode = "PAPER" if self.config.get("paper", True) else "LIVE"
            return ToolResult(True, (
                f"[{mode}] Portfolio:\n"
                f"  Equity: ${acct.equity}\n"
                f"  Cash: ${acct.cash}\n"
                f"  Buying Power: ${acct.buying_power}\n"
                f"  Portfolio Value: ${acct.portfolio_value}\n"
                f"  Day P&L: ${acct.equity - acct.last_equity}"
            ), tool_name="trade_portfolio")
        except Exception as e:
            return ToolResult(False, str(e), tool_name="trade_portfolio")

    def history(self, limit: int = 10) -> ToolResult:
        try:
            self._ensure_client()
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=limit)
            orders = self._trading_client.get_orders(req)
            if not orders:
                return ToolResult(True, "No recent orders.", tool_name="trade_history")
            lines = []
            for o in orders:
                lines.append(
                    f"  [{o.status}] {o.side} {o.qty} {o.symbol} "
                    f"@ {o.type} — {o.created_at.strftime('%m/%d %H:%M') if o.created_at else ''}"
                )
            return ToolResult(True, "Recent orders:\n" + "\n".join(lines), tool_name="trade_history")
        except Exception as e:
            return ToolResult(False, str(e), tool_name="trade_history")

    def cancel(self, order_id: str = "") -> ToolResult:
        try:
            self._ensure_client()
            if order_id:
                self._trading_client.cancel_order_by_id(order_id)
                return ToolResult(True, f"Cancelled order {order_id}", tool_name="trade_cancel")
            else:
                self._trading_client.cancel_orders()
                return ToolResult(True, "Cancelled all open orders", tool_name="trade_cancel")
        except Exception as e:
            return ToolResult(False, str(e), tool_name="trade_cancel")

    def watchlist(self, symbols: str = "") -> ToolResult:
        wl_file = DATA_DIR / "watchlist.json"
        if symbols:
            syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
            wl_file.parent.mkdir(parents=True, exist_ok=True)
            wl_file.write_text(json.dumps(syms))
            return ToolResult(True, f"Watchlist set: {', '.join(syms)}", tool_name="trade_watchlist")
        else:
            if wl_file.exists():
                syms = json.loads(wl_file.read_text())
                return ToolResult(True, f"Watchlist: {', '.join(syms)}", tool_name="trade_watchlist")
            return ToolResult(True, "Watchlist is empty. Set with: @tool trade_watchlist symbols=\"AAPL,TSLA,MSFT\"", tool_name="trade_watchlist")


def _tool_trade_quote(params: dict) -> ToolResult:
    return _get_trading().quote(params.get("symbol", ""))

def _tool_trade_buy(params: dict) -> ToolResult:
    return _get_trading().buy(
        params.get("symbol", ""), params.get("qty", "1"),
        params.get("order_type", "market"),
    )

def _tool_trade_sell(params: dict) -> ToolResult:
    return _get_trading().sell(
        params.get("symbol", ""), params.get("qty", "1"),
        params.get("order_type", "market"),
    )

def _tool_trade_positions(params: dict) -> ToolResult:
    return _get_trading().positions()

def _tool_trade_portfolio(params: dict) -> ToolResult:
    return _get_trading().portfolio()

def _tool_trade_history(params: dict) -> ToolResult:
    return _get_trading().history(int(params.get("limit", "10")))

def _tool_trade_cancel(params: dict) -> ToolResult:
    return _get_trading().cancel(params.get("order_id", ""))

def _tool_trade_watchlist(params: dict) -> ToolResult:
    return _get_trading().watchlist(params.get("symbols", ""))


# ── Deployment Tools ──────────────────────────────────────

SUBZERO_REPO = "https://github.com/jhawpetoss6-collab/subzero.git"
SUBZERO_ZIP  = "https://github.com/jhawpetoss6-collab/subzero/archive/refs/heads/main.zip"


def _find_usb_drives() -> list[str]:
    """Find removable USB drives on Windows."""
    drives = []
    if sys.platform == "win32":
        for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
            drive = f"{letter}:\\"
            try:
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive)
                # 2 = DRIVE_REMOVABLE
                if drive_type == 2 and os.path.exists(drive):
                    drives.append(drive)
            except Exception:
                pass
    return drives


def _tool_deploy_to_usb(params: dict) -> ToolResult:
    """Copy SubZero to a USB drive. Auto-detects USB or uses specified drive letter."""
    drive = params.get("drive", "").strip().upper()

    # Find source (portable folder or project root)
    script_dir = Path(__file__).parent
    portable = script_dir / "SubZero_Portable"
    source = portable if portable.exists() else script_dir

    # Find or validate USB drive
    if drive:
        if not drive.endswith("\\"):
            drive = drive.rstrip(":") + ":\\"
        if not os.path.exists(drive):
            return ToolResult(False, f"Drive {drive} not found. Is the USB plugged in?", tool_name="deploy_to_usb")
    else:
        usb_drives = _find_usb_drives()
        if not usb_drives:
            return ToolResult(False, "No USB drive detected. Plug in a USB stick and try again.", tool_name="deploy_to_usb")
        drive = usb_drives[0]  # Use first USB found

    dest = os.path.join(drive, "SubZero")
    try:
        import shutil
        # Copy entire folder
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(
            str(source), dest,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".gitignore"),
        )
        # Count files copied
        file_count = sum(1 for _, _, files in os.walk(dest) for _ in files)
        return ToolResult(
            True,
            f"SubZero deployed to {dest} ({file_count} files). "
            f"Run 'Launch Sub-Zero.bat' on any PC with Python to start.",
            tool_name="deploy_to_usb",
        )
    except Exception as e:
        return ToolResult(False, f"Failed to deploy: {e}", tool_name="deploy_to_usb")


def _tool_download_subzero(params: dict) -> ToolResult:
    """Download SubZero from GitHub. Can download to a folder or directly to USB."""
    dest = params.get("destination", "").strip()
    to_usb = params.get("usb", "").strip().lower() in ("true", "yes", "1", "")

    # If destination not specified, figure out where to put it
    if not dest:
        if to_usb:
            usb_drives = _find_usb_drives()
            if usb_drives:
                dest = os.path.join(usb_drives[0], "SubZero")
            else:
                return ToolResult(False, "No USB drive detected. Specify destination= or plug in a USB.", tool_name="download_subzero")
        else:
            dest = os.path.join(str(Path.home()), "Downloads", "SubZero")

    try:
        # Try git clone first
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", SUBZERO_REPO, dest],
                capture_output=True, text=True, timeout=120,
                encoding="utf-8", errors="replace",
                creationflags=NO_WINDOW,
            )
            if result.returncode == 0:
                file_count = sum(1 for _, _, files in os.walk(dest) for _ in files)
                msg = f"SubZero cloned to {dest} ({file_count} files)."
                if to_usb:
                    msg += " USB is ready — run 'Launch Sub-Zero.bat' on any PC."
                else:
                    msg += " Run setup.bat to install, or copy folder to USB."
                return ToolResult(True, msg, tool_name="download_subzero")
        except FileNotFoundError:
            pass  # git not available, try zip download

        # Fallback: download ZIP
        import zipfile
        import tempfile
        zip_path = os.path.join(tempfile.gettempdir(), "subzero_download.zip")
        urllib.request.urlretrieve(SUBZERO_ZIP, zip_path)

        # Extract
        os.makedirs(dest, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            # ZIP has subzero-main/ prefix, strip it
            for info in zf.infolist():
                if info.is_dir():
                    continue
                # Remove the top-level directory prefix
                parts = info.filename.split("/", 1)
                if len(parts) > 1:
                    target_path = os.path.join(dest, parts[1])
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with zf.open(info) as src, open(target_path, "wb") as dst:
                        dst.write(src.read())

        os.remove(zip_path)
        file_count = sum(1 for _, _, files in os.walk(dest) for _ in files)
        msg = f"SubZero downloaded to {dest} ({file_count} files)."
        if to_usb:
            msg += " USB is ready — run 'Launch Sub-Zero.bat' on any PC."
        else:
            msg += " Run setup.bat to install, or copy folder to USB."
        return ToolResult(True, msg, tool_name="download_subzero")

    except Exception as e:
        return ToolResult(False, f"Download failed: {e}", tool_name="download_subzero")


def _tool_detect_usb(params: dict) -> ToolResult:
    """Detect connected USB drives."""
    drives = _find_usb_drives()
    if not drives:
        return ToolResult(True, "No USB drives detected. Plug in a USB stick.", tool_name="detect_usb")
    drive_info = []
    for d in drives:
        try:
            import shutil
            total, used, free = shutil.disk_usage(d)
            gb_free = free / (1024**3)
            gb_total = total / (1024**3)
            drive_info.append(f"{d} — {gb_free:.1f} GB free / {gb_total:.1f} GB total")
        except Exception:
            drive_info.append(d)
    return ToolResult(True, f"USB drives found:\n" + "\n".join(drive_info), tool_name="detect_usb")


# ── Tool Registry ─────────────────────────────────────────

TOOLS = {
    "run_command":       ("Run a shell command", {"cmd": "The command to run"}, _tool_run_command),
    "run_python":        ("Execute Python code", {"code": "Python code to execute"}, _tool_run_python),
    "file_read":         ("Read a file", {"path": "File path"}, _tool_file_read),
    "file_write":        ("Write/create a file", {"path": "File path", "content": "File content"}, _tool_file_write),
    "file_append":       ("Append to a file", {"path": "File path", "content": "Content to append"}, _tool_file_append),
    "file_list":         ("List directory contents", {"directory": "Directory path"}, _tool_file_list),
    "file_delete":       ("Delete a file or directory", {"path": "Path to delete"}, _tool_file_delete),
    "web_search":        ("Search the web (DuckDuckGo)", {"query": "Search query"}, _tool_web_search),
    "web_get":           ("HTTP GET request", {"url": "URL to fetch"}, _tool_web_get),
    "web_post":          ("HTTP POST request", {"url": "URL", "data": "POST body"}, _tool_web_post),
    "browser_open":      ("Open URL in browser", {"url": "URL to open"}, _tool_browser_open),
    "browser_click":     ("Click element in browser", {"selector": "CSS selector"}, _tool_browser_click),
    "browser_type":      ("Type text into browser input", {"selector": "CSS selector", "text": "Text to type"}, _tool_browser_type),
    "browser_read":      ("Read text from browser page", {"selector": "CSS selector (optional)"}, _tool_browser_read),
    "browser_screenshot": ("Take browser screenshot", {}, _tool_browser_screenshot),
    "browser_wait":      ("Wait for element in browser", {"selector": "CSS selector", "timeout": "Seconds (default 10)"}, _tool_browser_wait),
    "browser_close":     ("Close the browser", {}, _tool_browser_close),
    "clipboard_copy":    ("Copy text to clipboard", {"text": "Text to copy"}, _tool_clipboard_copy),
    "clipboard_paste":   ("Read clipboard contents", {}, _tool_clipboard_paste),
    "open_app":          ("Launch an application", {"path": "App path or name"}, _tool_open_app),
    "trade_quote":       ("Get stock/crypto price", {"symbol": "Ticker symbol (e.g. AAPL)"}, _tool_trade_quote),
    "trade_buy":         ("Buy stock (paper or live)", {"symbol": "Ticker", "qty": "Quantity", "order_type": "market/limit"}, _tool_trade_buy),
    "trade_sell":        ("Sell stock (paper or live)", {"symbol": "Ticker", "qty": "Quantity", "order_type": "market/limit"}, _tool_trade_sell),
    "trade_positions":   ("List open trading positions", {}, _tool_trade_positions),
    "trade_portfolio":   ("Get account/portfolio info", {}, _tool_trade_portfolio),
    "trade_history":     ("Recent order history", {"limit": "Number of orders"}, _tool_trade_history),
    "trade_cancel":      ("Cancel order(s)", {"order_id": "Order ID (empty=cancel all)"}, _tool_trade_cancel),
    "trade_watchlist":   ("Get/set watchlist", {"symbols": "Comma-separated symbols"}, _tool_trade_watchlist),
    # Deployment tools
    "deploy_to_usb":     ("Copy SubZero to a USB drive", {"drive": "Drive letter (e.g. E:) or empty for auto-detect"}, _tool_deploy_to_usb),
    "download_subzero":  ("Download SubZero from GitHub", {"destination": "Folder path (default: Downloads/SubZero)", "usb": "true to download directly to USB"}, _tool_download_subzero),
    "detect_usb":        ("Detect connected USB drives", {}, _tool_detect_usb),
}


# ── Main Runtime Class ────────────────────────────────────────

class ToolRuntime:
    """The main runtime that agents instantiate and use."""

    def __init__(self, auto_trade: bool = False):
        self.auto_trade = auto_trade
        self.execution_log: list[ToolResult] = []
        self.max_iterations = 5

    def parse(self, text: str) -> list[ToolCall]:
        """Parse tool calls from AI response."""
        return parse_tool_calls(text)

    def execute(self, call: ToolCall, skip_confirm: bool = False) -> ToolResult:
        """Execute a single tool call."""
        if call.name not in TOOLS:
            return ToolResult(False, f"Unknown tool: {call.name}", tool_name=call.name)

        tier = TOOL_TIERS.get(call.name, TIER_CONFIRM)

        # Check if confirmation needed
        if tier == TIER_CONFIRM and not skip_confirm:
            if call.name.startswith("trade_") and call.name in ("trade_buy", "trade_sell", "trade_cancel"):
                if not self.auto_trade:
                    return ToolResult(
                        False, "", tool_name=call.name, needs_confirm=True,
                        output=f"⚠ Confirmation needed: {call.name} {call.params}",
                    )
            else:
                return ToolResult(
                    False, "", tool_name=call.name, needs_confirm=True,
                    output=f"⚠ Confirmation needed: {call.name} {call.params}",
                )

        # Execute
        _, _, func = TOOLS[call.name]
        result = func(call.params)
        self.execution_log.append(result)
        return result

    def execute_all(self, calls: list[ToolCall], skip_confirm: bool = False) -> list[ToolResult]:
        """Execute all tool calls and return results."""
        results = []
        for call in calls:
            result = self.execute(call, skip_confirm=skip_confirm)
            results.append(result)
        return results

    def format_results(self, results: list[ToolResult]) -> str:
        """Format tool results for feeding back into AI conversation."""
        parts = []
        for r in results:
            status = "✓" if r.success else "✗"
            if r.needs_confirm:
                parts.append(f"[{r.tool_name}] {r.output}")
            else:
                parts.append(f"[{status} {r.tool_name}] {r.output}")
        return "\n".join(parts)

    def has_pending_work(self, results: list[ToolResult]) -> bool:
        """Check if any results indicate more work is needed."""
        return any(r.needs_confirm for r in results)

    def get_system_prompt(self) -> str:
        """Generate the system prompt section describing available tools."""
        lines = [
            "You have access to autonomous tools. To use a tool, write on its own line:",
            '@tool tool_name param1="value1" param2="value2"',
            "",
            "For multi-line content (like file writes), use a content block:",
            '@tool file_write path="app.py"',
            "```",
            "print('hello world')",
            "```",
            "",
            "Available tools:",
        ]
        for name, (desc, params, _) in TOOLS.items():
            param_str = ", ".join(f'{k}="{v}"' for k, v in params.items()) if params else "(no params)"
            lines.append(f"  @tool {name} {param_str}  — {desc}")

        lines.extend([
            "",
            "RULES:",
            "- You can use multiple tools in one response",
            "- Tool results will be shown to you so you can chain actions",
            "- For web browsing: open URL first, then read/click/type as needed",
            "- For trading: quote first, then buy/sell (paper mode by default)",
            "- Always explain what you're doing before using tools",
        ])
        return "\n".join(lines)

    def get_tool_names(self) -> list[str]:
        return list(TOOLS.keys())
