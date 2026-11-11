"""Talking to the blaster: locally with tinytuya, or through the Tuya cloud for learning."""
import time

from .codes import to_base64

CLOUD_HINTS = {
    28841101: 'Authorize "IR Control Hub Open Service" in your Tuya cloud project (Service API > Go to Authorize).',
    1010: "The cloud token expired or the API key/secret is wrong. Check the \"cloud\" section.",
    1106: "Permission denied: link your Smart Life / Tuya app account to the cloud project (Devices > Link App Account).",
}


class DeviceError(Exception):
    pass


def _tinytuya():
    try:
        import tinytuya  # noqa: F401
        return tinytuya
    except ImportError:
        raise DeviceError("tinytuya is not installed. Run:  pip install tinytuya")


def open_local(dev):
    """Open an IR blaster described by a config "devices" entry."""
    _tinytuya()
    from tinytuya.Contrib import IRRemoteControlDevice

    for key in ("id", "key"):
        if not dev.get(key):
            raise DeviceError(f"Device is missing '{key}'. Run:  tuyair setup")
    kwargs = {"version": float(dev.get("version", 3.3))}
    if dev.get("control_type"):
        kwargs["control_type"] = int(dev["control_type"])
    return IRRemoteControlDevice(dev["id"], dev.get("ip") or "Auto", dev["key"], **kwargs)


def is_error(result):
    return isinstance(result, dict) and "Error" in result


def reachable(result):
    """status() result -> (ok, message). Many IR blasters can't report status and answer
    'json obj data unvalid'; that reply was decrypted with the local key, so the device is fine."""
    if not result:
        return False, "no answer"
    if is_error(result):
        if "unvalid" in str(result.get("Payload", "")) or "unvalid" in str(result.get("invalid_json", "")):
            return True, "reachable, key accepted (this blaster has no status to report)"
        hint = ""
        if str(result.get("Err")) in ("901", "905"):
            hint = " - check the IP, that the blaster is powered, and the firewall"
        if str(result.get("Err")) in ("914",):
            hint = " - wrong local key or version (re-run setup if the blaster was re-paired)"
        return False, f"{result.get('Error')}{hint}"
    return True, "OK"


def send(dev_handle, code):
    result = dev_handle.send_button(to_base64(code))
    if is_error(result):
        raise DeviceError(f"Send failed: {result.get('Error')}")


def learn_local(dev_handle, timeout=15):
    return dev_handle.receive_button(timeout=timeout)


# ------------------------------------------------------------------ cloud
def cloud_client(cloud_cfg, device_id):
    tinytuya = _tinytuya()
    if not cloud_cfg or not cloud_cfg.get("key") or not cloud_cfg.get("secret"):
        raise DeviceError('Cloud is not configured. Run "tuyair setup" or add a "cloud" section '
                          '({"region": "eu", "key": "...", "secret": "..."}).')
    return tinytuya.Cloud(apiRegion=cloud_cfg.get("region", "eu"), apiKey=cloud_cfg["key"],
                          apiSecret=cloud_cfg["secret"], apiDeviceID=device_id)


def cloud_error(r):
    if isinstance(r, dict) and not r.get("success", False):
        code = r.get("code")
        return f"{r.get('msg', r)}" + (f"\n  -> {CLOUD_HINTS[code]}" if code in CLOUD_HINTS else "")
    return None


def learn_cloud(cloud_cfg, device_id, timeout=30, on_ready=None):
    """Put the blaster in learning mode through the cloud and return the learned code (hex)."""
    c = cloud_client(cloud_cfg, device_id)
    base = f"/v2.0/infrareds/{device_id}"
    r = c.cloudrequest(f"{base}/learning-state", action="PUT", query={"state": "true"})
    err = cloud_error(r)
    if err:
        raise DeviceError(f"Could not start cloud learning: {err}")
    start = int(time.time() * 1000)
    if on_ready:
        on_ready()
    try:
        end = time.time() + timeout
        while time.time() < end:
            time.sleep(1.5)
            r = c.cloudrequest(f"{base}/learning-codes", query={"learning_time": start})
            res = r.get("result") if isinstance(r, dict) else None
            if isinstance(res, dict) and res.get("success") and res.get("code"):
                return res["code"]
    finally:
        c.cloudrequest(f"{base}/learning-state", action="PUT", query={"state": "false"})
    return None
