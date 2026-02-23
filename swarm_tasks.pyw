"""
SubZero Swarm Task Manager
───────────────────────────
Chat-driven task management with swarm agent collaboration.
• Type tasks in the chat and agents pick them up
• Multiple agents work simultaneously
• Real-time progress, notifications, notes
• Priority, deadlines, assignment tracking
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import threading
import time
import urllib.request
from pathlib import Path
from datetime import datetime, timedelta
from collections import deque
from sz_runtime import ToolRuntime

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

LOGO_PATH = Path(__file__).parent / "logo.png"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SWARM_FILE = os.path.join(SCRIPT_DIR, "swarm_tasks.json")

# ── Colors (Snowflake Dark Transparent) ────────────────────────
BG           = "#000000"
BG_PANEL     = "#020810"
BG_CARD      = "#010610"
BG_INPUT     = "#081428"
FG           = "#e0e0e0"
FG_DIM       = "#445577"
ACCENT       = "#0088ff"
GREEN        = "#00aaff"
YELLOW       = "#55aaff"
RED          = "#ff4444"
CYAN         = "#0088ff"
PINK         = "#4499dd"
BLUE         = "#4499dd"
ORANGE       = "#55ccff"

PRIORITY_COLORS = {"Critical": RED, "High": ORANGE, "Medium": YELLOW, "Low": GREEN}

# ── Agent definitions ──────────────────────────────────────────
AGENTS = [
    {"id": "alpha",   "name": "Agent Alpha",   "icon": "α", "color": "#0088ff", "specialty": "analysis"},
    {"id": "beta",    "name": "Agent Beta",    "icon": "β", "color": "#00aaff", "specialty": "execution"},
    {"id": "gamma",   "name": "Agent Gamma",   "icon": "γ", "color": "#00aaff", "specialty": "research"},
    {"id": "delta",   "name": "Agent Delta",   "icon": "δ", "color": "#55aaff", "specialty": "review"},
    {"id": "epsilon", "name": "Agent Epsilon", "icon": "ε", "color": "#0088ff", "specialty": "testing"},
]


def load_tasks():
    if os.path.exists(SWARM_FILE):
        try:
            with open(SWARM_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_tasks(tasks):
    with open(SWARM_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, default=str)


class OllamaEngine:
    """Lightweight Ollama interface for agent responses."""

    def __init__(self, model="qwen2.5:3b"):
        self.model = model

    def ask(self, prompt, timeout=120):
        """Streaming request to avoid timeouts."""
        try:
            payload = json.dumps({
                "model": self.model, "prompt": prompt, "stream": True,
            }).encode("utf-8")
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            full = []
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                for line in resp:
                    chunk = json.loads(line.decode("utf-8"))
                    token = chunk.get("response", "")
                    if token:
                        full.append(token)
                    if chunk.get("done"):
                        break
            text = "".join(full).strip()
            return text or None
        except Exception:
            return None


class SwarmTaskManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SubZero Swarm Tasks")
        self.root.geometry("1000x700")
        self.root.configure(bg=BG)
        self.root.attributes("-alpha", 0.96)
        self.root.minsize(800, 500)

        self.tasks = load_tasks()
        self.notifications = deque(maxlen=100)
        self.ollama = OllamaEngine()
        self._tool_rt = ToolRuntime()
        self.agent_status = {a["id"]: "idle" for a in AGENTS}

        self._build_ui()
        self._refresh_task_list()
        self._update_agent_panel()
        self._tick()
        self.root.mainloop()

    # ── UI Construction ────────────────────────────────────────

    def _build_ui(self):
        # ─ Header ─
        header = tk.Frame(self.root, bg="#0066cc", height=44)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        self._logo_img = None
        if HAS_PIL and LOGO_PATH.exists():
            try:
                img = Image.open(LOGO_PATH).resize((28, 28), Image.LANCZOS)
                self._logo_img = ImageTk.PhotoImage(img)
                tk.Label(header, image=self._logo_img, bg="#0066cc").pack(side=tk.LEFT, padx=(10, 4))
            except Exception:
                tk.Label(header, text="✦", bg="#0066cc", fg="#00aaff", font=("Segoe UI", 13)).pack(side=tk.LEFT, padx=(10, 4))
        else:
            tk.Label(header, text="✦", bg="#0066cc", fg="#00aaff", font=("Segoe UI", 13)).pack(side=tk.LEFT, padx=(10, 4))
        tk.Label(
            header, text="SWARM TASK MANAGER", bg="#0066cc", fg="white",
            font=("Segoe UI", 12, "bold"),
        ).pack(side=tk.LEFT)
        self.agent_count_label = tk.Label(
            header, text=f"{len(AGENTS)} agents", bg="#0066cc", fg="#cce0ff",
            font=("Segoe UI", 9),
        )
        self.agent_count_label.pack(side=tk.RIGHT, padx=14)

        # ─ Main split: left (chat+tasks) | right (agents+notifications) ─
        self.main_pane = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL, bg="#081428",
            sashwidth=4, sashrelief=tk.FLAT,
        )
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(self.main_pane, bg=BG_PANEL)
        right = tk.Frame(self.main_pane, bg=BG_PANEL)
        self.main_pane.add(left, stretch="always", minsize=400)
        self.main_pane.add(right, stretch="never", minsize=260, width=300)

        # === LEFT SIDE ===
        # ─ Chat input section (top) ─
        self._build_chat_section(left)
        tk.Frame(left, bg="#081428", height=1).pack(fill=tk.X)
        # ─ Task list (bottom) ─
        self._build_task_list(left)

        # === RIGHT SIDE ===
        # ─ Agent status panel ─
        self._build_agent_panel(right)
        tk.Frame(right, bg="#081428", height=1).pack(fill=tk.X)
        # ─ Notifications ─
        self._build_notification_panel(right)

    # ── Chat Section ───────────────────────────────────────────

    def _build_chat_section(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL)
        frame.pack(fill=tk.X, padx=0, pady=0)

        # Section label
        lbl = tk.Frame(frame, bg=BG_PANEL)
        lbl.pack(fill=tk.X, padx=10, pady=(8, 4))
        tk.Label(lbl, text="COMMAND CENTER", bg=BG_PANEL, fg=FG_DIM,
                 font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)

        # Chat log
        self.chat_log = tk.Text(
            frame, bg=BG_CARD, fg=FG, font=("Consolas", 9),
            wrap=tk.WORD, relief=tk.FLAT, borderwidth=0,
            padx=10, pady=6, height=10,
            insertbackground="white", selectbackground=ACCENT,
        )
        self.chat_log.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0, 4))
        self.chat_log.config(state=tk.DISABLED)

        # Color tags
        self.chat_log.tag_configure("user", foreground="#4499dd")
        self.chat_log.tag_configure("system", foreground=FG_DIM)
        self.chat_log.tag_configure("agent", foreground=CYAN)
        self.chat_log.tag_configure("success", foreground=GREEN)
        self.chat_log.tag_configure("error", foreground=RED)
        for a in AGENTS:
            self.chat_log.tag_configure(f"agent_{a['id']}", foreground=a["color"])

        # Right-click menu
        self.chat_ctx = tk.Menu(self.root, tearoff=0, bg="#010610", fg="#e0e0e0")
        self.chat_ctx.add_command(label="Copy", command=self._chat_copy)
        self.chat_ctx.add_command(label="Select All", command=self._chat_select_all)
        self.chat_log.bind("<Button-3>", lambda e: self._popup(e, self.chat_ctx))
        self.chat_log.bind("<Control-c>", lambda e: self._chat_copy())

        self._chat_msg("Swarm ready. Type a task or command below.\n", "system")
        self._chat_msg("Commands: /add, /assign, /status, /swarm, /clear, /select-all, /help\n", "system")

        # Input row
        inp_frame = tk.Frame(frame, bg=BG_PANEL)
        inp_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.chat_input = tk.Entry(
            inp_frame, bg=BG_INPUT, fg=FG, font=("Consolas", 10),
            relief=tk.FLAT, borderwidth=4, insertbackground="white",
        )
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.chat_input.bind("<Return>", lambda e: self._on_chat_enter())
        self.chat_input.focus_set()

        # Right-click on input
        self.input_ctx = tk.Menu(self.root, tearoff=0, bg="#010610", fg="#e0e0e0")
        self.input_ctx.add_command(label="Paste", command=self._input_paste)
        self.input_ctx.add_command(label="Copy", command=self._input_copy)
        self.input_ctx.add_command(label="Clear", command=lambda: self.chat_input.delete(0, tk.END))
        self.chat_input.bind("<Button-3>", lambda e: self._popup(e, self.input_ctx))

        tk.Button(
            inp_frame, text="Send", bg="#0088ff", fg="#000000",
            font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
            activebackground="#0066cc", cursor="hand2", padx=10,
            command=self._on_chat_enter,
        ).pack(side=tk.RIGHT)

        tk.Button(
            inp_frame, text="Swarm All", bg="#4499dd", fg="#000000",
            font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
            activebackground="#0044aa", cursor="hand2", padx=8,
            command=self._swarm_all_tasks,
        ).pack(side=tk.RIGHT, padx=(0, 4))

    # ── Task List ──────────────────────────────────────────────

    def _build_task_list(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL)
        frame.pack(fill=tk.BOTH, expand=True)

        # Section label + controls
        lbl = tk.Frame(frame, bg=BG_PANEL)
        lbl.pack(fill=tk.X, padx=10, pady=(8, 4))
        tk.Label(lbl, text="TASKS", bg=BG_PANEL, fg=FG_DIM,
                 font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
        self.task_count_label = tk.Label(
            lbl, text="0", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI", 8),
        )
        self.task_count_label.pack(side=tk.RIGHT)

        # Action buttons
        btn_row = tk.Frame(frame, bg=BG_PANEL)
        btn_row.pack(fill=tk.X, padx=8, pady=(0, 4))
        for text, cmd, color in [
            ("Select All", self._select_all_tasks, "#010610"),
            ("Complete", self._complete_selected, GREEN),
            ("Delete", self._delete_selected, RED),
            ("Archive Done", self._archive_done, "#081428"),
            ("Export", self._export_tasks, "#010610"),
        ]:
            tk.Button(
                btn_row, text=text, command=cmd, bg=color, fg="white",
                font=("Segoe UI", 8), relief=tk.FLAT, padx=6, cursor="hand2",
            ).pack(side=tk.LEFT, padx=2)

        # Treeview
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Swarm.Treeview",
                         background=BG_CARD, foreground=FG, fieldbackground=BG_CARD,
                         font=("Segoe UI", 9), rowheight=28)
        style.configure("Swarm.Treeview.Heading",
                         background="#020810", foreground=CYAN, font=("Segoe UI", 8, "bold"))
        style.map("Swarm.Treeview", background=[("selected", "#081428")])

        cols = ("status", "task", "priority", "agent", "progress", "due")
        tree_frame = tk.Frame(frame, bg=BG_PANEL)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self.task_tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings", style="Swarm.Treeview",
            selectmode="extended",
        )
        self.task_tree.heading("status", text="⬤")
        self.task_tree.heading("task", text="Task")
        self.task_tree.heading("priority", text="Priority")
        self.task_tree.heading("agent", text="Agent")
        self.task_tree.heading("progress", text="Progress")
        self.task_tree.heading("due", text="Due")

        self.task_tree.column("status", width=30, anchor="center")
        self.task_tree.column("task", width=220)
        self.task_tree.column("priority", width=70, anchor="center")
        self.task_tree.column("agent", width=90, anchor="center")
        self.task_tree.column("progress", width=70, anchor="center")
        self.task_tree.column("due", width=85, anchor="center")

        sb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=sb.set)
        self.task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Tags for status colors
        self.task_tree.tag_configure("pending", foreground=FG_DIM)
        self.task_tree.tag_configure("active", foreground=CYAN)
        self.task_tree.tag_configure("done", foreground=GREEN)
        self.task_tree.tag_configure("failed", foreground=RED)

        # Notes section
        notes_frame = tk.Frame(frame, bg=BG_PANEL)
        notes_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        tk.Label(notes_frame, text="NOTES", bg=BG_PANEL, fg=FG_DIM,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w")
        self.notes_text = tk.Text(
            notes_frame, bg=BG_INPUT, fg=FG, font=("Consolas", 9),
            height=3, wrap=tk.WORD, relief=tk.FLAT, borderwidth=4,
            insertbackground="white",
        )
        self.notes_text.pack(fill=tk.X)
        self.task_tree.bind("<<TreeviewSelect>>", self._on_task_select)

    # ── Agent Panel ────────────────────────────────────────────

    def _build_agent_panel(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL)
        frame.pack(fill=tk.X)

        lbl = tk.Frame(frame, bg=BG_PANEL)
        lbl.pack(fill=tk.X, padx=10, pady=(8, 4))
        tk.Label(lbl, text="SWARM AGENTS", bg=BG_PANEL, fg=FG_DIM,
                 font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)

        self.agent_widgets = {}
        for agent in AGENTS:
            card = tk.Frame(frame, bg=BG_CARD, highlightbackground="#081428", highlightthickness=1)
            card.pack(fill=tk.X, padx=8, pady=2)

            inner = tk.Frame(card, bg=BG_CARD)
            inner.pack(fill=tk.X, padx=8, pady=6)

            # Icon
            icon = tk.Canvas(inner, width=24, height=24, bg=BG_CARD, highlightthickness=0)
            icon.pack(side=tk.LEFT, padx=(0, 8))
            icon.create_oval(2, 2, 22, 22, fill=agent["color"], outline="")
            icon.create_text(12, 12, text=agent["icon"], fill="white", font=("Segoe UI", 9, "bold"))

            # Name + status
            info = tk.Frame(inner, bg=BG_CARD)
            info.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(info, text=agent["name"], bg=BG_CARD, fg=FG,
                     font=("Segoe UI", 9)).pack(anchor="w")
            status_lbl = tk.Label(info, text="● Idle", bg=BG_CARD, fg=FG_DIM,
                                  font=("Segoe UI", 7))
            status_lbl.pack(anchor="w")

            self.agent_widgets[agent["id"]] = {
                "card": card, "status": status_lbl, "icon": icon,
            }

    # ── Notification Panel ─────────────────────────────────────

    def _build_notification_panel(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL)
        frame.pack(fill=tk.BOTH, expand=True)

        lbl = tk.Frame(frame, bg=BG_PANEL)
        lbl.pack(fill=tk.X, padx=10, pady=(8, 4))
        tk.Label(lbl, text="NOTIFICATIONS", bg=BG_PANEL, fg=FG_DIM,
                 font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
        tk.Button(lbl, text="Clear", bg="#010610", fg=FG_DIM,
                  font=("Segoe UI", 7), relief=tk.FLAT, padx=4,
                  command=self._clear_notifications).pack(side=tk.RIGHT)

        self.notif_list = tk.Text(
            frame, bg=BG_CARD, fg=FG, font=("Consolas", 8),
            wrap=tk.WORD, relief=tk.FLAT, borderwidth=0,
            padx=8, pady=4, state=tk.DISABLED,
        )
        self.notif_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.notif_list.tag_configure("time", foreground=FG_DIM)
        self.notif_list.tag_configure("alert", foreground=YELLOW)

    # ── Chat Logic ─────────────────────────────────────────────

    def _chat_msg(self, text, tag="system"):
        self.chat_log.config(state=tk.NORMAL)
        self.chat_log.insert(tk.END, text, tag)
        self.chat_log.see(tk.END)
        self.chat_log.config(state=tk.DISABLED)

    def _on_chat_enter(self):
        raw = self.chat_input.get().strip()
        if not raw:
            return
        self.chat_input.delete(0, tk.END)
        self._chat_msg(f"You: {raw}\n", "user")
        self._process_command(raw)

    def _process_command(self, raw):
        low = raw.lower().strip()

        # /help
        if low == "/help":
            self._chat_msg(
                "Commands:\n"
                "  /add <task> [p:high] [due:2026-03-01]  — Add a task\n"
                "  /assign <task#> <agent>                — Assign agent\n"
                "  /swarm                                 — Swarm all pending tasks\n"
                "  /status                                — Show swarm status\n"
                "  /select-all                            — Select all tasks\n"
                "  /clear                                 — Clear chat\n"
                "  (or just type a task name to add it)\n\n", "system"
            )
            return

        # /clear
        if low == "/clear":
            self.chat_log.config(state=tk.NORMAL)
            self.chat_log.delete("1.0", tk.END)
            self.chat_log.config(state=tk.DISABLED)
            return

        # /status
        if low == "/status":
            self._show_swarm_status()
            return

        # /swarm
        if low == "/swarm":
            self._swarm_all_tasks()
            return

        # /select-all
        if low == "/select-all":
            self._select_all_tasks()
            self._chat_msg("Selected all tasks.\n", "system")
            return

        # /add <task> [p:priority] [due:date]
        if low.startswith("/add "):
            text = raw[5:].strip()
            self._add_task_from_text(text)
            return

        # /assign <index> <agent>
        if low.startswith("/assign "):
            parts = raw[8:].strip().split(None, 1)
            if len(parts) == 2:
                try:
                    idx = int(parts[0]) - 1
                    agent_name = parts[1].lower()
                    agent = next((a for a in AGENTS if agent_name in a["name"].lower() or agent_name == a["id"]), None)
                    if agent and 0 <= idx < len(self.tasks):
                        self.tasks[idx]["agent"] = agent["name"]
                        save_tasks(self.tasks)
                        self._refresh_task_list()
                        self._chat_msg(f"Assigned task #{idx+1} to {agent['name']}.\n", "success")
                        self._notify(f"Task assigned to {agent['name']}: {self.tasks[idx]['name']}")
                        return
                except ValueError:
                    pass
            self._chat_msg("Usage: /assign <task#> <agent-name>\n", "error")
            return

        # Default: treat as a new task
        self._add_task_from_text(raw)

    def _add_task_from_text(self, text):
        """Parse task text with optional p:priority and due:date."""
        import re
        priority = "Medium"
        due = ""

        # Extract p:priority
        m = re.search(r'\bp:(critical|high|medium|low)\b', text, re.IGNORECASE)
        if m:
            priority = m.group(1).capitalize()
            text = text[:m.start()] + text[m.end():]

        # Extract due:date
        m = re.search(r'\bdue:(\S+)', text, re.IGNORECASE)
        if m:
            due = m.group(1)
            text = text[:m.start()] + text[m.end():]

        name = text.strip()
        if not name:
            self._chat_msg("Task name cannot be empty.\n", "error")
            return

        task = {
            "id": int(time.time() * 1000),
            "name": name,
            "priority": priority,
            "status": "pending",
            "agent": "",
            "progress": 0,
            "due": due,
            "notes": "",
            "created": datetime.now().isoformat(),
            "history": [],
        }
        self.tasks.append(task)
        save_tasks(self.tasks)
        self._refresh_task_list()
        self._chat_msg(f"Task added: {name}", "success")
        if priority != "Medium":
            self._chat_msg(f" [{priority}]", "system")
        if due:
            self._chat_msg(f" (due: {due})", "system")
        self._chat_msg("\n", "system")
        self._notify(f"New task: {name}")

    # ── Swarm Execution ────────────────────────────────────────

    def _swarm_all_tasks(self):
        """Assign all pending tasks to available agents and start them."""
        pending = [i for i, t in enumerate(self.tasks) if t["status"] == "pending"]
        if not pending:
            self._chat_msg("No pending tasks to swarm.\n", "system")
            return

        self._chat_msg(f"Swarming {len(pending)} task(s) across {len(AGENTS)} agents...\n", "agent")

        # Round-robin assign agents
        for i, task_idx in enumerate(pending):
            agent = AGENTS[i % len(AGENTS)]
            self.tasks[task_idx]["agent"] = agent["name"]
            self.tasks[task_idx]["status"] = "active"
            self.tasks[task_idx]["progress"] = 0

            self._chat_msg(f"  {agent['icon']} {agent['name']} → ", f"agent_{agent['id']}")
            self._chat_msg(f"{self.tasks[task_idx]['name']}\n", "system")

            # Start agent worker thread
            threading.Thread(
                target=self._agent_work,
                args=(task_idx, agent),
                daemon=True,
            ).start()

        save_tasks(self.tasks)
        self._refresh_task_list()
        self._notify(f"Swarm started: {len(pending)} tasks assigned to {len(AGENTS)} agents")

    def _agent_work(self, task_idx, agent):
        """Simulate an agent working on a task (with optional Ollama assist)."""
        aid = agent["id"]

        # Update agent status
        self.root.after(0, lambda: self._set_agent_status(aid, "working", agent["color"]))

        task = self.tasks[task_idx]

        # Try to get Ollama to help (with tool runtime)
        tool_prompt = self._tool_rt.get_system_prompt()
        ai_result = self.ollama.ask(
            f"You are {agent['name']}, a specialist in {agent['specialty']}.\n"
            f"{tool_prompt}\n"
            f"Complete this task using tools if needed: {task['name']}",
            timeout=30,
        )

        # Execute @tool calls from AI response
        tool_outputs = []
        if ai_result:
            tool_calls = self._tool_rt.parse(ai_result)
            if tool_calls:
                self.root.after(0, lambda: self._chat_msg(
                    f"  {agent['icon']} Executing {len(tool_calls)} tool(s)...\n", f"agent_{aid}"))
                results = self._tool_rt.execute_all(tool_calls)
                for tr in results:
                    status = "\u2713" if tr.success else "\u2717"
                    tool_outputs.append(f"[{status} {tr.tool_name}] {tr.output[:80]}")
                    self.root.after(0, lambda s=status, t=tr: self._chat_msg(
                        f"    [{s} {t.tool_name}] {t.output[:100]}\n",
                        "success" if t.success else "error"))

        # Simulate progress steps
        for pct in [20, 40, 60, 80, 100]:
            time.sleep(0.3)
            self.tasks[task_idx]["progress"] = pct
            self.root.after(0, self._refresh_task_list)

        # Mark complete
        self.tasks[task_idx]["status"] = "done"
        self.tasks[task_idx]["progress"] = 100
        note = ai_result or f"Completed by {agent['name']}"
        if tool_outputs:
            note += "\n" + "\n".join(tool_outputs)
        self.tasks[task_idx]["history"].append({
            "agent": agent["name"],
            "action": "completed",
            "note": note,
            "time": datetime.now().isoformat(),
        })
        save_tasks(self.tasks)

        def finish():
            self._refresh_task_list()
            self._set_agent_status(aid, "idle", FG_DIM)
            self._chat_msg(f"{agent['icon']} {agent['name']}: ", f"agent_{aid}")
            self._chat_msg(f"Completed \"{task['name']}\"\n", "success")
            if ai_result:
                self._chat_msg(f"   → {ai_result[:120]}\n", "system")
            self._notify(f"{agent['name']} completed: {task['name']}")

        self.root.after(0, finish)

    # ── Status & Refresh ───────────────────────────────────────

    def _show_swarm_status(self):
        total = len(self.tasks)
        pending = sum(1 for t in self.tasks if t["status"] == "pending")
        active = sum(1 for t in self.tasks if t["status"] == "active")
        done = sum(1 for t in self.tasks if t["status"] == "done")
        idle_agents = sum(1 for s in self.agent_status.values() if s == "idle")

        self._chat_msg(
            f"─── Swarm Status ───\n"
            f"  Tasks:   {total} total, {pending} pending, {active} active, {done} done\n"
            f"  Agents:  {len(AGENTS)} total, {idle_agents} idle, {len(AGENTS)-idle_agents} working\n"
            f"─────────────────────\n\n", "system"
        )

    def _set_agent_status(self, aid, status, color):
        self.agent_status[aid] = status
        w = self.agent_widgets.get(aid)
        if w:
            label = "● Working..." if status == "working" else "● Idle"
            w["status"].config(text=label, fg=color)
            border = AGENTS[[a["id"] for a in AGENTS].index(aid)]["color"] if status == "working" else "#081428"
            w["card"].config(highlightbackground=border)

    def _update_agent_panel(self):
        for a in AGENTS:
            color = a["color"] if self.agent_status[a["id"]] == "working" else FG_DIM
            self._set_agent_status(a["id"], self.agent_status[a["id"]], color)

    def _refresh_task_list(self):
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)

        for t in self.tasks:
            status_icon = {"pending": "○", "active": "◉", "done": "✓", "failed": "✗"}.get(t["status"], "?")
            pct = f"{t.get('progress', 0)}%"
            agent = t.get("agent", "")
            tag = t.get("status", "pending")
            self.task_tree.insert("", tk.END, values=(
                status_icon, t["name"], t.get("priority", "Medium"),
                agent, pct, t.get("due", ""),
            ), tags=(tag,))

        self.task_count_label.config(text=f"{len(self.tasks)} tasks")

    def _on_task_select(self, event):
        sel = self.task_tree.selection()
        if not sel:
            return
        idx = self.task_tree.index(sel[0])
        if 0 <= idx < len(self.tasks):
            task = self.tasks[idx]
            self.notes_text.delete("1.0", tk.END)
            self.notes_text.insert("1.0", task.get("notes", ""))
            # Show history
            if task.get("history"):
                self.notes_text.insert(tk.END, "\n--- History ---\n")
                for h in task["history"]:
                    self.notes_text.insert(tk.END, f"[{h.get('agent','')}] {h.get('note','')}\n")

    # ── Task Actions ───────────────────────────────────────────

    def _select_all_tasks(self):
        children = self.task_tree.get_children()
        self.task_tree.selection_set(children)

    def _complete_selected(self):
        for item in self.task_tree.selection():
            idx = self.task_tree.index(item)
            if 0 <= idx < len(self.tasks):
                self.tasks[idx]["status"] = "done"
                self.tasks[idx]["progress"] = 100
        save_tasks(self.tasks)
        self._refresh_task_list()
        self._chat_msg("Marked selected tasks as complete.\n", "success")

    def _delete_selected(self):
        indices = sorted([self.task_tree.index(i) for i in self.task_tree.selection()], reverse=True)
        for idx in indices:
            if 0 <= idx < len(self.tasks):
                self.tasks.pop(idx)
        save_tasks(self.tasks)
        self._refresh_task_list()
        self._chat_msg(f"Deleted {len(indices)} task(s).\n", "system")

    def _archive_done(self):
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t["status"] != "done"]
        removed = before - len(self.tasks)
        save_tasks(self.tasks)
        self._refresh_task_list()
        self._chat_msg(f"Archived {removed} completed task(s).\n", "system")

    def _export_tasks(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Text", "*.txt")],
            title="Export Tasks",
        )
        if not path:
            return
        if path.endswith(".txt"):
            with open(path, "w", encoding="utf-8") as f:
                for t in self.tasks:
                    f.write(f"[{t['status'].upper()}] {t['name']} "
                            f"(P:{t.get('priority','')}) "
                            f"Agent:{t.get('agent','-')} "
                            f"{t.get('progress',0)}%\n")
        else:
            save_tasks(self.tasks)
        self._chat_msg(f"Exported to {os.path.basename(path)}\n", "success")

    # ── Notifications ──────────────────────────────────────────

    def _notify(self, message):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {message}"
        self.notifications.append(entry)

        self.notif_list.config(state=tk.NORMAL)
        self.notif_list.insert(tk.END, f"{ts} ", "time")
        self.notif_list.insert(tk.END, f"{message}\n")
        self.notif_list.see(tk.END)
        self.notif_list.config(state=tk.DISABLED)

    def _clear_notifications(self):
        self.notifications.clear()
        self.notif_list.config(state=tk.NORMAL)
        self.notif_list.delete("1.0", tk.END)
        self.notif_list.config(state=tk.DISABLED)

    # ── Helpers ────────────────────────────────────────────────

    def _popup(self, event, menu):
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _chat_copy(self):
        try:
            sel = self.chat_log.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(sel)
        except tk.TclError:
            pass

    def _chat_select_all(self):
        self.chat_log.config(state=tk.NORMAL)
        self.chat_log.tag_add(tk.SEL, "1.0", tk.END)
        self.chat_log.config(state=tk.DISABLED)

    def _input_paste(self):
        try:
            self.chat_input.insert(tk.INSERT, self.root.clipboard_get())
        except tk.TclError:
            pass

    def _input_copy(self):
        try:
            if self.chat_input.selection_present():
                self.root.clipboard_clear()
                self.root.clipboard_append(self.chat_input.selection_get())
        except tk.TclError:
            pass

    def _tick(self):
        """Periodic background tick for deadline checks."""
        now = datetime.now().strftime("%Y-%m-%d")
        for t in self.tasks:
            if t.get("due") and t["due"] <= now and t["status"] == "pending":
                self._notify(f"OVERDUE: {t['name']}")
        self.root.after(60000, self._tick)


if __name__ == "__main__":
    SwarmTaskManager()
