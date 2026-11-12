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
