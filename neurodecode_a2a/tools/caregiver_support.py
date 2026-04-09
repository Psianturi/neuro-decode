"""Tools: Caregiver-to-clinician bridge and caregiver wellbeing support.

Three skills that differentiate NeuroDecode from generic ASD chatbots:

1. draft_therapist_handover  — structured clinical briefing note for appointments
2. assess_caregiver_wellbeing — holistic caregiver stress and support screening
3. get_sensory_diet_plan      — evidence-based sensory diet tailored to the child

All inputs are descriptive/synthetic text — no PHI is accepted or stored.
All outputs are non-diagnostic guidance; professional consultation always recommended.
"""
import logging
import os

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an expert ASD (Autism Spectrum Disorder) caregiver support specialist. "
    "You provide evidence-based, practical, non-diagnostic guidance. "
    "You never diagnose. You always recommend professional consultation for clinical decisions. "
    "Respond in clear, structured, actionable language. "
    "If the caregiver's language context is Indonesian, respond in Indonesian."
)
_RETRYABLE = ("503", "429", "resource exhausted", "overloaded", "unavailable")


def _gemini_call(prompt: str, max_tokens: int = 700) -> str:
    import time
    from google import genai
    from google.genai import types as genai_types

    client = genai.Client()
    last_exc = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=_SYSTEM,
                    max_output_tokens=max_tokens,
                    temperature=0.4,
                ),
            )
            return response.text or ""
        except Exception as exc:
            last_exc = exc
            msg = str(exc).lower()
            if any(r in msg for r in _RETRYABLE) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            break
    logger.error("[caregiver_support] Gemini call failed: %s", last_exc)
    return f"[Tool temporarily unavailable. Please try again shortly. Error: {last_exc}]"


def draft_therapist_handover(
    behavior_summary: str,
    key_triggers: str,
    effective_interventions: str,
    session_count: str,
) -> str:
    """
    Draft a structured clinical handover note for a therapist or psychiatrist appointment.

    This bridges the gap between caregiver daily observations and clinical consultations
    — turning raw behavioral descriptions into a professional, structured briefing that
    a clinician can act on immediately.

    Args:
        behavior_summary: Plain-text description of the child's recent behavioral patterns.
                          Example: 'Increased meltdowns over last 2 weeks, mostly in the
                          afternoon. Hitting and biting more frequent. Sleep disrupted.'
        key_triggers: Comma-separated list of known or suspected triggers.
                      Example: 'loud noise, denied requests, transitions, hunger, fatigue'
        effective_interventions: Interventions or strategies that have been working.
                                 Example: 'deep pressure vest, noise-cancelling headphones,
                                 5-minute warning before transitions, visual schedule'
        session_count: Number of live sessions or observations this is based on.
                       Example: '8 sessions over 3 weeks'. Use 'unknown' if not sure.
                       Default: 'unknown'.

    Returns:
        A structured clinical handover note in plain text, ready to share with a therapist.
    """
    prompt = (
        f"A caregiver is preparing for a therapist/clinician appointment for their autistic child.\n"
        f"Based on {session_count} observations:\n\n"
        f"BEHAVIORAL PATTERNS OBSERVED:\n{behavior_summary}\n\n"
        f"KEY TRIGGERS IDENTIFIED:\n{key_triggers}\n\n"
        f"INTERVENTIONS THAT HELPED:\n{effective_interventions}\n\n"
        "Draft a clear, structured clinical handover note the caregiver can share with "
        "the therapist or psychiatrist. Format:\n"
        "REFERRAL CONTEXT: (1-2 sentences)\n"
        "BEHAVIORAL OBSERVATIONS: (bullet points, specific and observable)\n"
        "IDENTIFIED TRIGGERS: (bullet list)\n"
        "EFFECTIVE STRATEGIES TO DATE: (bullet list)\n"
        "QUESTIONS FOR CLINICIAN: (2-3 suggested questions the caregiver should ask)\n"
        "CAREGIVER NOTE: (1 sentence of encouragement for the caregiver)\n\n"
        "Keep the tone professional but accessible. This is for a parent, not a clinician author."
    )
    return _gemini_call(prompt, max_tokens=800)


