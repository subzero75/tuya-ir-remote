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


def address_groups(size=16, protocol="nec", exclude=(), first=()):
    common = [a for a in list(first) + COMMON[protocol] if a not in exclude]
    common = list(dict.fromkeys(common))
    rest = [a for a in range(256) if a not in common and a not in exclude]
    groups = [common[i:i + size // 2] for i in range(0, len(common), size // 2)]
    groups += [rest[i:i + size] for i in range(0, len(rest), size)]
    return groups


def probe(send, addresses, commands=PROBE_COMMANDS, protocol="nec"):
    for a in addresses:
        for c in commands:
            send(code(a, c, protocol))


def neighbours(address):
    """Addresses a second set of buttons often uses: next to the first one, or one bit different."""
    near = [address + d for d in (1, -1, 2, -2, 3, -3, 4, -4)]
    bits = [address ^ (1 << b) for b in range(8)]
    return [a for a in near + bits if 0 <= a <= 0xFF]


def find_address(send, ask, say=print, commands=PROBE_COMMANDS, protocol="nec", exclude=(), first=()):
    """Return an address the device answers to (skipping `exclude`), or None."""
    groups = address_groups(protocol=protocol, exclude=set(exclude), first=first)
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


def clean_label(label, ask, existing=None):
    """Guard against pasting a command into the prompt or overwriting a key by accident."""
    suspicious = len(label) > 24 or any(ch in label for ch in '()"%;=\\') or label.startswith(("python", "pip", "-"))
    if suspicious and ask(f"  Save a key named '{label[:40]}'? That looks like it was pasted by mistake. [y/N]: ") not in YES:
        return None
    if existing is not None and label in existing:
        if ask(f"  '{label}' already exists. Replace it? [y/N]: ") not in YES:
            return None
    return label


class Asker:
    """input() wrapper that remembers the last answer (lower-cased, stripped)."""

    def __init__(self, fn=input):
        self.fn = fn
        self.last = ""

    def __call__(self, prompt):
        self.last = self.fn(prompt).strip().lower()
        return self.last


def map_commands(send, ask, save_label, start=0, end=255, address=0, say=print, on_progress=None,
                 protocol="nec", on_seen=None, only=None):
    """Send each command and record what the user says it does. Returns the next command to try."""
    say("\nFor each command: Enter = nothing happened, type what it did (e.g. power, vol_up, menu, "
        "num_1, input, or any name), r = send again, b = back one, q = stop (progress is saved).")
    todo = list(only) if only is not None else list(range(start, end + 1))
    i = 0
    while i < len(todo):
        cmd = todo[i]
        send(code(address, cmd, protocol))
        answer = ask(f"[{cmd:#04x}] what happened? ")
        if answer == "q":
            break
        if answer == "r":
            continue
        if answer == "b":
            i = max(0, i - 1)
            continue
        if answer == "?":
            if on_seen:
                on_seen(cmd)
        elif answer:
            label = answer.replace(" ", "_")
            if save_label(label, cmd) is not False:
                say(f"  saved {label} = {cmd:#04x}")
        i += 1
        if on_progress:
            on_progress(cmd + 1)
    return todo[i] if i < len(todo) else None


# ---------------------------------------------------------------- auto mode (just watch)
def key_pressed():
    """True if a key was pressed in the console (doesn't wait)."""
    try:
        import msvcrt  # Windows
        if msvcrt.kbhit():
            while msvcrt.kbhit():
                msvcrt.getwch()
            return True
        return False
    except ImportError:
        import select
        import sys
        if select.select([sys.stdin], [], [], 0)[0]:
            sys.stdin.readline()
            return True
        return False


def auto_scan(items, send, delay=0.7, say=print, pressed=key_pressed, sleep=None):
    """Send items one after another; return the index being sent when the user pressed a key, or None."""
    import time
    sleep = sleep or time.sleep
    for i, (address, command) in enumerate(items):
        say(f"  {i + 1}/{len(items)}  address {address:#04x}  command {command:#04x}")
        send(code(address, command, AUTO_PROTOCOL[0]))
        steps = max(1, int(delay / 0.1))
        for _ in range(steps):
            if pressed():
                return i
            sleep(delay / steps)
    return None


AUTO_PROTOCOL = ["nec"]


def find_address_auto(send, ask, say=print, commands=PROBE_COMMANDS, protocol="nec", exclude=(), first=(),
                      delay=0.7, pressed=key_pressed, sleep=None):
    """Watch-only search: commands go out by themselves; press any key when the device reacts,
    then confirm which of the last few it was."""
    AUTO_PROTOCOL[0] = protocol
    order = [a for g in address_groups(protocol=protocol, exclude=set(exclude), first=first) for a in g]
    items = [(a, c) for a in order for c in commands]
    say(f"Sending {len(items)} test commands by themselves. Watch the device and press any key as soon as it reacts.")
    start = 0
    while start < len(items):
        hit = auto_scan(items[start:], send, delay, say, pressed, sleep)
        if hit is None:
            return None
        hit += start
        candidates = list(dict.fromkeys(a for a, _ in reversed(items[max(0, hit - 3):hit + 1])))
        say("Stopped. Checking the last addresses one by one...")
        for a in candidates:
            for c in commands:
                send(code(a, c, protocol))
            if ask(f"  Address {a:#04x}: did it react now? [y/N]: ") in YES:
                say(f"\nAddress found: {a:#04x}")
                return a
        say("None of them - continuing.")
        start = hit + 1
    return None


def find_address_one_by_one(send, ask, say=print, commands=PROBE_COMMANDS, protocol="nec", exclude=(), first=(),
                            start_at=0, on_progress=None):
    """One address per question, like command mapping: Enter = nothing, y = it reacted, r = again, b = back, q = stop."""
    order = [a for g in address_groups(protocol=protocol, exclude=set(exclude), first=first) for a in g]
    say(f"{len(order)} addresses. For each: Enter = nothing happened, y = the device reacted, r = send again, "
        "b = back one, q = stop (progress is saved).")
    i = min(start_at, len(order))
    while i < len(order):
        a = order[i]
        for c in commands:
            send(code(a, c, protocol))
        answer = ask(f"[{i + 1}/{len(order)}] address {a:#04x} - did it react? ")
        if answer == "q":
            return None
        if answer == "r":
            continue
        if answer == "b":
            i = max(0, i - 1)
            continue
        if answer in YES:
            say(f"\nAddress found: {a:#04x}")
            return a
        i += 1
        if on_progress:
            on_progress(i)
    return None
