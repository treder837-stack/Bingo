from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView

from google import genai

import json
import os
import re
import threading
from datetime import datetime, date


# =========================================================
# ⚔️ BINGO — ANDROID APP
# =========================================================

PLAYER_NAME = "Abdul"
ASSISTANT_NAME = "Bingo"


# =========================================================
# 🔑 GEMINI
# =========================================================

# Keep this empty for now.
# Do NOT put your API key in GitHub.
API_KEY = ""

MODEL = "gemini-3.7-flash"


# =========================================================
# 💾 FILES
# =========================================================

MEMORY_FILE = "bingo_memory.json"
PROFILE_FILE = "profile.json"
SYSTEM_FILE = "system.json"


# =========================================================
# 🤖 GEMINI CLIENT
# =========================================================

client = None

if API_KEY.strip():

    try:

        client = genai.Client(
            api_key=API_KEY
        )

    except Exception:

        client = None


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

            return json.load(file)

    except Exception:

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

    except Exception:

        pass


# =========================================================
# 👤 MEMORY
# =========================================================

memory = load_json(
    MEMORY_FILE,
    []
)

if not isinstance(memory, list):
    memory = []


# =========================================================
# 👤 PROFILE
# =========================================================

profile = load_json(
    PROFILE_FILE,
    {}
)

if not isinstance(profile, dict):
    profile = {}


# =========================================================
# ⚔️ SYSTEM
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
# 🛡️ REPAIR SYSTEM
# =========================================================

if not isinstance(system.get("level"), int):
    system["level"] = 1

if not isinstance(system.get("exp"), int):
    system["exp"] = 0

if not isinstance(system.get("exp_required"), int):
    system["exp_required"] = 100

if not isinstance(system.get("streak"), int):
    system["streak"] = 0

if not isinstance(system.get("quests_completed"), int):
    system["quests_completed"] = 0


# =========================================================
# 📅 DATE
# =========================================================

today = datetime.now()

today_date = today.strftime(
    "%Y-%m-%d"
)

day_name = today.strftime(
    "%A"
)


# =========================================================
# 📚 LEARNING
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
# ⚔️ TRAINING
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
# 🔄 DAILY RESET
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

PERSONALITY:

- intelligent
- calm
- friendly
- motivating
- honest
- practical
- patient
- explains difficult subjects step by step
- never pretends to know something you don't know

You are part of Abdul's
Solo-Leveling-inspired progress system.

PLAYER:
{PLAYER_NAME}

ASSISTANT:
{ASSISTANT_NAME}

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

SAFETY:

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
Provide safe, high-level educational information
about history, physics, engineering principles,
safety, and legal/ethical context.

Do not provide instructions that enable construction,
modification, or harmful use of weapons.

Martial arts:
Focus on fitness, technique concepts,
discipline, safety, and training structure.

When Abdul asks about his level, EXP, quests,
streak, or progress, use the PLAYER SYSTEM.

When Abdul asks about his schedule,
use the schedule information above.

You are Bingo.

You may use a Solo-Leveling-inspired style
for quests, EXP, levels, and motivation.

