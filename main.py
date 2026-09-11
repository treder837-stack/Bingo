from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView

from jnius import autoclass, PythonJavaClass, java_method
from android.runnable import run_on_ui_thread
from android.permissions import request_permissions, Permission

from google import genai
import json
import os
import re
import threading
from datetime import datetime, date


# =========================================================
# ⚔️ BINGO — SOLO SYSTEM v4
# =========================================================

PLAYER_NAME = "Abdul"
ASSISTANT_NAME = "Bingo"


# =========================================================
# 🔑 GEMINI API
# =========================================================

# IMPORTANT:
# Put your NEW Gemini API key here.
#
# Example:
# API_KEY = ""
#
# NEVER send your API key to anyone.

API_KEY = ""

# Current Gemini model
MODEL = "gemini-3.7-flash"


# =========================================================
# 💾 FILES
# =========================================================

MEMORY_FILE = "bingo_memory.json"
PROFILE_FILE = "profile.json"
SYSTEM_FILE = "system.json"


# =========================================================
# 🤖 CONNECT TO GEMINI
# =========================================================

client = None

if API_KEY.strip():

    try:
        client = genai.Client(
            api_key=API_KEY
        )

        print()
        print("🧠 Gemini client created successfully.")
        print()

    except Exception as error:

        print()
        print("❌ GEMINI CONNECTION ERROR")
        print("------------------------------")
        print(error)
        print("------------------------------")
        print()


# =========================================================
# 💾 JSON FUNCTIONS
# =========================================================

def load_json(filename, default):

    if not os.path.exists(filename):

        return default

    try:

        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        return data

    except Exception as error:

        print()
        print(
            f"⚠️ Could not load {filename}."
        )

        print(
            "Using default data."
        )

        print(error)
        print()

        return default


def save_json(filename, data):

    try:

        with open(
            filename,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2
            )

    except Exception as error:

        print()
        print(
            f"❌ Could not save {filename}:"
        )

        print(error)
        print()


# =========================================================
# 👤 LOAD MEMORY
# =========================================================

memory = load_json(
    MEMORY_FILE,
    []
)

if not isinstance(memory, list):

    memory = []


# =========================================================
# 👤 LOAD PROFILE
# =========================================================

profile = load_json(
    PROFILE_FILE,
    {}
)

if not isinstance(profile, dict):

    profile = {}


# =========================================================
# ⚔️ DEFAULT SYSTEM
# =========================================================

default_system = {

    "level": 1,

    "exp": 0,

    "exp_required": 100,

    "streak": 0,

    "quests_completed": 0,

    "learning_completed": False,

    "training_completed": False,

    "last_active_date": "",

    "today": ""

}


# =========================================================
# ⚔️ LOAD SYSTEM
# =========================================================

loaded_system = load_json(
    SYSTEM_FILE,
    {}
)

system = default_system.copy()

if isinstance(loaded_system, dict):

    system.update(
        loaded_system
    )


# =========================================================
# 🛡️ REPAIR SYSTEM DATA
# =========================================================

if not isinstance(
    system.get("level"),
    int
):

    system["level"] = 1


if not isinstance(
    system.get("exp"),
    int
):

    system["exp"] = 0


if not isinstance(
    system.get("exp_required"),
    int
):

    system["exp_required"] = 100


if not isinstance(
    system.get("streak"),
    int
):

    system["streak"] = 0


if not isinstance(
    system.get("quests_completed"),
    int
):

    system["quests_completed"] = 0


# =========================================================
# 📅 TODAY
# =========================================================

today = datetime.now()

today_date = today.strftime(
    "%Y-%m-%d"
)

day_name = today.strftime(
    "%A"
)


# =========================================================
# 📚 WEEKLY LEARNING
# =========================================================

