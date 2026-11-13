"""Panel texts. To add a language, copy the "en" block, translate it, and send a pull request."""

TEXTS = {
    "en": {
        "title": "AC",
        "modes": {"auto": "AUTO", "cool": "COOL", "dry": "DRY", "fan": "FAN", "heat": "HEAT"},
        "fans": {"auto": "AUTO", "high": "HIGH", "med": "MED", "low": "LOW", "quiet": "QUIET"},
        "mode": "MODE", "fan": "FAN", "power": "START / STOP", "off": "OFF",
        "commands": {"powerful": "POWERFUL", "economy": "ECONOMY", "swing": "SWING", "swing_h": "SWING ↔",
                     "airflow": "SET ↕", "airflow_h": "SET ↔"},
        "swing_on": "SWING", "sending": "Sending…", "sent": "Sent ✓", "error": "Error: ", "pin": "Pin",
        "templates": {"tv": "TV", "light": "Light", "fan": "Fan", "audio": "Audio", "box": "TV box",
                      "projector": "Projector", "custom": "Custom"},
        "keys": {"power": "⏻", "on": "ON", "off": "OFF", "input": "INPUT", "mute": "MUTE",
                 "vol_up": "VOL +", "vol_down": "VOL −", "ch_up": "CH +", "ch_down": "CH −",
                 "up": "▲", "down": "▼", "left": "◀", "right": "▶", "ok": "OK",
                 "back": "BACK", "home": "HOME", "menu": "MENU",
                 "num_0": "0", "num_1": "1", "num_2": "2", "num_3": "3", "num_4": "4",
                 "num_5": "5", "num_6": "6", "num_7": "7", "num_8": "8", "num_9": "9",
                 "bright_up": "☀ +", "bright_down": "☀ −", "night": "NIGHT", "warm": "WARM",
                 "white": "WHITE", "cool": "COOL", "red": "RED", "green": "GREEN", "blue": "BLUE",
                 "mode": "MODE", "timer": "TIMER", "speed": "SPEED", "speed_up": "SPEED +",
                 "speed_down": "SPEED −", "swing": "SWING", "light": "LIGHT", "prev": "⏮",
                 "play_pause": "⏯", "next": "⏭", "bass_up": "BASS +", "bass_down": "BASS −",
                 "rewind": "⏪", "forward": "⏩", "picture_mode": "PICTURE MODE", "sound_mode": "SOUND MODE",
                 "sleep": "SLEEP", "exit": "EXIT", "enter": "ENTER", "tv_input": "TV", "vga": "VGA",
                 "hdmi": "HDMI", "info": "INFO", "aspect": "ASPECT"},
        "no_keys": "No buttons yet. Run:  tuyair remote learn {name}",
    },
    "ar": {
        "title": "المكيف",
        "modes": {"auto": "تلقائي", "cool": "تبريد", "dry": "تجفيف", "fan": "مروحة", "heat": "تدفئة"},
        "fans": {"auto": "تلقائي", "high": "عالي", "med": "متوسط", "low": "منخفض", "quiet": "هادئ"},
        "mode": "الوضع", "fan": "المروحة", "power": "تشغيل / إيقاف", "off": "مطفأ",
        "commands": {"powerful": "قوي", "economy": "اقتصادي", "swing": "تأرجح", "swing_h": "تأرجح ↔",
                     "airflow": "اتجاه ↕", "airflow_h": "اتجاه ↔"},
        "swing_on": "تأرجح", "sending": "جارٍ الإرسال…", "sent": "تم الإرسال ✓", "error": "خطأ: ", "pin": "تثبيت",
        "templates": {"tv": "تلفزيون", "light": "إضاءة", "fan": "مروحة", "audio": "صوتيات", "box": "جهاز استقبال",
                      "projector": "بروجكتر", "custom": "مخصص"},
        "keys": {"power": "⏻", "on": "تشغيل", "off": "إطفاء", "input": "المصدر", "mute": "كتم",
                 "vol_up": "صوت +", "vol_down": "صوت −", "ch_up": "قناة +", "ch_down": "قناة −",
                 "ok": "موافق", "back": "رجوع", "home": "الرئيسية", "menu": "القائمة",
                 "bright_up": "☀ +", "bright_down": "☀ −", "night": "ليلي", "warm": "دافئ",
                 "white": "أبيض", "cool": "بارد", "red": "أحمر", "green": "أخضر", "blue": "أزرق",
                 "mode": "الوضع", "timer": "مؤقت", "speed": "السرعة", "speed_up": "سرعة +",
                 "speed_down": "سرعة −", "swing": "تأرجح", "light": "الإضاءة",
                 "bass_up": "باس +", "bass_down": "باس −", "picture_mode": "وضع الصورة",
                 "sound_mode": "وضع الصوت", "sleep": "مؤقت النوم", "exit": "خروج", "enter": "دخول",
                 "tv_input": "تلفزيون", "info": "معلومات", "aspect": "أبعاد الصورة"},
        "no_keys": "ما فيه أزرار للحين. شغّل:  tuyair remote learn {name}",
    },
}


def detect(setting="auto"):
    lang = str(setting or "auto").lower()
    if lang in TEXTS:
        return lang
    code = ""
    try:
        import ctypes
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        import locale
        code = locale.windows_locale.get(lcid, "")
    except Exception:
        import locale
        import os
        code = (os.environ.get("LANG") or locale.getlocale()[0] or "")
    code = code.lower()[:2]
    return code if code in TEXTS else "en"


def texts(setting="auto"):
    """Texts for the language, falling back to English for anything not translated."""
    lang = TEXTS[detect(setting)]
    out = {}
    for k, v in TEXTS["en"].items():
        out[k] = {**v, **lang.get(k, {})} if isinstance(v, dict) else lang.get(k, v)
    return out
