import json
import struct

import pytest

from tuyair import codes
from tuyair.config import Config
from tuyair.hotkeys import ahk_key, build_script
from tuyair.protocols import get_protocol

# Power-on frame captured from a real O General AR-RAJ1E remote (cool 24 C, fan high),
# as returned by Tuya cloud learning: hex of little-endian uint16 pulses.
REAL_TIMING = {"hdr_mark": 3103, "hdr_space": 1653, "bit_mark": 391, "zero_space": 438,
               "one_space": 1234, "gap": 8000}
REAL_BYTES = "14 63 00 10 10 FE 09 30 81 01 01 00 00 00 20 2D"


def real_capture_hex():
    p = get_protocol("fujitsu", {"timing": REAL_TIMING})
    pulses = p.full_state({"mode": "cool", "temp": 24, "fan": "high", "swing": "off"}, True)
    return struct.pack("<%dH" % len(pulses), *pulses).hex()


def test_full_state_matches_real_remote():
    p = get_protocol("fujitsu")
    data = p.full_bytes({"mode": "cool", "temp": 24, "fan": "high", "swing": "off"}, True)
    assert " ".join("%02X" % b for b in data) == REAL_BYTES


def test_short_command_and_off():
    p = get_protocol("fujitsu")
    assert p.short_bytes(0x39) == [0x14, 0x63, 0x00, 0x10, 0x10, 0x39, 0xC6]
    assert p.decode(p.off()) == "14 63 00 10 10 02 FD"


def test_every_generated_code_ends_with_a_gap():
    from tuyair.protocols import nec, proton
    for pulses in (get_protocol("fujitsu").off(), get_protocol("fujitsu").short("powerful"),
                   get_protocol("fujitsu").full_state({"temp": 24}, True), nec.pulses(1, 2), proton.pulses(20, 3),
                   [500, 500, 500]):
        p = codes.to_pulses(codes.pulses_to_base64(pulses))
        assert len(p) % 2 == 0 and p[-1] >= 3000


def test_hex_and_base64_are_the_same_code():
    hx = real_capture_hex()
    b64 = codes.to_base64(hx)
    assert codes.to_pulses(hx) == codes.to_pulses(b64)
    assert codes.to_base64(b64) == b64


def test_calibrate_from_capture():
    p = get_protocol("fujitsu")
    timing = p.calibrate(codes.to_pulses(real_capture_hex()))
    assert timing == REAL_TIMING
    calibrated = get_protocol("fujitsu", {"timing": timing})
    pulses = calibrated.full_state({"mode": "cool", "temp": 24, "fan": "high", "swing": "off"}, True)
    assert pulses == codes.to_pulses(real_capture_hex())


def test_calibrate_rejects_other_protocols():
    with pytest.raises(ValueError):
        get_protocol("fujitsu").calibrate([9000, 4500] + [560, 560] * 40)


@pytest.mark.parametrize("temp", [16, 22, 30])
def test_checksum(temp):
    data = get_protocol("fujitsu").full_bytes({"mode": "heat", "temp": temp, "fan": "low", "swing": "both"}, False)
    assert sum(data[7:]) & 0xFF == 0


def test_temperature_range():
    with pytest.raises(ValueError):
        get_protocol("fujitsu").full_bytes({"temp": 40}, True)


def test_hotkey_keys_are_layout_independent():
    assert ahk_key("ctrl+alt+a") == "^!vk41"
    assert ahk_key("Ctrl+Shift+F5") == "^+F5"
    assert ahk_key("win+alt+1") == "#!vk31"
    assert ahk_key("ctrl+alt+up") == "^!Up"
    with pytest.raises(ValueError):
        ahk_key("hyper+a")


def test_hotkey_script(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"devices": {"ir": {"id": "x", "key": "y"}},
                                "hotkeys": {"ctrl+alt+p": "ac cmd powerful", "ctrl+alt+t": "tv_power",
                                            "ctrl+alt+a": "@panel"}}))
    script = build_script(Config(path))
    assert '^!vk50:: Tuyair("ac cmd powerful"' in script
    assert '^!vk54:: Tuyair("send tv_power"' in script
    assert '^!vk41:: Tuyair("panel"' in script


