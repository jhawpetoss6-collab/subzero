"""
Snowflake 2.5 — Optimized Dual-Model AI Swarm (Performance Rewrite)
Architecture:
  - Split-thread model: Front + Back-Up coordinate via thread splitting
  - HTTP connection pooling (eliminates per-request connection overhead)
  - Retry with exponential backoff
  - Request queue with background drain
  - Background swarm workers
  - Model warmup / keepalive
  - Token batching (reduces UI thread pressure)
  - Compact prompts
"""
import tkinter as tk
import json, os, threading, time, queue, http.client
from datetime import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from sz_runtime import ToolRuntime

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

LOGO_PATH = Path(__file__).parent / "logo.png"
DATA_HOME = os.path.join(os.path.expanduser("~"), ".subzero", "snowflake")
os.makedirs(DATA_HOME, exist_ok=True)

BG = "#000000"; BG_PANEL = "#020810"; BG_CARD = "#010610"
BG_INPUT = "#081428"; BG_HOVER = "#041228"
FG = "#e0e0e0"; FG_DIM = "#445577"; ACCENT = "#0066cc"
BORDER = "#0a1e3a"

OLLAMA_HOST = "localhost"
OLLAMA_PORT = 11434
FRONT_MODEL = "qwen2.5:3b"
BACKUP_MODEL = "qwen2.5:3b"

FRONT_IDENTITY_BASE = "You are FRONT agent in Snowflake 2.5. Primary responder. Direct, precise, complete. Code in ```."
BACKUP_IDENTITY_BASE = "You are BACK-UP agent in Snowflake 2.5. Verify, catch errors, offer alternatives. Analytical. Code in ```."

MAX_RETRIES = 3; RETRY_BACKOFF = 1.0; STREAM_TIMEOUT = 45
GENERATE_TIMEOUT = 30; KEEPALIVE_SEC = 120; TOKEN_BATCH_MS = 25
CONTEXT_LIMIT = 3; POOL_WORKERS = 6; QUEUE_MAX = 20


