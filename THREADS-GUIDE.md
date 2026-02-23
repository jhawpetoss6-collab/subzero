# SubZero Thread-Split Architecture 🧠

## What Is This?

You asked for the **same dual-brain system** used by advanced AI agents:
- **Front-End**: Responds instantly (keeps conversation flowing)
- **Back-End**: Deep thinking in parallel (heavy lifting)
- **Watchdog**: Autonomous monitor (tracks goals 24/7)

## Architecture

```
┌─────────────────────────────────────┐
│         YOU (User)                  │
└──────────────┬──────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│      FRONT-END (Fast Core)           │
│  - Instant responses                 │
│  - Keeps chat flowing                │
│  - Decides if task needs deep think  │
└──────────────┬───────────────────────┘
               │
               ├──────► Simple Q? → Quick Answer
               │
               └──────► Complex Q? → Spawn Back-End
                                          │
                                          ▼
                            ┌──────────────────────────┐
                            │   BACK-END (Deep Core)   │
                            │  - Runs in background    │
                            │  - Deep analysis         │
                            │  - File-based results    │
                            └──────────────────────────┘

             ┌────────────────────────────────────┐
             │   WATCHDOG (Autonomous Monitor)    │
             │  - Runs continuously               │
             │  - Tracks progress                 │
             │  - Updates status automatically    │
             └────────────────────────────────────┘
```

## How It Works

### 1. Front-End (You see this)
When you ask something, the front-end:
1. Analyzes if it needs deep thinking
2. If simple: Answers immediately
3. If complex: Spawns back-end thread and tells you

**Example:**
```
You: Hello!
[FRONT-END] Hello! How can I help you?

You: Analyze Bitcoin market trends and create a trading strategy
[FRONT-END] Processing your request...
[BACK-END SPAWNED] Task ID: task_12345

I'm on it! Here's what I'm doing:
FRONT-END (me): Keeping our conversation flowing
BACK-END: Deep analysis running in parallel (Task: task_12345)

I can answer other questions while that processes. What else?
```

### 2. Back-End (Silent Worker)
Runs in PowerShell background job:
- Uses Ollama with "deep thinking" prompt
- Saves results to JSON file
- You can check status anytime

### 3. Watchdog (Autonomous)
Monitors your goals continuously:
- Checks progress every 30 seconds
- Tracks task completion
- Updates status automatically
- Runs until you stop it

## Usage

### Basic Interactive Mode
```powershell
.\subzero-threads.ps1
```

### Single Message
```powershell
.\subzero-threads.ps1 "Analyze crypto market"
```

### Commands Inside Interactive Mode

| Command | What It Does |
|---------|-------------|
| `tasks` | List all background tasks |
| `watch` | Start watchdog for a goal |
| `status` | Check watchdog progress |
| `stream task_123` | Watch a task's thought process live |
| `exit` | Quit (stops all threads) |

## Example Session

```powershell
.\subzero-threads.ps1

You: analyze the crypto market and build a trading bot

[FRONT-END] Processing your request...
[BACK-END SPAWNED] Task ID: task_54321

I'm on it! Here's what I'm doing:
FRONT-END (me): Keeping our conversation flowing
BACK-END: Deep analysis running in parallel (Task: task_54321)

You: what's 2+2?
[FRONT-END] 4

You: tasks

[TASKS]
  ... task_54321: analyze the crypto market and build a trading bot...

You: stream task_54321

========== THOUGHT STREAM ==========
Back-End Reasoning for Task: task_54321
=====================================

[STATUS] processing

[STATUS] completed

[RESULT]
{Deep analysis of crypto market...}
{Trading bot strategy...}
{Code implementation...}

=====================================

You: watch
Enter goal: Build crypto trading system

[WATCHDOG STARTED]
Goal: Build crypto trading system
Monitoring every 30 seconds

You: status

========== WATCHDOG STATUS ==========
Goal: Build crypto trading system
Started: 2026-02-21T19:52:00
Status: active

Latest Check:
  Time: 2026-02-21T19:53:30
  Progress: 50%
  Tasks: 1/2
=====================================
```

## Features

### ✅ Non-Blocking
- Front-end always responsive
- Ask new questions while back-end works
- Never "wait" for thinking to finish

### ✅ Parallel Processing
- Multiple back-end tasks at once
- Each task gets its own Ollama instance
- PowerShell background jobs handle concurrency

### ✅ Streaming Thought View
- Watch back-end reasoning live
- See what it's thinking
- Collapsible (don't watch if you don't want)

### ✅ Autonomous Monitoring
- Watchdog tracks goals automatically
- No manual checking needed
- Runs 24/7 (or until you stop it)

## File Structure

```
C:\Users\jhawp\.subzero\
├── tasks\           # Back-end task results
│   ├── task_123.json
│   ├── task_456.json
│   └── task_789.json
├── threads\         # Thread metadata
└── watchdog.json    # Watchdog status
```

## How This Compares

| Feature | SubZero Threads | Regular ChatBot |
|---------|----------------|-----------------|
| **Response Speed** | Instant | Waits for thinking |
| **Multi-tasking** | ✅ Yes | ❌ No |
| **Background Work** | ✅ Yes | ❌ No |
| **Autonomous Monitor** | ✅ Yes | ❌ No |
| **Thought Streaming** | ✅ Yes | ❌ No |

## Advanced: Watchdog For Project

Track a long-term goal:

```powershell
# Start SubZero
.\subzero-threads.ps1

# Set up watchdog
You: watch
Enter goal: Write 80-chapter book

# The watchdog now monitors:
# - Task completion rate
# - Progress toward goal
# - Time spent
# - Checks every 30 seconds

# Check anytime:
You: status
```

## Real-World Use Cases

### 1. Crypto Trading
```
Front-End: Chat about strategy
Back-End: Analyze market data in parallel
Watchdog: Monitor portfolio 24/7
```

### 2. Code Development
```
Front-End: Answer quick questions
Back-End: Write complex code/tests
Watchdog: Track project completion
```

### 3. Research
```
Front-End: Discuss findings
Back-End: Deep literature review
Watchdog: Monitor research progress
```

### 4. Content Creation
```
Front-End: Brainstorm ideas
Back-End: Write chapters
Watchdog: Track 80-chapter book progress
```

## Technical Details

### Back-End Implementation
- PowerShell `Start-Job`
- Separate Ollama process
- JSON file communication
- Non-blocking I/O

### Watchdog Implementation  
- Continuous background job
- Periodic checks (30s default)
- Progress calculation
- Auto-updates watchdog.json

### Front-End
- Pattern matching for complexity
- Smart task delegation
- Instant acknowledgment
- Conversation continuity

## Safety

1. **Local Only** - All processing on your machine
2. **Resource Limits** - PowerShell jobs are lightweight
3. **Clean Shutdown** - `exit` stops all threads
4. **File-Based** - Easy to inspect/debug

## You Built This! 🎉

This is YOUR custom dual-brain AI agent with:
- ✅ Parallel processing
- ✅ Autonomous monitoring
- ✅ Thought streaming
- ✅ Zero API costs
- ✅ 100% local

**No other framework has this architecture at this price (FREE)!**

---

Ready to test? Run: `.\subzero-threads.ps1`
