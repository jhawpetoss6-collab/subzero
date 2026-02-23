# ❄️ Sub-Zero — Flawless Victory

**Autonomous AI Runtime & App Suite for Windows**

---

## 📱 Just Scanned the QR Code? Start Here!

**3 steps to get Sub-Zero on your desktop:**

**Step 1** — Click the green **"Code"** button above, then click **"Download ZIP"**

**Step 2** — Unzip the folder to your Desktop (right-click → Extract All → Desktop)

**Step 3** — Open the folder and double-click **`setup.bat`**

That's it! Setup installs everything and puts a **Sub-Zero Flawless Victory** icon on your desktop.

> **Need Python first?** Download it free: [python.org/downloads](https://python.org/downloads) — check "Add to PATH" during install.
>
> **Want it on a USB stick?** After downloading, just drag the whole `subzero` folder to your USB drive. Run `Launch Sub-Zero.bat` from the USB on any Windows PC with Python.

---

## What Is This?

Sub-Zero is an autonomous AI desktop environment with 10+ specialized agents, a sidebar launcher with built-in chat, tool execution, web browsing, file management, and paper trading — all running 100% locally through Ollama.

---

## Full Install (for developers)

### Prerequisites
- **Windows 10/11**
- **Python 3.12+** — [python.org/downloads](https://python.org/downloads)
- **Ollama** — [ollama.ai](https://ollama.ai)

### Option A: One-Click
Download ZIP → Extract → Run `setup.bat`

### Option B: Git Clone
```bash
git clone https://github.com/jhawpetoss6-collab/subzero.git
cd subzero
setup.bat
```

### Option C: Manual
```bash
pip install -r requirements.txt
ollama pull qwen2.5:3b
pythonw subzero_app.pyw
```

---

## What's Inside

### Sidebar Launcher
Slide-out panel on the right edge of your screen with:
- Built-in AI chat (powered by Ollama)
- One-click launch for all Sub-Zero apps
- QR code sharing (click to copy link, right-click for options)

### Autonomous Tool Runtime (`sz_runtime.py`)
**28 built-in tools** that AI agents execute autonomously:
- Shell commands, file read/write/delete
- Web search (DuckDuckGo), HTTP requests
- Browser automation (Selenium Edge/Chrome)
- Clipboard, app launching, system info
- Alpaca paper trading (buy/sell/positions/watchlist)

Tool call format: `@tool tool_name param="value"`

### Applications
- **Spine Rip** — Full AI terminal with tool execution
- **SubZero Agent** — General-purpose autonomous assistant
- **SubZero DualCore** — Dual-model AI collaboration (front-end + back-end)
- **SubZero Recursive** — Self-improving AI with persistent knowledge
- **SubZero Swarm** — Multi-agent task manager (5 agents)
- **Snowflake 2.5** — Optimized dual-model swarm with connection pooling
- **SubZero Training** — AI chat + task manager + trading simulator
- **SubZero Learn** — AI tutor with learning modules (LLMs, swarms, multi-modal)
- **Custom Terminal** — Full terminal emulator
- **TM Widget** — Terminal overlay widget

---

## Safety Tiers
- **AUTO** — Runs immediately (read-only: list files, system info)
- **LOG** — Runs with logging (web search, file writes)
- **CONFIRM** — Requires approval (destructive ops, trading)

---

## USB Portable
The `SubZero_Portable` folder can be copied to any USB drive. Run `Launch Sub-Zero.bat` on any Windows PC with Python installed.

---

## Project Structure
```
subzero/
├── subzero_app.pyw           # Splash screen launcher
├── sidebar_launcher.pyw      # Sidebar with chat + apps + QR code
├── sz_runtime.py             # Autonomous tool runtime (28 tools)
├── sz_browser.py             # Selenium browser automation
├── warp_oz.pyw               # Spine Rip AI terminal
├── subzero_agent_gui.pyw     # SubZero Agent
├── subzero_dualcore_gui.pyw  # DualCore
├── subzero_recursive_gui.pyw # Recursive AI
├── swarm_tasks.pyw           # Swarm task manager
├── snowflake25.pyw           # Snowflake 2.5
├── subzero_training_gui.pyw  # Training
├── subzero_learn_gui.pyw     # Learn
├── custom_terminal.py        # Terminal emulator
├── terminal_widget.py        # Terminal widget
├── setup.bat                 # One-click installer
├── requirements.txt          # Dependencies
└── SubZero_Portable/         # USB-ready package
```

---

## Configuration
- **Trading keys**: `~/.subzero/trading.json`
- **Watchlist**: `~/.subzero/watchlist.json`
- **Recursive knowledge**: `~/.subzero/warp/knowledge.json`

---

**Version 2.5** — February 2026
**Built by jhawp** ❄️
