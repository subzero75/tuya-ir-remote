"""Config, state and log files.

Config lookup order:
  1. --config PATH
  2. TUYAIR_CONFIG environment variable
  3. the user folder: %APPDATA%\\tuyair (Windows), ~/Library/Application Support/tuyair (macOS),
     $XDG_CONFIG_HOME/tuyair or ~/.config/tuyair (Linux)

The state file (last AC state) and the log live next to the config file.
"""
import json
import os
import sys
import time
from pathlib import Path


class ConfigError(Exception):
    pass


def user_dir():
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "tuyair"


def find_config(explicit=None):
    if explicit:
        return Path(explicit).expanduser().resolve()
    if os.environ.get("TUYAIR_CONFIG"):
        return Path(os.environ["TUYAIR_CONFIG"]).expanduser().resolve()
    # (the current folder is not searched: another program's config.json there would be picked up by mistake)
    return user_dir() / "config.json"


DEFAULTS = {
    "default_device": None,
    "devices": {},
    "buttons": {},
    "delay_between_buttons": 0.5,
    "language": "auto",
}


class Config:
    def __init__(self, path):
        self.path = Path(path)
        self.data = json.loads(json.dumps(DEFAULTS))
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except ValueError as e:
                raise ConfigError(f"{self.path} is not valid JSON: {e}")

    # ------------------------------------------------------------ files
    @property
    def folder(self):
        return self.path.parent

    @property
    def state_path(self):
        return self.folder / "ac_state.json"

    @property
    def log_path(self):
        return self.folder / "tuyair.log"

    def save(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        write_json_atomic(self.path, self.data)

    # ------------------------------------------------------------ helpers
    def __getitem__(self, k):
        return self.data[k]

    def get(self, k, default=None):
        return self.data.get(k, default)

    def device_name(self, name=None):
        devices = self.data.get("devices") or {}
        if not devices:
            raise ConfigError(f"No devices in {self.path}. Run:  tuyair setup")
        name = name or (self.data.get("ac") or {}).get("device") or self.data.get("default_device") \
            or next(iter(devices))
        if name not in devices:
            raise ConfigError(f"Device '{name}' is not in config. Known: {', '.join(devices)}")
        return name

    def device(self, name=None):
        return self.data["devices"][self.device_name(name)]

    def log(self, msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
        try:
            print(line)
        except Exception:
            pass  # pythonw has no console
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def write_json_atomic(path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