DEFAULT_LEARNING = {

    "Monday":
        "Medicines",

    "Tuesday":
        "BMG & VIFTG",

    "Wednesday":
        "Gunsmithing & Blacksmithing",

    "Thursday":
        "Programming & Mechanical Engineering",

    "Friday":
        "AI + Robots & Cognitive Robots",

    "Saturday":
        "Hacking",

    "Sunday":
        "Mathematics"

}


# =========================================================
# ⚔️ WEEKLY TRAINING
# =========================================================

DEFAULT_TRAINING = {

    "Monday":
        "Boxing",

    "Tuesday":
        "Muay Thai",

    "Wednesday":
        "Jujutsu",

    "Thursday":
        "Jeet Kune Do",

    "Friday":
        "Taekwondo",

    "Saturday":
        "Kenjutsu + Gun Shooting",

    "Sunday":
        "Wrestling"

}


# =========================================================
# 👤 USER SCHEDULE
# =========================================================

learning_schedule = profile.get(
    "learning",
    DEFAULT_LEARNING
)

training_schedule = profile.get(
    "training",
    DEFAULT_TRAINING
)


if not isinstance(
    learning_schedule,
    dict
):

    learning_schedule = DEFAULT_LEARNING


if not isinstance(
    training_schedule,
    dict
):

    training_schedule = DEFAULT_TRAINING


# =========================================================
# 📚 TODAY'S LEARNING
# =========================================================

learning_today = learning_schedule.get(
    day_name,
    DEFAULT_LEARNING.get(
        day_name,
        "No learning quest"
    )
)


# =========================================================
# ⚔️ TODAY'S TRAINING
# =========================================================

training_today = training_schedule.get(
    day_name,
    DEFAULT_TRAINING.get(
        day_name,
        "No training quest"
    )
)


# =========================================================
# 🔄 RESET DAILY QUESTS
# =========================================================

if system.get("today") != today_date:

    system["learning_completed"] = False

    system["training_completed"] = False

    system["today"] = today_date

    save_json(
        SYSTEM_FILE,
        system
    )


# =========================================================
# 🧠 BINGO SYSTEM INSTRUCTION
# =========================================================

def get_system_instruction():

    return f"""

You are Bingo, Abdul's personal AI assistant.

Your personality:

- intelligent
- calm
- friendly
- motivating
- honest
- practical
- patient
- explains difficult subjects step by step
- never pretends to know something you don't know

You are part of Abdul's personal
Solo-Leveling-inspired progress system.

PLAYER:
Name: {PLAYER_NAME}

ASSISTANT:
Name: {ASSISTANT_NAME}

TODAY:
{day_name}

TODAY'S LEARNING:
{learning_today}

TODAY'S TRAINING:
{training_today}

PLAYER SYSTEM:

{json.dumps(
    system,
    ensure_ascii=False,
    indent=2
)}

PLAYER PROFILE:

{json.dumps(
    profile,
    ensure_ascii=False,
    indent=2
)}

IMPORTANT SAFETY RULES:

Medicine:
Give educational information.
Do not diagnose serious conditions.
Encourage professional medical care when appropriate.

Cybersecurity:
Teach defensive and ethical cybersecurity.
Do not provide instructions for unauthorized access,
credential theft, malware, destructive activity,
or bypassing security.

Weapons:
Provide safe, high-level educational information such as
history, physics, engineering principles, safety,
and legal/ethical context.

Do not provide instructions that enable construction,
modification, or harmful use of weapons.

Martial arts:
Focus on fitness, technique concepts,
discipline, safety, and training structure.

When Abdul asks about his schedule,
use the schedule above.

When Abdul asks about his level, EXP, quests,
streak, or progress,
use the PLAYER SYSTEM above.

You are Bingo, not an anime character.

You may use a Solo-Leveling-inspired style
for quests, EXP, levels, and motivation.

"""


# =========================================================
# 📊 STATUS
# =========================================================

