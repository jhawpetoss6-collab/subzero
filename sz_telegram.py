"""
SubZero Telegram Bridge — Spine Rip ↔ Telegram
═══════════════════════════════════════════════
Routes Telegram messages to the local Ollama AI (qwen2.5:1.5b)
and executes tools via the SubZero ToolRuntime.

Setup:
  1. Message @BotFather on Telegram → /newbot → get your bot token
  2. Run this module or use the Telegram button in Spine Rip
  3. It will ask for your token on first run (saved to ~/.subzero/telegram.json)

Usage:
    python sz_telegram.py            # standalone
    from sz_telegram import start_bot, stop_bot   # from Spine Rip GUI
"""

import os
import sys
import json
import asyncio
import logging
import threading
import urllib.request
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

# ── Config ─────────────────────────────────────────────────────
DATA_DIR = Path.home() / ".subzero"
TELEGRAM_CONFIG = DATA_DIR / "telegram.json"
OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
NO_WINDOW = 0x08000000

# ── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [TelegramBot] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Lazy import python-telegram-bot ────────────────────────────
try:
    from telegram import Update, BotCommand
    from telegram.ext import (
        Application, CommandHandler, MessageHandler,
        filters, ContextTypes,
    )
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False

# ── Lazy import ToolRuntime ────────────────────────────────────
try:
    from sz_runtime import ToolRuntime
    HAS_RUNTIME = True
except ImportError:
    HAS_RUNTIME = False


# ══════════════════════════════════════════════════════════════
#  Config helpers
# ══════════════════════════════════════════════════════════════

def load_config() -> dict:
    """Load telegram.json config."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if TELEGRAM_CONFIG.exists():
        try:
            return json.loads(TELEGRAM_CONFIG.read_text("utf-8"))
        except Exception:
            pass
    return {"bot_token": "", "allowed_users": [], "model": DEFAULT_MODEL}


def save_config(cfg: dict):
    """Save telegram.json config."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TELEGRAM_CONFIG.write_text(json.dumps(cfg, indent=2), "utf-8")


def get_bot_token() -> str:
    """Get bot token from config (or prompt in terminal if standalone)."""
    cfg = load_config()
    if cfg.get("bot_token"):
        return cfg["bot_token"]
    return ""


# ══════════════════════════════════════════════════════════════
#  Ollama AI caller (same backend as Spine Rip)
# ══════════════════════════════════════════════════════════════

def ollama_generate(prompt: str, model: str = None) -> str:
    """Call Ollama REST API — same engine Spine Rip uses."""
    model = model or DEFAULT_MODEL
    try:
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("response", "").strip() or "[No response from AI]"
    except urllib.error.URLError:
        return "⚠️ Ollama is not running. Start it with `ollama serve` on the Spine Rip machine."
    except Exception as e:
        return f"⚠️ AI error: {e}"


def is_ollama_online() -> bool:
    """Check if Ollama is reachable."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════
#  Per-user conversation memory
# ══════════════════════════════════════════════════════════════

_conversations: dict[int, list[dict]] = {}
MAX_HISTORY = 20


def _get_history(user_id: int) -> list[dict]:
    if user_id not in _conversations:
        _conversations[user_id] = []
    return _conversations[user_id]


def _add_message(user_id: int, role: str, content: str):
    hist = _get_history(user_id)
    hist.append({"role": role, "content": content, "ts": datetime.now().isoformat()})
    # Trim old messages
    if len(hist) > MAX_HISTORY * 2:
        _conversations[user_id] = hist[-MAX_HISTORY * 2:]


# ══════════════════════════════════════════════════════════════
#  Build the AI prompt (mirrors Spine Rip's approach)
# ══════════════════════════════════════════════════════════════

def _build_prompt(user_id: int, user_msg: str, model: str) -> str:
    tool_prompt = ""
    if HAS_RUNTIME:
        rt = ToolRuntime()
        tool_prompt = rt.get_system_prompt() + "\n\n"

    system = (
        "You are Spine Rip — the SubZero AI assistant connected via Telegram.\n"
        "You run LOCALLY on the user's machine using Ollama (model: " + model + ").\n"
        "You do NOT need API keys, cloud AI, or external services — you ARE the AI.\n\n"
        "CAPABILITIES:\n"
        "• Answer coding questions, debug errors, explain concepts\n"
        "• Execute shell commands on the local machine via @tool run_command\n"
        "• Read/write/create files via @tool file_read, file_write, file_list\n"
        "• Search the web via @tool web_search\n"
        "• Open websites via @tool browser_open\n"
        "• Manage clipboard via @tool clipboard_copy / clipboard_paste\n"
        "• Alpaca paper trading via @tool trade_buy, trade_sell, trade_quote\n"
        "• Deploy SubZero to USB drives or download from GitHub\n\n"
        + tool_prompt
        + "RULES:\n"
        "- Be concise. Telegram messages should be short and readable.\n"
        "- Use tool calls when the user asks you to DO something (run code, create files, etc.).\n"
        "- NEVER suggest setting API keys or env vars for AI — you run locally via Ollama.\n"
        "- Format code with markdown backticks.\n"
    )

    # Build conversation context
    hist = _get_history(user_id)
    conv_lines = []
    for m in hist[-10:]:
        speaker = "User" if m["role"] == "user" else "Spine Rip"
        conv_lines.append(f"{speaker}: {m['content']}")
    conv_lines.append(f"User: {user_msg}")

    return system + "\n\n" + "\n".join(conv_lines) + "\n\nSpine Rip:"


# ══════════════════════════════════════════════════════════════
#  Telegram command handlers
# ══════════════════════════════════════════════════════════════

WELCOME_TEXT = """
❄️ *SPINE RIP — SubZero AI Assistant* ❄️

