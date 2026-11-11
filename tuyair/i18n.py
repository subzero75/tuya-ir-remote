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
    },
    "ar": {
        "title": "المكيف",
        "modes": {"auto": "تلقائي", "cool": "تبريد", "dry": "تجفيف", "fan": "مروحة", "heat": "تدفئة"},
        "fans": {"auto": "تلقائي", "high": "عالي", "med": "متوسط", "low": "منخفض", "quiet": "هادئ"},
        "mode": "الوضع", "fan": "المروحة", "power": "تشغيل / إيقاف", "off": "مطفأ",
        "commands": {"powerful": "قوي", "economy": "اقتصادي", "swing": "تأرجح", "swing_h": "تأرجح ↔",
                     "airflow": "اتجاه ↕", "airflow_h": "اتجاه ↔"},
        "swing_on": "تأرجح", "sending": "جارٍ الإرسال…", "sent": "تم الإرسال ✓", "error": "خطأ: ", "pin": "تثبيت",
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
    base = dict(TEXTS["en"])
    base.update(TEXTS[detect(setting)])
    return base
