"""
Sub-Zero Flawless Victory
═══════════════════════════════
Click the desktop icon → QR splash screen → launches Sub-Zero.
Portable: can run from USB if Python is available.
"""
import tkinter as tk
import subprocess
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PY = r"C:\Python314\pythonw.exe"
QR_IMAGE = SCRIPT_DIR / "qr_code.png"
LOGO_IMAGE = SCRIPT_DIR / "logo.png"
SIDEBAR = SCRIPT_DIR / "sidebar_launcher.pyw"

# ── Colors ─────────────────────────────────────────────────────
BG = "#000000"
ACCENT = "#0066cc"
FG = "#e0e0e0"
FG_DIM = "#445577"
CYAN = "#03dac6"


class SplashScreen:
    """Splash screen with QR code that shows for 4 seconds before launching."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Sub-Zero Flawless Victory")
        self.root.overrideredirect(True)  # Frameless
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG)

        # Center on screen
        w, h = 420, 520
        sx = (self.root.winfo_screenwidth() - w) // 2
        sy = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{sx}+{sy}")

        # Rounded feel with border
        self.root.attributes("-alpha", 0.96)

        self._build()

        # Auto-close after 4 seconds and launch app
        self.root.after(4000, self._launch_and_close)

        # Click anywhere to skip splash
        self.root.bind("<Button-1>", lambda e: self._launch_and_close())
        self.root.bind("<Key>", lambda e: self._launch_and_close())

        self.root.mainloop()

    def _build(self):
        # Border frame
        border = tk.Frame(self.root, bg=ACCENT, padx=2, pady=2)
        border.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(border, bg=BG)
        inner.pack(fill=tk.BOTH, expand=True)

        # ── Top: Brand ──
        top = tk.Frame(inner, bg=BG)
        top.pack(fill=tk.X, pady=(20, 10))

        # Try to load logo
        self._logo_img = None
        try:
            from PIL import Image, ImageTk
            if LOGO_IMAGE.exists():
                img = Image.open(LOGO_IMAGE).resize((48, 48), Image.LANCZOS)
                self._logo_img = ImageTk.PhotoImage(img)
                tk.Label(top, image=self._logo_img, bg=BG).pack()
        except ImportError:
            pass

        if not self._logo_img:
            tk.Label(
                top, text="❄", bg=BG, fg=CYAN,
                font=("Segoe UI", 32),
            ).pack()

        tk.Label(
            inner, text="S U B - Z E R O", bg=BG, fg="white",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(0, 2))

        tk.Label(
            inner, text="F L A W L E S S   V I C T O R Y", bg=BG, fg=CYAN,
            font=("Segoe UI", 10, "bold"),
        ).pack(pady=(0, 2))

        tk.Label(
            inner, text="Autonomous AI Runtime", bg=BG, fg=FG_DIM,
            font=("Segoe UI", 9),
        ).pack()

        # ── Divider ──
        tk.Frame(inner, bg=ACCENT, height=2).pack(fill=tk.X, padx=40, pady=12)

        # ── QR Code ──
        self._qr_img = None
        try:
            from PIL import Image, ImageTk
            if QR_IMAGE.exists():
                img = Image.open(QR_IMAGE).resize((200, 200), Image.LANCZOS)
                self._qr_img = ImageTk.PhotoImage(img)
                tk.Label(inner, image=self._qr_img, bg=BG).pack(pady=(4, 8))
        except ImportError:
            pass

        if not self._qr_img:
            # Fallback: just show text
            tk.Label(
                inner, text="[QR Code]", bg=BG, fg=FG_DIM,
                font=("Consolas", 14),
            ).pack(pady=(4, 8))

        tk.Label(
            inner, text="Scan to Download", bg=BG, fg=ACCENT,
            font=("Segoe UI", 11, "bold"),
        ).pack()

        tk.Label(
            inner, text="Share Sub-Zero with anyone", bg=BG, fg=FG_DIM,
            font=("Segoe UI", 8),
        ).pack(pady=(2, 0))

        # ── Bottom: Version + skip ──
        bottom = tk.Frame(inner, bg=BG)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        tk.Label(
            bottom, text="v2.5  •  Click anywhere to skip", bg=BG, fg=FG_DIM,
            font=("Segoe UI", 8),
        ).pack()

        # Loading bar animation
        self.bar_canvas = tk.Canvas(
            inner, bg=BG, height=4, highlightthickness=0,
        )
        self.bar_canvas.pack(fill=tk.X, padx=40, pady=(12, 0))
        self._bar_width = 0
        self._animate_bar()

    def _animate_bar(self):
        """Animated loading bar."""
        self.bar_canvas.delete("all")
        canvas_w = self.bar_canvas.winfo_width() or 340
        self.bar_canvas.create_rectangle(
            0, 0, self._bar_width, 4,
            fill=ACCENT, outline="",
        )
        if self._bar_width < canvas_w:
            self._bar_width += canvas_w / 80  # ~4 seconds to fill
            self.root.after(50, self._animate_bar)

    def _launch_and_close(self):
        """Launch the main SubZero app and close splash."""
        if hasattr(self, "_launched"):
            return
        self._launched = True

        # Launch sidebar
        try:
            subprocess.Popen(
                [PY, str(SIDEBAR)],
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
        except Exception:
            # Fallback: try with sys.executable
            try:
                subprocess.Popen(
                    [sys.executable, str(SIDEBAR)],
                    creationflags=0x08000000,
                )
            except Exception:
                pass

        self.root.destroy()


if __name__ == "__main__":
    SplashScreen()
