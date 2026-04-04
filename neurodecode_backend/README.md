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

Clinical Resources (Phase 4):

- `GET /clinical-resources` — list, optional `?city=jakarta&resource_type=clinic&limit=50`
- `GET /clinical-resources/{id}` — single resource by Firestore doc ID or Google `place_id`
- `POST /admin/clinical-resources` — create (requires `X-Admin-Secret` header)
- `PATCH /admin/clinical-resources/{id}` — partial update (requires `X-Admin-Secret` header)

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

> ⚠️ **PENTING:** Selalu gunakan `--update-secrets` (bukan `--set-secrets`) saat menambah secret
> baru agar secret yang sudah ada tidak terhapus. `--set-secrets` = **replace all**.

Secret Manager secrets yang harus terpasang di Cloud Run:

| Env Var | Secret Manager Name |
|---------|--------------------|
| `GEMINI_API_KEY` | `neurodecode-gemini-api-key` |
| `NEURODECODE_ADMIN_DEBUG_TOKEN` | `neurodecode-admin-debug-token` |
| `TELEGRAM_BOT_TOKEN` | `neurodecode-telegram-bot-token` |
| `TELEGRAM_CHAT_ID` | `neurodecode-telegram-chat-id` |
| `NEURODECODE_ADMIN_SECRET` | `neurodecode-admin-secret` |

Semua sudah terdaftar di `cloudbuild.yaml` baris `--set-secrets`. Setiap build otomatis set ulang semua 5 secret sekaligus.

Untuk update satu secret tanpa mengganggu yang lain:

```powershell
gcloud run services update neurodecode-backend `
	--project gen-lang-client-0348071142 `
	--region asia-southeast1 `
	--platform managed `
	--update-secrets NEURODECODE_ADMIN_SECRET=neurodecode-admin-secret:latest
```

Untuk restore semua secrets sekaligus (jika ada yang hilang):

```powershell
gcloud run services update neurodecode-backend `
	--project gen-lang-client-0348071142 `
	--region asia-southeast1 `
	--platform managed `
	--update-secrets "GEMINI_API_KEY=neurodecode-gemini-api-key:latest" `
	--update-secrets "NEURODECODE_ADMIN_DEBUG_TOKEN=neurodecode-admin-debug-token:latest" `
	--update-secrets "TELEGRAM_BOT_TOKEN=neurodecode-telegram-bot-token:latest" `
	--update-secrets "TELEGRAM_CHAT_ID=neurodecode-telegram-chat-id:latest" `
	--update-secrets "NEURODECODE_ADMIN_SECRET=neurodecode-admin-secret:latest"
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
- If live session returns `GEMINI_API_KEY is required`, run the "restore all secrets" command above — most likely `--set-secrets` was used instead of `--update-secrets` somewhere.
- `NEURODECODE_ADMIN_SECRET` guards `POST /admin/clinical-resources` and `PATCH /admin/clinical-resources/{id}`. Without it set, those endpoints are unprotected.

## Clinical Resources harvest (Phase 4)

Data klinik/sekolah ASD Jakarta di-harvest dari Google Places API dan disimpan permanen ke Firestore `clinical_resources/`. User tidak pernah hit Places API.

Pre-requisites: set `PLACES_API_KEY_NEW` dan `PLACES_API_KEY` di `.env` (sudah di `.gitignore`).

```powershell
# Jalankan harvest (one-time / bulanan)
c:/PROJ/NeuroDecode/.venv/Scripts/python.exe neurodecode_backend/scripts/harvest_clinical_places.py

# Seed manual (Anak Unggul, dll)
c:/PROJ/NeuroDecode/.venv/Scripts/python.exe neurodecode_backend/scripts/seed_clinical_resources.py
```

Firestore composite indexes yang dibutuhkan (sudah READY):

```bash
# city + is_active
gcloud firestore indexes composite create --project=gen-lang-client-0348071142 \
  --collection-group=clinical_resources --query-scope=COLLECTION \
  --field-config=field-path=city,order=ASCENDING \
  --field-config=field-path=is_active,order=ASCENDING \
  --field-config=field-path=__name__,order=ASCENDING

# resource_type + is_active
gcloud firestore indexes composite create --project=gen-lang-client-0348071142 \
  --collection-group=clinical_resources --query-scope=COLLECTION \
  --field-config=field-path=resource_type,order=ASCENDING \
  --field-config=field-path=is_active,order=ASCENDING \
  --field-config=field-path=__name__,order=ASCENDING
```
