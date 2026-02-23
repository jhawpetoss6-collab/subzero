"""SubZero DualCore — Front-end + Back-end dual AI."""
import tkinter as tk
import json, os, threading, urllib.request
from datetime import datetime
from collections import deque
from pathlib import Path
from sz_runtime import ToolRuntime

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

LOGO_PATH = Path(__file__).parent / "logo.png"
DATA_HOME = os.path.join(os.path.expanduser("~"), ".subzero", "dualcore")
os.makedirs(DATA_HOME, exist_ok=True)

BG = "#000000"; BG_PANEL = "#020810"; BG_CARD = "#010610"
BG_INPUT = "#081428"; BG_HOVER = "#041228"
FG = "#e0e0e0"; FG_DIM = "#445577"; ACCENT = "#0066cc"
BORDER = "#0a1e3a"

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
        self.root.title("SubZero DualCore")
        self.root.geometry("1020x680")
        self.root.minsize(800, 500)
        self.root.configure(bg=BG)
        self.root.attributes("-alpha", 0.96)
        self.backend_queue = deque()
        self.thoughts = deque(maxlen=50)
        self.watchdog_goals = []
        self.completed = 0
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
        tk.Label(hdr, text="SUBZERO DUALCORE", bg=ACCENT, fg="white", font=("Segoe UI",12,"bold")).pack(side=tk.LEFT)
        self.stlbl = tk.Label(hdr, text="Front-End: Ready | Back-End: Idle", bg=ACCENT, fg="#cce0ff", font=("Segoe UI",8))
        self.stlbl.pack(side=tk.RIGHT, padx=14)

        # Body paned
        body = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=BORDER, sashwidth=4, sashrelief=tk.FLAT)
        body.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        left = tk.Frame(body, bg=BG_PANEL); right = tk.Frame(body, bg=BG_PANEL)
        body.add(left, stretch="always", minsize=420); body.add(right, stretch="never", minsize=300, width=340)

        # Left: Front-End Chat
        tk.Label(left, text="FRONT-END \u2022 Instant Responses", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold")).pack(anchor=tk.W, padx=8, pady=(6,2))
        self.chat = tk.Text(left, bg=BG_CARD, fg=FG, font=("Consolas",10), wrap=tk.WORD, relief=tk.FLAT, bd=0,
                            padx=10, pady=8, insertbackground="white", selectbackground=ACCENT)
        self.chat.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,4)); self.chat.config(state=tk.DISABLED)
        for t,c in [("user","#4499dd"),("sys",FG_DIM),("fe","#00aaff"),("be","#66bbff"),("wd","#ffaa00")]:
            self.chat.tag_configure(t, foreground=c)
        ctx = tk.Menu(self.root, tearoff=0, bg=BG_HOVER, fg="white")
        ctx.add_command(label="Copy", command=lambda:self._copy(self.chat))
        ctx.add_command(label="Select All", command=lambda:self._sel(self.chat))
        self.chat.bind("<Button-3>", lambda e: ctx.tk_popup(e.x_root, e.y_root))
        self._msg("DualCore online. I think and talk simultaneously!\n","sys")
        self._msg("Commands: status, thoughts, watch <goal>, watchdog\n\n","sys")

        inp = tk.Frame(left, bg=BG_PANEL); inp.pack(fill=tk.X, padx=6, pady=(0,6))
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

        # Right: Tabs (Back-End / Thoughts / Watchdog)
        tab_bar = tk.Frame(right, bg=BG_PANEL); tab_bar.pack(fill=tk.X)
        self._tab_frames = {}; self._tab_btns = {}
        for name in ["Back-End","Thoughts","Watchdog"]:
            b = tk.Button(tab_bar, text=name, bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold"),
                          relief=tk.FLAT, bd=0, padx=12, pady=4, cursor="hand2",
                          activebackground=BG_HOVER, activeforeground="white",
                          command=lambda n=name: self._show_tab(n))
            b.pack(side=tk.LEFT)
            self._tab_btns[name] = b
            f = tk.Frame(right, bg=BG_PANEL)
            self._tab_frames[name] = f

        # Back-End tab
        t1 = self._tab_frames["Back-End"]
        tk.Label(t1, text="BACK-END QUEUE", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold")).pack(anchor=tk.W, padx=8, pady=(6,4))
        self.be_list = tk.Text(t1, bg=BG_CARD, fg=FG, font=("Consolas",9), wrap=tk.WORD, relief=tk.FLAT, bd=0, padx=8, pady=4)
        self.be_list.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,6)); self.be_list.config(state=tk.DISABLED)
        for t,c in [("active","#00aaff"),("done","#00cc66"),("dim",FG_DIM)]: self.be_list.tag_configure(t, foreground=c)

        # Thoughts tab
        t2 = self._tab_frames["Thoughts"]
        tk.Label(t2, text="THOUGHT STREAM", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold")).pack(anchor=tk.W, padx=8, pady=(6,4))
        self.thought_log = tk.Text(t2, bg=BG_CARD, fg="#0088ff", font=("Consolas",9), wrap=tk.WORD, relief=tk.FLAT, bd=0, padx=8, pady=4)
        self.thought_log.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,6)); self.thought_log.config(state=tk.DISABLED)

        # Watchdog tab
        t3 = self._tab_frames["Watchdog"]
        tk.Label(t3, text="WATCHDOG MONITORING", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold")).pack(anchor=tk.W, padx=8, pady=(6,4))
        self.wd_log = tk.Text(t3, bg=BG_CARD, fg="#ffaa00", font=("Consolas",9), wrap=tk.WORD, relief=tk.FLAT, bd=0, padx=8, pady=4)
        self.wd_log.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,4)); self.wd_log.config(state=tk.DISABLED)
        wf = tk.Frame(t3, bg=BG_PANEL); wf.pack(fill=tk.X, padx=6, pady=(0,6))
        self.wd_entry = tk.Entry(wf, bg=BG_INPUT, fg=FG, font=("Consolas",9), relief=tk.FLAT, borderwidth=4, insertbackground="white")
        self.wd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,4))
        tk.Button(wf, text="Add Goal", bg="#886600", fg="white", font=("Segoe UI",8,"bold"),
                  relief=tk.FLAT, activebackground="#aa8800", cursor="hand2", command=self._add_goal).pack(side=tk.RIGHT)

        self._show_tab("Back-End")

    def _show_tab(self, name):
        for n, f in self._tab_frames.items():
            f.pack_forget()
            self._tab_btns[n].config(bg=BG_PANEL, fg=FG_DIM)
        self._tab_frames[name].pack(fill=tk.BOTH, expand=True)
        self._tab_btns[name].config(bg=ACCENT, fg="white")

    def _msg(self, text, tag="sys"):
        self.chat.config(state=tk.NORMAL); self.chat.insert(tk.END, text, tag); self.chat.see(tk.END); self.chat.config(state=tk.DISABLED)
    def _think(self, t):
        self.thoughts.append(f"[{datetime.now().strftime('%H:%M:%S')}] {t}")
        self.thought_log.config(state=tk.NORMAL); self.thought_log.insert(tk.END, f"{self.thoughts[-1]}\n"); self.thought_log.see(tk.END); self.thought_log.config(state=tk.DISABLED)
    def _be_update(self):
        self.be_list.config(state=tk.NORMAL); self.be_list.delete("1.0", tk.END)
        if not self.backend_queue: self.be_list.insert(tk.END, "No tasks in queue\n","dim")
        for t in self.backend_queue:
            tag = "active" if t.get("status")=="working" else "done" if t.get("status")=="done" else "dim"
            self.be_list.insert(tk.END, f"[{t.get('status','queued')}] {t.get('task','')}\n", tag)
        self.be_list.config(state=tk.DISABLED)

    def _send(self):
        raw = self.entry.get().strip()
        if not raw: return
        self.entry.delete(0, tk.END); self._msg(f"You: {raw}\n","user")

        if raw.lower() == "status":
            idle = len([t for t in self.backend_queue if t.get("status")!="done"])
            self._msg(f"Front-End: Ready | Back-End: {idle} tasks | Completed: {self.completed}\n\n","sys"); return
        if raw.lower() == "thoughts":
            for t in list(self.thoughts)[-5:]: self._msg(f"  {t}\n","sys")
            self._msg("\n","sys"); return
        if raw.lower().startswith("watch "):
            goal = raw[6:].strip(); self.watchdog_goals.append({"goal":goal,"checks":0,"status":"monitoring"})
            self._msg(f"Watchdog monitoring: {goal}\n","wd")
            self.wd_log.config(state=tk.NORMAL); self.wd_log.insert(tk.END, f"+ Monitoring: {goal}\n"); self.wd_log.config(state=tk.DISABLED); return
        if raw.lower() == "watchdog":
            for g in self.watchdog_goals: self._msg(f"  [{g['status']}] {g['goal']} (checks: {g['checks']})\n","wd")
            self._msg("\n","sys"); return

        # Front-End: instant streaming response
        self._think(f"Front-End processing: {raw[:40]}")
        needs_backend = any(kw in raw.lower() for kw in ["create","build","analyze","explain","research","write","code"])
        if needs_backend:
            self._msg("Front-End: I'll respond now while my Back-End works on the details.\n","fe")
            task = {"task":raw,"status":"queued","queued":datetime.now().isoformat()}
            self.backend_queue.append(task); self._be_update()
            self._think(f"Back-End queued: {raw[:30]}")
            threading.Thread(target=self._backend_work, args=(task,), daemon=True).start()
        self._msg("Front-End: ","fe")
        tool_prompt = self._tool_rt.get_system_prompt()
        prompt = f"You are SubZero DualCore front-end. {tool_prompt}\nGive a quick, helpful response. Be concise.\n\nUser: {raw}"

        def on_token(tok):
            self.root.after(0, lambda t=tok: self._append_stream(t))
        def on_done(result, error):
            def finish():
                if error: self._msg(f"\n[Error: {error}]\n\n","sys")
                else:
                    self._msg("\n","fe")
                    # Execute tool calls
                    calls = self._tool_rt.parse(result or "")
                    if calls:
                        results = self._tool_rt.execute_all(calls)
                        for r in results:
                            s = "\u2713" if r.success else "\u2717"
                            self._msg(f"  [{s} {r.tool_name}] {r.output[:120]}\n", "fe" if r.success else "sys")
                    self._msg("\n","fe")
            self.root.after(0, finish)
        threading.Thread(target=_stream_ollama, args=(prompt, on_token, on_done), daemon=True).start()

    def _append_stream(self, tok):
        self.chat.config(state=tk.NORMAL); self.chat.insert(tk.END, tok, "fe"); self.chat.see(tk.END); self.chat.config(state=tk.DISABLED)

    def _backend_work(self, task):
        self.root.after(0, lambda: self._think(f"Back-End started: {task['task'][:30]}"))
        task["status"] = "working"; self.root.after(0, self._be_update)
        self.root.after(0, lambda: self.stlbl.config(text="Front-End: Ready | Back-End: Working..."))
        prompt = f"Deep analysis of: {task['task']}. Give detailed result in 2-3 sentences."
        result_text = []
        def on_token(tok): result_text.append(tok)
        def on_done(result, error):
            final = result or "Back-end processing complete."
            task["status"] = "done"; self.completed += 1
            def done():
                self._be_update(); self._think(f"Back-End complete: {task['task'][:30]}")
                self._msg(f"Back-End: {final[:200]}\n\n","be")
                self.stlbl.config(text=f"Front-End: Ready | Back-End: Idle | Done: {self.completed}")
            self.root.after(0, done)
        threading.Thread(target=_stream_ollama, args=(prompt, on_token, on_done), daemon=True).start()

    def _add_goal(self):
        goal = self.wd_entry.get().strip()
        if not goal: return
        self.wd_entry.delete(0, tk.END)
        self.watchdog_goals.append({"goal":goal,"checks":0,"status":"monitoring"})
        self.wd_log.config(state=tk.NORMAL); self.wd_log.insert(tk.END, f"+ Monitoring: {goal}\n"); self.wd_log.config(state=tk.DISABLED)

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
