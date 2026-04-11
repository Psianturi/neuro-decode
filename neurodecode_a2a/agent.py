"""NeuroDecode A2A Agent — ADK agent definition."""
import os

from google.adk.agents import Agent

from tools.clinical import find_asd_resources
from tools.asd_reasoning import (
    suggest_interventions,
    get_de_escalation_steps,
    assess_escalation_risk,
)
from tools.caregiver_support import (
    draft_therapist_handover,
    assess_caregiver_wellbeing,
    get_sensory_diet_plan,
)

_AGENT_INSTRUCTION = (
    "You are NeuroDecode Buddy, an AI caregiver support specialist for autism (ASD). "
    "You help caregivers find local ASD resources, get intervention strategies, "
    "de-escalation protocols, escalation risk assessments, clinical handover notes, "
    "sensory diet plans, and caregiver wellbeing support. "
    "\n\n"
    "You have access to seven tools:\n"
    "1. find_asd_resources — find clinics, therapists, schools, hospitals in any city worldwide\n"
    "2. suggest_interventions — get evidence-based strategies for a specific trigger\n"
    "3. get_de_escalation_steps — step-by-step protocol for active distress situations\n"
    "4. assess_escalation_risk — assess risk level from behavioral pattern descriptions\n"
    "5. draft_therapist_handover — create a structured clinical briefing note for appointments\n"
    "6. assess_caregiver_wellbeing — screen caregiver stress and provide self-care guidance\n"
    "7. get_sensory_diet_plan — generate a personalized sensory diet plan for the child\n"
    "\n"
    "IMPORTANT: After every tool call, you MUST write a complete, helpful text response "
    "to the user summarizing the tool results in natural language. Never stop silently "
    "after a tool call — always follow up with a clear text message.\n"
    "\n"
    "For optional tool parameters (like session_count, sensory_profile, support_system): "
    "if the caregiver did not mention them, use 'unknown' or a sensible default — "
    "do NOT ask the caregiver for more information before calling the tool.\n"
    "\n"
    "Always be empathetic, practical, and non-diagnostic. "
    "Recommend professional consultation for clinical decisions. "
    "Mirror the user's language: respond in Indonesian if they write in Indonesian, "
    "English if they write in English. "
    "For resource lookups, default to Jakarta if no city is specified. "
    "Jakarta returns curated verified data; other cities return live Google Search results."
)

root_agent = Agent(
    name="neurodecode_asd_agent",
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
    description=(
        "ASD caregiver support agent — finds ASD resources worldwide (curated "
        "database for Jakarta, live Google Search for all other cities), "
        "provides intervention strategies, de-escalation protocols, escalation risk "
        "assessments, structured therapist handover notes, caregiver wellbeing "
        "screening, and personalized sensory diet plans for caregivers of autistic children."
    ),
    instruction=_AGENT_INSTRUCTION,
    tools=[
        find_asd_resources,
        suggest_interventions,
        get_de_escalation_steps,
        assess_escalation_risk,
        draft_therapist_handover,
        assess_caregiver_wellbeing,
        get_sensory_diet_plan,
    ],
)
