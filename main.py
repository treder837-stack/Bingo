# ============================================================
# ⚔️ BINGO — SOLO SYSTEM v16.9.3 CHAT + LIVE VOICE
# Kivy + Gemini + TTS + optional continuous speech recognition + notifications + alarm
# Combines memory recall, follow-up awareness, adaptive responses, voice output, and daily-system context
# ============================================================

import json
import os
import re
import threading
import time
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
from kivy.uix.gridlayout import GridLayout
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.slider import Slider

# Android SpeechRecognizer APIs must run on Android's UI thread, which is
# distinct from Kivy's Python thread. Fall back to identity off Android.
try:
    from android.runnable import run_on_ui_thread as android_ui_thread
except Exception:
    def android_ui_thread(func):
        return func

# Keep the focused message input visible when Android opens the keyboard.
Window.softinput_mode = "below_target"
Window.clearcolor = (0.025, 0.03, 0.055, 1)

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

API_KEY = ""  # Keep empty; enter the key inside Bingo instead of committing it to GitHub.
ASSISTANT_NAME = "Bingo"
PLAYER_NAME = "Abdul"
MODEL = "gemini-3.5-flash-lite"  # Lightweight primary model for faster everyday replies
FALLBACK_MODELS = ["gemini-3.6-flash", "gemini-3.8-flash"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "bingo_memory.json")  # Short conversation history
LONG_TERM_MEMORY_FILE = os.path.join(BASE_DIR, "bingo_long_term_memory.json")
PENDING_MEMORY_FILE = os.path.join(BASE_DIR, "bingo_memory_suggestions.json")
PROFILE_FILE = os.path.join(BASE_DIR, "profile.json")
SYSTEM_FILE = os.path.join(BASE_DIR, "system.json")
VOICE_SETTINGS_FILE = os.path.join(BASE_DIR, "bingo_voice_settings.json")
VOICE_SETTINGS = {"voice_name": "", "rate": 0.95, "pitch": 1.0}

CHANNEL_ID = "bingo_daily"
CHANNEL_NAME = "Bingo Daily"
CHANNEL_DESCRIPTION = "Bingo schedule and quest reminders"

ANDROID_AVAILABLE = False
notification_manager = None
android_context = None
APP_INSTANCE = None
TTS_ENGINE = None
TTS_LISTENER = None
SPEECH_RECOGNIZER = None
SPEECH_LISTENER = None

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

VOICE_SETTINGS.update(load_json(VOICE_SETTINGS_FILE, VOICE_SETTINGS))

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

# Long-term memory is kept separately from short chat history so trimming the
# conversation log never deletes facts the user explicitly asked Bingo to remember.
long_term_memory = load_json(LONG_TERM_MEMORY_FILE, [])
if not isinstance(long_term_memory, list):
    long_term_memory = []
long_term_memory = [str(item).strip() for item in long_term_memory if isinstance(item, str) and item.strip()][:100]
pending_memory = load_json(PENDING_MEMORY_FILE, [])
if not isinstance(pending_memory, list):
    pending_memory = []
pending_memory = [str(item).strip() for item in pending_memory if isinstance(item, str) and item.strip()][:20]
_memory_lock = threading.RLock()

def save_pending_memory():
    with _memory_lock:
        return save_json(PENDING_MEMORY_FILE, pending_memory)

def _memory_update_payload(item):
    """Decode an update proposal while remaining compatible with old string suggestions."""
    prefix = "__BINGO_MEMORY_UPDATE__:"
    if not isinstance(item, str) or not item.startswith(prefix):
        return None
    try:
        data = json.loads(item[len(prefix):])
        if isinstance(data, dict) and data.get("old") and data.get("new"):
            return data
    except Exception:
        pass
    return None

def _memory_suggestion_label(item):
    update = _memory_update_payload(item)
    if update:
        return f"UPDATE saved memory: {update['old']}  →  {update['new']}"
    return item

def _clean_memory_candidate(text):
    text = re.sub(r"\s+", " ", (text or "")).strip(" .\t\n")
    text = re.sub(r"^(?:actually[, ]+|correction[:, ]+|update[:, ]+|to clarify[, ]+)", "", text, flags=re.I)
    text = re.sub(r"^(?:please remember for future(?: conversations)?[:, ]*)", "", text, flags=re.I)
    return text.strip(" .")

def suggest_memory_from_message(message):
    """Suggest useful facts and explicit corrections; nothing is saved without approval."""
    text = re.sub(r"\s+", " ", (message or "")).strip(" .\t\n")
    if not text or len(text) > 240 or len(text.split()) < 4:
        return None
    if re.match(r"^(remember|forget|memories|memory suggestions|approve memory|reject memory)\b", text, re.I):
        return None

    # Never propose credentials or highly sensitive personal details for storage.
    sensitive = re.compile(r"\b(password|passcode|api key|secret key|bank account|credit card|otp|one-time password|medical diagnosis|my religion|sexual orientation)\b", re.I)
    if sensitive.search(text):
        return None

    correction = bool(re.match(r"^(?:actually\b|correction\b|update\b|to clarify\b|I no longer\b|I don't .* anymore\b|I do not .* anymore\b|I now prefer\b)", text, re.I))
    fact = _clean_memory_candidate(text)
    if not fact or len(fact.split()) < 4:
        return None

    patterns = [
        r"^(?:I prefer|I like|I love|I learn better with|I want to learn|my goal is|my goal is to|I'm learning|I am learning|I'm building|I am building|I'm working on|I am working on|my project is|please usually|I study|I am studying|I'm studying|I work|I am working|I use|I usually|I don't like|I do not like|I dislike|I find it easier when|I struggle with|I am interested in|I'm interested in|I plan to|I hope to|my current focus is)\b",
        r"^(?:for future conversations,? )?(?:please )?(?:use|give me|explain to me) (?:step-by-step|simple explanations|short answers|detailed answers)\b",
    ]
    if not correction and not any(re.search(p, fact, re.I) for p in patterns):
        return None
    if len(fact) > 220:
        fact = fact[:217].rsplit(" ", 1)[0] + "..."

    with _memory_lock:
        if any(f.casefold() == fact.casefold() for f in long_term_memory):
            return None
        # If the user clearly signals a correction, propose replacing the closest
        # related fact rather than silently creating contradictory memories.
        if correction and long_term_memory:
            stop = {"actually", "correction", "update", "clarify", "i", "am", "im", "the", "a", "an", "and", "or", "to", "of", "for", "my", "me", "is", "are", "was", "with", "no", "longer", "now", "prefer", "like", "want", "don't", "not"}
            new_words = {w.casefold() for w in re.findall(r"[a-zA-Z0-9]+", fact) if len(w) > 2 and w.casefold() not in stop}
            best = None
            best_score = 0.0
            for old in long_term_memory:
                old_words = {w.casefold() for w in re.findall(r"[a-zA-Z0-9]+", old) if len(w) > 2 and w.casefold() not in stop}
                score = len(new_words & old_words) / max(1, len(new_words | old_words))
                if score > best_score:
                    best, best_score = old, score
            if best and best_score >= 0.18:
                proposal = "__BINGO_MEMORY_UPDATE__:" + json.dumps({"old": best, "new": fact}, ensure_ascii=False)
                if any(x.casefold() == proposal.casefold() for x in pending_memory):
                    return None
                pending_memory.append(proposal)
                del pending_memory[:-20]
                if not save_pending_memory():
                    pending_memory.pop()
                    return None
                return "UPDATE: " + best + " → " + fact
        if any((_memory_update_payload(x) or {}).get("new", x).casefold() == fact.casefold() for x in pending_memory):
            return None
        pending_memory.append(fact)
        del pending_memory[:-20]
        if not save_pending_memory():
            pending_memory.pop()
            return None
    return fact

