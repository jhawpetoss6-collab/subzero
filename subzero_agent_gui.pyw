"""SubZero Agent — AI agent with tool execution."""
import tkinter as tk
from tkinter import ttk
import json, os, threading, subprocess, urllib.request, re
from datetime import datetime
from pathlib import Path
from sz_runtime import ToolRuntime

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

LOGO_PATH = Path(__file__).parent / "logo.png"
AGENT_HOME = os.path.join(os.path.expanduser("~"), ".subzero", "agent")
MEM_FILE = os.path.join(AGENT_HOME, "memory_agent_gui.json")
os.makedirs(AGENT_HOME, exist_ok=True)

BG = "#000000"; BG_PANEL = "#020810"; BG_CARD = "#010610"
BG_INPUT = "#081428"; BG_HOVER = "#041228"
FG = "#e0e0e0"; FG_DIM = "#445577"; ACCENT = "#0066cc"
BORDER = "#0a1e3a"

TOOLS = [("create_file","Create file"),("edit_file","Edit file"),("read_file","Read file"),
         ("run_command","Run shell cmd"),("run_python","Run Python"),("list_files","List dir")]

def load_mem():
    try:
        with open(MEM_FILE) as f: return json.load(f)
    except: return {"tasks":0,"ok":[],"fail":[]}
def save_mem(m):
    with open(MEM_FILE,"w") as f: json.dump(m,f,indent=2,default=str)


