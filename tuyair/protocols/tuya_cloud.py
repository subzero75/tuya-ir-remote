"""Any AC brand Smart Life supports, through the Tuya cloud.

When you add an air conditioner remote to your IR blaster in the Smart Life / Tuya app
(picking your brand and testing the code), the app creates a virtual "infrared_ac"
device. Its standard functions are power, mode, temp and wind; the cloud turns them
into the right IR code for your brand and the blaster sends it.

Needs internet and the "cloud" section in config.json. Options under "ac":
  remote_device_id   id of that virtual AC device (tuyair setup picks it for you)
"""
from . import Protocol

MODES = {"cool": 0, "heat": 1, "auto": 2, "fan": 3, "dry": 4}
FANS = {"auto": 0, "low": 1, "med": 2, "high": 3}


class TuyaCloud(Protocol):
    name = "tuya-cloud"
    title = "Any brand via Smart Life (cloud)"
    is_cloud = True
    modes = list(MODES)
    fans = list(FANS)
    swings = ["off"]
    temp_min, temp_max = 16, 30
    temp_free_modes = ("fan",)
    short_commands = {}

    def __init__(self, options=None):
        super().__init__(options)
        self.remote_id = self.options.get("remote_device_id")

    def commands(self, state, power_on):
        cmds = []
        if power_on:
            cmds.append({"code": "power", "value": True})
        cmds += [{"code": "mode", "value": MODES.get(state.get("mode", "cool"), 0)},
                 {"code": "wind", "value": FANS.get(state.get("fan", "auto"), 0)}]
        if state.get("mode") not in self.temp_free_modes:
            cmds.append({"code": "temp", "value": int(state.get("temp", 24))})
        return cmds

    def off_commands(self):
        return [{"code": "power", "value": False}]

    def send(self, cloud_cfg, commands):
        from ..device import DeviceError, cloud_client, cloud_error
        if not self.remote_id:
            raise DeviceError('No "remote_device_id" under "ac". Run:  tuyair setup')
        r = cloud_client(cloud_cfg).sendcommand(self.remote_id, {"commands": commands})
        err = cloud_error(r)
        if err:
            raise DeviceError(f"Cloud command failed: {err}")
