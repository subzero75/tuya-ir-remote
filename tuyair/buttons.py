"""Saved buttons (learned or generated codes) and sending them."""
import time

from .device import Link


def send_buttons(cfg, names, handles=None):
    buttons = cfg.get("buttons") or {}
    missing = [n for n in names if n not in buttons]
    if missing:
        raise KeyError(f"Unknown button(s): {', '.join(missing)}. See:  tuyair list")
    handles = {} if handles is None else handles
    for i, name in enumerate(names):
        b = buttons[name]
        dev_name = cfg.device_name(b.get("device"))
        if dev_name not in handles:
            handles[dev_name] = Link(cfg, dev_name)
        if i:
            time.sleep(float(cfg.get("delay_between_buttons", 0.5)))
        handles[dev_name].send(b["code"])
        cfg.log(f"Sent '{name}' via '{dev_name}'")
    return handles


def save_button(cfg, name, code, device=None, source=""):
    cfg.data.setdefault("buttons", {})[name] = {"device": cfg.device_name(device), "code": code, "source": source}
    cfg.save()
