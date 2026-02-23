"""
Warp Oz — SubZero AI Code Assistant
════════════════════════════════════
PyQt6 + QScintilla build.
• Session tabs (multiple conversations)
• Conversation history sidebar with search, ACTIVE/PAST
• QScintilla code editor with syntax highlighting
• Integrated terminal
• AI chat via Ollama
• Model selector, Ollama status indicator
• Code review, agent mode, TODO system
• Layer management system
"""
import sys
import os
import json
import subprocess
import threading
import shutil
import re
import uuid
import urllib.request
from pathlib import Path
from datetime import datetime
from functools import partial
from sz_runtime import ToolRuntime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTextEdit, QLabel, QPushButton, QLineEdit, QFrame,
    QScrollArea, QTabBar, QComboBox, QMenu, QDialog, QFileDialog,
    QMessageBox, QPlainTextEdit, QToolBar, QStatusBar, QSizePolicy,
    QTabWidget, QInputDialog, QWidgetAction
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, QSize, QEvent, QObject
)
from PyQt6.QtGui import (
    QFont, QColor, QAction, QKeySequence, QTextCursor, QIcon,
    QTextCharFormat, QPalette, QShortcut
)

try:
    from PyQt6.Qsci import QsciScintilla, QsciLexerPython, QsciLexerJavaScript, QsciLexerJSON
    HAS_QSCI = True
except ImportError:
    HAS_QSCI = False

# ── Colors ────────────────────────────────────────────────────────
BG_MAIN      = "#0a0a12"
BG_SIDEBAR   = "#08080f"
BG_EDITOR    = "#0c0c16"
BG_TERMINAL  = "#07070e"
BG_INPUT     = "#10101c"
BG_TAB_BAR   = "#08080f"
BG_TAB_ACTIVE = "#14142a"
BG_TAB_HOVER = "#0f0f22"
BG_CARD      = "#0e0e1a"
BG_CARD_HOVER = "#14142a"
BG_BUTTON    = "#14142a"
BG_STATUS    = "#06060c"
BG_HEADER    = "#0a0a12"

FG_PRIMARY   = "#c8c8d0"
FG_DIM       = "#55556a"
FG_ACCENT    = "#03dac6"
FG_USER      = "#bb86fc"
FG_AI        = "#00e676"
FG_ERROR     = "#ef5350"
FG_WARNING   = "#ffab00"
FG_REVIEW    = "#e040fb"
FG_BLUE      = "#448aff"

ACCENT       = "#03dac6"
BORDER       = "#1a1a2e"
DIVIDER      = "#12121e"

# ── Paths ─────────────────────────────────────────────────────────
HOME_DIR     = Path.home() / ".subzero" / "warpoz"
LAYERS_DIR   = HOME_DIR / "layers"
HISTORY_FILE = HOME_DIR / "history.json"
WORKFLOWS_FILE = HOME_DIR / "workflows.json"
TODO_FILE    = HOME_DIR / "todos.json"
MEMORY_FILE  = HOME_DIR / "memory.json"

MODELS = ["llama3.2", "qwen2.5:1.5b", "codellama", "deepseek-coder", "mistral"]
DEFAULT_MODEL = "qwen2.5:1.5b"
OLLAMA_URL = "http://localhost:11434"

SUMMARY_THRESHOLD = 20