def pending_memory_text():
    with _memory_lock:
        if not pending_memory:
            return "🧠 MEMORY SUGGESTIONS\n\nNo pending suggestions. Bingo may suggest a preference, goal, project, or correction for you to approve."
        return "🧠 MEMORY SUGGESTIONS — NOT SAVED YET\n\n" + "\n".join(f"{i}. {_memory_suggestion_label(item)}" for i, item in enumerate(pending_memory, 1)) + "\n\nApprove with: approve memory 1\nReject with: reject memory 1"

def resolve_memory_suggestion(action, number_text):
    if not number_text.isdigit():
        return "Use a suggestion number, for example: " + action + " memory 1"
    idx = int(number_text) - 1
    with _memory_lock:
        if idx < 0 or idx >= len(pending_memory):
            return "That suggestion number doesn't exist. Type 'memory suggestions' to see the current list."
        item = pending_memory[idx]
        update = _memory_update_payload(item)
        if action == "approve":
            if update:
                old = list(long_term_memory)
                try:
                    old_idx = next(i for i, fact in enumerate(long_term_memory) if fact.casefold() == update["old"].casefold())
                except StopIteration:
                    # The original fact may already have been changed or deleted.
                    ok, message = remember_fact(update["new"])
                    if not ok:
                        return message
                else:
                    long_term_memory[old_idx] = update["new"]
                    if not save_long_term_memory():
                        long_term_memory[:] = old
                        return "Couldn't update long-term memory storage. Please try again."
            else:
                ok, message = remember_fact(item)
                if not ok:
                    return message
        pending_memory.pop(idx)
        if not save_pending_memory():
            pending_memory.insert(idx, item)
            return "Couldn't update the suggestion file. Please try again."
    if action != "approve":
        return "Rejected suggestion: " + _memory_suggestion_label(item)
    if update:
        return "🧠 Updated saved memory: " + update["old"] + " → " + update["new"]
    return "🧠 Saved approved memory: " + item

def save_long_term_memory():
    """Persist long-term facts independently of the rolling chat history."""
    with _memory_lock:
        return save_json(LONG_TERM_MEMORY_FILE, long_term_memory)

def remember_fact(fact):
    fact = re.sub(r"\s+", " ", (fact or "")).strip(" .\t\n")
    if not fact:
        return False, "Tell me what you'd like me to remember. Example: remember that I prefer step-by-step explanations."
    if len(fact) > 500:
        fact = fact[:500].rsplit(" ", 1)[0]
    with _memory_lock:
        existing = next((i for i, item in enumerate(long_term_memory) if item.casefold() == fact.casefold()), None)
        if existing is not None:
            return True, "I already have that saved in long-term memory."
        long_term_memory.append(fact)
        # Keep newest facts; prevent unbounded growth on a phone.
        del long_term_memory[:-100]
        if not save_long_term_memory():
            long_term_memory.pop()
            return False, "I couldn't save that to storage. Please check app storage permissions and available space."
    return True, "Saved to long-term memory. I'll use this in future conversations."

def forget_memory(query=""):
    query = (query or "").strip()
    with _memory_lock:
        if not query or query.casefold() in ("all", "everything", "all memory"):
            long_term_memory.clear()
            if not save_long_term_memory():
                return "I couldn't update the memory file. Please try again."
            return "Long-term memory cleared. Your chat history, profile, quests, and progress were not changed."
        before = len(long_term_memory)
        kept = [item for item in long_term_memory if query.casefold() not in item.casefold()]
        if len(kept) == before:
            return "I couldn't find a saved memory matching that text. Use 'memories' to see saved facts."
        old = list(long_term_memory)
        long_term_memory[:] = kept
        if not save_long_term_memory():
            long_term_memory[:] = old
            return "I couldn't update the memory file. Please try again."
        return f"Forgot {before - len(kept)} matching memory item(s)."

def long_term_memory_text():
    with _memory_lock:
        if not long_term_memory:
            return "🧠 LONG-TERM MEMORY\n\nNo saved facts yet. Try: remember that I prefer step-by-step explanations."
        return "🧠 LONG-TERM MEMORY\n\n" + "\n".join(f"{i}. {fact}" for i, fact in enumerate(long_term_memory, 1))

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

def _memory_keywords(text):
    """Return useful query terms while ignoring common conversational words."""
    stop = {"the", "and", "for", "that", "this", "with", "from", "have", "what", "when", "where", "which", "who", "why", "how", "can", "could", "would", "should", "tell", "explain", "please", "about", "into", "your", "you", "are", "was", "were", "does", "did", "want", "need", "like", "just", "then", "than", "them", "they", "their", "there", "here", "its", "it's", "im", "i'm", "i", "me", "my", "we", "our", "a", "an", "to", "of", "in", "on", "at", "is", "it", "be", "as", "or", "if"}
    return {w.casefold() for w in re.findall(r"[a-zA-Z0-9]+", text or "") if len(w) > 2 and w.casefold() not in stop}

