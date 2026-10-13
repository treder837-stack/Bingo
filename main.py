# ============================================================
# ⚔️ BINGO — SOLO SYSTEM v15.1 KEYBOARD SUGGESTIONS FIX
# Kivy + Gemini + Android notifications + background daily alarm
# Designed for Pydroid 3 on Android; compact history + low thinking for faster replies
# ============================================================

import json
import os
import re
import threading
import urllib.request
import urllib.error
import ssl
try:
    import certifi
except ImportError:
    certifi = None
from datetime import datetime, timedelta

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup

# Keep the focused message input visible when Android opens the keyboard.
Window.softinput_mode = "below_target"

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

API_KEY = ""  # Keep empty; enter the key inside Bingo instead of committing it to GitHub.
ASSISTANT_NAME = "Bingo"
PLAYER_NAME = "Abdul"
MODEL = "gemini-3.8-flash"
FALLBACK_MODELS = ["gemini-3.6-flash", "gemini-2.5-flash"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "bingo_memory.json")
PROFILE_FILE = os.path.join(BASE_DIR, "profile.json")
SYSTEM_FILE = os.path.join(BASE_DIR, "system.json")

CHANNEL_ID = "bingo_daily"
CHANNEL_NAME = "Bingo Daily"
CHANNEL_DESCRIPTION = "Bingo schedule and quest reminders"

ANDROID_AVAILABLE = False
notification_manager = None
android_context = None
APP_INSTANCE = None

DAILY_QUEST_HOUR = 23
DAILY_QUEST_MINUTE = 0
daily_quest_notification_sent = False

BACKGROUND_ALARM_REQUEST_CODE = 1300
BACKGROUND_ALARM_ACTION = "com.bingo.DAILY_QUEST_ALARM"
NOTIFICATION_ACTION_PREFIX = "com.bingo.ACTION."
NOTIFICATION_OPEN_ACTION = NOTIFICATION_ACTION_PREFIX + "OPEN"
NOTIFICATION_LEARNING_ACTION = NOTIFICATION_ACTION_PREFIX + "LEARNING"
NOTIFICATION_TRAINING_ACTION = NOTIFICATION_ACTION_PREFIX + "TRAINING"

# ------------------------------------------------------------
# DEFAULT DATA
# ------------------------------------------------------------

default_system = {
    "level": 1,
    "exp": 0,
    "exp_required": 100,
    "streak": 0,
    "quests_completed": 0,
    "learning_completed": False,
    "training_completed": False,
    "last_active_date": "",
    "today": "",
    "daily_reminders": [],
    "notification_enabled": True,
    "notification_tested": False,
    "day_started": "",
}

default_profile = {
    "name": PLAYER_NAME,
    "assistant": ASSISTANT_NAME,
    "learning": {
        "Monday": "Medicines",
        "Tuesday": "BMG & VIFTG",
        "Wednesday": "Gunsmithing & Blacksmithing",
        "Thursday": "Programming & Mechanical Engineering",
        "Friday": "AI + Robots & Cognitive Robots",
        "Saturday": "Hacking",
        "Sunday": "Mathematics",
    },
    "training": {
        "Monday": "Boxing",
        "Tuesday": "Muay Thai",
        "Wednesday": "Jujutsu",
        "Thursday": "Jeet Kune Do",
        "Friday": "Taekwondo",
        "Saturday": "Kenjutsu + Gun Shooting",
        "Sunday": "Wrestling",
    },
}

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            value = json.load(f)
        return value
    except Exception:
        return default.copy() if isinstance(default, dict) else default

def save_json(path, value):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def api_key_file_path():
    """Store the key in this app's private Android data directory."""
    try:
        app = App.get_running_app()
        if app is not None:
            return os.path.join(app.user_data_dir, "bingo_api_config.json")
    except Exception:
        pass
    # Development fallback only; the installed APK uses user_data_dir.
    return os.path.join(BASE_DIR, "bingo_api_config.json")

def get_api_key():
    """Read the user's key from private app storage; never from source control."""
    if API_KEY.strip():
        return API_KEY.strip()
    saved = load_json(api_key_file_path(), {})
    if isinstance(saved, dict):
        return str(saved.get("gemini_api_key", "")).strip()
    return ""

def store_api_key(value):
    value = (value or "").strip()
    if not value:
        return False
    path = api_key_file_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"gemini_api_key": value}, f)
        return True
    except Exception:
        return False

system = default_system.copy()
loaded_system = load_json(SYSTEM_FILE, {})
if isinstance(loaded_system, dict):
    system.update(loaded_system)

profile = default_profile.copy()
loaded_profile = load_json(PROFILE_FILE, {})
if isinstance(loaded_profile, dict):
    profile.update(loaded_profile)

