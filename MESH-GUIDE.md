# SubZero Agent Mesh - Inter-Agent Communication 🕸️

## What You Asked For

Agents that **communicate with each other** so they:
- ✅ Know what tasks are done
- ✅ Don't duplicate work
- ✅ Share knowledge
- ✅ Coordinate actions

## How It Works

```
   Agent 1 (Coder)          Agent 2 (Trader)         Agent 3 (Researcher)
        │                          │                          │
        └─────────► MESSAGE BUS ◄──┴──────────────────────────┘
                          │
                ┌─────────┼─────────┐
                │         │         │
        TASK REGISTRY  MESSAGES  KNOWLEDGE BASE
     (What's done)   (Chat)    (Shared facts)
```

### Components:

1. **Message Bus**: Agents send messages to each other
2. **Task Registry**: Shared list of all tasks (prevents duplicates)
3. **Knowledge Base**: Shared facts learned by all agents
4. **Agent Registry**: Who's online, what they're doing

## Example: Preventing Duplicate Work

```powershell
.\subzero-mesh.ps1

# Spawn agents
[main] You: spawn coder Python Developer
[main] You: spawn trader Day Trader

# Agent 1 does a task
[main] You: switch coder
[coder] You: analyze Bitcoin price trends

[coder] Analyzing Bitcoin...
[TASK REGISTRY] Task registered: analyze Bitcoin price trends
(Saves result to knowledge base)

# Agent 2 tries same task
[coder] You: switch trader
[trader] You: analyze Bitcoin

[trader] I see that agent 'coder' already analyzed Bitcoin price trends.
        Here's what they found: [previous result]
        I'll build upon that work instead of duplicating it.
```

## Features

### 1. Task Registry (Prevents Duplicates)
When an agent starts a task:
- Checks if similar task already done
- If yes: Uses existing result
- If no: Registers new task
- Broadcasts to all agents

### 2. Message Bus (Agent Chat)
Agents can send messages:
- Direct: Agent A → Agent B
- Broadcast: Agent A → ALL

Message types:
- `join`: Agent joined mesh
- `task_registered`: New task started
- `task_update`: Task status changed
- `knowledge_added`: New fact learned

### 3. Knowledge Base (Shared Memory)
All agents contribute to shared knowledge:
- Facts are tagged with topic
- Any agent can query knowledge
- Prevents re-learning same things

### 4. Agent Awareness
Each agent sees:
- Recent messages from others
- Completed tasks by others
- Current status of all agents
- Shared knowledge base

## Usage

### Start Mesh
```powershell
.\subzero-mesh.ps1
```

### Spawn Agents
```
[main] You: spawn coder Python Developer
[main] You: spawn trader Stock Trader  
[main] You: spawn researcher Market Analyst
```

### Switch Between Agents
```
[main] You: switch coder
[coder] You: write a trading bot
```

### View Mesh Status
```
[main] You: mesh

========== AGENT MESH ==========

ACTIVE AGENTS:
  [ONLINE] main
    Role: Coordinator
    Tasks Done: 5
  [ONLINE] coder
    Role: Python Developer
    Tasks Done: 3
    Current: write a trading bot
  [ONLINE] trader
    Role: Stock Trader
    Tasks Done: 2

TASK REGISTRY:
  Pending: 1
  Completed: 9

KNOWLEDGE BASE:
  Facts: 12

MESSAGES:
  Total: 25
  Unread: 3
```

### View Tasks
```
[main] You: tasks

TASKS:
  [completed] analyze Bitcoin price trends
    Assigned: coder
  [completed] create trading strategy
    Assigned: trader
  [pending] implement bot
    Assigned: coder
```

### View Messages
```
[main] You: messages

MESSAGES for main:
  [NEW] From coder: New task: analyze Bitcoin price trends
  [READ] From trader: Task task_123 status: completed
  [NEW] From coder: New knowledge: Bitcoin analysis
```

## Real-World Example: Trading Team

```powershell
.\subzero-mesh.ps1

# Create team
You: spawn analyst Market Analyst
You: spawn coder Python Developer
You: spawn trader Day Trader
You: spawn risk Risk Manager

# Analyst does research
You: switch analyst
You: analyze crypto market trends for next week

# Result saved to task registry + knowledge base

# Coder builds on analyst's work
You: switch coder
You: build trading bot based on market analysis

# Coder sees analyst's work automatically!
[coder] I see analyst already analyzed crypto trends.
        Based on their findings, I'll build a bot that...

# Trader uses both results
You: switch trader
You: execute trades based on analysis

[trader] Using market analysis from analyst
         and trading bot from coder...
         Executing strategy...

# Risk manager monitors all
You: switch risk
You: check if trades are within risk limits

[risk] Checking tasks completed by trader...
       All trades within acceptable risk parameters.
```

## File Structure

```
C:\Users\jhawp\.subzero\
├── agents\              # Agent profiles
│   ├── main.json
│   ├── coder.json
│   ├── trader.json
│   └── analyst.json
├── messages\            # Inter-agent messages
│   ├── msg_123.json
│   ├── msg_456.json
│   └── msg_789.json
├── task-registry.json   # All tasks (prevents duplicates)
└── knowledge-base.json  # Shared facts
```

## Commands

| Command | What It Does |
|---------|-------------|
| `spawn <name> <role>` | Create new agent |
| `agents` | List all agents |
| `mesh` | Show mesh status |
| `tasks` | View task registry |
| `messages` | View agent messages |
| `switch <agent>` | Switch to agent |
| `exit` | Quit |

## How Duplicate Prevention Works

1. **Before starting task**: Agent checks task registry
2. **If similar task exists**: 
   - Agent notifies you
   - Uses existing result
   - Builds upon it instead
3. **If new task**:
   - Registers in task registry
   - Broadcasts to all agents
   - Executes work
   - Saves result

## Benefits

### No Wasted Work
- Agents check what's done before starting
- Build upon each other's work
- Share results automatically

### Faster Completion
- Parallel processing
- No duplicate effort
- Collaborative problem-solving

### Better Results
- Multiple perspectives
- Shared knowledge
- Coordinated actions

### Full Transparency
- See all agent activities
- Track all messages
- Monitor progress

## Advanced: Custom Communication

```powershell
# Agent 1 asks Agent 2 for help
[coder] You: I need help with API integration

# This creates a message
# Agent 2 sees it when they check messages
[trader] You: messages
[NEW] From coder: I need help with API integration
```

## Comparison

| Feature | SubZero Mesh | Regular Multi-Agent |
|---------|-------------|---------------------|
| **Task Deduplication** | ✅ Automatic | ❌ Manual |
| **Shared Knowledge** | ✅ Yes | ❌ No |
| **Agent Chat** | ✅ Yes | ❌ No |
| **Task Registry** | ✅ Yes | ❌ No |
| **Free** | ✅ Yes | Varies |
| **Local** | ✅ Yes | Varies |

## You Built This! 🎉

**SubZero Agent Mesh** is YOUR custom swarm intelligence system with:
- ✅ Inter-agent communication
- ✅ Duplicate work prevention
- ✅ Shared knowledge base
- ✅ Task coordination
- ✅ 100% free & local

No other framework at this price (FREE) has this level of agent coordination!

---

Ready to test? Run: `.\subzero-mesh.ps1`
