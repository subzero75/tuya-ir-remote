"""Proton infrared protocol (used by Daewoo and many white-label / Chinese TVs).

Frame: 8 ms mark, 4 ms space, 8-bit device (LSB first), 0.5 ms mark + 4 ms space,
8-bit command (LSB first), final 0.5 ms mark. Unit 500 us: 0 = mark, space;
1 = mark, 3 x space.
"""

HDR_MARK, HDR_SPACE, UNIT, MID_SPACE, GAP = 8000, 4000, 500, 4000, 40000


def _bits(byte):
    out = []
    for bit in range(8):
        out += [UNIT, UNIT * 3 if (byte >> bit) & 1 else UNIT]
    return out


def pulses(address, command):
    return [HDR_MARK, HDR_SPACE] + _bits(address & 0xFF) + [UNIT, MID_SPACE] + _bits(command & 0xFF) + [UNIT, GAP]


def decode(p):
    """(device, command) from Proton pulses, or None."""
    if len(p) < 35 or not (6500 < p[0] < 9500 and 3000 < p[1] < 5000) or not 3000 < p[19] < 5000:
        return None
    dev = sum((1 if p[3 + 2 * i] > 1000 else 0) << i for i in range(8))
    cmd = sum((1 if p[21 + 2 * i] > 1000 else 0) << i for i in range(8))
    return dev, cmd
