"""AC protocol registry.

A protocol turns an AC state (power, mode, temperature, fan, swing) and short
commands (powerful, swing, ...) into raw IR pulses. To add a brand, create a
module with a class following :class:`Protocol` and register it in PROTOCOLS.
"""


class Protocol:
    """Interface every protocol implements."""

    name = "base"
    title = "Base"
    is_cloud = False            # True: sends through the Tuya cloud instead of raw IR pulses
    modes = ["cool"]            # first one is the default
    fans = ["auto"]
    swings = ["off"]
    temp_min, temp_max = 16, 30
    temp_free_modes = ()        # modes where temperature is not used (e.g. fan only)
    short_commands = {}         # name -> description

    def __init__(self, options=None):
        self.options = options or {}

    def full_state(self, state, power_on):
        """Pulses for the full state. power_on=True also switches the AC on."""
        raise NotImplementedError

    def off(self):
        raise NotImplementedError

    def short(self, name):
        raise NotImplementedError

    def decode(self, pulses):
        """Human-readable bytes, or None if the pulses don't look like this protocol."""
        return None

    def calibrate(self, pulses):
        """Return timing options measured from a real capture (dict), or raise ValueError."""
        raise ValueError("calibration not supported")


def _registry():
    from . import fujitsu, tuya_cloud

    return {"fujitsu": fujitsu.Fujitsu, "tuya-cloud": tuya_cloud.TuyaCloud}


def get_protocol(name, options=None):
    protocols = _registry()
    if name not in protocols:
        raise KeyError(f"Unknown protocol '{name}'. Available: {', '.join(protocols)}")
    return protocols[name](options)


def available():
    return {k: v.title for k, v in _registry().items()}
