import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import subprocess
import threading
import json
import os
import re
import shutil
import base64
import mimetypes
import difflib
import urllib.request
from pathlib import Path
from datetime import datetime

from collections import deque
from sz_runtime import ToolRuntime

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False


# ============================================================
# CommBridge — Communication bridge between Terminal & SubZero
# ============================================================

class CommBridge:
    """Manages health monitoring, message queuing, and communication
    between the Terminal panel and SubZero panel.

    Handles scenarios where:
    - Both sides are working normally
    - SubZero (Ollama) goes offline mid-conversation
    - SubZero comes back online after being down
    - Messages need to be queued and retried
    """

    # Connection states
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    CHECKING = "checking"

    def __init__(self, subzero_agent, heartbeat_interval=5):
        self.agent = subzero_agent
        self.heartbeat_interval = heartbeat_interval  # seconds

        # State tracking
        self.status = self.CHECKING
        self.last_status = None
        self.last_check_time = None
        self.consecutive_failures = 0
        self.total_messages_sent = 0
        self.total_messages_failed = 0

        # Message queue for offline buffering
        self.message_queue = deque(maxlen=50)

        # Callbacks — set by the UI
        self.on_status_change = None      # (old_status, new_status) -> None
        self.on_message_queued = None     # (prompt, queue_size) -> None
        self.on_message_delivered = None  # (prompt, response) -> None
        self.on_message_failed = None    # (prompt, error) -> None
        self.on_queue_drained = None     # (count_delivered) -> None

        # Heartbeat control
        self._heartbeat_running = False
        self._heartbeat_thread = None

    def start_heartbeat(self):
        """Start the background heartbeat thread."""
        if self._heartbeat_running:
            return
        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._heartbeat_thread.start()

    def stop_heartbeat(self):
        """Stop the heartbeat thread."""
        self._heartbeat_running = False

    def _heartbeat_loop(self):
        """Periodically check Ollama connectivity."""
        import time
        while self._heartbeat_running:
            old_status = self.status
            reachable = self.agent.is_ollama_running()
            self.last_check_time = datetime.now()

            if reachable:
                self.consecutive_failures = 0
                if old_status == self.DISCONNECTED:
                    self.status = self.RECONNECTING
                    self._notify_status_change(old_status, self.RECONNECTING)
                    # Drain the queue now that we're back online
                    self._drain_queue()
                self.status = self.CONNECTED
                if old_status != self.CONNECTED:
                    self._notify_status_change(old_status, self.CONNECTED)
            else:
                self.consecutive_failures += 1
                self.status = self.DISCONNECTED
                if old_status != self.DISCONNECTED:
                    self._notify_status_change(old_status, self.DISCONNECTED)

            time.sleep(self.heartbeat_interval)

    def _notify_status_change(self, old, new):
        """Fire the status change callback if registered."""
        if self.on_status_change and old != new:
            self.on_status_change(old, new)

    def send_message(self, prompt, callback=None):
        """Send a message to SubZero, or queue it if offline.

        Args:
            prompt: The user's message.
            callback: Optional (response, error) -> None called when done.
        Returns:
            'sent' if message was dispatched, 'queued' if buffered.
        """
        if self.status == self.DISCONNECTED:
            # Queue the message for later delivery
            self.message_queue.append({"prompt": prompt, "callback": callback})
            if self.on_message_queued:
                self.on_message_queued(prompt, len(self.message_queue))
            return "queued"

        # Dispatch immediately in a thread
        self.total_messages_sent += 1
        thread = threading.Thread(
            target=self._dispatch, args=(prompt, callback), daemon=True
        )
        thread.start()
        return "sent"

    def _dispatch(self, prompt, callback=None):
        """Actually call SubZero and handle the result."""
        try:
            response = self.agent.chat(prompt)
            if self.agent.last_error:
                # The agent returned an error message
                self.total_messages_failed += 1
                if self.on_message_failed:
                    self.on_message_failed(prompt, self.agent.last_error)
                if callback:
                    callback(response, self.agent.last_error)
            else:
                if self.on_message_delivered:
                    self.on_message_delivered(prompt, response)
                if callback:
                    callback(response, None)
        except Exception as e:
            self.total_messages_failed += 1
            if self.on_message_failed:
                self.on_message_failed(prompt, str(e))
            if callback:
                callback(None, str(e))

    def _drain_queue(self):
        """Attempt to deliver all queued messages now that we're reconnected."""
        delivered = 0
        while self.message_queue:
            msg = self.message_queue.popleft()
            try:
                response = self.agent.chat(msg["prompt"])
                if not self.agent.last_error:
                    delivered += 1
                    if self.on_message_delivered:
                        self.on_message_delivered(msg["prompt"], response)
                    if msg.get("callback"):
                        msg["callback"](response, None)
                else:
                    # Still failing — put it back and stop
                    self.message_queue.appendleft(msg)
                    break
            except Exception:
                self.message_queue.appendleft(msg)
                break

        if delivered > 0 and self.on_queue_drained:
            self.on_queue_drained(delivered)

    def retry_queue(self):
        """Manually retry queued messages. Returns count delivered."""
        if not self.message_queue:
            return 0
        count_before = len(self.message_queue)
        self._drain_queue()
        return count_before - len(self.message_queue)

    def get_status_info(self):
        """Return a dict with current bridge status information."""
        return {
            "status": self.status,
            "last_check": self.last_check_time.strftime("%H:%M:%S") if self.last_check_time else "never",
            "consecutive_failures": self.consecutive_failures,
            "queued_messages": len(self.message_queue),
            "total_sent": self.total_messages_sent,
            "total_failed": self.total_messages_failed,
            "model": self.agent.model,
            "heartbeat_interval": f"{self.heartbeat_interval}s",
        }


