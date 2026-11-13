# tuya-ir-remote (`tuyair`)

Control your air conditioner (or TV, fan, anything with an IR remote) through a **Tuya / Smart Life
Wi-Fi IR blaster**, **locally on your network** — no Alexa, no IFTTT, no delay.

- **Control window** with a tab per device: the AC tab mirrors the remote's screen (mode, temperature,
  fan, swing, powerful…), and TVs, lights, fans, receivers… get a layout for their type
- **PC hotkeys** (Windows / AutoHotkey) that work inside games, with any keyboard language
- **Command line** for scripts and automation: `tuyair ac on`, `tuyair ac temp +1`, `tuyair send tv_power`
- **Lost the remote?** `tuyair remote discover` finds the device's codes by itself (NEC: most TVs and monitors)
- **Learn** buttons from your remote — locally, or through the Tuya cloud for blasters that won't report locally
- **Any AC brand**: full control (on/off, mode, temperature, fan) of every air conditioner the
  Smart Life app supports, through the Tuya cloud — or **locally and instantly** for Fujitsu / General /
  O General, with **calibration** to your exact remote
- **Self-healing connection**: if the router gives the blaster a new IP, it finds it again and updates
  the config by itself; the window shows a green / red connection dot
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

Two ways, chosen in `tuyair setup` (or `"protocol"` under `"ac"` in `config.json`):

| Protocol | Brands | Needs | Speed |
|---|---|---|---|
| `fujitsu` | Fujitsu, General, O General | nothing extra (local) | instant |
| `tuya-cloud` | **any brand** the Smart Life app supports | internet + an AC remote added to your blaster in the app | ~1 s |

For `tuya-cloud`: in the Smart Life app open your IR blaster, add an *Air conditioner* remote, pick
your brand and confirm the test code works. Setup then lets you pick that remote.
Extra buttons the cloud doesn't cover (powerful, swing...) can be learned: `tuyair learn powerful`.

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

## TV, light, fan and other devices

Each device gets a **remote** with a layout for its type, and its own tab in the window.

```
tuyair remote templates                       # tv, light, fan, audio, box, projector, custom
tuyair remote add tv --template tv --title "Living room TV"
tuyair remote learn tv                        # walks through the keys: Enter = learn, s = skip, q = stop
tuyair remote learn tv --key netflix          # any extra button, with your own name
tuyair remote press tv vol_up vol_up          # send keys
tuyair remote list | forget tv KEY | remove tv
```
The window shows only the keys you learned, arranged like the device's remote.
Learning tries locally first; if your blaster only reports to the cloud it switches to cloud
learning and remembers that, so the next keys go straight there.

Single saved buttons still work too: `tuyair learn NAME`, `tuyair send NAME`, `tuyair list`.

### Lost the remote? Discover the codes

Most TVs, monitors and boxes use the **NEC** protocol; Daewoo and many white-label TVs use **Proton**.
`discover` finds your device's codes without the original remote:

```
tuyair remote discover tv
```
1. **Address**: it sends test commands to groups of addresses and asks whether the device reacted
   (a number, volume bar, menu, input list, switching off…). A group that reacts is halved until one
   address is left — usually a few minutes.
2. **Commands**: it sends each command of that address; you type what happened (`power`, `vol_up`,
   `menu`, `num_1`, `input`… or any name), or just Enter if nothing did. `r` = send again, `b` = back,
   `q` = stop. Progress is saved — run the same command to continue.

