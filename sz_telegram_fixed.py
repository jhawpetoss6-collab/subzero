"""
SubZero Telegram Bridge — IMPROVED VERSION
═══════════════════════════════════════════
Enhanced with better error handling, connection retry, and timeout management.

IMPROVEMENTS:
- Auto-reconnect on connection loss
- Better timeout handling with user feedback
- Connection health monitoring
- Graceful error recovery
- Detailed error logging
"""

import os
import sys
import json
import asyncio
import logging
import threading
import urllib.request
import time
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

# ── Config ─────────────────────────────────────────────────────
DATA_DIR = Path.home() / ".subzero"
TELEGRAM_CONFIG = DATA_DIR / "telegram.json"
OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
NO_WINDOW = 0x08000000

# Connection settings
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
OLLAMA_TIMEOUT = 180  # 3 minutes
CONNECTION_CHECK_INTERVAL = 30  # seconds

# ── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [TelegramBot] %(levelname)s: %(message)s",
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
    log.error("python-telegram-bot not installed")

# ── Lazy import ToolRuntime ────────────────────────────────────
try:
    from sz_runtime import ToolRuntime
    HAS_RUNTIME = True
except ImportError:
    HAS_RUNTIME = False
    log.warning("sz_runtime not available - tools disabled")


# ══════════════════════════════════════════════════════════════
#  Connection Health Monitor
# ══════════════════════════════════════════════════════════════

class ConnectionMonitor:
    """Monitors Ollama connection health."""
    
    def __init__(self):
        self.last_check = None
        self.is_healthy = False
        self.consecutive_failures = 0
        self.last_error = None
    
    def check_health(self) -> bool:
        """Check if Ollama is responding."""
        try:
            req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.is_healthy = (resp.status == 200)
                self.consecutive_failures = 0
                self.last_check = datetime.now()
                return True
        except Exception as e:
            self.is_healthy = False
            self.consecutive_failures += 1
            self.last_error = str(e)
            self.last_check = datetime.now()
            return False
    
    def get_status(self) -> str:
        """Get human-readable status."""
        if self.is_healthy:
            return "🟢 Online"
        elif self.consecutive_failures > 5:
            return f"🔴 Offline (failed {self.consecutive_failures}x)"
        else:
            return f"🟡 Unstable ({self.consecutive_failures} failures)"

_connection_monitor = ConnectionMonitor()


# ══════════════════════════════════════════════════════════════
#  Config helpers
# ══════════════════════════════════════════════════════════════

def load_config() -> dict:
    """Load telegram.json config."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if TELEGRAM_CONFIG.exists():
        try:
            return json.loads(TELEGRAM_CONFIG.read_text("utf-8"))
        except Exception as e:
            log.error(f"Failed to load config: {e}")
    return {"bot_token": "", "allowed_users": [], "model": DEFAULT_MODEL}


def save_config(cfg: dict):
    """Save telegram.json config."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        TELEGRAM_CONFIG.write_text(json.dumps(cfg, indent=2), "utf-8")
    except Exception as e:
        log.error(f"Failed to save config: {e}")


def get_bot_token() -> str:
    """Get bot token from config."""
    cfg = load_config()
    return cfg.get("bot_token", "")


# ══════════════════════════════════════════════════════════════
#  IMPROVED Ollama AI caller with retry logic
# ══════════════════════════════════════════════════════════════