class CustomTerminal:
    def __init__(self, root):
        self.root = root
        self.root.title("SubZero Terminal")
        self.root.geometry("800x600")
        self.root.configure(bg="#000000")
        self.root.attributes("-alpha", 0.96)

        # LLM API settings
        self.config_path = os.path.join(os.path.dirname(__file__), "terminal_config.json")
        self.llm_config = self.load_config()

        # Attached files for the next AI message
        self.attached_files = []

        # Autocorrect settings
        self.autocorrect_enabled = True
        self.last_failed_command = None

        # --- SubZero LLM Agent + CommBridge ---
        self.subzero = SubZeroAgent()
        self.subzero_panel_visible = False
        self.bridge = CommBridge(self.subzero, heartbeat_interval=5)
        self._setup_bridge_callbacks()

        # --- Resizable split pane (terminal left | SubZero right) ---
        self.paned = tk.PanedWindow(
            root, orient=tk.HORIZONTAL, bg="#081428",
            sashwidth=6, sashrelief=tk.FLAT,
        )
        self.paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 0))

        # --- Output frame with text widget + scrollbar ---
        output_frame = tk.Frame(self.paned, bg="#000000")
        self.paned.add(output_frame, stretch="always", minsize=200)

        self.scrollbar = tk.Scrollbar(output_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_output = tk.Text(
            output_frame,
            wrap=tk.WORD,
            bg="#000000",
            fg="#e0e0e0",
            font=("Consolas", 11),
            insertbackground="#0088ff",
            yscrollcommand=self.scrollbar.set,
            relief=tk.FLAT,
            borderwidth=0,
            selectbackground="#081428",
            selectforeground="#e0e0e0",
        )
        self.text_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.text_output.yview)
        self.text_output.config(state=tk.DISABLED)

        # --- SubZero Chat Panel (hidden by default, added to paned when toggled) ---
        self.sz_panel = tk.Frame(self.paned, bg="#000000")
        # Not added to paned yet — toggled by the SubZero button

        # Panel header
        sz_header = tk.Frame(self.sz_panel, bg="#020810")
        sz_header.pack(fill=tk.X)
        # Connection status dot (green/red/yellow) in header
        self.sz_status_dot = tk.Label(
            sz_header, text="\u25CF", bg="#020810", fg="#445577",
            font=("Consolas", 12), padx=4,
        )
        self.sz_status_dot.pack(side=tk.LEFT, padx=(6, 0))
        tk.Label(
            sz_header, text="SubZero Chat", bg="#020810", fg="#0088ff",
            font=("Consolas", 11, "bold"), padx=4, pady=6,
        ).pack(side=tk.LEFT)
        tk.Button(
            sz_header, text="X", command=self.toggle_subzero_panel,
            bg="#081428", fg="#4499dd", font=("Consolas", 9, "bold"),
            relief=tk.FLAT, padx=6,
        ).pack(side=tk.RIGHT, padx=4, pady=2)
        # Model label
        self.sz_model_label = tk.Label(
            sz_header, text=f"({self.subzero.model})", bg="#020810", fg="#4499dd",
            font=("Consolas", 9),
        )
        self.sz_model_label.pack(side=tk.LEFT)
        # Queue count label (shows when messages are queued)
        self.sz_queue_label = tk.Label(
            sz_header, text="", bg="#020810", fg="#55aaff",
            font=("Consolas", 9),
        )
        self.sz_queue_label.pack(side=tk.LEFT, padx=(6, 0))

        # Panel chat output
        sz_output_frame = tk.Frame(self.sz_panel, bg="#000000")
        sz_output_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 0))

        self.sz_scrollbar = tk.Scrollbar(sz_output_frame)
        self.sz_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.sz_output = tk.Text(
            sz_output_frame, wrap=tk.WORD, bg="#000000", fg="#e0e0e0",
            font=("Consolas", 10), insertbackground="#0088ff",
            yscrollcommand=self.sz_scrollbar.set, relief=tk.FLAT,
            borderwidth=0, selectbackground="#081428",
        )
        self.sz_output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.sz_scrollbar.config(command=self.sz_output.yview)
        self.sz_output.config(state=tk.DISABLED)

        # Panel input
        sz_input_frame = tk.Frame(self.sz_panel, bg="#000000")
        sz_input_frame.pack(fill=tk.X, padx=4, pady=4)

        self.sz_input = tk.Entry(
            sz_input_frame, bg="#081428", fg="#e0e0e0",
            font=("Consolas", 10), insertbackground="#0088ff",
            relief=tk.FLAT, borderwidth=4,
        )
        self.sz_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.sz_input.bind("<Return>", lambda e: self.sz_send_message())

        tk.Button(
            sz_input_frame, text="Send", command=self.sz_send_message,
            bg="#0088ff", fg="#000000", font=("Consolas", 9, "bold"),
            relief=tk.FLAT, padx=8,
        ).pack(side=tk.RIGHT)

        # Quick action buttons in panel
        sz_actions = tk.Frame(self.sz_panel, bg="#000000")
        sz_actions.pack(fill=tk.X, padx=4, pady=(0, 4))
        self.sz_chat_visible = True
        tk.Button(
            sz_actions, text="Clear Chat", command=self.sz_clear_chat,
            bg="#081428", fg="#4499dd", font=("Consolas", 8),
            relief=tk.FLAT,
        ).pack(side=tk.LEFT, padx=2)
        self.sz_status_btn = tk.Button(
            sz_actions, text="Status", command=self.sz_toggle_text,
            bg="#081428", fg="#4499dd", font=("Consolas", 8),
            relief=tk.FLAT,
        )
        self.sz_status_btn.pack(side=tk.LEFT, padx=2)

        # Welcome message
        self._sz_append("SubZero ready. Type a message and press Enter.\n\n")

        # Right-click context menu for copy/select/paste
        self.context_menu = tk.Menu(root, tearoff=0, bg="#010610", fg="#e0e0e0")
        self.context_menu.add_command(label="Copy", command=self.copy_selection)
        self.context_menu.add_command(label="Select All", command=self.select_all)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Paste to Input", command=self.paste_to_input)

        self.text_output.bind("<Button-3>", self.show_context_menu)
        # Ctrl+C to copy from terminal output
        self.text_output.bind("<Control-c>", lambda e: self.copy_selection())
        # Ctrl+V to paste into the currently focused input
        root.bind("<Control-v>", self._global_paste)
        # Ctrl+C from SubZero output too
        self.sz_output.bind("<Control-c>", lambda e: self._copy_from_sz())
        self.sz_output.bind("<Button-3>", self._show_sz_context_menu)

        # SubZero panel context menu
        self.sz_context_menu = tk.Menu(root, tearoff=0, bg="#010610", fg="#e0e0e0")
        self.sz_context_menu.add_command(label="Copy", command=self._copy_from_sz)
        self.sz_context_menu.add_command(label="Select All", command=self._select_all_sz)
        self.sz_context_menu.add_separator()
        self.sz_context_menu.add_command(label="Paste to SubZero Input", command=self._paste_to_sz)

        # Right-click menu for SubZero input field (typing area)
        self.sz_input_menu = tk.Menu(root, tearoff=0, bg="#010610", fg="#e0e0e0")
        self.sz_input_menu.add_command(label="Paste", command=self._paste_to_sz)
        self.sz_input_menu.add_command(label="Copy", command=lambda: self._copy_from_entry(self.sz_input))
        self.sz_input_menu.add_command(label="Select All", command=lambda: self.sz_input.select_range(0, tk.END))
        self.sz_input_menu.add_separator()
        self.sz_input_menu.add_command(label="Clear", command=lambda: self.sz_input.delete(0, tk.END))
        self.sz_input.bind("<Button-3>", lambda e: self._show_menu(e, self.sz_input_menu))

        # --- Input frame with entry + button ---
        input_frame = tk.Frame(root, bg="#000000")
        input_frame.pack(fill=tk.X, padx=5, pady=5)

        prompt_label = tk.Label(
            input_frame, text=">", bg="#000000", fg="#0088ff",
            font=("Consolas", 12, "bold")
        )
        prompt_label.pack(side=tk.LEFT)

        self.command_input = tk.Entry(
            input_frame,
            bg="#081428",
            fg="#e0e0e0",
            font=("Consolas", 11),
            insertbackground="#0088ff",
            relief=tk.FLAT,
            borderwidth=4,
        )
        self.command_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        self.command_input.bind("<Return>", self._on_enter)
        self.command_input.focus_set()

        # Right-click menu for command input field (gray typing area)
        self.cmd_input_menu = tk.Menu(root, tearoff=0, bg="#010610", fg="#e0e0e0")
        self.cmd_input_menu.add_command(label="Paste", command=self.paste_to_input)
        self.cmd_input_menu.add_command(label="Copy", command=lambda: self._copy_from_entry(self.command_input))
        self.cmd_input_menu.add_command(label="Select All", command=lambda: self.command_input.select_range(0, tk.END))
        self.cmd_input_menu.add_separator()
        self.cmd_input_menu.add_command(label="Clear", command=lambda: self.command_input.delete(0, tk.END))
        self.command_input.bind("<Button-3>", lambda e: self._show_menu(e, self.cmd_input_menu))

        self.run_button = tk.Button(
            input_frame,
            text="Run",
            command=self.run_command,
            bg="#081428",
            fg="#00aaff",
            font=("Consolas", 10, "bold"),
            relief=tk.FLAT,
            padx=10,
        )
        self.run_button.pack(side=tk.RIGHT)

        # Ask AI button (remote API)
        self.ai_button = tk.Button(
            input_frame,
            text="Ask AI",
            command=self.ask_ai,
            bg="#081428",
            fg="#0088ff",
            font=("Consolas", 10, "bold"),
            relief=tk.FLAT,
            padx=10,
        )
        self.ai_button.pack(side=tk.RIGHT, padx=(0, 4))

        # SubZero toggle button (local Ollama LLM)
        self.subzero_button = tk.Button(
            input_frame,
            text="SubZero",
            command=self.toggle_subzero_panel,
            bg="#081428",
            fg="#4499dd",
            font=("Consolas", 10, "bold"),
            relief=tk.FLAT,
            padx=10,
        )
        self.subzero_button.pack(side=tk.RIGHT, padx=(0, 4))

        # --- Toolbar frame ---
        toolbar = tk.Frame(root, bg="#000000")
        toolbar.pack(fill=tk.X, padx=5, pady=(0, 5))

        self.settings_button = tk.Button(
            toolbar, text="API Settings", command=self.open_settings,
            bg="#010610", fg="#457", font=("Consolas", 9), relief=tk.FLAT,
        )
        self.settings_button.pack(side=tk.LEFT)

        self.export_button = tk.Button(
            toolbar, text="Export Log", command=self.export_log,
            bg="#010610", fg="#457", font=("Consolas", 9), relief=tk.FLAT,
        )
        self.export_button.pack(side=tk.LEFT, padx=(4, 0))

        self.import_button = tk.Button(
            toolbar, text="Import Log", command=self.import_log,
            bg="#010610", fg="#457", font=("Consolas", 9), relief=tk.FLAT,
        )
        self.import_button.pack(side=tk.LEFT, padx=(4, 0))

        self.attach_button = tk.Button(
            toolbar, text="Attach File", command=self.attach_file,
            bg="#010610", fg="#55aaff", font=("Consolas", 9), relief=tk.FLAT,
        )
        self.attach_button.pack(side=tk.LEFT, padx=(4, 0))

        self.clear_attach_button = tk.Button(
            toolbar, text="Clear Files", command=self.clear_attachments,
            bg="#010610", fg="#457", font=("Consolas", 9), relief=tk.FLAT,
        )
        self.clear_attach_button.pack(side=tk.LEFT, padx=(4, 0))

        self.autocorrect_toggle = tk.Button(
            toolbar, text="AutoCorrect: ON", command=self.toggle_autocorrect,
            bg="#001a33", fg="#00aaff", font=("Consolas", 9), relief=tk.FLAT,
        )
        self.autocorrect_toggle.pack(side=tk.LEFT, padx=(4, 0))

        # ScreenCast: 3-state button (OFF → ON → Cast SubZero)
        self._cast_state = 0  # 0=normal, 1=text off, 2=text on, next=cast
        self._cast_saved = ""  # saved terminal text when toggled off
        self.cast_btn = tk.Button(
            toolbar, text="ScreenCast", command=self._cycle_cast,
            bg="#010610", fg="#457", font=("Consolas", 9), relief=tk.FLAT,
        )
        self.cast_btn.pack(side=tk.LEFT, padx=(4, 0))

        # SwitchTerm: cycle through up to 4 open SubZero AI terminals
        self._switch_index = 0  # current terminal slot (0-3)
        self._switch_cast_files = self._get_cast_files()
        self.switch_btn = tk.Button(
            toolbar, text="SwitchTerm", command=self._cycle_switch_term,
            bg="#010610", fg="#0088ff", font=("Consolas", 9), relief=tk.FLAT,
        )
        self.switch_btn.pack(side=tk.LEFT, padx=(4, 0))

        self.bridge_visible = True  # tracks whether the bridge status bar is shown
        self.bridge_toggle_btn = tk.Button(
            toolbar, text="Bridge: ON", command=self.toggle_bridge_view,
            bg="#001a33", fg="#00aaff", font=("Consolas", 9), relief=tk.FLAT,
        )
        self.bridge_toggle_btn.pack(side=tk.LEFT, padx=(4, 0))

        self.output_visible = True  # tracks whether terminal text is shown
        self.output_toggle_btn = tk.Button(
            toolbar, text="Output: ON", command=self.toggle_output_view,
            bg="#001a33", fg="#00aaff", font=("Consolas", 9), relief=tk.FLAT,
        )
        self.output_toggle_btn.pack(side=tk.LEFT, padx=(4, 0))

        # Attachment status label
        self.attach_label = tk.Label(
            toolbar, text="", bg="#000000", fg="#55aaff",
            font=("Consolas", 9)
        )
        self.attach_label.pack(side=tk.LEFT, padx=(8, 0))

        # --- Drag-and-drop zone ---
        if HAS_DND:
            self.text_output.drop_target_register(DND_FILES)
            self.text_output.dnd_bind("<<Drop>>", self._on_drop)
        else:
            # Fallback: a visible drop hint
            drop_frame = tk.Frame(root, bg="#010610", height=30)
            drop_frame.pack(fill=tk.X, padx=5, pady=(0, 2))
            tk.Label(
                drop_frame,
                text="Drag & drop requires tkinterdnd2  |  Use 'Attach File' button instead",
                bg="#010610", fg="#445577", font=("Consolas", 9),
            ).pack(pady=4)

        # --- Connection status bar (bottom of window) ---
        self.status_bar = tk.Frame(root, bg="#000000", height=22)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_bar.pack_propagate(False)

        self.status_dot_main = tk.Label(
            self.status_bar, text="\u25CF", bg="#000000", fg="#445577",
            font=("Consolas", 10),
        )
        self.status_dot_main.pack(side=tk.LEFT, padx=(6, 2))

        self.status_label = tk.Label(
            self.status_bar, text="Bridge: checking...", bg="#000000", fg="#445577",
            font=("Consolas", 8), anchor="w",
        )
        self.status_label.pack(side=tk.LEFT, padx=(0, 10))

        self.queue_status_label = tk.Label(
            self.status_bar, text="", bg="#000000", fg="#55aaff",
            font=("Consolas", 8), anchor="w",
        )
        self.queue_status_label.pack(side=tk.LEFT)

        self.heartbeat_label = tk.Label(
            self.status_bar, text="", bg="#000000", fg="#234555",
            font=("Consolas", 8), anchor="e",
        )
        self.heartbeat_label.pack(side=tk.RIGHT, padx=(0, 6))

        # Confirm widgets loaded
        self.append_output("❄ SubZero Terminal — Dark Transparent\n")
        self.append_output("Type a command and press Enter, or type a question and click Ask AI.\n")
        self.append_output("Click 'SubZero' to chat with your local LLM (Ollama).\n")
        self.append_output("Attach files (images, text, audio, video) to include them in your AI prompt.\n")
        if not self.llm_config.get("api_key"):
            self.append_output("[Tip] Click 'API Settings' to configure your remote LLM API key.\n")
        self.append_output(f"[SubZero] Model: {self.subzero.model} | "
                           f"Memory: {len(self.subzero.conversation)} messages\n")
        self.append_output("Type 'bridge status' to view communication bridge info.\n")
        self.append_output("\n")

        # Start the CommBridge heartbeat
        self.bridge.start_heartbeat()

    def toggle_output_view(self):
        """Toggle terminal output text visibility for a clean command-line view."""
        if self.output_visible:
            # Save current text, then clear the display
            self._saved_output = self.text_output.get("1.0", tk.END)
            self.text_output.config(state=tk.NORMAL)
            self.text_output.delete("1.0", tk.END)
            self.text_output.config(state=tk.DISABLED)
            self.output_visible = False
            self.output_toggle_btn.config(text="Output: OFF", bg="#001122")
        else:
            # Restore the saved text
            self.text_output.config(state=tk.NORMAL)
            self.text_output.delete("1.0", tk.END)
            if hasattr(self, '_saved_output'):
                self.text_output.insert("1.0", self._saved_output.rstrip("\n"))
            self.text_output.see(tk.END)
            self.text_output.config(state=tk.DISABLED)
            self.output_visible = True
            self.output_toggle_btn.config(text="Output: ON", bg="#001a33")

    # Max age (seconds) for a cast file to be considered "live"
    CAST_MAX_AGE = 120

    def _is_cast_live(self, path):
        """Return True if the cast file exists and was written recently."""
        try:
            if not os.path.exists(path):
                return False
            age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))).total_seconds()
            return age <= self.CAST_MAX_AGE
        except Exception:
            return False

    def _get_cast_files(self):
        """Return ordered list of cast file paths for up to 4 terminals."""
        base = os.path.join(os.path.expanduser("~"), ".subzero")
        files = [
            os.path.join(base, "subzero_cast.txt"),
            os.path.join(base, "subzero_cast_2.txt"),
            os.path.join(base, "subzero_cast_3.txt"),
            os.path.join(base, "subzero_cast_4.txt"),
        ]
        return files

    def _cycle_switch_term(self):
        """Cycle through up to 4 SubZero AI terminal cast files on each click."""
        self._switch_cast_files = self._get_cast_files()

        # Find which cast files are live (recently written)
        available = []
        for i, path in enumerate(self._switch_cast_files):
            if self._is_cast_live(path):
                available.append((i, path))

        if not available:
            self.append_output("[SwitchTerm] No SubZero AI terminals found. "
                               "Open a SubZero terminal from the sidebar first.\n")
            self.switch_btn.config(text="SwitchTerm", bg="#010610")
            return

        # Find the next available terminal after the current index
        found_next = False
        for idx, path in available:
            if idx > self._switch_index:
                self._switch_index = idx
                found_next = True
                break
        if not found_next:
            # Wrap around to the first available
            self._switch_index = available[0][0]

        # Read and display the selected terminal's cast file
        cast_path = self._switch_cast_files[self._switch_index]
        term_label = "Main" if self._switch_index == 0 else str(self._switch_index + 1)
        try:
            with open(cast_path, "r", encoding="utf-8", errors="replace") as f:
                term_text = f.read().strip()
        except Exception:
            term_text = ""

        if term_text:
            self.text_output.config(state=tk.NORMAL)
            self.text_output.delete("1.0", tk.END)
            self.text_output.insert(
                "1.0",
                f"── SwitchTerm [{term_label}] — SubZero AI Terminal ──\n\n{term_text}\n"
            )
            self.text_output.see(tk.END)
            self.text_output.config(state=tk.DISABLED)
            self.switch_btn.config(
                text=f"Term {term_label}",
                bg="#001a44", fg="#0088ff",
            )
        else:
            self.append_output(
                f"[SwitchTerm] Terminal {term_label} cast file is empty.\n"
            )
            self.switch_btn.config(text=f"Term {term_label}", bg="#001122")

    def _cycle_cast(self):
        """2-click toggle: Cast ON (show live terminal) → Cast OFF (reset to blank)."""
        if self._cast_state == 0:
            # --- Cast ON: save original terminal text, then show cast content ---
            self._cast_saved = self.text_output.get("1.0", tk.END)

            cast_file = os.path.join(os.path.expanduser("~"), ".subzero", "subzero_cast.txt")
            term_text = ""
            try:
                if self._is_cast_live(cast_file):
                    with open(cast_file, "r", encoding="utf-8", errors="replace") as f:
                        term_text = f.read().strip()
            except Exception:
                pass

            if term_text:
                self.text_output.config(state=tk.NORMAL)
                self.text_output.delete("1.0", tk.END)
                self.text_output.insert("1.0", f"── ScreenCast from SubZero AI Terminal ──\n\n{term_text}\n")
                self.text_output.see(tk.END)
                self.text_output.config(state=tk.DISABLED)
                self.cast_btn.config(text="Cast: ON", bg="#001a33", fg="#00aaff")
                self._cast_state = 1
            else:
                # Nothing live — don't change state, just notify
                self._cast_saved = ""
                self.append_output("[ScreenCast] No live SubZero Terminal — open one from the sidebar first.\n")
                self.cast_btn.config(text="ScreenCast", bg="#010610")

        else:
            # --- Cast OFF: clear cast content, restore original terminal text ---
            self.text_output.config(state=tk.NORMAL)
            self.text_output.delete("1.0", tk.END)
            if self._cast_saved:
                self.text_output.insert("1.0", self._cast_saved.rstrip("\n"))
            self.text_output.see(tk.END)
            self.text_output.config(state=tk.DISABLED)

            # Full reset
            self._cast_saved = ""
            self._cast_state = 0
            self.cast_btn.config(text="ScreenCast", bg="#010610", fg="#457")

    def toggle_bridge_view(self):
        """Toggle the entire CommBridge status bar and heartbeat visibility."""
        if self.bridge_visible:
            self.status_bar.pack_forget()
            self.bridge_visible = False
            self.bridge_toggle_btn.config(text="Bridge: OFF", bg="#001122")
            self.bridge.stop_heartbeat()
            self.append_output("[Bridge] View hidden and heartbeat paused.\n")
        else:
            self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
            self.bridge_visible = True
            self.bridge_toggle_btn.config(text="Bridge: ON", bg="#001a33")
            self.bridge.start_heartbeat()
            self.append_output("[Bridge] View restored and heartbeat resumed.\n")

    def _on_enter(self, event):
        """Handle Enter key — run command from main input."""
        self.run_command()
        return "break"  # Prevent default behavior

    def show_context_menu(self, event):
        """Show the right-click context menu."""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _show_sz_context_menu(self, event):
        """Show right-click menu on SubZero output."""
        try:
            self.sz_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.sz_context_menu.grab_release()

    def copy_selection(self):
        """Copy highlighted text from terminal output to clipboard."""
        try:
            selected = self.text_output.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
        except tk.TclError:
            pass  # Nothing selected

    def _copy_from_sz(self):
        """Copy highlighted text from SubZero output to clipboard."""
        try:
            selected = self.sz_output.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
        except tk.TclError:
            pass

    def select_all(self):
        """Select all text in the terminal output area."""
        self.text_output.config(state=tk.NORMAL)
        self.text_output.tag_add(tk.SEL, "1.0", tk.END)
        self.text_output.config(state=tk.DISABLED)

    def _select_all_sz(self):
        """Select all text in the SubZero output area."""
        self.sz_output.config(state=tk.NORMAL)
        self.sz_output.tag_add(tk.SEL, "1.0", tk.END)
        self.sz_output.config(state=tk.DISABLED)

    def paste_to_input(self):
        """Paste clipboard content into the command input field."""
        try:
            clip = self.root.clipboard_get()
            self.command_input.insert(tk.INSERT, clip)
        except tk.TclError:
            pass  # Clipboard empty

    def _paste_to_sz(self):
        """Paste clipboard into the SubZero input field."""
        try:
            clip = self.root.clipboard_get()
            self.sz_input.insert(tk.INSERT, clip)
        except tk.TclError:
            pass

    def _global_paste(self, event):
        """Ctrl+V handler — paste into whichever input is focused."""
        focused = self.root.focus_get()
        if focused == self.sz_input:
            self._paste_to_sz()
        elif focused == self.command_input:
            # Entry widgets handle Ctrl+V natively, but just in case:
            try:
                clip = self.root.clipboard_get()
                self.command_input.insert(tk.INSERT, clip)
            except tk.TclError:
                pass
        else:
            # If focus is on a text output, paste into command input
            self.paste_to_input()
        return "break"

    def _show_menu(self, event, menu):
        """Show a right-click context menu at the cursor position."""
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_from_entry(self, entry):
        """Copy selected text from an Entry widget to clipboard."""
        try:
            if entry.selection_present():
                selected = entry.selection_get()
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
        except tk.TclError:
            pass

    # --- CommBridge callbacks ---
    def _setup_bridge_callbacks(self):
        """Wire up CommBridge events to the UI."""
        self.bridge.on_status_change = self._bridge_status_changed
        self.bridge.on_message_queued = self._bridge_message_queued
        self.bridge.on_message_delivered = self._bridge_message_delivered
        self.bridge.on_message_failed = self._bridge_message_failed
        self.bridge.on_queue_drained = self._bridge_queue_drained

    def _bridge_status_changed(self, old_status, new_status):
        """Called by CommBridge when connection status changes."""
        # Color map: connected=green, disconnected=red, reconnecting=yellow, checking=gray
        colors = {
            CommBridge.CONNECTED: "#00aaff",
            CommBridge.DISCONNECTED: "#ff1744",
            CommBridge.RECONNECTING: "#55aaff",
            CommBridge.CHECKING: "#445577",
        }
        color = colors.get(new_status, "#445577")
        labels = {
            CommBridge.CONNECTED: "Bridge: connected",
            CommBridge.DISCONNECTED: "Bridge: disconnected",
            CommBridge.RECONNECTING: "Bridge: reconnecting...",
            CommBridge.CHECKING: "Bridge: checking...",
        }

        def update_ui():
            # Update status bar
            self.status_dot_main.config(fg=color)
            self.status_label.config(text=labels.get(new_status, new_status), fg=color)

            # Update SubZero panel header dot
            self.sz_status_dot.config(fg=color)

            # Update sash color based on status
            sash_colors = {
                CommBridge.CONNECTED: "#0066cc",
                CommBridge.DISCONNECTED: "#002244",
                CommBridge.RECONNECTING: "#0055aa",
                CommBridge.CHECKING: "#0a1e3a",
            }
            self.paned.config(bg=sash_colors.get(new_status, "#0a1e3a"))

            # Update heartbeat timestamp
            if self.bridge.last_check_time:
                self.heartbeat_label.config(
                    text=f"\u2764 {self.bridge.last_check_time.strftime('%H:%M:%S')}"
                )

            # Notify in terminal on status transitions
            if new_status == CommBridge.DISCONNECTED and old_status != CommBridge.CHECKING:
                self.append_output(
                    f"[Bridge] SubZero connection lost. Messages will be queued.\n"
                )
                if self.subzero_panel_visible:
                    self._sz_append("[Bridge] Connection lost. Messages will be queued and sent when reconnected.\n")
            elif new_status == CommBridge.RECONNECTING:
                self.append_output("[Bridge] SubZero reconnecting...\n")
                if self.subzero_panel_visible:
                    self._sz_append("[Bridge] Reconnecting...\n")
            elif new_status == CommBridge.CONNECTED and old_status in (
                CommBridge.DISCONNECTED, CommBridge.RECONNECTING, CommBridge.CHECKING
            ):
                self.append_output("[Bridge] SubZero connected.\n")
                if self.subzero_panel_visible:
                    self._sz_append("[Bridge] Connected.\n")

        self.root.after(0, update_ui)

    def _bridge_message_queued(self, prompt, queue_size):
        """Called when a message is queued because SubZero is offline."""
        def update_ui():
            short = prompt[:40] + ("..." if len(prompt) > 40 else "")
            self._sz_append(f"[Queued] \"{short}\" ({queue_size} in queue)\n")
            self.sz_queue_label.config(text=f"\u231B {queue_size} queued")
            self.queue_status_label.config(text=f"Queue: {queue_size} pending")
        self.root.after(0, update_ui)

    def _bridge_message_delivered(self, prompt, response):
        """Called when the bridge successfully delivers a queued message."""
        def update_ui():
            short = prompt[:40] + ("..." if len(prompt) > 40 else "")
            self._sz_append(f"[Delivered] \"{short}\"\n")
            self._sz_append(f"SubZero: {response}\n\n")
            # Update queue count
            qsize = len(self.bridge.message_queue)
            if qsize > 0:
                self.sz_queue_label.config(text=f"\u231B {qsize} queued")
                self.queue_status_label.config(text=f"Queue: {qsize} pending")
            else:
                self.sz_queue_label.config(text="")
                self.queue_status_label.config(text="")
        self.root.after(0, update_ui)

    def _bridge_message_failed(self, prompt, error):
        """Called when a message fails to deliver."""
        def update_ui():
            short = prompt[:40] + ("..." if len(prompt) > 40 else "")
            self._sz_append(f"[Failed] \"{short}\" - {error}\n")
        self.root.after(0, update_ui)

    def _bridge_queue_drained(self, count_delivered):
        """Called when queued messages have been auto-delivered after reconnect."""
        def update_ui():
            self._sz_append(f"[Bridge] Delivered {count_delivered} queued message(s).\n")
            self.append_output(f"[Bridge] Delivered {count_delivered} queued message(s) to SubZero.\n")
            qsize = len(self.bridge.message_queue)
            if qsize == 0:
                self.sz_queue_label.config(text="")
                self.queue_status_label.config(text="")
            else:
                self.sz_queue_label.config(text=f"\u231B {qsize} queued")
                self.queue_status_label.config(text=f"Queue: {qsize} pending")
        self.root.after(0, update_ui)

    # --- Provider presets ---
    PRESETS = {
        "OpenAI": {
            "api_url": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-3.5-turbo",
            "auth_header": "Bearer",
            "response_path": "choices.0.message.content",
        },
        "Anthropic (Claude)": {
            "api_url": "https://api.anthropic.com/v1/messages",
            "model": "claude-3-haiku-20240307",
            "auth_header": "x-api-key",
            "response_path": "content.0.text",
        },
        "Ollama (Local)": {
            "api_url": "http://localhost:11434/api/chat",
            "model": "qwen2.5:3b",
            "auth_header": "",
            "response_path": "message.content",
        },
        "LM Studio (Local)": {
            "api_url": "http://localhost:1234/v1/chat/completions",
            "model": "local-model",
            "auth_header": "Bearer",
            "response_path": "choices.0.message.content",
        },
        "Custom": {
            "api_url": "",
            "model": "",
            "auth_header": "Bearer",
            "response_path": "choices.0.message.content",
        },
    }

    # --- Config load/save ---
    def load_config(self):
        """Load LLM config from file."""
        defaults = {
            "provider": "OpenAI",
            "api_key": "",
            "api_url": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-3.5-turbo",
            "auth_header": "Bearer",
            "response_path": "choices.0.message.content",
            "system_prompt": "You are a helpful assistant.",
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    saved = json.load(f)
                defaults.update(saved)
            except Exception:
                pass
        return defaults

    def save_config(self):
        """Save LLM config to file."""
        with open(self.config_path, "w") as f:
            json.dump(self.llm_config, f, indent=2)

    # --- Settings dialog ---
    def open_settings(self):
        """Open a dialog to configure any LLM provider."""
        win = tk.Toplevel(self.root)
        win.title("API Settings")
        win.geometry("560x420")
        win.configure(bg="#000000")
        win.transient(self.root)
        win.grab_set()

        row = 0

        # Provider preset dropdown
        tk.Label(win, text="Provider", bg="#000000", fg="#e0e0e0",
                 font=("Consolas", 10)).grid(row=row, column=0, padx=10, pady=8, sticky="e")
        provider_var = tk.StringVar(value=self.llm_config.get("provider", "Custom"))
        provider_menu = tk.OptionMenu(win, provider_var, *self.PRESETS.keys())
        provider_menu.config(bg="#081428", fg="#e0e0e0", font=("Consolas", 10),
                             highlightthickness=0)
        provider_menu.grid(row=row, column=1, padx=10, pady=8, sticky="w")
        row += 1

        # Editable fields
        fields = [
            ("API Key", "api_key", True),
            ("API URL", "api_url", False),
            ("Model", "model", False),
            ("Auth Header", "auth_header", False),
            ("Response Path", "response_path", False),
            ("System Prompt", "system_prompt", False),
        ]
        entries = {}
        for label_text, key, masked in fields:
            tk.Label(win, text=label_text, bg="#000000", fg="#e0e0e0",
                     font=("Consolas", 10)).grid(row=row, column=0, padx=10, pady=6, sticky="e")
            entry = tk.Entry(win, width=45, bg="#081428", fg="#e0e0e0",
                             font=("Consolas", 10), insertbackground="#0088ff")
            entry.grid(row=row, column=1, padx=10, pady=6)
            entry.insert(0, self.llm_config.get(key, ""))
            if masked:
                entry.config(show="*")
            entries[key] = entry
            row += 1

        def apply_preset(*_):
            preset = self.PRESETS.get(provider_var.get(), {})
            for key, val in preset.items():
                if key in entries:
                    entries[key].delete(0, tk.END)
                    entries[key].insert(0, val)

        provider_var.trace_add("write", apply_preset)

        def save_and_close():
            self.llm_config["provider"] = provider_var.get()
            for key, entry in entries.items():
                self.llm_config[key] = entry.get().strip()
            self.save_config()
            self.append_output(f"[Settings] Saved — provider: {self.llm_config['provider']}, "
                               f"model: {self.llm_config['model']}\n\n")
            win.destroy()

        tk.Button(win, text="Save", command=save_and_close,
                  bg="#0088ff", fg="#000000", font=("Consolas", 10, "bold"),
                  relief=tk.FLAT, padx=20).grid(row=row, column=0, columnspan=2, pady=12)

    # --- File attachment ---
    FILE_CATEGORIES = {
        "image": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".ico", ".svg"},
        "audio": {".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".wma"},
        "video": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".webm", ".flv"},
        "text":  {".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml",
                  ".py", ".js", ".ts", ".html", ".css", ".c", ".cpp", ".h",
                  ".java", ".go", ".rs", ".rb", ".php", ".sh", ".bat", ".ps1",
                  ".log", ".ini", ".cfg", ".toml"},
    }

    def _categorize_file(self, path):
        """Return the category of a file based on its extension."""
        ext = os.path.splitext(path)[1].lower()
        for cat, exts in self.FILE_CATEGORIES.items():
            if ext in exts:
                return cat
        return "binary"

    def _process_file(self, path):
        """Read a file and return a dict with its type, name, and content."""
        category = self._categorize_file(path)
        name = os.path.basename(path)
        size = os.path.getsize(path)
        result = {"path": path, "name": name, "category": category, "size": size}

        if category == "text":
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    result["content"] = f.read(50000)  # limit to 50KB text
            except Exception as e:
                result["content"] = f"[Could not read: {e}]"

        elif category == "image":
            with open(path, "rb") as f:
                result["base64"] = base64.b64encode(f.read()).decode("utf-8")
            mime = mimetypes.guess_type(path)[0] or "image/png"
            result["mime"] = mime

        elif category in ("audio", "video"):
            # Encode as base64 for APIs that support it; also provide metadata
            with open(path, "rb") as f:
                result["base64"] = base64.b64encode(f.read()).decode("utf-8")
            mime = mimetypes.guess_type(path)[0] or f"{category}/mp4"
            result["mime"] = mime
            result["description"] = f"[{category.upper()} file: {name}, {size:,} bytes]"

        else:
            result["description"] = f"[Binary file: {name}, {size:,} bytes]"

        return result

    def attach_file(self):
        """Open a file dialog to attach one or more files."""
        paths = filedialog.askopenfilenames(
            title="Attach Files",
            filetypes=[
                ("All files", "*.*"),
                ("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                ("Audio", "*.mp3 *.wav *.ogg *.flac *.aac *.m4a"),
                ("Video", "*.mp4 *.avi *.mkv *.mov *.webm"),
                ("Text", "*.txt *.md *.csv *.json *.py *.js *.ts *.html"),
            ],
        )
        for p in paths:
            self._add_attachment(p)

    def _add_attachment(self, path):
        """Process and add a file to the attachment list."""
        path = path.strip().strip('"').strip("'")
        if not os.path.isfile(path):
            self.append_output(f"[Attach] File not found: {path}\n")
            return
        processed = self._process_file(path)
        self.attached_files.append(processed)
        cat = processed["category"]
        name = processed["name"]
        size_kb = processed["size"] / 1024
        self.append_output(f"[Attach] {cat.upper()}: {name} ({size_kb:.1f} KB)\n")
        self._update_attach_label()

    def clear_attachments(self):
        """Remove all attached files."""
        self.attached_files.clear()
        self.append_output("[Attach] All files cleared.\n")
        self._update_attach_label()

    def _update_attach_label(self):
        count = len(self.attached_files)
        if count == 0:
            self.attach_label.config(text="")
        else:
            names = ", ".join(f["name"] for f in self.attached_files[:3])
            extra = f" +{count - 3} more" if count > 3 else ""
            self.attach_label.config(text=f"Attached: {names}{extra}")

    def _on_drop(self, event):
        """Handle drag-and-drop files."""
        # tkinterdnd2 gives paths as a string, possibly with {} around spaced names
        raw = event.data
        paths = []
        i = 0
        while i < len(raw):
            if raw[i] == "{":
                end = raw.index("}", i)
                paths.append(raw[i + 1:end])
                i = end + 2
            elif raw[i] == " ":
                i += 1
            else:
                end = raw.find(" ", i)
                if end == -1:
                    end = len(raw)
                paths.append(raw[i:end])
                i = end + 1
        for p in paths:
            self._add_attachment(p)

    # --- Ask AI ---
    def ask_ai(self):
        """Send the input text + attached files to the configured LLM API."""
        prompt = self.command_input.get().strip()
        if not prompt and not self.attached_files:
            return

        # Local models (Ollama, LM Studio) don't need an API key
        needs_key = self.llm_config.get("auth_header", "") != ""
        if needs_key and not self.llm_config.get("api_key"):
            self.append_output("[Error] No API key set. Click 'API Settings' first.\n\n")
            return

        self.command_input.delete(0, tk.END)
        file_names = [f["name"] for f in self.attached_files]
        if file_names:
            self.append_output(f"[You -> AI] {prompt or '(see attached files)'}\n")
            self.append_output(f"  Files: {', '.join(file_names)}\n")
        else:
            self.append_output(f"[You -> AI] {prompt}\n")

        # Grab current attachments and clear them
        files = self.attached_files[:]
        self.attached_files.clear()
        self._update_attach_label()

        thread = threading.Thread(
            target=self._call_llm, args=(prompt, files), daemon=True
        )
        thread.start()

    def _build_user_content(self, prompt, files):
        """Build the user message content, mixing text and file data."""
        # If no files, just return text
        if not files:
            return prompt

        # Multimodal content array (OpenAI vision / Anthropic format)
        parts = []

        # Add text prompt first
        if prompt:
            parts.append({"type": "text", "text": prompt})

        for f in files:
            cat = f["category"]

            if cat == "text":
                text_block = f"--- File: {f['name']} ---\n{f.get('content', '')}\n--- End ---"
                parts.append({"type": "text", "text": text_block})

            elif cat == "image" and "base64" in f:
                parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{f['mime']};base64,{f['base64']}"
                    },
                })

            elif cat in ("audio", "video") and "base64" in f:
                # Many APIs don't support raw audio/video yet.
                # Send as base64 data URL + a text description.
                parts.append({
                    "type": "text",
                    "text": f.get("description", f"[{cat} file: {f['name']}]"),
                })
                parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{f['mime']};base64,{f['base64']}"
                    },
                })

            else:
                parts.append({
                    "type": "text",
                    "text": f.get("description", f"[Attached: {f['name']}]"),
                })

        return parts

    def _build_payload(self, prompt, files=None):
        """Build the request payload based on the provider."""
        provider = self.llm_config.get("provider", "")
        system_prompt = self.llm_config.get("system_prompt", "You are a helpful assistant.")
        model = self.llm_config["model"]
        user_content = self._build_user_content(prompt, files or [])

        if "anthropic" in provider.lower() or "anthropic" in self.llm_config["api_url"]:
            # Convert to Anthropic content format
            if isinstance(user_content, list):
                anthropic_parts = []
                for part in user_content:
                    if part["type"] == "text":
                        anthropic_parts.append({"type": "text", "text": part["text"]})
                    elif part["type"] == "image_url":
                        url = part["image_url"]["url"]
                        if url.startswith("data:"):
                            mime, b64 = url.split(";base64,", 1)
                            mime = mime.replace("data:", "")
                            anthropic_parts.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime,
                                    "data": b64,
                                },
                            })
                user_content = anthropic_parts
            return {
                "model": model,
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_content}],
            }
        else:
            # OpenAI-compatible format
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_content})
            return {"model": model, "messages": messages}

    def _build_headers(self):
        """Build request headers based on auth config."""
        headers = {"Content-Type": "application/json"}
        auth = self.llm_config.get("auth_header", "").strip()
        key = self.llm_config.get("api_key", "").strip()

        if auth and key:
            if auth.lower() == "x-api-key":
                # Anthropic style
                headers["x-api-key"] = key
                headers["anthropic-version"] = "2023-06-01"
            else:
                # Bearer style (OpenAI, LM Studio, etc.)
                headers["Authorization"] = f"{auth} {key}"
        return headers

    def _extract_response(self, data):
        """Walk the response JSON using the configured response_path."""
        path = self.llm_config.get("response_path", "choices.0.message.content")
        obj = data
        for part in path.split("."):
            if isinstance(obj, list):
                obj = obj[int(part)]
            elif isinstance(obj, dict):
                obj = obj[part]
            else:
                return str(obj)
        return str(obj)

    def _call_llm(self, prompt, files=None):
        """Call the LLM API and display the response."""
        try:
            payload = json.dumps(self._build_payload(prompt, files)).encode("utf-8")
            headers = self._build_headers()

            req = urllib.request.Request(
                self.llm_config["api_url"],
                data=payload,
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            reply = self._extract_response(data)
            self.root.after(0, self.append_output, f"[AI] {reply}\n\n")

        except Exception as e:
            self.root.after(0, self.append_output, f"[AI Error] {e}\n\n")

    # --- Export / Import ---
    def export_log(self):
        """Export the terminal output to a text file."""
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Export Terminal Log",
        )
        if path:
            content = self.text_output.get("1.0", tk.END)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.append_output(f"[Export] Saved to {path}\n\n")

    def import_log(self):
        """Import a text file into the terminal output."""
        path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Import File",
        )
        if path:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.append_output(f"[Import] --- {os.path.basename(path)} ---\n")
            self.append_output(content)
            self.append_output(f"\n[Import] --- end ---\n\n")

    def append_output(self, text):
        if not self.output_visible:
            # Buffer the text so it appears when output is toggled back on
            if not hasattr(self, '_saved_output'):
                self._saved_output = ""
            self._saved_output += text
            return
        self.text_output.config(state=tk.NORMAL)
        self.text_output.insert(tk.END, text)
        self.text_output.see(tk.END)
        self.text_output.config(state=tk.DISABLED)

    # --- Autocorrect engine ---

    # Common command typos: wrong -> right
    TYPO_MAP = {
        "dri": "dir", "dier": "dir", "di": "dir",
        "lls": "ls", "sl": "ls", "l": "ls",
        "csl": "cls", "clr": "cls", "claer": "clear", "cler": "clear",
        "pyhton": "python", "pytohn": "python", "pyton": "python", "pythn": "python",
        "pthon": "python", "pytho": "python",
        "pipp": "pip", "ppi": "pip", "piip": "pip",
        "gti": "git", "igt": "git", "gt": "git",
        "mkdr": "mkdir", "mkidr": "mkdir", "mdir": "mkdir",
        "rmdr": "rmdir", "remdir": "rmdir",
        "cdd": "cd", "dc": "cd",
        "caT": "cat", "cta": "cat",
        "ehco": "echo", "ecoh": "echo", "eho": "echo",
        "grpe": "grep", "gerp": "grep", "gre": "grep",
        "curl": "curl", "crul": "curl",
        "nmp": "npm", "nop": "npm", "nmpm": "npm",
        "ndoe": "node", "noed": "node",
        "dcoker": "docker", "dokcer": "docker",
        "sssh": "ssh", "shh": "ssh",
        "tpuch": "touch", "touhc": "touch", "tuoch": "touch",
        "mvoe": "move", "moev": "move",
        "cpoy": "copy", "coyp": "copy",
        "rnename": "rename", "renam": "rename",
        "powerhsell": "powershell", "powesrhell": "powershell",
    }

    # Common flag/argument typos
    FLAG_TYPO_MAP = {
        "--hlep": "--help", "-hlep": "--help", "--hepl": "--help",
        "--vesrion": "--version", "--verison": "--version", "--vresion": "--version",
        "--vervose": "--verbose", "--vebrose": "--verbose",
        "-rf": "-rf", "-r": "-r",
        "isntall": "install", "insatll": "install", "intsall": "install",
        "unisntall": "uninstall", "uninsatll": "uninstall",
        "staus": "status", "stauts": "status", "statsu": "status",
        "comit": "commit", "commti": "commit", "commt": "commit",
        "pus": "push", "psuh": "push",
        "pul": "pull", "plul": "pull",
        "chekout": "checkout", "checkou": "checkout",
        "brnach": "branch", "brach": "branch",
        "merg": "merge", "megre": "merge",
        "reb ase": "rebase",
        "strat": "start", "statr": "start",
        "sotp": "stop", "stpo": "stop",
        "restrat": "restart", "restat": "restart",
    }

    def toggle_autocorrect(self):
        self.autocorrect_enabled = not self.autocorrect_enabled
        if self.autocorrect_enabled:
            self.autocorrect_toggle.config(text="AutoCorrect: ON", bg="#001a33")
            self.append_output("[AutoCorrect] Enabled\n")
        else:
            self.autocorrect_toggle.config(text="AutoCorrect: OFF", bg="#001122")
            self.append_output("[AutoCorrect] Disabled\n")

    def _get_known_commands(self):
        """Build a list of known commands from PATH."""
        known = set()
        # Common built-in commands (PowerShell / cmd)
        builtins = [
            "dir", "cd", "cls", "copy", "move", "del", "mkdir", "rmdir",
            "echo", "type", "set", "path", "rename", "start", "exit",
            "ls", "cat", "clear", "pwd", "rm", "cp", "mv", "touch",
            "python", "pip", "git", "node", "npm", "docker", "curl",
            "ssh", "scp", "grep", "find", "where", "whoami", "ping",
            "ipconfig", "netstat", "tasklist", "taskkill",
        ]
        known.update(builtins)

        # Scan PATH for executables
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        for d in path_dirs:
            try:
                for f in os.listdir(d):
                    name = os.path.splitext(f)[0].lower()
                    known.add(name)
            except (OSError, PermissionError):
                pass
        return known

    def _autocorrect_command(self, command):
        """Try to fix a mistyped command. Returns (corrected, changes_list)."""
        if not self.autocorrect_enabled:
            return command, []

        parts = command.split()
        if not parts:
            return command, []

        changes = []
        original_cmd = parts[0].lower()

        # 1. Direct typo map lookup for the command name
        if original_cmd in self.TYPO_MAP:
            fixed = self.TYPO_MAP[original_cmd]
            changes.append(f"'{parts[0]}' -> '{fixed}'")
            parts[0] = fixed

        # 2. Fuzzy match against known commands
        elif not shutil.which(parts[0]):
            known = self._get_known_commands()
            matches = difflib.get_close_matches(original_cmd, known, n=1, cutoff=0.6)
            if matches:
                fixed = matches[0]
                changes.append(f"'{parts[0]}' -> '{fixed}'")
                parts[0] = fixed

        # 3. Fix arguments/subcommands
        for i in range(1, len(parts)):
            token = parts[i]
            lower = token.lower()
            if lower in self.FLAG_TYPO_MAP:
                fixed = self.FLAG_TYPO_MAP[lower]
                changes.append(f"'{token}' -> '{fixed}'")
                parts[i] = fixed

        # 4. Fix common pattern issues
        corrected = " ".join(parts)

        # Fix doubled spaces
        corrected = re.sub(r"  +", " ", corrected)

        # Fix missing space after common commands
        for cmd in ["cd", "dir", "ls", "cat", "echo", "mkdir", "git", "pip", "python", "npm", "node"]:
            pattern = rf"^({cmd})([^\s\-/\\])"  # e.g. "cdDesktop" -> "cd Desktop"
            match = re.match(pattern, corrected, re.IGNORECASE)
            if match:
                corrected = f"{match.group(1)} {match.group(2)}" + corrected[match.end():]
                changes.append(f"added space after '{cmd}'")
                break

        return corrected, changes

    # --- SubZero Panel Toggle ---
    def toggle_subzero_panel(self):
        """Toggle the SubZero chat panel in/out with draggable splitter."""
        if self.subzero_panel_visible:
            # Remember the sash position so we can restore it
            try:
                self._sz_sash_pos = self.paned.sash_coord(0)[0]
            except Exception:
                pass
            self.paned.forget(self.sz_panel)
            self.subzero_panel_visible = False
            self.subzero_button.config(bg="#081428", fg="#4499dd", relief=tk.FLAT)
        else:
            # Add the SubZero panel to the right side of the pane
            self.paned.add(self.sz_panel, stretch="always", minsize=200)
            self.subzero_panel_visible = True
            self.subzero_button.config(bg="#4499dd", fg="#000000", relief=tk.FLAT)
            # Set the divider to ~60% terminal / ~40% SubZero
            sash_pos = getattr(self, '_sz_sash_pos', None)
            if sash_pos is None:
                sash_pos = int(self.root.winfo_width() * 0.6)
            self.root.after(50, lambda: self._set_sash(sash_pos))
            self.sz_input.focus_set()

    def _set_sash(self, x):
        """Set the sash position safely after the widget is rendered."""
        try:
            self.paned.sash_place(0, x, 0)
        except Exception:
            pass

    def _sz_append(self, text):
        """Append text to the SubZero panel output."""
        if not self.sz_chat_visible:
            if not hasattr(self, '_saved_sz_output'):
                self._saved_sz_output = ""
            self._saved_sz_output += text
            return
        self.sz_output.config(state=tk.NORMAL)
        self.sz_output.insert(tk.END, text)
        self.sz_output.see(tk.END)
        self.sz_output.config(state=tk.DISABLED)

    def sz_send_message(self):
        """Send a message from the SubZero panel input."""
        prompt = self.sz_input.get().strip()
        if not prompt:
            return
        self.sz_input.delete(0, tk.END)
        self._sz_append(f"You: {prompt}\n")

        # Also include attached files if any
        file_context = ""
        if self.attached_files:
            file_names = [f["name"] for f in self.attached_files]
            self._sz_append(f"  Files: {', '.join(file_names)}\n")
            for f in self.attached_files:
                if f["category"] == "text" and "content" in f:
                    file_context += f"\n--- File: {f['name']} ---\n{f['content']}\n--- End ---\n"
                else:
                    file_context += f"\n[Attached {f['category']} file: {f['name']}, {f['size']:,} bytes]\n"
            self.attached_files.clear()
            self._update_attach_label()

        full_prompt = prompt
        if file_context:
            full_prompt = f"{prompt}\n\nAttached files:{file_context}"

        thread = threading.Thread(
            target=self._sz_call, args=(full_prompt,), daemon=True
        )
        thread.start()

    def _sz_call(self, prompt):
        """Call SubZero via the CommBridge — handles queueing if offline."""
        # If bridge says we're disconnected, route through the bridge queue
        if self.bridge.status == CommBridge.DISCONNECTED:
            self.root.after(0, self._sz_append, "SubZero: [Offline — message queued]\n")
            self.bridge.send_message(prompt)
            return

        self.root.after(0, self._sz_append, "SubZero: Thinking...\n")
        self.root.after(0, lambda: self.subzero_button.config(state=tk.DISABLED, text="..."))
        try:
            response = self.subzero.chat(prompt)
            # Remove the "Thinking..." line and show real response
            def show_response():
                self.sz_output.config(state=tk.NORMAL)
                # Delete the last "Thinking..." line
                content = self.sz_output.get("1.0", tk.END)
                if "SubZero: Thinking...\n" in content:
                    idx = self.sz_output.search("SubZero: Thinking...", "1.0", tk.END)
                    if idx:
                        line_end = f"{idx} lineend + 1 char"
                        self.sz_output.delete(idx, line_end)
                self.sz_output.insert(tk.END, f"SubZero: {response}\n\n")
                self.sz_output.see(tk.END)
                self.sz_output.config(state=tk.DISABLED)
            self.root.after(0, show_response)

            # If the response contains an error from the agent, the bridge tracks it
            if self.subzero.last_error:
                self.bridge.total_messages_failed += 1
            else:
                self.bridge.total_messages_sent += 1

        except Exception as e:
            self.root.after(0, self._sz_append, f"[Error] {e}\n\n")
            self.bridge.total_messages_failed += 1
        finally:
            self.root.after(0, lambda: self.subzero_button.config(state=tk.NORMAL, text="SubZero"))

    def sz_clear_chat(self):
        """Clear the SubZero panel chat and memory."""
        self.sz_output.config(state=tk.NORMAL)
        self.sz_output.delete("1.0", tk.END)
        self.sz_output.config(state=tk.DISABLED)
        self.subzero.conversation.clear()
        self.subzero.save_memory()
        self._sz_append("Chat and memory cleared.\n\n")

    def sz_toggle_text(self):
        """Toggle SubZero chat text visibility — click to hide, click again to restore."""
        if self.sz_chat_visible:
            # Save and clear
            self._saved_sz_output = self.sz_output.get("1.0", tk.END)
            self.sz_output.config(state=tk.NORMAL)
            self.sz_output.delete("1.0", tk.END)
            self.sz_output.config(state=tk.DISABLED)
            self.sz_chat_visible = False
            self.sz_status_btn.config(text="Status: OFF", bg="#2e0a1a")
        else:
            # Restore
            self.sz_output.config(state=tk.NORMAL)
            self.sz_output.delete("1.0", tk.END)
            if hasattr(self, '_saved_sz_output'):
                self.sz_output.insert("1.0", self._saved_sz_output.rstrip("\n"))
            self.sz_output.see(tk.END)
            self.sz_output.config(state=tk.DISABLED)
            self.sz_chat_visible = True
            self.sz_status_btn.config(text="Status", bg="#081428")

    def sz_show_status(self):
        """Show SubZero + CommBridge status in the panel."""
        info = self.bridge.get_status_info()
        status_color = {
            CommBridge.CONNECTED: "CONNECTED",
            CommBridge.DISCONNECTED: "DISCONNECTED",
            CommBridge.RECONNECTING: "RECONNECTING",
            CommBridge.CHECKING: "CHECKING",
        }
        self._sz_append(
            f"--- SubZero Status ---\n"
            f"Model: {self.subzero.model}\n"
            f"Bridge: {status_color.get(info['status'], info['status'])}\n"
            f"Last check: {info['last_check']}\n"
            f"Heartbeat: every {info['heartbeat_interval']}\n"
            f"Messages sent: {info['total_sent']}\n"
            f"Messages failed: {info['total_failed']}\n"
            f"Queued: {info['queued_messages']}\n"
            f"Memory: {len(self.subzero.conversation)} messages\n"
            f"--- End Status ---\n\n"
        )
        self.sz_model_label.config(text=f"({self.subzero.model})")

    def _offer_ai_fix(self, command, error_output):
        """When a command fails, offer to send it to the AI for a fix."""
        self.last_failed_command = command
        self.last_error_output = error_output
        self.append_output(
            f"[AutoCorrect] Command failed. Type 'fix' or click Ask AI/SubZero for help.\n"
        )

    def run_command(self):
        command = self.command_input.get().strip()
        if not command:
            return

        self.command_input.delete(0, tk.END)

        # Special: "fix" sends the last failed command to AI
        if command.lower() == "fix" and self.last_failed_command:
            self.append_output(f"> fix\n")
            self._fix_with_ai()
            return

        # Bridge commands
        lower = command.lower().strip()
        if lower == "bridge status":
            self.append_output(f"> bridge status\n")
            info = self.bridge.get_status_info()
            self.append_output(
                f"--- CommBridge Status ---\n"
                f"  Connection:  {info['status'].upper()}\n"
                f"  Last check:  {info['last_check']}\n"
                f"  Heartbeat:   every {info['heartbeat_interval']}\n"
                f"  Failures:    {info['consecutive_failures']} consecutive\n"
                f"  Queued:      {info['queued_messages']} message(s)\n"
                f"  Sent total:  {info['total_sent']}\n"
                f"  Failed total:{info['total_failed']}\n"
                f"  Model:       {info['model']}\n"
                f"--- End ---\n\n"
            )
            return
        if lower == "bridge queue":
            self.append_output(f"> bridge queue\n")
            qsize = len(self.bridge.message_queue)
            if qsize == 0:
                self.append_output("[Bridge] No messages in queue.\n\n")
            else:
                self.append_output(f"[Bridge] {qsize} message(s) queued:\n")
                for i, msg in enumerate(self.bridge.message_queue, 1):
                    short = msg['prompt'][:60] + ('...' if len(msg['prompt']) > 60 else '')
                    self.append_output(f"  {i}. {short}\n")
                self.append_output("\n")
            return
        if lower == "bridge retry":
            self.append_output(f"> bridge retry\n")
            delivered = self.bridge.retry_queue()
            if delivered > 0:
                self.append_output(f"[Bridge] Delivered {delivered} queued message(s).\n\n")
            else:
                self.append_output("[Bridge] No messages delivered (queue empty or still offline).\n\n")
            return

        # SubZero commands from the main terminal input (type "sz hello" or "subzero hello")
        lower = command.lower()
        if lower.startswith("sz ") or lower.startswith("subzero "):
            prompt = command.split(" ", 1)[1] if " " in command else ""
            if not prompt:
                return
            self.append_output(f"> {command}\n")
            # Open the panel if not visible
            if not self.subzero_panel_visible:
                self.toggle_subzero_panel()
            self._sz_append(f"You: {prompt}\n")
            thread = threading.Thread(
                target=self._sz_call, args=(prompt,), daemon=True
            )
            thread.start()
            return

        # Run autocorrect
        corrected, changes = self._autocorrect_command(command)
        if changes:
            self.append_output(f"> {command}\n")
            self.append_output(f"[AutoCorrect] {', '.join(changes)}\n")
            self.append_output(f"[AutoCorrect] Running: {corrected}\n")
        else:
            self.append_output(f"> {corrected}\n")

        thread = threading.Thread(target=self._execute, args=(corrected,), daemon=True)
        thread.start()

    def _fix_with_ai(self):
        """Send the failed command + error to the AI for a corrected command."""
        prompt = (
            f"The following command failed:\n"
            f"  {self.last_failed_command}\n\n"
            f"Error output:\n{self.last_error_output}\n\n"
            f"Please give me the corrected command. "
            f"Reply with ONLY the corrected command, no explanation."
        )
        self.append_output(f"[AutoCorrect] Asking AI to fix: {self.last_failed_command}\n")
        self.last_failed_command = None

        thread = threading.Thread(
            target=self._call_llm_for_fix, args=(prompt,), daemon=True
        )
        thread.start()

    def _call_llm_for_fix(self, prompt):
        """Call LLM specifically for command correction."""
        try:
            payload = json.dumps(self._build_payload(prompt)).encode("utf-8")
            headers = self._build_headers()

            req = urllib.request.Request(
                self.llm_config["api_url"],
                data=payload,
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            reply = self._extract_response(data).strip()
            # Strip markdown code fences if the AI wraps the answer
            reply = re.sub(r"^```\w*\n?", "", reply)
            reply = re.sub(r"\n?```$", "", reply)
            reply = reply.strip()

            self.root.after(0, self.append_output, f"[AI Fix] Suggested: {reply}\n")
            # Put the suggested command in the input field so user can review/run it
            self.root.after(0, lambda: self.command_input.insert(0, reply))

        except Exception as e:
            self.root.after(0, self.append_output, f"[AI Fix Error] {e}\n\n")

    def _execute(self, command):
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=30, encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.stdout:
                self.root.after(0, self.append_output, result.stdout)
            if result.stderr:
                self.root.after(0, self.append_output, f"[stderr] {result.stderr}")
            self.root.after(0, self.append_output, "\n")

            # If command failed and autocorrect is on, offer AI fix
            if result.returncode != 0 and self.autocorrect_enabled:
                error_text = result.stderr or result.stdout or "(no output)"
                self.root.after(0, self._offer_ai_fix, command, error_text)

        except subprocess.TimeoutExpired:
            self.root.after(0, self.append_output, "[Error] Command timed out.\n\n")
        except Exception as e:
            self.root.after(
                0, lambda: messagebox.showerror("Error", str(e))
            )


# ============================================================
# SubZero Agent — local Ollama LLM with conversation memory
# ============================================================

class SubZeroAgent:
    """SubZero LLM agent using Ollama locally."""

    def __init__(self):
        self.model = "qwen2.5:3b"
        self.home_dir = Path.home() / ".subzero"
        self.memory_file = self.home_dir / "memory_terminal.json"
        self.skills_dir = self.home_dir / "skills"
        self.conversation = []
        self.last_error = None
        self.tool_runtime = ToolRuntime()
        self._init_dirs()
        self._load_memory()

    def _init_dirs(self):
        self.home_dir.mkdir(exist_ok=True)
        self.skills_dir.mkdir(exist_ok=True)

    def _load_memory(self):
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r") as f:
                    self.conversation = json.load(f)
            except Exception:
                self.conversation = []

    def save_memory(self):
        with open(self.memory_file, "w") as f:
            json.dump(self.conversation[-50:], f, indent=2, default=str)

    def is_ollama_running(self):
        """Quick check if Ollama server is reachable (2 second timeout)."""
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            return False

    def chat(self, user_input):
        """Send a message to Ollama and get a response."""
        # Quick connectivity check first
        if not self.is_ollama_running():
            self.last_error = "not_running"
            return (
                "Ollama is not running. To fix this:\n"
                "  1. Make sure Ollama is installed (https://ollama.com)\n"
                "  2. Start it: open a terminal and run 'ollama serve'\n"
                f"  3. Pull the model: 'ollama pull {self.model}'\n"
                "  4. Try again."
            )

        # Add user message
        self.conversation.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat(),
        })

        # Build context from recent messages
        context = "\n".join(
            f"{'User' if m['role'] == 'user' else 'SubZero'}: {m['content']}"
            for m in self.conversation[-10:]
        )
        tool_prompt = self.tool_runtime.get_system_prompt()
        full_prompt = f"{tool_prompt}\n\n{context}\nSubZero:"

        # Try Ollama REST API first
        response, error = self._call_ollama_api(full_prompt)

        # If API failed, try CLI as fallback
        if response is None:
            response, error = self._call_ollama_cli(full_prompt)

        # If still no response, return the error
        if response is None:
            self.last_error = error
            return f"Could not get a response: {error}"

        self.last_error = None

        # Execute any tool calls in the response
        tool_calls = self.tool_runtime.parse(response)
        if tool_calls:
            results = self.tool_runtime.execute_all(tool_calls)
            tool_output = self.tool_runtime.format_results(results)
            response = response + "\n" + tool_output

        # Save response
        self.conversation.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat(),
        })
        self.save_memory()
        return response

    def _call_ollama_api(self, prompt):
        """Try calling Ollama via streaming REST API. Returns (response, error)."""
        try:
            payload = json.dumps({
                "model": self.model,
                "prompt": prompt,
                "stream": True,
            }).encode("utf-8")
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            full = []
            with urllib.request.urlopen(req, timeout=300) as resp:
                for line in resp:
                    chunk = json.loads(line.decode("utf-8"))
                    token = chunk.get("response", "")
                    if token:
                        full.append(token)
                    if chunk.get("done"):
                        break
            text = "".join(full).strip()
            if text:
                return text, None
            return None, "Empty response from Ollama API"
        except urllib.error.URLError as e:
            return None, f"Cannot connect to Ollama API: {e.reason}"
        except TimeoutError:
            return None, "Ollama API timed out"
        except Exception as e:
            return None, f"Ollama API error: {e}"

    def _call_ollama_cli(self, prompt):
        """Fall back to calling Ollama via CLI. Returns (response, error)."""
        try:
            result = subprocess.run(
                ["ollama", "run", self.model, prompt],
                capture_output=True, text=True, timeout=60,
                encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip(), None
            err = result.stderr.strip() or "No output from ollama CLI"
            return None, f"Ollama CLI: {err}"
        except FileNotFoundError:
            return None, ("Ollama not found. Install from https://ollama.com "
                          f"then run: ollama pull {self.model}")
        except subprocess.TimeoutExpired:
            return None, "Ollama CLI timed out (60s)"
        except Exception as e:
            return None, f"Ollama CLI error: {e}"


if __name__ == "__main__":
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = CustomTerminal(root)
    root.mainloop()
