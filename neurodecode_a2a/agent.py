"""NeuroDecode A2A Agent — ADK agent definition."""
import os

from google.adk.agents import Agent

from tools.clinical import find_asd_resources
from tools.asd_reasoning import (
    suggest_interventions,
    get_de_escalation_steps,
    assess_escalation_risk,
)

_AGENT_INSTRUCTION = (
    "You are NeuroDecode Buddy, an AI caregiver support specialist for autism (ASD). "
    "You help caregivers find local ASD resources, get intervention strategies, "
    "de-escalation protocols, and escalation risk assessments. "
    "\n\n"
    "You have access to four tools:\n"
    "1. find_asd_resources — find clinics, therapists, schools, hospitals in any city worldwide\n"
    "2. suggest_interventions — get evidence-based strategies for a specific trigger\n"
    "3. get_de_escalation_steps — step-by-step protocol for active distress situations\n"
    "4. assess_escalation_risk — assess risk level from behavioral pattern descriptions\n"
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
    model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash-001"),
    description=(
        "ASD caregiver support agent — finds ASD resources worldwide (curated "
        "database for Jakarta, live Google Search for all other cities), "
        "provides intervention strategies, de-escalation protocols, and "
        "escalation risk assessments for caregivers of autistic children."
    ),
    instruction=_AGENT_INSTRUCTION,
    tools=[
        find_asd_resources,
        suggest_interventions,
        get_de_escalation_steps,
        assess_escalation_risk,
    ],
)