def show_status():

    print()

    print(
        "╔══════════════════════════════════════╗"
    )

    print(
        "║          ⚔️ BINGO SYSTEM             ║"
    )

    print(
        "╠══════════════════════════════════════╣"
    )

    print(
        f"║ 👤 PLAYER : {PLAYER_NAME:<23}║"
    )

    print(
        f"║ ⚡ LEVEL  : {system['level']:<23}║"
    )

    print(
        f"║ ⭐ EXP    : "
        f"{system['exp']} / "
        f"{system['exp_required']:<17}║"
    )

    print(
        f"║ 🔥 STREAK : "
        f"{system['streak']} days"
        f"{' ':<17}║"
    )

    print(
        f"║ 🎯 QUESTS : "
        f"{system['quests_completed']:<23}║"
    )

    print(
        "╠══════════════════════════════════════╣"
    )

    learning_mark = (
        "✅"
        if system["learning_completed"]
        else "⬜"
    )

    training_mark = (
        "✅"
        if system["training_completed"]
        else "⬜"
    )

    print(
        f"║ {learning_mark} Learning quest              ║"
    )

    print(
        f"║ {training_mark} Training quest              ║"
    )

    print(
        "╚══════════════════════════════════════╝"
    )

    print()


# =========================================================
# 🎯 TODAY'S QUESTS
# =========================================================

def show_quests():

    learning_mark = (
        "✅"
        if system["learning_completed"]
        else "⬜"
    )

    training_mark = (
        "✅"
        if system["training_completed"]
        else "⬜"
    )

    print()

    print(
        "╔══════════════════════════════════════╗"
    )

    print(
        "║          🎯 DAILY QUEST              ║"
    )

    print(
        "╠══════════════════════════════════════╣"
    )

    print(
        f"║ 📅 {day_name:<31}║"
    )

    print(
        "║                                      ║"
    )

    print(
        f"║ {learning_mark} 📚 LEARNING                    ║"
    )

    print(
        f"║    {learning_today:<32}║"
    )

    print(
        "║                                      ║"
    )

    print(
        f"║ {training_mark} ⚔️ TRAINING                    ║"
    )

    print(
        f"║    {training_today:<32}║"
    )

    print(
        "║                                      ║"
    )

    print(
        "║ 🎁 REWARDS                           ║"
    )

    print(
        "║    Learning  +50 EXP                 ║"
    )

    print(
        "║    Training  +50 EXP                 ║"
    )

    print(
        "║    Both       +100 EXP               ║"
    )

    print(
        "╚══════════════════════════════════════╝"
    )

    print()


# =========================================================
# ⭐ ADD EXP
# =========================================================

def add_exp(amount):

    old_level = system["level"]

    system["exp"] += amount


    while system["exp"] >= system["exp_required"]:

        system["exp"] -= system["exp_required"]

        system["level"] += 1

        system["exp_required"] = max(
            1,
            int(
                system["exp_required"] * 1.5
            )
        )


    save_json(
        SYSTEM_FILE,
        system
    )


    if system["level"] > old_level:

        print()

        print(
            "╔══════════════════════════════════════╗"
        )

        print(
            "║           ⚡ LEVEL UP! ⚡             ║"
        )

        print(
            "╠══════════════════════════════════════╣"
        )

        print(
            f"║        LEVEL {system['level']:<21}║"
        )

        print(
            "║                                      ║"
        )

        print(
            "║   🔥 Your power is increasing.       ║"
        )

        print(
            "║   🧠 Knowledge is increasing.        ║"
        )

        print(
            "║   💪 Discipline is increasing.       ║"
        )

        print(
            "╚══════════════════════════════════════╝"
        )

        print()


# =========================================================
# 🔥 UPDATE STREAK
# =========================================================

def update_streak():

    last_date = system.get(
        "last_active_date",
        ""
    )


    if last_date == today_date:

        return


    if last_date == "":

        system["streak"] = 1

    else:

        try:

            last = datetime.strptime(
                last_date,
                "%Y-%m-%d"
            ).date()

            current = date.today()

            difference = (
                current - last
            ).days


            if difference == 1:

                system["streak"] += 1

            elif difference > 1:

                system["streak"] = 1

        except Exception:

            system["streak"] = 1


    system["last_active_date"] = today_date

    save_json(
        SYSTEM_FILE,
        system
    )


