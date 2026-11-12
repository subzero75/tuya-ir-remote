"""Find the IR codes of a device whose remote is lost.

Protocols: NEC (most TVs, monitors, boxes) and Proton (Daewoo and many white-label TVs).

Step 1 - address: send a few test commands to groups of addresses and ask whether the
         device reacted; a group that reacts is split in half until one address is left.
Step 2 - commands: send each command of that address and let the user say what happened
         (a key id such as vol_up, or any name). Labelled commands are saved as keys of a
         remote, so they show up in the window and can be used in hotkeys.

Progress is saved after every answer, so it can be stopped and resumed.
The functions take `send(code)` and `ask(prompt)` callables, so they are easy to test.
"""
from .codes import adjust, pulses_to_base64
from .protocols import nec, proton

PROTOCOLS = {"nec": nec, "proton": proton}

# Addresses used by many brands and generic boards, tried first.
COMMON = {
    "nec": [0x00, 0x01, 0x02, 0x03, 0x04, 0x08, 0x10, 0x14, 0x15, 0x20, 0x40, 0x80, 0x86, 0x7F, 0xBF, 0xFE],
    "proton": [20, 0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x15, 0x16, 0x1F, 0x30, 0x50, 0xFF],
}
COMMON_ADDRESSES = COMMON["nec"]
# Commands sent to each address while searching: spread out so at least one usually shows
# something (a number, volume bar, menu, input list...).
PROBE_COMMANDS = [0x02, 0x0C, 0x12, 0x1A, 0x40, 0x45]

YES = ("y", "yes", "ن", "نعم")


FIX = {}   # blaster timing compensation, set by the caller (see codes.adjust)


def code(address, command, protocol="nec"):
    return pulses_to_base64(adjust(PROTOCOLS[protocol].pulses(address, command), FIX))


def address_groups(size=16, protocol="nec"):
    common = COMMON[protocol]
    rest = [a for a in range(256) if a not in common]
    groups = [common[i:i + size // 2] for i in range(0, len(common), size // 2)]
    groups += [rest[i:i + size] for i in range(0, len(rest), size)]
    return groups


def probe(send, addresses, commands=PROBE_COMMANDS, protocol="nec"):
    for a in addresses:
        for c in commands:
            send(code(a, c, protocol))


def find_address(send, ask, say=print, commands=PROBE_COMMANDS, protocol="nec"):
    """Return the address the device answers to, or None."""
    groups = address_groups(protocol=protocol)
    for gi, group in enumerate(groups, 1):
        say(f"\nGroup {gi}/{len(groups)}: addresses {group[0]:#04x}..{group[-1]:#04x} - watch the screen...")
        probe(send, group, commands, protocol)
        if ask("Did the device react at all (number, volume, menu, input, turned off...)? [y/N/q]: ") == "q":
            return None
        if ask.last not in YES:
            continue
        while len(group) > 1:
            half = group[: len(group) // 2]
            say(f"  narrowing down: {half[0]:#04x}..{half[-1]:#04x} ({len(group)} left)...")
            probe(send, half, commands, protocol)
            answer = ask("  React this time? [y/N]: ")
            group = half if answer in YES else group[len(group) // 2:]
        say(f"\nAddress found: {group[0]:#04x}")
        return group[0]
    return None


class Asker:
    """input() wrapper that remembers the last answer (lower-cased, stripped)."""

    def __init__(self, fn=input):
        self.fn = fn
        self.last = ""

    def __call__(self, prompt):
        self.last = self.fn(prompt).strip().lower()
        return self.last


def map_commands(send, ask, save_label, start=0, end=255, address=0, say=print, on_progress=None,
                 protocol="nec"):
    """Send each command and record what the user says it does. Returns the next command to try."""
    say("\nFor each command: Enter = nothing happened, type what it did (e.g. power, vol_up, menu, "
        "num_1, input, or any name), r = send again, b = back one, q = stop (progress is saved).")
    cmd = start
    while cmd <= end:
        send(code(address, cmd, protocol))
        answer = ask(f"[{cmd:#04x}] what happened? ")
        if answer == "q":
            break
        if answer == "r":
            continue
        if answer == "b":
            cmd = max(start, cmd - 1)
            continue
        if answer:
            save_label(answer.replace(" ", "_"), cmd)
            say(f"  saved {answer} = {cmd:#04x}")
        cmd += 1
        if on_progress:
            on_progress(cmd)
    return cmd