memory = load_json(MEMORY_FILE, [])
if not isinstance(memory, list):
    memory = []

for key, value in (
    ("level", 1), ("exp", 0), ("exp_required", 100),
    ("streak", 0), ("quests_completed", 0)
):
    if not isinstance(system.get(key), int):
        system[key] = value

for key in ("learning_completed", "training_completed", "notification_enabled"):
    if not isinstance(system.get(key), bool):
        system[key] = False if key != "notification_enabled" else True

# ------------------------------------------------------------
# DATE / SCHEDULE
# ------------------------------------------------------------

def now():
    return datetime.now()

def today_date():
    return now().strftime("%Y-%m-%d")

def day_name():
    return now().strftime("%A")

def learning_today():
    return profile.get("learning", default_profile["learning"]).get(
        day_name(), "No learning quest"
    )

def training_today():
    return profile.get("training", default_profile["training"]).get(
        day_name(), "No training quest"
    )

def daily_reset():
    today = today_date()
    if system.get("today") != today:
        system["learning_completed"] = False
        system["training_completed"] = False
        system["today"] = today
        system["day_started"] = now().strftime("%H:%M:%S")
        save_json(SYSTEM_FILE, system)

# ------------------------------------------------------------
# SCHEDULE
# ------------------------------------------------------------

def schedule_items():
    lunch = "2:45 PM" if day_name() == "Friday" else "4:00 PM"
    return [
        ("08:45", "Wake Up"),
        ("09:30", "Breakfast"),
        ("10:00", "Work"),
        (datetime.strptime(lunch, "%I:%M %p").strftime("%H:%M"), "Lunch"),
        ("17:00", "Back to Work"),
        ("22:00", "Home"),
        ("22:30", "Namaz"),
        ("22:35", "Dinner"),
        ("23:00", "Learning + Training"),
    ]

def schedule_text():
    lines = ["📅 TODAY'S SCHEDULE", ""]
    for t, label in schedule_items():
        display = datetime.strptime(t, "%H:%M").strftime("%I:%M %p")
        lines.append(f"• {display} — {label}")
    lines.append("")
    lines.append(f"📚 Learning: {learning_today()}")
    lines.append(f"🥋 Training: {training_today()}")
    return "\n".join(lines)

def next_event():
    current = now()
    candidates = []
    for t, label in schedule_items():
        h, m = map(int, t.split(":"))
        dt = current.replace(hour=h, minute=m, second=0, microsecond=0)
        if dt <= current:
            dt += timedelta(days=1)
        candidates.append((dt, label))
    return min(candidates, key=lambda x: x[0] - current)

# ------------------------------------------------------------
# PROGRESS
# ------------------------------------------------------------

def add_exp(amount):
    system["exp"] += int(amount)
    leveled = False
    level_ups = 0
    while system["exp"] >= system["exp_required"]:
        system["exp"] -= system["exp_required"]
        system["level"] += 1
        system["exp_required"] = max(1, int(system["exp_required"] * 1.5))
        leveled = True
        level_ups += 1
    save_json(SYSTEM_FILE, system)
    return leveled, level_ups

