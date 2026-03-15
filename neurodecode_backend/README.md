# NeuroDecode AI (Backend)

FastAPI backend for NeuroDecode AI, serving live multimodal support sessions plus post-session proactive automation.

## Current backend capabilities

- Live WebSocket streaming endpoint (`/ws/live`) for audio/text turns.
- Gemini Live bridge with transcript support and audio chunk streaming.
- Session summary generation and storage.
- Rule-based proactive notifications (`notification_items`).
- Admin debug APIs for rules and push rollout checks.
- Feature-flagged FCM delivery via Firebase Admin SDK.

## Core endpoints

HTTP:

- `GET /health`
- `GET /sessions`
- `GET /sessions/latest`
- `GET /notifications`
- `POST /notifications/{notification_id}/read`
- `GET /profiles/{profile_id}`
- `PUT /profiles/{profile_id}`
- `GET /profiles/{profile_id}/memory`
- `POST /profiles/{profile_id}/memory`
- `GET /profiles/{profile_id}/memory-context`
- `POST /devices/push-token`
- `POST /devices/push-token/deactivate`
- `GET /admin/rules/debug` (admin token required)
- `GET /admin/push/devices` (admin token required)
- `POST /admin/push/test` (admin token required)

WebSocket:

- `GET /ws/live?user_id=<id>&profile_id=<optional>`

## Local run (Windows PowerShell)

```powershell
cd c:\PROJ\NeuroDecode\neurodecode_backend
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt

$env:GEMINI_API_KEY = "YOUR_KEY_HERE"
$env:NEURODECODE_SUMMARY_ENABLED = "1"
$env:NEURODECODE_FIRESTORE_ENABLED = "1"

.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Smoke tests:

```powershell
.\.venv\Scripts\python scripts\ws_smoke_test.py
.\.venv\Scripts\python scripts\memory_eval_probe.py --profile-id joy1 --runs 1
```

## Cloud Run deploy notes

Current default deployment target in this repo:

- Region: `asia-southeast1`
- Service: `neurodecode-backend`
- Trigger file: `cloudbuild.yaml` in repository root

Deploy/update runtime secrets and flags:

```powershell
gcloud run services update neurodecode-backend `
	--project gen-lang-client-0348071142 `
	--region asia-southeast1 `
	--platform managed `
	--set-secrets GEMINI_API_KEY=neurodecode-gemini-api-key:latest `
	--set-secrets NEURODECODE_ADMIN_DEBUG_TOKEN=neurodecode-admin-debug-token:latest `
	--update-env-vars NEURODECODE_ADMIN_DEBUG_ENABLED=1,NEURODECODE_ADMIN_DEBUG_MAX_ITEMS=500,NEURODECODE_FCM_ENABLED=0,NEURODECODE_FIRESTORE_PUSH_DEVICE_COLLECTION=push_device_tokens
```

Enable FCM later (after admin test is healthy):

```powershell
gcloud run services update neurodecode-backend `
	--project gen-lang-client-0348071142 `
	--region asia-southeast1 `
	--platform managed `
	--update-env-vars NEURODECODE_FCM_ENABLED=1
```

Verify runtime env:

```powershell
gcloud run services describe neurodecode-backend `
	--project gen-lang-client-0348071142 `
	--region asia-southeast1 `
	--platform managed `
	--format="yaml(spec.template.spec.containers[0].env)"
```

Important:

- Cloud Run does not read local `.env`; runtime values must come from service env and Secret Manager.
- If live session returns `GEMINI_API_KEY is required`, re-apply `--set-secrets GEMINI_API_KEY=...`.
