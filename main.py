from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

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

API_KEY = ""
MODEL = "gemini-3.6-flash"


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
        client = genai.Client(api_key=API_KEY)
        print("\n🧠 Gemini client created successfully.\n")
    except Exception as error:
        print("\n❌ GEMINI CONNECTION ERROR")
        print("------------------------------")
        print(error)
        print("------------------------------\n")


# =========================================================
# 💾 JSON FUNCTIONS
# =========================================================

def load_json(filename, default):
    if not os.path.exists(filename):
        return default
    try:
        with open(filename, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data
    except Exception as error:
        print(f"\n⚠️ Could not load {filename}. Using default data.")
        print(error)
        print()
        return default


def save_json(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
    except Exception as error:
        print(f"\n❌ Could not save {filename}:")
        print(error)
        print()


# =========================================================
# 👤 LOAD DATA
# =========================================================

memory = load_json(MEMORY_FILE, [])
if not isinstance(memory, list):
    memory = []

profile = load_json(PROFILE_FILE, {})
if not isinstance(profile, dict):
    profile = {}

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

loaded_system = load_json(SYSTEM_FILE, {})
system = default_system.copy()
if isinstance(loaded_system, dict):
    system.update(loaded_system)

# 🛡️ Repair system data types
for key, val in [("level", 1), ("exp", 0), ("exp_required", 100), ("streak", 0), ("quests_completed", 0)]:
    if not isinstance(system.get(key), int):
        system[key] = val


# =========================================================
# 📅 TODAY & SCHEDULES
# =========================================================

today = datetime.now()
today_date = today.strftime("%Y-%m-%d")
day_name = today.strftime("%A")

DEFAULT_LEARNING = {
    "Monday": "Medicines",
    "Tuesday": "BMG & VIFTG",
    "Wednesday": "Gunsmithing & Blacksmithing",
    "Thursday": "Programming & Mechanical Engineering",
    "Friday": "AI + Robots & Cognitive Robots",
    "Saturday": "Hacking",
    "Sunday": "Mathematics"
}

DEFAULT_TRAINING = {
    "Monday": "Boxing",
    "Tuesday": "Muay Thai",
    "Wednesday": "Jujutsu",
    "Thursday": "Jeet Kune Do",
    "Friday": "Taekwondo",
    "Saturday": "Kenjutsu + Gun Shooting",
    "Sunday": "Wrestling"
}

learning_schedule = profile.get("learning", DEFAULT_LEARNING)
training_schedule = profile.get("training", DEFAULT_TRAINING)

if not isinstance(learning_schedule, dict):
    learning_schedule = DEFAULT_LEARNING
if not isinstance(training_schedule, dict):
    training_schedule = DEFAULT_TRAINING

learning_today = learning_schedule.get(day_name, DEFAULT_LEARNING.get(day_name, "No learning quest"))
training_today = training_schedule.get(day_name, DEFAULT_TRAINING.get(day_name, "No training quest"))

if system.get("today") != today_date:
    system["learning_completed"] = False
    system["training_completed"] = False
    system["today"] = today_date
    save_json(SYSTEM_FILE, system)


# =========================================================
# ANDROID VOICE CLASSES
# =========================================================

PythonActivity = autoclass("org.kivy.android.PythonActivity")
Intent = autoclass("android.content.Intent")
RecognizerIntent = autoclass("android.speech.RecognizerIntent")
SpeechRecognizer = autoclass("android.speech.SpeechRecognizer")


class RecognitionListener(PythonJavaClass):
    __javainterfaces__ = ["android/speech/RecognitionListener"]
    __javacontext__ = "app"

    def __init__(self, app):
        super().__init__()
        self.app = app

    @java_method("(Landroid/os/Bundle;)V")
    def onReadyForSpeech(self, params):
        Clock.schedule_once(lambda dt: self.app.set_message("🎤 Listening..."))

    @java_method("()V")
    def onBeginningOfSpeech(self):
        Clock.schedule_once(lambda dt: self.app.set_message("🎤 I'm listening..."))

    @java_method("(F)V")
    def onRmsChanged(self, rmsdB):
        pass

    @java_method("([B)V")
    def onBufferReceived(self, buffer):
        pass

    @java_method("()V")
    def onEndOfSpeech(self):
        Clock.schedule_once(lambda dt: self.app.set_message("⚙️ Processing..."))

    @java_method("(I)V")
    def onError(self, error):
        Clock.schedule_once(lambda dt: self.app.show_voice_error(error))

    @java_method("(Landroid/os/Bundle;)V")
    def onResults(self, results):
        try:
            matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            if matches and matches.size() > 0:
                text = str(matches.get(0))
                Clock.schedule_once(lambda dt: self.app.voice_result(text))
            else:
                Clock.schedule_once(lambda dt: self.app.set_message("❌ I couldn't understand that."))
        except Exception as e:
            Clock.schedule_once(lambda dt: self.app.set_message(f"❌ Result error:\n{e}"))

    @java_method("(Landroid/os/Bundle;)V")
    def onPartialResults(self, results):
        pass

    @java_method("(ILandroid/os/Bundle;)V")
    def onEvent(self, eventType, params):
        pass


# =========================================================
# 📱 BINGO KIVY APP
# =========================================================

class BingoApp(App):

    def build(self):
        self.layout = BoxLayout(
            orientation="vertical",
            padding=30,
            spacing=20
        )

        self.title_label = Label(
            text="⚔️ BINGO",
            font_size=32
        )

        self.message = Label(
            text="Bingo is ready!",
            font_size=22
        )

        self.button = Button(
            text="🎤 TALK TO BINGO",
            font_size=22
        )

        self.button.bind(on_press=lambda instance: self.set_message("✅ Bingo GUI is working!"))

        self.layout.add_widget(self.title_label)
        self.layout.add_widget(self.message)
        self.layout.add_widget(self.button)

        self.recognizer = None
        self.listener = RecognitionListener(self)

        return self.layout

    @mainthread
    def set_message(self, text):
        self.message.text = text

    def talk(self, instance):
        self.message.text = "🎤 Checking microphone permission..."
        request_permissions(
            [Permission.RECORD_AUDIO],
            self.permission_callback
        )

    def permission_callback(self, permissions, grants):
        if all(grants):
            self.message.text = "🎤 Starting microphone..."
            self.start_speech()
        else:
            self.message.text = (
                "❌ Microphone permission denied.\n\n"
                "Please allow microphone access."
            )

    @run_on_ui_thread
    def start_speech(self):
        try:
            activity = PythonActivity.mActivity

            available = SpeechRecognizer.isRecognitionAvailable(activity)
            if not available:
                Clock.schedule_once(
                    lambda dt: self.set_message("❌ Speech recognition is not available.")
                )
                return

            if self.recognizer is not None:
                try:
                    self.recognizer.destroy()
                except Exception:
                    pass
                self.recognizer = None

            self.recognizer = SpeechRecognizer.createSpeechRecognizer(activity)
            self.recognizer.setRecognitionListener(self.listener)

            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(
                RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
            )
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-IN")
            intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, False)

            self.recognizer.startListening(intent)

        except Exception as e:
            error = str(e)
            Clock.schedule_once(
                lambda dt: self.set_message(f"❌ Speech error:\n{error}")
            )

    @mainthread
    def voice_result(self, text):
        self.message.text = (
            f"👤 You said:\n\n{text}\n\n🤖 Bingo received it!"
        )
        self.destroy_recognizer()

    @mainthread
    def show_voice_error(self, error):
        errors = {
            1: "Network timeout",
            2: "Network error",
            3: "Audio recording error",
            4: "Server error",
            5: "Client error",
            6: "Speech timeout",
            7: "No speech match",
            8: "Recognizer busy",
            9: "Microphone permission problem",
            10: "Language not supported",
            11: "Language unavailable",
            12: "Server disconnected",
            13: "Cannot listen to speech"
        }
        message = errors.get(int(error), "Unknown speech error")
        self.message.text = f"❌ Voice error\n\nCode: {error}\n{message}"
        self.destroy_recognizer()

    def destroy_recognizer(self):
        if self.recognizer is not None:
            try:
                self.recognizer.stopListening()
            except Exception:
                pass
            try:
                self.recognizer.cancel()
            except Exception:
                pass
            try:
                self.recognizer.destroy()
            except Exception:
                pass
            self.recognizer = None


# =========================================================
# RUN BINGO
# =========================================================

if __name__ == "__main__":
    BingoApp().run()