def update_streak():
    today = today_date()
    if system.get("last_active_date") == today:
        return
    yesterday = (now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if system.get("last_active_date") == yesterday:
        system["streak"] += 1
    else:
        system["streak"] = 1
    system["last_active_date"] = today

def complete_learning():
    if system["learning_completed"]:
        return "📚 Learning quest is already complete today."
    subject = learning_today()
    system["learning_completed"] = True
    system["quests_completed"] += 1
    update_streak()
    leveled, _ = add_exp(50)
    save_json(SYSTEM_FILE, system)
    send_android_notification("⚔️ QUEST COMPLETE", f"📚 {subject} | +50 EXP | 🔥 Streak {system['streak']}")
    if leveled:
        send_android_notification("⚡ LEVEL UP!", f"Abdul reached Level {system['level']}!")
    result = (f"📚 LEARNING QUEST COMPLETE!\n\n📖 Subject: {subject}\n⭐ +50 EXP\n🔥 Streak: {system['streak']} days\n⚡ Level: {system['level']}\n📊 EXP: {system['exp']} / {system['exp_required']}")
    if leveled:
        result += f"\n\n⚡ LEVEL UP!\n🎉 You reached Level {system['level']}!"
    return result

def complete_training():
    if system["training_completed"]:
        return "🥋 Training quest is already complete today."
    subject = training_today()
    system["training_completed"] = True
    system["quests_completed"] += 1
    update_streak()
    leveled, _ = add_exp(50)
    save_json(SYSTEM_FILE, system)
    send_android_notification("⚔️ QUEST COMPLETE", f"🥋 {subject} | +50 EXP | 🔥 Streak {system['streak']}")
    if leveled:
        send_android_notification("⚡ LEVEL UP!", f"Abdul reached Level {system['level']}!")
    result = (f"🥋 TRAINING QUEST COMPLETE!\n\n🥋 Training: {subject}\n⭐ +50 EXP\n🔥 Streak: {system['streak']} days\n⚡ Level: {system['level']}\n📊 EXP: {system['exp']} / {system['exp_required']}")
    if leveled:
        result += f"\n\n⚡ LEVEL UP!\n🎉 You reached Level {system['level']}!"
    return result

# ------------------------------------------------------------
# DAILY QUEST NOTIFICATION
# ------------------------------------------------------------
def check_daily_quest_notification():
    global daily_quest_notification_sent
    current = now()
    today = today_date()
    if system.get("today") != today:
        daily_quest_notification_sent = False

    if current.hour < DAILY_QUEST_HOUR:
        return
    if current.hour == DAILY_QUEST_HOUR and current.minute < DAILY_QUEST_MINUTE:
        return
    if daily_quest_notification_sent:
        return
    if system.get("learning_completed") and system.get("training_completed"):
        daily_quest_notification_sent = True
        return
    learning = learning_today(); training = training_today()
    if system.get("learning_completed"):
        message = f"🥋 Training remaining: {training}"
    elif system.get("training_completed"):
        message = f"📚 Learning remaining: {learning}"
    else:
        message = f"📚 {learning} + 🥋 {training}"
    ok, _ = send_android_notification("⚔️ DAILY QUESTS READY", message, with_actions=True)
    if ok:
        daily_quest_notification_sent = True
        reminders = system.get("daily_reminders", [])
        if not isinstance(reminders, list): reminders = []
        reminders.append({"date": today, "time": current.strftime("%H:%M:%S"), "learning": learning, "training": training})
        system["daily_reminders"] = reminders[-30:]
        save_json(SYSTEM_FILE, system)

def test_daily_quest_notification():
    return send_android_notification("⚔️ DAILY QUESTS READY", f"📚 {learning_today()} + 🥋 {training_today()}", with_actions=True)

def status_text():
    lm = "✅" if system["learning_completed"] else "⬜"
    tm = "✅" if system["training_completed"] else "⬜"
    return (
        "⚔️ BINGO SYSTEM\n\n"
        f"👤 PLAYER: {PLAYER_NAME}\n"
        f"⚡ LEVEL: {system['level']}\n"
        f"⭐ EXP: {system['exp']} / {system['exp_required']}\n"
        f"🔥 STREAK: {system['streak']} days\n"
        f"🎯 QUESTS: {system['quests_completed']}\n\n"
        f"{lm} Learning: {learning_today()}\n"
        f"{tm} Training: {training_today()}"
    )

def quests_text():
    return (
        "🎯 TODAY'S QUESTS\n\n"
        f"{'✅' if system['learning_completed'] else '⬜'} Learning — {learning_today()}\n"
        f"{'✅' if system['training_completed'] else '⬜'} Training — {training_today()}"
    )

# ------------------------------------------------------------
# GEMINI
# ------------------------------------------------------------

def system_instruction():
    return f"""You are Bingo, Abdul's personal AI assistant.
Be intelligent, calm, friendly, motivating, honest, practical and patient.
Explain difficult subjects step by step. Do not pretend to know things you do not know.
Use a Solo-Leveling-inspired progress style, but you are Bingo, not an anime character.

PLAYER: {PLAYER_NAME}
TODAY: {day_name()}
LEARNING: {learning_today()}
TRAINING: {training_today()}
LEVEL: {system['level']}
EXP: {system['exp']} / {system['exp_required']}
STREAK: {system['streak']}
QUESTS COMPLETED: {system['quests_completed']}

Safety:
- Medicine: educational information only; do not diagnose.
- Cybersecurity: defensive and authorized learning only; no credential theft, malware, destructive activity, or security bypass.
- Weapons: safe high-level history, physics, engineering, safety and legal context only; no construction, modification or harmful-use instructions.
- Martial arts: fitness, concepts, discipline and safety.
"""

def ask_gemini(message):
    api_key = get_api_key()
    if not api_key:
        return "🔑 Gemini API key is not set yet. Tap API KEY, enter your key, and save it."

    # Use Google's HTTPS REST API directly; no google-genai package is required.
    # Send only the latest 8 messages (about 4 exchanges) to reduce prompt size.
    # The full local memory is still saved below; only the API context is shortened.
    history = []
    for item in memory[-8:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role", "user")
        parts = item.get("parts", [])
        if role not in ("user", "model") or not isinstance(parts, list):
            continue
        valid_parts = []
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                # Avoid sending huge old messages repeatedly.
                valid_parts.append({"text": part["text"][-2400:]})
        if valid_parts:
            history.append({"role": role, "parts": valid_parts})
    history.append({"role": "user", "parts": [{"text": message}]})

    last_error = None
    for model_name in [MODEL] + [m for m in FALLBACK_MODELS if m != MODEL]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_instruction()}]},
            "contents": history,
            # Low thinking reduces latency for everyday chat while retaining reasoning.
            "generationConfig": {"maxOutputTokens": 1536},
        }
        if model_name.startswith("gemini-3."):
            payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": "low"}
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=35,
                context=ssl.create_default_context(cafile=certifi.where()) if certifi else ssl.create_default_context(),
            ) as response:
                result = json.loads(response.read().decode("utf-8"))
            candidates = result.get("candidates", [])
            answer = "".join(
                part.get("text", "")
                for part in (candidates[0].get("content", {}).get("parts", []) if candidates else [])
                if isinstance(part, dict)
            ).strip()
            if not answer:
                feedback = result.get("promptFeedback", {})
                return "❌ Gemini returned no text. " + str(feedback or result.get("candidates", ""))[:500]
            memory.append({"role": "user", "parts": [{"text": message}]})
            memory.append({"role": "model", "parts": [{"text": answer}]})
            del memory[:-40]
            save_json(MEMORY_FILE, memory)
            return answer
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = str(exc)
            last_error = f"HTTP {exc.code}: {detail[:700]}"
            # Try the fallback model for model-specific errors; key/quota errors won't improve.
            if exc.code in (400, 401, 403, 429):
                break
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
    return f"❌ Gemini error: {last_error or 'Unknown connection error'}"

