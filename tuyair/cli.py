"""Command line interface:  tuyair <command> ...   (or  python -m tuyair <command> ...)"""
import argparse
import sys

from . import __version__
from . import device as D
from .buttons import save_button, send_buttons
from .codes import to_pulses
from .config import Config, ConfigError, find_config


# ---------------------------------------------------------------- generic
def cmd_setup(cfg, a):
    from .setup_wizard import run
    return run(cfg)


def cmd_test(cfg, a):
    names = [a.device] if a.device else list(cfg.get("devices") or {})
    if not names:
        raise ConfigError("No devices configured. Run:  tuyair setup")
    ok_all = True
    for name in names:
        ok, msg = D.Link(cfg, name).check()
        ok_all &= ok
        cfg.log(f"[{name}] {'OK' if ok else 'NOT reachable'}: {msg}")
    return 0 if ok_all else 1


def learn_code(cfg, name, device=None, method="auto", timeout=15):
    """Learn locally; if the blaster doesn't report locally, fall back to cloud learning."""
    dev_name = cfg.device_name(device)
    dev = cfg.device(dev_name)
    code = None
    if method == "auto" and dev.get("learn_method") == "cloud" and cfg.get("cloud"):
        method = "cloud"   # this blaster was seen to report learned codes only to the cloud
    if method in ("auto", "local"):
        print(f"Point the remote at the blaster (5-10 cm) and press '{name}' within {timeout} s...")
        code = D.learn_local(D.open_local(dev), timeout)
        if not code and method == "auto":
            if cfg.get("cloud"):
                print("Nothing came back locally (some blasters only report to the cloud). Trying cloud learning...")
            else:
                print("Nothing came back locally. Some blasters only report learned codes to the cloud:")
                print('add a "cloud" section (run: tuyair setup) and try again, or use --cloud.')
    if not code and method in ("auto", "cloud") and (cfg.get("cloud") or method == "cloud"):
        code = D.learn_cloud(cfg.get("cloud"), dev["id"], timeout=max(timeout, 30),
                             on_ready=lambda: print(f"Press '{name}' now (30 s)..."))
        if code and method == "auto" and dev.get("learn_method") != "cloud":
            dev["learn_method"] = "cloud"
            cfg.save()
            print("(Remembered: this blaster learns through the cloud; next time it goes straight there.)")
    return dev_name, code


def cmd_learn(cfg, a):
    method = "cloud" if a.cloud else "local" if a.local else "auto"
    dev_name, code = learn_code(cfg, a.name, a.device, method, a.timeout)
    if not code:
        raise D.DeviceError("No IR signal received. Move the remote closer and try again.")
    save_button(cfg, a.name, code, dev_name, f"learn ({method})")
    cfg.log(f"Learned '{a.name}'. Test it:  tuyair send {a.name}")
    return 0


def cmd_send(cfg, a):
    send_buttons(cfg, a.names)
    return 0


def cmd_list(cfg, a):
    buttons = cfg.get("buttons") or {}
    if not buttons:
        print("No saved buttons.")
    for name, b in sorted(buttons.items()):
        print(f"{name:24} device={b.get('device')}  {b.get('source', '')}")
    return 0


def cmd_delete(cfg, a):
    if (cfg.get("buttons") or {}).pop(a.name, None) is None:
        raise KeyError(f"No button named '{a.name}'.")
    cfg.save()
    cfg.log(f"Deleted '{a.name}'.")
    return 0


def cmd_decode(cfg, a):
    from .protocols import get_protocol
    b = (cfg.get("buttons") or {}).get(a.name)
    if not b:
        raise KeyError(f"No button named '{a.name}'.")
    pulses = to_pulses(b["code"])
    print(f"{len(pulses)} pulses, first: {pulses[:6]}")
    proto = get_protocol((cfg.get("ac") or {}).get("protocol", "fujitsu"), cfg.get("ac") or {})
    print(f"{proto.title} bytes: {proto.decode(pulses) or '(not this protocol)'}")
    return 0