def test_ac_state_flow(tmp_path, monkeypatch):
    from tuyair.ac import AC
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"devices": {"ir": {"id": "x", "key": "y"}}, "ac": {"protocol": "fujitsu"}}))
    cfg = Config(path)
    ac = AC(cfg)
    sent = []
    monkeypatch.setattr(ac, "send_pulses", lambda p: sent.append(ac.protocol.decode(p)))
    ac.set(temp=22)                      # off: stored, not sent
    assert sent == []
    st = ac.on(fan="high")
    assert st["power"] and st["temp"] == 22 and sent[-1].startswith("14 63 00 10 10 FE")
    ac.step("temp", "+1")
    assert ac.read_state()["temp"] == 23 and sent[-1].split()[8] == "70"   # power bit cleared, 23C
    ac.step("mode", "next")
    assert ac.read_state()["mode"] == "dry"
    ac.command("powerful")
    assert ac.read_state()["powerful"] is True
    ac.off()
    assert ac.read_state()["power"] is False and sent[-1] == "14 63 00 10 10 02 FD"


def test_cloud_protocol_commands():
    p = get_protocol("tuya-cloud", {"remote_device_id": "r1"})
    assert p.is_cloud
    on = p.commands({"mode": "cool", "temp": 22, "fan": "high"}, True)
    assert on == [{"code": "power", "value": True}, {"code": "mode", "value": 0},
                  {"code": "wind", "value": 3}, {"code": "temp", "value": 22}]
    fan_only = p.commands({"mode": "fan", "temp": 22, "fan": "low"}, False)
    assert {"code": "temp", "value": 22} not in fan_only and fan_only[0]["code"] == "mode"
    assert p.off_commands() == [{"code": "power", "value": False}]


def test_ac_cloud_flow(tmp_path, monkeypatch):
    from tuyair.ac import AC
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"devices": {"ir": {"id": "x", "key": "y"}}, "cloud": {"key": "k", "secret": "s"},
                                "ac": {"protocol": "tuya-cloud", "remote_device_id": "r1"}}))
    ac = AC(Config(path))
    sent = []
    monkeypatch.setattr(ac.protocol, "send", lambda cloud, cmds: sent.append(cmds))
    ac.write_state({"power": False, "mode": "cool", "temp": 24, "fan": "quiet", "swing": "both"})
    st = ac.on()
    assert st["fan"] == "auto" and st["swing"] == "off"          # normalized to what the protocol supports
    assert sent[-1][0] == {"code": "power", "value": True}
    ac.step("temp", "-1")
    assert {"code": "temp", "value": 23} in sent[-1] and sent[-1][0]["code"] != "power"
    with pytest.raises(KeyError):
        ac.command("powerful")                                    # not available through the cloud
    ac.off()
    assert sent[-1] == [{"code": "power", "value": False}]


def test_link_rediscovers_new_ip(tmp_path, monkeypatch):
    from tuyair import device as D
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"devices": {"ir": {"id": "x", "key": "y", "ip": "10.0.0.5", "version": 3.3}}}))
    cfg = Config(path)
    calls = []

    class Handle:
        def __init__(self, ip):
            self.ip = ip

        def send_button(self, code):
            calls.append(self.ip)
            return None if self.ip == "10.0.0.9" else {"Error": "Network Error: Unable to Connect", "Err": "901"}

    monkeypatch.setattr(D, "open_local", lambda dev: Handle(dev["ip"]))
    monkeypatch.setattr(D, "find_on_network", lambda dev_id: ("10.0.0.9", "3.5"))
    D.Link(cfg, "ir").send(codes.pulses_to_base64([100, 200, 300]))
    assert calls == ["10.0.0.5", "10.0.0.9"]
    saved = json.loads(path.read_text())["devices"]["ir"]
    assert saved["ip"] == "10.0.0.9" and saved["version"] == 3.5