# ------------------------------------------------------------
# ANDROID NOTIFICATIONS
# ------------------------------------------------------------

def test_jni():
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        return True, f"✅ JNI TEST SUCCESS!\n\nAndroid Activity detected.\n\n{activity}"
    except Exception as exc:
        return False, f"❌ JNI TEST FAILED!\n\n{repr(exc)}"

def setup_android_notifications():
    global ANDROID_AVAILABLE, notification_manager, android_context
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        android_context = PythonActivity.mActivity
        Context = autoclass("android.content.Context")
        NotificationManager = autoclass("android.app.NotificationManager")
        notification_manager = android_context.getSystemService(Context.NOTIFICATION_SERVICE)
        if notification_manager is None:
            ANDROID_AVAILABLE = False
            return False, "❌ NotificationManager is NULL."

        # Deliberately avoid Build.VERSION: PyJNIus on this Pydroid setup
        # does not expose the nested VERSION class reliably.
        NotificationChannel = autoclass("android.app.NotificationChannel")
        channel = NotificationChannel(
            CHANNEL_ID,
            CHANNEL_NAME,
            NotificationManager.IMPORTANCE_DEFAULT,
        )
        channel.setDescription(CHANNEL_DESCRIPTION)
        notification_manager.createNotificationChannel(channel)

        ANDROID_AVAILABLE = True
        return True, "✅ Android notification system ONLINE."
    except Exception as exc:
        ANDROID_AVAILABLE = False
        return False, "❌ Android notification setup failed:\n\n" + repr(exc)

def request_notification_permission():
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        permission = "android.permission.POST_NOTIFICATIONS"
        activity.requestPermissions([permission], 9001)
        return True, "✅ Notification permission requested."
    except Exception as exc:
        return False, "❌ Permission request failed:\n\n" + repr(exc)

def _make_activity_pending_intent(action, request_code):
    """Create a PendingIntent using Pydroid's actual package launch intent."""
    from jnius import autoclass

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    PendingIntent = autoclass("android.app.PendingIntent")
    activity = PythonActivity.mActivity

    # Using the package launch intent is more reliable on Android launchers
    # than constructing a new PythonActivity intent directly.
    package_manager = activity.getPackageManager()
    package_name = activity.getPackageName()
    intent = package_manager.getLaunchIntentForPackage(package_name)
    if intent is None:
        raise RuntimeError("Android could not find Bingo/Pydroid launch intent")

    intent.setAction(str(action))
    intent.putExtra("bingo_notification_action", str(action))

    # Clear/recreate the task so the action is present on startup. Keep each
    # action's PendingIntent distinct by request code and action string.
    FLAG_ACTIVITY_NEW_TASK = 0x10000000
    FLAG_ACTIVITY_CLEAR_TASK = 0x00008000
    intent.addFlags(FLAG_ACTIVITY_NEW_TASK | FLAG_ACTIVITY_CLEAR_TASK)

    FLAG_UPDATE_CURRENT = 0x08000000
    FLAG_IMMUTABLE = 0x04000000
    return PendingIntent.getActivity(
        activity,
        int(request_code),
        intent,
        FLAG_UPDATE_CURRENT | FLAG_IMMUTABLE,
    )


