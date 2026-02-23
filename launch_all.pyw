"""
SubZero Suite — App Launcher
─────────────────────────────
Launch any SubZero application from a single window.
"""
import tkinter as tk
import subprocess, os, sys
from pathlib import Path

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

LOGO_PATH = Path(__file__).parent / "logo.png"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PY = r"C:\Python314\pythonw.exe"
PS = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

BG       = "#000000"
BG_PANEL = "#020810"
BG_CARD  = "#010610"
BG_HOVER = "#041228"
FG       = "#e0e0e0"
FG_DIM   = "#445577"
ACCENT   = "#0066cc"
BORDER   = "#0a1e3a"

APPS = [
    ("Spine Rip",         "#0088ff", "warp_oz.pyw"),
    ("Snowflake 2.5",     "#00aaff", "snowflake25.pyw"),
    ("SubZero Swarm",     "#0077dd", "swarm_tasks.pyw"),
    ("SubZero DualCore",  "#0066cc", "subzero_dualcore_gui.pyw"),
    ("SubZero Recursive", "#0088ff", "subzero_recursive_gui.pyw"),
    ("SubZero Training",  "#00aaff", "subzero_training_gui.pyw"),
    ("SubZero Agent",     "#0077dd", "subzero_agent_gui.pyw"),
    ("SubZero Learn",     "#0066cc", "subzero_learn_gui.pyw"),
    ("Custom Terminal",   "#0088ff", "custom_terminal.py"),
    ("TM Widget",         "#00aaff", "terminal_widget.py"),
]


class SubZeroSuite:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SubZero Suite")
        self.root.geometry("420x620")
        self.root.configure(bg=BG)
        self.root.attributes("-alpha", 0.96)
        self.root.minsize(360, 400)
        self.launched = 0
        self._build()
        self.root.mainloop()

    def _build(self):
        header = tk.Frame(self.root, bg=ACCENT, height=48)
        header.pack(fill=tk.X); header.pack_propagate(False)
        self._logo_img = None
        if HAS_PIL and LOGO_PATH.exists():
            try:
                img = Image.open(LOGO_PATH).resize((28, 28), Image.LANCZOS)
                self._logo_img = ImageTk.PhotoImage(img)
                tk.Label(header, image=self._logo_img, bg=ACCENT).pack(side=tk.LEFT, padx=(10, 4))
            except Exception:
                tk.Label(header, text="\u2726", bg=ACCENT, fg="#00aaff", font=("Segoe UI", 13)).pack(side=tk.LEFT, padx=(10, 4))
        else:
            tk.Label(header, text="\u2726", bg=ACCENT, fg="#00aaff", font=("Segoe UI", 13)).pack(side=tk.LEFT, padx=(10, 4))
        tk.Label(header, text="S U B Z E R O   S U I T E", bg=ACCENT, fg="white",
                 font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill=tk.X)

        lbl = tk.Frame(self.root, bg=BG_PANEL)
        lbl.pack(fill=tk.X, padx=10, pady=(8, 4))
        tk.Label(lbl, text="APPLICATIONS", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT)
        tk.Label(lbl, text=f"{len(APPS)}", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI", 8)).pack(side=tk.RIGHT)

        cf = tk.Frame(self.root, bg=BG_PANEL)
        cf.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))
        canvas = tk.Canvas(cf, bg=BG_PANEL, highlightthickness=0)
        sb = tk.Scrollbar(cf, orient=tk.VERTICAL, command=canvas.yview, bg=BG, troughcolor=BG_PANEL)
        self.app_list = tk.Frame(canvas, bg=BG_PANEL)
        self.app_list.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.app_list, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.root.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        for name, color, script in APPS:
            self._make_card(name, color, script)

        bf = tk.Frame(self.root, bg=BG_PANEL)
        bf.pack(fill=tk.X, padx=8, pady=(0, 6))
        tk.Button(bf, text="Launch All", bg=ACCENT, fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, activebackground="#004499", cursor="hand2",
                  command=self._launch_all).pack(fill=tk.X)

        self.footer = tk.Label(self.root, text="Click an app to launch", bg=BG, fg=FG_DIM,
                               font=("Segoe UI", 8), anchor="w", padx=10, pady=4)
        self.footer.pack(fill=tk.X, side=tk.BOTTOM)

    def _make_card(self, name, color, script):
        card = tk.Frame(self.app_list, bg=BG_CARD, cursor="hand2",
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill=tk.X, pady=2)
        inner = tk.Frame(card, bg=BG_CARD)
        inner.pack(fill=tk.X, padx=10, pady=8)
        tk.Frame(inner, bg=color, width=4, height=24).pack(side=tk.LEFT, padx=(0, 10))
        ic = tk.Canvas(inner, width=28, height=28, bg=BG_CARD, highlightthickness=0)
        ic.pack(side=tk.LEFT, padx=(0, 8))
        ic.create_oval(2, 2, 26, 26, fill=color, outline="")
        initial = name.replace("SubZero ", "").replace("SubZero", "SZ")[0]
        ic.create_text(14, 14, text=initial, fill="white", font=("Segoe UI", 9, "bold"))
        tk.Label(inner, text=name, bg=BG_CARD, fg=FG, font=("Segoe UI", 9), anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
        arrow = tk.Label(inner, text="\u25b6", bg=BG_CARD, fg=FG_DIM, font=("Segoe UI", 8))
        arrow.pack(side=tk.RIGHT)

        def hi(e):
            card.config(highlightbackground=color)
            for w in (card, inner, arrow):
                w.config(bg=BG_HOVER)
            for c in inner.winfo_children():
                try: c.config(bg=BG_HOVER)
                except tk.TclError: pass
        def ho(e):
            card.config(highlightbackground=BORDER)
            for w in (card, inner, arrow):
                w.config(bg=BG_CARD)
            for c in inner.winfo_children():
                try: c.config(bg=BG_CARD)
                except tk.TclError: pass
        def launch(e):
            self._launch(name, script, card, color)
        for w in [card, inner, arrow]:
            w.bind("<Enter>", hi); w.bind("<Leave>", ho); w.bind("<Button-1>", launch)
        for c in inner.winfo_children():
            c.bind("<Enter>", hi); c.bind("<Leave>", ho); c.bind("<Button-1>", launch)

    def _launch(self, name, script, card, color):
        path = os.path.join(SCRIPT_DIR, script)
        try:
            subprocess.Popen([PY, path])
            self.launched += 1
            card.config(highlightbackground=color, highlightthickness=2)
            self.footer.config(text=f"Launched: {name}", fg=color)
            self.root.after(800, lambda: card.config(highlightbackground=BORDER, highlightthickness=1))
            self.root.after(3000, lambda: self.footer.config(text=f"{self.launched} app(s) launched", fg=FG_DIM))
        except Exception as err:
            self.footer.config(text=f"Error: {err}", fg="#ff4444")

    def _launch_all(self):
        for name, color, script in APPS:
            try:
                subprocess.Popen([PY, os.path.join(SCRIPT_DIR, script)])
                self.launched += 1
            except Exception: pass
        self.footer.config(text=f"Launched {self.launched} apps", fg="#00aaff")


if __name__ == "__main__":
    SubZeroSuite()
