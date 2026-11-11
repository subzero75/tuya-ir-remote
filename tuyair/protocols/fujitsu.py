"""Fujitsu / General / O General air conditioners (AR-RAH, AR-RAJ, AR-REB style remotes).

Frames are bytes sent LSB first after a header. Short commands (off, powerful,
swing, louver step...) are 7 bytes; a full state is 16 bytes.

Options (all optional, stored under "ac" in config.json):
  remote_id  0..3   remote custom code A..D (only 0/A is verified)
  variant    A..D   small per-model differences in the full-state frame
  timing     dict   pulse timings; "calibrate" fills it from your real remote
"""
from . import Protocol

DEFAULT_TIMING = {"hdr_mark": 3324, "hdr_space": 1574, "bit_mark": 448,
                  "one_space": 1182, "zero_space": 390, "gap": 0}

VARIANTS = {
    "A": {"protocol": 0x30, "byte14": 0x20},   # AR-RAH2E / AR-RAJ / AR-REB1E style
    "B": {"protocol": 0x30, "byte14": 0x00},
    "C": {"protocol": 0x31, "byte14": 0x20},   # AR-REW4E style
    "D": {"protocol": 0x31, "byte14": 0x00},
}

MODES = {"cool": 1, "dry": 2, "fan": 3, "heat": 4, "auto": 0}
FANS = {"auto": 0, "high": 1, "med": 2, "low": 3, "quiet": 4}
SWINGS = {"off": 0, "vert": 1, "horiz": 2, "both": 3}

SHORT = {
    "powerful": (0x39, "Powerful (toggle)"),
    "economy": (0x09, "Economy (toggle)"),
    "swing": (0x6D, "Vertical swing (toggle)"),
    "swing_h": (0x7A, "Horizontal swing (toggle)"),
    "airflow": (0x6C, "Step vertical louver (SET up/down)"),
    "airflow_h": (0x79, "Step horizontal louver (SET left/right)"),
}
OFF = 0x02


class Fujitsu(Protocol):
    name = "fujitsu"
    title = "Fujitsu / General / O General"
    modes = list(MODES)
    fans = list(FANS)
    swings = list(SWINGS)
    temp_min, temp_max = 16, 30
    temp_free_modes = ("fan",)
    short_commands = {k: v[1] for k, v in SHORT.items()}

    def __init__(self, options=None):
        super().__init__(options)
        self.timing = dict(DEFAULT_TIMING)
        self.timing.update({k: int(v) for k, v in (self.options.get("timing") or {}).items()
                            if k in DEFAULT_TIMING})
        self.remote_id = int(self.options.get("remote_id", 0)) & 0x3
        self.variant = VARIANTS.get(str(self.options.get("variant", "A")).upper(), VARIANTS["A"])

    # ---------------------------------------------------------------- frames
    def _head(self):
        return [0x14, 0x63, 0x00, 0x10 | (self.remote_id << 4), 0x10]

    def short_bytes(self, cmd):
        return self._head() + [cmd, (~cmd) & 0xFF]

    def full_bytes(self, state, power_on):
        temp = int(state.get("temp", 24))
        if not self.temp_min <= temp <= self.temp_max:
            raise ValueError(f"Temperature must be {self.temp_min}-{self.temp_max}")
        data = self._head() + [0xFE, 0x09, self.variant["protocol"],
                               (1 if power_on else 0) | ((temp - 16) << 4),
                               MODES[state.get("mode", "cool")],
                               FANS[state.get("fan", "auto")] | (SWINGS[state.get("swing", "off")] << 4),
                               0x00, 0x00, 0x00, self.variant["byte14"]]
        data.append((-sum(data[7:])) & 0xFF)
        return data

    def pulses(self, data):
        t = self.timing
        out = [t["hdr_mark"], t["hdr_space"]]
        for byte in data:
            for bit in range(8):
                out += [t["bit_mark"], t["one_space"] if (byte >> bit) & 1 else t["zero_space"]]
        out.append(t["bit_mark"])
        if t.get("gap"):
            out.append(t["gap"])
        return out

    # ---------------------------------------------------------------- interface
    def full_state(self, state, power_on):
        return self.pulses(self.full_bytes(state, power_on))

    def off(self):
        return self.pulses(self.short_bytes(OFF))

    def short(self, name):
        if name not in SHORT:
            raise KeyError(f"Unknown command '{name}'. Available: {', '.join(SHORT)}")
        return self.pulses(self.short_bytes(SHORT[name][0]))

    @staticmethod
    def decode_bytes(pulses):
        if len(pulses) < 20 or not 2000 < pulses[0] < 5000:
            return None
        bits = [1 if pulses[i] > 800 else 0 for i in range(3, len(pulses), 2) if pulses[i] < 3000]
        data = [sum(bits[j * 8 + k] << k for k in range(8)) for j in range(len(bits) // 8)]
        if data[:2] != [0x14, 0x63]:
            return None
        return data

    def decode(self, pulses):
        data = self.decode_bytes(pulses)
        return " ".join("%02X" % b for b in data) if data else None

    def calibrate(self, pulses):
        if not self.decode_bytes(pulses):
            raise ValueError("This capture is not a Fujitsu-family signal.")
        body = pulses[2:]
        marks = sorted(body[0::2])
        spaces = [x for x in body[1::2] if x < 3000]
        zeros = sorted(x for x in spaces if x < 800)
        ones = sorted(x for x in spaces if x >= 800)
        if not (marks and zeros and ones):
            raise ValueError("Capture too short to measure timings.")
        med = lambda v: v[len(v) // 2]
        return {"hdr_mark": pulses[0], "hdr_space": pulses[1], "bit_mark": med(marks),
                "zero_space": med(zeros), "one_space": med(ones),
                "gap": pulses[-1] if len(pulses) % 2 == 0 and pulses[-1] >= 3000 else 0}