# ---------------------------------------------------------------- remotes
def cmd_remote(cfg, a):
    from . import remotes as R
    from .templates import TEMPLATES, keys_of
    act = a.action
    if act == "templates":
        for name, rows in TEMPLATES.items():
            print(f"{name:10} {', '.join(keys_of(name)) or '(add your own keys with --key)'}")
        return 0
    if act == "list":
        rs = R.all_remotes(cfg)
        if not rs:
            print("No remotes. Add one:  tuyair remote add tv --template tv")
        for name, r in rs.items():
            keys = ", ".join(r.get("keys") or {}) or "-"
            print(f"{name:14} {r.get('template'):10} device={r.get('device')}  keys: {keys}")
        return 0
    if not a.name:
        raise ValueError(f"Usage: tuyair remote {act} NAME ...")
    if act == "add":
        R.add(cfg, a.name, a.template or "custom", a.title, a.device)
        cfg.log(f"Added remote '{a.name}'. Now learn its buttons:  tuyair remote learn {a.name}")
        return 0
    if act == "remove":
        if R.all_remotes(cfg).pop(a.name, None) is None:
            raise KeyError(f"No remote named '{a.name}'.")
        cfg.save()
        cfg.log(f"Removed remote '{a.name}'.")
        return 0
    if act == "press":
        if not a.keys:
            raise ValueError(f"Usage: tuyair remote press {a.name} KEY [KEY ...]")
        R.press(cfg, a.name, a.keys)
        return 0
    if act == "forget":
        r = R.get(cfg, a.name)
        for k in a.keys:
            (r.get("keys") or {}).pop(k, None)
        cfg.save()
        cfg.log(f"Forgot {', '.join(a.keys)} on '{a.name}'.")
        return 0
    if act == "learn":
        return remote_learn(cfg, a)
    if act == "discover":
        return remote_discover(cfg, a)
    if act == "add-code":
        return remote_add_code(cfg, a)
    raise ValueError(f"Unknown remote action '{act}'")


def _ensure_remote(cfg, a):
    from . import remotes as R
    if a.name not in R.all_remotes(cfg):
        R.add(cfg, a.name, a.template or "tv", a.title, a.device)
        print(f"Created remote '{a.name}' ({a.template or 'tv'}).")
    return R.get(cfg, a.name)


def remote_discover(cfg, a):
    """Find the codes of a device whose remote is lost (NEC protocol)."""
    from . import discover as X
    from . import remotes as R
    from .codes import pulses_to_base64
    from .device import Link
    from .protocols import nec
    r = _ensure_remote(cfg, a)
    state = r.setdefault("discover", {"protocol": "nec"})
    link = Link(cfg, r.get("device"))
    ask = X.Asker()
    print("Point the blaster at the device, switch the device on (with its own button if needed) and watch it.")
    print("Tip: if a test turns it off, that's a reaction too - answer y and switch it back on.")

    address = nec.parse_number(a.address) if a.address else state.get("address")
    if address is None:
        address = X.find_address(link.send, ask)
        if address is None:
            print("No address found. The device may use another protocol, or need --address (e.g. 0x1234 for a 16-bit NEC address).")
            return 1
        state.update(address=address, next=0)
        cfg.save()
    else:
        print(f"Using address {address:#04x}" + (" (saved earlier)" if not a.address else ""))
        state["address"] = address

    start = nec.parse_number(a.start) if a.start is not None else int(state.get("next", 0))
    end = nec.parse_number(a.end) if a.end is not None else 0xFF
    print(f"Learned key ids you can use: {', '.join(list(_keys_hint(r)))} ... or any name.")

    def save_label(label, cmd):
        R.save_key(cfg, a.name, label, pulses_to_base64(nec.pulses(address, cmd)), f"discover nec {address:#04x} {cmd:#04x}")

    def progress(n):
        state["next"] = n
        cfg.save()

    nxt = X.map_commands(link.send, ask, save_label, start, end, address, on_progress=progress)
    progress(nxt)
    keys = ", ".join(r.get("keys") or {}) or "none yet"
    print(f"\nSaved keys: {keys}")
    if nxt <= end:
        print(f"Stopped at {nxt:#04x}. Run the same command again to continue.")
    return 0