def send_android_notification(title, text, with_actions=False):
    """Post a notification and, optionally, quest action buttons."""
    if not ANDROID_AVAILABLE or notification_manager is None or android_context is None:
        return False, "❌ Android notifications are offline. Tap TEST first and read the setup result."
    try:
        from jnius import autoclass
        Builder = autoclass("android.app.Notification$Builder")
        Intent = autoclass("android.content.Intent")
        PendingIntent = autoclass("android.app.PendingIntent")

        icon_id = android_context.getResources().getIdentifier(
            "ic_dialog_info", "drawable", "android"
        )
        if not icon_id:
            icon_id = android_context.getApplicationInfo().icon
        if not icon_id:
            return False, "❌ No usable small icon was found for the notification."

        # Use the channel constructor (Android 8+) as this app creates a channel at startup.
        builder = Builder(android_context, CHANNEL_ID)
        builder.setContentTitle(str(title))
        builder.setContentText(str(text))
        builder.setSmallIcon(int(icon_id))
        builder.setAutoCancel(True)
        builder.setPriority(0)
        builder.setDefaults( -1 )

        open_pi = _make_activity_pending_intent(NOTIFICATION_OPEN_ACTION, 1401)
        builder.setContentIntent(open_pi)

        if with_actions:
            learning_pi = _make_activity_pending_intent(NOTIFICATION_LEARNING_ACTION, 1402)
            training_pi = _make_activity_pending_intent(NOTIFICATION_TRAINING_ACTION, 1403)
            # PyJNIus does not reliably convert a Python str to Java CharSequence
            # for Notification.Builder.addAction(int, CharSequence, PendingIntent).
            # Explicitly create java.lang.String objects so the overload matches.
            JavaString = autoclass("java.lang.String")
            learning_title = JavaString("Complete Learning")
            training_title = JavaString("Complete Training")
            builder.addAction(int(icon_id), learning_title, learning_pi)
            builder.addAction(int(icon_id), training_title, training_pi)

        notification_id = 1414 if with_actions else 1415
        notification_manager.notify(notification_id, builder.build())
        system["notification_tested"] = True
        save_json(SYSTEM_FILE, system)
        suffix = " with Complete Learning / Complete Training buttons" if with_actions else ""
        return True, "🔔 Android notification posted successfully" + suffix + ". Check the notification shade and expand it."
    except Exception as exc:
        return False, "❌ Android notification failed:\n\n" + repr(exc)


def test_action_notification():
    ok, setup_msg = setup_android_notifications()
    if not ok:
        return setup_msg
    sent, send_msg = send_android_notification(
        "⚔️ BINGO DAILY QUESTS",
        f"📚 {learning_today()}  |  🥋 {training_today()}",
        with_actions=True,
    )
    return setup_msg + "\n\n" + send_msg


def handle_notification_action_launch():
    """Process an action intent when Android opens Bingo from a notification."""
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        intent = activity.getIntent()
        if intent is None:
            return False
        action = intent.getAction()
        if not action:
            action = intent.getStringExtra("bingo_notification_action")
        if action == NOTIFICATION_LEARNING_ACTION:
            result = complete_learning()
            intent.setAction(NOTIFICATION_OPEN_ACTION)
            intent.removeExtra("bingo_notification_action")
        elif action == NOTIFICATION_TRAINING_ACTION:
            result = complete_training()
            intent.setAction(NOTIFICATION_OPEN_ACTION)
            intent.removeExtra("bingo_notification_action")
        elif action == NOTIFICATION_OPEN_ACTION:
            return False
        else:
            return False
        if APP_INSTANCE:
            APP_INSTANCE.add_message("⚔️ Bingo", "📲 Notification action received\n\n" + result)
            APP_INSTANCE.refresh_hud()
        return True
    except Exception as exc:
        if APP_INSTANCE:
            APP_INSTANCE.add_message("⚔️ Bingo", "❌ Notification action error: " + repr(exc))
        return False

# ------------------------------------------------------------
# BACKGROUND DAILY QUEST ALARM
# ------------------------------------------------------------