def test_link_does_not_retry_on_other_errors(tmp_path, monkeypatch):
    from tuyair import device as D
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"devices": {"ir": {"id": "x", "key": "y", "ip": "10.0.0.5"}}}))

    class Handle:
        def send_button(self, code):
            return {"Error": "Unexpected Payload from Device", "Err": "904"}

    monkeypatch.setattr(D, "open_local", lambda dev: Handle())
    monkeypatch.setattr(D, "find_on_network", lambda dev_id: pytest.fail("should not search"))
    with pytest.raises(D.DeviceError):
        D.Link(Config(path), "ir").send("AAAA")


def test_templates_layout_shows_only_learned_keys():
    from tuyair.templates import TEMPLATES, keys_of, layout
    assert "vol_up" in keys_of("tv") and keys_of("custom") == []
    rows = layout("tv", ["power", "vol_up", "ok", "my_extra"])
    assert rows[0] == ["power", None, None]
    assert ["vol_up", None, None] in rows and [None, "ok", None] in rows
    assert rows[-1] == ["my_extra", None, None]                    # custom keys go at the end
    assert all(len(r) == 3 for t in TEMPLATES.values() for r in t)


def test_every_template_key_has_a_label():
    from tuyair.i18n import TEXTS
    from tuyair.templates import TEMPLATES, keys_of
    for lang, t in TEXTS.items():
        for name in TEMPLATES:
            assert name in t["templates"], (lang, name)
    for name in TEMPLATES:
        for k in keys_of(name):
            assert k in TEXTS["en"]["keys"], k


def test_remote_add_save_press(tmp_path, monkeypatch):
    from tuyair import device as D
    from tuyair import remotes as R
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"devices": {"ir": {"id": "x", "key": "y", "ip": "1.1.1.1"}}}))
    cfg = Config(path)
    R.add(cfg, "tv", "tv", "Living room TV")
    with pytest.raises(ValueError):
        R.add(cfg, "tv", "tv")
    with pytest.raises(ValueError):
        R.add(cfg, "x", "toaster")
    R.save_key(cfg, "tv", "power", codes.pulses_to_base64([1, 2, 3]))
    sent = []

    class Handle:
        def send_button(self, code):
            sent.append(code)

    monkeypatch.setattr(D, "open_local", lambda dev: Handle())
    monkeypatch.setattr(cfg, "log", lambda m: None)
    R.press(cfg, "tv", ["power"])
    assert sent == [codes.pulses_to_base64([1, 2, 3])]
    with pytest.raises(KeyError):
        R.press(cfg, "tv", ["vol_up"])
    saved = json.loads(path.read_text())["remotes"]["tv"]
    assert saved["title"] == "Living room TV" and "power" in saved["keys"]


def test_hotkey_remote_action(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"devices": {"ir": {"id": "x", "key": "y"}},
                                "hotkeys": {"ctrl+alt+v": "remote tv vol_up"}}))
    assert '^!vk56:: Tuyair("remote press tv vol_up"' in build_script(Config(path))


def test_nec_roundtrip():
    from tuyair.protocols import nec
    assert nec.frame_bytes(0x04, 0x08) == [0x04, 0xFB, 0x08, 0xF7]
    assert nec.decode(nec.pulses(0x04, 0x08)) == (0x04, 0x08)
    assert nec.decode(nec.pulses(0x1234, 0x12)) == (0x1234, 0x12)       # extended address
    assert nec.decode([3000, 1500] + [400, 400] * 40) is None


def test_find_address_narrows_to_one():
    from tuyair import discover as X
    from tuyair.protocols import nec
    target = 0x5A
    batch = []

    def send(c):
        batch.append(nec.decode(codes.to_pulses(c))[0])

    def answer(prompt):
        reacted = target in batch
        batch.clear()
        return "y" if reacted else ""

    found = X.find_address(send, X.Asker(answer), say=lambda *a: None)
    assert found == target


def test_find_address_common_first():
    from tuyair import discover as X
    from tuyair.protocols import nec
    sent = []
    X.find_address(lambda c: sent.append(nec.decode(codes.to_pulses(c))[0]),
                   X.Asker(lambda p: "q"), say=lambda *a: None)
    assert set(sent) == set(X.COMMON_ADDRESSES[:8])            # first group = common addresses


