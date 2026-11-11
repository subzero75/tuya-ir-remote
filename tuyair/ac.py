"""AC control on top of a protocol: keeps the last sent state, builds and sends codes.

IR is one-way, so the "state" is what was last sent. It is shared by the CLI,
the hotkeys and the panel through ac_state.json next to the config file.
"""
import json

from . import device as D
from .codes import pulses_to_base64
from .config import write_json_atomic
from .protocols import get_protocol

DEFAULT_STATE = {"power": False, "mode": "cool", "temp": 24, "fan": "auto", "swing": "off", "powerful": False}


class AC:
    def __init__(self, cfg):
        self.cfg = cfg
        self.opts = cfg.get("ac") or {}
        self.protocol = get_protocol(self.opts.get("protocol", "fujitsu"), self.opts)
        self._dev = None

    # ------------------------------------------------------------ state
    def read_state(self):
        st = dict(DEFAULT_STATE)
        st["mode"] = self.protocol.modes[0]
        try:
            st.update(json.loads(self.cfg.state_path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        return st

    def write_state(self, st):
        try:
            self.cfg.folder.mkdir(parents=True, exist_ok=True)
            write_json_atomic(self.cfg.state_path, st)
        except OSError:
            pass

    # ------------------------------------------------------------ sending
    def device(self):
        if self._dev is None:
            self._dev = D.open_local(self.cfg.device(self.opts.get("device")))
        return self._dev

    def send_pulses(self, pulses):
        try:
            D.send(self.device(), pulses_to_base64(pulses))
        except Exception:
            self._dev = None  # reconnect next time
            raise

    # ------------------------------------------------------------ actions
    def on(self, **changes):
        st = self.read_state()
        st.update({k: v for k, v in changes.items() if v is not None})
        st.update(power=True, powerful=False)
        self.send_pulses(self.protocol.full_state(st, power_on=True))
        self.write_state(st)
        return st

    def off(self):
        st = self.read_state()
        self.send_pulses(self.protocol.off())
        st.update(power=False, powerful=False)
        self.write_state(st)
        return st

    def toggle(self):
        return self.off() if self.read_state().get("power") else self.on()

    def set(self, send=True, **changes):
        """Change mode/temp/fan/swing. Sent only while the AC is on (like the real remote)."""
        st = self.read_state()
        st.update({k: v for k, v in changes.items() if v is not None})
        p = self.protocol
        st["temp"] = max(p.temp_min, min(p.temp_max, int(st["temp"])))
        if "mode" in changes and changes["mode"] is not None:
            st["powerful"] = False
        if send and st.get("power"):
            self.send_pulses(p.full_state(st, power_on=False))
        self.write_state(st)
        return st

    def step(self, field, value):
        """temp +1 / -1 / 22, mode next / cool, fan next / high, swing next / off."""
        st = self.read_state()
        if field == "temp":
            v = str(value)
            new = st["temp"] + int(v) if v[:1] in "+-" else int(v)
            return self.set(temp=new)
        choices = {"mode": self.protocol.modes, "fan": self.protocol.fans, "swing": self.protocol.swings}[field]
        if value == "next":
            cur = st.get(field)
            value = choices[(choices.index(cur) + 1) % len(choices)] if cur in choices else choices[0]
        if value not in choices:
            raise ValueError(f"{field} must be one of: {', '.join(choices)} or next")
        return self.set(**{field: value})

    def command(self, name):
        st = self.read_state()
        self.send_pulses(self.protocol.short(name))
        if name == "powerful":
            st["powerful"] = not st.get("powerful")
        elif name in ("swing", "swing_h"):
            st["swing"] = "off" if st.get("swing") != "off" else ("vert" if name == "swing" else "horiz")
        self.write_state(st)
        return st
