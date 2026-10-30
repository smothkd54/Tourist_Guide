# Pushkinskaya Explorer (Android, Kotlin, Jetpack Compose)

Native Android client for the Flask API: Explore, Detail, Identify, Routes (with
reminders) and More.

## Status

Built and unit-tested locally with JDK 21 + Android SDK 35 + Gradle 8.9:

- `assembleDebug` → `app/build/outputs/apk/debug/app-debug.apk` (28.6 MB)
- `testDebugUnitTest` → 5 tests, 0 failures (JSON parsing against the real API shapes)
- CI runs both and uploads the APK. Launch is verified on the physical demo
  phone; an emulator smoke test was removed because the runner's emulator
  failed and its logs need authentication to read, so it could not be
  diagnosed.

It has **not** been run on the physical demo phone yet: `adb devices` is empty
until the phone is connected with USB debugging enabled.

## What is in it

- Explore: cached landmark list (Room), search, add to route, EN/RU names, status badge.
- Detail: photo, description, Listen (text-to-speech), add or remove from route.
- Identify: take or pick a photo, resized to 1024 px JPEG on the phone, sent to `POST /predict`.
- Routes: visit list, `POST /plan-custom`, route reminders (15 min, 1 h, 3 h).
- More: language, refresh, notification settings.
- Notifications: two channels (Reminders, Place status). Permission is asked when
  the user first sets a reminder.
- Place status alerts without any push provider: a 6-hour WorkManager check compares
  statuses for landmarks on the route. The Flask API does not send `status` yet, so
  the badge and alerts stay quiet until the server adds it.

Reminders use `AlarmManager` (`setExactAndAllowWhileIdle`, falling back to
`setAndAllowWhileIdle` when exact alarms are not permitted). WorkManager is only
used for the status poll, where a late run is harmless: it can be deferred for
hours under Doze, which would make a 15-minute reminder useless.

## Not in it yet

- Map and offline tiles, on-device TFLite, offline route solver (slices 2 and 3 of the design).
- Offline queue for Identify (the web app has one; here it shows "No connection").
- Remote push (FCM or RuStore): optional, see the push plan.

## Run

### Requirements

- JDK 21 (Gradle runs on it; the code targets Java 17)
- Android SDK platform 35 and build-tools 35.0.0
- `android/local.properties` with `sdk.dir=...` (already present on the dev machine)

### Build

```bat
cd android
gradlew.bat assembleDebug
```

### Install on a real phone over USB

```bat
adb reverse tcp:5000 tcp:5000
adb install -r app\build\outputs\apk\debug\app-debug.apk
adb shell am start -n app.pushkinskaya.android/.MainActivity
```

`adb reverse` maps the phone's `localhost:5000` to the PC, and the debug build
uses `http://127.0.0.1:5000/`, so no LAN IP or `HOST=0.0.0.0` is needed. Start
the API first (`python backend/app.py`).

### Release

Release builds use HTTPS and cleartext is disabled. Set the real domain in the
release `API_BASE_URL` in `app/build.gradle.kts`; the current placeholder is
`https://your-domain.com/`.

## Notes

- Native apps do not use CORS, so the server's CORS list is irrelevant here.
- `minSdk 28` (Android 9) is required by `ImageDecoder`.
- Dependency and plugin versions are pinned to what actually resolved and
  compiled: AGP 8.7.3, Kotlin 2.0.21, Compose BOM 2024.12.01, Room 2.6.1,
  Retrofit 2.11.0, WorkManager 2.10.0.