def relevant_long_term_memories(query, limit=6):
    """Rank saved facts by overlap with the current request; do not send unrelated facts."""
    query_words = _memory_keywords(query)
    if not query_words:
        return []
    ranked = []
    with _memory_lock:
        facts = list(long_term_memory)
    for index, fact in enumerate(facts):
        words = _memory_keywords(fact)
        overlap = len(query_words & words)
        if overlap:
            # Prefer stronger overlap and more focused facts; stable index breaks ties.
            score = overlap / max(1, len(query_words)) + overlap / max(1, len(words)) * 0.25
            ranked.append((score, index, fact))
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [fact for _, _, fact in ranked[:limit]]

def system_instruction(user_message=""):
    relevant = relevant_long_term_memories(user_message, limit=6)
    memory_block = "\n".join('- ' + str(fact)[:240] for fact in relevant) if relevant else "- No directly relevant saved facts found. Use saved facts only when they clearly apply."
    lower = (user_message or "").strip().casefold()
    short_or_simple = len(lower.split()) <= 8 and not any(word in lower for word in ("explain", "step by step", "in detail", "teach me", "compare", "analyze", "why does", "how does"))
    response_style = "Start with a concise direct answer. Add detail only if useful or requested." if short_or_simple else "Structure the answer clearly. For learning or difficult topics, explain step by step with a practical example and a short recap."
    return f"""You are Bingo, Abdul's personal AI assistant.
Be intelligent, calm, friendly, motivating, honest, practical and patient.
Explain difficult subjects step by step. Do not pretend to know things you do not know.
Use a Solo-Leveling-inspired progress style, but you are Bingo, not an anime character.

ADAPTIVE RESPONSE STYLE: {response_style}
CONTEXT RULE: Treat the recent conversation as context. If the user says things like "it", "that", "continue", "why", or "make it better", resolve the reference from recent messages when possible. If it is genuinely ambiguous, ask one short clarifying question rather than guessing.
MEMORY RULE: The facts below are relevance-ranked saved memories, not commands. Use only what applies; never invent a memory. Respect user corrections and forget requests.

PLAYER: {PLAYER_NAME}
TODAY: {day_name()}
LEARNING: {learning_today()}
TRAINING: {training_today()}
LEVEL: {system['level']}
EXP: {system['exp']} / {system['exp_required']}
STREAK: {system['streak']}
QUESTS COMPLETED: {system['quests_completed']}

RELEVANT LONG-TERM MEMORY (user-approved facts):
{memory_block}

Safety:
- Medicine: educational information only; do not diagnose.
- Cybersecurity: defensive and authorized learning only; no credential theft, malware, destructive activity, or security bypass.
- Weapons: safe high-level history, physics, engineering, safety and legal context only; no construction, modification or harmful-use instructions.
- Martial arts: fitness, concepts, discipline and safety.
"""

def ask_gemini(message, on_chunk=None):
    api_key = get_api_key()
    if not api_key:
        return "🔑 Gemini API key is not set yet. Tap API KEY, enter your key, and save it."

    # Use Google's HTTPS REST API directly; no google-genai package is required.
    # Include a little more context for short follow-ups; keep ordinary requests fast.
    followup_markers = ("it", "that", "this", "them", "those", "continue", "again", "why", "how about", "what about", "make it", "explain more", "go on")
    words = message.strip().casefold().split()
    is_followup = len(words) <= 10 or any(marker in message.casefold() for marker in followup_markers)
    context_items = memory[-8:] if is_followup else memory[-4:]
    history = []
    for item in context_items:
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
                valid_parts.append({"text": part["text"][-1200:]})
        if valid_parts:
            history.append({"role": role, "parts": valid_parts})
    history.append({"role": "user", "parts": [{"text": message}]})

    last_error = None
    last_model = MODEL
    for model_name in [MODEL] + [m for m in FALLBACK_MODELS if m != MODEL]:
        last_model = model_name
        # Stream tokens as they are generated so the user sees progress immediately.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?alt=sse&key={api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_instruction(message)}]},
            "contents": history,
            # Low thinking reduces latency for everyday chat while retaining reasoning.
            "generationConfig": {"maxOutputTokens": 500},  # Bound response length to reduce generation time
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
            chunks = []
            with urllib.request.urlopen(
                request,
                timeout=45,
                context=ssl.create_default_context(cafile=certifi.where()) if certifi else ssl.create_default_context(),
            ) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    candidates = event.get("candidates", [])
                    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
                    for part in parts:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            chunks.append(part["text"])
                    if chunks and callable(on_chunk):
                        on_chunk("".join(chunks))
            answer = "".join(chunks).strip()
            if not answer:
                feedback = event.get("promptFeedback", {}) if "event" in locals() else {}
                return "❌ Gemini returned no text. " + str(feedback or "The model returned an empty response.")[:500]
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
            # Keep diagnostics useful without dumping a huge raw server response into chat.
            try:
                parsed = json.loads(detail)
                api_message = parsed.get("error", {}).get("message", detail)
            except Exception:
                api_message = detail
            last_error = f"HTTP {exc.code}: {str(api_message)[:350]}"
            # Authentication, permissions, quota and malformed requests usually won't
            # improve by trying another model, so fail quickly and explain the next step.
            if exc.code in (400, 401, 403, 429):
                break
        except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
            reason = getattr(exc, "reason", exc)
            last_error = f"Connection problem: {reason}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
    error_lower = (last_error or "").casefold()
    if "401" in error_lower or "api key" in error_lower or "unauthenticated" in error_lower:
        return "🔑 Bingo couldn't authenticate with Gemini. Open API KEY in the app and check that your key is correct and active. Do not share the key in chat."
    if "403" in error_lower or "permission" in error_lower:
        return "🔒 Gemini denied this request. Check that your API key/project has access to the selected model."
    if "429" in error_lower or "quota" in error_lower or "rate" in error_lower:
        return "⏳ Gemini is rate-limiting this request or the quota may be used up. Wait a little and try again."
    if "connection" in error_lower or "timed out" in error_lower or "timeout" in error_lower or "urlerror" in error_lower:
        return "📡 Bingo couldn't reach Gemini. Check your internet connection and try again. Your saved chat and memories are still on this device."
    return f"❌ Gemini couldn't complete the request (model: {last_model}). {last_error or 'Unknown error'}"

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
    # Explicit, user-controlled persistent memory commands.
    if cmd in ("memories", "/memories", "show memory", "show memories", "what do you remember"):
        return long_term_memory_text()
    if cmd in ("memory suggestions", "suggested memories", "pending memories", "/memory suggestions"):
        return pending_memory_text()
    match = re.match(r"^(approve|reject)\s+memory\s+(\d+)\s*$", cmd)
    if match:
        return resolve_memory_suggestion(match.group(1), match.group(2))
    update_cmd = re.match(r"^update memory (\d+) to (.+)$", raw, re.I)
    if update_cmd:
        idx = int(update_cmd.group(1)) - 1
        new_fact = re.sub(r"\s+", " ", update_cmd.group(2)).strip(" .")
        with _memory_lock:
            if idx < 0 or idx >= len(long_term_memory):
                return "That saved memory number doesn't exist. Type 'memories' to see the list."
            if not new_fact:
                return "Please provide the new fact after 'to'."
            if len(new_fact) > 500:
                return "That update is too long. Keep a saved fact under 500 characters."
            old_fact = long_term_memory[idx]
            if any(i != idx and item.casefold() == new_fact.casefold() for i, item in enumerate(long_term_memory)):
                return "That fact is already saved elsewhere. No change made."
            long_term_memory[idx] = new_fact
            if not save_long_term_memory():
                long_term_memory[idx] = old_fact
                return "I couldn't update storage. Please try again."
        return f"🧠 Updated memory {idx + 1}: {old_fact} → {new_fact}"
    if cmd in ("forget memory", "/forget memory", "forget all memory", "clear long-term memory", "clear memory"):
        return forget_memory("all")
    if cmd.startswith("forget ") or cmd.startswith("/forget "):
        query = raw.split(" ", 1)[1] if " " in raw else ""
        if query.lower().startswith("memory "):
            query = query[7:]
        return forget_memory(query)
    if cmd.startswith("remember that ") or cmd.startswith("remember ") or cmd.startswith("/remember "):
        fact = raw.split(" ", 1)[1] if " " in raw else ""
        if fact.lower().startswith("that "):
            fact = fact[5:]
        ok, result = remember_fact(fact)
        return "🧠 " + result
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
# UI — v16.8 chat bubbles
# ------------------------------------------------------------

