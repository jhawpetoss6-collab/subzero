"""SubZero Learn — AI tutor with learning modules."""
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
LEARN_HOME = os.path.join(os.path.expanduser("~"), ".subzero", "learn")
PROG_FILE = os.path.join(LEARN_HOME, "progress.json")
os.makedirs(LEARN_HOME, exist_ok=True)

BG = "#000000"; BG_PANEL = "#020810"; BG_CARD = "#010610"
BG_INPUT = "#081428"; BG_HOVER = "#041228"
FG = "#e0e0e0"; FG_DIM = "#445577"; ACCENT = "#0066cc"
BORDER = "#0a1e3a"

MODULES = [
    ("llm_basics","LLM Fundamentals","What is a language model, key components, training process"),
    ("llm_architecture","Transformer Deep Dive","Self-attention, multi-head attention, feed-forward networks"),
    ("llm_training","Train Your Own Model","From-scratch training, fine-tuning with LoRA, quantization"),
    ("llm_code","Training Code","Complete working scripts for training and fine-tuning"),
    ("swarm_basics","Swarm Intelligence","Agent types, swarm patterns, communication methods"),
    ("swarm_implementation","Building Swarms","Agent class, coordinator, JSON/in-memory patterns"),
    ("swarm_advanced","Advanced Techniques","Ant colony, particle swarm, consensus, multi-level"),
]

def load_prog():
    try:
        with open(PROG_FILE) as f: return json.load(f)
    except: return {"completed":[],"last":""}
