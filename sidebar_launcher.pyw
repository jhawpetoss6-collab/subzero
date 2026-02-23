"""
SubZero Sidebar Launcher
─────────────────────────
Sleek slide-out panel on the right edge of the screen.
• All SubZero apps arranged bottom-to-top
• Integrated SubZero chat at the top
• Click the tab to slide in/out
"""
import tkinter as tk
import subprocess
import os
import sys
import json
import threading
import urllib.request
from pathlib import Path
from datetime import datetime
from sz_runtime import ToolRuntime

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

LOGO_PATH = Path(__file__).parent / "logo.png"
QR_PATH   = Path(__file__).parent / "qr_code.png"
DOWNLOAD_URL = "https://github.com/jhawp/subzero"

# ── App registry (bottom → top order) ──────────────────────────
# Each entry: (label, color_accent, launch_command)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PS = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
PY = r"C:\Python314\pythonw.exe"

APPS = [
    # Bottom of sidebar (index 0) → Top of sidebar (last)
    ("SubZero Agent",    "#e91e63", [PY, os.path.join(SCRIPT_DIR, "subzero_agent_gui.pyw")]),
    ("SubZero Learn",    "#9c27b0", [PY, os.path.join(SCRIPT_DIR, "subzero_learn_gui.pyw")]),
    ("SubZero Suite",    "#673ab7", [PY, os.path.join(SCRIPT_DIR, "launch_all.pyw")]),
    ("SubZero Training", "#3f51b5", [PY, os.path.join(SCRIPT_DIR, "subzero_training_gui.pyw")]),
    ("SubZero Swarm",    "#2196f3", [PY, os.path.join(SCRIPT_DIR, "swarm_tasks.pyw")]),
    ("SubZero DualCore", "#00bcd4", [PY, os.path.join(SCRIPT_DIR, "subzero_dualcore_gui.pyw")]),
    ("SubZero Recursive","#009688", [PY, os.path.join(SCRIPT_DIR, "subzero_recursive_gui.pyw")]),
    ("Spine Rip",        "#0088ff", [PY, os.path.join(SCRIPT_DIR, "warp_oz.pyw")]),
    ("TM Widget",        "#ff9800", [PY, os.path.join(SCRIPT_DIR, "terminal_widget.py")]),
    ("Custom Terminal",  "#ff5722", [PY, os.path.join(SCRIPT_DIR, "custom_terminal.py")]),
    ("Snowflake 2.5",    "#03dac6", [PY, os.path.join(SCRIPT_DIR, "snowflake25.pyw")]),
    ("SubZero",          "#7c4dff", [PS, "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-File", os.path.join(SCRIPT_DIR, "subzero-simple.ps1")]),
]

# ── Colors ─────────────────────────────────────────────────────
BG_DARK      = "#000000"
BG_PANEL     = "#020810"
BG_CARD      = "#010610"
BG_INPUT     = "#081428"
BG_HOVER     = "#041228"
FG_PRIMARY   = "#e0e0e0"
FG_DIM       = "#445577"
ACCENT       = "#0066cc"
TAB_BG       = "#0066cc"
TAB_HOVER    = "#0088ff"
CHAT_USER    = "#4499dd"
CHAT_SZ      = "#00aaff"
BORDER_COLOR = "#0a1e3a"

SIDEBAR_W    = 280
TAB_W        = 28
SLIDE_SPEED  = 15   # ms per frame
SLIDE_STEP   = 40   # pixels per frame