def _stream_ollama(prompt, on_token, on_done, model="qwen2.5:3b"):
    """Stream Ollama response token-by-token."""
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
        self.root.title("SubZero Agent")
        self.root.geometry("960x660")
        self.root.minsize(760, 480)
        self.root.configure(bg=BG)
        self.root.attributes("-alpha", 0.96)
        self.mem = load_mem()
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
        tk.Label(hdr, text="SUBZERO AGENT", bg=ACCENT, fg="white", font=("Segoe UI",12,"bold")).pack(side=tk.LEFT)
        self.stat = tk.Label(hdr, text="", bg=ACCENT, fg="#cce0ff", font=("Segoe UI",8))
        self.stat.pack(side=tk.RIGHT, padx=14)
        self._upstat()

        # Body paned
        body = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=BORDER, sashwidth=4, sashrelief=tk.FLAT)
        body.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        left = tk.Frame(body, bg=BG_PANEL); right = tk.Frame(body, bg=BG_PANEL)
        body.add(left, stretch="always", minsize=400); body.add(right, stretch="never", minsize=220, width=260)

        # Left: Chat
        tk.Label(left, text="COMMAND CENTER", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold")).pack(anchor=tk.W, padx=8, pady=(6,2))
        self.chat = tk.Text(left, bg=BG_CARD, fg=FG, font=("Consolas",10), wrap=tk.WORD, relief=tk.FLAT, bd=0,
                            padx=10, pady=8, insertbackground="white", selectbackground=ACCENT)
        self.chat.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,4)); self.chat.config(state=tk.DISABLED)
        for t,c in [("user","#4499dd"),("sys",FG_DIM),("ai","#00aaff"),("ok","#00aaff"),("err","#ff4444")]:
            self.chat.tag_configure(t, foreground=c)
        # Right-click
        ctx = tk.Menu(self.root, tearoff=0, bg=BG_HOVER, fg="white")
        ctx.add_command(label="Copy", command=lambda:self._copy(self.chat))
        ctx.add_command(label="Select All", command=lambda:self._sel(self.chat))
        self.chat.bind("<Button-3>", lambda e: ctx.tk_popup(e.x_root, e.y_root))

        self._msg("SubZero Agent ready. Ask me anything or give a task.\n","sys")
        self._msg("Tools: create_file, edit_file, read_file, run_command, run_python, list_files\n\n","sys")

        inp = tk.Frame(left, bg=BG_PANEL); inp.pack(fill=tk.X, padx=6, pady=(0,6))
        self.entry = tk.Entry(inp, bg=BG_INPUT, fg=FG, font=("Consolas",10), relief=tk.FLAT, borderwidth=4, insertbackground="white")
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,4))
        self.entry.bind("<Return>", lambda e: self._send()); self.entry.focus_set()
        # Input right-click
        ictx = tk.Menu(self.root, tearoff=0, bg=BG_HOVER, fg="white")
        ictx.add_command(label="Paste", command=lambda: self.entry.insert(tk.INSERT, self.root.clipboard_get()))
        ictx.add_command(label="Copy", command=lambda: self._copy_entry(self.entry))
        ictx.add_command(label="Clear", command=lambda: self.entry.delete(0, tk.END))
        self.entry.bind("<Button-3>", lambda e: ictx.tk_popup(e.x_root, e.y_root))
        tk.Button(inp, text="Send", bg=ACCENT, fg="white", font=("Segoe UI",9,"bold"),
                  relief=tk.FLAT, activebackground="#004499", cursor="hand2", command=self._send).pack(side=tk.RIGHT)

        # Right: Tools + Log
        tk.Label(right, text="TOOLS", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold")).pack(anchor=tk.W, padx=8, pady=(6,4))
        for n,d in TOOLS:
            f = tk.Frame(right, bg=BG_PANEL); f.pack(fill=tk.X, padx=6, pady=1)
            tk.Label(f, text=f"\u25b8 {n}", bg=BG_PANEL, fg="#0088ff", font=("Consolas",9)).pack(side=tk.LEFT)
            tk.Label(f, text=d, bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",7)).pack(side=tk.RIGHT)
            tk.Frame(right, bg=BORDER, height=1).pack(fill=tk.X, padx=6)

        tk.Label(right, text="ACTION LOG", bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI",8,"bold")).pack(anchor=tk.W, padx=8, pady=(10,4))
        self.log = tk.Text(right, bg=BG_CARD, fg=FG, font=("Consolas",8), wrap=tk.WORD, relief=tk.FLAT, bd=0, padx=8, pady=4, height=12)
        self.log.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,6)); self.log.config(state=tk.DISABLED)
        for t,c in [("ok","#00aaff"),("fail","#ff4444"),("ts",FG_DIM)]: self.log.tag_configure(t, foreground=c)

    def _msg(self, text, tag="sys"):
        self.chat.config(state=tk.NORMAL); self.chat.insert(tk.END, text, tag); self.chat.see(tk.END); self.chat.config(state=tk.DISABLED)
    def _alog(self, tool, ok, d=""):
        ts = datetime.now().strftime("%H:%M:%S"); self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, f"{ts} ","ts"); self.log.insert(tk.END, f"{'✓' if ok else '✗'} {tool} {d[:60]}\n","ok" if ok else "fail")
        self.log.see(tk.END); self.log.config(state=tk.DISABLED)

    def _send(self):
        raw = self.entry.get().strip()
        if not raw: return
        self.entry.delete(0, tk.END); self._msg(f"You: {raw}\n","user")
        if raw.lower() == "stats":
            m = self.mem; self._msg(f"Tasks:{m.get('tasks',0)} OK:{len(m.get('ok',[]))} Fail:{len(m.get('fail',[]))}\n\n","sys"); return
        self._msg("Agent: ","ai")
        sys_prompt = (
            "You are SubZero Agent, an autonomous AI that executes tasks directly.\n"
            + self._tool_rt.get_system_prompt() + "\n"
            "Be concise. Execute tools to complete tasks.\n"
        )
        prompt = sys_prompt + "\nUser: " + raw

        def on_token(tok):
            self.root.after(0, lambda t=tok: self._append_stream(t))
        def on_done(result, error):
            def finish():
                if error:
                    self._msg(f"\n[Error: {error}]\n\n","err")
                else:
                    self._msg("\n","ai")
                    # Execute @tool calls via sz_runtime
                    tool_calls = self._tool_rt.parse(result or "")
                    if tool_calls:
                        results = self._tool_rt.execute_all(tool_calls)
                        for r in results:
                            self._msg(f"  [{'\u2713' if r.success else '\u2717'} {r.tool_name}] {r.output[:120]}\n", "ok" if r.success else "err")
                            self._alog(r.tool_name, r.success, r.output[:60])
                            self.mem.setdefault("ok" if r.success else "fail",[]).append({"tool":r.tool_name,"t":datetime.now().isoformat()})
                    # Legacy TOOL[] format fallback
                    for m in re.finditer(r'TOOL\[(\w+)\]\(([^)]*)\)', result or ""):
                        tool, a = m.group(1), m.group(2)
                        args = [x.strip().strip("'\"") for x in a.split(",") if x.strip()] if a.strip() else []
                        res = self._exec(tool, args); ok = res.get("success", False)
                        msg = res.get("message", res.get("output", res.get("error","")))
                        self._msg(f"  [{tool}] {str(msg)[:120]}\n","ok" if ok else "err")
                        self._alog(tool, ok, str(msg)[:60])
                        self.mem.setdefault("ok" if ok else "fail",[]).append({"tool":tool,"t":datetime.now().isoformat()})
                    self._msg("\n","sys")
                    self.mem["tasks"] = self.mem.get("tasks",0)+1; save_mem(self.mem); self._upstat()
            self.root.after(0, finish)
        threading.Thread(target=_stream_ollama, args=(prompt, on_token, on_done), daemon=True).start()

    def _append_stream(self, tok):
        self.chat.config(state=tk.NORMAL); self.chat.insert(tk.END, tok, "ai"); self.chat.see(tk.END); self.chat.config(state=tk.DISABLED)

    def _exec(self, tool, args):
        try:
            if tool=="create_file" and len(args)>=2:
                os.makedirs(os.path.dirname(args[0]) or ".", exist_ok=True)
                with open(args[0],"w",encoding="utf-8") as f: f.write(", ".join(args[1:]))
                return {"success":True,"message":f"Created {args[0]}"}
            elif tool=="read_file" and args:
                with open(args[0],"r",encoding="utf-8") as f: return {"success":True,"output":f.read()[:200]}
            elif tool=="run_command" and args:
                r = subprocess.run(" ".join(args),shell=True,capture_output=True,text=True,timeout=15,encoding="utf-8",errors="replace",creationflags=subprocess.CREATE_NO_WINDOW)
                return {"success":r.returncode==0,"output":(r.stdout or r.stderr)[:200]}
            elif tool=="run_python" and args:
                r = subprocess.run(["python","-c"," ".join(args)],capture_output=True,text=True,timeout=15,encoding="utf-8",errors="replace",creationflags=subprocess.CREATE_NO_WINDOW)
                return {"success":r.returncode==0,"output":(r.stdout or r.stderr)[:200]}
            elif tool=="list_files" and args: return {"success":True,"output":", ".join(os.listdir(args[0])[:20])}
            elif tool=="edit_file" and len(args)>=3:
                with open(args[0],"r",encoding="utf-8") as f: c=f.read()
                with open(args[0],"w",encoding="utf-8") as f: f.write(c.replace(args[1],args[2]))
                return {"success":True,"message":f"Edited {args[0]}"}
            return {"success":False,"error":f"Unknown: {tool}"}
        except Exception as e: return {"success":False,"error":str(e)}

    def _upstat(self):
        m = self.mem; self.stat.config(text=f"Tasks: {m.get('tasks',0)} | OK: {len(m.get('ok',[]))} | Fail: {len(m.get('fail',[]))}")
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