def _keys_hint(r):
    from .templates import keys_of
    return keys_of(r.get("template", "tv"))[:15]


def remote_add_code(cfg, a):
    """Add a key from a known code: --nec ADDRESS COMMAND, or --code BASE64/HEX."""
    from . import remotes as R
    from .codes import pulses_to_base64
    from .protocols import nec
    if not a.keys:
        raise ValueError("Usage: tuyair remote add-code NAME KEY (--nec ADDRESS COMMAND | --code CODE)")
    _ensure_remote(cfg, a)
    if a.nec:
        addr, cmd = (nec.parse_number(x) for x in a.nec)
        code, src = pulses_to_base64(nec.pulses(addr, cmd)), f"nec {addr:#04x} {cmd:#04x}"
    elif a.code:
        code, src = a.code, "manual"
    else:
        raise ValueError("Give --nec ADDRESS COMMAND or --code CODE")
    R.save_key(cfg, a.name, a.keys[0], code, src)
    cfg.log(f"Saved {a.name}.{a.keys[0]} ({src}). Test:  tuyair remote press {a.name} {a.keys[0]}")
    return 0


def remote_learn(cfg, a):
    """Walk through the template's keys (or the ones given with --key) and learn each."""
    from . import remotes as R
    from .i18n import texts
    from .templates import keys_of
    r = R.get(cfg, a.name)
    labels = texts("en")["keys"]
    todo = list(a.key or []) or [k for k in keys_of(r.get("template")) if a.redo or k not in (r.get("keys") or {})]
    if not todo:
        print("Nothing to learn. Add a custom key with --key NAME, or relearn everything with --redo.")
        return 0
    method = "cloud" if a.cloud else "local" if a.local else "auto"
    print(f"Learning {len(todo)} key(s) for '{a.name}'. For each: Enter = learn, s = skip, q = stop.")
    for key in todo:
        ans = input(f"\n[{key}] {labels.get(key, key)} - ready? ").strip().lower()
        if ans == "q":
            break
        if ans == "s":
            continue
        _, code = learn_code(cfg, key, r.get("device"), method, a.timeout)
        if code:
            R.save_key(cfg, a.name, key, code, f"learn ({method})")
            print(f"  saved {key}")
        else:
            print("  nothing received, skipped (run again later for the missing keys)")
    cfg.log(f"Remote '{a.name}' keys: {', '.join((r.get('keys') or {}))}")
    return 0


# ---------------------------------------------------------------- ac
def show_state(st):
    if not st.get("power"):
        return "OFF"
    extra = " SWING" if st.get("swing") != "off" else ""
    extra += " POWERFUL" if st.get("powerful") else ""
    return f"ON {st['mode'].upper()} {st['temp']}C fan={st['fan']}{extra}"


def cmd_ac(cfg, a):
    from .ac import AC
    if not cfg.get("ac"):
        raise ConfigError('No "ac" section in config. Run:  tuyair setup  (or add {"ac": {"protocol": "fujitsu"}})')
    ac = AC(cfg)
    act = a.action
    changes = {k: getattr(a, k, None) for k in ("mode", "temp", "fan", "swing")}
    if act == "on":
        st = ac.on(**changes)
    elif act == "off":
        st = ac.off()
    elif act == "toggle":
        st = ac.toggle()
    elif act == "set":
        st = ac.set(**changes)
    elif act in ("temp", "mode", "fan", "swing"):
        if not a.value:
            raise ValueError(f"Usage: tuyair ac {act} <value>   (temp: +1 / -1 / 22, others: next / <name>)")
        st = ac.step(act, a.value)
    elif act == "cmd":
        if not a.value:
            raise ValueError("Usage: tuyair ac cmd <" + "|".join(ac.protocol.short_commands) + ">")
        st = ac.command(a.value)
    elif act == "status":
        st = ac.read_state()
    elif act == "calibrate":
        return ac_calibrate(cfg, ac, a)
    elif act == "probe":
        return ac_probe(cfg, ac, a)
    else:
        raise ValueError(f"Unknown ac action '{act}'")
    cfg.log(f"AC: {show_state(st)}")
    return 0