# =========================================================
# 📚 COMPLETE LEARNING
# =========================================================

def complete_learning():

    if system["learning_completed"]:

        print()

        print(
            "Bingo: Your learning quest "
            "is already completed today. ✅"
        )

        print()

        return


    system["learning_completed"] = True

    system["quests_completed"] += 1

    update_streak()

    add_exp(50)


    print()

    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    print(
        "📚 LEARNING QUEST COMPLETE!"
    )

    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    print(
        f"📖 Subject: {learning_today}"
    )

    print(
        "✨ +50 EXP"
    )

    print(
        f"🔥 Streak: {system['streak']} days"
    )

    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    print()


# =========================================================
# ⚔️ COMPLETE TRAINING
# =========================================================

def complete_training():

    if system["training_completed"]:

        print()

        print(
            "Bingo: Your training quest "
            "is already completed today. ✅"
        )

        print()

        return


    system["training_completed"] = True

    system["quests_completed"] += 1

    update_streak()

    add_exp(50)


    print()

    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    print(
        "⚔️ TRAINING QUEST COMPLETE!"
    )

    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    print(
        f"🥋 Training: {training_today}"
    )

    print(
        "✨ +50 EXP"
    )

    print(
        f"🔥 Streak: {system['streak']} days"
    )

    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    print()


# =========================================================
# 🎯 COMPLETE QUEST
# =========================================================

def complete_quest():

    print()

    print(
        "🎯 QUEST COMPLETION"
    )

    print()

    print(
        "1. 📚 Complete Learning"
    )

    print(
        "2. ⚔️ Complete Training"
    )

    print(
        "3. 🌟 Complete Both"
    )

    print()


    choice = input(
        "Abdul: "
    ).strip()


    if choice == "1":

        complete_learning()


    elif choice == "2":

        complete_training()


    elif choice == "3":

        complete_learning()

        complete_training()


    else:

        print()

        print(
            "Bingo: Invalid selection."
        )

        print()


# =========================================================
# ⏰ REMINDER
# =========================================================

def reminder_message(message):

    print()
    print()

    print(
        "╔══════════════════════════════════════╗"
    )

    print(
        "║            🔔 BINGO                 ║"
    )

    print(
        "╠══════════════════════════════════════╣"
    )

    print(
        f"║ {message:<36}║"
    )

    print(
        "╚══════════════════════════════════════╝"
    )

    print()


def set_reminder(minutes, message):

    timer = threading.Timer(
        minutes * 60,
        reminder_message,
        args=(message,)
    )

    timer.daemon = True

    timer.start()


    print()

    print(
        f"🔔 Bingo: Reminder set for "
        f"{minutes} minute(s)."
    )

    print()


# =========================================================
# 🗣️ REMINDER COMMAND
# =========================================================

def check_reminder_command(message):

    text = message.lower().strip()


    if text == "later":

        set_reminder(
            5,
            "Abdul, your 5-minute reminder is here. ⚔️"
        )

        return True


    pattern = r"remind me in (\d+) minutes?"

    match = re.search(
        pattern,
        text
    )


    if match:

        minutes = int(
            match.group(1)
        )


        if minutes <= 0:

            minutes = 1


        set_reminder(
            minutes,
            "Abdul, your reminder is here. ⚔️"
        )

        return True


    return False


# =========================================================
# 📅 SHOW SCHEDULE
# =========================================================

