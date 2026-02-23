"""SubZero Recursive — Self-improving AI with knowledge base."""
import tkinter as tk
import json, os, threading, urllib.request
from datetime import datetime
from pathlib import Path
from sz_runtime import ToolRuntime

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

LOGO_PATH = Path(__file__).parent / "logo.png"
DATA_HOME = os.path.join(os.path.expanduser("~"), ".subzero", "recursive")
os.makedirs(DATA_HOME, exist_ok=True)
KB_FILE = os.path.join(DATA_HOME, "knowledge_base.json")

BG = "#000000"; BG_PANEL = "#020810"; BG_CARD = "#010610"
BG_INPUT = "#081428"; BG_HOVER = "#041228"
FG = "#e0e0e0"; FG_DIM = "#445577"; ACCENT = "#0066cc"
BORDER = "#0a1e3a"

MODULES = [
    {"name":"Pattern Recognition","desc":"Identify and store recurring patterns from conversations"},
    {"name":"Success Analysis","desc":"Record and analyze successful task completions"},
    {"name":"Failure Recovery","desc":"Learn from failures and build recovery strategies"},
    {"name":"Self-Reflection","desc":"Periodic introspection on knowledge and capabilities"},
    {"name":"Knowledge Synthesis","desc":"Combine patterns into higher-order understanding"},
    {"name":"Adaptive Response","desc":"Adjust behavior based on accumulated learning"},
]

def _load_kb():
    try:
        with open(KB_FILE,"r") as f: return json.load(f)
    except: return {"patterns":[],"successes":[],"failures":[],"reflections":[]}