Welcome! I'm *Spine Rip*, your personal AI assistant powered by SubZero.

🧠 *What is Spine Rip?*
Spine Rip is the Telegram interface to *Warp Oz*, the SubZero AI Code Assistant. It runs 100% locally on your machine using Ollama — no cloud, no API keys, no subscriptions. Your conversations stay private.

⚡ *What I can do:*
• 💬 Answer questions — coding, debugging, concepts, anything
• 🖥️ Run commands on your PC — `@tool run_command cmd="dir"`
• 📁 Read & write files — create scripts, edit configs
• 🌐 Search the web — find docs, tutorials, answers
• 🌍 Open websites — browse pages via automation
• 📋 Clipboard — copy/paste between me and your PC
• 📈 Paper trading — Alpaca stock trading (paper mode)
• 💾 Deploy — push SubZero to USB drives or download updates

🚀 *How to use me:*
Just type normally! Ask me anything or tell me to do something.

*Examples:*
  → `write me a python script that sorts a list`
  → `what files are in my Downloads folder?`
  → `search the web for PyQt6 tutorial`
  → `create a file called hello.py with a hello world program`

*Commands:*
  /start — This welcome message
  /help — Quick command reference
  /tools — List all available tools
  /status — Check Ollama & system status
  /model — Show or change the AI model
  /clear — Clear conversation history

_Type anything to get started!_ ❄️
"""

HELP_TEXT = """
❄️ *Spine Rip — Quick Reference*

*Just type naturally:*
  → Ask questions, give instructions, request code

*Slash commands:*
  /start — Welcome & overview
  /help — This reference
  /tools — List all 31 tools
  /status — Ollama status, model info
  /model — Show/change AI model
  /clear — Reset conversation

*Tool call format (used by AI automatically):*
  `@tool tool_name param="value"`

*Examples:*
  `list the files in C:\\Users`
  `write a Python web scraper`
  `what's the weather in New York?`
  `run the command ipconfig`
"""

TOOLS_TEXT = """
❄️ *Spine Rip — Available Tools (31)*

🖥️ *System*
  • `run_command` — Execute shell commands
  • `run_python` — Run Python code
  • `open_app` — Launch applications

📁 *Files*
  • `file_read` — Read file contents
  • `file_write` — Create/overwrite files
  • `file_append` — Append to files
  • `file_list` — List directory contents
  • `file_delete` — Delete files

🌐 *Web*
  • `web_search` — DuckDuckGo search
  • `web_get` — HTTP GET request
  • `web_post` — HTTP POST request

🌍 *Browser Automation*
  • `browser_open` — Open URL in browser
  • `browser_click` — Click elements
  • `browser_type` — Type into fields
  • `browser_read` — Read page text
  • `browser_screenshot` — Capture page
  • `browser_wait` — Wait for elements
  • `browser_close` — Close browser

📋 *Clipboard*
  • `clipboard_copy` — Copy text
  • `clipboard_paste` — Read clipboard

📈 *Trading (Alpaca Paper)*
  • `trade_quote` — Get stock price
  • `trade_buy` — Buy shares
  • `trade_sell` — Sell shares
  • `trade_positions` — View positions
  • `trade_portfolio` — Portfolio summary
  • `trade_history` — Order history
  • `trade_cancel` — Cancel order
  • `trade_watchlist` — View watchlist

