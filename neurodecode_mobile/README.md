# NeuroDecode Mobile

Flutter client for NeuroDecode AI live caregiving support.

## Main Flows

1. Home
	- Active Profile Summary
	- Latest Session Summary
	- History / Insights entry
2. Support
	- Session mode: `Audio only` or `Video + audio`
	- Profile ID input + saved profile ID picker
	- Start Live Support
3. Live Session
	- Push-to-talk manual turn control
	- Realtime transcript bubbles
	- Optional observer camera preview (draggable, tap pause/resume, retry)
4. Profile Workspace
	- Essential profile details
	- Structured support preferences
	- Optional memory notes
	- Stored memory review
5. History / Insights
	- Session detail cards
	- Suggested memory actions (`Save audio trigger`, `Save visual trigger`, `Save follow-up`)

## Run Locally

```powershell
cd c:\PROJ\NeuroDecode\neurodecode_mobile
flutter pub get
flutter run
```

## Configuration

Set backend host in:

1. `lib/config/app_config.dart`

Expected pattern:

```dart
static const String backendUrl = 'YOUR_CLOUD_RUN_HOST';
static const String wsEndpoint = 'wss://$backendUrl/ws/live';
```

## Notes

1. Android uses native PCM playback path for low-latency model audio.
2. Profile memory status can appear during live session when backend context is loaded.
3. Camera observer is optional and controlled by session mode.
