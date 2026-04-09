# NeuroDecode A2A Agent Overview

## Purpose
NeuroDecode A2A Agent exposes caregiver support capabilities over Agent-to-Agent (A2A) protocol so external orchestrators (such as Prompt Opinion) can invoke structured ASD caregiver tools.

This service is designed for:
- fast caregiver guidance during distress moments
- practical intervention support without long prompts
- bridging household observations into clinician-friendly outputs

## Live Service
- Service name: neurodecode-a2a
- Region: asia-southeast1
- Base URL: https://neurodecode-a2a-jzfv6ygw3q-as.a.run.app
- Agent card: /.well-known/agent-card.json
- Health check: /health
- Main endpoint: POST /

## Protocol
- Protocol: A2A JSON-RPC
- protocolVersion: 0.2.2
- preferredTransport: JSONRPC

## Current Skill Set (7)
1. find_asd_resources
   - Find ASD-relevant clinics, therapists, inclusive schools, hospitals, and community centers.
   - Uses curated Firestore data where available; otherwise uses grounded web search.

2. suggest_interventions
   - Evidence-based intervention strategies for specific triggers.

3. get_de_escalation_steps
   - Step-by-step protocol for active distress situations.

4. assess_escalation_risk
   - Structured risk reasoning from behavioral descriptions.

5. draft_therapist_handover
   - Creates structured clinician handover notes from caregiver observations.

6. assess_caregiver_wellbeing
   - Screens caregiver stress/burnout indicators and suggests support actions.

7. get_sensory_diet_plan
   - Generates age- and context-aware sensory regulation plans.

## Data Sources
- Firestore clinical_resources collection for curated resource directory.
- Gemini model for reasoning and synthesis.
- Google Search grounding (for non-curated location coverage).

## Reliability and Cost Controls
- In-memory cache for repeated lookups.
- Firestore cache for cross-instance persistence.
- Per-location rate limiting to avoid runaway query loops.
- Retry and graceful handling for transient provider overload (503/429).
- User-friendly fallback response when model is temporarily overloaded.

## Security
- Optional API key enforcement via middleware.
- Behavior controlled by environment variable A2A_REQUIRE_AUTH.
- Agent card endpoint remains public by design for discovery.

## Branching and Release
- Active development branch for this service: feature/a2a-agent.
- Main app flow and mobile integration merge through dev after validation.

## Validation Checklist
- Agent card loads and lists all 7 skills.
- Prompt Opinion A2A connection shows Skills (7).
- Smoke prompts return completed state with non-empty text.
- No parser error from missing task discriminator fields.

## Known Notes
- Intermittent upstream provider overload can still occur under high demand.
- Transient failures are mitigated via retry and graceful response.
- For best trust in location lookups, encourage verification of live-search contacts before visit.