def show_schedule():

    print()

    print(
        "╔══════════════════════════════════════╗"
    )

    print(
        "║          📅 ABDUL'S SCHEDULE         ║"
    )

    print(
        "╚══════════════════════════════════════╝"
    )


    for day in DEFAULT_LEARNING:

        print()

        print(
            f"📅 {day}"
        )

        print(
            f"   📚 Learning : "
            f"{learning_schedule.get(day, DEFAULT_LEARNING[day])}"
        )

        print(
            f"   ⚔️ Training : "
            f"{training_schedule.get(day, DEFAULT_TRAINING[day])}"
        )


    print()

    print(
        "🍽️ Friday lunch: 2:45 PM"
    )

    print()


# =========================================================
# 🧠 LOCAL COMMANDS
# =========================================================

def local_command(user_message):

    text = user_message.lower().strip()


    # -----------------------------------------
    # STATUS
    # -----------------------------------------

    if text in (
        "status",
        "/status",
        "show status",
        "show my status",
        "my status",
        "player status"
    ):

        show_status()

        return True


    # -----------------------------------------
    # QUEST
    # -----------------------------------------

    if text in (
        "quest",
        "/quest",
        "show quests",
        "show my quests",
        "my quests",
        "today's quests",
        "todays quests"
    ):

        show_quests()

        return True


    # -----------------------------------------
    # TODAY'S LEARNING
    # -----------------------------------------

    if (
        "what am i learning today" in text
        or "what am i learning" in text
        or "today's learning" in text
        or "todays learning" in text
    ):

        print()

        print(
            f"Bingo: Today is {day_name}. 📅"
        )

        print(
            f"Bingo: Your learning quest is "
            f"{learning_today}. 🧠"
        )

        print()

        return True


    # -----------------------------------------
    # TODAY'S TRAINING
    # -----------------------------------------

    if (
        "what is my training today" in text
        or "what am i training today" in text
        or "today's training" in text
        or "todays training" in text
    ):

        print()

        print(
            f"Bingo: Today's training is "
            f"{training_today}. ⚔️"
        )

        print()

        return True


    # -----------------------------------------
    # LEVEL
    # -----------------------------------------

    if (
        "what is my level" in text
        or "what's my level" in text
        or "what is my current level" in text
        or "my level" in text
    ):

        print()

        print(
            f"Bingo: You are LEVEL "
            f"{system['level']} ⚡"
        )

        print(
            f"Bingo: EXP "
            f"{system['exp']} / "
            f"{system['exp_required']} ⭐"
        )

        print()

        return True


    # -----------------------------------------
    # EXP
    # -----------------------------------------

    if (
        "how much exp" in text
        or "how much experience" in text
        or "my exp" in text
        or "my experience" in text
        or "how much xp" in text
        or "my xp" in text
    ):

        print()

        print(
            f"Bingo: You currently have "
            f"{system['exp']} / "
            f"{system['exp_required']} EXP. ⭐"
        )

        print()

        return True


    # -----------------------------------------
    # STREAK
    # -----------------------------------------

    if (
        "my streak" in text
        or "what is my streak" in text
        or "what's my streak" in text
        or "current streak" in text
    ):

        print()

        print(
            f"Bingo: Your current streak is "
            f"{system['streak']} day(s). 🔥"
        )

        print()

        return True


    # -----------------------------------------
    # QUEST PROGRESS
    # -----------------------------------------

    if (
        "quest progress" in text
        or "how are my quests" in text
        or "did i complete my quests" in text
        or "quest status" in text
    ):

        learning = (
            "completed"
            if system["learning_completed"]
            else "not completed"
        )

        training = (
            "completed"
            if system["training_completed"]
            else "not completed"
        )


        print()

        print(
            "Bingo: Today's quest progress:"
        )

        print(
            f"📚 Learning: {learning}"
        )

        print(
            f"⚔️ Training: {training}"
        )

        print()

        return True


    # -----------------------------------------
    # SCHEDULE
    # -----------------------------------------

    if text in (
        "schedule",
        "/schedule",
        "show schedule",
        "show my schedule",
        "my schedule",
        "weekly schedule"
    ):

        show_schedule()

        return True


    # -----------------------------------------
    # NOTHING FOUND
    # -----------------------------------------

    return False


