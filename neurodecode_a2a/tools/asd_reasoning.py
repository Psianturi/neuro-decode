"""Tools: ASD reasoning via Gemini — suggest_interventions, get_de_escalation_steps,
assess_escalation_risk. All inputs are synthetic/descriptive text — no PHI."""
import logging
import os
import time

logger = logging.getLogger(__name__)

_ASD_SYSTEM = (
    "You are an expert ASD (Autism Spectrum Disorder) caregiver support specialist. "
    "You provide evidence-based, practical, non-diagnostic guidance to caregivers. "
    "You never diagnose. You always recommend professional consultation for clinical decisions. "
    "Respond in clear, structured, actionable language. "
    "If the caregiver's language context is Indonesian, respond in Indonesian."
)

_RETRYABLE = ("503", "429", "resource exhausted", "overloaded", "unavailable")


def _gemini_call(prompt, max_tokens=512):
    from google import genai
    from google.genai import types as genai_types
    client = genai.Client()
    last_exc = None
    for attempt in range(3):  # up to 3 attempts: 0s, 2s, 4s backoff
        try:
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=_ASD_SYSTEM,
                    temperature=0.3,
                    max_output_tokens=max_tokens,
                ),
            )
            return (response.text or "").strip()
        except Exception as exc:
            last_exc = exc
            msg = str(exc).lower()
            if any(code in msg for code in _RETRYABLE) and attempt < 2:
                wait = 2 * (attempt + 1)
                logger.warning("[asd_reasoning] Gemini %s on attempt %d, retry in %ds", exc, attempt + 1, wait)
                time.sleep(wait)
            else:
                break
    logger.warning("[asd_reasoning] Gemini call failed after retries: %s", last_exc)
    return f"Unable to generate response: {last_exc}"


def suggest_interventions(
    trigger_type: str,
    child_age: str = "unknown",
    sensory_profile: str = "",
) -> str:
    """
    Suggest evidence-based interventions for a specific ASD trigger type.

    Args:
        trigger_type: Description of what triggered the distress. Examples:
                      'loud noise', 'denied request', 'transition', 'crowded place',
                      'waiting too long', 'unexpected change'.
        child_age: Age or age range of the child, e.g. '5', '8-10', 'teenager'.
                   Default: 'unknown'.
        sensory_profile: Optional description of known sensory sensitivities,
                         e.g. 'sensitive to sound and light, seeks deep pressure'.

    Returns:
        A dict with 'interventions' list and 'rationale'.
    """
    profile_note = f"\nKnown sensory profile: {sensory_profile}" if sensory_profile else ""
    child_age = child_age or "unknown"
    prompt = (
        f"A caregiver needs intervention strategies for an autistic child (age: {child_age}).\n"
        f"Trigger: {trigger_type}{profile_note}\n\n"
        "Provide 3-5 specific, immediately actionable interventions. "
        "Format as a numbered list. Include rationale for each."
    )
    return _gemini_call(prompt)


def get_de_escalation_steps(
    situation_description: str,
    urgency_level: str = "medium",
) -> str:
    """
    Get step-by-step de-escalation protocol for an active distress situation.

    Args:
        situation_description: Plain text description of the current situation.
                               Example: 'Child is screaming and hitting walls after
                               being told no to screen time. Has been escalating for
                               5 minutes.'
        urgency_level: One of 'low', 'medium', 'high', 'critical'. Default: 'medium'.
                       Use 'critical' only if there is immediate safety risk.

    Returns:
        A dict with 'steps' list, 'safety_note', and 'follow_up'.
    """
    prompt = (
        f"URGENCY: {(urgency_level or 'medium').upper()}\n"
        f"Situation: {situation_description}\n\n"
        "Provide an immediate de-escalation protocol for the caregiver. "
        "Format:\n"
        "IMMEDIATE STEPS: (numbered, max 5 steps)\n"
        "SAFETY NOTE: (one sentence)\n"
        "FOLLOW UP: (what to do after the situation calms)"
    )
    text = _gemini_call(prompt, max_tokens=600)
    return text


def assess_escalation_risk(
    audio_pattern_description: str,
    visual_pattern_description: str = "",
    session_history_summary: str = "",
) -> str:
    """
    Assess escalation risk based on behavioral pattern descriptions.
    Simulates the NeuroDecode observer model reasoning in natural language.
    All inputs must be synthetic or de-identified descriptions — no real PHI.

    Args:
        audio_pattern_description: Description of vocal/audio patterns observed.
                                   Example: 'High-pitched repetitive vocalizations,
                                   increasing in frequency over last 10 minutes.'
        visual_pattern_description: Optional description of visual/movement patterns.
                                    Example: 'Rocking back and forth, covering ears,
                                    avoiding eye contact.'
        session_history_summary: Optional summary of recent session patterns.
                                 Example: 'Three sessions this week with audio triggers,
                                 all between 3-5pm after school.'

    Returns:
        A dict with 'risk_level' (low/medium/high/critical),
        'confidence', 'reasoning', and 'recommended_actions'.
    """
    history_note = f"\nRecent pattern history: {session_history_summary}" if session_history_summary else ""
    visual_note = f"\nVisual patterns: {visual_pattern_description}" if visual_pattern_description else ""

    prompt = (
        f"Behavioral observation for escalation risk assessment:\n"
        f"Audio patterns: {audio_pattern_description}"
        f"{visual_note}"
        f"{history_note}\n\n"
        "Assess the escalation risk. Respond in this exact format:\n"
        "RISK_LEVEL: [low/medium/high/critical]\n"
        "CONFIDENCE: [low/medium/high]\n"
        "REASONING: [2-3 sentences explaining the assessment]\n"
        "RECOMMENDED_ACTIONS: [3 specific actions for the caregiver right now]"
    )
    text = _gemini_call(prompt, max_tokens=400)
    return text