def assess_caregiver_wellbeing(
    stress_indicators: str,
    support_system: str,
    sleep_quality: str,
) -> str:
    """
    Assess caregiver wellbeing and provide personalized self-care and support guidance.

    Caregiver burnout is a major risk factor for child outcomes in ASD families.
    This tool screens for warning signs and provides actionable, empathetic guidance —
    addressing the whole family system, not just the child.

    Args:
        stress_indicators: Description of current stress or burnout signs the caregiver notices.
                           Example: 'Feeling exhausted all the time, snapping at the child more
                           often, no longer enjoying activities I used to like, crying more.'
        support_system: Description of the caregiver's current support network.
                        Example: 'Spouse is helpful but working long hours. No family nearby.
                        Have a therapist but sessions are monthly.'
                        Use 'none described' if not mentioned.
        sleep_quality: Brief description of caregiver's sleep.
                       Example: '5-6 hours broken by child waking up'. Use 'unknown' if not shared.

    Returns:
        A warm, structured wellbeing assessment with immediate self-care actions and resources.
    """
    prompt = (
        "A caregiver of a child with ASD is sharing their current wellbeing situation.\n\n"
        f"STRESS/BURNOUT INDICATORS:\n{stress_indicators}\n\n"
        f"SUPPORT SYSTEM:\n{support_system}\n\n"
        f"SLEEP QUALITY:\n{sleep_quality}\n\n"
        "Provide a caring, structured wellbeing response. Format:\n"
        "WHAT I HEAR: (1-2 sentences validating what the caregiver is experiencing)\n"
        "WELLBEING SIGNALS: (assess low/medium/high concern level with brief rationale)\n"
        "IMMEDIATE SELF-CARE ACTIONS: (3-5 small, realistic actions for this week)\n"
        "SUPPORT RESOURCES TO CONSIDER: (2-3 types of support: respite care, caregiver "
        "support groups, mental health, etc.)\n"
        "IMPORTANT REMINDER: (1 sentence about why caregiver health matters for the child)\n\n"
        "Be warm, non-judgmental, and non-clinical. This is peer-level support, not therapy."
    )
    return _gemini_call(prompt, max_tokens=700)


def get_sensory_diet_plan(
    sensory_profile: str,
    child_age: str,
    environment: str,
) -> str:
    """
    Generate a personalized sensory diet plan based on the child's sensory profile.

    A sensory diet is a structured set of sensory input activities prescribed by
    occupational therapists to help children with ASD self-regulate throughout the day.
    This tool generates an evidence-based starting plan tailored to the child.

    Args:
        sensory_profile: Description of the child's sensory sensitivities and seeking behaviors.
                         Example: 'Seeks deep pressure and proprioceptive input. Hypersensitive
                         to sound and light touch. Avoids crowds. Loves jumping and spinning.'
        child_age: Age or age range of the child.
                   Example: '7', '4-6', 'teenager (14)'. Use 'unknown' if not specified.
        environment: Primary environment where the plan will be used.
                     Example: 'home on weekdays', 'school classroom', 'both home and school'.

    Returns:
        A structured daily sensory diet plan with morning, midday, and evening activity sets.
    """
    prompt = (
        f"Create a personalized sensory diet plan for a child with ASD.\n\n"
        f"CHILD AGE: {child_age}\n"
        f"SENSORY PROFILE:\n{sensory_profile}\n"
        f"PRIMARY ENVIRONMENT: {environment}\n\n"
        "Generate a structured sensory diet plan. Format:\n"
        "SENSORY PROFILE SUMMARY: (brief interpretation of the sensory needs)\n"
        "MORNING ROUTINE ACTIVITIES: (3-4 activities to prepare the nervous system for the day)\n"
        "MIDDAY REGULATION BREAKS: (2-3 short activities, 5-10 minutes each)\n"
        "AFTERNOON/WIND-DOWN ACTIVITIES: (3-4 calming activities for after school/high-demand periods)\n"
        "TOOLS & EQUIPMENT: (helpful sensory tools appropriate for this profile, with brief explanation)\n"
        "IMPORTANT NOTE: (remind caregiver to work with an OT to personalize and adjust)\n\n"
        "All activities should be practical, low-cost where possible, and appropriate for the age and environment. "
        "Base recommendations on occupational therapy sensory integration principles."
    )
    return _gemini_call(prompt, max_tokens=900)
