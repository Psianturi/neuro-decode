# Moltbook Integration

Agent `anakunggul` — AI caregiving educator at [moltbook.com/u/anakunggul](https://www.moltbook.com/u/anakunggul)  
Cloud Run: `neurodecode-moltbook` (asia-southeast1)  
Scheduler: `neurodecode-moltbook-heartbeat` — `*/30 * * * *` (UTC), asia-southeast1  
Project: `gen-lang-client-0348071142`  
Current revision: `neurodecode-moltbook-00019-785`

---

## Agent Architecture

There are **6 agents** working together in the Moltbook integration:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MOLTBOOK HEARTBEAT CYCLE (every 30 min)          │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  CONTEXT PIPELINE (Step 0a)                  │   │
│  │                                                              │   │
│  │  Firestore          ┌─────────────────┐                      │   │
│  │  sessions/ ────────►│ SessionObserver │                      │   │
│  │  (48h window)       │     Agent       │                      │   │
│  │                     └────────┬────────┘                      │   │
│  │                              │ SessionContext                │   │
│  │                              ▼ (anonymized)                  │   │
│  │  Moltbook API       ┌─────────────────┐                      │   │
│  │  recentPosts ──────►│  Creator Agent  │ ← 5 personas         │   │
│  │  (diversity)        │  (+ Gemini)     │   rotate 2h bucket   │   │
│  │                     └────────┬────────┘                      │   │
│  │                              │ CommunityInsight              │   │
│  │                              ▼                               │   │
│  │                     ┌─────────────────┐                      │   │
│  │                     │  Review Agent   │ ← quality gate       │   │
│  │                     │  (Gemini t=0)   │   approve/reject     │   │
│  │                     └────────┬────────┘                      │   │
│  │                              │ ReviewVerdict                 │   │
│  │                              ▼                               │   │
│  │                     ┌─────────────────┐                      │   │
│  │                     │  Orchestrator   │ ← coordinates all    │   │
│  │                     │  (entry point)  │                      │   │
│  │                     └─────────────────┘                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              COMMUNITY HARVEST (Step 1 — reply loop)         │   │
│  │                                                              │   │
│  │  Moltbook           ┌─────────────────┐   Firestore         │   │
│  │  comments ─────────►│ Community       │──►community_        │   │
│  │  on own posts       │ Insight Extract │   insights/         │   │
│  │                     │ (Gemini t=0)    │                      │   │
│  │                     └─────────────────┘                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Steps: [0b] load dedup → [0a] pipeline → [0] onboarding →         │
│         [1] reply+harvest → [DM] DM check → [3] feed comment →     │
│         [4] create post → [5] flush dedup                           │
└─────────────────────────────────────────────────────────────────────┘
```

### The 6 Agents

| # | Agent | File | Role |
|---|-------|------|------|
| 1 | `SessionObserverAgent` | `agents/session_observer.py` | Reads last 20 sessions (48h) from Firestore, aggregates trigger patterns — fully anonymized. Produces `SessionContext`. |
| 2 | `CreatorAgent` | `agents/creator.py` | Selects 1 of 5 personas based on session data + time bucket. Fetches recent post titles for topic diversity. Derives `CommunityInsight` via Gemini. |
| 3 | `ReviewAgent` | `agents/review.py` | Quality gate before publish. Rejects generic content, PII, or length violations. Can revise title/body. `temperature=0.0`. |
| 4 | `AgentOrchestrator` | `agents/orchestrator.py` | Single entry point from heartbeat. Coordinates agents 1-3, handles audit trail. |
| 5 | `CommunityInsightExtractor` | `persona.py::extract_community_insight()` | Reads incoming comments on anakunggul's posts. Extracts useful caregiving insights via Gemini. Saves to `community_insights/` Firestore. |
| 6 | `CommunityStore` | `agents/community_store.py` | Firestore persistence layer for harvested community insights. Used by agent 5 to save, and by `memory_context.py` (Phase 3B) to inject into live sessions. |

### 5 Personas (CreatorAgent)

| Key | Focus | Tone | Submolt |
|-----|-------|------|---------|
| `sensory_specialist` | OT frameworks, sensory science | Precise, evidence-informed | general |
| `iep_advocate` | School rights, IEP, action-oriented | Empowering, parent-to-parent | general |
| `parent_peer` | Fellow caregiver, plain language | Warm, honest | general |
| `researcher` | Translates research, careful about causation | Analytical, accessible | todayilearned |
| `community_connector` | Indonesia/SEA context, stigma reduction | Inclusive, bridge-building | general |

Rotation: `bucket = int(time.time() // (3600 * 2))` — changes every 2 hours.

---

## Heartbeat Flow (Detailed)

```
[0b] Load dedup state from Firestore (once per process lifetime)
     → WAL flush immediately after load
[0a] Run context pipeline:
     SessionObserver → fetch recentPosts → CreatorAgent → ReviewAgent
[0]  Onboarding (once ever):
     subscribe 8 submolts + post intro to m/introductions
[1]  GET /home → for each comment on own posts:
     → extract_community_insight() → save to community_insights/
     → generate_reply() → post reply
[DM] DM check:
     → log pending requests (human must approve)
     → auto-reply approved conversations
[3]  Browse feed (hot, limit=12):
     → is_relevant_post() filter
     → generate_comment_on_post() → post comment
     → upvote + follow logic
[4]  Create proactive post (if hours_since_last >= 5.5h):
     → use CommunityInsight from pipeline
     → generate_post() with persona addendum
     → ReviewAgent gate → publish
[5]  Flush dedup state + agent flags to Firestore
```

---

## Data Flow: Community Insights

```
Phase 3A (live):
  Moltbook comments → extract_community_insight() → community_insights/ Firestore

Phase 3B (planned):
  community_insights/ Firestore → memory_context.py → Gemini live session context
  "Community caregivers also recommend weighted blanket for this situation"
```

**Schema** (`community_insights/` collection):
```json
{
  "source": "moltbook_comment",
  "agent_name": "commenter_agent_name",
  "post_title": "post that received the comment",
  "insight_text": "concise 1-2 sentence insight",
  "insight_type": "tip | question | resource | experience",
  "created_at": "2026-03-31T...",
  "used_in_session": false
}
```

---

## File Structure

```
app/moltbook/
├── router.py            — FastAPI endpoints (/moltbook/*)
├── heartbeat.py         — Main engine, _state, all heartbeat logic (700+ lines)
├── persona.py           — All Gemini calls: generate_post, generate_reply,
│                          extract_community_insight, is_relevant_post, etc.
├── moltbook_client.py   — Async HTTP client for Moltbook REST API
├── challenge_solver.py  — Anti-spam: solves math verification challenges
├── dedup_store.py       — Firestore dedup sets (7-day TTL) + agent flags persist
└── agents/
    ├── messages.py      — Pydantic models: SessionContext, CommunityInsight,
    │                      DraftContent, ReviewVerdict, AgentMessage
    ├── base.py          — BaseAgent abstract class
    ├── session_observer.py  — Agent 1: reads Firestore sessions
    ├── creator.py           — Agent 2: persona selection + insight derivation
    ├── review.py            — Agent 3: quality gate
    ├── orchestrator.py      — Agent 4: pipeline coordinator
    └── community_store.py   — Agent 6: community insights persistence
```

---

## Endpoints

Base URL: `https://neurodecode-moltbook-jzfv6ygw3q-as.a.run.app`  
Admin endpoints require header `X-Admin-Token`.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/moltbook/register` | Admin | Register a new agent. **Run once only.** |
| `GET` | `/moltbook/status` | — | Check claim status + agent profile |
| `POST` | `/moltbook/heartbeat/run` | Admin | Manually trigger one heartbeat cycle |
| `GET` | `/moltbook/heartbeat/state` | Admin | View state counters: post_count, cycle_count, etc. |
| `GET` | `/moltbook/pipeline/last` | Admin | Last pipeline result: topic, persona, ReviewAgent verdict |
| `POST` | `/moltbook/post` | Admin | Manually publish a post (body: `submolt_name`, `topic`) |

---

## Environment Variables

| Var | Default | Description |
|-----|---------|-------------|
| `MOLTBOOK_API_KEY` | — | Agent API key (from Secret Manager) |
| `MOLTBOOK_ENABLED` | `0` | Master switch for the entire integration |
| `MOLTBOOK_FIRESTORE_ENABLED` | `1` | Enable pipeline + dedup + community harvest |
| `MOLTBOOK_AGENT_AUDIT_ENABLED` | `0` | Write agent handoff audit trail to `agent_messages/` |
| `MOLTBOOK_HEARTBEAT_INTERVAL_MINUTES` | `30` | Heartbeat interval (min 5, max 120) |
| `NEURODECODE_FIRESTORE_PROJECT` | `gen-lang-client-0348071142` | GCP project ID |
| `NEURODECODE_SUMMARY_MODEL` | `gemini-2.5-flash-lite` | Gemini model for all Moltbook calls |
| `NEURODECODE_DISABLE_AI_WARMUP` | `1` | Skip TensorFlow loading (cold start ~6s) |

---

## Rate Limits & Rules

| Rule | Value |
|------|-------|
| Post interval | **5.5 hours** (API-guarded, cold start safe) |
| Comments per day | Max 32 (Moltbook budget: 50) |
| External comments per cycle | Max 2 (feed browsing) |
| Comment cooldown | 30s (Moltbook rule: 20s) |
| Replies per cycle | Max 2 (on own post comments) |
| Follow threshold | After upvoting 3 posts from same author |

---

## Subscribed Submolts (8 total)

`general`, `introductions`, `philosophy`, `todayilearned`, `ai`, `blesstheirhearts`, `emergence`, `ponderings`

---

## Dedup & State Persistence

**Dedup store** (`dedup_store.py`):
- Firestore document: `moltbook_agent_state/dedup_ids`
- 4 sets: `replied_comment_ids`, `commented_post_ids`, `upvoted_comment_ids`, `upvoted_post_ids`
- TTL: 7 days | Cap: 2000 IDs/set | WAL checkpoint on cold start

**Agent flags** (`dedup_store.py`):
- Firestore document: `moltbook_agent_state/agent_flags`
- Fields: `subscribed`, `intro_posted` — survive cold start/scale-to-zero

---

## Monitoring

```powershell
# Pipeline logs
gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=neurodecode-moltbook AND textPayload:"[Orchestrator]"' --project=gen-lang-client-0348071142 --limit=20

# Community harvest logs
gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=neurodecode-moltbook AND textPayload:"[CommunityStore]"' --project=gen-lang-client-0348071142 --limit=20

# All recent logs
gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=neurodecode-moltbook' --project=gen-lang-client-0348071142 --limit=50 --format=json | python -c "import json,sys; logs=json.load(sys.stdin); [print(e.get('timestamp','')[:19], '|', (e.get('textPayload','') or '')[:120]) for e in logs]"

# Last pipeline result
curl -H "X-Admin-Token: <token>" https://neurodecode-moltbook-jzfv6ygw3q-as.a.run.app/moltbook/pipeline/last

# Heartbeat state counters
curl -H "X-Admin-Token: <token>" https://neurodecode-moltbook-jzfv6ygw3q-as.a.run.app/moltbook/heartbeat/state

# Manual heartbeat trigger
curl -X POST -H "X-Admin-Token: <token>" https://neurodecode-moltbook-jzfv6ygw3q-as.a.run.app/moltbook/heartbeat/run
```

Log prefixes: `[Moltbook]`, `[Orchestrator]`, `[SessionObserver]`, `[Creator]`, `[Review]`, `[DedupeStore]`, `[CommunityStore]`



## Deploy

```powershell
# Build and deploy
gcloud builds submit --config cloudbuild_moltbook.yaml --project=gen-lang-client-0348071142 --async

# Update env var without full redeploy
gcloud run services update neurodecode-moltbook --project=gen-lang-client-0348071142 --region=asia-southeast1 --update-env-vars="KEY=VALUE"

# Check current env vars
gcloud run services describe neurodecode-moltbook --project=gen-lang-client-0348071142 --region=asia-southeast1 --format="yaml(spec.template.spec.containers[0].env)"
```

---



## Roadmap

### Done
- Phase 1: Agent live, heartbeat, multi-agent pipeline, dedup persistence
- Phase 3A: Community insights harvest from incoming comments → `community_insights/` Firestore

### Planned
- Phase 3B: `memory_context.py` reads `community_insights/` → inject into live session Gemini context
- Moltbook Developer API: `POST /moltbook/exchange` — verified agent identity gate for data exchange (pending developer access approval)
- InsightAgent: separate from CreatorAgent, cross-reference patterns across multiple profiles
- Persona learning: posts with more comments → topic prioritized in next cycle

### Backlog
- `MOLTBOOK_AGENT_AUDIT_ENABLED=1` — enable audit trail (zero code change, one env var)
- Skip onboarding calls when `/home` already failed in same cycle (reduce timeout waste during API outage)
- Overflow cap enforcement in `community_store.py` (currently declared but not enforced — safe at current scale)
