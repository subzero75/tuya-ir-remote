"""Remotes: one per IR device (TV, light, fan...), each with a template and learned keys.

config.json:
  "remotes": {
    "tv": {"template": "tv", "title": "Living room TV", "device": "ir",
           "keys": {"power": {"code": "...", "source": "learn (cloud)"}, ...}}
  }
"""
import time

from .device import Link
from .templates import TEMPLATES


def all_remotes(cfg):
    return cfg.data.setdefault("remotes", {})


def get(cfg, name):
    r = all_remotes(cfg).get(name)
    if r is None:
        known = ", ".join(all_remotes(cfg)) or "none"
        raise KeyError(f"No remote named '{name}' (known: {known}). Add one:  tuyair remote add {name} --template tv")
    return r


def add(cfg, name, template, title=None, device=None):
    if template not in TEMPLATES:
        raise ValueError(f"Unknown template '{template}'. Available: {', '.join(TEMPLATES)}")
    remotes = all_remotes(cfg)
    if name in remotes:
        raise ValueError(f"A remote named '{name}' already exists.")
    remotes[name] = {"template": template, "title": title or name, "device": cfg.device_name(device), "keys": {}}
    cfg.save()
    return remotes[name]


def save_key(cfg, name, key, code, source=""):
    get(cfg, name).setdefault("keys", {})[key] = {"code": code, "source": source}
    cfg.save()


def press(cfg, name, keys, links=None):
    """Send one or more keys of a remote, in order."""
    r = get(cfg, name)
    learned = r.get("keys") or {}
    missing = [k for k in keys if k not in learned]
    if missing:
        raise KeyError(f"'{name}' has no learned key(s): {', '.join(missing)}. Learn: tuyair remote learn {name} --key {missing[0]}")
    links = {} if links is None else links
    dev = cfg.device_name(r.get("device"))
    if dev not in links:
        links[dev] = Link(cfg, dev)
    for i, k in enumerate(keys):
        if i:
            time.sleep(float(cfg.get("delay_between_buttons", 0.5)))
        links[dev].send(learned[k]["code"])
        cfg.log(f"Sent {name}.{k}")
    return links