"""


# =========================================================
# 📊 STATUS TEXT
# =========================================================

def status_text():

    learning = (
        "✅"
        if system["learning_completed"]
        else "⬜"
    )

    training = (
        "✅"
        if system["training_completed"]
        else "⬜"
    )

    return (
        "⚔️ BINGO SYSTEM\n\n"
        f"👤 Player: {PLAYER_NAME}\n"
        f"⚡ Level: {system['level']}\n"
        f"⭐ EXP: {system['exp']} / "
        f"{system['exp_required']}\n"
        f"🔥 Streak: {system['streak']} days\n"
        f"🎯 Quests: {system['quests_completed']}\n\n"
        f"{learning} Learning quest\n"
        f"{training} Training quest"
    )


# =========================================================
# 🎯 QUEST TEXT
# =========================================================

def quest_text():

    learning = (
        "✅"
        if system["learning_completed"]
        else "⬜"
    )

    training = (
        "✅"
        if system["training_completed"]
        else "⬜"
    )

    return (
        "🎯 DAILY QUEST\n\n"
        f"📅 {day_name}\n\n"
        f"{learning} 📚 LEARNING\n"
        f"   {learning_today}\n\n"
        f"{training} ⚔️ TRAINING\n"
        f"   {training_today}\n\n"
        "🎁 REWARDS\n"
        "📚 Learning: +50 EXP\n"
        "⚔️ Training: +50 EXP\n"
        "🌟 Both: +100 EXP"
    )


# =========================================================
# 📅 SCHEDULE TEXT
# =========================================================

def schedule_text():

    text = "📅 WEEKLY SCHEDULE\n\n"

    for day in DEFAULT_LEARNING:

        text += (
            f"📅 {day}\n"
            f"📚 {learning_schedule.get(day, DEFAULT_LEARNING[day])}\n"
            f"⚔️ {training_schedule.get(day, DEFAULT_TRAINING[day])}\n\n"
        )

    text += "🍽️ Friday lunch: 2:45 PM"

    return text


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

        return (
            f"⚡ LEVEL UP!\n\n"
            f"New Level: {system['level']}\n"
            "🔥 Power increased.\n"
            "🧠 Knowledge increased.\n"
            "💪 Discipline increased."
        )

    return ""


# =========================================================
# 🔥 STREAK
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

        return (
            "📚 Learning quest is "
            "already completed today. ✅"
        )

    system["learning_completed"] = True

    system["quests_completed"] += 1

    update_streak()

    level_message = add_exp(50)

    message = (
        "📚 LEARNING QUEST COMPLETE!\n\n"
        f"📖 Subject: {learning_today}\n"
        "✨ +50 EXP\n"
        f"🔥 Streak: {system['streak']} days"
    )

    if level_message:

        message += (
            "\n\n" + level_message
        )

    return message


# =========================================================
# ⚔️ COMPLETE TRAINING
# =========================================================

def complete_training():

    if system["training_completed"]:

        return (
            "⚔️ Training quest is "
            "already completed today. ✅"
        )

    system["training_completed"] = True

    system["quests_completed"] += 1

    update_streak()

    level_message = add_exp(50)

    message = (
        "⚔️ TRAINING QUEST COMPLETE!\n\n"
        f"🥋 Training: {training_today}\n"
        "✨ +50 EXP\n"
        f"🔥 Streak: {system['streak']} days"
    )

    if level_message:

        message += (
            "\n\n" + level_message
        )

    return message


# =========================================================
# 🎯 COMPLETE BOTH
# =========================================================

def complete_both():

    first = complete_learning()

    second = complete_training()

    return (
        first
        + "\n\n"
        + second
    )


# =========================================================
# ⏰ REMINDER
# =========================================================

def set_reminder(minutes):

    timer = threading.Timer(
        minutes * 60,
        reminder_callback
    )

    timer.daemon = True

    timer.start()


def reminder_callback():

    update_chat(
        "🔔 Bingo reminder:\n"
        "Abdul, your reminder is here. ⚔️"
    )


# =========================================================
# 🗣️ LOCAL COMMANDS
# =========================================================

def local_command(message):

    text = message.lower().strip()

    # STATUS

    if text in (
        "status",
        "/status",
        "show status",
        "show my status",
        "my status",
        "player status"
    ):

        return status_text()


    # QUESTS

    if text in (
        "quest",
        "/quest",
        "show quests",
        "show my quests",
        "my quests",
        "today's quests",
        "todays quests"
    ):

        return quest_text()


    # LEARNING

    if (
        "what am i learning today" in text
        or "what am i learning" in text
        or "today's learning" in text
        or "todays learning" in text
    ):

        return (
            f"📅 Today is {day_name}.\n\n"
            f"📚 Your learning quest is:\n"
            f"{learning_today}"
        )


    # TRAINING

    if (
        "what is my training today" in text
        or "what am i training today" in text
        or "today's training" in text
        or "todays training" in text
    ):

        return (
            f"📅 Today is {day_name}.\n\n"
            f"⚔️ Your training is:\n"
            f"{training_today}"
        )


    # LEVEL

    if (
        "what is my level" in text
        or "what's my level" in text
        or "what is my current level" in text
        or text == "my level"
    ):

        return (
            f"⚡ Your level is "
            f"{system['level']}.\n\n"
            f"⭐ EXP: "
            f"{system['exp']} / "
            f"{system['exp_required']}"
        )


    # EXP

    if (
        "how much exp" in text
        or "how much experience" in text
        or "my exp" in text
        or "my experience" in text
        or "how much xp" in text
        or "my xp" in text
    ):

        return (
            f"⭐ EXP: "
            f"{system['exp']} / "
            f"{system['exp_required']}"
        )


    # STREAK

    if (
        "my streak" in text
        or "what is my streak" in text
        or "what's my streak" in text
        or "current streak" in text
    ):

        return (
            f"🔥 Your streak is "
            f"{system['streak']} day(s)."
        )


    # QUEST PROGRESS

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

        return (
            "🎯 QUEST PROGRESS\n\n"
            f"📚 Learning: {learning}\n"
            f"⚔️ Training: {training}"
        )


    # SCHEDULE

    if text in (
        "schedule",
        "/schedule",
        "show schedule",
        "show my schedule",
        "my schedule",
        "weekly schedule"
    ):

        return schedule_text()


    # COMPLETE LEARNING

    if text in (
        "complete learning",
        "/complete learning"
    ):

        return complete_learning()


    # COMPLETE TRAINING

    if text in (
        "complete training",
        "/complete training"
    ):

        return complete_training()


    # COMPLETE BOTH

    if text in (
        "complete both",
        "/complete both",
        "complete quests",
        "/complete"
    ):

        return complete_both()


    # REMINDER

    if text == "later":

        set_reminder(5)

        return (
            "🔔 Reminder set for "
            "5 minutes."
        )


    match = re.search(
        r"remind me in (\d+) minutes?",
        text
    )

    if match:

        minutes = int(
            match.group(1)
        )

        if minutes <= 0:
            minutes = 1

        set_reminder(minutes)

        return (
            f"🔔 Reminder set for "
            f"{minutes} minute(s)."
        )


    return None


# =========================================================
# 🧠 ASK BINGO
# =========================================================

def ask_bingo_android(message):

    global memory

    # LOCAL COMMAND

    result = local_command(
        message
    )

    if result is not None:

        update_chat(
            "Bingo: " + result
        )

        return


    # API KEY

    if not API_KEY.strip():

        update_chat(
            "Bingo: ⚠️ AI is offline.\n\n"
            "Local commands are working.\n\n"
            "Gemini API key has not been added yet."
        )

        return


    # CLIENT

    if client is None:

        update_chat(
            "Bingo: ❌ Gemini connection failed.\n\n"
            "Check your API key and internet connection."
        )

        return


    # CONVERSATION

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

            answer = (
                "I received an empty response."
            )


        # SAVE USER

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


        # SAVE BINGO

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


        # LIMIT MEMORY

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
            "Bingo: ❌ Gemini error.\n\n"
            + str(error)
        )


# =========================================================
# 🗣️ TALK TO BINGO
# =========================================================

def talk_to_bingo(message):

    message = message.strip()

    if not message:
        return

    threading.Thread(
        target=ask_bingo_android,
        args=(message,),
        daemon=True
    ).start()


# =========================================================
# 📱 ANDROID UI
# =========================================================

bingo_app = None


class BingoLayout(BoxLayout):

    def __init__(self, **kwargs):

        super().__init__(
            orientation="vertical",
            padding=10,
            spacing=10,
            **kwargs
        )


        # =================================================
        # CHAT
        # =================================================

        self.chat_label = Label(

            text=(
                "⚔️ BINGO\n\n"
                "Hello Abdul.\n"
                "I'm ready. ⚔️\n\n"
                "Try:\n"
                "/status\n"
                "/quest\n"
                "/schedule"
            ),

            size_hint_y=None,

            halign="left",

            valign="top"
        )


        self.chat_label.bind(
            texture_size=
            self.chat_label.setter(
                "size"
            )
        )


        self.scroll = ScrollView()


        self.scroll.add_widget(
            self.chat_label
        )


        self.add_widget(
            self.scroll
        )


        # =================================================
        # MESSAGE INPUT
        # =================================================

        self.message_box = TextInput(

            hint_text=
            "Talk to Bingo...",

            multiline=False,

            size_hint_y=None,

            height=55
        )


        self.message_box.bind(
            on_text_validate=
            self.send_message
        )


        self.add_widget(
            self.message_box
        )


        # =================================================
        # SEND BUTTON
        # =================================================

        send_button = Button(

            text="⚔️ SEND",

            size_hint_y=None,

            height=55
        )


        send_button.bind(
            on_press=
            self.send_message
        )


        self.add_widget(
            send_button
        )


    # =====================================================
    # SEND
    # =====================================================

    def send_message(self, instance):

        message = (
            self.message_box.text.strip()
        )


        if not message:
            return


        self.chat_label.text += (
            "\n\nAbdul: "
            + message
        )


        self.message_box.text = ""


        talk_to_bingo(
            message
        )


        Clock.schedule_once(
            self.scroll_to_bottom,
            0.1
        )


    # =====================================================
    # UPDATE CHAT
    # =====================================================

    @mainthread
    def update_chat(self, message):

        self.chat_label.text += (
            "\n\n" + message
        )


        Clock.schedule_once(
            self.scroll_to_bottom,
            0.1
        )


    # =====================================================
    # SCROLL
    # =====================================================

    def scroll_to_bottom(self, *args):

        self.scroll.scroll_y = 0


# =========================================================
# 📢 GLOBAL UI UPDATE
# =========================================================

def update_chat(message):

    if bingo_app is not None:

        if bingo_app.root is not None:

            bingo_app.root.update_chat(
                message
            )


# =========================================================
# 📱 BINGO APP
# =========================================================

class BingoApp(App):

    def build(self):

        global bingo_app

        bingo_app = self

        return BingoLayout()


# =========================================================
# 🚀 START
# =========================================================

if __name__ == "__main__":

    BingoApp().run()
