"""
风险聚合节点（risk_aggregator_node.py）

此节点功能：
1. 将各专家产生的异常更新和新发现写入 anomalies_table；
2. 计算 LieIndex（谎言指数）：
   - 每条活跃专家异常事件的风险值 V = severity_base_score * confidence_weight
   - LieIndex = 100 * (1 - product(1 - V_i / 100))
"""

from memory.anomaly_table import (
    add_specialist_results_as_anomalies,   # 将专家结果写入 anomalies_table
    apply_specialist_anomaly_updates,      # 更新旧异常状态
)
from state_schema import DialogueState
from utils.score_utils import (
    VALID_CONFIDENCES,
    VALID_SEVERITIES,
    combine_independent_risk_values,      # 对独立风险值做加权归一化
    effective_risk_value,                 # 根据 severity/confidence 计算风险值
)

# 这些来源才会被纳入风险聚合计算
RISK_EVIDENCE_SOURCES = {
    "quick_preanalysis",
    "experience_density",
    "semantic",
    "logical",
    "domain",
    "psycho_linguistic",
}

# 显示名称映射（用于生成日志或可视化）
SOURCE_DISPLAY_NAMES = {
    "quick_preanalysis": "表层检测",
    "experience_density": "经验密度",
    "semantic": "语义一致性",
    "logical": "逻辑时间线",
    "domain": "职业常识",
    "psycho_linguistic": "心理语言",
}

VAGUE_SIGNAL_TYPES = {
    "vague",
    "lack_of_detail",
    "vague_expression",
    "avoidance",
}

def _is_active_specialist_evidence(anomaly: dict) -> bool:
    """
    判断异常是否属于“活跃专家证据”
    条件：
    1. anomaly 是 dict
    2. source 属于 RISK_EVIDENCE_SOURCES
    3. stop_followup != True
    4. status != "resolved"
    """
    if not isinstance(anomaly, dict):
        return False
    if anomaly.get("source") not in RISK_EVIDENCE_SOURCES:
        return False
    if anomaly.get("stop_followup") is True:
        return False
    if anomaly.get("status") == "resolved":
        return False
    return True

def _risk_events_from_anomalies(anomalies_table: list[dict]) -> list[dict]:
    """
    从 anomalies_table 中提取活跃专家事件，并计算风险值
    逻辑：
    1. 遍历 anomalies_table
    2. 只保留活跃专家异常
    3. 校验 severity/confidence 是否合法
    4. 计算 risk_value（若异常未提供，则使用 effective_risk_value）
    """
    events = []

    for anomaly in anomalies_table:
        if not _is_active_specialist_evidence(anomaly):
            continue

        severity = str(anomaly.get("severity") or "").strip().upper()
        confidence = str(anomaly.get("confidence") or "").strip().upper()
        if severity not in VALID_SEVERITIES or confidence not in VALID_CONFIDENCES:
            continue

        if "risk_value" in anomaly:
            risk_value = float(anomaly.get("risk_value") or 0.0)
        else:
            risk_value = effective_risk_value(severity, confidence)
        if risk_value <= 0:
            continue

        # 生成标准化事件对象
        events.append({
            "source": anomaly.get("source", ""),
            "display_source": SOURCE_DISPLAY_NAMES.get(
                anomaly.get("source", ""),
                anomaly.get("source", ""),
            ),
            "anomaly_id": anomaly.get("anomaly_id", ""),
            "type": anomaly.get("type", ""),
            "description": anomaly.get("description", ""),
            "severity": severity,
            "confidence": confidence,
            "risk_value": risk_value,
        })

    return events


def _experience_density_event(state: DialogueState) -> dict | None:
    """Convert repeated generic answers into a visible accumulating risk signal."""
    current_generic = bool(state.get("generic_answer_flag"))
    streak = int(state.get("generic_answer_streak", 0) or 0)
    count = int(state.get("generic_answer_count", 0) or 0)
    density = str(state.get("experience_density") or "MEDIUM").upper()
    specificity = str(state.get("specificity_level") or "MEDIUM").upper()
    reason = state.get("generic_answer_reason") or "历史回答多次符合常识但缺少具体场景、流程、边界或限制"

    if current_generic and (streak >= 4 or count >= 5):
        severity = "MEDIUM"
        confidence = "HIGH"
        risk_value = 24.0
    elif current_generic and (streak >= 3 or count >= 4):
        severity = "MEDIUM"
        confidence = "HIGH"
        risk_value = 20.0
    elif current_generic and streak >= 2:
        severity = "LOW"
        confidence = "HIGH"
        risk_value = 16.0
    elif current_generic and density == "LOW":
        severity = "LOW"
        confidence = "LOW"
        risk_value = 8.0
    elif not current_generic and count > 0:
        severity = "LOW" if count < 5 else "MEDIUM"
        confidence = "HIGH"
        risk_value = _residual_experience_risk(count, specificity)
    else:
        return None

    return {
        "source": "experience_density",
        "display_source": SOURCE_DISPLAY_NAMES["experience_density"],
        "anomaly_id": "",
        "type": "generic_answer_low_experience_density",
        "description": reason,
        "severity": severity,
        "confidence": confidence,
        "risk_value": risk_value,
    }