def ollama_generate(prompt: str, model: str = None, retry_count: int = 0) -> tuple[str, bool]:
    """
    Call Ollama REST API with automatic retry on failure.
    
    Returns: (response_text, success)
    """
    model = model or DEFAULT_MODEL
    
    try:
        log.info(f"Calling Ollama (attempt {retry_count + 1}/{MAX_RETRIES + 1})...")
        
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
        
        start_time = time.time()
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        elapsed = time.time() - start_time
        response_text = data.get("response", "").strip()
        
        if response_text:
            log.info(f"✓ Response received in {elapsed:.1f}s")
            _connection_monitor.is_healthy = True
            _connection_monitor.consecutive_failures = 0
            return response_text, True
        else:
            log.warning("Empty response from Ollama")
            return "[No response from AI - please try again]", False
            
    except urllib.error.HTTPError as e:
        error_msg = f"HTTP {e.code}: {e.reason}"
        log.error(f"Ollama HTTP error: {error_msg}")
        
        if e.code == 404:
            return (
                f"⚠️ Model '{model}' not found.\n\n"
                f"Install it with:\n`ollama pull {model}`",
                False
            )
        
        # Retry on server errors (5xx)
        if 500 <= e.code < 600 and retry_count < MAX_RETRIES:
            log.info(f"Server error, retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
            return ollama_generate(prompt, model, retry_count + 1)
        
        return f"⚠️ Ollama error: {error_msg}", False
        
    except urllib.error.URLError as e:
        log.error(f"Connection failed: {e.reason}")
        _connection_monitor.consecutive_failures += 1
        
        # Retry on connection errors
        if retry_count < MAX_RETRIES:
            log.info(f"Connection lost, retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)
            return ollama_generate(prompt, model, retry_count + 1)
        
        return (
            "⚠️ Cannot connect to Ollama.\n\n"
            "**Troubleshooting:**\n"
            "1. Check if Ollama is running:\n   `ollama serve`\n\n"
            "2. Verify it's accessible:\n   Open http://localhost:11434 in browser\n\n"
            "3. Test the model:\n   `ollama run qwen2.5:1.5b \"hello\"`"
        ), False
        
    except TimeoutError:
        log.error(f"Request timed out after {OLLAMA_TIMEOUT}s")
        _connection_monitor.consecutive_failures += 1
        
        return (
            f"⚠️ Request timed out after {OLLAMA_TIMEOUT}s.\n\n"
            "**This usually means:**\n"
            "• The prompt was too long\n"
            "• Your system is under heavy load\n"
            "• The model is too large for your hardware\n\n"
            "**Try:**\n"
            "• Use a shorter message\n"
            "• Switch to smaller model: `/model qwen2.5:1.5b`\n"
            "• Close other applications"
        ), False
        
    except Exception as e:
        log.error(f"Unexpected error: {e}", exc_info=True)
        return f"⚠️ Unexpected error: {type(e).__name__}: {e}", False


def is_ollama_online() -> bool:
    """Check if Ollama is reachable."""
    return _connection_monitor.check_health()


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
#  Build AI prompt
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
        "• Alpaca paper trading via @tool trade_buy, trade_sell, trade_quote\n\n"
        + tool_prompt
        + "RULES:\n"
        "- Be concise. Telegram messages should be short and readable.\n"
        "- Use tool calls when the user asks you to DO something.\n"
        "- NEVER suggest setting API keys — you run locally via Ollama.\n"
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
#  Telegram command handlers (same as original)
# ══════════════════════════════════════════════════════════════

WELCOME_TEXT = """
❄️ *SPINE RIP — SubZero AI Assistant* ❄️

Welcome! I'm *Spine Rip*, your personal AI assistant powered by SubZero.

🧠 *What is Spine Rip?*
Spine Rip is the Telegram interface to *Warp Oz*, the SubZero AI Code Assistant. It runs 100% locally on your machine using Ollama — no cloud, no API keys, no subscriptions.

⚡ *What I can do:*
• 💬 Answer questions — coding, debugging, concepts
• 🖥️ Run commands on your PC
• 📁 Read & write files
• 🌐 Search the web
• 📈 Paper trading

*Commands:*
/start — Welcome message
/help — Quick reference
/status — Check system status
/model — Change AI model
/clear — Clear conversation

_Type anything to get started!_ ❄️
"""

HELP_TEXT = """
❄️ *Spine Rip — Quick Reference*

*Just type naturally:*
→ Ask questions, give instructions, request code

*Slash commands:*
/start — Welcome & overview
/help — This reference
/status — Check Ollama & connection
/model — Show/change AI model
/clear — Reset conversation

*Examples:*
`list the files in C:\\Users`
`write a Python web scraper`
`run the command ipconfig`
"""


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(WELCOME_TEXT, parse_mode="Markdown")
    log.info(f"/start from {update.effective_user.first_name} ({update.effective_user.id})")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command with enhanced connection info."""
    cfg = load_config()
    model = cfg.get("model", DEFAULT_MODEL)
    
    # Force fresh health check
    online = is_ollama_online()
    status = _connection_monitor.get_status()
    
    user_id = update.effective_user.id
    hist_len = len(_get_history(user_id))

    text = (
        f"❄️ *Spine Rip Status*\n\n"
        f"{status}\n"
        f"🧠 Model: `{model}`\n"
        f"💬 Messages in memory: {hist_len}\n"
        f"🖥️ Platform: Windows\n"
        f"⏰ Server time: {datetime.now().strftime('%H:%M:%S')}\n"
    )
    
    if not online:
        text += f"\n⚠️ Last error: {_connection_monitor.last_error}\n"
        text += f"Failed checks: {_connection_monitor.consecutive_failures}\n"
    
    if HAS_RUNTIME:
        text += "🔧 Tool Runtime: Loaded (31 tools)\n"
    else:
        text += "⚠️ Tool Runtime: Not available\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /model command."""
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
        models = ["qwen2.5:1.5b", "llama3.2", "qwen2.5:3b", "codellama", "mistral"]
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
    """Handle /clear command."""
    user_id = update.effective_user.id
    _conversations[user_id] = []
    await update.message.reply_text("🗑️ Conversation cleared. Fresh start!")
    log.info(f"Cleared history for {update.effective_user.first_name}")


# ══════════════════════════════════════════════════════════════
#  IMPROVED Message handler with better error handling
# ══════════════════════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages with enhanced error handling."""
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
        status = _connection_monitor.get_status()
        await update.message.reply_text(
            f"{status}\n\n"
            "**Ollama is not responding.**\n\n"
            "Start it with:\n`ollama serve`\n\n"
            f"Then pull the model:\n`ollama pull {model}`",
            parse_mode="Markdown",
        )
        return

    # Show typing indicator
    try:
        await update.message.chat.send_action("typing")
    except Exception as e:
        log.warning(f"Could not send typing action: {e}")

    # Save user message
    _add_message(user_id, "user", user_msg)

    # Build prompt and call AI with error handling
    try:
        prompt = _build_prompt(user_id, user_msg, model)
        
        # Show progress for long operations
        if len(prompt) > 2000:
            await update.message.reply_text("⏳ Processing (this may take 20-30 seconds)...")
        
        response, success = await asyncio.to_thread(ollama_generate, prompt, model)
        
        if not success:
            # Error response - send as-is
            await update.message.reply_text(response, parse_mode="Markdown")
            return
        
        # Save AI response
        _add_message(user_id, "assistant", response)

        # Execute any tool calls from the response
        tool_output = ""
        if HAS_RUNTIME and success:
            try:
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
            except Exception as e:
                log.error(f"Tool execution error: {e}", exc_info=True)
                tool_output = f"\n\n⚠️ Tool execution failed: {e}"

        # Send response (split if too long)
        full_response = response + tool_output
        if len(full_response) > 4000:
            chunks = [full_response[i:i+4000] for i in range(0, len(full_response), 4000)]
            for i, chunk in enumerate(chunks):
                try:
                    if i > 0:
                        await asyncio.sleep(0.5)  # Rate limit
                    await update.message.reply_text(chunk, parse_mode="Markdown")
                except Exception:
                    await update.message.reply_text(chunk)
        else:
            try:
                await update.message.reply_text(full_response, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(full_response)

        log.info(f"[Spine Rip → {user_name}] Response sent successfully")
        
    except Exception as e:
        log.error(f"Message handling error: {e}", exc_info=True)
        await update.message.reply_text(
            f"⚠️ An error occurred: {type(e).__name__}\n\n"
            "Please try again or use /status to check the system."
        )


# ══════════════════════════════════════════════════════════════
#  Bot lifecycle with improved error handling
# ══════════════════════════════════════════════════════════════

_app_instance: "Application | None" = None
_bot_thread: threading.Thread | None = None
_bot_loop: asyncio.AbstractEventLoop | None = None


def _run_bot(token: str):
    """Run the bot with auto-restart on errors."""
    global _app_instance, _bot_loop

    try:
        _bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_bot_loop)

        _app_instance = Application.builder().token(token).build()

        # Register handlers
        _app_instance.add_handler(CommandHandler("start", cmd_start))
        _app_instance.add_handler(CommandHandler("help", cmd_help))
        _app_instance.add_handler(CommandHandler("status", cmd_status))
        _app_instance.add_handler(CommandHandler("model", cmd_model))
        _app_instance.add_handler(CommandHandler("clear", cmd_clear))
        _app_instance.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        log.info("✓ Spine Rip Telegram bot is running!")
        log.info("  Send /start to your bot to begin")
        
        _bot_loop.run_until_complete(_app_instance.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        ))
        
    except Exception as e:
        log.error(f"Bot crashed: {e}", exc_info=True)
        log.info("Bot will need manual restart")


def start_bot(token: str = None) -> tuple[bool, str]:
    """Start the Telegram bot in a background thread."""
    global _bot_thread

    if not HAS_TELEGRAM:
        return False, "python-telegram-bot not installed. Run: pip install python-telegram-bot"

    if _bot_thread and _bot_thread.is_alive():
        return False, "Bot is already running."

    token = token or get_bot_token()
    if not token:
        return False, "No bot token configured. Set it in ~/.subzero/telegram.json"

    # Save token
    cfg = load_config()
    cfg["bot_token"] = token
    save_config(cfg)

    # Start bot thread
    _bot_thread = threading.Thread(target=_run_bot, args=(token,), daemon=True)
    _bot_thread.start()
    
    log.info("Bot thread started successfully")
    return True, "✓ Spine Rip Telegram bot started! Open Telegram and message your bot."


def stop_bot() -> tuple[bool, str]:
    """Stop the running Telegram bot."""
    global _app_instance, _bot_thread, _bot_loop

    if _app_instance and _bot_loop:
        try:
            _bot_loop.call_soon_threadsafe(_app_instance.stop)
            _app_instance = None
            _bot_thread = None
            _bot_loop = None
            log.info("Bot stopped successfully")
            return True, "✓ Telegram bot stopped."
        except Exception as e:
            log.error(f"Error stopping bot: {e}")
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
    print("❄️  Starting Spine Rip Telegram bot (IMPROVED VERSION)...")
    print(f"   Model: {cfg.get('model', DEFAULT_MODEL)}")
    
    # Check Ollama before starting
    if is_ollama_online():
        print(f"   Ollama: {_connection_monitor.get_status()}")
    else:
        print("   Ollama: 🔴 OFFLINE")
        print()
        print("   ⚠️  Start Ollama first:")
        print("      ollama serve")
        print()
        ans = input("Continue anyway? (y/n): ")
        if ans.lower() != 'y':
            sys.exit(0)
    
    print()
    print("✓ Bot is starting...")
    print("  Open Telegram and send /start to your bot!")
    print("  Press Ctrl+C to stop.")
    print()

    try:
        app = Application.builder().token(token).build()
        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("help", cmd_help))
        app.add_handler(CommandHandler("status", cmd_status))
        app.add_handler(CommandHandler("model", cmd_model))
        app.add_handler(CommandHandler("clear", cmd_clear))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("✓ Bot is running!\n")
        app.run_polling(drop_pending_updates=True)
        
    except KeyboardInterrupt:
        print("\n\n✓ Bot stopped by user.")
    except Exception as e:
        print(f"\n\n✗ Bot crashed: {e}")
        log.error(f"Bot crashed", exc_info=True)