def schedule_background_quest_alarm():
    """Schedule Android to launch Bingo around 11:00 PM every day.

    This is the v13 background upgrade. If Android kills Bingo while it is
    not open, AlarmManager can wake/launch the app. Once Bingo starts, the
    app sends the normal quest notification and schedules the next alarm.
    """
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        Context = autoclass("android.content.Context")
        Intent = autoclass("android.content.Intent")
        PendingIntent = autoclass("android.app.PendingIntent")
        AlarmManager = autoclass("android.app.AlarmManager")

        # Numeric flags avoid more PyJNIus nested-class compatibility issues.
        FLAG_UPDATE_CURRENT = 0x08000000
        FLAG_IMMUTABLE = 0x04000000
        FLAG_ACTIVITY_NEW_TASK = 0x10000000
        FLAG_ACTIVITY_CLEAR_TOP = 0x04000000

        intent = Intent(activity, PythonActivity)
        intent.setAction(BACKGROUND_ALARM_ACTION)
        intent.addFlags(FLAG_ACTIVITY_NEW_TASK | FLAG_ACTIVITY_CLEAR_TOP)

        pending_intent = PendingIntent.getActivity(
            activity,
            BACKGROUND_ALARM_REQUEST_CODE,
            intent,
            FLAG_UPDATE_CURRENT | FLAG_IMMUTABLE,
        )

        alarm_manager = activity.getSystemService(Context.ALARM_SERVICE)
        if alarm_manager is None:
            return False, "❌ Android AlarmManager is unavailable."

        target = now().replace(
            hour=DAILY_QUEST_HOUR,
            minute=DAILY_QUEST_MINUTE,
            second=0,
            microsecond=0,
        )
        if target <= now():
            target += timedelta(days=1)

        trigger_ms = int(target.timestamp() * 1000)

        # setAndAllowWhileIdle works without requiring exact-alarm permission.
        alarm_manager.setAndAllowWhileIdle(
            AlarmManager.RTC_WAKEUP,
            trigger_ms,
            pending_intent,
        )

        return True, f"⏰ Background quest alarm scheduled for {target.strftime('%Y-%m-%d %I:%M %p')}."

    except Exception as exc:
        return False, "❌ Background alarm setup failed:\n\n" + repr(exc)


def cancel_background_quest_alarm():
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        Context = autoclass("android.content.Context")
        Intent = autoclass("android.content.Intent")
        PendingIntent = autoclass("android.app.PendingIntent")
        AlarmManager = autoclass("android.app.AlarmManager")

        FLAG_UPDATE_CURRENT = 0x08000000
        FLAG_IMMUTABLE = 0x04000000
        intent = Intent(activity, PythonActivity)
        intent.setAction(BACKGROUND_ALARM_ACTION)
        pending_intent = PendingIntent.getActivity(
            activity,
            BACKGROUND_ALARM_REQUEST_CODE,
            intent,
            FLAG_UPDATE_CURRENT | FLAG_IMMUTABLE,
        )
        alarm_manager = activity.getSystemService(Context.ALARM_SERVICE)
        alarm_manager.cancel(pending_intent)
        pending_intent.cancel()
        return True, "✅ Background quest alarm cancelled."
    except Exception as exc:
        return False, "❌ Could not cancel background alarm:\n\n" + repr(exc)


def handle_background_alarm_launch():
    """If Android launched Bingo because of the alarm, send the quest alert."""
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        intent = activity.getIntent()
        if intent is None:
            return False
        action = intent.getAction()
        if action != BACKGROUND_ALARM_ACTION:
            return False

        daily_reset()
        check_daily_quest_notification()
        # Make the next day's alarm ready immediately.
        schedule_background_quest_alarm()
        return True
    except Exception as exc:
        if APP_INSTANCE:
            APP_INSTANCE.add_message(
                "⚔️ Bingo",
                "❌ Background alarm launch error:\n\n" + repr(exc),
            )
        return False


def test_background_alarm():
    ok, msg = schedule_background_quest_alarm()
    return msg

# ------------------------------------------------------------
# COMMANDS
# ------------------------------------------------------------