def ac_calibrate(cfg, ac, a):
    """Use the timings of the user's real remote (fixes 'off works but on doesn't')."""
    if a.value:
        b = (cfg.get("buttons") or {}).get(a.value)
        if not b:
            raise KeyError(f"No button named '{a.value}'.")
        code = b["code"]
    else:
        print("Set your remote to COOL 24 and switch it OFF, so START sends a power-on frame.")
        _, code = learn_code(cfg, "START/STOP (power on)", ac.opts.get("device"),
                             "cloud" if a.cloud else "auto", 15)
        if not code:
            raise D.DeviceError("Nothing captured.")
        save_button(cfg, "remote_power_on", code, ac.opts.get("device"), "calibrate capture")
    pulses = to_pulses(code)
    timing = ac.protocol.calibrate(pulses)
    print(f"Captured bytes: {ac.protocol.decode(pulses)}")
    cfg.data["ac"]["timing"] = timing
    cfg.save()
    cfg.log(f"Calibrated timings: {timing}. Try:  tuyair ac on")
    return 0


def ac_probe(cfg, ac, a):
    """Try each full-state variant of the protocol until the AC turns on."""
    from .protocols import get_protocol
    variants = getattr(sys.modules[type(ac.protocol).__module__], "VARIANTS", None)
    if not variants:
        raise ValueError("This protocol has no variants to probe.")
    for name in variants:
        proto = get_protocol(ac.opts.get("protocol", "fujitsu"), {**ac.opts, "variant": name})
        print(f"\nVariant {name}: off, wait 4 s, on (cool 24)...")
        ac.send_pulses(proto.off())
        import time
        time.sleep(4)
        ac.send_pulses(proto.full_state({"mode": "cool", "temp": 24, "fan": "auto", "swing": "off"}, True))
        ans = input("Did the AC turn on? [y / Enter = no / q = quit]: ").strip().lower()
        if ans == "q":
            break
        if ans in ("y", "yes", "ن", "نعم"):
            cfg.data["ac"]["variant"] = name
            cfg.save()
            cfg.log(f"Variant {name} saved.")
            return 0
    print("No variant worked. Try:  tuyair ac calibrate   (captures your real remote)")
    return 1


# ---------------------------------------------------------------- panel / hotkeys
def cmd_panel(cfg, a):
    from .panel import run_panel
    return run_panel(cfg)


def cmd_hotkeys(cfg, a):
    from pathlib import Path
    from .hotkeys import build_script, startup_folder
    script = build_script(cfg)
    if a.print:
        print(script)
        return 0
    if a.startup:
        folder = startup_folder()
        if not folder:
            raise ConfigError("Startup folder not found (Windows only).")
        target = folder / "tuyair.ahk"
    else:
        target = Path(a.write) if a.write else cfg.folder / "tuyair.ahk"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(script, encoding="utf-8-sig")
    cfg.log(f"Hotkeys written to {target}. Double-click it (AutoHotkey v2) to start them.")
    return 0