# ── Global Stylesheet ─────────────────────────────────────────────
STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_MAIN};
    color: {FG_PRIMARY};
    font-family: 'Segoe UI', sans-serif;
    font-size: 10pt;
}}
QSplitter::handle {{
    background-color: {DIVIDER};
    width: 2px;
    height: 2px;
}}
QScrollBar:vertical {{
    background: {BG_MAIN};
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {BG_MAIN};
    height: 8px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QLineEdit {{
    background-color: {BG_INPUT};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    font-family: 'Consolas', monospace;
}}
QLineEdit:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox {{
    background-color: {BG_INPUT};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 2px 8px;
    min-width: 120px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    color: {FG_PRIMARY};
    selection-background-color: {BG_TAB_ACTIVE};
    border: 1px solid {BORDER};
}}
QPushButton {{
    background-color: {BG_BUTTON};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 9pt;
}}
QPushButton:hover {{
    background-color: {BG_TAB_HOVER};
    border-color: {ACCENT};
}}
QPushButton:pressed {{
    background-color: {BG_TAB_ACTIVE};
}}
QMenu {{
    background-color: {BG_CARD};
    color: {FG_PRIMARY};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item:selected {{
    background-color: {BG_TAB_ACTIVE};
}}
QTabBar {{
    background-color: {BG_TAB_BAR};
    border: none;
}}
QTabBar::tab {{
    background-color: {BG_TAB_BAR};
    color: {FG_DIM};
    padding: 6px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 9pt;
}}
QTabBar::tab:selected {{
    color: {FG_PRIMARY};
    background-color: {BG_TAB_ACTIVE};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover {{
    background-color: {BG_TAB_HOVER};
    color: {FG_PRIMARY};
}}
QTextEdit, QPlainTextEdit {{
    background-color: {BG_TERMINAL};
    color: {FG_PRIMARY};
    border: none;
    font-family: 'Consolas', monospace;
    font-size: 10pt;
    selection-background-color: {BG_TAB_ACTIVE};
}}
QStatusBar {{
    background-color: {BG_STATUS};
    color: {FG_DIM};
    font-size: 8pt;
    border-top: 1px solid {BORDER};
}}
"""


# ══════════════════════════════════════════════════════════════════
#  Data Classes
# ══════════════════════════════════════════════════════════════════

class Session:
    """A conversation session."""
    def __init__(self, sid=None, name="New conversation"):
        self.id = sid or str(uuid.uuid4())[:8]
        self.name = name
        self.messages = []       # list of {"role","content","timestamp"}
        self.created = datetime.now().isoformat()
        self.active = True
        self.summary = ""

    def add_message(self, role, content):
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        # Auto-name from first user message
        if role == "user" and len(self.messages) == 1:
            self.name = content[:40].strip()
            if len(content) > 40:
                self.name += "..."

    def to_dict(self):
        return {
            "id": self.id, "name": self.name,
            "messages": self.messages[-50:],
            "created": self.created,
            "active": self.active,
            "summary": self.summary,
        }

    @staticmethod
    def from_dict(d):
        s = Session(sid=d.get("id"), name=d.get("name", "Untitled"))
        s.messages = d.get("messages", [])
        s.created = d.get("created", "")
        s.active = d.get("active", False)
        s.summary = d.get("summary", "")
        return s


class LayerManager:
    """Manages layers and their versions on disk."""
    def __init__(self):
        LAYERS_DIR.mkdir(parents=True, exist_ok=True)

    def list_layers(self):
        if not LAYERS_DIR.exists():
            return []
        return sorted([
            d.name for d in LAYERS_DIR.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ])

    def list_versions(self, layer_name):
        layer_dir = LAYERS_DIR / layer_name
        if not layer_dir.exists():
            return []
        return sorted([
            d.name for d in layer_dir.iterdir()
            if d.is_dir() and d.name.startswith("v")
        ], key=lambda v: int(v[1:]) if v[1:].isdigit() else 0)

    def create_layer(self, name):
        layer_dir = LAYERS_DIR / name
        if layer_dir.exists():
            return False, "Layer already exists"
        v1_dir = layer_dir / "v1"
        v1_dir.mkdir(parents=True)
        (v1_dir / "main.py").write_text(
            f'# Layer: {name} — v1\n'
            f'# Created: {datetime.now().strftime("%Y-%m-%d %H:%M")}\n\n'
            f'def handler(event, context):\n'
            f'    """Main entry point for {name}."""\n'
            f'    return {{"status": "ok", "layer": "{name}"}}\n',
            encoding="utf-8",
        )
        (v1_dir / "requirements.txt").write_text(
            f"# Dependencies for {name}\n", encoding="utf-8"
        )
        manifest = {
            "name": name, "version": "v1",
            "created": datetime.now().isoformat(),
            "description": "", "runtime": "python3",
        }
        (v1_dir / "layer.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        return True, "v1"

    def create_version(self, layer_name):
        versions = self.list_versions(layer_name)
        if not versions:
            return False, "No versions exist"
        latest = versions[-1]
        next_num = int(latest[1:]) + 1 if latest[1:].isdigit() else len(versions) + 1
        new_ver = f"v{next_num}"
        src = LAYERS_DIR / layer_name / latest
        dst = LAYERS_DIR / layer_name / new_ver
        shutil.copytree(src, dst)
        manifest_path = dst / "layer.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["version"] = new_ver
            manifest["created"] = datetime.now().isoformat()
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return True, new_ver

    def delete_layer(self, name):
        layer_dir = LAYERS_DIR / name
        if layer_dir.exists():
            shutil.rmtree(layer_dir)
            return True
        return False

    def get_files(self, layer_name, version):
        ver_dir = LAYERS_DIR / layer_name / version
        if not ver_dir.exists():
            return []
        return sorted([f.name for f in ver_dir.iterdir() if f.is_file()])

    def read_file(self, layer_name, version, filename):
        path = LAYERS_DIR / layer_name / version / filename
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")
        return ""

    def write_file(self, layer_name, version, filename, content):
        path = LAYERS_DIR / layer_name / version / filename
        path.write_text(content, encoding="utf-8")

    def get_file_path(self, layer_name, version, filename):
        return LAYERS_DIR / layer_name / version / filename


# ══════════════════════════════════════════════════════════════════
#  Ollama Agent
# ══════════════════════════════════════════════════════════════════

class OllamaAgent:
    """Handles Ollama communication."""
    def __init__(self):
        self.model = DEFAULT_MODEL
        self.conversation = []
        self._load_memory()

    def _load_memory(self):
        try:
            if MEMORY_FILE.exists():
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    self.conversation = json.load(f)
        except Exception:
            self.conversation = []

    def save_memory(self):
        try:
            MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.conversation[-50:], f, indent=2, default=str)
        except Exception:
            pass

    def is_ollama_running(self):
        try:
            req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    def call_api(self, prompt, model=None):
        """Call Ollama REST API. Returns (response, error)."""
        try:
            payload = json.dumps({
                "model": model or self.model,
                "prompt": prompt,
                "stream": False,
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = data.get("response", "").strip()
            if text:
                return text, None
            return None, "Empty response from Ollama API"
        except urllib.error.URLError as e:
            return None, f"Cannot connect to Ollama: {e.reason}"
        except TimeoutError:
            return None, "Ollama timed out (3 min)"
        except Exception as e:
            return None, f"Ollama error: {e}"

    def call_cli(self, prompt, model=None):
        """Fallback: call Ollama via CLI."""
        import tempfile
        try:
            tmp = tempfile.NamedTemporaryFile(
                mode='w', suffix='.txt', delete=False, encoding='utf-8'
            )
            tmp.write(prompt)
            tmp.close()
            try:
                m = model or self.model
                cmd = f'type "{tmp.name}" | ollama run {m}'
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True,
                    timeout=120, encoding="utf-8", errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip(), None
                err = result.stderr.strip() or "No output from ollama CLI"
                return None, f"CLI: {err}"
            finally:
                os.unlink(tmp.name)
        except FileNotFoundError:
            return None, "Ollama not found. Install from https://ollama.com"
        except subprocess.TimeoutExpired:
            return None, "CLI timed out (2 min)"
        except Exception as e:
            return None, f"CLI error: {e}"


# ══════════════════════════════════════════════════════════════════
#  Worker Thread for AI calls
# ══════════════════════════════════════════════════════════════════

class AIWorker(QThread):
    """Background thread for Ollama calls."""
    finished = pyqtSignal(str, str)  # response, error

    def __init__(self, agent, prompt, model=None):
        super().__init__()
        self.agent = agent
        self.prompt = prompt
        self.model = model

    def run(self):
        response, error = self.agent.call_api(self.prompt, self.model)
        if response is None:
            short = self.prompt[-4000:]
            response, error = self.agent.call_cli(short, self.model)
        self.finished.emit(response or "", error or "")


# ══════════════════════════════════════════════════════════════════
#  Ollama Status Checker
# ══════════════════════════════════════════════════════════════════

class OllamaStatusChecker(QThread):
    status_changed = pyqtSignal(bool)

    def __init__(self, agent):
        super().__init__()
        self.agent = agent
        self._running = True

    def run(self):
        while self._running:
            online = self.agent.is_ollama_running()
            self.status_changed.emit(online)
            self.sleep(10)

    def stop(self):
        self._running = False


# ══════════════════════════════════════════════════════════════════
#  Code Editor (QScintilla)
# ══════════════════════════════════════════════════════════════════

def create_editor(parent=None):
    """Create a QScintilla editor or fallback QPlainTextEdit."""
    if HAS_QSCI:
        editor = QsciScintilla(parent)
        # Font
        font = QFont("Consolas", 11)
        editor.setFont(font)
        editor.setMarginsFont(font)

        # Line numbers
        editor.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
        editor.setMarginWidth(0, "00000")
        editor.setMarginsForegroundColor(QColor(FG_DIM))
        editor.setMarginsBackgroundColor(QColor(BG_SIDEBAR))

        # Colors
        editor.setPaper(QColor(BG_EDITOR))
        editor.setColor(QColor(FG_PRIMARY))
        editor.setCaretForegroundColor(QColor(ACCENT))
        editor.setCaretLineVisible(True)
        editor.setCaretLineBackgroundColor(QColor(BG_TAB_ACTIVE))
        editor.setSelectionBackgroundColor(QColor("#1a1a3e"))
        editor.setSelectionForegroundColor(QColor(FG_PRIMARY))
        editor.setIndentationGuides(True)
        editor.setIndentationGuidesForegroundColor(QColor(BORDER))
        editor.setTabWidth(4)
        editor.setAutoIndent(True)
        editor.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        editor.setMatchedBraceForegroundColor(QColor(ACCENT))
        editor.setMatchedBraceBackgroundColor(QColor(BG_TAB_ACTIVE))
        editor.setFolding(QsciScintilla.FoldStyle.BoxedTreeFoldStyle)
        editor.setFoldMarginColors(QColor(BG_SIDEBAR), QColor(BG_SIDEBAR))

        # Default Python lexer
        lexer = QsciLexerPython(editor)
        lexer.setFont(font)
        lexer.setDefaultPaper(QColor(BG_EDITOR))
        lexer.setDefaultColor(QColor(FG_PRIMARY))
        lexer.setColor(QColor("#66bbff"), QsciLexerPython.Keyword)
        lexer.setColor(QColor("#88ccff"), QsciLexerPython.DoubleQuotedString)
        lexer.setColor(QColor("#88ccff"), QsciLexerPython.SingleQuotedString)
        lexer.setColor(QColor("#88ccff"), QsciLexerPython.TripleSingleQuotedString)
        lexer.setColor(QColor("#88ccff"), QsciLexerPython.TripleDoubleQuotedString)
        lexer.setColor(QColor("#2a5070"), QsciLexerPython.Comment)
        lexer.setColor(QColor("#2a5070"), QsciLexerPython.CommentBlock)
        lexer.setColor(QColor("#44aaff"), QsciLexerPython.Number)
        lexer.setColor(QColor("#55ccff"), QsciLexerPython.FunctionMethodName)
        lexer.setColor(QColor("#55ccff"), QsciLexerPython.ClassName)
        lexer.setColor(QColor("#55aaff"), QsciLexerPython.Decorator)
        for i in range(20):
            lexer.setPaper(QColor(BG_EDITOR), i)
        editor.setLexer(lexer)
        editor._lexer = lexer
        return editor
    else:
        # Fallback plain text editor
        editor = QPlainTextEdit(parent)
        editor.setFont(QFont("Consolas", 11))
        editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {BG_EDITOR};
                color: {FG_PRIMARY};
                border: none;
                selection-background-color: #1a1a3e;
            }}
        """)
        return editor


# ══════════════════════════════════════════════════════════════════
#  History Manager
# ══════════════════════════════════════════════════════════════════

class HistoryManager:
    """Persists session history to disk."""
    def __init__(self):
        HOME_DIR.mkdir(parents=True, exist_ok=True)

    def load_sessions(self):
        try:
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return [Session.from_dict(d) for d in data]
        except Exception:
            pass
        return []

    def save_sessions(self, sessions):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([s.to_dict() for s in sessions], f, indent=2, default=str)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════
#  Main Window
# ══════════════════════════════════════════════════════════════════

class WarpOzWindow(QMainWindow):
    append_terminal = pyqtSignal(str, str)  # text, color

    def __init__(self):
        super().__init__()
        self.setWindowTitle("\u2744 WARP OZ \u2014 SubZero AI Code Assistant")
        self.setMinimumSize(900, 600)
        self.resize(1200, 800)
        self.setWindowOpacity(0.95)

        # Data
        self.layers = LayerManager()
        self.agent = OllamaAgent()
        self.history_mgr = HistoryManager()
        self.sessions = self.history_mgr.load_sessions()
        self.current_session_idx = -1
        self.current_layer = None
        self.current_version = None
        self.current_file = None
        self.open_tabs = []         # (layer, version, filename)
        self.active_tab_idx = -1
        self.ai_busy = False
        self.ai_visible = True
        self.ai_responses = []
        self.agent_mode = True
        self.cmd_history = []
        self.cmd_history_idx = None
        self.ollama_online = False
        self._worker = None
        self._todos = []
        self._todo_counter = 0
        self._conversation_summary = ""
        self._tool_runtime = ToolRuntime()

        # Ensure at least one session
        if not self.sessions:
            self._create_new_session(switch=False)

        self._load_todos()
        self._build_ui()
        self._apply_stylesheet()
        self._start_status_checker()

        # Connect cross-thread signal
        self.append_terminal.connect(self._do_append_terminal)

        # Select first active session
        active = [i for i, s in enumerate(self.sessions) if s.active]
        if active:
            self._switch_session(active[0])
        elif self.sessions:
            self._switch_session(0)

        self._refresh_sidebar()
        self._term_print("\u2744 Warp Oz ready.\n", FG_ACCENT)
        self._term_print(f"[Model] {self.agent.model} | Memory: {len(self.agent.conversation)} msgs\n", FG_DIM)
        self._term_print(f"[Agent] {'\u26A1 ON' if self.agent_mode else 'OFF'}\n", FG_AI)

    # ── Stylesheet ────────────────────────────────────────────────

    def _apply_stylesheet(self):
        self.setStyleSheet(STYLESHEET)

    # ── UI Construction ───────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Header bar ──
        self._build_header(main_layout)

        # ── Session tabs ──
        self._build_session_tabs(main_layout)

        # ── Main content (sidebar + editor/terminal) ──
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(2)
        main_layout.addWidget(self.main_splitter, 1)

        # Left sidebar
        self._build_sidebar()

        # Right content (editor + terminal vertical split)
        self._build_content()

        self.main_splitter.setSizes([240, 960])

        # ── Action bar ──
        self._build_action_bar(main_layout)

        # ── Input bar ──
        self._build_input_bar(main_layout)

        # ── Status bar / footer ──
        self._build_footer()

        # ── Keyboard shortcuts ──
        self._setup_shortcuts()

    # ── Header ────────────────────────────────────────────────────

    def _build_header(self, layout):
        header = QFrame()
        header.setFixedHeight(38)
        header.setStyleSheet(f"background-color: {BG_HEADER}; border-bottom: 1px solid {BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 0, 12, 0)
        hl.setSpacing(8)

        title = QLabel("\u2744 WARP OZ")
        title.setStyleSheet(f"color: {ACCENT}; font-size: 12pt; font-weight: bold;")
        hl.addWidget(title)

        subtitle = QLabel("AI CODE ASSISTANT")
        subtitle.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; letter-spacing: 2px;")
        hl.addWidget(subtitle)

        hl.addStretch()

        # Code review button
        self.review_btn = QPushButton("\u2B21 Code Review")
        self.review_btn.setStyleSheet(f"""
            QPushButton {{
                color: {FG_REVIEW}; background: {BG_BUTTON};
                border: 1px solid {FG_REVIEW}; border-radius: 4px;
                padding: 3px 10px; font-size: 9pt;
            }}
            QPushButton:hover {{ background: #1a0a2a; }}
        """)
        self.review_btn.clicked.connect(self._code_review)
        hl.addWidget(self.review_btn)

        # New layer button
        new_layer_btn = QPushButton("+ New Layer")
        new_layer_btn.setStyleSheet(f"color: {ACCENT};")
        new_layer_btn.clicked.connect(self._new_layer_dialog)
        hl.addWidget(new_layer_btn)

        # Run button
        run_btn = QPushButton("Run \u25B6")
        run_btn.setStyleSheet(f"color: {FG_AI}; font-weight: bold;")
        run_btn.clicked.connect(self._run_current)
        hl.addWidget(run_btn)

        layout.addWidget(header)

    # ── Session Tabs ──────────────────────────────────────────────

    def _build_session_tabs(self, layout):
        tab_bar_frame = QFrame()
        tab_bar_frame.setFixedHeight(32)
        tab_bar_frame.setStyleSheet(f"background-color: {BG_TAB_BAR}; border-bottom: 1px solid {BORDER};")
        tl = QHBoxLayout(tab_bar_frame)
        tl.setContentsMargins(8, 0, 8, 0)
        tl.setSpacing(0)

        self.session_tab_bar = QTabBar()
        self.session_tab_bar.setExpanding(False)
        self.session_tab_bar.setTabsClosable(True)
        self.session_tab_bar.setMovable(True)
        self.session_tab_bar.currentChanged.connect(self._on_session_tab_changed)
        self.session_tab_bar.tabCloseRequested.connect(self._close_session_tab)
        tl.addWidget(self.session_tab_bar, 1)

        add_btn = QPushButton("+")
        add_btn.setFixedSize(28, 24)
        add_btn.setStyleSheet(f"color: {ACCENT}; font-size: 14pt; border: none;")
        add_btn.setToolTip("New conversation")
        add_btn.clicked.connect(lambda: self._create_new_session(switch=True))
        tl.addWidget(add_btn)

        layout.addWidget(tab_bar_frame)
        self._rebuild_session_tabs()

    def _rebuild_session_tabs(self):
        self.session_tab_bar.blockSignals(True)
        while self.session_tab_bar.count():
            self.session_tab_bar.removeTab(0)
        for s in self.sessions:
            if s.active:
                idx = self.session_tab_bar.addTab(s.name[:30])
                self.session_tab_bar.setTabToolTip(idx, s.name)
        if 0 <= self.current_session_idx < len(self.sessions):
            active_sessions = [i for i, s in enumerate(self.sessions) if s.active]
            try:
                tab_idx = active_sessions.index(self.current_session_idx)
                self.session_tab_bar.setCurrentIndex(tab_idx)
            except ValueError:
                pass
        self.session_tab_bar.blockSignals(False)

    def _on_session_tab_changed(self, idx):
        if idx >= 0:
            active_sessions = [i for i, s in enumerate(self.sessions) if s.active]
            if idx < len(active_sessions):
                self._switch_session(active_sessions[idx])

    def _close_session_tab(self, tab_idx):
        active_sessions = [i for i, s in enumerate(self.sessions) if s.active]
        if tab_idx < len(active_sessions):
            si = active_sessions[tab_idx]
            self.sessions[si].active = False
            self.history_mgr.save_sessions(self.sessions)
            self._rebuild_session_tabs()
            self._refresh_sidebar()
            # Switch to another active session
            remaining = [i for i, s in enumerate(self.sessions) if s.active]
            if remaining:
                self._switch_session(remaining[0])
            else:
                self._create_new_session(switch=True)

    def _create_new_session(self, switch=True):
        s = Session()
        self.sessions.append(s)
        self.history_mgr.save_sessions(self.sessions)
        self._rebuild_session_tabs()
        if hasattr(self, 'sidebar_search'):
            self._refresh_sidebar()
        if switch:
            self._switch_session(len(self.sessions) - 1)

    def _switch_session(self, session_idx):
        if session_idx < 0 or session_idx >= len(self.sessions):
            return
        self.current_session_idx = session_idx
        s = self.sessions[session_idx]
        # Update tab bar
        active_sessions = [i for i, sess in enumerate(self.sessions) if sess.active]
        try:
            tab_idx = active_sessions.index(session_idx)
            self.session_tab_bar.blockSignals(True)
            self.session_tab_bar.setCurrentIndex(tab_idx)
            self.session_tab_bar.blockSignals(False)
        except ValueError:
            pass

    # ── Sidebar ───────────────────────────────────────────────────

    def _build_sidebar(self):
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setMinimumWidth(200)
        self.sidebar_widget.setMaximumWidth(350)
        sl = QVBoxLayout(self.sidebar_widget)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)

        # Brand header
        brand = QFrame()
        brand.setFixedHeight(40)
        brand.setStyleSheet(f"background-color: {BG_SIDEBAR}; border-bottom: 1px solid {BORDER};")
        bl = QHBoxLayout(brand)
        bl.setContentsMargins(12, 0, 12, 0)
        lbl = QLabel("\u2726 SubZero")
        lbl.setStyleSheet(f"color: {ACCENT}; font-weight: bold; font-size: 11pt;")
        bl.addWidget(lbl)
        bl.addStretch()
        warp_lbl = QLabel("Warp Oz")
        warp_lbl.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt;")
        bl.addWidget(warp_lbl)
        sl.addWidget(brand)

        # New conversation button
        new_conv_btn = QPushButton("+ New conversation")
        new_conv_btn.setStyleSheet(f"""
            QPushButton {{
                color: {ACCENT}; background: {BG_BUTTON};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 6px; margin: 8px 10px 4px 10px; font-size: 9pt;
            }}
            QPushButton:hover {{ background: {BG_TAB_HOVER}; border-color: {ACCENT}; }}
        """)
        new_conv_btn.clicked.connect(lambda: self._create_new_session(switch=True))
        sl.addWidget(new_conv_btn)

        # Search
        self.sidebar_search = QLineEdit()
        self.sidebar_search.setPlaceholderText("\U0001f50d Search...")
        self.sidebar_search.setStyleSheet(f"""
            QLineEdit {{
                margin: 4px 10px; padding: 5px 8px;
                background: {BG_INPUT}; color: {FG_PRIMARY};
                border: 1px solid {BORDER}; border-radius: 4px;
            }}
        """)
        self.sidebar_search.textChanged.connect(self._refresh_sidebar)
        sl.addWidget(self.sidebar_search)

        # Scrollable area for sessions + layers
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG_SIDEBAR}; }}")
        self.sidebar_list = QWidget()
        self.sidebar_list.setStyleSheet(f"background: {BG_SIDEBAR};")
        self.sidebar_list_layout = QVBoxLayout(self.sidebar_list)
        self.sidebar_list_layout.setContentsMargins(8, 4, 8, 4)
        self.sidebar_list_layout.setSpacing(2)
        self.sidebar_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.sidebar_list)
        sl.addWidget(scroll, 1)

        self.main_splitter.addWidget(self.sidebar_widget)

    def _refresh_sidebar(self):
        # Clear
        while self.sidebar_list_layout.count():
            item = self.sidebar_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        query = self.sidebar_search.text().lower().strip()

        # ACTIVE sessions
        active_sessions = [s for s in self.sessions if s.active]
        if active_sessions:
            hdr = QLabel("ACTIVE")
            hdr.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; font-weight: bold; padding: 6px 4px 2px 4px;")
            self.sidebar_list_layout.addWidget(hdr)
            for s in active_sessions:
                if query and query not in s.name.lower():
                    continue
                self._add_session_card(s, active=True)

        # PAST sessions
        past_sessions = [s for s in self.sessions if not s.active]
        if past_sessions:
            hdr = QLabel("PAST")
            hdr.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; font-weight: bold; padding: 10px 4px 2px 4px;")
            self.sidebar_list_layout.addWidget(hdr)
            for s in past_sessions:
                if query and query not in s.name.lower():
                    continue
                self._add_session_card(s, active=False)

        # LAYERS section
        all_layers = self.layers.list_layers()
        if query:
            all_layers = [l for l in all_layers if query in l.lower()]

        hdr = QLabel(f"LAYERS ({len(all_layers)})")
        hdr.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; font-weight: bold; padding: 10px 4px 2px 4px;")
        self.sidebar_list_layout.addWidget(hdr)

        if not all_layers:
            empty = QLabel("No layers yet.\nClick '+ New Layer' to create one.")
            empty.setStyleSheet(f"color: {FG_DIM}; font-size: 9pt; padding: 8px;")
            self.sidebar_list_layout.addWidget(empty)
        else:
            for layer_name in all_layers:
                self._add_layer_card(layer_name)

        self.sidebar_list_layout.addStretch()

    def _add_session_card(self, session, active=True):
        card = QPushButton()
        name = session.name[:35]
        msgs = len(session.messages)
        card.setText(f"{'\U0001f4ac' if active else '\U0001f4c1'}  {name}")
        card.setToolTip(f"{session.name}\n{msgs} messages\nCreated: {session.created[:16]}")
        is_current = (self.sessions.index(session) == self.current_session_idx)
        bg = BG_TAB_ACTIVE if is_current else BG_CARD
        accent = ACCENT if is_current else FG_DIM
        card.setStyleSheet(f"""
            QPushButton {{
                text-align: left; padding: 6px 8px;
                background: {bg}; color: {FG_PRIMARY};
                border: none; border-left: 2px solid {accent};
                border-radius: 0; font-size: 9pt;
            }}
            QPushButton:hover {{ background: {BG_CARD_HOVER}; }}
        """)
        card.clicked.connect(lambda checked=False, s=session: self._on_session_card_clicked(s))
        self.sidebar_list_layout.addWidget(card)

    def _on_session_card_clicked(self, session):
        idx = self.sessions.index(session)
        if not session.active:
            session.active = True
            self.history_mgr.save_sessions(self.sessions)
            self._rebuild_session_tabs()
        self._switch_session(idx)
        self._refresh_sidebar()

    def _add_layer_card(self, layer_name):
        versions = self.layers.list_versions(layer_name)
        latest = versions[-1] if versions else "\u2014"
        is_active = (layer_name == self.current_layer)

        card = QPushButton()
        card.setText(f"{'\u25CF' if is_active else '\u25CB'}  {layer_name}  ({latest}, {len(versions)} ver)")
        bg = BG_TAB_ACTIVE if is_active else BG_CARD
        card.setStyleSheet(f"""
            QPushButton {{
                text-align: left; padding: 6px 8px;
                background: {bg}; color: {FG_PRIMARY};
                border: none; border-radius: 4px; font-size: 9pt;
            }}
            QPushButton:hover {{ background: {BG_CARD_HOVER}; }}
        """)
        card.clicked.connect(lambda checked=False, n=layer_name: self._select_layer(n))
        card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        card.customContextMenuRequested.connect(
            lambda pos, n=layer_name, btn=card: self._layer_context_menu(n, btn, pos)
        )
        self.sidebar_list_layout.addWidget(card)

    def _layer_context_menu(self, layer_name, widget, pos):
        menu = QMenu(self)
        menu.addAction("New Version", lambda: self._new_version(layer_name))
        menu.addAction("New File", lambda: self._new_file_dialog(layer_name))
        menu.addSeparator()
        menu.addAction("Delete Layer", lambda: self._delete_layer(layer_name))
        menu.exec(widget.mapToGlobal(pos))

    def _select_layer(self, name):
        self.current_layer = name
        versions = self.layers.list_versions(name)
        if versions:
            self.current_version = versions[-1]
            files = self.layers.get_files(name, self.current_version)
            if files:
                self._open_file(name, self.current_version, files[0])
        self._refresh_sidebar()
        self._update_version_bar()
        self._term_print(f"Selected layer: {name} ({self.current_version})\n", FG_ACCENT)

    # ── Right Content ─────────────────────────────────────────────

    def _build_content(self):
        self.content_widget = QWidget()
        cl = QVBoxLayout(self.content_widget)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # Version / file selector bar
        self._build_version_bar(cl)

        # Vertical split: editor on top, terminal on bottom
        self.editor_splitter = QSplitter(Qt.Orientation.Vertical)
        self.editor_splitter.setHandleWidth(2)

        # Editor
        self.editor = create_editor()
        self.editor_splitter.addWidget(self.editor)

        # Terminal
        self._build_terminal_widget()
        self.editor_splitter.addWidget(self.terminal_frame)

        self.editor_splitter.setSizes([500, 250])
        cl.addWidget(self.editor_splitter, 1)

        self.main_splitter.addWidget(self.content_widget)

    def _build_version_bar(self, layout):
        self.version_bar = QFrame()
        self.version_bar.setFixedHeight(30)
        self.version_bar.setStyleSheet(f"background-color: {BG_TAB_BAR}; border-bottom: 1px solid {BORDER};")
        vl = QHBoxLayout(self.version_bar)
        vl.setContentsMargins(8, 0, 8, 0)
        vl.setSpacing(4)

        self.version_label = QLabel("No layer selected")
        self.version_label.setStyleSheet(f"color: {FG_DIM}; font-size: 9pt;")
        vl.addWidget(self.version_label)

        self.version_buttons_widget = QWidget()
        self.version_buttons_layout = QHBoxLayout(self.version_buttons_widget)
        self.version_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.version_buttons_layout.setSpacing(2)
        vl.addWidget(self.version_buttons_widget, 1)

        vl.addStretch()

        new_file_btn = QPushButton("+ File")
        new_file_btn.setStyleSheet(f"color: {FG_WARNING}; font-size: 8pt; padding: 2px 6px;")
        new_file_btn.clicked.connect(self._new_file_current)
        vl.addWidget(new_file_btn)

        new_ver_btn = QPushButton("+ Version")
        new_ver_btn.setStyleSheet(f"color: {FG_USER}; font-size: 8pt; padding: 2px 6px;")
        new_ver_btn.clicked.connect(self._new_version_current)
        vl.addWidget(new_ver_btn)

        layout.addWidget(self.version_bar)

    def _update_version_bar(self):
        # Clear old buttons
        while self.version_buttons_layout.count():
            item = self.version_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.current_layer:
            self.version_label.setText("No layer selected")
            return

        self.version_label.setText(f"{self.current_layer} \u203A")
        versions = self.layers.list_versions(self.current_layer)
        files = self.layers.get_files(self.current_layer, self.current_version) if self.current_version else []

        for ver in versions:
            is_active = (ver == self.current_version)
            btn = QPushButton(ver)
            bg = ACCENT if is_active else BG_BUTTON
            fg = "#000000" if is_active else FG_DIM
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {bg}; color: {fg};
                    border-radius: 3px; padding: 1px 8px; font-size: 8pt;
                    {'font-weight: bold;' if is_active else ''}
                }}
            """)
            btn.clicked.connect(lambda checked=False, v=ver: self._switch_version(v))
            self.version_buttons_layout.addWidget(btn)

        if files:
            sep = QLabel("\u2502")
            sep.setStyleSheet(f"color: {FG_DIM}; font-size: 9pt;")
            self.version_buttons_layout.addWidget(sep)
            for fname in files:
                is_open = (fname == self.current_file)
                btn = QPushButton(fname)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {BG_TAB_ACTIVE if is_open else BG_BUTTON};
                        color: {ACCENT if is_open else FG_DIM};
                        border-radius: 3px; padding: 1px 6px; font-size: 8pt;
                    }}
                """)
                btn.clicked.connect(
                    lambda checked=False, f=fname: self._open_file(
                        self.current_layer, self.current_version, f)
                )
                self.version_buttons_layout.addWidget(btn)

        self.version_buttons_layout.addStretch()

    # ── Terminal Widget ───────────────────────────────────────────

    def _build_terminal_widget(self):
        self.terminal_frame = QFrame()
        tl = QVBoxLayout(self.terminal_frame)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)

        # Terminal header
        term_hdr = QFrame()
        term_hdr.setFixedHeight(26)
        term_hdr.setStyleSheet(f"background: {BG_TERMINAL}; border-top: 1px solid {BORDER};")
        thl = QHBoxLayout(term_hdr)
        thl.setContentsMargins(8, 0, 8, 0)
        lbl = QLabel("TERMINAL")
        lbl.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; font-weight: bold;")
        thl.addWidget(lbl)
        thl.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; border: none; padding: 2px 6px;")
        clear_btn.clicked.connect(self._clear_terminal)
        thl.addWidget(clear_btn)
        tl.addWidget(term_hdr)

        # Terminal output
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFont(QFont("Consolas", 10))
        self.terminal.setStyleSheet(f"""
            QTextEdit {{
                background-color: {BG_TERMINAL};
                color: {FG_PRIMARY};
                border: none;
                padding: 4px 8px;
            }}
        """)
        tl.addWidget(self.terminal, 1)

    def _term_print(self, text, color=None):
        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color or FG_PRIMARY))
        fmt.setFont(QFont("Consolas", 10))
        cursor.insertText(text, fmt)
        self.terminal.setTextCursor(cursor)
        self.terminal.ensureCursorVisible()

    def _do_append_terminal(self, text, color):
        self._term_print(text, color or FG_PRIMARY)

    def _clear_terminal(self):
        self.terminal.clear()

    # ── Action Bar ────────────────────────────────────────────────

    def _build_action_bar(self, layout):
        bar = QFrame()
        bar.setFixedHeight(30)
        bar.setStyleSheet(f"background-color: {BG_STATUS}; border-top: 1px solid {BORDER};")
        al = QHBoxLayout(bar)
        al.setContentsMargins(8, 0, 8, 0)
        al.setSpacing(4)

        self.hide_btn = QPushButton("Hide responses  Ctrl+G")
        self.hide_btn.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; border: none; padding: 2px 8px;")
        self.hide_btn.clicked.connect(self._toggle_ai_responses)
        al.addWidget(self.hide_btn)

        takeover_btn = QPushButton("Take over  Ctrl+I")
        takeover_btn.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; border: none; padding: 2px 8px;")
        takeover_btn.clicked.connect(self._take_over)
        al.addWidget(takeover_btn)

        self.agent_btn = QPushButton("\u26A1 Agent")
        self.agent_btn.setStyleSheet(f"color: {FG_AI}; font-size: 8pt; font-weight: bold; border: none; padding: 2px 8px;")
        self.agent_btn.clicked.connect(self._toggle_agent_mode)
        al.addWidget(self.agent_btn)

        al.addStretch()

        self.stop_btn = QPushButton("\u25A0 Stop")
        self.stop_btn.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; border: none; padding: 2px 8px;")
        self.stop_btn.clicked.connect(self._ai_stop)
        al.addWidget(self.stop_btn)

        layout.addWidget(bar)

    # ── Input Bar ─────────────────────────────────────────────────

    def _build_input_bar(self, layout):
        self.input_frame = QFrame()
        self.input_frame.setFixedHeight(50)
        self.input_frame.setStyleSheet(f"background-color: {BG_INPUT}; border-top: 1px solid {BORDER};")
        il = QHBoxLayout(self.input_frame)
        il.setContentsMargins(12, 4, 12, 4)
        il.setSpacing(8)

        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Ask a follow up... (Enter to send)")
        self.cmd_input.setFont(QFont("Consolas", 11))
        self.cmd_input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent; color: {FG_PRIMARY};
                border: none; padding: 4px;
                font-family: 'Consolas', monospace; font-size: 11pt;
            }}
        """)
        self.cmd_input.returnPressed.connect(self._on_cmd_enter)
        self.cmd_input.installEventFilter(self)
        il.addWidget(self.cmd_input, 1)

        send_btn = QPushButton("\u25B6")
        send_btn.setFixedSize(32, 32)
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: #000000;
                border-radius: 16px; font-size: 12pt; font-weight: bold;
            }}
            QPushButton:hover {{ background: #04f0d8; }}
        """)
        send_btn.clicked.connect(self._on_cmd_enter)
        il.addWidget(send_btn)

        layout.addWidget(self.input_frame)

    def eventFilter(self, obj, event):
        """Handle Up/Down arrow for command history in input."""
        if obj == self.cmd_input and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Up:
                self._cmd_history_prev()
                return True
            elif event.key() == Qt.Key.Key_Down:
                self._cmd_history_next()
                return True
        return super().eventFilter(obj, event)

    # ── Footer / Status Bar ───────────────────────────────────────

    def _build_footer(self):
        self.statusBar().setStyleSheet(f"""
            QStatusBar {{
                background-color: {BG_STATUS};
                color: {FG_DIM};
                font-size: 8pt;
                border-top: 1px solid {BORDER};
            }}
        """)

        # Path
        cwd = os.path.basename(os.getcwd())
        self.path_label = QLabel(f"  \U0001f4c1 ~\\{cwd}")
        self.path_label.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt;")
        self.statusBar().addWidget(self.path_label)

        # Ollama status dot
        self.ollama_dot = QLabel("\u25CF")
        self.ollama_dot.setStyleSheet(f"color: {FG_ERROR}; font-size: 10pt;")
        self.ollama_dot.setToolTip("Ollama: offline")
        self.statusBar().addWidget(self.ollama_dot)

        self.ollama_label = QLabel("Ollama")
        self.ollama_label.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt;")
        self.statusBar().addWidget(self.ollama_label)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.statusBar().addWidget(spacer)

        # TODO counter
        self.todo_label = QLabel("\u2630 0/0")
        self.todo_label.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; padding: 0 8px;")
        self.todo_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.todo_label.mousePressEvent = lambda e: self._show_todo_panel()
        self.statusBar().addPermanentWidget(self.todo_label)

        # Model selector
        self.model_combo = QComboBox()
        self.model_combo.addItems(MODELS)
        idx = MODELS.index(DEFAULT_MODEL) if DEFAULT_MODEL in MODELS else 0
        self.model_combo.setCurrentIndex(idx)
        self.model_combo.setStyleSheet(f"""
            QComboBox {{
                background: {BG_INPUT}; color: {ACCENT};
                border: 1px solid {BORDER}; border-radius: 3px;
                padding: 1px 6px; font-size: 8pt; min-width: 100px;
            }}
        """)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.statusBar().addPermanentWidget(self.model_combo)

        # Git status
        self.git_label = QLabel("SubZero")
        self.git_label.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; padding: 0 8px;")
        self.statusBar().addPermanentWidget(self.git_label)

        # Start git status timer
        self._git_timer = QTimer(self)
        self._git_timer.timeout.connect(self._refresh_git_status)
        self._git_timer.start(15000)
        self._refresh_git_status()

    def _on_model_changed(self, model):
        self.agent.model = model
        self._term_print(f"[Model] Switched to {model}\n", FG_USER)

    def _start_status_checker(self):
        self._status_checker = OllamaStatusChecker(self.agent)
        self._status_checker.status_changed.connect(self._update_ollama_status)
        self._status_checker.start()

    def _update_ollama_status(self, online):
        self.ollama_online = online
        if online:
            self.ollama_dot.setStyleSheet(f"color: {FG_AI}; font-size: 10pt;")
            self.ollama_dot.setToolTip("Ollama: online")
        else:
            self.ollama_dot.setStyleSheet(f"color: {FG_ERROR}; font-size: 10pt;")
            self.ollama_dot.setToolTip("Ollama: offline")

    def _refresh_git_status(self):
        # GIT_TERMINAL_PROMPT=0 prevents credential popups
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GCM_INTERACTIVE"] = "never"
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=3,
                cwd=os.getcwd(), env=env,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
                status = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True, text=True, timeout=3,
                    cwd=os.getcwd(), env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                dirty = "*" if status.stdout.strip() else ""
                self.git_label.setText(f"\U0001f500 {branch}{dirty} \u2502 SubZero")
                self.git_label.setStyleSheet(f"color: {ACCENT}; font-size: 8pt; padding: 0 8px;")
            else:
                self.git_label.setText("SubZero")
                self.git_label.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; padding: 0 8px;")
        except Exception:
            pass

    # ── Keyboard Shortcuts ────────────────────────────────────────

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_current)
        QShortcut(QKeySequence("Ctrl+G"), self, self._toggle_ai_responses)
        QShortcut(QKeySequence("Ctrl+I"), self, self._take_over)
        QShortcut(QKeySequence("Ctrl+L"), self, self._clear_terminal)
        QShortcut(QKeySequence("Ctrl+Shift+P"), self, self._show_command_palette)
        QShortcut(QKeySequence("Ctrl+O"), self, self._open_external_file)
        QShortcut(QKeySequence("Ctrl+T"), self, self._show_todo_panel)
        QShortcut(QKeySequence("Ctrl+F"), self, self._show_find_bar)
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out)

    # ── File Operations ───────────────────────────────────────────

    def _open_file(self, layer, version, filename):
        self.current_layer = layer
        self.current_version = version
        self.current_file = filename
        content = self.layers.read_file(layer, version, filename)
        if HAS_QSCI:
            self.editor.setText(content)
            # Set lexer based on file type
            ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
            if ext in ("js", "jsx", "ts", "tsx"):
                lexer = QsciLexerJavaScript(self.editor)
            elif ext == "json":
                lexer = QsciLexerJSON(self.editor)
            else:
                lexer = QsciLexerPython(self.editor)
            font = QFont("Consolas", 11)
            lexer.setFont(font)
            lexer.setDefaultPaper(QColor(BG_EDITOR))
            lexer.setDefaultColor(QColor(FG_PRIMARY))
            for i in range(20):
                lexer.setPaper(QColor(BG_EDITOR), i)
            self.editor.setLexer(lexer)
        else:
            self.editor.setPlainText(content)
        self._update_version_bar()
        self.statusBar().showMessage(f"{layer}/{version}/{filename}", 5000)

    def _save_current(self):
        if self.current_layer and self.current_version and self.current_file:
            if HAS_QSCI:
                content = self.editor.text()
            else:
                content = self.editor.toPlainText()
            self.layers.write_file(self.current_layer, self.current_version,
                                   self.current_file, content)
            self._term_print(f"Saved: {self.current_layer}/{self.current_version}/{self.current_file}\n", FG_AI)

    def _switch_version(self, version):
        if not self.current_layer:
            return
        self._save_current()
        self.current_version = version
        files = self.layers.get_files(self.current_layer, version)
        if files:
            self._open_file(self.current_layer, version, files[0])
        self._update_version_bar()
        self._term_print(f"Switched to {self.current_layer}/{version}\n", FG_USER)

    def _run_current(self):
        if not self.current_file:
            self._term_print("No file open to run.\n", FG_WARNING)
            return
        self._save_current()
        path = self.layers.get_file_path(
            self.current_layer, self.current_version, self.current_file)
        self._term_print(f"Running {self.current_file}...\n", FG_AI)
        threading.Thread(target=self._exec_cmd, args=(f'python "{path}"',), daemon=True).start()

    def _exec_cmd(self, cmd):
        try:
            self.append_terminal.emit(f"[Running] {cmd}\n", FG_AI)
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=300, encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.stdout:
                self.append_terminal.emit(result.stdout, "")
            if result.stderr:
                color = FG_DIM if result.returncode == 0 else FG_ERROR
                self.append_terminal.emit(result.stderr, color)
            status = "[Done]" if result.returncode == 0 else f"[Failed] Exit code: {result.returncode}"
            color = FG_AI if result.returncode == 0 else FG_ERROR
            self.append_terminal.emit(f"{status}\n", color)
        except subprocess.TimeoutExpired:
            self.append_terminal.emit("[Timed out]\n", FG_ERROR)
        except Exception as e:
            self.append_terminal.emit(f"[Error] {e}\n", FG_ERROR)

    # ── Command Input ─────────────────────────────────────────────

    def _on_cmd_enter(self):
        cmd = self.cmd_input.text().strip()
        if not cmd:
            return
        self.cmd_input.clear()

        # Save to history
        if not self.cmd_history or self.cmd_history[-1] != cmd:
            self.cmd_history.append(cmd)
        self.cmd_history_idx = None

        lower = cmd.lower()
        if lower == "clear":
            self._clear_terminal()
        elif lower == "layers":
            layers = self.layers.list_layers()
            if layers:
                self._term_print(f"Layers ({len(layers)}):\n", FG_ACCENT)
                for l in layers:
                    vers = self.layers.list_versions(l)
                    self._term_print(f"  {l}  [{', '.join(vers)}]\n")
            else:
                self._term_print("No layers.\n", FG_DIM)
        elif lower == "help":
            self._term_print(
                "Commands:\n"
                "  layers       List all layers\n"
                "  run          Run current file\n"
                "  clear        Clear terminal\n"
                "  save         Save current file\n"
                "  !<cmd>       Shell command\n"
                "  todo add/list/done/clear\n"
                "  <other>      Ask AI\n\n", FG_DIM)
        elif self._handle_todo_command(cmd):
            pass
        elif lower == "run":
            self._run_current()
        elif lower == "save":
            self._save_current()
        elif cmd.startswith("!"):
            threading.Thread(target=self._exec_cmd, args=(cmd[1:].strip(),), daemon=True).start()
        else:
            self._ask_ai(cmd)

    def _cmd_history_prev(self):
        if not self.cmd_history:
            return
        if self.cmd_history_idx is None:
            self.cmd_history_idx = len(self.cmd_history) - 1
        elif self.cmd_history_idx > 0:
            self.cmd_history_idx -= 1
        else:
            return
        self.cmd_input.setText(self.cmd_history[self.cmd_history_idx])

    def _cmd_history_next(self):
        if not self.cmd_history or self.cmd_history_idx is None:
            return
        if self.cmd_history_idx < len(self.cmd_history) - 1:
            self.cmd_history_idx += 1
            self.cmd_input.setText(self.cmd_history[self.cmd_history_idx])
        else:
            self.cmd_history_idx = None
            self.cmd_input.clear()

    # ── AI Chat ───────────────────────────────────────────────────

    def _ask_ai(self, prompt):
        if self.ai_busy:
            self._term_print("[AI] Still processing...\n", FG_WARNING)
            return

        if not self.ollama_online:
            self._term_print(
                f"[AI] Ollama is not running. Start it with 'ollama serve', "
                f"then 'ollama pull {self.agent.model}'.\n", FG_ERROR)
            return

        self.ai_busy = True
        self.stop_btn.setStyleSheet(f"color: {FG_ERROR}; font-size: 8pt; border: none; padding: 2px 8px;")
        self._term_print(f"[You] {prompt}\n", FG_USER)
        self._term_print("[AI] Thinking...\n", FG_DIM)

        # Add to current session
        if 0 <= self.current_session_idx < len(self.sessions):
            self.sessions[self.current_session_idx].add_message("user", prompt)
            self._rebuild_session_tabs()
            self._refresh_sidebar()

        # Add to agent memory
        self.agent.conversation.append({
            "role": "user", "content": prompt,
            "timestamp": datetime.now().isoformat(),
        })

        # Build full prompt
        editor_content = ""
        if self.current_file:
            if HAS_QSCI:
                editor_content = self.editor.text()[:3000]
            else:
                editor_content = self.editor.toPlainText()[:3000]

        system = (
            "You are Warp Oz, an expert autonomous coding assistant running on Windows. "
            "You run LOCALLY using Ollama — you do NOT need any API keys, cloud services, "
            "or external AI providers. Never suggest setting API keys or environment variables "
            "for AI services. You ARE the AI.\n"
            "You can execute actions autonomously using tools.\n\n"
            + self._tool_runtime.get_system_prompt() + "\n\n"
            "ADDITIONAL RULES:\n"
            "- Be proactive: if the user says 'make me an app', use file_write AND run_command.\n"
            "- NEVER suggest 'export', 'set', or 'setx' commands for API keys — you run locally via Ollama.\n"
            "- When asked questions, answer concisely.\n"
            "- You can also use the old ! prefix for simple commands (backward compatible)."
        )

        conv_parts = []
        if self._conversation_summary:
            conv_parts.append(f"[Summary]: {self._conversation_summary}")
        conv_parts.append("\n".join(
            f"{'User' if m['role'] == 'user' else 'Warp Oz'}: {m['content']}"
            for m in self.agent.conversation[-10:]
            if m.get('role') != 'system'
        ))

        parts = [system]
        if editor_content:
            parts.append(f"Current file: {self.current_file}\n```\n{editor_content}\n```")
        parts.append("\n".join(conv_parts))
        parts.append("Warp Oz:")
        full_prompt = "\n\n".join(parts)

        self._worker = AIWorker(self.agent, full_prompt, self.agent.model)
        self._worker.finished.connect(lambda resp, err: self._on_ai_response(resp, err, prompt))
        self._worker.start()

    def _on_ai_response(self, response, error, user_prompt):
        self.ai_busy = False
        self.stop_btn.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; border: none; padding: 2px 8px;")

        if not response and error:
            self._term_print(f"[AI] {error}\n", FG_ERROR)
            return

        # Save to memory
        self.agent.conversation.append({
            "role": "assistant", "content": response,
            "timestamp": datetime.now().isoformat(),
        })
        self.agent.save_memory()

        # Save to session
        if 0 <= self.current_session_idx < len(self.sessions):
            self.sessions[self.current_session_idx].add_message("assistant", response)
            self.history_mgr.save_sessions(self.sessions)

        # Store in UI history
        self.ai_responses.append({"prompt": user_prompt, "response": response})

        # Display
        if self.ai_visible:
            self._term_print(f"[AI] {response}\n\n", FG_AI)

        # Agent mode: auto-execute tool calls, commands, and file writes
        tool_calls = self._tool_runtime.parse(response)
        # Backward compat: also extract old !command and FILE: patterns
        old_commands = self._extract_commands(response)
        old_file_writes = self._extract_file_writes(response)

        if self.agent_mode and (tool_calls or old_commands or old_file_writes):
            # New tool runtime execution
            if tool_calls:
                self._term_print(f"[Agent] Executing {len(tool_calls)} tool(s)...\n", FG_AI)
                threading.Thread(
                    target=self._run_tool_loop, args=(tool_calls, response, user_prompt),
                    daemon=True,
                ).start()
            # Legacy support
            if old_file_writes:
                self._term_print(f"[Agent] Writing {len(old_file_writes)} file(s)...\n", FG_AI)
                for fpath, content in old_file_writes:
                    self._agent_write_file(fpath, content)
            if old_commands:
                self._term_print(f"[Agent] Running {len(old_commands)} command(s)...\n", FG_AI)
                for cmd in old_commands:
                    self._term_print(f"  $ {cmd}\n", FG_ACCENT)
                    threading.Thread(target=self._exec_cmd, args=(cmd,), daemon=True).start()

    def _run_tool_loop(self, tool_calls, response, user_prompt, iteration=0):
        """Execute tool calls and optionally feed results back to AI for chaining."""
        results = self._tool_runtime.execute_all(tool_calls)
        for r in results:
            if r.needs_confirm:
                self.append_terminal.emit(f"  {r.output}\n", FG_WARNING)
            elif r.success:
                self.append_terminal.emit(f"  \u2713 [{r.tool_name}] {r.output[:200]}\n", FG_AI)
            else:
                self.append_terminal.emit(f"  \u2717 [{r.tool_name}] {r.output[:200]}\n", FG_ERROR)

        # Auto-chain: if tools produced output and we're under max iterations,
        # feed results back to the AI for the next step
        if (iteration < self._tool_runtime.max_iterations
                and results
                and not self._tool_runtime.has_pending_work(results)
                and any(r.success for r in results)):
            result_text = self._tool_runtime.format_results(results)
            # Check if AI seems to want to continue (heuristic)
            if any(kw in response.lower() for kw in
                   ["next", "then", "now i", "let me", "step 2", "step 3"]):
                self.append_terminal.emit(
                    f"[Agent] Iteration {iteration + 1} — feeding results back...\n", FG_DIM,
                )
                # Queue a follow-up AI call with tool results
                follow_up = f"Tool results:\n{result_text}\n\nContinue with the next step."
                self.agent.conversation.append({
                    "role": "user", "content": follow_up,
                    "timestamp": datetime.now().isoformat(),
                })

    def _extract_commands(self, response):
        """Extract shell commands — ONLY those explicitly prefixed with ! or $.
        Bare commands (pip, git, etc.) are NOT auto-extracted to prevent
        accidental execution of AI explanation text."""
        commands = []
        for line in response.split("\n"):
            line = line.strip()
            # Only ! prefixed commands (our format)
            if line.startswith("!") and len(line) > 1:
                cmd = line[1:].strip()
                # Skip obvious non-commands
                if cmd and not cmd.startswith("#") and len(cmd) < 500:
                    commands.append(cmd)
            # $ prefixed (unix convention)
            elif line.startswith("$ ") and len(line) > 2:
                cmd = line[2:].strip()
                if cmd and not cmd.startswith("#") and len(cmd) < 500:
                    commands.append(cmd)
        return commands

    def _extract_file_writes(self, response):
        file_writes = []
        pattern = re.findall(
            r'(?:FILE|File|file|WRITE|Write|write)[:\s]+([^\n`]+?)\s*\n```(?:\w*)\n(.*?)```',
            response, re.DOTALL
        )
        for path, content in pattern:
            path = path.strip().strip('"').strip("'")
            if path:
                file_writes.append((path, content.strip()))
        return file_writes

    def _agent_write_file(self, filepath, content):
        try:
            fpath = Path(filepath)
            if not fpath.is_absolute():
                fpath = Path(os.getcwd()) / fpath
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(content, encoding="utf-8")
            self._term_print(f"  \u2713 Wrote {fpath} ({len(content)} bytes)\n", FG_AI)
        except Exception as e:
            self._term_print(f"  \u2717 Failed: {filepath}: {e}\n", FG_ERROR)

    def _extract_code(self, response):
        match = re.search(r"```(?:\w+)?\n(.+?)```", response, re.DOTALL)
        if match:
            return match.group(1).strip()
        lines = response.strip().split("\n")
        if lines and any(lines[0].startswith(kw) for kw in
                         ["def ", "class ", "import ", "from ", "#", "async "]):
            return response.strip()
        return None

    # ── UI Actions ────────────────────────────────────────────────

    def _toggle_ai_responses(self):
        self.ai_visible = not self.ai_visible
        if self.ai_visible:
            self.hide_btn.setText("Hide responses  Ctrl+G")
            self.hide_btn.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; border: none; padding: 2px 8px;")
        else:
            self.hide_btn.setText("Show responses  Ctrl+G")
            self.hide_btn.setStyleSheet(f"color: {ACCENT}; font-size: 8pt; border: none; padding: 2px 8px;")

    def _take_over(self):
        if not self.ai_responses:
            self._term_print("[AI] No AI response to insert.\n", FG_WARNING)
            return
        last = self.ai_responses[-1]["response"]
        code = self._extract_code(last)
        if code and self.current_file:
            if HAS_QSCI:
                self.editor.setText(code)
            else:
                self.editor.setPlainText(code)
            self._term_print(f"[AI] Code inserted into {self.current_file}\n", FG_AI)
            self._save_current()
        else:
            self._term_print("[AI] No code to insert or no file open.\n", FG_WARNING)

    def _toggle_agent_mode(self):
        self.agent_mode = not self.agent_mode
        if self.agent_mode:
            self.agent_btn.setStyleSheet(f"color: {FG_AI}; font-size: 8pt; font-weight: bold; border: none; padding: 2px 8px;")
            self._term_print("[Agent] \u26A1 ON \u2014 auto-execute enabled.\n", FG_AI)
        else:
            self.agent_btn.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; font-weight: bold; border: none; padding: 2px 8px;")
            self._term_print("[Agent] OFF \u2014 manual approval required.\n", FG_DIM)

    def _ai_stop(self):
        self.ai_busy = False
        self.stop_btn.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; border: none; padding: 2px 8px;")
        self._term_print("[AI] Stopped.\n", FG_WARNING)

    # ── Code Review ───────────────────────────────────────────────

    def _code_review(self):
        if not self.current_file:
            self._term_print("[Review] No file open.\n", FG_WARNING)
            return
        if HAS_QSCI:
            content = self.editor.text()
        else:
            content = self.editor.toPlainText()
        if not content.strip():
            self._term_print("[Review] File is empty.\n", FG_WARNING)
            return

        self._term_print(f"[Review] Reviewing {self.current_file}...\n", FG_REVIEW)
        prompt = (
            f"Review this code for bugs, security issues, performance, and best practices. "
            f"Be concise and actionable.\n\nFile: {self.current_file}\n```\n{content[:4000]}\n```"
        )
        self._ask_ai(prompt)

    # ── Dialogs ───────────────────────────────────────────────────

    def _new_layer_dialog(self):
        name, ok = QInputDialog.getText(
            self, "New Layer", "Layer name:",
            text="my-layer"
        )
        if ok and name:
            name = name.strip().replace(" ", "-").lower()
            success, msg = self.layers.create_layer(name)
            if success:
                self._term_print(f"Created layer: {name} ({msg})\n", FG_AI)
                self._select_layer(name)
            else:
                self._term_print(f"[Error] {msg}\n", FG_ERROR)

    def _new_version(self, layer_name):
        ok, msg = self.layers.create_version(layer_name)
        if ok:
            self._term_print(f"Created {layer_name}/{msg}\n", FG_AI)
            if layer_name == self.current_layer:
                self._switch_version(msg)
            self._refresh_sidebar()
        else:
            self._term_print(f"[Error] {msg}\n", FG_ERROR)

    def _new_version_current(self):
        if self.current_layer:
            self._save_current()
            self._new_version(self.current_layer)

    def _new_file_dialog(self, layer_name=None):
        layer_name = layer_name or self.current_layer
        if not layer_name:
            return
        versions = self.layers.list_versions(layer_name)
        if not versions:
            return
        version = versions[-1]
        name, ok = QInputDialog.getText(
            self, "New File", f"Filename in {layer_name}/{version}:",
            text="new_file.py"
        )
        if ok and name:
            self.layers.write_file(layer_name, version, name.strip(), f"# {name.strip()}\n")
            self._term_print(f"Created {layer_name}/{version}/{name.strip()}\n", FG_AI)
            self._open_file(layer_name, version, name.strip())

    def _new_file_current(self):
        if self.current_layer:
            self._new_file_dialog(self.current_layer)

    def _delete_layer(self, name):
        reply = QMessageBox.question(
            self, "Delete Layer",
            f"Delete layer '{name}' and all its versions?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.layers.delete_layer(name)
            if self.current_layer == name:
                self.current_layer = None
                self.current_version = None
                self.current_file = None
                self._update_version_bar()
            self._refresh_sidebar()
            self._term_print(f"Deleted layer: {name}\n", FG_ERROR)

    def _open_external_file(self):
        fpath, _ = QFileDialog.getOpenFileName(
            self, "Open File", "",
            "Python (*.py *.pyw);;JavaScript (*.js *.jsx *.ts *.tsx);;JSON (*.json);;All Files (*.*)"
        )
        if fpath:
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                if HAS_QSCI:
                    self.editor.setText(content)
                else:
                    self.editor.setPlainText(content)
                self.current_file = os.path.basename(fpath)
                self.current_layer = None
                self.current_version = None
                self.statusBar().showMessage(fpath, 5000)
                self.setWindowTitle(f"\u2744 WARP OZ \u2014 {self.current_file}")
            except Exception as e:
                self._term_print(f"[Error] {e}\n", FG_ERROR)

    # ── Find & Replace ────────────────────────────────────────────

    def _show_find_bar(self):
        if HAS_QSCI:
            text, ok = QInputDialog.getText(self, "Find", "Search for:")
            if ok and text:
                self.editor.findFirst(text, False, False, False, True)
        else:
            text, ok = QInputDialog.getText(self, "Find", "Search for:")
            if ok and text:
                self.editor.find(text)

    # ── Zoom ──────────────────────────────────────────────────────

    def _zoom_in(self):
        if HAS_QSCI:
            self.editor.zoomIn(1)
        else:
            font = self.editor.font()
            font.setPointSize(min(font.pointSize() + 1, 24))
            self.editor.setFont(font)

    def _zoom_out(self):
        if HAS_QSCI:
            self.editor.zoomOut(1)
        else:
            font = self.editor.font()
            font.setPointSize(max(font.pointSize() - 1, 8))
            self.editor.setFont(font)

    # ── Command Palette ───────────────────────────────────────────

    def _show_command_palette(self):
        actions = [
            ("Clear Terminal", self._clear_terminal),
            ("Save File", self._save_current),
            ("Run Current File", self._run_current),
            ("New Layer", self._new_layer_dialog),
            ("New Version", self._new_version_current),
            ("New File", self._new_file_current),
            ("Open File", self._open_external_file),
            ("Toggle AI Responses", self._toggle_ai_responses),
            ("Toggle Agent Mode", self._toggle_agent_mode),
            ("Code Review", self._code_review),
            ("Zoom In", self._zoom_in),
            ("Zoom Out", self._zoom_out),
            ("Find", self._show_find_bar),
            ("Take Over (Insert AI Code)", self._take_over),
            ("TODO List", self._show_todo_panel),
        ]

        dialog = QDialog(self)
        dialog.setWindowTitle("Command Palette")
        dialog.setFixedSize(500, 400)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: #0a0e1a;
                border: 1px solid {BORDER};
            }}
        """)
        dl = QVBoxLayout(dialog)
        dl.setContentsMargins(8, 8, 8, 8)

        search = QLineEdit()
        search.setPlaceholderText("Type a command...")
        search.setFont(QFont("Consolas", 11))
        dl.addWidget(search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 4, 0, 0)
        results_layout.setSpacing(2)
        results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(results_widget)
        dl.addWidget(scroll, 1)

        def refresh(text=""):
            while results_layout.count():
                item = results_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            q = text.lower()
            for name, action in actions:
                if q and q not in name.lower():
                    continue
                btn = QPushButton(f"  {name}")
                btn.setStyleSheet(f"""
                    QPushButton {{
                        text-align: left; padding: 8px 12px;
                        background: transparent; color: {FG_PRIMARY};
                        border: none; font-size: 10pt;
                    }}
                    QPushButton:hover {{ background: {BG_TAB_ACTIVE}; }}
                """)
                btn.clicked.connect(lambda checked=False, a=action: (dialog.close(), a()))
                results_layout.addWidget(btn)

        search.textChanged.connect(refresh)
        refresh()
        search.setFocus()
        dialog.exec()

    # ── TODO System ───────────────────────────────────────────────

    def _load_todos(self):
        try:
            if TODO_FILE.exists():
                with open(TODO_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._todos = data.get("todos", [])
                self._todo_counter = data.get("counter", 0)
        except Exception:
            self._todos = []
            self._todo_counter = 0

    def _save_todos(self):
        try:
            TODO_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(TODO_FILE, "w", encoding="utf-8") as f:
                json.dump({"todos": self._todos, "counter": self._todo_counter}, f, indent=2)
        except Exception:
            pass

    def _update_todo_label(self):
        done = sum(1 for t in self._todos if t.get("done"))
        total = len(self._todos)
        self.todo_label.setText(f"\u2630 {done}/{total}")
        if total > 0:
            self.todo_label.setStyleSheet(f"color: {ACCENT}; font-size: 8pt; padding: 0 8px;")
        else:
            self.todo_label.setStyleSheet(f"color: {FG_DIM}; font-size: 8pt; padding: 0 8px;")

    def _add_todo(self, title):
        if not title.strip():
            return
        self._todo_counter += 1
        self._todos.append({
            "id": self._todo_counter, "title": title.strip(),
            "done": False, "created": datetime.now().isoformat(),
        })
        self._save_todos()
        self._update_todo_label()

    def _complete_todo(self, todo_id):
        for t in self._todos:
            if t["id"] == todo_id:
                t["done"] = True
        self._save_todos()
        self._update_todo_label()

    def _delete_todo(self, todo_id):
        self._todos = [t for t in self._todos if t["id"] != todo_id]
        self._save_todos()
        self._update_todo_label()

    def _show_todo_panel(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("TODO List")
        dialog.setFixedSize(500, 420)
        dialog.setStyleSheet(f"QDialog {{ background-color: #0a0e1a; }}")
        dl = QVBoxLayout(dialog)
        dl.setContentsMargins(12, 12, 12, 12)

        done = sum(1 for t in self._todos if t.get("done"))
        hdr = QLabel(f"\u2630 TODO List ({done}/{len(self._todos)})")
        hdr.setStyleSheet(f"color: {ACCENT}; font-size: 11pt; font-weight: bold;")
        dl.addWidget(hdr)

        # Add input
        add_layout = QHBoxLayout()
        todo_input = QLineEdit()
        todo_input.setPlaceholderText("Add a task...")
        add_layout.addWidget(todo_input, 1)
        add_btn = QPushButton("+ Add")
        add_btn.setStyleSheet(f"background: {ACCENT}; color: #000; font-weight: bold; padding: 4px 12px;")
        add_layout.addWidget(add_btn)
        dl.addLayout(add_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 4, 0, 0)
        list_layout.setSpacing(2)
        list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(list_widget)
        dl.addWidget(scroll, 1)

        def refresh_list():
            while list_layout.count():
                item = list_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            d = sum(1 for t in self._todos if t.get("done"))
            hdr.setText(f"\u2630 TODO List ({d}/{len(self._todos)})")
            for t in sorted(self._todos, key=lambda x: (x.get("done", False), -x["id"])):
                row = QHBoxLayout()
                is_done = t.get("done", False)
                chk = QPushButton("\u2611" if is_done else "\u2610")
                chk.setFixedWidth(30)
                chk.setStyleSheet(f"color: {FG_AI if is_done else FG_DIM}; font-size: 14pt; border: none;")
                chk.clicked.connect(lambda checked=False, tid=t["id"], d=is_done:
                    (self._complete_todo(tid) if not d else None, refresh_list()))
                row.addWidget(chk)

                lbl = QLabel(t["title"])
                if is_done:
                    lbl.setStyleSheet(f"color: {FG_DIM}; text-decoration: line-through;")
                else:
                    lbl.setStyleSheet(f"color: {FG_PRIMARY};")
                row.addWidget(lbl, 1)

                del_btn = QPushButton("\u2715")
                del_btn.setFixedWidth(24)
                del_btn.setStyleSheet(f"color: {FG_ERROR}; border: none; font-size: 10pt;")
                del_btn.clicked.connect(lambda checked=False, tid=t["id"]: (self._delete_todo(tid), refresh_list()))
                row.addWidget(del_btn)

                container = QWidget()
                container.setLayout(row)
                list_layout.addWidget(container)

        def add_and_refresh():
            title = todo_input.text().strip()
            if title:
                self._add_todo(title)
                todo_input.clear()
                refresh_list()

        todo_input.returnPressed.connect(add_and_refresh)
        add_btn.clicked.connect(add_and_refresh)
        refresh_list()
        todo_input.setFocus()
        dialog.exec()

    def _handle_todo_command(self, cmd):
        lower = cmd.lower().strip()
        if lower.startswith("todo add "):
            title = cmd[9:].strip()
            self._add_todo(title)
            self._term_print(f"[TODO] Added: {title}\n", FG_AI)
            self._update_todo_label()
            return True
        elif lower.startswith("todo done "):
            try:
                idx = int(cmd.split()[-1])
                self._complete_todo(idx)
                self._term_print(f"[TODO] Completed #{idx}\n", FG_AI)
                self._update_todo_label()
            except (ValueError, IndexError):
                self._term_print("[TODO] Usage: todo done <id>\n", FG_ERROR)
            return True
        elif lower in ("todo", "todo list", "todos"):
            if not self._todos:
                self._term_print("[TODO] No tasks. Use 'todo add <task>'.\n", FG_DIM)
            else:
                done = sum(1 for t in self._todos if t.get("done"))
                self._term_print(f"[TODO] Tasks ({done}/{len(self._todos)}):\n", FG_ACCENT)
                for t in self._todos:
                    mark = "\u2713" if t.get("done") else " "
                    color = FG_DIM if t.get("done") else FG_PRIMARY
                    self._term_print(f"  [{mark}] #{t['id']}  {t['title']}\n", color)
            return True
        elif lower == "todo clear":
            self._todos = [t for t in self._todos if not t.get("done")]
            self._save_todos()
            self._update_todo_label()
            self._term_print("[TODO] Cleared completed tasks.\n", FG_AI)
            return True
        return False

    # ── Cleanup ───────────────────────────────────────────────────

    def closeEvent(self, event):
        if hasattr(self, '_status_checker'):
            self._status_checker.stop()
            self._status_checker.wait(2000)
        self.history_mgr.save_sessions(self.sessions)
        self.agent.save_memory()
        self._save_todos()
        event.accept()


# ══════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette base
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG_MAIN))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(FG_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG_EDITOR))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.Text, QColor(FG_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(BG_BUTTON))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(FG_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
    app.setPalette(palette)

    window = WarpOzWindow()
    window.show()
    sys.exit(app.exec())
