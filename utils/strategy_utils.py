"""Shared follow-up strategy helpers."""

ALLOWED_FOLLOWUP_STRATEGIES = {
    "daily_routine",
    "entry_experience",
    "work_style",
    "recent_memory",
    "light_clarification",
    "topic_shift_buffer",
    "experience_probe",
    "knowledge_probe",
    "tool_workflow_probe",
    "scenario_judgment_probe",
}


def normalize_followup_strategy(strategy: str, has_risk: bool = False) -> str:
    """Return a valid follow-up strategy with a conservative fallback."""
    if strategy in ALLOWED_FOLLOWUP_STRATEGIES:
        return strategy
    return "light_clarification" if has_risk else "daily_routine"