def test_map_commands_labels_and_resume():
    from tuyair import discover as X
    answers = iter(["", "power", "r", "vol up", "b", "", "q"])
    saved, progress = {}, []
    nxt = X.map_commands(lambda c: None, X.Asker(lambda p: next(answers)),
                         lambda label, cmd: saved.__setitem__(label, cmd), start=0x10, end=0x20,
                         address=0x01, say=lambda *a: None, on_progress=progress.append)
    assert saved == {"power": 0x11, "vol_up": 0x12}
    assert nxt == 0x13 and progress[-1] == 0x13
    done = X.map_commands(lambda c: None, X.Asker(lambda p: ""), lambda l, c: None, start=0, end=2,
                          say=lambda *a: None)
    assert done is None                                  # finished the range


def test_map_commands_marks_and_reviews():
    from tuyair import discover as X
    answers = iter(["?", "", "?", "q"])
    seen = []
    X.map_commands(lambda c: None, X.Asker(lambda p: next(answers)), lambda l, c: None, start=0, end=9,
                   say=lambda *a: None, on_seen=seen.append)
    assert seen == [0, 2]
    answers = iter(["mute", ""])
    saved = {}
    X.map_commands(lambda c: None, X.Asker(lambda p: next(answers)), lambda l, c: saved.__setitem__(l, c),
                   say=lambda *a: None, only=seen)
    assert saved == {"mute": 0}


def test_proton_roundtrip():
    from tuyair.protocols import proton
    p = proton.pulses(20, 0x0B)
    assert p[:2] == [8000, 4000] and len(p) == 2 + 16 + 2 + 16 + 2 and p[-1] >= 20000
    assert proton.decode(p) == (20, 0x0B)
    from tuyair.protocols import nec
    assert proton.decode(nec.pulses(1, 2)) is None and nec.decode(p) is None


def test_find_address_proton_tries_daewoo_device_first():
    from tuyair import discover as X
    from tuyair.protocols import proton
    batch = []

    def send(c):
        batch.append(proton.decode(codes.to_pulses(c))[0])

    def answer(prompt):
        reacted = 20 in batch
        batch.clear()
        return "y" if reacted else ""

    assert X.find_address(send, X.Asker(answer), say=lambda *a: None, protocol="proton") == 20


def test_cloud_map_keys_are_sent_through_the_cloud(tmp_path, monkeypatch):
    from tuyair import remotes as R
    calls = []

    class FakeCloud:
        def cloudrequest(self, url, action=None, post=None, query=None):
            calls.append((url, action, post))
            if url.endswith("/remotes/r1/command"):
                return {"success": False, "code": 1108, "msg": "uri path invalid"}
            return {"success": True, "result": True}

    monkeypatch.setattr(R, "cloud_client", lambda cloud_cfg, device_id=None: FakeCloud())
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"devices": {"ir": {"id": "IR1", "key": "y"}}, "cloud": {"key": "k", "secret": "s"}}))
    cfg = Config(path)
    monkeypatch.setattr(cfg, "log", lambda m: None)
    R.add(cfg, "magic", "tv")
    ref = {"remote_id": "r1", "category_id": 2, "key": "Power", "key_id": 1}
    cfg.data["remotes"]["magic"]["keys"]["vol_up"] = {"cloud": ref}
    R.press(cfg, "magic", ["vol_up"])
    assert calls[0] == ("/v2.0/infrareds/IR1/remotes/r1/command", "POST", {"category_id": 2, "key_id": 1, "key": "Power"})
    assert calls[1][0] == "/v2.0/infrareds/IR1/remotes/r1/raw/command" and ref["path"].endswith("raw/command")
    calls.clear()
    R.press(cfg, "magic", ["vol_up"])                         # remembered path: one call only
    assert len(calls) == 1


def test_timing_fix_shifts_marks_and_spaces():
    assert codes.adjust([3324, 1574, 448, 390, 448], {"mark": -57, "space": 50}) == [3267, 1624, 391, 440, 391]
    assert codes.adjust([100, 200]) == [100, 200]