💾 *Deployment*
  • `detect_usb` — Find USB drives
  • `deploy_to_usb` — Copy SubZero to USB
  • `download_subzero` — Download from GitHub
"""


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(WELCOME_TEXT, parse_mode="Markdown")
    log.info(f"/start from {update.effective_user.first_name} ({update.effective_user.id})")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def cmd_tools(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /tools command."""
    await update.message.reply_text(TOOLS_TEXT, parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    cfg = load_config()
    model = cfg.get("model", DEFAULT_MODEL)
    online = is_ollama_online()
    status_icon = "🟢" if online else "🔴"
    user_id = update.effective_user.id
    hist_len = len(_get_history(user_id))

    text = (
        f"❄️ *Spine Rip Status*\n\n"
        f"{status_icon} Ollama: {'Online' if online else 'Offline'}\n"
        f"🧠 Model: `{model}`\n"
        f"💬 Messages in memory: {hist_len}\n"
        f"🖥️ Platform: Windows\n"
        f"⏰ Server time: {datetime.now().strftime('%H:%M:%S')}\n"
    )
    if HAS_RUNTIME:
        text += "🔧 Tool Runtime: Loaded (31 tools)\n"
    else:
        text += "⚠️ Tool Runtime: Not available\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /model command — show or change model."""
    cfg = load_config()
    current = cfg.get("model", DEFAULT_MODEL)

    if context.args:
        new_model = context.args[0]
        cfg["model"] = new_model
        save_config(cfg)
        await update.message.reply_text(
            f"✅ Model changed to `{new_model}`\n"
            f"_(Make sure it's pulled: `ollama pull {new_model}`)_",
            parse_mode="Markdown",
        )
        log.info(f"Model changed to {new_model}")
    else:
        models = ["qwen2.5:1.5b", "llama3.2", "codellama", "deepseek-coder", "mistral"]
        model_list = "\n".join(
            f"  {'→' if m == current else '  '} `{m}`" for m in models
        )
        await update.message.reply_text(
            f"🧠 Current model: `{current}`\n\n"
            f"Available models:\n{model_list}\n\n"
            f"Change with: `/model model_name`",
            parse_mode="Markdown",
        )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command — reset conversation."""
    user_id = update.effective_user.id
    _conversations[user_id] = []
    await update.message.reply_text("🗑️ Conversation cleared. Fresh start!")
    log.info(f"Cleared history for {update.effective_user.first_name}")


# ══════════════════════════════════════════════════════════════
#  Message handler — the main AI bridge
# ══════════════════════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages — send to Ollama AI."""
    user_msg = update.message.text
    if not user_msg or not user_msg.strip():
        return

    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    cfg = load_config()
    model = cfg.get("model", DEFAULT_MODEL)

    log.info(f"[{user_name}] {user_msg[:80]}")

    # Check Ollama is running
    if not is_ollama_online():
        await update.message.reply_text(
            "⚠️ Ollama is offline. Start it on your PC:\n"
            "`ollama serve`\n"
            f"Then make sure the model is pulled:\n"
            f"`ollama pull {model}`",
            parse_mode="Markdown",
        )
        return

    # Show typing indicator
    await update.message.chat.send_action("typing")

    # Save user message
    _add_message(user_id, "user", user_msg)

    # Build prompt and call AI
    prompt = _build_prompt(user_id, user_msg, model)
    response = await asyncio.to_thread(ollama_generate, prompt, model)

    # Save AI response
    _add_message(user_id, "assistant", response)

    # Execute any tool calls from the response
    tool_output = ""
    if HAS_RUNTIME:
        rt = ToolRuntime()
        tool_calls = rt.parse(response)
        if tool_calls:
            results = await asyncio.to_thread(rt.execute_all, tool_calls)
            tool_parts = []
            for r in results:
                icon = "✅" if r.success else "❌"
                tool_parts.append(f"{icon} `{r.tool_name}`: {r.output[:500]}")
            if tool_parts:
                tool_output = "\n\n🔧 *Tool Results:*\n" + "\n".join(tool_parts)

    # Send response (split if too long for Telegram's 4096 char limit)
    full_response = response + tool_output
    if len(full_response) > 4000:
        # Split into chunks
        chunks = [full_response[i:i+4000] for i in range(0, len(full_response), 4000)]
        for chunk in chunks:
            try:
                await update.message.reply_text(chunk, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(chunk)
    else:
        try:
            await update.message.reply_text(full_response, parse_mode="Markdown")
        except Exception:
            # Fallback without markdown if parsing fails
            await update.message.reply_text(full_response)

    log.info(f"[Spine Rip → {user_name}] {response[:80]}...")


# ══════════════════════════════════════════════════════════════
#  Bot lifecycle
# ══════════════════════════════════════════════════════════════

_app_instance: "Application | None" = None
_bot_thread: threading.Thread | None = None
_bot_loop: asyncio.AbstractEventLoop | None = None


def _run_bot(token: str):
    """Run the bot in its own event loop (for threading)."""
    global _app_instance, _bot_loop

    _bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_bot_loop)

    _app_instance = Application.builder().token(token).build()

    # Register handlers
    _app_instance.add_handler(CommandHandler("start", cmd_start))
    _app_instance.add_handler(CommandHandler("help", cmd_help))
    _app_instance.add_handler(CommandHandler("tools", cmd_tools))
    _app_instance.add_handler(CommandHandler("status", cmd_status))
    _app_instance.add_handler(CommandHandler("model", cmd_model))
    _app_instance.add_handler(CommandHandler("clear", cmd_clear))
    _app_instance.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Spine Rip Telegram bot is running! Send /start to your bot.")
    _bot_loop.run_until_complete(_app_instance.run_polling(drop_pending_updates=True))


def start_bot(token: str = None) -> tuple[bool, str]:
    """Start the Telegram bot in a background thread.

    Returns (success, message).
    """
    global _bot_thread

    if not HAS_TELEGRAM:
        return False, "python-telegram-bot not installed. Run: pip install python-telegram-bot"

    if _bot_thread and _bot_thread.is_alive():
        return False, "Bot is already running."

    token = token or get_bot_token()
    if not token:
        return False, "No bot token configured. Set it in ~/.subzero/telegram.json or pass it directly."

    # Save token to config
    cfg = load_config()
    cfg["bot_token"] = token
    save_config(cfg)

    _bot_thread = threading.Thread(target=_run_bot, args=(token,), daemon=True)
    _bot_thread.start()
    return True, "Spine Rip Telegram bot started! Open Telegram and message your bot."


def stop_bot() -> tuple[bool, str]:
    """Stop the running Telegram bot."""
    global _app_instance, _bot_thread, _bot_loop

    if _app_instance and _bot_loop:
        try:
            _bot_loop.call_soon_threadsafe(_app_instance.stop_running)
            _app_instance = None
            _bot_thread = None
            _bot_loop = None
            return True, "Telegram bot stopped."
        except Exception as e:
            return False, f"Error stopping bot: {e}"
    return False, "Bot is not running."


def is_bot_running() -> bool:
    """Check if the bot thread is alive."""
    return _bot_thread is not None and _bot_thread.is_alive()


# ══════════════════════════════════════════════════════════════
#  Standalone entry point
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if not HAS_TELEGRAM:
        print("ERROR: python-telegram-bot not installed.")
        print("Run:  pip install python-telegram-bot")
        sys.exit(1)

    cfg = load_config()
    token = cfg.get("bot_token", "")

    if not token:
        print("=" * 50)
        print("  SPINE RIP — Telegram Bot Setup")
        print("=" * 50)
        print()
        print("To connect Spine Rip to Telegram:")
        print("  1. Open Telegram and message @BotFather")
        print("  2. Send /newbot and follow the prompts")
        print("  3. Copy the bot token BotFather gives you")
        print()
        token = input("Paste your bot token here: ").strip()
        if not token:
            print("No token provided. Exiting.")
            sys.exit(1)
        cfg["bot_token"] = token
        save_config(cfg)
        print(f"\n✅ Token saved to {TELEGRAM_CONFIG}")

    print()
    print("❄️  Starting Spine Rip Telegram bot...")
    print(f"   Model: {cfg.get('model', DEFAULT_MODEL)}")
    print(f"   Ollama: {'Online' if is_ollama_online() else 'OFFLINE — run ollama serve'}")
    print()
    print("Open Telegram and send /start to your bot!")
    print("Press Ctrl+C to stop.\n")

    try:
        app = Application.builder().token(token).build()
        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("help", cmd_help))
        app.add_handler(CommandHandler("tools", cmd_tools))
        app.add_handler(CommandHandler("status", cmd_status))
        app.add_handler(CommandHandler("model", cmd_model))
        app.add_handler(CommandHandler("clear", cmd_clear))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        print("\nBot stopped.")
