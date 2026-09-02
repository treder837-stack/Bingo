[app]

# (str) Title of your application
title = Bingo

# (str) Package name
package.name = bingo

# (str) Package domain
package.domain = org.bingo

# (str) Source directory
source.dir = .

# (str) Main Python file
source.main = main.py

# (list) Application requirements
requirements = python3,kivy,pyjnius,google-genai

# (str) Application version
version = 1.0

# (list) Supported orientations
orientation = portrait

# (list) Android permissions
android.permissions = INTERNET

# (bool) Fullscreen
fullscreen = 0

# (bool) Accept Android SDK licenses automatically
android.accept_sdk_license = True

# (str) Android API
android.api = 35

# (str) Minimum Android API
android.minapi = 23

# (str) Android NDK version
android.ndk = 27c

# (str) Android architecture
android.arch = arm64-v8a

# (str) Android build tools version
android.build_tools_version = 35.0.0


[buildozer]

# (str) Log level
log_level = 2

# (bool) Warn when buildozer is run as root
warn_on_root = 1