def command_response(message):
    raw = message.strip()
    cmd = raw.lower()
    if cmd in ("status", "/status"):
        return status_text()
    if cmd in ("quests", "/quests", "today"):
        return quests_text()
    if cmd in ("schedule", "/schedule"):
        return schedule_text()
    if cmd in ("level", "/level"):
        return f"⚡ LEVEL {system['level']} — {system['exp']} / {system['exp_required']} EXP"
    if cmd in ("exp", "/exp"):
        return f"⭐ EXP: {system['exp']} / {system['exp_required']}"
    if cmd in ("streak", "/streak"):
        return f"🔥 STREAK: {system['streak']} days"
    if cmd in ("learning", "/learning"):
        return f"📚 Today's learning: {learning_today()}"
    if cmd in ("training", "/training"):
        return f"🥋 Today's training: {training_today()}"
    if cmd in ("complete learning", "/complete learning", "done learning"):
        return complete_learning()
    if cmd in ("complete training", "/complete training", "done training"):
        return complete_training()
    if cmd in ("test jni", "/test jni"):
        return test_jni()[1]
    if cmd in ("test action notification", "/test action notification", "test action"):
        return test_action_notification()
    if cmd in ("test notification", "/test notification", "test notifications"):
        ok, msg = setup_android_notifications()
        if not ok:
            return msg
        _, sent = send_android_notification("Bingo test", "Android notifications are working.")
        return msg + "\n\n" + sent
    if cmd in ("test daily quest", "/test daily quest", "test daily notification"):
        ok, msg = setup_android_notifications()
        if not ok: return msg
        _, sent = test_daily_quest_notification()
        return msg + "\n\n" + sent

    if cmd in ("notifications", "/notifications"):
        ok, msg = setup_android_notifications()
        return msg
    if cmd in ("background alarm", "/background alarm", "test background alarm"):
        return test_background_alarm()
    if cmd in ("cancel background alarm", "/cancel background alarm"):
        return cancel_background_quest_alarm()[1]
    if cmd in ("next", "/next"):
        dt, label = next_event()
        remaining = dt - now()
        total = max(0, int(remaining.total_seconds()))
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"⏳ NEXT: {label}\n{dt.strftime('%I:%M %p')}\nIn {h}h {m}m {s}s"
    if cmd.startswith("remind me in "):
        match = re.search(r"remind me in\s+(\d+)\s+minute", cmd)
        if match:
            minutes = int(match.group(1))
            threading.Timer(
                minutes * 60,
                lambda: send_android_notification("Bingo reminder", "Your reminder is due."),
            ).start()
            return f"⏰ Reminder set for {minutes} minute(s)."
    return None

# ------------------------------------------------------------
# UI
# ------------------------------------------------------------

class BingoLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(8), **kwargs)

        self.hud = Label(
            text="⚔️ BINGO SYSTEM",
            size_hint_y=None,
            height=dp(80),
            halign="left",
            valign="middle",
        )
        self.hud.bind(size=lambda obj, value: setattr(obj, "text_size", value))
        self.add_widget(self.hud)

        self.scroll = ScrollView(
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(4),
            scroll_type=["bars", "content"],
        )
        self.chat_label = Label(
            text="⚔️ BINGO\n\nHello Abdul. I'm ready.",
            size_hint=(1, None),
            halign="left",
            valign="top",
            padding=(dp(8), dp(8)),
        )
        # Keep the label exactly as wide as the visible scroll area and wrap long lines.
        self.chat_label.bind(width=self._fit_chat_text)
        self.chat_label.bind(texture_size=self._fit_chat_height)
        self.scroll.add_widget(self.chat_label)
        self.add_widget(self.scroll)

        self.message_box = TextInput(
            hint_text="Talk to Bingo...",
            hint_text_color=(0.72, 0.74, 0.78, 1),
            foreground_color=(1, 1, 1, 1),
            background_color=(0.12, 0.13, 0.17, 1),
            cursor_color=(1, 1, 1, 1),
            selection_color=(0.2, 0.45, 0.8, 0.7),
            # Ask Android/Gboard to use normal text input with word suggestions.
            input_type="text",
            keyboard_suggestions=True,
            multiline=True,
            size_hint_y=None,
            height=dp(58),
            padding=(dp(10), dp(10)),
        )
        self.add_widget(self.message_box)

        # Two compact rows avoid cramped buttons on narrow phone screens.
        for button_specs in [
            [("SEND", self.send_message), ("STATUS", self.status_button), ("QUESTS", self.quests_button)],
            [("API KEY", self.api_key_button), ("TEST NOTICE", self.notification_button), ("ACTION TEST", self.action_notification_button), ("ALARM", self.alarm_button)],
        ]:
            row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(5))
            for text_value, callback in button_specs:
                b = Button(text=text_value, font_size="11sp")
                b.bind(on_press=callback)
                row.add_widget(b)
            self.add_widget(row)

        Clock.schedule_interval(self.refresh_hud, 1)
        Clock.schedule_interval(self.check_daily_reminder, 10)

    def _fit_chat_text(self, instance, width):
        instance.text_size = (max(1, width - dp(16)), None)

    def _fit_chat_height(self, instance, texture_size):
        instance.height = texture_size[1] + dp(16)

    @mainthread
    def add_message(self, sender, message):
        self.chat_label.text += f"\n\n{sender}: {message}"
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.05)

    def send_message(self, instance):
        message = self.message_box.text.strip()
        if not message:
            return
        self.message_box.text = ""
        self.add_message("Abdul", message)
        quick = command_response(message)
        if quick is not None:
            self.add_message("⚔️ Bingo", quick)
            return
        threading.Thread(target=self._ask_worker, args=(message,), daemon=True).start()

    def _ask_worker(self, message):
        answer = ask_gemini(message)
        self.add_message("⚔️ Bingo", answer)

    def api_key_button(self, instance):
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        info = Label(
            text="Enter your Gemini API key. It is saved in Bingo's private app storage, not in GitHub.",
            size_hint_y=None, height=dp(70), halign="left", valign="middle"
        )
        info.bind(size=lambda obj, value: setattr(obj, "text_size", value))
        key_input = TextInput(
            hint_text="Paste Gemini API key here",
            hint_text_color=(0.72, 0.74, 0.78, 1),
            foreground_color=(1, 1, 1, 1),
            background_color=(0.12, 0.13, 0.17, 1),
            cursor_color=(1, 1, 1, 1),
            multiline=False, password=True, size_hint_y=None, height=dp(48)
        )
        content.add_widget(info)
        content.add_widget(key_input)
        buttons = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        save_btn = Button(text="SAVE KEY")
        cancel_btn = Button(text="CANCEL")
        buttons.add_widget(save_btn)
        buttons.add_widget(cancel_btn)
        content.add_widget(buttons)
        popup = Popup(title="Bingo — Gemini API Key", content=content,
                      size_hint=(0.92, None), height=dp(250), auto_dismiss=False)

        def save_key(_button):
            key = key_input.text.strip()
            if not key:
                self.add_message("⚔️ Bingo", "❌ Please enter a key first.")
                return
            if store_api_key(key):
                key_input.text = ""
                popup.dismiss()
                self.add_message("⚔️ Bingo", "✅ API key saved in Bingo's private app storage. Send a message to test Gemini.")
            else:
                self.add_message("⚔️ Bingo", "❌ Could not save the key. Check app storage permissions and try again.")

        save_btn.bind(on_press=save_key)
        cancel_btn.bind(on_press=lambda _button: popup.dismiss())
        popup.open()

    def status_button(self, instance):
        self.add_message("⚔️ Bingo", status_text())

    def quests_button(self, instance):
        self.add_message("⚔️ Bingo", quests_text())

    def notification_button(self, instance):
        ok, setup_msg = setup_android_notifications()
        if not ok:
            self.add_message("⚔️ Bingo", setup_msg)
            return
        _, send_msg = send_android_notification("Bingo test", "Android notifications are working.")
        self.add_message("⚔️ Bingo", setup_msg + "\n\n" + send_msg)

    def action_notification_button(self, instance):
        result = test_action_notification()
        self.add_message("⚔️ Bingo", result)

    def alarm_button(self, instance):
        self.add_message("⚔️ Bingo", test_background_alarm())

    def jni_button(self, instance):
        self.add_message("⚔️ Bingo", test_jni()[1])

    def check_daily_reminder(self, *args):
        check_daily_quest_notification()

    def refresh_hud(self, *args):
        daily_reset()
        dt, label = next_event()
        total = max(0, int((dt - now()).total_seconds()))
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        self.hud.text = (
            f"⚔️ BINGO  |  LV {system['level']}  |  EXP {system['exp']}/{system['exp_required']}\n"
            f"🔥 Streak {system['streak']}  |  🎯 Quests {system['quests_completed']}\n"
            f"⏳ Next: {label} in {h:02d}:{m:02d}:{s:02d}"
        )