# =========================================================
# 🧠 ASK BINGO AI
# =========================================================

def ask_bingo(user_message):

    global memory


    # -----------------------------------------
    # CHECK API KEY
    # -----------------------------------------

    if (
        not API_KEY.strip()
        or API_KEY == "YOUR_NEW_API_KEY"
    ):

        print()

        print(
            "⚠️ Bingo AI is not connected."
        )

        print()

        print(
            "Local Bingo commands are working."
        )

        print(
            "Add your Gemini API key to API_KEY."
        )

        print()

        return


    # -----------------------------------------
    # CHECK CLIENT
    # -----------------------------------------

    if client is None:

        print()

        print(
            "❌ Bingo could not connect to Gemini."
        )

        print(
            "Check your API key and internet connection."
        )

        print()

        return


    # -----------------------------------------
    # BUILD CONVERSATION
    # -----------------------------------------

    contents = list(memory)

    contents.append(
        {
            "role": "user",
            "parts": [
                {
                    "text": user_message
                }
            ]
        }
    )


    # -----------------------------------------
    # ASK GEMINI
    # -----------------------------------------

    try:

        response = client.models.generate_content(

            model=MODEL,

            contents=contents,

            config={
                "system_instruction":
                    get_system_instruction()
            }

        )


        # -----------------------------------------
        # GET ANSWER
        # -----------------------------------------

        answer = response.text


        if not answer:

            answer = (
                "I received an empty response "
                "from Gemini."
            )


        print()

        print(
            "Bingo:",
            answer
        )

        print()


        # -----------------------------------------
        # SAVE USER MESSAGE
        # -----------------------------------------

        memory.append(

            {
                "role":
                    "user",

                "parts":
                    [
                        {
                            "text":
                                user_message
                        }
                    ]
            }

        )


        # -----------------------------------------
        # SAVE BINGO RESPONSE
        # -----------------------------------------

        memory.append(

            {
                "role":
                    "model",

                "parts":
                    [
                        {
                            "text":
                                answer
                        }
                    ]
            }

        )


        # -----------------------------------------
        # LIMIT MEMORY
        # -----------------------------------------

        if len(memory) > 40:

            memory = memory[-40:]


        # -----------------------------------------
        # SAVE MEMORY
        # -----------------------------------------

        save_json(
            MEMORY_FILE,
            memory
        )


    except Exception as error:

        print()

        print(
            "❌ Bingo encountered an error:"
        )

        print()

        print(
            error
        )

        print()

        print(
            "💡 Check:"
        )

        print(
            "1. Internet connection"
        )

        print(
            "2. Gemini API key"
        )

        print(
            "3. google-genai package"
        )

        print()


# =========================================================
# 💾 SAVE EVERYTHING
# =========================================================

def save_all():

    save_json(
        MEMORY_FILE,
        memory
    )

    save_json(
        SYSTEM_FILE,
        system
    )


# =========================================================
# ⚔️ START BINGO
# =========================================================

print()

print(
    "========================================"
)

print(
    "              ⚔️ BINGO"
)

print(
    "========================================"
)

print()

print(
    "Player    :",
    PLAYER_NAME
)

print(
    "Assistant :",
    ASSISTANT_NAME
)

print()

print(
    "🧠 AI BRAIN :",
    "ONLINE" if client else "OFFLINE"
)

print(
    "💾 MEMORY   : ONLINE"
)

print(
    "👤 PROFILE  : ONLINE"
)

print(
    "⚔️ SYSTEM   : ONLINE"
)

print()


if memory:

    print(
        "💾 Previous conversation memory loaded."
    )

else:

    print(
        "💾 No previous conversation memory found."
    )


if profile:

    print(
        "👤 Abdul's profile loaded."
    )


print(
    "⚔️ Player system loaded."
)

print()

print(
    f"📅 Today: {day_name}"
)

print(
    f"📚 Learning: {learning_today}"
)

