"""
风险聚合节点（risk_aggregator_node.py）

此节点功能：
1. 将各专家产生的异常更新和新发现写入 anomalies_table；
2. 计算 LieIndex（谎言指数）：
   - 每条活跃专家异常事件的风险值 V = severity_base_score * confidence_weight
   - LieIndex = 100 * (1 - ∏(1 - V_i / 100))
   - 去掉维度权重系统，各异常直接通过独立风险叠加公式组合，自然不超过100
"""

from memory.anomaly_table import (
    add_specialist_results_as_anomalies,   # 将专家结果写入 anomalies_table
    apply_specialist_anomaly_updates,      # 更新旧异常状态
)
from state_schema import DialogueState
from utils.score_utils import (
    VALID_CONFIDENCES,
    VALID_SEVERITIES,
    effective_risk_value,
    combine_independent_risk_values,
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
    判断异常是否属于"活跃专家证据"
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
    """Convert repeated generic answers into a progressive risk signal.

    - 当前轮为泛泛回答时：风险值随 streak 递增（streak×7+3，上限50）
    - 当前轮已给出具体回答，但历史有泛泛记录：按 count 计算残余风险
    - 无泛泛历史时返回 None
    """
    current_generic = bool(state.get("generic_answer_flag"))
    streak = int(state.get("generic_answer_streak", 0) or 0)
    count = int(state.get("generic_answer_count", 0) or 0)
    specificity = str(state.get("specificity_level") or "MEDIUM").upper()
    reason = state.get("generic_answer_reason") or "历史回答多次符合常识但缺少具体场景、流程、边界或限制"

    if current_generic and streak >= 1:
        # 连续泛泛轮数越多，风险越高
        # streak=1→10, 2→17, 3→24, 4→31, 5→38, 6→45, 7→50
        risk_value = min(50.0, streak * 7.0 + 3.0)
        severity = "HIGH" if risk_value >= 25 else "MEDIUM"
        confidence = "HIGH"
    elif not current_generic and count > 0:
        # 虽然本轮不泛泛，但历史泛泛记录仍产生残余风险
        # count=1→5, 2→10, 3→15, 4→20, 5→25, 6→30
        base = min(50.0, count * 5.0)
        if specificity == "HIGH":
            factor = 0.6
        elif specificity == "MEDIUM":
            factor = 0.7
        else:
            factor = 1.0
        risk_value = round(max(3.0, base * factor), 1)
        severity = "HIGH" if risk_value >= 25 else "MEDIUM"
        confidence = "HIGH"
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
        "risk_value": round(risk_value, 1),
    }


def risk_aggregator_node(state: DialogueState) -> dict:
    """
    核心聚合函数：
    1. 应用专家异常更新
    2. 将专家产生的新异常写入表
    3. 提取活跃异常事件
    4. 计算 LieIndex（独立风险叠加公式，自然不超过100）
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

    # 4. 独立风险叠加计算 LieIndex
    #    去掉维度权重，每个活跃异常事件独立贡献风险分
    #    公式：LieIndex = 100 * (1 - ∏(1 - V_i / 100))
    #    效果：单维度连续泛泛 streak=6 得 45 分，多维度叠加自然不超过 100
    risk_values = [float(e["risk_value"]) for e in risk_events if e.get("risk_value", 0) > 0]
    if risk_values:
        lie_index = combine_independent_risk_values(risk_values)
    else:
        lie_index = 0.0

    # ----------------------------
    # 5. 维度分数（每个来源取最大 risk_value，用于展示）
    dimension_scores: dict[str, float] = {}
    for event in risk_events:
        source = event["source"]
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
