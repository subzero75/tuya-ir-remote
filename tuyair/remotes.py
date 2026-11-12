"""Remotes: one per IR device (TV, light, fan...), each with a template and learned keys.

config.json:
  "remotes": {
    "tv": {"template": "tv", "title": "Living room TV", "device": "ir",
           "keys": {"power": {"code": "...", "source": "learn (cloud)"}, ...}}
  }
"""
import time

from .device import DeviceError, Link, cloud_client, cloud_error
from .templates import TEMPLATES

# Ways the Tuya cloud accepts "press this key of a Smart Life remote"; the first that works is remembered.
CLOUD_SEND_PATHS = ["/v2.0/infrareds/{ir}/remotes/{rid}/command",
                    "/v2.0/infrareds/{ir}/remotes/{rid}/raw/command",
                    "/v1.0/infrareds/{ir}/remotes/{rid}/command"]


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
    for i, k in enumerate(keys):
        if i:
            time.sleep(float(cfg.get("delay_between_buttons", 0.5)))
        entry = learned[k]
        if "cloud" in entry:
            send_cloud_key(cfg, cfg.device(dev)["id"], entry["cloud"])
        else:
            if dev not in links:
                links[dev] = Link(cfg, dev)
            links[dev].send(entry["code"])
        cfg.log(f"Sent {name}.{k}")
    return links


# ------------------------------------------------------------------ Smart Life (cloud) remotes
def cloud_remotes(cfg, ir_id):
    """Remotes added to the blaster in the Smart Life app: [{remote_id, remote_name, category_id, ...}]."""
    c = cloud_client(cfg.get("cloud"))
    r = c.cloudrequest(f"/v2.0/infrareds/{ir_id}/remotes")
    err = cloud_error(r)
    if err:
        raise DeviceError(f"Could not list Smart Life remotes: {err}")
    res = r.get("result")
    return res if isinstance(res, list) else (res or {}).get("list", [])


def cloud_keys(cfg, ir_id, remote_id):
    """Keys of a Smart Life remote: (category_id, [{key, key_id, key_name}])."""
    c = cloud_client(cfg.get("cloud"))
    r = c.cloudrequest(f"/v2.0/infrareds/{ir_id}/remotes/{remote_id}/keys")
    err = cloud_error(r)
    if err:
        raise DeviceError(f"Could not read the remote's keys: {err}")
    res = r.get("result") or {}
    keys = res if isinstance(res, list) else res.get("key_list") or res.get("keys") or []
    category = None if isinstance(res, list) else res.get("category_id")
    return category, keys


def send_cloud_key(cfg, ir_id, ref):
    """Press a key of a Smart Life remote through the cloud. ref: {remote_id, category_id, key, key_id}."""
    c = cloud_client(cfg.get("cloud"))
    body = {k: ref[k] for k in ("category_id", "key_id", "key") if ref.get(k) is not None}
    paths = [ref["path"]] if ref.get("path") else CLOUD_SEND_PATHS
    last = None
    for path in paths:
        r = c.cloudrequest(path.format(ir=ir_id, rid=ref["remote_id"]), action="POST", post=body)
        if isinstance(r, dict) and r.get("success"):
            ref["path"] = path
            return path
        last = r
    raise DeviceError(f"Cloud key send failed: {cloud_error(last) or last}")
