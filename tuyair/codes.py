"""IR code formats.

Tuya IR blasters use raw timings: a list of pulse durations in microseconds
(mark, space, mark, ...), packed as little-endian unsigned 16-bit integers.

* Local learning and local sending use that byte string encoded as **base64**.
* Tuya cloud learning returns the very same bytes encoded as **hex**.

Everything in this project stores whatever it got and converts with
:func:`to_base64` right before sending.
"""
import base64
import string
import struct


TRAILING_GAP = 20000  # us


def pulses_to_base64(pulses):
    """Pack pulses for the blaster. Real captures always end with a space (the gap after the last
    mark); codes ending on a mark were not sent reliably, so one is added when missing."""
    pulses = [max(1, min(65535, int(p))) for p in pulses]
    if len(pulses) % 2:
        pulses.append(TRAILING_GAP)
    return base64.b64encode(struct.pack("<%dH" % len(pulses), *pulses)).decode("ascii")


def is_hex_code(code):
    c = code.strip()
    return len(c) >= 8 and len(c) % 4 == 0 and all(ch in string.hexdigits for ch in c)


def to_base64(code):
    """Accept base64 (local) or hex (cloud) and return base64, the format local sending expects."""
    c = code.strip()
    if is_hex_code(c):
        return base64.b64encode(bytes.fromhex(c)).decode("ascii")
    return c


def to_pulses(code):
    raw = base64.b64decode(to_base64(code))
    n = len(raw) // 2
    return list(struct.unpack("<%dH" % n, raw[: n * 2]))
