# tuya-ir-remote (`tuyair`)

Control your air conditioner (or TV, fan, anything with an IR remote) through a **Tuya / Smart Life
Wi-Fi IR blaster**, **locally on your network** — no Alexa, no IFTTT, no delay.

- **Control window** that looks like the remote's screen (mode, temperature, fan, swing, powerful…)
- **PC hotkeys** (Windows / AutoHotkey) that work inside games, with any keyboard language
- **Command line** for scripts and automation: `tuyair ac on`, `tuyair ac temp +1`, `tuyair send tv_power`
- **Learn** buttons from your remote — locally, or through the Tuya cloud for blasters that won't report locally
- **Generate** AC codes without learning (Fujitsu / General / O General built in), and **calibrate**
  them to your exact remote if the generic timings don't work
- English and Arabic interface (auto-detected); more languages welcome

> 🇸🇦 [الشرح بالعربي في الأسفل](#بالعربي)

---

## Install

1. Python 3.8+ (Windows: python.org, tick **Add to PATH**)
2. Install:
   ```
   pip install git+https://github.com/subzero75/tuya-ir-remote
   ```
   or download the ZIP, open a terminal in the folder and run `pip install .`
   (or use it without installing: `python -m tuyair ...` from the folder).
3. Windows hotkeys only: [AutoHotkey v2](https://www.autohotkey.com/).

## Setup (once)

You need a free Tuya developer project, only to read your blaster's **local key**:

1. On <https://iot.tuya.com>: **Cloud → Development → Create Cloud Project**
   (Industry: Smart Home, pick the data center of your app account).
2. In the project: **Devices → Link App Account → Add App Account**, and scan the QR code
   in the Smart Life / Tuya app (*Me → scan icon*).
3. **Service API → Go to Authorize** and add **IR Control Hub Open Service**
   (needed only for cloud learning / calibration).
4. Run the wizard and paste the project's *Access ID* and *Access Secret*:
   ```
   tuyair setup
   ```
   It lists your devices, finds the blaster on your network, saves `config.json` and tests the connection.

Your settings (keys, buttons, calibration) are in `config.json` — `tuyair setup` prints where.
**Back it up** and **never share it**: it contains your device key and cloud secret.

## Air conditioner

```
tuyair ac on                       # turn on with the last settings
tuyair ac on --mode cool --temp 24 --fan high
tuyair ac off
tuyair ac temp +1 | -1 | 22
tuyair ac mode next | cool | dry | fan | heat | auto
tuyair ac fan next | auto | high | med | low | quiet
tuyair ac cmd powerful | swing | airflow | airflow_h | economy | swing_h
tuyair ac status
tuyair panel                       # control window (run again to close it)
```

**`off` works but `on` doesn't?** Your remote uses slightly different timings. Capture it once:
```
tuyair ac calibrate                # set the remote to OFF, press START when asked
```
It measures the timings of your real power-on signal and uses them for every code it generates
(this is what fixed an O General ASSA24FRTA with an AR-RAJ1E-style remote).
If it still fails, `tuyair ac probe` tries the known model variants one by one.

IR is one-way: the window shows what was **last sent**. If you use the original remote,
press START/STOP once in the window to resync.

## Any other device (TV, fan, receiver…)

```
tuyair learn tv_power              # press the button on your remote when asked
tuyair send tv_power
tuyair send tv_power hdmi2         # several, in order
tuyair list | tuyair delete NAME | tuyair decode NAME
```
`learn` tries local learning first and falls back to cloud learning automatically.
Add saved buttons to the window with `"panel_buttons": ["tv_power", ...]` in `config.json`.

## Hotkeys (Windows)

Edit the `"hotkeys"` section of `config.json` (see [examples/config.example.json](examples/config.example.json)), then:
```
tuyair hotkeys --startup           # writes tuyair.ahk to the Startup folder (runs at every login)
tuyair hotkeys                     # or next to config.json, double-click to start
```
Default keys: **Ctrl+Alt+A** window · **I** on · **O** off · **P** powerful · **S** swing ·
**D / H** louvers · **Ctrl+Alt+↑/↓** temperature. Actions: `@panel`, `ac ...`, or saved button names.
Keys are written as virtual-key codes, so they work with Arabic, English or any other layout.
If a hotkey does nothing, another program may own it (screenshot tools often take Ctrl+Alt+A) — pick another.
If hotkeys don't work inside a game, run the `.ahk` as administrator.

On Linux/macOS, bind the same commands (`tuyair ac on`, `tuyair panel`...) in your desktop's keyboard settings.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `json obj data unvalid` | Normal for IR blasters: the device answered with your key, it just has no status. |
| Setup can't find the blaster | Make sure it's powered and on the same network; allow Python in the firewall (UDP 6666/6667/7000); or enter the IP from your router. |
| Worked before, now fails | The IP changed (reserve it in your router) or the blaster was re-paired (new key → run `tuyair setup` again). |
| `learn` gets nothing | Some blasters only report learned codes to the cloud: authorize *IR Control Hub Open Service* and it falls back automatically. Try `"control_type": 1` for older blasters. |
| `This API is not subscribed` | Authorize *IR Control Hub Open Service* in the cloud project. |
| AC turns off but not on | `tuyair ac calibrate` |
| Window doesn't open from a hotkey | It may already be open: the same hotkey opens and closes it. Errors go to `tuyair.log` next to `config.json`. |

## Adding an AC brand

Protocols live in [`tuyair/protocols/`](tuyair/protocols). Implement `full_state`, `off`, `short`
(and ideally `decode` / `calibrate`) and register it in `get_protocol`. Pull requests welcome —
include a captured code (`tuyair decode`) so it can be tested.

## License

MIT

---

## بالعربي

برنامج يتحكم بالمكيف، أو أي جهاز فيه ريموت (تلفزيون، مروحة، رسيفر...)، عن طريق جهاز **IR من Tuya أو Smart Life**. التحكم يصير **محلياً على شبكة البيت**، بدون Alexa ولا IFTTT ولا تأخير.

- **نافذة تحكم صغيرة:** شكلها مثل شاشة الريموت، وفيها الوضع والحرارة والمروحة والتأرجح والقوي.
- **اختصارات كيبورد على ويندوز:** تشتغل داخل الألعاب، ومع أي لغة كيبورد.
- **أوامر سطر الأوامر:** مثل `tuyair ac on` و`tuyair ac temp +1`.
- **تعلّم الأزرار:** محلياً، أو عن طريق السحابة إذا كان جهازك ما يرسل الأكواد اللي يتعلّمها محلياً.
- **توليد أكواد المكيف بدون تعلّم:** مدعوم حالياً Fujitsu وGeneral وO General، مع **معايرة** على ريموتك إذا ما اشتغلت الأكواد العامة.

### التثبيت والإعداد

- **ثبّت بايثون:** وفعّل خيار Add to PATH أثناء التثبيت.
- **ثبّت البرنامج:**
  ```
  pip install git+https://github.com/subzero75/tuya-ir-remote
  ```
- **ثبّت AutoHotkey v2:** إذا تبي الاختصارات على ويندوز.
- **سوّ مشروع في iot.tuya.com:** ادخل Cloud ← Development ← Create Cloud Project.
- **اربط حسابك:** ادخل Devices ← Link App Account، وامسح الكود من تطبيق Smart Life.
- **فعّل خدمة الـ IR:** ادخل Service API ← Go to Authorize، وأضف **IR Control Hub Open Service**.
- **شغّل المعالج:** اكتب `tuyair setup`، والصق Access ID وAccess Secret.

### الاستخدام

- **تشغيل المكيف وإطفاؤه:** `tuyair ac on` و`tuyair ac off`
- **تغيير الحرارة:** `tuyair ac temp +1`
- **فتح النافذة:** `tuyair panel` (نفس الأمر يسكّرها)
- **الاختصارات:** `tuyair hotkeys --startup` (تشتغل تلقائياً مع ويندوز)
- **أجهزة ثانية:** `tuyair learn tv_power`، وبعدها `tuyair send tv_power`

### مشاكل شائعة

- **المكيف ينطفي بس ما يشتغل:** شغّل `tuyair ac calibrate`، وهو يلتقط إشارة التشغيل الحقيقية من ريموتك.
- **رسالة json obj data unvalid:** طبيعية، ومعناها إن الجهاز رد بالمفتاح الصحيح.
- **كان شغال ووقف:** غالباً تغيّر عنوان الـ IP، فثبّته من الراوتر. أو أعدت ربط الجهاز، فأعد `tuyair setup`.
- **ملف الإعدادات:** `config.json` فيه مفاتيح سرية. خذ منه نسخة احتياطية، ولا تشاركه مع أحد.
