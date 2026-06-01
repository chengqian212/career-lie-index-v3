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
    "process_sequence",
    "boundary_judgment",
    "real_constraint",
    "counterexample",
    "term_clarification",
    "output_evidence",
}

ALLOWED_PROBE_ANGLES = {
    "process_sequence",
    "boundary_judgment",
    "real_constraint",
    "counterexample",
    "term_clarification",
    "output_evidence",
}

PROBE_ANGLE_ORDER = [
    "process_sequence",
    "boundary_judgment",
    "real_constraint",
    "counterexample",
    "term_clarification",
    "output_evidence",
]

PROBE_ANGLE_HINTS = {
    "process_sequence": "换到过程顺序角度，问对方一般怎么判断先做什么、后做什么",
    "boundary_judgment": "换到边界判断角度，问哪些情况需要收住、转介、升级或避免继续推进",
    "real_constraint": "换到真实限制角度，问记录、时间、流程、协作、规范或现实约束",
    "counterexample": "换到反例和卡点角度，问遇到常规方法不管用时通常怎么处理",
    "term_clarification": "换到术语澄清角度，问对方自己说的关键词在实际场景里具体指什么",
    "output_evidence": "换到产出证据角度，问工作结束后通常留下什么记录、结果或复盘",
}


def normalize_followup_strategy(strategy: str, has_risk: bool = False) -> str:
    """Return a valid follow-up strategy with a conservative fallback."""
    if strategy in ALLOWED_FOLLOWUP_STRATEGIES:
        return strategy
    return "light_clarification" if has_risk else "daily_routine"


def normalize_probe_angle(angle: str, used_angles: list[str] | None = None) -> str:
    """Return a valid probe angle, rotating away from angles already used."""
    normalized = str(angle or "").strip()
    if normalized not in ALLOWED_PROBE_ANGLES:
        normalized = PROBE_ANGLE_ORDER[0]

    used = [item for item in (used_angles or []) if item in ALLOWED_PROBE_ANGLES]
    if normalized in used and len(set(used)) < len(ALLOWED_PROBE_ANGLES):
        for candidate in PROBE_ANGLE_ORDER:
            if candidate not in used:
                return candidate
    return normalized


def probe_angle_hint(angle: str) -> str:
    """Human-readable generation hint for a probe angle."""
    return PROBE_ANGLE_HINTS.get(str(angle or "").strip(), "换一个新的经验细节角度追问")