def save_prog(p):
    with open(PROG_FILE,"w") as f: json.dump(p,f,indent=2)

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
        self.root.title("SubZero Learn")
        self.root.geometry("1020x680")
        self.root.minsize(800, 500)
        self.root.configure(bg=BG)
        self.root.attributes("-alpha", 0.96)
        self.prog = load_prog()
        self.cur_mod = None
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
        tk.Label(hdr, text="SUBZERO LEARN", bg=ACCENT, fg="white", font=("Segoe UI",12,"bold")).pack(side=tk.LEFT)
        self.plbl = tk.Label(hdr, text="", bg=ACCENT, fg="#cce0ff", font=("Segoe UI",8))
        self.plbl.pack(side=tk.RIGHT, padx=14)
        self._upprog()

        # Body paned
        body = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=BORDER, sashwidth=4, sashrelief=tk.FLAT)
        body.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        left = tk.Frame(body, bg=BG_PANEL); right = tk.Frame(body, bg=BG_PANEL)
        body.add(left, stretch="always", minsize=340); body.add(right, stretch="always", minsize=380)

        # Left: Chat
        tk.Label(left, text="AI ASSISTANT", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold")).pack(anchor=tk.W, padx=8, pady=(6,2))
        self.chat = tk.Text(left, bg=BG_CARD, fg=FG, font=("Consolas",10), wrap=tk.WORD, relief=tk.FLAT, bd=0,
                            padx=10, pady=8, insertbackground="white", selectbackground=ACCENT)
        self.chat.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,4)); self.chat.config(state=tk.DISABLED)
        for t,c in [("user","#4499dd"),("sys",FG_DIM),("ai","#00aaff"),("ok","#00aaff")]:
            self.chat.tag_configure(t, foreground=c)
        ctx = tk.Menu(self.root, tearoff=0, bg=BG_HOVER, fg="white")
        ctx.add_command(label="Copy", command=lambda:self._copy(self.chat))
        ctx.add_command(label="Select All", command=lambda:self._sel(self.chat))
        self.chat.bind("<Button-3>", lambda e: ctx.tk_popup(e.x_root, e.y_root))
        self._msg("SubZero Learn ready. Ask questions or browse modules.\n\n","sys")

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

        # Right: Modules + Viewer
        tk.Label(right, text="LEARNING MODULES", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold")).pack(anchor=tk.W, padx=8, pady=(6,4))
        mf = tk.Frame(right, bg=BG_PANEL); mf.pack(fill=tk.X, padx=6)
        self.mbtn = {}
        for mid, title, desc in MODULES:
            done = mid in self.prog.get("completed",[])
            b = tk.Button(mf, text=f"{'✓' if done else '○'} {title}", anchor=tk.W,
                          bg=BG_CARD if not done else "#041228", fg="#00aaff" if done else FG,
                          font=("Segoe UI",9), relief=tk.FLAT, bd=1, padx=8, pady=3,
                          activebackground=BG_HOVER, activeforeground="white", cursor="hand2",
                          command=lambda m=mid: self._load_mod(m))
            b.pack(fill=tk.X, pady=1)
            b.bind("<Enter>", lambda e, w=b: w.config(bg=BG_HOVER))
            b.bind("<Leave>", lambda e, w=b, d=done: w.config(bg="#041228" if d else BG_CARD))
            self.mbtn[mid] = b

        tk.Frame(right, bg=BORDER, height=1).pack(fill=tk.X, padx=6, pady=6)
        tk.Label(right, text="MODULE CONTENT", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold")).pack(anchor=tk.W, padx=8, pady=(0,4))
        vf = tk.Frame(right, bg=BG_PANEL); vf.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,4))
        self.viewer = tk.Text(vf, bg=BG_CARD, fg=FG, font=("Consolas",9), wrap=tk.WORD, relief=tk.FLAT, bd=0,
                              padx=10, pady=6, insertbackground="white", selectbackground=ACCENT)
        vsb = tk.Scrollbar(vf, orient=tk.VERTICAL, command=self.viewer.yview, bg=BG_PANEL, troughcolor=BG_CARD)
        self.viewer.configure(yscrollcommand=vsb.set)
        self.viewer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.viewer.config(state=tk.DISABLED)
        vctx = tk.Menu(self.root, tearoff=0, bg=BG_HOVER, fg="white")
        vctx.add_command(label="Copy", command=lambda:self._copy(self.viewer))
        vctx.add_command(label="Select All", command=lambda:self._sel(self.viewer))
        self.viewer.bind("<Button-3>", lambda e: vctx.tk_popup(e.x_root, e.y_root))

        bf = tk.Frame(right, bg=BG_PANEL); bf.pack(fill=tk.X, padx=6, pady=(0,6))
        tk.Button(bf, text="Mark Complete \u2713", bg="#005522", fg="white", font=("Segoe UI",9,"bold"),
                  relief=tk.FLAT, activebackground="#007733", cursor="hand2", command=self._mark).pack(side=tk.LEFT)

    def _load_mod(self, mid):
        self.cur_mod = mid
        title = next((t for m,t,d in MODULES if m==mid), mid)
        desc = next((d for m,t,d in MODULES if m==mid), "")
        prompt = f"You are a technical educator. Write a detailed lesson on: {title}. Topics: {desc}. Use numbered sections and code examples. Under 500 words."
        self.viewer.config(state=tk.NORMAL); self.viewer.delete("1.0", tk.END)
        self.viewer.insert("1.0", f"\u2550\u2550\u2550 {title.upper()} \u2550\u2550\u2550\n\n"); self.viewer.config(state=tk.DISABLED)

        def on_token(tok):
            self.root.after(0, lambda t=tok: self._vappend(t))
        def on_done(result, error):
            def finish():
                if error:
                    self.viewer.config(state=tk.NORMAL); self.viewer.delete("1.0", tk.END)
                    self.viewer.insert("1.0", f"[Error: {error}]"); self.viewer.config(state=tk.DISABLED)
            self.root.after(0, finish)
        threading.Thread(target=_stream_ollama, args=(prompt, on_token, on_done), daemon=True).start()

    def _vappend(self, tok):
        self.viewer.config(state=tk.NORMAL); self.viewer.insert(tk.END, tok); self.viewer.see(tk.END); self.viewer.config(state=tk.DISABLED)

    def _mark(self):
        if not self.cur_mod: return
        if self.cur_mod not in self.prog["completed"]:
            self.prog["completed"].append(self.cur_mod); save_prog(self.prog)
            title = next((t for m,t,d in MODULES if m==self.cur_mod), self.cur_mod)
            self.mbtn[self.cur_mod].config(text=f"\u2713 {title}", bg="#041228", fg="#00aaff")
            self._msg(f"Module '{self.cur_mod}' complete! \u2713\n","ok"); self._upprog()

    def _upprog(self):
        self.plbl.config(text=f"Progress: {len(self.prog.get('completed',[]))}/{len(MODULES)} modules")

    def _msg(self, text, tag="sys"):
        self.chat.config(state=tk.NORMAL); self.chat.insert(tk.END, text, tag); self.chat.see(tk.END); self.chat.config(state=tk.DISABLED)

    def _send(self):
        raw = self.entry.get().strip()
        if not raw: return
        self.entry.delete(0, tk.END); self._msg(f"You: {raw}\n","user"); self._msg("Tutor: ","ai")
        prompt = (
            "You are SubZero Learn, an AI tutor for software dev, LLMs, and swarm systems. Be helpful and concise.\n"
            + self._tool_rt.get_system_prompt() + "\n\nUser: " + raw
        )

        def on_token(tok):
            self.root.after(0, lambda t=tok: self._append_stream(t))
        def on_done(result, error):
            def finish():
                if error:
                    self._msg(f"\n[Error: {error}]\n\n","sys")
                else:
                    self._msg("\n","ai")
                    tool_calls = self._tool_rt.parse(result or "")
                    if tool_calls:
                        results = self._tool_rt.execute_all(tool_calls)
                        for r in results:
                            self._msg(f"  [{'\u2713' if r.success else '\u2717'} {r.tool_name}] {r.output[:120]}\n", "ok" if r.success else "sys")
                    self._msg("\n","sys")
            self.root.after(0, finish)
        threading.Thread(target=_stream_ollama, args=(prompt, on_token, on_done), daemon=True).start()

    def _append_stream(self, tok):
        self.chat.config(state=tk.NORMAL); self.chat.insert(tk.END, tok, "ai"); self.chat.see(tk.END); self.chat.config(state=tk.DISABLED)

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