class SubZeroChatEngine:
    """Lightweight Ollama chat for the sidebar."""

    def __init__(self, model="qwen2.5:3b"):
        self.model = model
        self.conversation = []
        self.last_success = True
        self.tool_runtime = ToolRuntime()

    def is_running(self):
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status == 200
        except Exception:
            return False

    def send_stream(self, message, on_token, on_done):
        """Stream response token-by-token. Callbacks are called from worker thread."""
        self.conversation.append({"role": "user", "content": message})
        context = "\n".join(
            f"{'User' if m['role']=='user' else 'SubZero'}: {m['content']}"
            for m in self.conversation[-8:]
        )
        sys_prompt = (
            "You are SubZero, an autonomous AI assistant. "
            + self.tool_runtime.get_system_prompt() + "\n"
        )
        prompt = f"{sys_prompt}\n{context}\nSubZero:"
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
            full_text = ""
            with urllib.request.urlopen(req, timeout=300) as resp:
                for line in resp:
                    chunk = json.loads(line.decode("utf-8"))
                    token = chunk.get("response", "")
                    if token:
                        full_text += token
                        on_token(token)
                    if chunk.get("done"):
                        break
            full_text = full_text.strip()
            if full_text:
                self.conversation.append({"role": "assistant", "content": full_text})
                self.last_success = True
                # Execute any tool calls in the response
                tool_calls = self.tool_runtime.parse(full_text)
                if tool_calls:
                    results = self.tool_runtime.execute_all(tool_calls)
                    for r in results:
                        status = "\u2713" if r.success else "\u2717"
                        on_token(f"\n[{status} {r.tool_name}] {r.output[:150]}")
            else:
                self.last_success = False
                on_token("[No response from Ollama]")
            on_done(self.last_success)
        except Exception as e:
            self.last_success = False
            on_token(f"[Error] {e}")
            on_done(False)


class SidebarLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Sub-Zero Flawless Victory")
        self.root.overrideredirect(True)           # frameless
        self.root.attributes("-topmost", True)      # always on top
        self.root.attributes("-alpha", 0.96)        # slight transparency
        self.root.configure(bg=BG_DARK)

        # Screen geometry
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        self.full_w = SIDEBAR_W + TAB_W
        self.root.geometry(
            f"{self.full_w}x{self.screen_h}"
            f"+{self.screen_w - TAB_W}+0"
        )

        self.is_open = False
        self._animating = False
        self.chat_engine = SubZeroChatEngine()

        self._build_ui()
        self.root.mainloop()

    # ── UI Construction ────────────────────────────────────────

    def _build_ui(self):
        # Main container (tab handle + panel)
        self.container = tk.Frame(self.root, bg=BG_DARK)
        self.container.pack(fill=tk.BOTH, expand=True)

        # ── Slide tab (visible when closed) ─────────────
        self.tab = tk.Canvas(
            self.container, width=TAB_W, bg=BG_DARK,
            highlightthickness=0, cursor="hand2",
        )
        self.tab.pack(side=tk.LEFT, fill=tk.Y)
        self._draw_tab()
        self.tab.bind("<Button-1>", lambda e: self.toggle())
        self.tab.bind("<Enter>", self._tab_hover_in)
        self.tab.bind("<Leave>", self._tab_hover_out)

        # ── Main panel ──────────────────────────────────
        self.panel = tk.Frame(self.container, bg=BG_PANEL, width=SIDEBAR_W)
        self.panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.panel.pack_propagate(False)

        # ─ Header ─
        header = tk.Frame(self.panel, bg=ACCENT, height=48)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        # Logo + brand
        self._logo_img = None
        if HAS_PIL and LOGO_PATH.exists():
            try:
                img = Image.open(LOGO_PATH).resize((28, 28), Image.LANCZOS)
                self._logo_img = ImageTk.PhotoImage(img)
                tk.Label(
                    header, image=self._logo_img, bg=ACCENT,
                ).pack(side=tk.LEFT, padx=(10, 4))
            except Exception:
                tk.Label(
                    header, text="✦", bg=ACCENT, fg="#00aaff",
                    font=("Segoe UI", 13),
                ).pack(side=tk.LEFT, padx=(10, 4))
        else:
            tk.Label(
                header, text="✦", bg=ACCENT, fg="#00aaff",
                font=("Segoe UI", 13),
            ).pack(side=tk.LEFT, padx=(10, 4))
        brand_frame = tk.Frame(header, bg=ACCENT)
        brand_frame.pack(side=tk.LEFT)
        tk.Label(
            brand_frame, text="S U B - Z E R O", bg=ACCENT, fg="white",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        tk.Label(
            brand_frame, text="FLAWLESS VICTORY", bg=ACCENT, fg="#99ccff",
            font=("Segoe UI", 6, "bold"),
        ).pack(anchor="w")
        tk.Button(
            header, text="✕", bg=ACCENT, fg="white",
            font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
            activebackground="#004499", cursor="hand2",
            command=self.toggle,
        ).pack(side=tk.RIGHT, padx=8)

        # ─ Divider ─
        tk.Frame(self.panel, bg=BORDER_COLOR, height=1).pack(fill=tk.X)

        # ─ Chat section (top) ─
        self._build_chat_section()

        # ─ Divider ─
        tk.Frame(self.panel, bg=BORDER_COLOR, height=1).pack(fill=tk.X)

        # ─ App launcher section (bottom, scrollable) ─
        self._build_app_section()

        # ─ QR Code section ─
        self._build_qr_section()

        # ─ Footer status ─
        self.footer = tk.Label(
            self.panel, text="", bg=BG_DARK, fg=FG_DIM,
            font=("Segoe UI", 7), anchor="w", padx=8, pady=2,
        )
        self.footer.pack(fill=tk.X, side=tk.BOTTOM)
        self._update_status()

    def _draw_tab(self, color=TAB_BG):
        """Draw the vertical tab handle with an arrow."""
        self.tab.delete("all")
        w, h = TAB_W, self.screen_h
        # Tab pill shape in the middle
        cy = h // 2
        pill_h = 80
        self.tab.create_rounded_rect = None  # not needed
        self.tab.create_rectangle(
            2, cy - pill_h // 2, w - 2, cy + pill_h // 2,
            fill=color, outline="", width=0,
        )
        # Arrow
        arrow = "◀" if self.is_open else "▶"
        self.tab.create_text(
            w // 2, cy - 10, text="❄", fill="white",
            font=("Segoe UI", 10),
        )
        self.tab.create_text(
            w // 2, cy + 14, text=arrow, fill="white",
            font=("Segoe UI", 9, "bold"),
        )

    def _tab_hover_in(self, e):
        self._draw_tab(TAB_HOVER)

    def _tab_hover_out(self, e):
        self._draw_tab(TAB_BG)

    # ── QR Code Section ──────────────────────────────────────────

    def _build_qr_section(self):
        """QR code at bottom of sidebar. Click to copy link, right-click for menu."""
        qr_frame = tk.Frame(self.panel, bg=BG_PANEL)
        qr_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(4, 2))

        # Section label
        lbl_frame = tk.Frame(qr_frame, bg=BG_PANEL)
        lbl_frame.pack(fill=tk.X, padx=10, pady=(4, 2))
        tk.Label(
            lbl_frame, text="SHARE", bg=BG_PANEL, fg=FG_DIM,
            font=("Segoe UI", 7, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            lbl_frame, text="Scan or Click", bg=BG_PANEL, fg=FG_DIM,
            font=("Segoe UI", 7),
        ).pack(side=tk.RIGHT)

        # QR image container
        qr_card = tk.Frame(qr_frame, bg=BG_CARD, cursor="hand2",
                           highlightbackground=BORDER_COLOR, highlightthickness=1)
        qr_card.pack(fill=tk.X, padx=8, pady=(0, 2))

        self._qr_img = None
        if HAS_PIL and QR_PATH.exists():
            try:
                img = Image.open(QR_PATH).resize((80, 80), Image.LANCZOS)
                self._qr_img = ImageTk.PhotoImage(img)
            except Exception:
                pass

        inner_qr = tk.Frame(qr_card, bg=BG_CARD)
        inner_qr.pack(padx=8, pady=6)

        if self._qr_img:
            qr_label = tk.Label(inner_qr, image=self._qr_img, bg=BG_CARD, cursor="hand2")
            qr_label.pack(side=tk.LEFT, padx=(0, 8))
        else:
            qr_label = tk.Label(inner_qr, text="[QR]", bg=BG_CARD, fg=FG_DIM,
                                font=("Consolas", 9), cursor="hand2")
            qr_label.pack(side=tk.LEFT, padx=(0, 8))

        text_frame = tk.Frame(inner_qr, bg=BG_CARD)
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(
            text_frame, text="Sub-Zero", bg=BG_CARD, fg=FG_PRIMARY,
            font=("Segoe UI", 9, "bold"), anchor="w",
        ).pack(anchor="w")
        tk.Label(
            text_frame, text="Flawless Victory", bg=BG_CARD, fg="#03dac6",
            font=("Segoe UI", 8, "bold"), anchor="w",
        ).pack(anchor="w")
        self.qr_status = tk.Label(
            text_frame, text="Click to copy link", bg=BG_CARD, fg=FG_DIM,
            font=("Segoe UI", 7), anchor="w",
        )
        self.qr_status.pack(anchor="w")

        # Context menu
        self.qr_ctx = tk.Menu(self.root, tearoff=0, bg=BG_HOVER, fg="white",
                              font=("Segoe UI", 9))
        self.qr_ctx.add_command(label="Copy Download Link", command=self._copy_qr_link)
        self.qr_ctx.add_command(label="Copy QR Image", command=self._copy_qr_image)
        self.qr_ctx.add_separator()
        self.qr_ctx.add_command(label="Open in Browser", command=self._open_qr_link)

        # Bind click and right-click to all widgets in the card
        for widget in [qr_card, inner_qr, qr_label, text_frame] + text_frame.winfo_children():
            widget.bind("<Button-1>", lambda e: self._copy_qr_link())
            widget.bind("<Button-3>", self._show_qr_ctx)

        # Hover effects
        def qr_hover_in(e):
            qr_card.config(highlightbackground=ACCENT)
            for w in [qr_card, inner_qr, qr_label, text_frame] + text_frame.winfo_children():
                try: w.config(bg=BG_HOVER)
                except tk.TclError: pass

        def qr_hover_out(e):
            qr_card.config(highlightbackground=BORDER_COLOR)
            for w in [qr_card, inner_qr, qr_label, text_frame] + text_frame.winfo_children():
                try: w.config(bg=BG_CARD)
                except tk.TclError: pass

        for widget in [qr_card, inner_qr, qr_label, text_frame] + text_frame.winfo_children():
            widget.bind("<Enter>", qr_hover_in)
            widget.bind("<Leave>", qr_hover_out)

    def _show_qr_ctx(self, event):
        try:
            self.qr_ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self.qr_ctx.grab_release()

    def _copy_qr_link(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(DOWNLOAD_URL)
        self.qr_status.config(text="\u2713 Link copied!", fg="#03dac6")
        self.root.after(2000, lambda: self.qr_status.config(text="Click to copy link", fg=FG_DIM))

    def _copy_qr_image(self):
        """Copy QR code image to clipboard via PowerShell."""
        if QR_PATH.exists():
            try:
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command",
                     f"Add-Type -AssemblyName System.Windows.Forms; "
                     f"[System.Windows.Forms.Clipboard]::SetImage("
                     f"[System.Drawing.Image]::FromFile('{QR_PATH}'))"],
                    creationflags=0x08000000,
                )
                self.qr_status.config(text="\u2713 QR image copied!", fg="#03dac6")
                self.root.after(2000, lambda: self.qr_status.config(text="Click to copy link", fg=FG_DIM))
            except Exception:
                self._copy_qr_link()  # fallback
        else:
            self._copy_qr_link()

    def _open_qr_link(self):
        import webbrowser
        webbrowser.open(DOWNLOAD_URL)

    # ── Chat Section ───────────────────────────────────────────

    def _build_chat_section(self):
        chat_frame = tk.Frame(self.panel, bg=BG_PANEL)
        chat_frame.pack(fill=tk.BOTH, expand=True)

        # Chat label
        lbl_frame = tk.Frame(chat_frame, bg=BG_PANEL)
        lbl_frame.pack(fill=tk.X, padx=10, pady=(8, 2))
        tk.Label(
            lbl_frame, text="CHAT", bg=BG_PANEL, fg=FG_DIM,
            font=("Segoe UI", 8, "bold"),
        ).pack(side=tk.LEFT)
        # Online dot
        self.chat_dot = tk.Label(
            lbl_frame, text="●", bg=BG_PANEL, fg=FG_DIM,
            font=("Segoe UI", 8),
        )
        self.chat_dot.pack(side=tk.RIGHT)

        # Chat output
        self.chat_output = tk.Text(
            chat_frame, bg=BG_CARD, fg=FG_PRIMARY,
            font=("Consolas", 9), wrap=tk.WORD,
            relief=tk.FLAT, borderwidth=0, padx=8, pady=6,
            insertbackground="white", selectbackground=ACCENT,
            height=8,
        )
        self.chat_output.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2, 4))
        self.chat_output.config(state=tk.DISABLED)

        # Right-click context menu for chat output
        self.chat_ctx = tk.Menu(self.root, tearoff=0, bg=BG_HOVER, fg="white")
        self.chat_ctx.add_command(label="Copy", command=self._chat_copy)
        self.chat_ctx.add_command(label="Select All", command=self._chat_select_all)
        self.chat_output.bind("<Button-3>", self._show_chat_ctx)
        self.chat_output.bind("<Control-c>", lambda e: self._chat_copy())

        # Color tags
        self.chat_output.tag_configure("user", foreground=CHAT_USER)
        self.chat_output.tag_configure("sz", foreground=CHAT_SZ)
        self.chat_output.tag_configure("system", foreground=FG_DIM)

        self._chat_append("SubZero ready.\n", "system")

        # Chat input row
        input_frame = tk.Frame(chat_frame, bg=BG_PANEL)
        input_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.chat_input = tk.Entry(
            input_frame, bg=BG_INPUT, fg=FG_PRIMARY,
            font=("Consolas", 9), relief=tk.FLAT, borderwidth=4,
            insertbackground="white",
        )
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.chat_input.bind("<Return>", lambda e: self._chat_send())

        # Right-click context menu for chat input
        self.input_ctx = tk.Menu(self.root, tearoff=0, bg=BG_HOVER, fg="white")
        self.input_ctx.add_command(label="Paste", command=self._input_paste)
        self.input_ctx.add_command(label="Copy", command=self._input_copy)
        self.input_ctx.add_separator()
        self.input_ctx.add_command(label="Clear", command=lambda: self.chat_input.delete(0, tk.END))
        self.chat_input.bind("<Button-3>", self._show_input_ctx)

        tk.Button(
            input_frame, text="▶", bg=ACCENT, fg="white",
            font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
            activebackground="#004499", cursor="hand2", padx=6,
            command=self._chat_send,
        ).pack(side=tk.RIGHT)

    def _show_chat_ctx(self, event):
        try:
            self.chat_ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self.chat_ctx.grab_release()

    def _chat_copy(self):
        try:
            selected = self.chat_output.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
        except tk.TclError:
            pass

    def _chat_select_all(self):
        self.chat_output.config(state=tk.NORMAL)
        self.chat_output.tag_add(tk.SEL, "1.0", tk.END)
        self.chat_output.config(state=tk.DISABLED)

    def _show_input_ctx(self, event):
        try:
            self.input_ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self.input_ctx.grab_release()

    def _input_paste(self):
        try:
            clip = self.root.clipboard_get()
            self.chat_input.insert(tk.INSERT, clip)
        except tk.TclError:
            pass

    def _input_copy(self):
        try:
            if self.chat_input.selection_present():
                selected = self.chat_input.selection_get()
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
        except tk.TclError:
            pass

    def _chat_append(self, text, tag=None):
        self.chat_output.config(state=tk.NORMAL)
        if tag:
            self.chat_output.insert(tk.END, text, tag)
        else:
            self.chat_output.insert(tk.END, text)
        self.chat_output.see(tk.END)
        self.chat_output.config(state=tk.DISABLED)

    def _chat_send(self):
        msg = self.chat_input.get().strip()
        if not msg:
            return
        self.chat_input.delete(0, tk.END)
        self._chat_append(f"You: {msg}\n", "user")
        self._chat_append("SubZero: ", "sz")
        self._streaming_first = True

        def on_token(token):
            def _append():
                self.chat_output.config(state=tk.NORMAL)
                self.chat_output.insert(tk.END, token, "sz")
                self.chat_output.see(tk.END)
                self.chat_output.config(state=tk.DISABLED)
            self.root.after(0, _append)

        def on_done(success):
            def _finish():
                self._chat_append("\n\n", None)
                if not success:
                    self.chat_dot.config(fg="#ff1744", text="● Offline")
            self.root.after(0, _finish)

        threading.Thread(
            target=self.chat_engine.send_stream,
            args=(msg, on_token, on_done),
            daemon=True,
        ).start()

    # ── App Launcher Section ───────────────────────────────────

    def _build_app_section(self):
        # Section label
        lbl_frame = tk.Frame(self.panel, bg=BG_PANEL)
        lbl_frame.pack(fill=tk.X, padx=10, pady=(8, 4))
        tk.Label(
            lbl_frame, text="APPLICATIONS", bg=BG_PANEL, fg=FG_DIM,
            font=("Segoe UI", 8, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            lbl_frame, text=f"{len(APPS)}", bg=BG_PANEL, fg=FG_DIM,
            font=("Segoe UI", 8),
        ).pack(side=tk.RIGHT)

        # Scrollable area
        canvas_frame = tk.Frame(self.panel, bg=BG_PANEL)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        canvas = tk.Canvas(
            canvas_frame, bg=BG_PANEL, highlightthickness=0, borderwidth=0,
        )
        scrollbar = tk.Scrollbar(
            canvas_frame, orient=tk.VERTICAL, command=canvas.yview,
            bg=BG_DARK, troughcolor=BG_PANEL,
        )
        self.app_list = tk.Frame(canvas, bg=BG_PANEL)

        self.app_list.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self.app_list, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._app_canvas = canvas

        # Mouse wheel scrolling — scoped to canvas only
        self._mouse_over_apps = False

        def _on_mousewheel(event):
            if self._mouse_over_apps:
                # Normalize: Windows gives delta in multiples of 120
                direction = -1 if event.delta > 0 else 1
                canvas.yview_scroll(direction * 3, "units")
                return "break"  # stop event propagation

        def _enter_app_area(event):
            self._mouse_over_apps = True

        def _leave_app_area(event):
            self._mouse_over_apps = False
            self._auto_scroll_speed = 0

        # Bind mousewheel globally but only act when over app area
        self.root.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind("<Enter>", _enter_app_area)
        canvas.bind("<Leave>", _leave_app_area)

        # Auto-scroll when mouse is near top/bottom edges of the app list
        self._auto_scroll_speed = 0

        def _check_edge_scroll(event):
            if not self._mouse_over_apps:
                self._auto_scroll_speed = 0
                return
            try:
                cy = canvas.winfo_rooty()
                ch = canvas.winfo_height()
                mouse_y = event.y_root
                edge = 40  # pixels from edge to trigger scroll

                if mouse_y < cy + edge and mouse_y >= cy:
                    self._auto_scroll_speed = -2  # scroll up
                elif mouse_y > cy + ch - edge and mouse_y <= cy + ch:
                    self._auto_scroll_speed = 2   # scroll down
                else:
                    self._auto_scroll_speed = 0
            except Exception:
                self._auto_scroll_speed = 0

        def _do_auto_scroll():
            if self._auto_scroll_speed != 0 and self._mouse_over_apps:
                canvas.yview_scroll(self._auto_scroll_speed, "units")
            self.root.after(80, _do_auto_scroll)

        canvas.bind("<Motion>", _check_edge_scroll)
        self.root.after(80, _do_auto_scroll)

        # Build app cards (reversed so bottom-to-top maps to visual top-to-bottom)
        for name, color, cmd in reversed(APPS):
            self._make_app_card(name, color, cmd)

    def _make_app_card(self, name, color, cmd):
        """Create a single app launch card."""
        card = tk.Frame(
            self.app_list, bg=BG_CARD, cursor="hand2",
            highlightbackground=BORDER_COLOR, highlightthickness=1,
        )
        card.pack(fill=tk.X, pady=2)

        inner = tk.Frame(card, bg=BG_CARD)
        inner.pack(fill=tk.X, padx=10, pady=8)

        # Color accent bar
        accent = tk.Frame(inner, bg=color, width=4, height=24)
        accent.pack(side=tk.LEFT, padx=(0, 10))

        # Icon circle
        icon_canvas = tk.Canvas(
            inner, width=28, height=28, bg=BG_CARD, highlightthickness=0,
        )
        icon_canvas.pack(side=tk.LEFT, padx=(0, 8))
        icon_canvas.create_oval(2, 2, 26, 26, fill=color, outline="")
        # First letter
        initial = name.replace("SubZero ", "").replace("SubZero", "SZ")[0]
        icon_canvas.create_text(14, 14, text=initial, fill="white", font=("Segoe UI", 9, "bold"))

        # Label
        tk.Label(
            inner, text=name, bg=BG_CARD, fg=FG_PRIMARY,
            font=("Segoe UI", 9), anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Launch arrow
        arrow = tk.Label(
            inner, text="▶", bg=BG_CARD, fg=FG_DIM,
            font=("Segoe UI", 8),
        )
        arrow.pack(side=tk.RIGHT)

        # Hover effects
        def hover_in(e):
            card.config(highlightbackground=color)
            for w in (card, inner, arrow):
                w.config(bg=BG_HOVER)
            for child in inner.winfo_children():
                try:
                    child.config(bg=BG_HOVER)
                except tk.TclError:
                    pass

        def hover_out(e):
            card.config(highlightbackground=BORDER_COLOR)
            for w in (card, inner, arrow):
                w.config(bg=BG_CARD)
            for child in inner.winfo_children():
                try:
                    child.config(bg=BG_CARD)
                except tk.TclError:
                    pass

        def launch(e):
            try:
                # Interactive PS terminals (-NoExit) need a visible console;
                # background PS scripts get CREATE_NO_WINDOW.
                if cmd[0] == PS and "-NoExit" in cmd:
                    flags = subprocess.CREATE_NEW_CONSOLE
                elif cmd[0] == PS:
                    flags = subprocess.CREATE_NO_WINDOW
                else:
                    flags = 0
                subprocess.Popen(cmd, creationflags=flags)
                self._flash_launched(card, name, color)
            except Exception as err:
                self._chat_append(f"[Launch Error] {name}: {err}\n", "system")

        for widget in [card, inner, arrow]:
            widget.bind("<Enter>", hover_in)
            widget.bind("<Leave>", hover_out)
            widget.bind("<Button-1>", launch)
        for child in inner.winfo_children():
            child.bind("<Enter>", hover_in)
            child.bind("<Leave>", hover_out)
            child.bind("<Button-1>", launch)

    def _flash_launched(self, card, name, color):
        """Brief visual flash when an app is launched."""
        original = card.cget("highlightbackground")
        card.config(highlightbackground=color, highlightthickness=2)
        self.footer.config(text=f"  Launched: {name}", fg=color)
        self.root.after(
            800,
            lambda: card.config(highlightbackground=original, highlightthickness=1),
        )
        self.root.after(3000, lambda: self.footer.config(text="", fg=FG_DIM))

    # ── Slide Animation ────────────────────────────────────────

    def toggle(self):
        if self._animating:
            return
        if self.is_open:
            self._slide_out()
        else:
            self._slide_in()

    def _slide_in(self):
        """Slide panel open (from right edge toward left)."""
        self._animating = True
        target_x = self.screen_w - self.full_w
        current_x = self.root.winfo_x()

        def step():
            nonlocal current_x
            current_x -= SLIDE_STEP
            if current_x <= target_x:
                current_x = target_x
                self.root.geometry(f"{self.full_w}x{self.screen_h}+{current_x}+0")
                self.is_open = True
                self._animating = False
                self._draw_tab()
                return
            self.root.geometry(f"{self.full_w}x{self.screen_h}+{current_x}+0")
            self.root.after(SLIDE_SPEED, step)

        step()

    def _slide_out(self):
        """Slide panel closed (hide behind right edge)."""
        self._animating = True
        target_x = self.screen_w - TAB_W
        current_x = self.root.winfo_x()

        def step():
            nonlocal current_x
            current_x += SLIDE_STEP
            if current_x >= target_x:
                current_x = target_x
                self.root.geometry(f"{self.full_w}x{self.screen_h}+{current_x}+0")
                self.is_open = False
                self._animating = False
                self._draw_tab()
                return
            self.root.geometry(f"{self.full_w}x{self.screen_h}+{current_x}+0")
            self.root.after(SLIDE_SPEED, step)

        step()

    # ── Status ─────────────────────────────────────────────────

    def _update_status(self):
        """Periodic check of Ollama status."""
        def check():
            running = self.chat_engine.is_running()
            color = CHAT_SZ if running else "#ff1744"
            label = "● Online" if running else "● Offline"
            self.root.after(0, lambda: self.chat_dot.config(fg=color, text=label))

        threading.Thread(target=check, daemon=True).start()
        self.root.after(10000, self._update_status)  # check every 10s


if __name__ == "__main__":
    SidebarLauncher()
