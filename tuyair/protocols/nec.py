"""NEC infrared protocol: used by most TVs, monitors, set-top boxes and cheap remotes.

A frame is: 9 ms mark, 4.5 ms space, 32 bits (LSB first), final mark.
  standard:  address, ~address, command, ~command
  extended:  address low byte, address high byte, command, ~command   (16-bit address)
"""

HDR_MARK, HDR_SPACE, BIT_MARK, ONE_SPACE, ZERO_SPACE, GAP = 9000, 4500, 560, 1690, 560, 40000


def frame_bytes(address, command):
    command &= 0xFF
    if address > 0xFF:
        return [address & 0xFF, (address >> 8) & 0xFF, command, (~command) & 0xFF]
    return [address, (~address) & 0xFF, command, (~command) & 0xFF]


def pulses(address, command):
    out = [HDR_MARK, HDR_SPACE]
    for byte in frame_bytes(address, command):
        for bit in range(8):
            out += [BIT_MARK, ONE_SPACE if (byte >> bit) & 1 else ZERO_SPACE]
    out += [BIT_MARK, GAP]
    return out


def decode(p):
    """(address, command) from NEC pulses, or None."""
    if len(p) < 67 or not (7000 < p[0] < 11000 and 3500 < p[1] < 5500):
        return None
    bits = [1 if p[i] > 1100 else 0 for i in range(3, 67, 2)]
    b = [sum(bits[j * 8 + k] << k for k in range(8)) for j in range(4)]
    if b[2] ^ b[3] != 0xFF:
        return None
    address = b[0] if b[0] ^ b[1] == 0xFF else b[0] | (b[1] << 8)
    return address, b[2]


def parse_number(text):
    return int(str(text), 0)