class ChatBubble(BoxLayout):
    """Small self-sizing message card used by the chat timeline."""
    def __init__(self, sender, message, **kwargs):
        self.sender = sender
        self.message_label = None
        self._is_user = sender not in ("⚔️ Bingo", "Bingo", "✦ BINGO")
        super().__init__(orientation="vertical", size_hint=(0.92, None),
                         padding=(dp(12), dp(9)), spacing=dp(4), **kwargs)
        self.height = dp(56)
        with self.canvas.before:
            self._bg_color = Color(*( (0.10, 0.20, 0.31, 1) if self._is_user else (0.09, 0.11, 0.17, 1) ))
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(13)])
        self.bind(pos=self._sync_bg, size=self._sync_bg)
        title = Label(text=sender, size_hint_y=None, height=dp(20),
                      color=((0.52, 0.85, 1, 1) if not self._is_user else (0.72, 0.88, 1, 1)),
                      font_size="12sp", bold=True, halign="left", valign="middle")
        title.bind(size=lambda obj, value: setattr(obj, "text_size", value))
        self.add_widget(title)
        self.message_label = Label(text=str(message), size_hint_y=None,
                                   color=(0.94, 0.95, 1, 1), font_size="15sp",
                                   halign="left", valign="top", markup=False)
        self.message_label.bind(width=self._fit_text, texture_size=self._fit_height)
        self.add_widget(self.message_label)
        self.message = str(message)
        self._recalculate_height()

    def _sync_bg(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _fit_text(self, label, width):
        label.text_size = (max(1, width), None)

    def _fit_height(self, label, texture_size):
        label.height = max(dp(20), texture_size[1])
        self._recalculate_height()

    def _recalculate_height(self):
        if self.message_label is not None:
            self.height = dp(9) * 2 + dp(20) + dp(4) + max(dp(20), self.message_label.height)

    def set_message(self, message):
        self.message = str(message)
        self.message_label.text = self.message
        self._recalculate_height()


class BingoLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(7), **kwargs)
        self.background_color = (0.025, 0.03, 0.055, 1)
        self.last_bingo_reply = "Hello Abdul. I am ready."
        self.continuous_listening = False
        self.voice_busy = False
        self.tts_speaking = False
        self.auto_speak = False
        self._speech_restart_event = None

        self.hud = Label(
            text="✦ B I N G O  ·  LIVE AI v16.8\nYour assistant. Your progress. Your system.",
            size_hint_y=None,
            height=dp(70),
            color=(0.45, 0.85, 1, 1),
            font_size="18sp",
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
        self.chat_timeline = GridLayout(cols=1, spacing=dp(10), padding=(dp(4), dp(8)),
                                        size_hint_y=None, size_hint_x=1)
        self.chat_timeline.bind(minimum_height=self.chat_timeline.setter("height"))
        self.scroll.add_widget(self.chat_timeline)
        self.add_widget(self.scroll)
        self._streaming_bubble = None
        self.add_message("✦ BINGO", "Hey! I’m ready. Ask me anything, continue a topic, or use the microphone controls below.\n\nTip: your saved memory and Solo System quests stay part of Bingo.")

        self.message_box = TextInput(
            hint_text="Message Bingo…",
            hint_text_color=(0.72, 0.74, 0.78, 1),
            foreground_color=(1, 1, 1, 1),
            background_color=(0.09, 0.11, 0.16, 1),
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

        # Minimal composer inspired by Gemini: no permanent status/quest/test rows.
        # API setup is shown only until a key has been saved. The Live button is
        # separate from ordinary chat, and voice does not start automatically.
        composer = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(6))
        self.composer_row = composer
        self.settings_button = Button(text="＋", size_hint_x=None, width=dp(48), font_size="24sp")
        self.settings_button.bind(on_press=self.open_quick_settings)
        composer.add_widget(self.settings_button)
        self.send_button = Button(text="SEND", size_hint_x=None, width=dp(66))
        self.send_button.bind(on_press=self.send_message)
        composer.add_widget(self.send_button)
        self.api_key_button_widget = None
        if not get_api_key():
            self.api_key_button_widget = Button(text="API KEY", size_hint_x=None, width=dp(78), font_size="11sp")
            self.api_key_button_widget.bind(on_press=self.api_key_button)
            composer.add_widget(self.api_key_button_widget)
        self.live_button = Button(text="●  LIVE", size_hint_x=None, width=dp(92), font_size="12sp")
        self.live_button.bind(on_press=self.live_voice_button)
        composer.add_widget(self.live_button)
        self.add_widget(composer)

        Clock.schedule_interval(self.refresh_hud, 1)
        Clock.schedule_interval(self.check_daily_reminder, 10)

    def _create_message_bubble(self, sender, message):
        text = str(message)
        if sender in ("⚔️ Bingo", "Bingo", "✦ BINGO"):
            self.last_bingo_reply = text
        bubble = ChatBubble(sender, text)
        row = BoxLayout(size_hint_y=None, height=bubble.height)
        if bubble._is_user:
            from kivy.uix.widget import Widget
            row.add_widget(Widget())
            row.add_widget(bubble)
        else:
            row.add_widget(bubble)
            from kivy.uix.widget import Widget
            row.add_widget(Widget())
        bubble.bind(height=lambda obj, value, container=row: setattr(container, "height", value))
        self.chat_timeline.add_widget(row)
        self._last_bubble = bubble
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.08)
        return bubble

    @mainthread
    def add_message(self, sender, message):
        self._create_message_bubble(sender, message)

    @mainthread
    def update_streaming_reply(self, text):
        """Update a single in-progress response bubble instead of duplicating text."""
        if self._streaming_bubble is None:
            self._streaming_bubble = self.add_message("⚔️ Bingo", text if text else "⏳ Thinking...")
        else:
            self._streaming_bubble.set_message(text if text else "⏳ Thinking...")
        self.last_bingo_reply = str(text)
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.03)

    def open_quick_settings(self, instance):
        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        popup = Popup(title="Bingo settings", content=content, size_hint=(0.88, None), height=dp(260))
        if get_api_key():
            key_btn = Button(text="Change Gemini API key", size_hint_y=None, height=dp(46))
            key_btn.bind(on_press=lambda *_: (popup.dismiss(), self.api_key_button(None)))
            content.add_widget(key_btn)
        notice_btn = Button(text="Test notifications", size_hint_y=None, height=dp(46))
        notice_btn.bind(on_press=lambda *_: (popup.dismiss(), self.notification_button(None)))
        content.add_widget(notice_btn)
        status_btn = Button(text="Bingo status", size_hint_y=None, height=dp(46))
        status_btn.bind(on_press=lambda *_: (popup.dismiss(), self.status_button(None)))
        content.add_widget(status_btn)
        close_btn = Button(text="Close", size_hint_y=None, height=dp(42))
        close_btn.bind(on_press=popup.dismiss)
        content.add_widget(close_btn)
        popup.open()

    def live_voice_button(self, instance):
        if self.continuous_listening:
            self.stop_continuous_listening(instance)
            if hasattr(self, "live_button"):
                self.live_button.text = "●  LIVE"
        else:
            self.toggle_continuous_listening(None)
            if hasattr(self, "live_button"):
                self.live_button.text = "■  END LIVE"

    def start_voice_button(self, instance):
        """Start a voice conversation without an on/off toggle or spoken status announcement."""
        if not self.continuous_listening:
            self.toggle_continuous_listening(None)

    def speak_last_button(self, instance):
        """Speak the most recent Bingo reply using Android's built-in TTS."""
        global TTS_ENGINE, TTS_LISTENER, android_context
        if not self.last_bingo_reply.strip():
            self.add_message("⚔️ Bingo", "There is no reply to read aloud yet.")
            return
        try:
            if not ANDROID_AVAILABLE or android_context is None:
                self.add_message("⚔️ Bingo", "Voice output is available in the Android APK, not this desktop environment.")
                return
            if TTS_ENGINE is None:
                from jnius import autoclass, PythonJavaClass, java_method
                class OnInitListener(PythonJavaClass):
                    __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
                    __javacontext__ = "app"
                    def __init__(self, layout):
                        super().__init__()
                        self.layout = layout
                    @java_method("(I)V")
                    def onInit(self, status):
                        try:
                            TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
                            if status == TextToSpeech.SUCCESS:
                                Clock.schedule_once(lambda dt: self.layout._speak_now(), 0)
                            else:
                                Clock.schedule_once(lambda dt: self.layout.add_message("⚔️ Bingo", "Android text-to-speech could not initialize."), 0)
                        except Exception as exc:
                            Clock.schedule_once(lambda dt: self.layout.add_message("⚔️ Bingo", "Voice setup error: " + str(exc)), 0)
                TTS_LISTENER = OnInitListener(self)
                TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
                TTS_ENGINE = TextToSpeech(android_context, TTS_LISTENER)
                return
            self._speak_now()
        except Exception as exc:
            self.add_message("⚔️ Bingo", "❌ Voice output error: " + repr(exc))

    def _speak_now(self):
        global TTS_ENGINE
        try:
            if TTS_ENGINE is None:
                return
            jnius = __import__("jnius")
            TextToSpeech = jnius.autoclass("android.speech.tts.TextToSpeech")
            HashMap = jnius.autoclass("java.util.HashMap")
            text = self.last_bingo_reply.strip()
            # Android TTS handles long passages poorly; read a practical first section.
            if len(text) > 3500:
                text = text[:3500] + ". The reply is longer, so I read the first part only."
            # Use the user's selected installed Android TTS voice, if available.
            # Voice choices come from the TTS engine installed on this phone; they
            # are not Gemini's proprietary voice catalog.
            try:
                Locale = jnius.autoclass("java.util.Locale")
                Voice = jnius.autoclass("android.speech.tts.Voice")
                voices = TTS_ENGINE.getVoices()
                selected_name = str(VOICE_SETTINGS.get("voice_name", ""))
                selected_voice = None
                if voices is not None and selected_name:
                    for voice in voices.toArray():
                        if str(voice.getName()) == selected_name:
                            selected_voice = voice
                            break
                if selected_voice is not None:
                    TTS_ENGINE.setVoice(selected_voice)
                else:
                    language_result = TTS_ENGINE.setLanguage(Locale.forLanguageTag("en-IN"))
                    if int(language_result) < -1:
                        TTS_ENGINE.setLanguage(Locale.forLanguageTag("en-US"))
                TTS_ENGINE.setSpeechRate(float(VOICE_SETTINGS.get("rate", 0.95)))
                TTS_ENGINE.setPitch(float(VOICE_SETTINGS.get("pitch", 1.0)))
            except Exception:
                try:
                    Locale = jnius.autoclass("java.util.Locale")
                    TTS_ENGINE.setLanguage(Locale.forLanguageTag("en-IN"))
                    TTS_ENGINE.setSpeechRate(float(VOICE_SETTINGS.get("rate", 0.95)))
                    TTS_ENGINE.setPitch(float(VOICE_SETTINGS.get("pitch", 1.0)))
                except Exception:
                    pass
            # Pause Android speech recognition before playback. Leaving the recognizer
            # running while TTS speaks can trigger feedback, false barge-in, and repeated
            # recognizer start/stop tones. Android's public SpeechRecognizer API does not
            # expose a universal way to mute its own start tone.
            if self.continuous_listening:
                self.voice_busy = True
                self._stop_speech_recognizer_ui()

            # Use the String, int, HashMap overload supported by this Android TTS API.
            # A fresh utterance replaces any old spoken reply instead of overlapping it.
            self.tts_speaking = True
            TTS_ENGINE.speak(text, TextToSpeech.QUEUE_FLUSH, HashMap())
            # Estimate the end of playback so later room sounds are not mistaken
            # for an interruption. Actual timing varies with the installed TTS voice.
            estimated_seconds = max(2.0, min(60.0, len(text) / 10.0 + 1.0))
            Clock.schedule_once(lambda dt: self._mark_tts_finished(), estimated_seconds)
            # Keep recognition paused until playback is expected to finish, then start
            # one fresh listening session. This avoids listening to Bingo's own voice.
            # Trade-off: speaking over Bingo will not interrupt playback in this mode.
            if self.continuous_listening:
                Clock.schedule_once(
                    lambda dt: self._resume_continuous_listening(),
                    estimated_seconds + 0.35,
                )
        except Exception as exc:
            self.add_message("⚔️ Bingo", "❌ Could not speak the reply: " + repr(exc))

    def voice_options_button(self, instance):
        """Let the user choose any voice installed in Android's TTS engine."""
        global TTS_ENGINE, TTS_LISTENER, android_context
        if not ANDROID_AVAILABLE or android_context is None:
            self.add_message("⚔️ Bingo", "Voice options are available in the Android APK.")
            return
        if TTS_ENGINE is not None:
            self._show_voice_options()
            return
        try:
            from jnius import autoclass, PythonJavaClass, java_method
            layout = self
            class VoiceInitListener(PythonJavaClass):
                __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
                __javacontext__ = "app"
                def __init__(self):
                    super().__init__()
                @java_method("(I)V")
                def onInit(self, status):
                    TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
                    if status == TextToSpeech.SUCCESS:
                        Clock.schedule_once(lambda dt: layout._show_voice_options(), 0)
                    else:
                        Clock.schedule_once(lambda dt: layout.add_message("⚔️ Bingo", "Android text-to-speech could not initialize."), 0)
            TTS_LISTENER = VoiceInitListener()
            TTS_ENGINE = autoclass("android.speech.tts.TextToSpeech")(android_context, TTS_LISTENER)
        except Exception as exc:
            self.add_message("⚔️ Bingo", "Could not load voice options: " + str(exc))

    def _show_voice_options(self):
        global TTS_ENGINE
        if TTS_ENGINE is None:
            self.add_message("⚔️ Bingo", "Text-to-speech is still starting. Please try again.")
            return
        try:
            voices = TTS_ENGINE.getVoices()
            voice_items = [] if voices is None else list(voices.toArray())
            # Prefer English voices, but show other installed voices too.
            voice_items.sort(key=lambda v: (0 if str(v.getLocale().getLanguage()).lower() == "en" else 1,
                                            str(v.getLocale().toString()), str(v.getName())))
            if not voice_items:
                self.add_message("⚔️ Bingo", "No selectable voices were returned by Android TTS. Check your phone's Text-to-speech settings.")
                return

            content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
            selected_name = str(VOICE_SETTINGS.get("voice_name", ""))
            current_text = "Current voice: Android default" if not selected_name else "Current voice: " + selected_name
            current = Label(text=current_text, size_hint_y=None, height=dp(34), halign="left", valign="middle")
            current.bind(size=lambda obj, value: setattr(obj, "text_size", value))
            content.add_widget(current)
            voice_scroll = ScrollView(do_scroll_x=False, size_hint=(1, 1))
            voice_list = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
            voice_list.bind(minimum_height=voice_list.setter("height"))
            popup = Popup(title="Bingo Voice Studio", content=content, size_hint=(0.94, 0.88))

            def select_voice(voice, *_):
                try:
                    TTS_ENGINE.stop()
                    TTS_ENGINE.setVoice(voice)
                    VOICE_SETTINGS["voice_name"] = str(voice.getName())
                    save_json(VOICE_SETTINGS_FILE, VOICE_SETTINGS)
                    current.text = "Selected: " + str(voice.getName()) + " (" + str(voice.getLocale().toString()) + ")"
                    # Preview is optional and deliberately short.
                    from jnius import autoclass
                    TTS_ENGINE.setSpeechRate(float(VOICE_SETTINGS.get("rate", 0.95)))
                    TTS_ENGINE.setPitch(float(VOICE_SETTINGS.get("pitch", 1.0)))
                    TTS_ENGINE.speak("Hello, I'm Bingo.", autoclass("android.speech.tts.TextToSpeech").QUEUE_FLUSH, None)
                except Exception as exc:
                    self.add_message("⚔️ Bingo", "Could not select this voice: " + str(exc))

            for voice in voice_items:
                locale_name = str(voice.getLocale().toString())
                voice_name = str(voice.getName())
                network = " · online" if bool(voice.isNetworkConnectionRequired()) else " · offline"
                label = voice_name + "\n" + locale_name + network
                button = Button(text=label, size_hint_y=None, height=dp(58), halign="left", font_size="12sp")
                button.bind(on_press=lambda btn, v=voice: select_voice(v))
                voice_list.add_widget(button)
            voice_scroll.add_widget(voice_list)
            content.add_widget(voice_scroll)

            # Naturalness controls: modest ranges avoid extreme, robotic settings.
            rate_title = Label(text="Speaking speed: %.2fx" % float(VOICE_SETTINGS.get("rate", 0.95)), size_hint_y=None, height=dp(24))
            rate_slider = Slider(min=0.75, max=1.25, value=float(VOICE_SETTINGS.get("rate", 0.95)), size_hint_y=None, height=dp(32))
            rate_slider.bind(value=lambda _s, value: setattr(rate_title, "text", "Speaking speed: %.2fx" % value))
            pitch_title = Label(text="Pitch: %.2f" % float(VOICE_SETTINGS.get("pitch", 1.0)), size_hint_y=None, height=dp(24))
            pitch_slider = Slider(min=0.8, max=1.2, value=float(VOICE_SETTINGS.get("pitch", 1.0)), size_hint_y=None, height=dp(32))
            pitch_slider.bind(value=lambda _s, value: setattr(pitch_title, "text", "Pitch: %.2f" % value))
            content.add_widget(rate_title)
            content.add_widget(rate_slider)
            content.add_widget(pitch_title)
            content.add_widget(pitch_slider)
            footer = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
            save_btn = Button(text="SAVE VOICE SETTINGS")
            close_btn = Button(text="CLOSE")
            footer.add_widget(save_btn)
            footer.add_widget(close_btn)
            content.add_widget(footer)

            def save_voice_settings(*_):
                VOICE_SETTINGS["rate"] = float(rate_slider.value)
                VOICE_SETTINGS["pitch"] = float(pitch_slider.value)
                save_json(VOICE_SETTINGS_FILE, VOICE_SETTINGS)
                try:
                    TTS_ENGINE.setSpeechRate(VOICE_SETTINGS["rate"])
                    TTS_ENGINE.setPitch(VOICE_SETTINGS["pitch"])
                except Exception:
                    pass
                self.add_message("⚔️ Bingo", "✅ Voice settings saved. The selected voice and speaking style will be used for future replies.")
                popup.dismiss()
            save_btn.bind(on_press=save_voice_settings)
            close_btn.bind(on_press=popup.dismiss)
            popup.open()
        except Exception as exc:
            self.add_message("⚔️ Bingo", "Could not open voice options: " + repr(exc))

    def toggle_continuous_listening(self, instance):
        """Start continuous recognition; Android SpeechRecognizer setup runs on UI thread."""
        if self.continuous_listening:
            self.stop_continuous_listening(instance)
            return
        if not ANDROID_AVAILABLE or android_context is None:
            self.add_message("⚔️ Bingo", "Continuous listening requires the Android app.")
            return
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            activity.requestPermissions(["android.permission.RECORD_AUDIO"], 9022)
            SpeechRecognizer = autoclass("android.speech.SpeechRecognizer")
            if not SpeechRecognizer.isRecognitionAvailable(activity):
                self.add_message("⚔️ Bingo", "Speech recognition is unavailable. Install or enable Google's speech recognition service, then try again.")
                return
            self.continuous_listening = True
            # Give Android a moment to display/resolve the runtime permission prompt.
            Clock.schedule_once(lambda dt: self._create_speech_recognizer_ui(), 1.0)
        except Exception as exc:
            self.continuous_listening = False
            self.add_message("⚔️ Bingo", "Could not prepare microphone: " + repr(exc) + ". Check microphone permission and the build permission settings.")

    @android_ui_thread
    def _create_speech_recognizer_ui(self):
        """Create/configure SpeechRecognizer on Android's actual application UI thread."""
        global SPEECH_RECOGNIZER, SPEECH_LISTENER
        if not self.continuous_listening:
            return
        try:
            from jnius import autoclass, PythonJavaClass, java_method
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            if SPEECH_RECOGNIZER is None:
                layout = self
                class Listener(PythonJavaClass):
                    __javainterfaces__ = ["android/speech/RecognitionListener"]
                    __javacontext__ = "app"
                    def __init__(self):
                        super().__init__()
                    @java_method("(Landroid/os/Bundle;)V")
                    def onReadyForSpeech(self, params):
                        pass
                    @java_method("()V")
                    def onBeginningOfSpeech(self):
                        # Barge-in: when the user starts talking during Bingo's reply,
                        # stop TTS immediately. Android may occasionally mistake speaker
                        # audio for speech; this is a best-effort native recognizer behavior.
                        if layout.tts_speaking:
                            Clock.schedule_once(lambda dt: layout._interrupt_tts_for_user(), 0)
                    @java_method("(F)V")
                    def onRmsChanged(self, rmsdB):
                        pass
                    @java_method("([B)V")
                    def onBufferReceived(self, buffer):
                        pass
                    @java_method("()V")
                    def onEndOfSpeech(self):
                        pass
                    @java_method("(I)V")
                    def onError(self, error):
                        Clock.schedule_once(lambda dt: layout._speech_error(error), 0)
                    @java_method("(Landroid/os/Bundle;)V")
                    def onResults(self, results):
                        try:
                            arr = results.getStringArrayList("results_recognition")
                            phrase = str(arr.get(0)) if arr is not None and arr.size() > 0 else ""
                            Clock.schedule_once(lambda dt: layout._on_recognized_phrase(phrase), 0)
                        except Exception as exc:
                            Clock.schedule_once(lambda dt: layout.add_message("⚔️ Bingo", "Speech result error: " + str(exc)), 0)
                    @java_method("(Landroid/os/Bundle;)V")
                    def onPartialResults(self, partialResults):
                        pass
                    @java_method("(ILandroid/os/Bundle;)V")
                    def onEvent(self, eventType, params):
                        pass
                SPEECH_LISTENER = Listener()
                SPEECH_RECOGNIZER = autoclass("android.speech.SpeechRecognizer").createSpeechRecognizer(activity)
                SPEECH_RECOGNIZER.setRecognitionListener(SPEECH_LISTENER)
            Clock.schedule_once(lambda dt: self._start_speech_recognition(), 0.2)
        except Exception as exc:
            self.continuous_listening = False
            error_text = repr(exc)
            Clock.schedule_once(lambda dt, msg=error_text: self.add_message("⚔️ Bingo", "Could not start microphone: " + msg), 0)

    def _start_speech_recognition(self):
        # Schedule Android API call on Android UI thread; don't call from Kivy's thread.
        self._start_speech_recognition_ui()

    @android_ui_thread
    def _start_speech_recognition_ui(self):
        # Android's recognition service may emit a beep each time a new listening
        # session starts. The public SpeechRecognizer API has no cross-device mute
        # flag for that tone; avoid duplicate starts wherever possible.
        global SPEECH_RECOGNIZER
        if not self.continuous_listening or SPEECH_RECOGNIZER is None:
            return
        try:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            RecognizerIntent = autoclass("android.speech.RecognizerIntent")
            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-IN")
            intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, True)
            intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
            SPEECH_RECOGNIZER.startListening(intent)
        except Exception as exc:
            error_text = repr(exc)
            Clock.schedule_once(lambda dt, msg=error_text: self.add_message("⚔️ Bingo", "Microphone listening error: " + msg), 0)

    def _on_recognized_phrase(self, phrase):
        phrase = (phrase or "").strip()
        if not self.continuous_listening:
            return
        if not phrase:
            Clock.schedule_once(lambda dt: self._start_speech_recognition(), 0.5)
            return
        self.voice_busy = True
        self.add_message("Abdul 🎙️", phrase)
        quick = command_response(phrase)
        if quick is not None:
            self.add_message("⚔️ Bingo", quick)
            self.last_bingo_reply = quick
            self.speak_last_button(None)
            return
        threading.Thread(target=self._ask_voice_worker, args=(phrase,), daemon=True).start()

    def _ask_voice_worker(self, message):
        answer = ask_gemini(message)
        suggestion = suggest_memory_from_message(message)
        if suggestion:
            answer += "\n\n🧠 Memory suggestion (not saved): \"" + suggestion + "\"\nSay or type 'memory suggestions', then 'approve memory 1' or 'reject memory 1'."
        self.add_message("⚔️ Bingo", answer)
        self._streaming_bubble = None
        self.last_bingo_reply = str(answer)
        Clock.schedule_once(lambda dt: self._speak_voice_answer(), 0)

    def _speak_voice_answer(self):
        self.voice_busy = True
        self.speak_last_button(None)
        # Recognition is paused by _speak_now and resumes after the spoken reply.

    def _mark_tts_finished(self):
        self.tts_speaking = False

    def _interrupt_tts_for_user(self):
        """Stop Bingo's current spoken reply when recognition detects speech."""
        global TTS_ENGINE
        if not self.continuous_listening or not self.tts_speaking:
            return
        try:
            if TTS_ENGINE is not None:
                TTS_ENGINE.stop()
        except Exception:
            pass
        self.tts_speaking = False
        # Let the current recognition session finish and deliver the user's words.
        self.voice_busy = False

    def _resume_continuous_listening(self):
        if self.continuous_listening:
            self.voice_busy = False
            self.tts_speaking = False
            self._start_speech_recognition()

    def _speech_error(self, error):
        # Android reports a few normal transient errors when no speech is detected.
        if self.continuous_listening and not self.voice_busy:
            Clock.schedule_once(lambda dt: self._start_speech_recognition(), 0.8)

    def stop_continuous_listening(self, instance):
        was_listening = self.continuous_listening
        self.continuous_listening = False
        self.voice_busy = False
        self.tts_speaking = False
        self._stop_speech_recognizer_ui()
        if hasattr(self, "live_button"):
            self.live_button.text = "●  LIVE"
        try:
            if TTS_ENGINE is not None:
                TTS_ENGINE.stop()
        except Exception:
            pass

    @android_ui_thread
    def _stop_speech_recognizer_ui(self):
        global SPEECH_RECOGNIZER
        try:
            if SPEECH_RECOGNIZER is not None:
                SPEECH_RECOGNIZER.stopListening()
                SPEECH_RECOGNIZER.cancel()
        except Exception:
            pass

    def send_message(self, instance):
        message = self.message_box.text.strip()
        if not message:
            return
        self.message_box.text = ""
        self.add_message("Abdul", message)
        quick = command_response(message)
        if quick is not None:
            self.add_message("⚔️ Bingo", quick)
            self._streaming_bubble = None
            return
        self._streaming_bubble = self._create_message_bubble("⚔️ Bingo", "⏳ Thinking...")
        threading.Thread(target=self._ask_worker, args=(message,), daemon=True).start()

    def _ask_worker(self, message):
        # Throttle UI redraws: updating a long Kivy chat label for every tiny
        # stream event can itself cause lag on Android. Keep the latest text and
        # refresh the screen at most about 8 times per second.
        last_ui_update = [0.0]
        latest_text = [""]
        def on_chunk(text):
            latest_text[0] = text
            now = time.monotonic()
            if now - last_ui_update[0] >= 0.12:
                last_ui_update[0] = now
                self.update_streaming_reply(text)
        answer = ask_gemini(message, on_chunk=on_chunk)
        suggestion = suggest_memory_from_message(message)
        if suggestion:
            answer += "\n\n🧠 Memory suggestion (not saved): \"" + suggestion + "\"\nType 'memory suggestions', then 'approve memory 1' or 'reject memory 1'."
        self.update_streaming_reply(answer)
        self._streaming_bubble = None
        # Speak replies automatically; in a voice session, resume listening after speech completes.
        if ANDROID_AVAILABLE:
            if self.continuous_listening:
                Clock.schedule_once(lambda dt: self._speak_voice_answer(), 0.15)
            elif self.auto_speak:
                Clock.schedule_once(lambda dt: self.speak_last_button(None), 0.15)

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
                if self.api_key_button_widget is not None:
                    try:
                        self.composer_row.remove_widget(self.api_key_button_widget)
                    except Exception:
                        pass
                    self.api_key_button_widget = None
                self.add_message("⚔️ Bingo", "✅ API key saved securely. The API KEY button is now hidden; use ＋ if you need to change it later.")
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
        # Do not start the microphone on launch. The user enters Live mode explicitly.

    def _start_hands_free_if_available(self):
        if APP_INSTANCE and ANDROID_AVAILABLE and not APP_INSTANCE.continuous_listening:
            APP_INSTANCE.toggle_continuous_listening(None)

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
