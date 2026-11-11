"""Small always-on-top window that mirrors the remote's screen and controls the AC.

Run:  tuyair panel      (pythonw -m tuyair panel  to run without a console)
Running it again while it is open closes it (or brings it back if minimized),
so one hotkey can open and close it.
"""
import queue
import socket
import sys
import threading
import tkinter as tk

from . import i18n
from .ac import AC
from .buttons import send_buttons

PORT = 48731

BG, BTN, BTN_HI, FG, MUTED, ACCENT = "#1e1f24", "#2c2e35", "#3a3d46", "#e8e8ea", "#9a9ca5", "#e0a458"
LCD_BG, LCD_FG, LCD_DIM = "#c7d1bd", "#1d2a1d", "#9aa58f"
OK_FG, ERR_FG = "#7fbf7f", "#e07070"
DEFAULT_COMMANDS = ["powerful", "swing", "airflow", "airflow_h"]


def single_instance():
    """Listening socket if this is the only panel; otherwise tell the running one to toggle."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", PORT))
        s.listen(1)
        return s
    except OSError:
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=1) as c:
                c.sendall(b"toggle")
        except OSError:
            pass
        return None


class Worker(threading.Thread):
    """Runs sends one at a time off the UI thread."""

    def __init__(self, report):
        super().__init__(daemon=True)
        self.q = queue.Queue()
        self.report = report

    def run(self):
        while True:
            job = self.q.get()
            try:
                job()
                self.report(True, "")
            except BaseException as e:
                self.report(False, str(e) or e.__class__.__name__)


class Panel:
    def __init__(self, root, cfg):
        self.root, self.cfg = root, cfg
        self.ac = AC(cfg)
        self.p = self.ac.protocol
        self.t = i18n.texts(cfg.get("language", "auto"))
        self.st = self.ac.read_state()
        self.pending = None
        self.status_job = None
        self.handles = {}
        self.worker = Worker(lambda ok, msg: root.after(0, self.show_result, ok, msg))
        self.worker.start()

        root.title(self.t["title"])
        root.configure(bg=BG)
        root.resizable(False, False)
        root.attributes("-topmost", True)
        self.restore_position()
        self.build()
        self.render()
        self.last_seen = self.state_text()
        root.after(1500, self.poll)
        root.protocol("WM_DELETE_WINDOW", self.close)

    # ------------------------------------------------------------ layout
    def btn(self, parent, text, cmd):
        return tk.Button(parent, text=text, command=cmd, bg=BTN, fg=FG, activebackground=BTN_HI,
                         activeforeground=FG, relief="flat", bd=0, font=("Segoe UI", 10, "bold"),
                         padx=6, pady=6, cursor="hand2")

    def build(self):
        pad = {"padx": 4, "pady": 4, "sticky": "ew"}
        lcd = tk.Frame(self.root, bg=LCD_BG, padx=10, pady=6)
        lcd.grid(row=0, column=0, columnspan=3, sticky="ew", padx=8, pady=(8, 4))
        lcd.columnconfigure(1, weight=1)
        lab = lambda **kw: tk.Label(lcd, bg=LCD_BG, fg=LCD_FG, **kw)
        self.l_mode = lab(font=("Segoe UI", 11, "bold"), width=7, anchor="w")
        self.l_mode.grid(row=0, column=0, sticky="nw")
        self.l_temp = lab(font=("Consolas", 40, "bold"))
        self.l_temp.grid(row=0, column=1, rowspan=2)
        self.l_fan = lab(font=("Segoe UI", 11, "bold"), width=7, anchor="e")
        self.l_fan.grid(row=0, column=2, sticky="ne")
        self.l_swing = lab(font=("Segoe UI", 9, "bold"), anchor="w")
        self.l_swing.grid(row=1, column=0, sticky="sw")
        self.l_powerful = lab(font=("Segoe UI", 9, "bold"), anchor="e")
        self.l_powerful.grid(row=1, column=2, sticky="se")

        self.btn(self.root, self.t["mode"], lambda: self.change("mode", "next")).grid(row=1, column=0, **pad)
        self.b_power = self.btn(self.root, self.t["power"], self.toggle_power)
        self.b_power.grid(row=1, column=1, **pad)
        self.btn(self.root, self.t["fan"], lambda: self.change("fan", "next")).grid(row=1, column=2, **pad)

        cmds = [c for c in ((self.cfg.get("ac") or {}).get("panel_commands") or DEFAULT_COMMANDS)
                if c in self.p.short_commands]
        left, right = cmds[0::2], cmds[1::2]
        self.btn(self.root, "▲", lambda: self.change("temp", "+1")).grid(row=2, column=1, **pad)
        self.btn(self.root, "▼", lambda: self.change("temp", "-1")).grid(row=3, column=1, **pad)
        for i, c in enumerate(left):
            self.btn(self.root, self.t["commands"].get(c, c), lambda c=c: self.command(c)).grid(row=2 + i, column=0, **pad)
        for i, c in enumerate(right):
            self.btn(self.root, self.t["commands"].get(c, c), lambda c=c: self.command(c)).grid(row=2 + i, column=2, **pad)
        row = 2 + max(2, len(left), len(right))

        extra = [b for b in (self.cfg.get("panel_buttons") or []) if b in (self.cfg.get("buttons") or {})]
        for i, name in enumerate(extra):
            self.btn(self.root, name, lambda n=name: self.custom(n)).grid(row=row + i // 3, column=i % 3, **pad)
        row += (len(extra) + 2) // 3

        bottom = tk.Frame(self.root, bg=BG)
        bottom.grid(row=row, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 6))
        bottom.columnconfigure(0, weight=1)
        self.l_status = tk.Label(bottom, bg=BG, fg=MUTED, font=("Segoe UI", 8), anchor="w")
        self.l_status.grid(row=0, column=0, sticky="w")
        self.pin = tk.BooleanVar(value=True)
        tk.Checkbutton(bottom, text=self.t["pin"], variable=self.pin, command=self.toggle_pin, bg=BG, fg=MUTED,
                       selectcolor=BG, activebackground=BG, activeforeground=FG, font=("Segoe UI", 8),
                       bd=0).grid(row=0, column=1, sticky="e")
        for c in range(3):
            self.root.columnconfigure(c, weight=1, minsize=96)

    # ------------------------------------------------------------ display
    def render(self):
        st, t = self.st, self.t
        on = st.get("power")
        fg = LCD_FG if on else LCD_DIM
        self.l_mode.config(text=t["modes"].get(st["mode"], st["mode"].upper()), fg=fg)
        self.l_fan.config(text=t["fans"].get(st["fan"], st["fan"].upper()), fg=fg)
        if not on:
            self.l_temp.config(text=t["off"], fg=LCD_FG, font=("Segoe UI", 30, "bold"))
        elif st["mode"] in self.p.temp_free_modes:
            self.l_temp.config(text="--", fg=fg, font=("Consolas", 40, "bold"))
        else:
            self.l_temp.config(text=f"{st['temp']}°C", fg=fg, font=("Consolas", 40, "bold"))
        self.l_swing.config(text=t["swing_on"] if on and st.get("swing") != "off" else "")
        self.l_powerful.config(text=t["commands"]["powerful"] if on and st.get("powerful") else "")
        self.b_power.config(fg=ACCENT if on else FG)

    def status(self, text, color=MUTED):
        self.l_status.config(text=text, fg=color)
        if self.status_job:
            self.root.after_cancel(self.status_job)
        self.status_job = self.root.after(4000, lambda: self.l_status.config(text=""))

    def show_result(self, ok, msg):
        self.st = self.ac.read_state()
        self.render()
        self.status(self.t["sent"], OK_FG) if ok else self.status(self.t["error"] + msg[:70], ERR_FG)

    # ------------------------------------------------------------ actions
    def run(self, job):
        self.status(self.t["sending"])
        self.worker.q.put(job)

    def toggle_power(self):
        if self.pending:
            self.root.after_cancel(self.pending)
            self.pending = None
        if self.st.get("power"):
            self.st.update(power=False, powerful=False)
            self.run(self.ac.off)
        else:
            self.st.update(power=True, powerful=False)
            snapshot = {k: self.st[k] for k in ("mode", "temp", "fan", "swing")}
            self.run(lambda: self.ac.on(**snapshot))
        self.render()

    def change(self, field, value):
        if field == "temp" and self.st["mode"] in self.p.temp_free_modes:
            return
        # update the screen now, send once the clicks stop (like the real remote)
        self.st = self.ac.step(field, value) if not self.st.get("power") else self._local_step(field, value)
        self.render()
        if self.st.get("power"):
            if self.pending:
                self.root.after_cancel(self.pending)
            self.pending = self.root.after(600, self.flush)

    def _local_step(self, field, value):
        st = dict(self.st)
        if field == "temp":
            st["temp"] = max(self.p.temp_min, min(self.p.temp_max, st["temp"] + int(value)))
        else:
            choices = {"mode": self.p.modes, "fan": self.p.fans}[field]
            st[field] = choices[(choices.index(st[field]) + 1) % len(choices)] if st[field] in choices else choices[0]
            if field == "mode":
                st["powerful"] = False
        return st

    def flush(self):
        self.pending = None
        snapshot = {k: self.st[k] for k in ("mode", "temp", "fan", "swing")}
        self.run(lambda: self.ac.set(**snapshot))

    def command(self, name):
        if not self.st.get("power"):
            return
        self.run(lambda: self.ac.command(name))

    def custom(self, name):
        self.run(lambda: send_buttons(self.cfg, [name], self.handles))

    # ------------------------------------------------------------ window
    def state_text(self):
        try:
            return self.cfg.state_path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def poll(self):
        """Pick up changes made by hotkeys / the command line."""
        text = self.state_text()
        if text != self.last_seen:
            self.last_seen = text
            if not self.pending:
                self.st = self.ac.read_state()
                self.render()
        self.root.after(1500, self.poll)

    def restore_position(self):
        pos = self.st.get("window")
        try:
            x, y = (int(v) for v in str(pos).lstrip("+").split("+"))
            if 0 <= x < self.root.winfo_screenwidth() - 100 and 0 <= y < self.root.winfo_screenheight() - 100:
                self.root.geometry(f"+{x}+{y}")
        except (ValueError, tk.TclError):
            pass

    def toggle_pin(self):
        self.root.attributes("-topmost", self.pin.get())

    def toggle_window(self):
        try:
            visible = self.root.state() == "normal" and self.root.winfo_viewable()
        except tk.TclError:
            visible = False
        if visible:
            self.close()
        else:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            if not self.pin.get():
                self.root.after(300, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()

    def close(self):
        st = self.ac.read_state()
        st["window"] = f"+{self.root.winfo_x()}+{self.root.winfo_y()}"
        self.ac.write_state(st)
        self.root.destroy()


def listen(lock, root, on_toggle):
    def loop():
        while True:
            try:
                conn, _ = lock.accept()
                conn.close()
                root.after(0, on_toggle)
            except OSError:
                return
    threading.Thread(target=loop, daemon=True).start()


def run_panel(cfg):
    lock = single_instance()
    if lock is None:
        return 0
    root = tk.Tk()
    panel = Panel(root, cfg)
    listen(lock, root, panel.toggle_window)
    root.mainloop()
    return 0


def error_box(message):
    try:
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("tuyair", message)
        r.destroy()
    except Exception:
        print(message, file=sys.stderr)
