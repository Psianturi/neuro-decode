# NeuroDecode Mobile

Mobile app for NeuroDecode AI.

This app helps caregivers or parents get real-time support during stressful sensory moments. The app can listen, optionally use camera context, speak back with Gemini, save session summaries, and show proactive notifications.

## What You Can Do

1. Start a live support session with voice.
2. Choose `Audio only` or `Video + audio`.
3. Get spoken and written guidance from Gemini.
4. Review session summaries and history.
5. Save useful profile memory for future sessions.
6. Receive proactive notifications from the backend.

## Main Screens

1. Home
	- Active profile summary
	- Latest session summary
	- Notifications badge
2. Support
	- Pick a profile
	- Pick session mode
	- Start Live Support
3. Live Session
	- Push-to-talk control
	- Real-time transcript bubbles
	- Optional draggable camera preview
4. Profile Workspace
	- Profile details
	- Support preferences
	- Memory notes
5. History / Insights
	- Session detail cards
	- Suggested memory actions

## Prerequisites

1. Flutter SDK installed and available in terminal.
2. Android Studio or Android SDK platform tools for device/emulator deployment.
3. A running NeuroDecode backend endpoint.
4. Firebase Android config file for FCM:
	- `android/app/google-services.json`
	- Android application id must match `com.neurodecode.neurodecode_mobile`

## Configuration

The backend host is configured in:

1. `lib/config/app_config.dart`

Current expected pattern:

```dart
static const String backendUrl = 'neurodecode-backend-90710068442.asia-southeast1.run.app';
static const String wsEndpoint = 'wss://$backendUrl/ws/live';
```

If you change environments, update the host before building or running.

## Run The App

Run on a connected Android device:

```powershell
cd c:\PROJ\NeuroDecode\neurodecode_mobile
flutter pub get
flutter devices
flutter run
```

If you add or replace `google-services.json`, refresh first:

```powershell
cd c:\PROJ\NeuroDecode\neurodecode_mobile
flutter clean; flutter pub get
flutter run
```

Build a release APK:

```powershell
cd c:\PROJ\NeuroDecode\neurodecode_mobile
flutter build apk --release
```

## Firebase / FCM Setup

1. Create or reuse the Firebase project that belongs to the same Google Cloud project as the backend deployment.
2. Register an Android app with package name `com.neurodecode.neurodecode_mobile`.
3. Download `google-services.json` and place it in `android/app/google-services.json`.
4. Open the app Home screen after launch so the app can request notification permission and register the current device token to the backend.

Expected behavior after setup:

1. Device token is posted to `POST /devices/push-token`.
2. Admin push test can deliver an Android notification banner.
3. Proactive backend rules can surface as OS notifications and in-app notifications.

## Reproducible Test Steps

1. Launch the app with a connected Android device.
2. Open Home and wait a few seconds for initial profile summary and push token sync.
3. Open Support, choose `Audio only` or `Video + audio`, and start a live session.
4. Speak one or more turns and end the session.
5. Return to Home or Notifications and verify summary/history/notification updates.
6. Optionally run backend admin push test to verify OS banner delivery.

## Video


- [Watch the mobile demo](assets/neurodecode-vid.mp4)

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
