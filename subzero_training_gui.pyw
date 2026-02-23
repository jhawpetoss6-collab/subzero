"""SubZero Training — AI chat + Tasks + Trading simulator."""
import tkinter as tk
import json, os, threading, random, urllib.request
from datetime import datetime
from pathlib import Path
from sz_runtime import ToolRuntime

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

LOGO_PATH = Path(__file__).parent / "logo.png"
DATA_HOME = os.path.join(os.path.expanduser("~"), ".subzero", "training")
TASKS_FILE = os.path.join(DATA_HOME, "tasks.json")
TRADES_FILE = os.path.join(DATA_HOME, "trades.json")
os.makedirs(DATA_HOME, exist_ok=True)

BG = "#000000"; BG_PANEL = "#020810"; BG_CARD = "#010610"
BG_INPUT = "#081428"; BG_HOVER = "#041228"
FG = "#e0e0e0"; FG_DIM = "#445577"; ACCENT = "#0066cc"
BORDER = "#0a1e3a"

def load_j(p, d):
    try:
        with open(p) as f: return json.load(f)
    except: return d
def save_j(p, d):
    with open(p,"w") as f: json.dump(d, f, indent=2, default=str)

def _stream_ollama(prompt, on_token, on_done, model="qwen2.5:3b"):
    try:
        payload = json.dumps({"model": model, "prompt": prompt, "stream": True}).encode()
        req = urllib.request.Request("http://localhost:11434/api/generate",
                                     data=payload, headers={"Content-Type":"application/json"}, method="POST")
        full = []
        with urllib.request.urlopen(req, timeout=300) as resp:
            for line in resp:
                chunk = json.loads(line.decode())
                token = chunk.get("response","")
                if token:
                    full.append(token)
                    on_token(token)
                if chunk.get("done"): break
        on_done("".join(full).strip(), None)
    except Exception as e:
        on_done(None, str(e))


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SubZero Training")
        self.root.geometry("1020x680")
        self.root.minsize(800, 500)
        self.root.configure(bg=BG)
        self.root.attributes("-alpha", 0.96)
        self.tasks = load_j(TASKS_FILE, [])
        self.trades = load_j(TRADES_FILE, [])
        self._tool_rt = ToolRuntime()
        self._build()
        self.root.mainloop()

    def _build(self):
        # Header
        hdr = tk.Frame(self.root, bg=ACCENT, height=44)
        hdr.pack(fill=tk.X); hdr.pack_propagate(False)
        self._logo_img = None
        if HAS_PIL and LOGO_PATH.exists():
            try:
                img = Image.open(LOGO_PATH).resize((28, 28), Image.LANCZOS)
                self._logo_img = ImageTk.PhotoImage(img)
                tk.Label(hdr, image=self._logo_img, bg=ACCENT).pack(side=tk.LEFT, padx=(10,4))
            except: tk.Label(hdr, text="\u2726", bg=ACCENT, fg="#00aaff", font=("Segoe UI",13)).pack(side=tk.LEFT, padx=(10,4))
        else: tk.Label(hdr, text="\u2726", bg=ACCENT, fg="#00aaff", font=("Segoe UI",13)).pack(side=tk.LEFT, padx=(10,4))
        tk.Label(hdr, text="SUBZERO TRAINING", bg=ACCENT, fg="white", font=("Segoe UI",12,"bold")).pack(side=tk.LEFT)
        self.stlbl = tk.Label(hdr, text="", bg=ACCENT, fg="#cce0ff", font=("Segoe UI",8))
        self.stlbl.pack(side=tk.RIGHT, padx=14); self._upstat()

        # Tab bar + tab frames
        tab_bar = tk.Frame(self.root, bg=BG_PANEL); tab_bar.pack(fill=tk.X)
        self._tab_frames = {}; self._tab_btns = {}
        for name in ["AI Chat","Tasks","Trading"]:
            b = tk.Button(tab_bar, text=name, bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",9,"bold"),
                          relief=tk.FLAT, bd=0, padx=16, pady=5, cursor="hand2",
                          activebackground=BG_HOVER, activeforeground="white",
                          command=lambda n=name: self._show_tab(n))
            b.pack(side=tk.LEFT); self._tab_btns[name] = b
            f = tk.Frame(self.root, bg=BG_PANEL); self._tab_frames[name] = f

        # Tab 1: AI Chat
        t1 = self._tab_frames["AI Chat"]
        tk.Label(t1, text="COMMAND CENTER", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold")).pack(anchor=tk.W, padx=8, pady=(6,2))
        self.chat = tk.Text(t1, bg=BG_CARD, fg=FG, font=("Consolas",10), wrap=tk.WORD, relief=tk.FLAT, bd=0,
                            padx=10, pady=8, insertbackground="white", selectbackground=ACCENT)
        self.chat.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,4)); self.chat.config(state=tk.DISABLED)
        for t,c in [("user","#4499dd"),("sys",FG_DIM),("ai","#00aaff"),("ok","#00cc66"),("err","#ff4444")]:
            self.chat.tag_configure(t, foreground=c)
        ctx = tk.Menu(self.root, tearoff=0, bg=BG_HOVER, fg="white")
        ctx.add_command(label="Copy", command=lambda:self._copy(self.chat))
        ctx.add_command(label="Select All", command=lambda:self._sel(self.chat))
        self.chat.bind("<Button-3>", lambda e: ctx.tk_popup(e.x_root, e.y_root))
        self._msg("SubZero Training ready. AI agent with tasks & trading.\n","sys")
        self._msg("Commands: /tasks, /addtask <name>, /trades, /buy <SYM> <QTY>\n\n","sys")

        inp = tk.Frame(t1, bg=BG_PANEL); inp.pack(fill=tk.X, padx=6, pady=(0,6))
        self.entry = tk.Entry(inp, bg=BG_INPUT, fg=FG, font=("Consolas",10), relief=tk.FLAT, borderwidth=4, insertbackground="white")
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,4))
        self.entry.bind("<Return>", lambda e: self._send()); self.entry.focus_set()
        ictx = tk.Menu(self.root, tearoff=0, bg=BG_HOVER, fg="white")
        ictx.add_command(label="Paste", command=lambda: self.entry.insert(tk.INSERT, self.root.clipboard_get()))
        ictx.add_command(label="Copy", command=lambda: self._copy_entry(self.entry))
        ictx.add_command(label="Clear", command=lambda: self.entry.delete(0, tk.END))
        self.entry.bind("<Button-3>", lambda e: ictx.tk_popup(e.x_root, e.y_root))
        tk.Button(inp, text="Send", bg=ACCENT, fg="white", font=("Segoe UI",9,"bold"),
                  relief=tk.FLAT, activebackground="#004499", cursor="hand2", command=self._send).pack(side=tk.RIGHT)

        # Tab 2: Tasks
        t2 = self._tab_frames["Tasks"]
        tf = tk.Frame(t2, bg=BG_PANEL); tf.pack(fill=tk.X, padx=8, pady=6)
        self.task_entry = tk.Entry(tf, bg=BG_INPUT, fg=FG, font=("Consolas",10), relief=tk.FLAT, borderwidth=4, insertbackground="white")
        self.task_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,4))
        self.task_entry.bind("<Return>", lambda e: self._add_task())
        tk.Button(tf, text="Add", bg="#005522", fg="white", font=("Segoe UI",8,"bold"),
                  relief=tk.FLAT, cursor="hand2", command=self._add_task).pack(side=tk.LEFT, padx=2)
        tk.Button(tf, text="Complete", bg="#886600", fg="white", font=("Segoe UI",8,"bold"),
                  relief=tk.FLAT, cursor="hand2", command=self._complete_task).pack(side=tk.LEFT, padx=2)
        tk.Button(tf, text="Delete", bg="#662222", fg="white", font=("Segoe UI",8,"bold"),
                  relief=tk.FLAT, cursor="hand2", command=self._del_task).pack(side=tk.LEFT, padx=2)

        # Task list with Listbox (replacing Treeview to avoid ttk dependency for styling)
        self.task_list = tk.Listbox(t2, bg=BG_CARD, fg=FG, font=("Consolas",10), relief=tk.FLAT, bd=0,
                                    selectbackground=ACCENT, selectforeground="white", activestyle="none")
        self.task_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0,8))
        self._refresh_tasks()

        # Tab 3: Trading
        t3 = self._tab_frames["Trading"]
        tk.Label(t3, text="SIMULATED TRADING (Demo Only)", bg=BG_PANEL, fg="#ffaa00", font=("Segoe UI",9,"bold")).pack(anchor=tk.W, padx=8, pady=(8,4))
        self.trade_log = tk.Text(t3, bg=BG_CARD, fg=FG, font=("Consolas",10), wrap=tk.WORD, relief=tk.FLAT, bd=0,
                                 padx=10, pady=8, insertbackground="white", selectbackground=ACCENT)
        self.trade_log.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,4)); self.trade_log.config(state=tk.DISABLED)
        for t,c in [("buy","#00cc66"),("sell","#ff4444"),("info","#0088ff"),("dim",FG_DIM)]:
            self.trade_log.tag_configure(t, foreground=c)
        self._tlog("Trade history:\n","info")
        for tr in self.trades:
            self._tlog(f"  {tr.get('action','?')} {tr.get('symbol','?')} x{tr.get('qty',0)} @${tr.get('price',0)}\n",
                       "buy" if tr.get("action")=="BUY" else "sell")

        tif = tk.Frame(t3, bg=BG_PANEL); tif.pack(fill=tk.X, padx=6, pady=(0,6))
        self.tentry = tk.Entry(tif, bg=BG_INPUT, fg=FG, font=("Consolas",10), relief=tk.FLAT, borderwidth=4, insertbackground="white")
        self.tentry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,4))
        self.tentry.bind("<Return>", lambda e: self._trade_cmd())
        tk.Button(tif, text="Execute", bg="#005522", fg="white", font=("Segoe UI",9,"bold"),
                  relief=tk.FLAT, activebackground="#007733", cursor="hand2", command=self._trade_cmd).pack(side=tk.RIGHT)

        self._show_tab("AI Chat")

    def _show_tab(self, name):
        for n, f in self._tab_frames.items():
            f.pack_forget(); self._tab_btns[n].config(bg=BG_PANEL, fg=FG_DIM)
        self._tab_frames[name].pack(fill=tk.BOTH, expand=True)
        self._tab_btns[name].config(bg=ACCENT, fg="white")

    def _msg(self, text, tag="sys"):
        self.chat.config(state=tk.NORMAL); self.chat.insert(tk.END, text, tag); self.chat.see(tk.END); self.chat.config(state=tk.DISABLED)
    def _tlog(self, text, tag="info"):
        self.trade_log.config(state=tk.NORMAL); self.trade_log.insert(tk.END, text, tag); self.trade_log.see(tk.END); self.trade_log.config(state=tk.DISABLED)

    def _send(self):
        raw = self.entry.get().strip()
        if not raw: return
        self.entry.delete(0, tk.END)
        if raw.startswith("/addtask "):
            name = raw[9:].strip()
            self.tasks.append({"title":name,"status":"pending","priority":"medium","created":datetime.now().isoformat()})
            save_j(TASKS_FILE, self.tasks); self._refresh_tasks(); self._msg(f"Task added: {name}\n","ok"); self._upstat(); return
        if raw == "/tasks":
            for t in self.tasks: self._msg(f"  [{t['status']}] {t['title']}\n","ai")
            self._msg("\n","sys"); return
        if raw == "/trades":
            self._msg(f"Total trades: {len(self.trades)}\n\n","sys"); return

        self._msg(f"You: {raw}\n","user"); self._msg("Agent: ","ai")
        prompt = (
            "You are SubZero Training agent. Help with coding, tasks, and trading analysis. Be concise.\n"
            + self._tool_rt.get_system_prompt() + "\n\nUser: " + raw
        )

        def on_token(tok):
            self.root.after(0, lambda t=tok: self._append_stream(t))
        def on_done(result, error):
            def finish():
                if error:
                    self._msg(f"\n[Error: {error}]\n\n","err")
                else:
                    self._msg("\n","ai")
                    tool_calls = self._tool_rt.parse(result or "")
                    if tool_calls:
                        results = self._tool_rt.execute_all(tool_calls)
                        for r in results:
                            self._msg(f"  [{'\u2713' if r.success else '\u2717'} {r.tool_name}] {r.output[:120]}\n", "ok" if r.success else "err")
                    self._msg("\n","sys")
            self.root.after(0, finish)
        threading.Thread(target=_stream_ollama, args=(prompt, on_token, on_done), daemon=True).start()

    def _append_stream(self, tok):
        self.chat.config(state=tk.NORMAL); self.chat.insert(tk.END, tok, "ai"); self.chat.see(tk.END); self.chat.config(state=tk.DISABLED)

    def _add_task(self):
        name = self.task_entry.get().strip()
        if not name: return
        self.task_entry.delete(0, tk.END)
        self.tasks.append({"title":name,"status":"pending","priority":"medium","created":datetime.now().isoformat()})
        save_j(TASKS_FILE, self.tasks); self._refresh_tasks(); self._upstat()

    def _complete_task(self):
        sel = self.task_list.curselection()
        if sel:
            idx = sel[0]
            if 0 <= idx < len(self.tasks): self.tasks[idx]["status"] = "done"
            save_j(TASKS_FILE, self.tasks); self._refresh_tasks()

    def _del_task(self):
        sel = self.task_list.curselection()
        if sel:
            idx = sel[0]
            if 0 <= idx < len(self.tasks): self.tasks.pop(idx)
            save_j(TASKS_FILE, self.tasks); self._refresh_tasks(); self._upstat()

    def _refresh_tasks(self):
        self.task_list.delete(0, tk.END)
        for t in self.tasks:
            ico = "\u2713" if t["status"]=="done" else "\u25cb"
            self.task_list.insert(tk.END, f"  {ico}  {t['title']}  [{t.get('priority','')}]  {t.get('created','')[:16]}")

    def _trade_cmd(self):
        raw = self.tentry.get().strip()
        if not raw: return
        self.tentry.delete(0, tk.END)
        parts = raw.split()
        if len(parts) >= 3 and parts[0].upper() in ("BUY","SELL"):
            action, sym = parts[0].upper(), parts[1].upper()
            try: qty = int(parts[2])
            except: qty = 1
            price = round(random.uniform(50, 500), 2)
            trade = {"action":action,"symbol":sym,"qty":qty,"price":price,"total":round(price*qty,2),
                     "time":datetime.now().isoformat(),"mode":"SIMULATION"}
            self.trades.append(trade); save_j(TRADES_FILE, self.trades)
            tag = "buy" if action=="BUY" else "sell"
            self._tlog(f"[SIM] {action} {qty}x {sym} @${price} = ${trade['total']}\n", tag); self._upstat()
        else:
            self._tlog("Usage: BUY AAPL 10 / SELL TSLA 5\n","dim")

    def _upstat(self):
        pending = sum(1 for t in self.tasks if t["status"]=="pending")
        self.stlbl.config(text=f"Tasks: {pending} pending | Trades: {len(self.trades)}")

    def _copy(self, w):
        try: self.root.clipboard_clear(); self.root.clipboard_append(w.get(tk.SEL_FIRST, tk.SEL_LAST))
        except: pass
    def _sel(self, w):
        w.config(state=tk.NORMAL); w.tag_add(tk.SEL,"1.0",tk.END); w.config(state=tk.DISABLED)
    def _copy_entry(self, e):
        try:
            if e.selection_present(): self.root.clipboard_clear(); self.root.clipboard_append(e.selection_get())
        except: pass

if __name__=="__main__": App()
