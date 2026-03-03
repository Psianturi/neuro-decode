# NeuroDecode AI (Backend)

FastAPI backend for **NeuroDecode AI** (Gemini Live Agent Challenge MVP).

## What this backend does (MVP)

- Exposes a WebSocket endpoint for a **live, interruptible** session.
- Bridges client streaming input (audio/text) to **Gemini Live API** using **Google GenAI SDK**.
- Streams model audio chunks back to the client.
- Falls back to a **mock mode** when `GEMINI_API_KEY` is not set (so you can test the WebSocket locally).

## Current progress (what you should see working now)

When everything is running, a WebSocket client should receive streaming events like:

- `model_audio` (base64) with `mime_type: audio/pcm;rate=24000`
- `transcript_out` / `transcript_in` (text) when transcription is enabled
- sometimes `model_text` (text) depending on model output

The included smoke test sends a text turn and prints a few server messages. In a successful “real mode” run, you should see at least one `model_audio` event (often very large) and transcription text.

## Local run (Windows PowerShell)

1) Create a venv and install deps (run from the backend folder):

```powershell
cd c:\PROJ\NeuroDecode\neurodecode_backend
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt
```

2) Set your API key for the *current terminal session* (recommended while testing):

```powershell
$env:GEMINI_API_KEY = "YOUR_KEY_HERE"
```

Notes:

- `setx` sets a persistent env var, but it will NOT affect the currently-open terminal.
- If you want to force mock mode even when the key is present:

```powershell
$env:NEURODECODE_FORCE_MOCK = "1"
```

3) Start server (use the backend venv python explicitly):

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4) Smoke test the WebSocket:

```powershell
.\.venv\Scripts\python scripts\ws_smoke_test.py
```

## WebSocket protocol (simple JSON)

Client → Server:

- `{"type":"audio","data_b64":"...","mime_type":"audio/pcm;rate=16000"}`
- `{"type":"text","text":"hello","end_of_turn":true}`
- `{"type":"observer_note","text":"Internal observation: ..."}` (best-effort; used for the “silent observer” channel)

Server → Client:

- `{"type":"model_audio","data_b64":"...","mime_type":"audio/pcm;rate=24000"}`
- `{"type":"model_audio_end"}` (marks end of one model audio turn)
- `{"type":"transcript_in","text":"..."}` (if enabled)
- `{"type":"transcript_out","text":"..."}` (if enabled)
- `{"type":"interrupted"}`

## Deployment notes (Cloud Run)

### What you need before deploy

- A Google Cloud project + billing enabled
- `gcloud` CLI installed and authenticated (`gcloud auth login`)
- Cloud Run supports WebSockets, but set a long request timeout for long sessions

Enable APIs (one-time per project):

```powershell
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
```

### Deploy from source (Cloud Build)

Run this from the backend folder:

```powershell
cd c:\PROJ\NeuroDecode\neurodecode_backend
gcloud run deploy neurodecode-backend --source . --region asia-southeast2 --allow-unauthenticated --timeout 3600 --concurrency 1
```

Notes:

- `--timeout 3600` helps keep WebSocket sessions alive (up to 60 minutes).
- `--concurrency 1` is a safe default for live audio sessions.

### Set environment variables

Minimum required:

- `GEMINI_API_KEY` (recommended via Secret Manager)

Optional:

- `NEURODECODE_LIVE_MODEL`
- `NEURODECODE_RESPONSE_MODALITY` (default: `AUDIO`)
- `NEURODECODE_VOICE_NAME`
- `NEURODECODE_INPUT_TRANSCRIPTION` / `NEURODECODE_OUTPUT_TRANSCRIPTION`

Secret Manager (recommended) example:

```powershell
echo -n "YOUR_KEY_HERE" | gcloud secrets create neurodecode-gemini-api-key --data-file=-
gcloud run services update neurodecode-backend --region asia-southeast2 --set-secrets GEMINI_API_KEY=neurodecode-gemini-api-key:latest
```

If your `gcloud` version doesn’t support `--set-secrets`, set the env var via the Cloud Run Console (Variables & Secrets) instead.

### Cloud Run URL

Use:

- `wss://YOUR_CLOUD_RUN_URL/ws/live` for WebSocket
- `https://YOUR_CLOUD_RUN_URL/healthz` for health check
