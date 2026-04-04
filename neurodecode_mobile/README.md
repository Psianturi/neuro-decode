# NeuroDecode Mobile

Flutter Android app for NeuroDecode AI.

The app gives caregivers & parents a real-time co-pilot during stressful sensory moments — speak to get instant guidance, review past sessions, manage a child's support profile, find local ASD clinics and therapists, and receive proactive follow-up notifications automatically after high-severity sessions.

## What You Can Do

1. Start a live support session with voice (audio only or with camera).
2. Receive spoken and transcript guidance from Gemini in real time.
3. Review session summaries and trigger history.
4. Set and save a child's support profile (triggers, calming strategies, communication style).
5. Approve AI-suggested memory actions from past sessions with one tap.
6. Browse 198 Jakarta ASD clinics, therapists, hospitals, and inclusive schools.
7. Receive proactive follow-up push notifications hours after high-severity sessions.

## Navigation (4 Tabs)

Bottom navigation bar:

| Tab | Icon | Purpose |
|---|---|---|
| **Home** | Home | Dashboard: active profile, latest session summary, notification badge |
| **Support** | Support Agent | Start a live session — pick profile, pick mode (audio / video+audio) |
| **Find Help** | Medical Services | Browse and filter local ASD resources |
| **Buddy** | Smart Toy | Profile Workspace, theme settings |

## Main Screens

1. **Home Dashboard**
   - Active profile summary card (name, last session date)
   - Latest session summary (title, triggers, agent actions, follow-up note)
   - Notification bell badge showing unread count
   - Pull-to-refresh

2. **Support Hub**
   - Session mode selection: Audio Only / Video + Audio
   - Profile ID input (links session to a child's memory context)
   - Launch button → navigates to Live Session screen

3. **Live Agent Screen**
   - Push-to-talk microphone button
   - Real-time transcript bubble stream
   - Optional draggable camera preview (Video + Audio mode)
   - Session timer and close button

4. **Find Help Screen** *(new in Phase 4)*
   - Loads up to 100 active resources from backend `GET /clinical-resources`
   - Filter chips: All / Clinic / Therapist / School / Hospital / Community
   - Resource cards: name, type badge (color-coded), address, tap-to-copy phone number, Instagram handle, service tags, staleness warning
   - Pull-to-refresh, error state with retry

5. **Profile Workspace** (via Buddy tab)
   - Profile selector (create / switch profiles)
   - Support Preferences: known trigger chips, calming strategy chips, communication style, sensory profile
   - **SAVE SUPPORT PREFERENCES** button — must tap to persist chip selections to Firestore
   - Profile Memory notes

6. **History / Insights**
   - Session timeline with structured summary cards
   - Color-coded close reason labels
   - Suggested memory actions (approve/dismiss with one tap)

7. **Notifications Center**
   - Full notification history with read/unread state
   - Mark as read on tap

## Prerequisites

1. Flutter SDK `^3.6.2` installed and available in terminal.
2. Android Studio or Android SDK platform tools for device/emulator deployment.
3. A running NeuroDecode backend (Cloud Run or local).
4. Firebase Android config file for FCM:
   - `android/app/google-services.json`
   - Android application ID must match `com.neurodecode.neurodecode_mobile`

## Configuration

Backend host is set in one place:

```dart
// lib/config/app_config.dart
static const String backendUrl =
    'neurodecode-backend-90710068442.asia-southeast1.run.app';
static const String wsEndpoint = 'wss://$backendUrl/ws/live';
```

To point at a local backend, change `backendUrl` to your machine's IP (e.g. `192.168.x.x:8000`) and use `ws://` instead of `wss://`.

## Run The App

```powershell
cd c:\PROJ\NeuroDecode\neurodecode_mobile
flutter pub get
flutter devices
flutter run
```

If you replaced `google-services.json`, clean first:

```powershell
flutter clean ; flutter pub get ; flutter run
```

Build a release APK:

```powershell
flutter build apk --release
```

## Firebase / FCM Setup

1. Reuse or create the Firebase project linked to the same GCP project as the backend (`gen-lang-client-0348071142`).
2. Register an Android app with package name `com.neurodecode.neurodecode_mobile`.
3. Download `google-services.json` → place at `android/app/google-services.json`.
4. Open the app Home screen — the app auto-registers the FCM device token to `POST /devices/push-token` on every launch.

Expected behaviour after setup:

1. Device token posted to backend on app start.
2. Admin push test (`POST /admin/push/test`) delivers an Android notification banner.
3. Rule-based notifications and time-delayed follow-up pushes surface as OS banners and in-app notification items.

## Key Dependencies

| Package | Purpose |
|---|---|
| `web_socket_channel` | WebSocket live session |
| `record` | Microphone audio capture |
| `audioplayers` | Gemini audio response playback |
| `camera` | Optional video observer frames |
| `firebase_core` + `firebase_messaging` | FCM push notifications |
| `shared_preferences` | Local profile ID + theme persistence |
| `intl` | Date formatting |

## Profile Memory — Important Note

After setting trigger chips and calming strategy chips in the **Support Preferences** section of the Buddy tab, you **must tap SAVE SUPPORT PREFERENCES** at the bottom of the section. Selecting chips alone does not persist — the explicit save action is required.

This data is what the AI uses during live sessions to give child-specific guidance instead of generic ASD advice.

## Feature Flags (Backend)

Some app features require the backend to have specific environment variables set:

| Feature | Backend env var |
|---|---|
| Profile memory context in sessions | `NEURODECODE_ENABLE_PROFILE_MEMORY_CONTEXT=1` |
| Post-session summary generation | `NEURODECODE_SUMMARY_ENABLED=1` |
| FCM push delivery | `NEURODECODE_FCM_ENABLED=1` |
| Clinical resources | Always on — no flag needed |

## Reproducible Test Steps

1. Launch the app with a connected Android device.
2. Open Home and wait a few seconds for initial profile summary and push token sync.
3. Open Support, choose `Audio only` or `Video + audio`, and start a live session.
4. Speak one or more turns and end the session.
5. Return to Home or Notifications and verify summary/history/notification updates.
6. Optionally run backend admin push test to verify OS banner delivery.


## Troubleshooting

1. `google-services.json is missing`
	- Confirm the file exists at `android/app/google-services.json`.
2. Live session connects but returns configuration errors
	- Verify the backend Cloud Run runtime still has `GEMINI_API_KEY` configured.
3. Push banner does not appear
	- Ensure app notification permission is enabled.
	- Make sure the Firebase project matches the backend Google Cloud project.
	- Open Home again so the latest device token is re-registered.
4. Profile-specific push does not arrive
	- Confirm the active profile ID in the app matches the profile used when testing backend push delivery.

## Notes

1. Android uses native PCM playback path for low-latency model audio.
2. Profile memory status can appear during live session when backend context is loaded.
3. Camera observer is optional and controlled by session mode.
4. Push notifications depend on a valid Firebase app configuration and successful token registration.