# ------------------------------------------------------------
# APP
# ------------------------------------------------------------

class BingoApp(App):
    def build(self):
        global APP_INSTANCE
        daily_reset()
        APP_INSTANCE = BingoLayout()
        ok, msg = test_jni()
        APP_INSTANCE.add_message("⚔️ Bingo", msg)
        ok2, msg2 = setup_android_notifications()
        APP_INSTANCE.add_message("⚔️ Bingo", msg2)
        return APP_INSTANCE

    def on_start(self):
        ok, msg = request_notification_permission()
        if APP_INSTANCE:
            APP_INSTANCE.add_message("⚔️ Bingo", msg)
            APP_INSTANCE.refresh_hud()

        # Always arm the next 11:00 PM Android alarm.
        Clock.schedule_once(lambda dt: self._finish_startup(), 1.5)

    def _finish_startup(self):
        ok, msg = setup_android_notifications()
        if APP_INSTANCE:
            APP_INSTANCE.add_message("⚔️ Bingo", msg)

        alarm_triggered = handle_background_alarm_launch()
        action_triggered = handle_notification_action_launch()
        if APP_INSTANCE and action_triggered:
            APP_INSTANCE.add_message("⚔️ Bingo", "✅ Notification action processed.")
        if APP_INSTANCE:
            if alarm_triggered:
                APP_INSTANCE.add_message(
                    "⚔️ Bingo",
                    "⚔️ Background Daily Quest alarm triggered."
                )
            ok_alarm, alarm_msg = schedule_background_quest_alarm()
            APP_INSTANCE.add_message("⚔️ Bingo", alarm_msg)

if __name__ == "__main__":
    BingoApp().run()