Every labelled command becomes a key of the remote (window tab, hotkeys, `remote press`).
Nothing reacts with NEC? Try `--protocol proton`. If a **Daewoo** remote in the Smart Life app makes
your device react but with the wrong functions, go straight to `--protocol proton --address 20`
(Daewoo's Proton device number) and only the commands need mapping.
**Easiest when the brand is unknown:** if *any* remote in the Smart Life app makes the device react,
even with the wrong functions, map it instead of guessing protocols:
```
tuyair remote cloud-map tv
```
It presses each key of that Smart Life remote through the cloud and you type what really happened
(`power`, `vol_up`…). Those keys then appear with the right names (needs internet and the
*IR Control Hub Open Service* authorization).

Already know a code? `tuyair remote add-code tv mute --nec 0x04 0x0D` (or `--proton 20 0x0D`, or `--code BASE64_OR_HEX`).

## Hotkeys (Windows)

Edit the `"hotkeys"` section of `config.json` (see [examples/config.example.json](examples/config.example.json)), then:
```
tuyair hotkeys --startup           # writes tuyair.ahk to the Startup folder (runs at every login)
tuyair hotkeys                     # or next to config.json, double-click to start
```
Default keys: **Ctrl+Alt+A** window · **I** on · **O** off · **P** powerful · **S** swing ·
**D / H** louvers · **Ctrl+Alt+↑/↓** temperature. Actions: `@panel`, `ac ...`, `remote tv vol_up`,
or saved button names.
Keys are written as virtual-key codes, so they work with Arabic, English or any other layout.
If a hotkey does nothing, another program may own it (screenshot tools often take Ctrl+Alt+A) — pick another.
If hotkeys don't work inside a game, run the `.ahk` as administrator.

On Linux/macOS, bind the same commands (`tuyair ac on`, `tuyair panel`...) in your desktop's keyboard settings.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Commands say *Sent* but nothing happens, LED doesn't blink | The blaster wants the other command format: `tuyair fix --control-type 1` (or `2`). This was the fix on a v3.5 "Smart IR" blaster. |
| `json obj data unvalid` | Normal for IR blasters: the device answered with your key, it just has no status. |
| Setup can't find the blaster | Make sure it's powered and on the same network; allow Python in the firewall (UDP 6666/6667/7000); or enter the IP from your router. |
| Worked before, now fails | A new IP is found automatically. If the blaster was re-paired in the app it has a new key → run `tuyair setup` again. |
| `learn` gets nothing | Some blasters only report learned codes to the cloud: authorize *IR Control Hub Open Service* and it falls back automatically. Try `"control_type": 1` for older blasters. |
| `This API is not subscribed` | Authorize *IR Control Hub Open Service* in the cloud project. |
| AC turns off but not on | `tuyair ac calibrate` |
| Window doesn't open from a hotkey | It may already be open: the same hotkey opens and closes it. Errors go to `tuyair.log` next to `config.json`. |

## Adding a device type or an AC brand

Device layouts are in [`tuyair/templates.py`](tuyair/templates.py) (a 3-column grid of key ids) and
their labels in [`tuyair/i18n.py`](tuyair/i18n.py) — adding a type or a language is a few lines.


Protocols live in [`tuyair/protocols/`](tuyair/protocols). Implement `full_state`, `off`, `short`
(and ideally `decode` / `calibrate`) and register it in `get_protocol`. Pull requests welcome —
include a captured code (`tuyair decode`) so it can be tested.

## Credits

- **[subzero75](https://github.com/subzero75)** — idea, real-device testing, maintainer
- **Claude (Anthropic)** — co-developer: wrote the code, protocols, tests and documentation
- Built on [tinytuya](https://github.com/jasonacox/tinytuya) for local Tuya communication.
  Fujitsu protocol details follow the public work of the
  [IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266) community.

## License

MIT

---

## بالعربي

برنامج يتحكم بالمكيف، أو أي جهاز فيه ريموت (تلفزيون، مروحة، رسيفر...)، عن طريق جهاز **IR من Tuya أو Smart Life**. التحكم يصير **محلياً على شبكة البيت**، بدون Alexa ولا IFTTT ولا تأخير.

- **نافذة تحكم صغيرة:** شكلها مثل شاشة الريموت، وفيها الوضع والحرارة والمروحة والتأرجح والقوي.
- **اختصارات كيبورد على ويندوز:** تشتغل داخل الألعاب، ومع أي لغة كيبورد.
- **أوامر سطر الأوامر:** مثل `tuyair ac on` و`tuyair ac temp +1`.
- **نافذة لكل جهاز:** تلفزيون أو إضاءة أو مروحة أو غيرها، بترتيب أزرار يناسب نوع الجهاز.
- **اكتشاف أكواد جهاز ضاع ريموته:** يشتغل مع أغلب الشاشات والتلفزيونات، خصوصاً الماركات الصينية.
- **تعلّم الأزرار:** محلياً، أو عن طريق السحابة إذا كان جهازك ما يرسل الأكواد اللي يتعلّمها محلياً.
- **التحكم الكامل بأي مكيف يدعمه Smart Life:** التشغيل والحرارة والوضع والمروحة، عن طريق السحابة.
- **التحكم المحلي الفوري لمكيفات Fujitsu وGeneral وO General:** مع **معايرة** على ريموتك إذا ما اشتغلت الأكواد العامة.
- **اتصال يصلّح نفسه:** إذا تغيّر عنوان الـ IP حق جهاز الـ IR، البرنامج يلقاه ويحدّث الإعدادات بنفسه. والنافذة فيها نقطة خضراء أو حمراء توضح حالة الاتصال.

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
- **ضيّعت الريموت؟** أمر `tuyair remote discover tv` يكتشف أكواد الجهاز بنفسه: يدوّر على العنوان، وبعدها يرسل الأوامر وحدة وحدة، وإنت تكتب له وش صار مع كل أمر. ويقدر يكمل من وين وقفت.
- **أسهل طريقة إذا ماركة جهازك مو معروفة:** إذا فيه أي ريموت في Smart Life يخلي جهازك يستجيب، حتى لو بوظائف غلط، استخدم `tuyair remote cloud-map tv`. البرنامج يضغط أزرار هالريموت وحدة وحدة، وإنت تكتب وش صار فعلاً، فتصير عندك الأزرار بأسمائها الصحيحة.
- **إذا ما استجاب الجهاز للاكتشاف:** جرّب `--protocol proton`. وإذا كان ريموت Daewoo في Smart Life يخلي جهازك يستجيب، استخدم `--protocol proton --address 20` على طول.
- **إضافة تلفزيون:** `tuyair remote add tv --template tv`، وبعدها `tuyair remote learn tv` يمشي معك على الأزرار واحد واحد.
- **أنواع الأجهزة المتاحة:** تلفزيون، إضاءة، مروحة، صوتيات، جهاز استقبال، بروجكتر، أو مخصص. وكل جهاز له تبويب في النافذة.

### مشاكل شائعة

- **المكيف ينطفي بس ما يشتغل:** شغّل `tuyair ac calibrate`، وهو يلتقط إشارة التشغيل الحقيقية من ريموتك.
- **رسالة json obj data unvalid:** طبيعية، ومعناها إن الجهاز رد بالمفتاح الصحيح.
- **مكيف من ماركة ثانية:** في Smart Life أضف ريموت مكيف لجهاز الـ IR واختر ماركتك، وبعدها اختر `tuya-cloud` في `tuyair setup`.
- **الأوامر تنرسل بس ما يصير شي، واللمبة ما تومض:** جهاز الـ IR يبي صيغة أوامر ثانية، فاكتب `tuyair fix --control-type 1` (أو `2`).
- **كان شغال ووقف:** تغيّر الـ IP يتحل تلقائياً. أما إذا أعدت ربط الجهاز في التطبيق، فأعد `tuyair setup`.
- **ملف الإعدادات:** `config.json` فيه مفاتيح سرية. خذ منه نسخة احتياطية، ولا تشاركه مع أحد.

### المطورون

- **صاحب الفكرة والمشرف على المشروع:** [subzero75](https://github.com/subzero75)، وهو اللي اختبره على أجهزة حقيقية.
- **مطوّر مشارك:** Claude من Anthropic، كتب الكود والبروتوكولات والاختبارات والتوثيق.