def _residual_experience_risk(generic_count: int, specificity: str) -> float:
    """
    Keep discounted historical experience-density risk after a concrete answer.

    A later concrete detail can reduce prior generic-answer risk, but it should not
    erase the pattern completely.
    """
    if generic_count >= 5:
        base = 18.0
    elif generic_count >= 3:
        base = 16.0
    elif generic_count == 2:
        base = 12.0
    else:
        base = 8.0

    if specificity == "HIGH":
        factor = 0.65
    elif specificity == "MEDIUM":
        factor = 0.8
    else:
        factor = 1.0
    return round(max(3.0, base * factor), 1)


def _vagueness_persistence_event(anomalies_table: list[dict]) -> dict | None:
    """
    Treat repeated vague/lack-of-detail signals as a separate persistence risk.

    This covers cases where each answer is logically correct but the user keeps
    avoiding concrete business, workflow, object, boundary, or output details.
    """
    active_vague = [
        anomaly for anomaly in anomalies_table
        if _is_active_specialist_evidence(anomaly)
        and str(anomaly.get("type", "")).strip() in VAGUE_SIGNAL_TYPES
    ]
    count = len(active_vague)
    if count < 2:
        return None

    if count >= 5:
        risk_value = 22.0
        severity = "MEDIUM"
    elif count >= 3:
        risk_value = 18.0
        severity = "MEDIUM"
    else:
        risk_value = 12.0
        severity = "LOW"

    descriptions = [
        str(item.get("description", "")).strip()
        for item in active_vague[-3:]
        if str(item.get("description", "")).strip()
    ]
    return {
        "source": "experience_density",
        "display_source": SOURCE_DISPLAY_NAMES["experience_density"],
        "anomaly_id": "",
        "type": "persistent_vague_or_low_detail_answers",
        "description": "连续回答缺少具体业务、流程、对象或产出细节"
        + (f"；近期线索：{'；'.join(descriptions)}" if descriptions else ""),
        "severity": severity,
        "confidence": "HIGH",
        "risk_value": risk_value,
    }

def risk_aggregator_node(state: DialogueState) -> dict:
    """
    核心聚合函数：
    1. 应用专家异常更新
    2. 将专家产生的新异常写入表
    3. 提取活跃异常事件
    4. 计算 LieIndex
    5. 生成维度分数与风险解释
    """
    round_id = state.get("round_id", 1)
    anomalies_table = state.get("anomalies_table", [])
    specialist_results = state.get("specialist_results", [])

    # ----------------------------
    # 1. 更新旧异常状态（clarify/resolve/reinforce/remain_unresolved）
    updated_anomalies_table = apply_specialist_anomaly_updates(
        anomalies_table=anomalies_table,
        specialist_results=specialist_results,
        round_id=round_id,
    )

    # 2. 写入专家产生的新异常
    updated_anomalies_table = add_specialist_results_as_anomalies(
        anomalies_table=updated_anomalies_table,
        specialist_results=specialist_results,
        round_id=round_id,
    )

    # 3. 提取活跃专家事件，计算单条风险值
    risk_events = _risk_events_from_anomalies(updated_anomalies_table)
    generic_event = _experience_density_event(state)
    if generic_event:
        risk_events.append(generic_event)
    vague_event = _vagueness_persistence_event(updated_anomalies_table)
    if vague_event:
        risk_events.append(vague_event)

    # 4. LieIndex 聚合公式（独立事件概率叠加）
    lie_index = combine_independent_risk_values([
        event["risk_value"] for event in risk_events
    ])

    # ----------------------------
    # 5. 维度分数计算（每个来源取最大 risk_value）
    dimension_scores: dict[str, float] = {}
    for event in risk_events:
        source = event["display_source"]
        dimension_scores[source] = round(
            max(dimension_scores.get(source, 0.0), event["risk_value"]),
            1,
        )

    # 6. 风险解释文本
    risk_explanation = [
        (
            f"{event['display_source']}:{event['type']} "
            f"severity={event['severity']} "
            f"confidence={event['confidence']} "
            f"V={event['risk_value']:.1f}"
        )
        for event in risk_events
    ]
    if not risk_explanation:
        risk_explanation.append("No active specialist evidence; LieIndex=0.")

    # ----------------------------
    # 7. 返回更新状态
    return {
        "lie_index": lie_index,
        "dimension_scores": dimension_scores,
        "risk_explanation": risk_explanation,
        "anomalies_table": updated_anomalies_table,
    }