def test_ac_uses_device_timing_fix(tmp_path, monkeypatch):
    from tuyair.ac import AC
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"devices": {"ir": {"id": "x", "key": "y", "timing_fix": {"mark": -57, "space": 50}}},
                                "ac": {"protocol": "fujitsu"}}))
    ac = AC(Config(path))
    sent = []
    monkeypatch.setattr(ac, "_link", type("L", (), {"send": lambda self, c: sent.append(codes.to_pulses(c))})())
    ac.command("powerful")
    assert sent[0][:4] == [3324 - 57, 1574 + 50, 448 - 57, 390 + 50]


def test_clean_label_guards():
    from tuyair import discover as X
    no = X.Asker(lambda p: "")
    assert X.clean_label("vol_up", no, {}) == "vol_up"
    assert X.clean_label('python_-m_tuyair_remote_discover', no, {}) is None
    assert X.clean_label("menu", no, {"menu": {}}) is None
    assert X.clean_label("menu", X.Asker(lambda p: "y"), {"menu": {}}) == "menu"


def test_map_commands_does_not_claim_a_refused_save():
    from tuyair import discover as X
    said = []
    answers = iter(["down", "q"])
    X.map_commands(lambda c: None, X.Asker(lambda p: next(answers)), lambda l, c: False, start=0, end=3,
                   say=said.append)
    assert not any("saved down" in s for s in said)


def test_remote_rename(tmp_path):
    from tuyair.cli import main
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"devices": {"ir": {"id": "x", "key": "y"}},
                                "remotes": {"tv": {"template": "tv", "device": "ir", "keys": {"mode": {"code": "AAAA"}}}}}))
    assert main(["--config", str(path), "remote", "rename", "tv", "mode", "picture_mode"]) == 0
    assert list(json.loads(path.read_text())["remotes"]["tv"]["keys"]) == ["picture_mode"]
    assert main(["--config", str(path), "remote", "rename", "tv", "nope", "x"]) == 1


def test_second_address_search_skips_first_and_starts_nearby():
    from tuyair import discover as X
    from tuyair.protocols import nec
    groups = X.address_groups(exclude={0x20}, first=X.neighbours(0x20))
    flat = [a for g in groups for a in g]
    assert 0x20 not in flat and flat[:2] == [0x21, 0x1F] and len(flat) == 255
    target, batch = 0x21, []

    def send(c):
        batch.append(nec.decode(codes.to_pulses(c))[0])

    def answer(p):
        hit = target in batch
        batch.clear()
        return "y" if hit else ""
    assert X.find_address(send, X.Asker(answer), say=lambda *a: None, exclude={0x20},
                          first=X.neighbours(0x20)) == 0x21


def test_auto_address_search_stops_on_keypress_and_confirms():
    from tuyair import discover as X
    from tuyair.protocols import nec
    target = 0x23
    sent = []
    state = {"pressed": False}

    def send(c):
        sent.append(nec.decode(codes.to_pulses(c)))

    def pressed():
        # the user presses a key one step after the device reacted
        if not state["pressed"] and len(sent) >= 2 and sent[-2][0] == target:
            state["pressed"] = True
            return True
        return False

    def answer(p):
        return "y" if "0x23" in p else ""

    found = X.find_address_auto(send, X.Asker(answer), say=lambda *a: None, commands=[0x03], exclude={0x20},
                                first=X.neighbours(0x20), delay=0.1, pressed=pressed, sleep=lambda s: None)
    assert found == 0x23


def test_one_by_one_address_search_and_resume():
    from tuyair import discover as X
    from tuyair.protocols import nec
    target, last = 0x1E, []

    def send(c):
        last.append(nec.decode(codes.to_pulses(c))[0])

    progress = []
    answers = iter(["", "", "q"])
    assert X.find_address_one_by_one(send, X.Asker(lambda p: next(answers)), say=lambda *a: None, commands=[3],
                                     exclude={0x20}, first=X.neighbours(0x20), on_progress=progress.append) is None
    assert progress == [1, 2]

    def answer(p):
        return "y" if last[-1] == target else ""
    found = X.find_address_one_by_one(send, X.Asker(answer), say=lambda *a: None, commands=[3], exclude={0x20},
                                      first=X.neighbours(0x20), start_at=progress[-1])
    assert found == target