def _save_kb(kb):
    with open(KB_FILE,"w") as f: json.dump(kb,f,indent=2)

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
        self.root.title("SubZero Recursive")
        self.root.geometry("1040x700")
        self.root.minsize(820, 520)
        self.root.configure(bg=BG)
        self.root.attributes("-alpha", 0.96)
        self.kb = _load_kb()
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
        tk.Label(hdr, text="SUBZERO RECURSIVE", bg=ACCENT, fg="white", font=("Segoe UI",12,"bold")).pack(side=tk.LEFT)
        self.stlbl = tk.Label(hdr, text="", bg=ACCENT, fg="#cce0ff", font=("Segoe UI",8))
        self.stlbl.pack(side=tk.RIGHT, padx=14); self._upstat()

        # Body paned
        body = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=BORDER, sashwidth=4, sashrelief=tk.FLAT)
        body.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        left = tk.Frame(body, bg=BG_PANEL); right = tk.Frame(body, bg=BG_PANEL)
        body.add(left, stretch="always", minsize=420); body.add(right, stretch="never", minsize=300, width=360)

        # Left: Chat
        tk.Label(left, text="RECURSIVE CHAT \u2022 Self-Improving", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold")).pack(anchor=tk.W, padx=8, pady=(6,2))
        self.chat = tk.Text(left, bg=BG_CARD, fg=FG, font=("Consolas",10), wrap=tk.WORD, relief=tk.FLAT, bd=0,
                            padx=10, pady=8, insertbackground="white", selectbackground=ACCENT)
        self.chat.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,4)); self.chat.config(state=tk.DISABLED)
        for t,c in [("user","#4499dd"),("sys",FG_DIM),("ai","#00aaff"),("learn","#0088ff"),("reflect","#66bbff")]:
            self.chat.tag_configure(t, foreground=c)
        ctx = tk.Menu(self.root, tearoff=0, bg=BG_HOVER, fg="white")
        ctx.add_command(label="Copy", command=lambda:self._copy(self.chat))
        ctx.add_command(label="Select All", command=lambda:self._sel(self.chat))
        self.chat.bind("<Button-3>", lambda e: ctx.tk_popup(e.x_root, e.y_root))
        self._msg("Recursive AI online. I learn from every interaction.\n","sys")
        self._msg("Commands: kb, reflect, patterns, learn <topic>, clear kb\n\n","sys")

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

        # Right: Tabs — Knowledge / Modules / Reflections
        tab_bar = tk.Frame(right, bg=BG_PANEL); tab_bar.pack(fill=tk.X)
        self._tab_frames = {}; self._tab_btns = {}
        for name in ["Knowledge","Modules","Reflections"]:
            b = tk.Button(tab_bar, text=name, bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold"),
                          relief=tk.FLAT, bd=0, padx=12, pady=4, cursor="hand2",
                          activebackground=BG_HOVER, activeforeground="white",
                          command=lambda n=name: self._show_tab(n))
            b.pack(side=tk.LEFT); self._tab_btns[name] = b
            f = tk.Frame(right, bg=BG_PANEL); self._tab_frames[name] = f

        # Knowledge tab
        t1 = self._tab_frames["Knowledge"]
        tk.Label(t1, text="KNOWLEDGE BASE", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold")).pack(anchor=tk.W, padx=8, pady=(6,4))
        self.kb_view = tk.Text(t1, bg=BG_CARD, fg="#0088ff", font=("Consolas",9), wrap=tk.WORD, relief=tk.FLAT, bd=0, padx=8, pady=4)
        self.kb_view.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,4)); self.kb_view.config(state=tk.DISABLED)
        for t,c in [("hdr","#4499dd"),("ok","#00cc66"),("fail","#ff4444"),("dim",FG_DIM)]:
            self.kb_view.tag_configure(t, foreground=c)
        bf = tk.Frame(t1, bg=BG_PANEL); bf.pack(fill=tk.X, padx=6, pady=(0,6))
        tk.Button(bf, text="Refresh", bg="#003366", fg="white", font=("Segoe UI",8,"bold"),
                  relief=tk.FLAT, cursor="hand2", command=self._refresh_kb).pack(side=tk.LEFT, padx=(0,4))
        tk.Button(bf, text="Export", bg=BG_HOVER, fg=FG, font=("Segoe UI",8,"bold"),
                  relief=tk.FLAT, cursor="hand2", command=self._export_kb).pack(side=tk.LEFT)
        self._refresh_kb()

        # Modules tab
        t2 = self._tab_frames["Modules"]
        tk.Label(t2, text="LEARNING MODULES", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold")).pack(anchor=tk.W, padx=8, pady=(6,4))
        for m in MODULES:
            f = tk.Frame(t2, bg=BG_PANEL); f.pack(fill=tk.X, padx=6, pady=2)
            tk.Label(f, text="\u25cf", bg=BG_PANEL, fg="#0088ff", font=("Segoe UI",8)).pack(side=tk.LEFT, padx=(0,6))
            tk.Label(f, text=m["name"], bg=BG_PANEL, fg=FG, font=("Segoe UI",9,"bold")).pack(side=tk.LEFT)
            tk.Label(f, text=f"  {m['desc']}", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",7)).pack(side=tk.LEFT, padx=4)

        # Reflections tab
        t3 = self._tab_frames["Reflections"]
        tk.Label(t3, text="SELF-REFLECTION LOG", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold")).pack(anchor=tk.W, padx=8, pady=(6,4))
        self.ref_log = tk.Text(t3, bg=BG_CARD, fg="#66bbff", font=("Consolas",9), wrap=tk.WORD, relief=tk.FLAT, bd=0, padx=8, pady=4)
        self.ref_log.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,4)); self.ref_log.config(state=tk.DISABLED)
        tk.Button(t3, text="Trigger Reflection", bg="#553300", fg="white", font=("Segoe UI",9,"bold"),
                  relief=tk.FLAT, activebackground="#775500", cursor="hand2", command=self._do_reflect).pack(padx=6, pady=(0,6), anchor=tk.W)

        self._show_tab("Knowledge")

    def _show_tab(self, name):
        for n, f in self._tab_frames.items():
            f.pack_forget(); self._tab_btns[n].config(bg=BG_PANEL, fg=FG_DIM)
        self._tab_frames[name].pack(fill=tk.BOTH, expand=True)
        self._tab_btns[name].config(bg=ACCENT, fg="white")

    def _upstat(self):
        kb = self.kb
        self.stlbl.config(text=f"KB: {len(kb['patterns'])}P {len(kb['successes'])}S {len(kb['failures'])}F")

    def _msg(self, text, tag="sys"):
        self.chat.config(state=tk.NORMAL); self.chat.insert(tk.END, text, tag); self.chat.see(tk.END); self.chat.config(state=tk.DISABLED)

    def _refresh_kb(self):
        self.kb_view.config(state=tk.NORMAL); self.kb_view.delete("1.0", tk.END)
        self.kb_view.insert(tk.END, f"Patterns ({len(self.kb['patterns'])})\n","hdr")
        for p in self.kb["patterns"][-10:]: self.kb_view.insert(tk.END, f"  \u2022 {p}\n","dim")
        self.kb_view.insert(tk.END, f"\nSuccesses ({len(self.kb['successes'])})\n","hdr")
        for s in self.kb["successes"][-10:]: self.kb_view.insert(tk.END, f"  \u2713 {s}\n","ok")
        self.kb_view.insert(tk.END, f"\nFailures ({len(self.kb['failures'])})\n","hdr")
        for f in self.kb["failures"][-10:]: self.kb_view.insert(tk.END, f"  \u2717 {f}\n","fail")
        self.kb_view.config(state=tk.DISABLED); self._upstat()

    def _export_kb(self):
        _save_kb(self.kb); self._msg(f"Knowledge base exported to {KB_FILE}\n","learn")

    def _send(self):
        raw = self.entry.get().strip()
        if not raw: return
        self.entry.delete(0, tk.END); self._msg(f"You: {raw}\n","user")
        lo = raw.lower()

        if lo == "kb":
            self._msg(f"Patterns: {len(self.kb['patterns'])} | Successes: {len(self.kb['successes'])} | Failures: {len(self.kb['failures'])}\n\n","learn"); return
        if lo == "reflect": self._do_reflect(); return
        if lo == "patterns":
            for p in self.kb["patterns"][-5:]: self._msg(f"  \u2022 {p}\n","learn")
            self._msg("\n","sys"); return
        if lo.startswith("learn "):
            topic = raw[6:].strip(); self._msg(f"Learning about: {topic}...\n","learn")
            threading.Thread(target=self._learn_topic, args=(topic,), daemon=True).start(); return
        if lo == "clear kb":
            self.kb = {"patterns":[],"successes":[],"failures":[],"reflections":[]}; _save_kb(self.kb)
            self._refresh_kb(); self._msg("Knowledge base cleared.\n\n","sys"); return

        # Regular chat with learning
        relevant = self._get_relevant(raw)
        self._msg("AI: ","ai")
        ctx_str = ""
        if relevant: ctx_str = f"\n\nRelevant knowledge from past interactions:\n" + "\n".join(f"- {r}" for r in relevant)
        prompt = f"You are SubZero Recursive, a self-improving AI. Be helpful and note any patterns you observe.{ctx_str}\n\nUser: {raw}"

        def on_token(tok):
            self.root.after(0, lambda t=tok: self._append_stream(t))
        def on_done(result, error):
            def finish():
                if error:
                    self._msg(f"\n[Error: {error}]\n\n","sys")
                else:
                    self._msg("\n","ai")
                    if relevant: self._msg(f"  (used {len(relevant)} knowledge entries)\n","learn")
                    self._msg("\n","sys")
                    # Learn from interaction
                    pattern = f"Q:{raw[:50]} \u2192 responded successfully"
                    self.kb["patterns"].append(pattern)
                    self.kb["successes"].append(f"[{datetime.now().strftime('%m/%d %H:%M')}] {raw[:60]}")
                    _save_kb(self.kb); self._refresh_kb()
            self.root.after(0, finish)
        threading.Thread(target=_stream_ollama, args=(prompt, on_token, on_done), daemon=True).start()

    def _append_stream(self, tok):
        self.chat.config(state=tk.NORMAL); self.chat.insert(tk.END, tok, "ai"); self.chat.see(tk.END); self.chat.config(state=tk.DISABLED)

    def _get_relevant(self, query):
        q = query.lower(); matches = []
        for p in self.kb["patterns"]:
            if any(w in p.lower() for w in q.split() if len(w) > 3): matches.append(p)
        return matches[:3]

    def _learn_topic(self, topic):
        prompt = f"Summarize key patterns and insights about: {topic}. List 3-5 bullet points."
        result_parts = []
        def on_token(tok): result_parts.append(tok)
        def on_done(result, error):
            text = result or "Could not learn about topic."
            self.kb["patterns"].append(f"Studied: {topic}"); _save_kb(self.kb)
            def up():
                self._msg(f"Learned: {text[:300]}\n\n","learn"); self._refresh_kb()
            self.root.after(0, up)
        threading.Thread(target=_stream_ollama, args=(prompt, on_token, on_done), daemon=True).start()

    def _do_reflect(self):
        self._msg("Self-reflecting...\n","reflect")
        threading.Thread(target=self._reflect_worker, daemon=True).start()

    def _reflect_worker(self):
        summary = f"Patterns: {len(self.kb['patterns'])}, Successes: {len(self.kb['successes'])}, Failures: {len(self.kb['failures'])}"
        prompt = f"You are reflecting on your knowledge. Stats: {summary}. Recent patterns: {self.kb['patterns'][-5:]}. Give a brief 2-sentence self-assessment."
        result_parts = []
        def on_token(tok): result_parts.append(tok)
        def on_done(result, error):
            text = result or "Reflection: knowledge base growing steadily."
            ts = datetime.now().strftime("%H:%M:%S")
            self.kb["reflections"].append(f"[{ts}] {text[:200]}"); _save_kb(self.kb)
            def up():
                self._msg(f"Reflection: {text[:200]}\n\n","reflect")
                self.ref_log.config(state=tk.NORMAL); self.ref_log.insert(tk.END, f"[{ts}] {text[:200]}\n\n"); self.ref_log.see(tk.END); self.ref_log.config(state=tk.DISABLED)
            self.root.after(0, up)
        threading.Thread(target=_stream_ollama, args=(prompt, on_token, on_done), daemon=True).start()

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
