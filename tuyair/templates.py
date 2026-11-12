"""Remote layouts per device type.

A template is a grid of key ids (3 columns, None = empty cell). Keys are learned from
the device's own remote with  tuyair remote learn NAME ; the window then shows only
the keys that were learned, in this layout. Labels live in i18n.py ("keys").

To add a device type: add a layout here and labels for any new key ids in i18n.py.
"""

TEMPLATES = {
    "tv": [
        ["power", "input", "mute"],
        ["vol_up", "up", "ch_up"],
        ["left", "ok", "right"],
        ["vol_down", "down", "ch_down"],
        ["back", "home", "menu"],
        ["num_1", "num_2", "num_3"],
        ["num_4", "num_5", "num_6"],
        ["num_7", "num_8", "num_9"],
        [None, "num_0", None],
    ],
    "light": [
        ["power", "on", "off"],
        ["bright_up", "night", "bright_down"],
        ["warm", "white", "cool"],
        ["red", "green", "blue"],
        ["mode", "timer", None],
    ],
    "fan": [
        ["power", "speed", "swing"],
        ["speed_up", "mode", "speed_down"],
        ["timer", "light", None],
    ],
    "audio": [
        ["power", "input", "mute"],
        ["vol_up", "mode", "vol_down"],
        ["prev", "play_pause", "next"],
        ["bass_up", None, "bass_down"],
    ],
    "box": [
        ["power", "home", "back"],
        [None, "up", None],
        ["left", "ok", "right"],
        [None, "down", None],
        ["rewind", "play_pause", "forward"],
        ["vol_up", "mute", "vol_down"],
    ],
    "projector": [
        ["on", "off", "input"],
        ["menu", "up", "back"],
        ["left", "ok", "right"],
        [None, "down", None],
    ],
    "custom": [],
}


def keys_of(template):
    """Key ids of a template, in learning order."""
    return [k for row in TEMPLATES.get(template, []) for k in row if k]


def layout(template, learned):
    """Rows to show: the template's rows with only learned keys, then any extra learned keys."""
    rows, used = [], set()
    for row in TEMPLATES.get(template, []):
        shown = [k if k in learned else None for k in row]
        used.update(k for k in row if k)
        if any(shown):
            rows.append(shown)
    extra = [k for k in learned if k not in used]
    for i in range(0, len(extra), 3):
        rows.append((extra[i:i + 3] + [None, None])[:3])
    return rows