class OllamaEngine:
    """HTTP/1.1 persistent-connection Ollama client with retry + backoff."""

    def __init__(self):
        self._online = None; self._last_check = 0
        self._local = threading.local()

    def _conn(self):
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = http.client.HTTPConnection(OLLAMA_HOST, OLLAMA_PORT, timeout=10)
            self._local.conn = conn
        return conn

    def _reset_conn(self):
        old = getattr(self._local, "conn", None)
        if old:
            try: old.close()
            except: pass
        self._local.conn = http.client.HTTPConnection(OLLAMA_HOST, OLLAMA_PORT, timeout=10)
        return self._local.conn

    def is_online(self):
        now = time.time()
        if now - self._last_check < 3: return self._online
        try:
            conn = self._conn(); conn.request("GET", "/api/tags")
            resp = conn.getresponse(); resp.read()
            self._online = resp.status == 200
        except:
            self._online = False; self._reset_conn()
        self._last_check = now
        return self._online

    def warmup(self, model):
        try:
            body = json.dumps({"model": model, "prompt": "hi", "stream": False, "options": {"num_predict": 1}}).encode()
            conn = self._conn()
            conn.request("POST", "/api/generate", body=body, headers={"Content-Type": "application/json"})
            resp = conn.getresponse(); resp.read()
        except: self._reset_conn()

    def stream(self, model, prompt, on_token, on_done, timeout=STREAM_TIMEOUT):
        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                self._stream_once(model, prompt, on_token, on_done, timeout); return
            except Exception as e:
                last_err = str(e); self._reset_conn()
                if attempt < MAX_RETRIES - 1: time.sleep(RETRY_BACKOFF * (2 ** attempt))
        on_done(None, f"Failed after {MAX_RETRIES} retries: {last_err}")

    def _stream_once(self, model, prompt, on_token, on_done, timeout):
        body = json.dumps({"model": model, "prompt": prompt, "stream": True}).encode()
        conn = self._conn(); conn.timeout = timeout
        conn.request("POST", "/api/generate", body=body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        if resp.status != 200:
            data = resp.read(); raise ConnectionError(f"HTTP {resp.status}: {data[:200]}")
        full = []; buf = b""
        while True:
            chunk = resp.read(4096)
            if not chunk: break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip(): continue
                try:
                    obj = json.loads(line)
                    token = obj.get("response", "")
                    if token: full.append(token); on_token(token)
                    if obj.get("done"): on_done("".join(full), None); return
                except json.JSONDecodeError: continue
        on_done("".join(full) if full else None, None if full else "Empty stream")

    def generate(self, model, prompt, timeout=GENERATE_TIMEOUT):
        for attempt in range(MAX_RETRIES):
            try:
                body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
                conn = self._conn(); conn.timeout = timeout
                conn.request("POST", "/api/generate", body=body, headers={"Content-Type": "application/json"})
                resp = conn.getresponse(); data = json.loads(resp.read().decode())
                return data.get("response", "").strip() or "[No response]"
            except Exception as e:
                self._reset_conn()
                if attempt == MAX_RETRIES - 1: return f"[Error after {MAX_RETRIES} retries: {e}]"
                time.sleep(RETRY_BACKOFF * (2 ** attempt))


class SharedMemory:
    def __init__(self):
        self.lock = threading.Lock()
        self.front_history = deque(maxlen=20)
        self.backup_history = deque(maxlen=20)
        self.shared_context = deque(maxlen=10)
        self.perf = {"front_calls":0,"backup_calls":0,"front_time":0.0,"backup_time":0.0,
                     "front_errors":0,"backup_errors":0,"failovers":0,"tasks_done":0,"retries":0,"queued":0,"warmups":0}

    def add_front(self, q, a):
        with self.lock:
            self.front_history.append({"q":q,"a":a,"t":time.time()})
            self.shared_context.append(f"[F] {q[:50]}\u2192{a[:80]}")
    def add_backup(self, q, a):
        with self.lock:
            self.backup_history.append({"q":q,"a":a,"t":time.time()})
            self.shared_context.append(f"[B] {q[:50]}\u2192{a[:80]}")
    def get_context(self, limit=CONTEXT_LIMIT):
        with self.lock: return list(self.shared_context)[-limit:]
    def record(self, agent, elapsed, error=False):
        with self.lock:
            self.perf[f"{agent}_calls"] += 1; self.perf[f"{agent}_time"] += elapsed
            if error: self.perf[f"{agent}_errors"] += 1
    def get_perf(self):
        with self.lock:
            p = dict(self.perf)
            p["front_avg"] = p["front_time"]/p["front_calls"] if p["front_calls"] else 0
            p["backup_avg"] = p["backup_time"]/p["backup_calls"] if p["backup_calls"] else 0
            return p


class SwarmQueue:
    def __init__(self, engine, memory, on_result):
        self._q = queue.Queue(maxsize=QUEUE_MAX)
        self._engine = engine; self._memory = memory; self._on_result = on_result; self._running = True
        for i in range(2):
            threading.Thread(target=self._worker, name=f"swarm-bg-{i}", daemon=True).start()

    def enqueue(self, which, model, identity, req, shared_ctx):
        try:
            self._q.put_nowait((which, model, identity, req, shared_ctx))
            with self._memory.lock: self._memory.perf["queued"] += 1
            return True
        except queue.Full: return False

    def _worker(self):
        while self._running:
            try: item = self._q.get(timeout=2)
            except queue.Empty: continue
            which, model, identity, req, shared_ctx = item
            prompt = identity
            if shared_ctx: prompt += f"\n\nContext:\n{shared_ctx}"
            prompt += f"\n\nUser: {req}"
            start = time.time()
            result = self._engine.generate(model, prompt, timeout=GENERATE_TIMEOUT)
            self._on_result(which, req, result, time.time() - start)
            self._q.task_done()

    @property
    def pending(self): return self._q.qsize()
    def stop(self): self._running = False


class TokenBatcher:
    def __init__(self, root, flush_fn, interval_ms=TOKEN_BATCH_MS):
        self.root = root; self.flush_fn = flush_fn; self.interval = interval_ms
        self._buf = []; self._lock = threading.Lock(); self._scheduled = False

    def add(self, token):
        with self._lock:
            self._buf.append(token)
            if not self._scheduled:
                self._scheduled = True; self.root.after(self.interval, self._flush)

    def _flush(self):
        with self._lock:
            tokens = self._buf[:]; self._buf.clear(); self._scheduled = False
        if tokens: self.flush_fn("".join(tokens))


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Snowflake 2.5 \u2014 Optimized Dual-Model Swarm")
        self.root.geometry("1280x780")
        self.root.minsize(1020, 580)
        self.root.configure(bg=BG)
        self.root.attributes("-alpha", 0.96)

        self.engine = OllamaEngine()
        self.memory = SharedMemory()
        self._tool_rt = ToolRuntime()
        self.pool = ThreadPoolExecutor(max_workers=POOL_WORKERS, thread_name_prefix="swarm")
        self.front_busy = False; self.backup_busy = False
        self.front_batcher = None; self.backup_batcher = None
        self.swarm_queue = SwarmQueue(self.engine, self.memory, self._on_queue_result)

        # Build identity prompts with tool runtime
        tool_prompt = self._tool_rt.get_system_prompt()
        self.FRONT_IDENTITY = FRONT_IDENTITY_BASE + "\n" + tool_prompt
        self.BACKUP_IDENTITY = BACKUP_IDENTITY_BASE + "\n" + tool_prompt

        self._build()
        self.front_batcher = TokenBatcher(self.root, lambda t: self._fmsg(t, "stream"))
        self.backup_batcher = TokenBatcher(self.root, lambda t: self._bmsg(t, "stream"))
        self._log("Snowflake 2.5 online \u2014 performance engine active.", "info")
        self._log(f"Front: {FRONT_MODEL} | Back-Up: {BACKUP_MODEL}", "info")
        self._log(f"Pool: {POOL_WORKERS} threads | Retry: {MAX_RETRIES}x | Batch: {TOKEN_BATCH_MS}ms | Queue: {QUEUE_MAX}", "dim")
        self._check_conn(); self._warmup_models(); self._keepalive_loop()
        self.root.mainloop()

    def _warmup_models(self):
        def do():
            self._log("Warming up models...", "dim")
            self.engine.warmup(FRONT_MODEL)
            if BACKUP_MODEL != FRONT_MODEL: self.engine.warmup(BACKUP_MODEL)
            with self.memory.lock: self.memory.perf["warmups"] += 1
            self._log("Models warm. Ready.", "info")
        self.pool.submit(do)

    def _keepalive_loop(self):
        def ping():
            if self.engine.is_online(): self.engine.warmup(FRONT_MODEL)
        self.pool.submit(ping); self.root.after(KEEPALIVE_SEC * 1000, self._keepalive_loop)

    def _build(self):
        # Header
        hdr = tk.Frame(self.root, bg=ACCENT, height=48)
        hdr.pack(fill=tk.X); hdr.pack_propagate(False)
        self._logo_img = None
        if HAS_PIL and LOGO_PATH.exists():
            try:
                img = Image.open(LOGO_PATH).resize((28, 28), Image.LANCZOS)
                self._logo_img = ImageTk.PhotoImage(img)
                tk.Label(hdr, image=self._logo_img, bg=ACCENT).pack(side=tk.LEFT, padx=(10,4))
            except: tk.Label(hdr, text="\u2726", bg=ACCENT, fg="#00aaff", font=("Segoe UI",14)).pack(side=tk.LEFT, padx=(10,4))
        else: tk.Label(hdr, text="\u2726", bg=ACCENT, fg="#00aaff", font=("Segoe UI",14)).pack(side=tk.LEFT, padx=(10,4))
        tk.Label(hdr, text="SNOWFLAKE 2.5", bg=ACCENT, fg="white", font=("Segoe UI",13,"bold")).pack(side=tk.LEFT)
        tk.Label(hdr, text="OPTIMIZED DUAL-MODEL SWARM", bg=ACCENT, fg="#aaccee", font=("Segoe UI",8)).pack(side=tk.LEFT, padx=8)

        self.stat_lbl = tk.Label(hdr, text="", bg=ACCENT, fg="#cce0ff", font=("Segoe UI",8))
        self.stat_lbl.pack(side=tk.RIGHT, padx=14)
        sf = tk.Frame(hdr, bg=ACCENT); sf.pack(side=tk.RIGHT, padx=10)
        self.conn_dot = tk.Label(sf, text="\u25cf Ollama", bg=ACCENT, fg=FG_DIM, font=("Segoe UI",8))
        self.conn_dot.pack(side=tk.LEFT, padx=(0,10))
        self.front_dot = tk.Label(sf, text="\u25cf Front", bg=ACCENT, fg="#00cc66", font=("Segoe UI",8))
        self.front_dot.pack(side=tk.LEFT, padx=(0,8))
        self.backup_dot = tk.Label(sf, text="\u25cf Back-Up", bg=ACCENT, fg="#00cc66", font=("Segoe UI",8))
        self.backup_dot.pack(side=tk.LEFT, padx=(0,4))
        self.queue_lbl = tk.Label(sf, text="", bg=ACCENT, fg="#ffaa00", font=("Segoe UI",8))
        self.queue_lbl.pack(side=tk.LEFT, padx=(8,0))

        # Body: 3-panel paned
        body = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=BORDER, sashwidth=4, sashrelief=tk.FLAT)
        body.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        left = tk.Frame(body, bg=BG_PANEL); center = tk.Frame(body, bg=BG_PANEL); right = tk.Frame(body, bg=BG_PANEL)
        body.add(left, stretch="always", minsize=300); body.add(center, stretch="always", minsize=300)
        body.add(right, stretch="never", minsize=220, width=280)

        self._build_agent(left, "front"); self._build_agent(center, "backup")
        self._build_panel(right); self._build_input()

    def _build_agent(self, parent, which):
        lbl = f"FRONT-LINE \u2022 {FRONT_MODEL}" if which == "front" else f"BACK-UP \u2022 {BACKUP_MODEL}"
        clr = "#00aaff" if which == "front" else "#66bbff"
        tk.Label(parent, text=lbl, bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",9,"bold")).pack(anchor=tk.W, padx=8, pady=(6,2))
        chat = tk.Text(parent, bg=BG_CARD, fg=FG, font=("Consolas",10), wrap=tk.WORD, relief=tk.FLAT, bd=0,
                       padx=10, pady=8, insertbackground="white", selectbackground=ACCENT)
        chat.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,6)); chat.config(state=tk.DISABLED)
        for t,c in [("user","#4499dd"),("ai",clr),("sys",FG_DIM),("code","#0088ff"),("warn","#ffaa00"),
                     ("stream",clr),("queue","#ff6644")]:
            chat.tag_configure(t, foreground=c)
        ctx = tk.Menu(self.root, tearoff=0, bg=BG_HOVER, fg="white")
        ctx.add_command(label="Copy", command=lambda w=chat: self._copy(w))
        ctx.add_command(label="Select All", command=lambda w=chat: self._sel(w))
        chat.bind("<Button-3>", lambda e, m=ctx: m.tk_popup(e.x_root, e.y_root))
        if which == "front":
            self.front_chat = chat; self._fmsg("Front-Line ready. Split-thread streaming.\n","sys")
        else:
            self.backup_chat = chat; self._bmsg("Back-Up ready. Split-thread streaming.\n","sys")

    def _build_panel(self, parent):
        tab_bar = tk.Frame(parent, bg=BG_PANEL); tab_bar.pack(fill=tk.X)
        self._ptabs = {}; self._pbtns = {}
        for name in ["Log","Perf","Memory"]:
            b = tk.Button(tab_bar, text=name, bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold"),
                          relief=tk.FLAT, bd=0, padx=10, pady=3, cursor="hand2",
                          activebackground=BG_HOVER, activeforeground="white",
                          command=lambda n=name: self._show_ptab(n))
            b.pack(side=tk.LEFT); self._pbtns[name] = b
            f = tk.Frame(parent, bg=BG_PANEL); self._ptabs[name] = f

        # Log
        t1 = self._ptabs["Log"]
        self.log_view = tk.Text(t1, bg=BG_CARD, fg="#0088ff", font=("Consolas",8), wrap=tk.WORD, relief=tk.FLAT, bd=0, padx=8, pady=6)
        self.log_view.pack(fill=tk.BOTH, expand=True, padx=4, pady=4); self.log_view.config(state=tk.DISABLED)
        for t,c in [("info","#0088ff"),("front","#00aaff"),("backup","#66bbff"),("warn","#ffaa00"),("dim",FG_DIM),("err","#ff4444")]:
            self.log_view.tag_configure(t, foreground=c)

        # Perf
        t2 = self._ptabs["Perf"]
        self.perf_view = tk.Text(t2, bg=BG_CARD, fg=FG, font=("Consolas",9), wrap=tk.WORD, relief=tk.FLAT, bd=0, padx=8, pady=6)
        self.perf_view.pack(fill=tk.BOTH, expand=True, padx=4, pady=4); self.perf_view.config(state=tk.DISABLED)
        for t,c in [("hdr","#4499dd"),("val","#00aaff"),("dim",FG_DIM)]:
            self.perf_view.tag_configure(t, foreground=c)

        # Memory
        t3 = self._ptabs["Memory"]
        self.mem_view = tk.Text(t3, bg=BG_CARD, fg="#0088ff", font=("Consolas",8), wrap=tk.WORD, relief=tk.FLAT, bd=0, padx=8, pady=6)
        self.mem_view.pack(fill=tk.BOTH, expand=True, padx=4, pady=4); self.mem_view.config(state=tk.DISABLED)
        tk.Button(t3, text="Refresh", bg="#003366", fg="white", font=("Segoe UI",8,"bold"),
                  relief=tk.FLAT, cursor="hand2", command=self._refresh_mem).pack(padx=6, pady=(0,6), anchor=tk.W)

        self._show_ptab("Log")

    def _show_ptab(self, name):
        for n, f in self._ptabs.items():
            f.pack_forget(); self._pbtns[n].config(bg=BG_PANEL, fg=FG_DIM)
        self._ptabs[name].pack(fill=tk.BOTH, expand=True)
        self._pbtns[name].config(bg=ACCENT, fg="white")

    def _build_input(self):
        inp = tk.Frame(self.root, bg=BG_PANEL); inp.pack(fill=tk.X, padx=6, pady=(0,6))
        # Mode selector
        self.mode_var = tk.StringVar(value="both")
        mf = tk.Frame(inp, bg=BG_PANEL); mf.pack(side=tk.LEFT, padx=(0,8))
        for txt, val in [("Both","both"),("Front","front"),("Back-Up","backup")]:
            tk.Radiobutton(mf, text=txt, variable=self.mode_var, value=val,
                           bg=BG_PANEL, fg=FG, selectcolor=BG_CARD, activebackground=BG_HOVER,
                           activeforeground="white", font=("Segoe UI",8), indicatoron=0,
                           padx=8, pady=2, relief=tk.FLAT, bd=1).pack(side=tk.LEFT, padx=1)

        self.entry = tk.Entry(inp, bg=BG_INPUT, fg=FG, font=("Consolas",10), relief=tk.FLAT, borderwidth=4, insertbackground="white")
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,4))
        self.entry.bind("<Return>", lambda e: self._send()); self.entry.focus_set()
        ictx = tk.Menu(self.root, tearoff=0, bg=BG_HOVER, fg="white")
        ictx.add_command(label="Paste", command=lambda: self.entry.insert(tk.INSERT, self.root.clipboard_get()))
        ictx.add_command(label="Copy", command=lambda: self._copy_entry(self.entry))
        ictx.add_command(label="Clear", command=lambda: self.entry.delete(0, tk.END))
        self.entry.bind("<Button-3>", lambda e: ictx.tk_popup(e.x_root, e.y_root))
        tk.Button(inp, text="Send", bg=ACCENT, fg="white", font=("Segoe UI",9,"bold"),
                  relief=tk.FLAT, activebackground="#004499", cursor="hand2", command=self._send).pack(side=tk.RIGHT, padx=(0,4))
        tk.Button(inp, text="Swarm", bg="#886600", fg="white", font=("Segoe UI",9,"bold"),
                  relief=tk.FLAT, activebackground="#aa8800", cursor="hand2", command=self._swarm).pack(side=tk.RIGHT, padx=(0,4))
        tk.Button(inp, text="Clear", bg=BG_HOVER, fg=FG, font=("Segoe UI",9,"bold"),
                  relief=tk.FLAT, cursor="hand2", command=self._clear).pack(side=tk.RIGHT, padx=(0,4))

    # Helpers
    def _fmsg(self, t, tag="sys"):
        self.front_chat.config(state=tk.NORMAL); self.front_chat.insert(tk.END, t, tag)
        self.front_chat.see(tk.END); self.front_chat.config(state=tk.DISABLED)
    def _bmsg(self, t, tag="sys"):
        self.backup_chat.config(state=tk.NORMAL); self.backup_chat.insert(tk.END, t, tag)
        self.backup_chat.see(tk.END); self.backup_chat.config(state=tk.DISABLED)
    def _log(self, text, tag="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view.config(state=tk.NORMAL); self.log_view.insert(tk.END, f"[{ts}] {text}\n", tag)
        self.log_view.see(tk.END); self.log_view.config(state=tk.DISABLED)

    def _update_dots(self):
        online = self.engine.is_online()
        self.conn_dot.config(fg="#00cc66" if online else "#ff4444")
        self.front_dot.config(fg="#ffaa00" if self.front_busy else "#00cc66",
                              text=f"{'◉' if self.front_busy else '●'} Front")
        self.backup_dot.config(fg="#ffaa00" if self.backup_busy else "#00cc66",
                               text=f"{'◉' if self.backup_busy else '●'} Back-Up")
        qn = self.swarm_queue.pending
        self.queue_lbl.config(text=f"\u23f3 {qn}" if qn else "")
        p = self.memory.get_perf()
        self.stat_lbl.config(text=f"F:{p['front_avg']:.1f}s B:{p['backup_avg']:.1f}s | "
                                  f"Calls:{p['front_calls']+p['backup_calls']} | Fail:{p['failovers']} Q:{p['queued']}")

    def _check_conn(self):
        self._update_dots(); self.root.after(4000, self._check_conn)

    def _refresh_perf(self):
        p = self.memory.get_perf()
        self.perf_view.config(state=tk.NORMAL); self.perf_view.delete("1.0", tk.END)
        self.perf_view.insert(tk.END, "PERFORMANCE\n\n","hdr")
        for k, v in [("Front Calls",p["front_calls"]),("Front Avg",f"{p['front_avg']:.2f}s"),
                      ("Front Errors",p["front_errors"]),("",""),
                      ("Backup Calls",p["backup_calls"]),("Backup Avg",f"{p['backup_avg']:.2f}s"),
                      ("Backup Errors",p["backup_errors"]),("",""),
                      ("Failovers",p["failovers"]),("Retries",p["retries"]),
                      ("Queued",p["queued"]),("Warmups",p["warmups"]),("Tasks Done",p["tasks_done"])]:
            if not k: self.perf_view.insert(tk.END, "\n"); continue
            self.perf_view.insert(tk.END, f"  {k:<16}","dim"); self.perf_view.insert(tk.END, f" {v}\n","val")
        self.perf_view.config(state=tk.DISABLED)

    def _refresh_mem(self):
        ctx = self.memory.get_context(10)
        self.mem_view.config(state=tk.NORMAL); self.mem_view.delete("1.0", tk.END)
        self.mem_view.insert(tk.END, "SHARED MEMORY\n\n")
        for c in ctx: self.mem_view.insert(tk.END, f"  {c}\n\n")
        if not ctx: self.mem_view.insert(tk.END, "  (empty)\n")
        self.mem_view.config(state=tk.DISABLED)

    # Send
    def _send(self):
        raw = self.entry.get().strip()
        if not raw: return
        self.entry.delete(0, tk.END)
        mode = self.mode_var.get()
        shared = self.memory.get_context(CONTEXT_LIMIT)
        shared_str = "\n".join(shared) if shared else ""

        if mode in ("both","front"):
            if self.front_busy:
                self.swarm_queue.enqueue("front", FRONT_MODEL, FRONT_IDENTITY, raw, shared_str)
                self.root.after(0, lambda: self._fmsg(f"[Queued] {raw[:60]}...\n","queue"))
                self._log(f"Front busy \u2014 queued: {raw[:40]}...","warn")
            else:
                self._fmsg(f"You: {raw}\n","user")
                self.pool.submit(self._stream_agent, "front", raw, shared_str)

        if mode in ("both","backup"):
            if self.backup_busy:
                self.swarm_queue.enqueue("backup", BACKUP_MODEL, BACKUP_IDENTITY, raw, shared_str)
                self.root.after(0, lambda: self._bmsg(f"[Queued] {raw[:60]}...\n","queue"))
                self._log(f"Backup busy \u2014 queued: {raw[:40]}...","warn")
            else:
                self._bmsg(f"You: {raw}\n","user")
                self.pool.submit(self._stream_agent, "backup", raw, shared_str)
        self._log(f"[{mode}] {raw[:50]}...","info")

    def _stream_agent(self, which, req, shared_ctx):
        model = FRONT_MODEL if which == "front" else BACKUP_MODEL
        identity = self.FRONT_IDENTITY if which == "front" else self.BACKUP_IDENTITY
        msg = self._fmsg if which == "front" else self._bmsg
        batcher = self.front_batcher if which == "front" else self.backup_batcher

        if which == "front": self.front_busy = True
        else: self.backup_busy = True
        self.root.after(0, self._update_dots)

        prompt = identity
        if shared_ctx: prompt += f"\n\nContext:\n{shared_ctx}"
        prompt += f"\n\nUser: {req}"
        self.root.after(0, lambda: msg(f"{which.title()}: ","stream"))
        start = time.time(); tokens = []

        def on_token(tok): tokens.append(tok); batcher.add(tok)
        def on_done(result, error):
            elapsed = time.time() - start
            if error:
                self.memory.record(which, elapsed, error=True)
                self.root.after(0, lambda: msg(f"\n[Error: {error}]\n","warn"))
                self._log(f"{which} error \u2014 failover","err")
                other_model = BACKUP_MODEL if which == "front" else FRONT_MODEL
                with self.memory.lock: self.memory.perf["failovers"] += 1
                fb = self.engine.generate(other_model, prompt, timeout=GENERATE_TIMEOUT)
                self.root.after(0, lambda: msg(f"[Failover]: {fb}\n\n","warn"))
            else:
                self.memory.record(which, elapsed)
                r = "".join(tokens)
                if which == "front": self.memory.add_front(req, r[:200])
                else: self.memory.add_backup(req, r[:200])
                self.root.after(0, lambda: msg("\n\n","stream"))
                self._log(f"{which} done ({elapsed:.1f}s)", which)
                # Execute @tool calls
                tool_calls = self._tool_rt.parse(r)
                if tool_calls:
                    results = self._tool_rt.execute_all(tool_calls)
                    for tr in results:
                        status = "\u2713" if tr.success else "\u2717"
                        self.root.after(0, lambda s=status, t=tr: msg(f"  [{s} {t.tool_name}] {t.output[:120]}\n", "sys"))
                        self._log(f"  [{status} {tr.tool_name}] {tr.output[:60]}", "info" if tr.success else "err")
            if which == "front": self.front_busy = False
            else: self.backup_busy = False
            self.root.after(0, self._update_dots); self.root.after(0, self._refresh_perf)

        self.engine.stream(model, prompt, on_token, on_done, timeout=STREAM_TIMEOUT)

    def _on_queue_result(self, which, req, result, elapsed):
        msg = self._fmsg if which == "front" else self._bmsg
        self.memory.record(which, elapsed)
        if which == "front": self.memory.add_front(req, result[:200])
        else: self.memory.add_backup(req, result[:200])
        def show():
            msg(f"[Queue\u2192{which.title()}]: {result}\n\n","stream")
            self._update_dots(); self._refresh_perf()
        self.root.after(0, show)
        self._log(f"Queue delivered to {which} ({elapsed:.1f}s)", which)

    def _swarm(self):
        raw = self.entry.get().strip()
        if not raw: return
        self.entry.delete(0, tk.END)
        self._fmsg(f"[Swarm] {raw}\n","warn"); self._bmsg(f"[Swarm] {raw}\n","warn")
        self._log(f"SWARM: {raw[:50]}...","warn")
        self.pool.submit(self._coordinated, raw)

    def _coordinated(self, req):
        self.front_busy = True; self.root.after(0, self._update_dots)
        self.root.after(0, lambda: self._fmsg("Front-Line: ","stream"))
        start = time.time(); front_tokens = []
        def ft(tok): front_tokens.append(tok); self.front_batcher.add(tok)
        done_event = threading.Event(); front_result = [None]
        def fd(result, error):
            self.front_busy = False
            self.root.after(0, lambda: self._fmsg("\n\n","stream"))
            self.root.after(0, self._update_dots)
            if error:
                self.memory.record("front", time.time()-start, error=True); front_result[0] = "[Error]"
            else:
                elapsed = time.time()-start; self.memory.record("front", elapsed)
                front_result[0] = "".join(front_tokens)
                self.memory.add_front(req, front_result[0][:200])
                self._log(f"Swarm front done ({elapsed:.1f}s)","front")
            done_event.set()
        self.engine.stream(FRONT_MODEL, f"{self.FRONT_IDENTITY}\n\nTask: {req}", ft, fd, timeout=STREAM_TIMEOUT)
        done_event.wait()

        self.backup_busy = True; self.root.after(0, self._update_dots)
        self.root.after(0, lambda: self._bmsg("Back-Up [Verify]: ","stream"))
        start2 = time.time()
        verify = (f"{BACKUP_IDENTITY}\n\nTask: {req}\n\nFront said:\n{front_result[0][:2000]}\n\n"
                  f"Review: correct? complete? Flag errors or confirm.")
        def bt(tok): self.backup_batcher.add(tok)
        def bd(result, error):
            elapsed2 = time.time() - start2; self.backup_busy = False
            self.root.after(0, lambda: self._bmsg("\n\n","stream"))
            self.root.after(0, self._update_dots)
            if not error:
                self.memory.record("backup", elapsed2); self.memory.add_backup(req, (result or "")[:200])
            else: self.memory.record("backup", elapsed2, error=True)
            with self.memory.lock: self.memory.perf["tasks_done"] += 1
            self._log(f"SWARM DONE: {req[:40]}... ({time.time()-start:.1f}s)","warn")
            self.root.after(0, self._refresh_perf)
        self.engine.stream(BACKUP_MODEL, verify, bt, bd, timeout=STREAM_TIMEOUT)

    def _clear(self):
        for w in [self.front_chat, self.backup_chat]:
            w.config(state=tk.NORMAL); w.delete("1.0", tk.END); w.config(state=tk.DISABLED)
        self._fmsg("Front-Line ready.\n","sys"); self._bmsg("Back-Up ready.\n","sys")

    def _copy(self, w):
        try: self.root.clipboard_clear(); self.root.clipboard_append(w.get(tk.SEL_FIRST, tk.SEL_LAST))
        except: pass
    def _sel(self, w):
        w.config(state=tk.NORMAL); w.tag_add(tk.SEL,"1.0",tk.END); w.config(state=tk.DISABLED)
    def _copy_entry(self, e):
        try:
            if e.selection_present(): self.root.clipboard_clear(); self.root.clipboard_append(e.selection_get())
        except: pass

if __name__ == "__main__": App()