print(
    f"⚔️ Training: {training_today}"
)

print()

print(
    "Bingo: Hello Abdul. I'm ready. ⚔️"
)

print()

print(
    "Commands:"
)

print(
    "  /status   → Player status"
)

print(
    "  /quest    → Today's quests"
)

print(
    "  /complete → Complete quests"
)

print(
    "  /schedule → Weekly schedule"
)

print(
    "  later     → Reminder in 5 minutes"
)

print(
    "  remind me in 10 minutes"
)

print(
    "  exit      → Shut down Bingo"
)

print()


def talk_to_bingo(message):
    """
    This is Bingo's Android chat function.
    """

    message = message.strip()

    if not message:
        return

    # Run Bingo's AI in the background
    threading.Thread(
        target=ask_bingo_android,
        args=(message,),
        daemon=True
    ).start()


def ask_bingo_android(message):

    global memory

    # Check local commands first
    if local_command(message):
        return

    # Check reminder commands
    if check_reminder_command(message):
        return

    # Check Gemini
    if not API_KEY.strip():

        update_chat(
            "Bingo: ⚠️ AI is offline. "
            "Add your Gemini API key when building the app."
        )

        return

    if client is None:

        update_chat(
            "Bingo: ❌ I couldn't connect to Gemini."
        )

        return

    contents = list(memory)

    contents.append(
        {
            "role": "user",
            "parts": [
                {
                    "text": message
                }
            ]
        }
    )

    try:

        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config={
                "system_instruction":
                    get_system_instruction()
            }
        )

        answer = response.text

        if not answer:
            answer = "I received an empty response."

        memory.append(
            {
                "role": "user",
                "parts": [
                    {
                        "text": message
                    }
                ]
            }
        )

        memory.append(
            {
                "role": "model",
                "parts": [
                    {
                        "text": answer
                    }
                ]
            }
        )

        if len(memory) > 40:
            memory = memory[-40:]

        save_json(
            MEMORY_FILE,
            memory
        )

        update_chat(
            "Bingo: " + answer
        )

    except Exception as error:

        update_chat(
            "Bingo: ❌ Error: " + str(error)
        )
        class BingoLayout(BoxLayout):

    def __init__(self, **kwargs):

        super().__init__(
            orientation="vertical",
            padding=10,
            spacing=10,
            **kwargs
        )

        # Chat area
        self.chat_label = Label(
            text=(
                "⚔️ BINGO\n\n"
                "Hello Abdul. I'm ready. ⚔️"
            ),
            size_hint_y=None,
            halign="left",
            valign="top"
        )

        self.chat_label.bind(
            texture_size=self.chat_label.setter(
                "size"
            )
        )

        scroll = ScrollView()

        scroll.add_widget(
            self.chat_label
        )

        self.add_widget(scroll)

        # Message box
        self.message_box = TextInput(
            hint_text="Talk to Bingo...",
            multiline=False,
            size_hint_y=None,
            height=55
        )

        self.add_widget(
            self.message_box
        )

        # Send button
        send_button = Button(
            text="⚔️ SEND",
            size_hint_y=None,
            height=55
        )

        send_button.bind(
    on_press=lambda instance: self.update_chat("✅ BUTTON TEST WORKING")
)

        self.add_widget(
            send_button
        )

    def send_message(self, instance):

        message = self.message_box.text.strip()

        if not message:
            return

        self.chat_label.text += (
            "\n\nAbdul: " + message
        )

        self.message_box.text = ""

        talk_to_bingo(message)


    @mainthread
    def update_chat(self, message):

        self.chat_label.text += (
            "\n\n" + message
        )


def update_chat(message):

    if bingo_app:

        bingo_app.root.update_chat(
            message
        )


bingo_app = None


class BingoApp(App):

    def build(self):

        global bingo_app

        bingo_app = self

        return BingoLayout()


if __name__ == "__main__":

    BingoApp().run()
