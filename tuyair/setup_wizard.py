"""Interactive first-time setup: cloud credentials -> pick the blaster -> find it on the LAN -> test."""
from . import device as D
from .protocols import available

REGIONS = {"eu": "Central Europe", "us": "Western America", "us-e": "Eastern America", "eu-w": "Western Europe",
           "in": "India", "cn": "China", "sg": "Singapore"}
IR_CATEGORIES = ("wnykq", "hwktwkq", "infrared")


def ask(prompt, default=None, secret=False):
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val or (default or "")


def yes(prompt, default=True):
    d = "Y/n" if default else "y/N"
    v = input(f"{prompt} [{d}]: ").strip().lower()
    return default if not v else v in ("y", "yes", "ن", "نعم")


def run(cfg):
    tinytuya = D._tinytuya()
    print(f"\nConfig file: {cfg.path}\n")
    print("Step 1/4 - Tuya cloud project (needed once to read your blaster's local key).")
    print("  Create one at https://iot.tuya.com > Cloud > Development > Create Cloud Project,")
    print("  then Devices > Link App Account and scan the QR code with the Smart Life / Tuya app.\n")
    cloud = dict(cfg.get("cloud") or {})
    cloud["key"] = ask("Access ID / Client ID", cloud.get("key"))
    cloud["secret"] = ask("Access Secret / Client Secret", cloud.get("secret"))
    print("  Data centers: " + ", ".join(f"{k} ({v})" for k, v in REGIONS.items()))
    cloud["region"] = ask("Data center", cloud.get("region", "eu"))
    c = tinytuya.Cloud(apiRegion=cloud["region"], apiKey=cloud["key"], apiSecret=cloud["secret"])
    devices = c.getdevices(verbose=False)
    if not isinstance(devices, list) or not devices:
        print(f"\nNo devices returned: {devices}")
        print("Check the key/secret, that your app account is linked, and try another data center.")
        return 1
    cfg.data["cloud"] = cloud

    print("\nStep 2/4 - Pick your IR blaster:")
    devices.sort(key=lambda d: d.get("category") not in IR_CATEGORIES)
    for i, d in enumerate(devices, 1):
        tag = "  <- IR blaster" if d.get("category") in IR_CATEGORIES else ""
        print(f"  {i}. {d.get('name')}  ({d.get('category')}, {d.get('id')}){tag}")
    choice = int(ask("Number", "1")) - 1
    dev = devices[choice]

    print("\nStep 3/4 - Finding it on your network (about 20 seconds)...")
    found = {}
    try:
        found = tinytuya.deviceScan(verbose=False, maxretry=18) or {}
    except Exception as e:
        print(f"  scan failed: {e}")
    match = next((v for v in found.values() if v.get("gwId") == dev["id"] or v.get("id") == dev["id"]), None)
    if match:
        ip, version = match.get("ip"), match.get("version", "3.3")
        print(f"  found at {ip}, protocol {version}")
    else:
        print("  Not found. Make sure it is powered and on the same network as this PC,")
        print("  and allow Python through the firewall (UDP 6666/6667/7000). Enter it by hand:")
        ip = ask("  IP address (see your router's device list)")
        version = ask("  Protocol version", "3.3")

    name = ask("\nName for this blaster", "ir")
    cfg.data.setdefault("devices", {})[name] = {"id": dev["id"], "ip": ip, "key": dev.get("key", ""),
                                                "version": float(version), "control_type": 2}
    cfg.data["default_device"] = cfg.data.get("default_device") or name
    cfg.save()

    print("\nStep 4/4 - Testing the connection...")
    ok, msg = D.Link(cfg, name).check()
    print(f"  {'OK' if ok else 'FAILED'}: {msg}")

    if yes("\nIs it an air conditioner you want to control (panel + hotkeys)?"):
        protos = available()
        print("  Protocols: " + ", ".join(f"{k} ({v})" for k, v in protos.items()))
        print("  fujitsu works locally and fast; tuya-cloud works with any brand the Smart Life app supports.")
        proto = ask("  Protocol", "fujitsu")
        ac = {**(cfg.get("ac") or {}), "device": name, "protocol": proto}
        if proto == "tuya-cloud":
            remotes = [d for d in devices if d.get("category") == "infrared_ac" or "air" in str(d.get("category"))]
            if not remotes:
                print("  No AC remote found. In the Smart Life app open your IR blaster, add an air conditioner")
                print("  remote (pick your brand, test the code), then run  tuyair setup  again.")
            else:
                for i, d in enumerate(remotes, 1):
                    print(f"    {i}. {d.get('name')}  ({d.get('id')})")
                ac["remote_device_id"] = remotes[int(ask("  AC remote number", "1")) - 1]["id"]
        cfg.data["ac"] = ac
        cfg.save()
        print("\nNext steps:")
        print("  tuyair ac on / tuyair ac off          test power")
        print("  tuyair ac calibrate                   if 'on' doesn't work: capture your remote's power button")
        print("  tuyair panel                          control window")
        print("  tuyair hotkeys --startup              Windows hotkeys, started with Windows")
    else:
        print("\nNext: tuyair learn <name>  then  tuyair send <name>")
    print(f"\nSaved to {cfg.path}")
    return 0