# ---------------------------------------------------------------- main
def build_parser():
    p = argparse.ArgumentParser(prog="tuyair", description="Control IR devices and ACs through a Tuya IR blaster, locally.")
    p.add_argument("--config", help="config.json path (default: ./config.json or your user folder)")
    p.add_argument("--debug", action="store_true", help="print raw device traffic")
    p.add_argument("--version", action="version", version=f"tuyair {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="first-time setup wizard").set_defaults(func=cmd_setup)
    s = sub.add_parser("test", help="check the connection")
    s.add_argument("--device")
    s.set_defaults(func=cmd_test)

    s = sub.add_parser("learn", help="learn a button from the original remote (local, cloud fallback)")
    s.add_argument("name")
    s.add_argument("--device")
    s.add_argument("--timeout", type=int, default=15)
    g = s.add_mutually_exclusive_group()
    g.add_argument("--cloud", action="store_true", help="learn through the Tuya cloud only")
    g.add_argument("--local", action="store_true", help="learn locally only")
    s.set_defaults(func=cmd_learn)

    s = sub.add_parser("send", help="send saved buttons")
    s.add_argument("names", nargs="+")
    s.set_defaults(func=cmd_send)
    sub.add_parser("list", help="list saved buttons").set_defaults(func=cmd_list)
    s = sub.add_parser("delete", help="delete a saved button")
    s.add_argument("name")
    s.set_defaults(func=cmd_delete)
    s = sub.add_parser("decode", help="show what is inside a saved button")
    s.add_argument("name")
    s.set_defaults(func=cmd_decode)

    s = sub.add_parser("ac", help="air conditioner: on, off, toggle, set, temp, mode, fan, swing, cmd, status, calibrate, probe")
    s.add_argument("action", choices=["on", "off", "toggle", "set", "temp", "mode", "fan", "swing", "cmd",
                                      "status", "calibrate", "probe"])
    s.add_argument("value", nargs="?", help="temp: +1/-1/22 · mode/fan/swing: next or a name · cmd: powerful, swing...")
    s.add_argument("--mode")
    s.add_argument("--temp", type=int)
    s.add_argument("--fan")
    s.add_argument("--swing")
    s.add_argument("--cloud", action="store_true", help="calibrate: capture through the cloud")
    s.set_defaults(func=cmd_ac)

    s = sub.add_parser("remote", help="devices with a remote (TV, light, fan...): templates, add, learn, discover, "
                                      "add-code, press, list, forget, remove")
    s.add_argument("action", choices=["templates", "list", "add", "learn", "discover", "add-code", "press",
                                      "forget", "remove"])
    s.add_argument("name", nargs="?")
    s.add_argument("keys", nargs="*", help="press / forget: key ids")
    s.add_argument("--template", help="add: tv, light, fan, audio, box, projector, custom")
    s.add_argument("--title", help="add: name shown in the window")
    s.add_argument("--device", help="add: which blaster sends for this remote")
    s.add_argument("--key", action="append", help="learn: only this key (repeatable; any name for custom keys)")
    s.add_argument("--redo", action="store_true", help="learn: relearn keys that are already learned")
    s.add_argument("--address", help="discover: skip the search and use this NEC address (e.g. 0x00, 0x7F80)")
    s.add_argument("--start", help="discover: first command to try (default: where you stopped)")
    s.add_argument("--end", help="discover: last command to try (default 0xFF)")
    s.add_argument("--nec", nargs=2, metavar=("ADDRESS", "COMMAND"), help="add-code: NEC address and command")
    s.add_argument("--code", help="add-code: a raw code (base64 or hex)")
    s.add_argument("--timeout", type=int, default=15)
    g = s.add_mutually_exclusive_group()
    g.add_argument("--cloud", action="store_true")
    g.add_argument("--local", action="store_true")
    s.set_defaults(func=cmd_remote)

    sub.add_parser("panel", help="open / close the control window").set_defaults(func=cmd_panel)
    s = sub.add_parser("hotkeys", help="write an AutoHotkey v2 script from the config (Windows)")
    s.add_argument("--write", help="output file (default: next to config.json)")
    s.add_argument("--startup", action="store_true", help="write it to the Windows Startup folder")
    s.add_argument("--print", action="store_true", help="print the script instead of writing it")
    s.set_defaults(func=cmd_hotkeys)
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    if a.debug:
        try:
            import tinytuya
            tinytuya.set_debug(True)
        except ImportError:
            pass
    gui = a.cmd == "panel" or sys.stdout is None
    try:
        cfg = Config(find_config(a.config))
        if a.cmd not in ("setup",) and not cfg.path.exists():
            raise ConfigError(f"No config at {cfg.path}. Run:  tuyair setup")
        return a.func(cfg, a) or 0
    except (ConfigError, D.DeviceError, KeyError, ValueError) as e:
        msg = str(e.args[0]) if isinstance(e, KeyError) and e.args else str(e)
        try:
            cfg.log("ERROR: " + msg)
        except Exception:
            print("ERROR: " + msg, file=sys.stderr)
        if gui:
            from .panel import error_box
            error_box(msg)
        return 1
    except KeyboardInterrupt:
        return 130
