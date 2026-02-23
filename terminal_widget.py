"""
Terminal Manager Widget (TM Widget)
- System tray icon with popup dashboard
- Tabs: Terminal, Tasks, Files, Notifications
- Task management with to-do list, due dates, priorities
- File explorer and text viewer
- Quick command execution
- Notification panel with real-time alerts
- JSON persistence for tasks and settings
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import json
import os
import time
from datetime import datetime, timedelta

# --- Config paths ---
WIDGET_DIR = os.path.dirname(os.path.abspath(__file__))
TASKS_FILE = os.path.join(WIDGET_DIR, "tm_tasks.json")
NOTIFICATIONS_FILE = os.path.join(WIDGET_DIR, "tm_notifications.json")
SETTINGS_FILE = os.path.join(WIDGET_DIR, "tm_settings.json")


# ============================================================
# Data layer — tasks, notifications, settings
# ============================================================

def load_json(path, default=None):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default if default is not None else []


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


# ============================================================
# Main Widget Application
# ============================================================

class TMWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Terminal Manager")
        self.root.geometry("700x520")
        self.root.configure(bg="#000000")
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        # Data
        self.tasks = load_json(TASKS_FILE, [])
        self.notifications = load_json(NOTIFICATIONS_FILE, [])
        self.settings = load_json(SETTINGS_FILE, {
            "watch_folder": "",
            "auto_notify": True,
        })
        self.watched_files = set()

        # System tray state
        self.is_hidden = False

        # --- Menu bar ---
        menubar = tk.Menu(self.root, bg="#041228", fg="white")
        view_menu = tk.Menu(menubar, tearoff=0, bg="#041228", fg="white")
        view_menu.add_command(label="Minimize to Tray", command=self.minimize_to_tray)
        view_menu.add_command(label="Open Custom Terminal", command=self.open_custom_terminal)
        view_menu.add_separator()
        view_menu.add_command(label="Exit", command=self.quit_app)
        menubar.add_cascade(label="Menu", menu=view_menu)
        self.root.config(menu=menubar)

        # --- Notebook (tabs) ---
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background="#000000", borderwidth=0)
        style.configure("TNotebook.Tab", background="#0a1e3a", foreground="white",
                        padding=[12, 6], font=("Consolas", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", "#0066cc")],
                  foreground=[("selected", "white")])

        # --- Status bar (created early so tabs can use set_status) ---
        self.status_bar = tk.Label(
            self.root, text="TM Widget Ready", bg="#0066cc", fg="white",
            font=("Consolas", 9), anchor="w", padx=10
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create tabs
        self.create_terminal_tab()
        self.create_tasks_tab()
        self.create_files_tab()
        self.create_notifications_tab()

        # Start background watchers
        self._start_watchers()

        # Refresh UI
        self.refresh_tasks_list()
        self.refresh_notifications_list()

    # --------------------------------------------------------
    # TAB 1: Terminal
    # --------------------------------------------------------
    def create_terminal_tab(self):
        frame = tk.Frame(self.notebook, bg="#000000")
        self.notebook.add(frame, text=" Terminal ")

        # Quick command buttons
        btn_frame = tk.Frame(frame, bg="#000000")
        btn_frame.pack(fill=tk.X, padx=5, pady=(5, 0))

        quick_commands = [
            ("System Info", "systeminfo"),
            ("IP Config", "ipconfig"),
            ("Task List", "tasklist"),
            ("Disk Space", "wmic logicaldisk get size,freespace,caption"),
            ("Processes", "tasklist /FO TABLE"),
            ("Network", "netstat -an"),
        ]
        for i, (label, cmd) in enumerate(quick_commands):
            tk.Button(
                btn_frame, text=label,
                command=lambda c=cmd: self.quick_run(c),
                bg="#0a1e3a", fg="white", font=("Consolas", 9),
                relief=tk.RAISED, padx=6,
            ).grid(row=0, column=i, padx=2, pady=2)

        # Command input
        input_frame = tk.Frame(frame, bg="#000000")
        input_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(input_frame, text=">", bg="#000000", fg="lime",
                 font=("Consolas", 12, "bold")).pack(side=tk.LEFT)
        self.term_input = tk.Entry(
            input_frame, bg="#041228", fg="white",
            font=("Consolas", 11), insertbackground="white",
            relief=tk.FLAT, borderwidth=4,
        )
        self.term_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.term_input.bind("<Return>", lambda e: self.quick_run(self.term_input.get()))

        tk.Button(
            input_frame, text="Run", command=lambda: self.quick_run(self.term_input.get()),
            bg="#0066cc", fg="white", font=("Consolas", 10, "bold"),
            relief=tk.RAISED, padx=10,
        ).pack(side=tk.RIGHT)

        # Output area
        self.term_output = tk.Text(
            frame, bg="black", fg="white", font=("Consolas", 10),
            wrap=tk.WORD, relief=tk.SUNKEN, borderwidth=2,
            selectbackground="#0a2e5a", state=tk.DISABLED,
        )
        self.term_output.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

    def quick_run(self, command):
        command = command.strip()
        if not command:
            return
        self.term_input.delete(0, tk.END)
        self._term_append(f"> {command}\n")
        self.set_status(f"Running: {command}")

        def run():
            try:
                result = subprocess.run(
                    command, shell=True, capture_output=True, text=True, timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if result.stdout:
                    self.root.after(0, self._term_append, result.stdout)
                if result.stderr:
                    self.root.after(0, self._term_append, f"[stderr] {result.stderr}")
                self.root.after(0, self._term_append, "\n")
                self.root.after(0, self.set_status, "Command complete")
            except subprocess.TimeoutExpired:
                self.root.after(0, self._term_append, "[Error] Timed out.\n\n")
            except Exception as e:
                self.root.after(0, self._term_append, f"[Error] {e}\n\n")

        threading.Thread(target=run, daemon=True).start()

    def _term_append(self, text):
        self.term_output.config(state=tk.NORMAL)
        self.term_output.insert(tk.END, text)
        self.term_output.see(tk.END)
        self.term_output.config(state=tk.DISABLED)

    # --------------------------------------------------------
    # TAB 2: Tasks
    # --------------------------------------------------------
    def create_tasks_tab(self):
        frame = tk.Frame(self.notebook, bg="#000000")
        self.notebook.add(frame, text=" Tasks ")

        # Add task area
        add_frame = tk.Frame(frame, bg="#000000")
        add_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(add_frame, text="Task:", bg="#000000", fg="white",
                 font=("Consolas", 10)).grid(row=0, column=0, padx=4)
        self.task_name_entry = tk.Entry(
            add_frame, bg="#041228", fg="white", font=("Consolas", 10),
            insertbackground="white", width=30,
        )
        self.task_name_entry.grid(row=0, column=1, padx=4)

        tk.Label(add_frame, text="Due:", bg="#000000", fg="white",
                 font=("Consolas", 10)).grid(row=0, column=2, padx=4)
        self.task_due_entry = tk.Entry(
            add_frame, bg="#041228", fg="white", font=("Consolas", 10),
            insertbackground="white", width=12,
        )
        self.task_due_entry.grid(row=0, column=3, padx=4)
        self.task_due_entry.insert(0, "YYYY-MM-DD")

        tk.Label(add_frame, text="Priority:", bg="#000000", fg="white",
                 font=("Consolas", 10)).grid(row=0, column=4, padx=4)
        self.task_priority_var = tk.StringVar(value="Medium")
        tk.OptionMenu(
            add_frame, self.task_priority_var, "High", "Medium", "Low"
        ).grid(row=0, column=5, padx=4)

        tk.Button(
            add_frame, text="Add Task", command=self.add_task,
            bg="#0066cc", fg="white", font=("Consolas", 10, "bold"),
        ).grid(row=0, column=6, padx=8)

        # Task list
        list_frame = tk.Frame(frame, bg="#000000")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        columns = ("status", "task", "due", "priority", "created")
        self.task_tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", height=12,
        )
        self.task_tree.heading("status", text="Status")
        self.task_tree.heading("task", text="Task")
        self.task_tree.heading("due", text="Due Date")
        self.task_tree.heading("priority", text="Priority")
        self.task_tree.heading("created", text="Created")

        self.task_tree.column("status", width=70, anchor="center")
        self.task_tree.column("task", width=250)
        self.task_tree.column("due", width=100, anchor="center")
        self.task_tree.column("priority", width=80, anchor="center")
        self.task_tree.column("created", width=100, anchor="center")

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=scrollbar.set)
        self.task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Task action buttons
        action_frame = tk.Frame(frame, bg="#000000")
        action_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        for text, cmd in [
            ("Complete", self.complete_task),
            ("Delete", self.delete_task),
            ("Export Tasks", self.export_tasks),
            ("Import Tasks", self.import_tasks),
        ]:
            tk.Button(
                action_frame, text=text, command=cmd,
                bg="#0a1e3a", fg="white", font=("Consolas", 9),
            ).pack(side=tk.LEFT, padx=2)

    def add_task(self):
        name = self.task_name_entry.get().strip()
        if not name:
            return
        due = self.task_due_entry.get().strip()
        if due == "YYYY-MM-DD":
            due = ""
        task = {
            "id": int(time.time() * 1000),
            "name": name,
            "due": due,
            "priority": self.task_priority_var.get(),
            "status": "Pending",
            "created": datetime.now().strftime("%Y-%m-%d"),
        }
        self.tasks.append(task)
        save_json(TASKS_FILE, self.tasks)
        self.task_name_entry.delete(0, tk.END)
        self.refresh_tasks_list()
        self.add_notification(f"New task added: {name}")
        self.set_status(f"Task added: {name}")

    def complete_task(self):
        selected = self.task_tree.selection()
        if not selected:
            return
        idx = self.task_tree.index(selected[0])
        self.tasks[idx]["status"] = "Done"
        save_json(TASKS_FILE, self.tasks)
        self.refresh_tasks_list()
        self.add_notification(f"Task completed: {self.tasks[idx]['name']}")

    def delete_task(self):
        selected = self.task_tree.selection()
        if not selected:
            return
        idx = self.task_tree.index(selected[0])
        removed = self.tasks.pop(idx)
        save_json(TASKS_FILE, self.tasks)
        self.refresh_tasks_list()
        self.set_status(f"Task deleted: {removed['name']}")

    def refresh_tasks_list(self):
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        for t in self.tasks:
            tag = "done" if t["status"] == "Done" else ""
            self.task_tree.insert("", tk.END, values=(
                t["status"], t["name"], t.get("due", ""),
                t.get("priority", ""), t.get("created", ""),
            ), tags=(tag,))
        self.task_tree.tag_configure("done", foreground="#445577")

    def export_tasks(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Text", "*.txt"), ("All", "*.*")],
            title="Export Tasks",
        )
        if path:
            if path.endswith(".txt"):
                with open(path, "w", encoding="utf-8") as f:
                    for t in self.tasks:
                        line = f"[{t['status']}] {t['name']}"
                        if t.get("due"):
                            line += f" (due: {t['due']})"
                        if t.get("priority"):
                            line += f" [{t['priority']}]"
                        f.write(line + "\n")
            else:
                save_json(path, self.tasks)
            self.set_status(f"Tasks exported to {os.path.basename(path)}")

    def import_tasks(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            title="Import Tasks",
        )
        if path:
            imported = load_json(path, [])
            self.tasks.extend(imported)
            save_json(TASKS_FILE, self.tasks)
            self.refresh_tasks_list()
            self.set_status(f"Imported {len(imported)} tasks")

    # --------------------------------------------------------
    # TAB 3: Files
    # --------------------------------------------------------
    def create_files_tab(self):
        frame = tk.Frame(self.notebook, bg="#000000")
        self.notebook.add(frame, text=" Files ")

        # Path bar
        path_frame = tk.Frame(frame, bg="#000000")
        path_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(path_frame, text="Path:", bg="#000000", fg="white",
                 font=("Consolas", 10)).pack(side=tk.LEFT)
        self.file_path_entry = tk.Entry(
            path_frame, bg="#041228", fg="white", font=("Consolas", 10),
            insertbackground="white",
        )
        self.file_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.file_path_entry.insert(0, WIDGET_DIR)
        self.file_path_entry.bind("<Return>", lambda e: self.browse_path())

        tk.Button(
            path_frame, text="Go", command=self.browse_path,
            bg="#0066cc", fg="white", font=("Consolas", 9),
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            path_frame, text="Browse...", command=self.pick_folder,
            bg="#0a1e3a", fg="white", font=("Consolas", 9),
        ).pack(side=tk.LEFT, padx=2)

        # File list
        list_frame = tk.Frame(frame, bg="#000000")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5)

        columns = ("name", "type", "size", "modified")
        self.file_tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", height=10,
        )
        self.file_tree.heading("name", text="Name")
        self.file_tree.heading("type", text="Type")
        self.file_tree.heading("size", text="Size")
        self.file_tree.heading("modified", text="Modified")

        self.file_tree.column("name", width=250)
        self.file_tree.column("type", width=80, anchor="center")
        self.file_tree.column("size", width=100, anchor="e")
        self.file_tree.column("modified", width=150, anchor="center")

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_tree.bind("<Double-1>", self.on_file_double_click)

        # File action buttons
        action_frame = tk.Frame(frame, bg="#000000")
        action_frame.pack(fill=tk.X, padx=5, pady=2)

        for text, cmd in [
            ("View File", self.view_selected_file),
            ("Open in Editor", self.open_in_editor),
            ("Copy to Clipboard", self.copy_file_content),
            ("Watch Folder", self.set_watch_folder),
        ]:
            tk.Button(
                action_frame, text=text, command=cmd,
                bg="#0a1e3a", fg="white", font=("Consolas", 9),
            ).pack(side=tk.LEFT, padx=2)

        # File preview area
        self.file_preview = tk.Text(
            frame, bg="#000000", fg="#cccccc", font=("Consolas", 10),
            wrap=tk.WORD, height=8, relief=tk.SUNKEN, borderwidth=2,
        )
        self.file_preview.pack(fill=tk.X, padx=5, pady=(2, 5))

        # Load initial directory
        self.browse_path()

    def browse_path(self):
        path = self.file_path_entry.get().strip()
        if not os.path.isdir(path):
            self.set_status(f"Not a directory: {path}")
            return

        for item in self.file_tree.get_children():
            self.file_tree.delete(item)

        try:
            # Parent directory entry
            parent = os.path.dirname(path)
            if parent != path:
                self.file_tree.insert("", tk.END, values=("..", "DIR", "", ""), tags=("dir",))

            entries = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
            for entry in entries:
                full = os.path.join(path, entry)
                try:
                    stat = os.stat(full)
                    mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    if os.path.isdir(full):
                        self.file_tree.insert("", tk.END, values=(
                            entry, "DIR", "", mod_time,
                        ), tags=("dir",))
                    else:
                        ext = os.path.splitext(entry)[1] or "file"
                        size = self._format_size(stat.st_size)
                        self.file_tree.insert("", tk.END, values=(
                            entry, ext, size, mod_time,
                        ))
                except (OSError, PermissionError):
                    self.file_tree.insert("", tk.END, values=(entry, "?", "?", "?"))

            self.file_tree.tag_configure("dir", foreground="#0088ff")
            self.set_status(f"Browsing: {path}")
        except (OSError, PermissionError) as e:
            self.set_status(f"Error: {e}")

    def _format_size(self, size):
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def pick_folder(self):
        path = filedialog.askdirectory(title="Choose Folder")
        if path:
            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(0, path)
            self.browse_path()

    def on_file_double_click(self, event):
        selected = self.file_tree.selection()
        if not selected:
            return
        values = self.file_tree.item(selected[0], "values")
        name = values[0]
        current = self.file_path_entry.get().strip()

        if name == "..":
            parent = os.path.dirname(current)
            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(0, parent)
            self.browse_path()
        elif values[1] == "DIR":
            new_path = os.path.join(current, name)
            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(0, new_path)
            self.browse_path()
        else:
            self.view_selected_file()

    def _get_selected_file_path(self):
        selected = self.file_tree.selection()
        if not selected:
            return None
        name = self.file_tree.item(selected[0], "values")[0]
        return os.path.join(self.file_path_entry.get().strip(), name)

    def view_selected_file(self):
        path = self._get_selected_file_path()
        if not path or not os.path.isfile(path):
            return
        self.file_preview.delete("1.0", tk.END)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(100000)
            self.file_preview.insert("1.0", content)
            self.set_status(f"Viewing: {os.path.basename(path)}")
        except Exception as e:
            self.file_preview.insert("1.0", f"Cannot read file: {e}")

    def open_in_editor(self):
        path = self._get_selected_file_path()
        if path and os.path.isfile(path):
            os.startfile(path)

    def copy_file_content(self):
        content = self.file_preview.get("1.0", tk.END).strip()
        if content:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.set_status("File content copied to clipboard")

    def set_watch_folder(self):
        path = self.file_path_entry.get().strip()
        if os.path.isdir(path):
            self.settings["watch_folder"] = path
            save_json(SETTINGS_FILE, self.settings)
            self.watched_files = set(os.listdir(path))
            self.set_status(f"Watching folder: {path}")
            self.add_notification(f"Now watching: {path}")

    # --------------------------------------------------------
    # TAB 4: Notifications
    # --------------------------------------------------------
    def create_notifications_tab(self):
        frame = tk.Frame(self.notebook, bg="#000000")
        self.notebook.add(frame, text=" Notifications ")

        # Notification list
        self.notif_listbox = tk.Listbox(
            frame, bg="#000000", fg="#cccccc", font=("Consolas", 10),
            selectbackground="#0a2e5a", relief=tk.SUNKEN, borderwidth=2,
        )
        self.notif_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Action buttons
        btn_frame = tk.Frame(frame, bg="#000000")
        btn_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        tk.Button(
            btn_frame, text="Clear All", command=self.clear_notifications,
            bg="#0a1e3a", fg="white", font=("Consolas", 9),
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            btn_frame, text="Export Notifications", command=self.export_notifications,
            bg="#0a1e3a", fg="white", font=("Consolas", 9),
        ).pack(side=tk.LEFT, padx=2)

    def add_notification(self, message):
        notif = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": message,
        }
        self.notifications.insert(0, notif)
        # Keep last 200 notifications
        self.notifications = self.notifications[:200]
        save_json(NOTIFICATIONS_FILE, self.notifications)
        self.refresh_notifications_list()

    def refresh_notifications_list(self):
        self.notif_listbox.delete(0, tk.END)
        for n in self.notifications:
            self.notif_listbox.insert(tk.END, f"[{n['time']}] {n['message']}")

    def clear_notifications(self):
        self.notifications.clear()
        save_json(NOTIFICATIONS_FILE, self.notifications)
        self.refresh_notifications_list()
        self.set_status("Notifications cleared")

    def export_notifications(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("JSON", "*.json"), ("All", "*.*")],
            title="Export Notifications",
        )
        if path:
            if path.endswith(".json"):
                save_json(path, self.notifications)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    for n in self.notifications:
                        f.write(f"[{n['time']}] {n['message']}\n")
            self.set_status(f"Notifications exported")

    # --------------------------------------------------------
    # Background watchers
    # --------------------------------------------------------
    def _start_watchers(self):
        # File watcher thread
        self._watcher_running = True
        threading.Thread(target=self._watch_loop, daemon=True).start()
        # Task deadline checker
        threading.Thread(target=self._deadline_loop, daemon=True).start()

    def _watch_loop(self):
        """Watch a folder for new/changed files."""
        while self._watcher_running:
            folder = self.settings.get("watch_folder", "")
            if folder and os.path.isdir(folder):
                try:
                    current = set(os.listdir(folder))
                    new_files = current - self.watched_files
                    if new_files and self.watched_files:  # skip first scan
                        for f in new_files:
                            self.root.after(0, self.add_notification, f"New file detected: {f}")
                    self.watched_files = current
                except (OSError, PermissionError):
                    pass
            time.sleep(5)

    def _deadline_loop(self):
        """Check for upcoming task deadlines."""
        while self._watcher_running:
            today = datetime.now().strftime("%Y-%m-%d")
            for t in self.tasks:
                if t.get("status") == "Pending" and t.get("due") == today:
                    msg = f"Task due today: {t['name']}"
                    # Avoid duplicate notifications
                    recent = [n["message"] for n in self.notifications[:10]]
                    if msg not in recent:
                        self.root.after(0, self.add_notification, msg)
            time.sleep(60)

    # --------------------------------------------------------
    # Tray / Window management
    # --------------------------------------------------------
    def minimize_to_tray(self):
        """Minimize to a small floating button instead of closing."""
        self.root.withdraw()
        self.is_hidden = True

        # Create a small floating restore button
        if not hasattr(self, "tray_win") or not self.tray_win.winfo_exists():
            self.tray_win = tk.Toplevel()
            self.tray_win.title("TM")
            self.tray_win.geometry("120x40+10+10")
            self.tray_win.overrideredirect(True)
            self.tray_win.attributes("-topmost", True)
            self.tray_win.configure(bg="#0066cc")

            tk.Button(
                self.tray_win, text="TM Widget", command=self.restore_from_tray,
                bg="#0066cc", fg="white", font=("Consolas", 9, "bold"),
                relief=tk.FLAT, padx=8, pady=4,
            ).pack(fill=tk.BOTH, expand=True)

            # Make it draggable
            self.tray_win.bind("<Button-1>", self._tray_start_drag)
            self.tray_win.bind("<B1-Motion>", self._tray_drag)

    def _tray_start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _tray_drag(self, event):
        x = self.tray_win.winfo_x() + event.x - self._drag_x
        y = self.tray_win.winfo_y() + event.y - self._drag_y
        self.tray_win.geometry(f"+{x}+{y}")

    def restore_from_tray(self):
        self.is_hidden = False
        if hasattr(self, "tray_win") and self.tray_win.winfo_exists():
            self.tray_win.destroy()
        self.root.deiconify()
        self.root.lift()

    def open_custom_terminal(self):
        """Launch the custom terminal alongside this widget."""
        terminal_path = os.path.join(WIDGET_DIR, "custom_terminal.py")
        if os.path.exists(terminal_path):
            subprocess.Popen(["python", terminal_path], creationflags=subprocess.CREATE_NO_WINDOW)
            self.set_status("Custom Terminal launched")
        else:
            self.set_status("custom_terminal.py not found")

    def set_status(self, text):
        self.status_bar.config(text=text)

    def quit_app(self):
        self._watcher_running = False
        save_json(TASKS_FILE, self.tasks)
        save_json(SETTINGS_FILE, self.settings)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ============================================================
# Entry point
# ============================================================
if __name__ == "__main__":
    app = TMWidget()
    app.run()
