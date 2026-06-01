"""
风险评分工具：基于 severity（严重度）和 confidence（置信度）标签计算风险值
"""

from typing import Any, Dict, List

import config

# 各严重度对应基础分值
SEVERITY_BASE_SCORE = {
    "CRITICAL": 45.0,  # 极高风险
    "HIGH": 25.0,      # 高风险
    "MEDIUM": 10.0,    # 中等风险
    "LOW": 3.0,        # 低风险
}

# 各置信度对应权重
CONFIDENCE_WEIGHT = {
    "CRITICAL": 1.0,
    "HIGH": 0.8,
    "MEDIUM": 0.5,
    "LOW": 0.2,
}

# 合法严重度和置信度集合
VALID_SEVERITIES = set(SEVERITY_BASE_SCORE)
VALID_CONFIDENCES = set(CONFIDENCE_WEIGHT)
# 快速风险标签仅使用 HIGH / LOW
QUICK_CONFIDENCES = {"HIGH", "LOW"}


def normalize_severity(value: Any, default: str = "LOW") -> str:
    """
    标准化严重度标签

    Args:
        value: 原始严重度值
        default: 默认值（非法时使用）

    Returns:
        标准化后的严重度字符串
    """
    label = str(value or "").strip().upper()
    return label if label in VALID_SEVERITIES else default


def normalize_confidence(value: Any, default: str = "LOW") -> str:
    """
    标准化置信度标签

    Args:
        value: 原始置信度值
        default: 默认值（非法时使用）

    Returns:
        标准化后的置信度字符串
    """
    label = str(value or "").strip().upper()
    return label if label in VALID_CONFIDENCES else default


def effective_risk_value(severity: Any, confidence: Any) -> float:
    """
    计算单条风险的有效分值（基础分 * 权重）

    Args:
        severity: 严重度标签
        confidence: 置信度标签

    Returns:
        float: 风险值
    """
    normalized_severity = normalize_severity(severity)
    normalized_confidence = normalize_confidence(confidence)
    return SEVERITY_BASE_SCORE[normalized_severity] * CONFIDENCE_WEIGHT[normalized_confidence]


def combine_independent_risk_values(values: List[float]) -> float:
    """
    组合多个独立风险值，类似概率非事件相乘计算总体风险
    公式: 1 - ∏(1 - value/100)

    Args:
        values: 多个风险值列表（0-100）

    Returns:
        float: 总体风险值（0-100）
    """
    product = 1.0
    for value in values:
        # 限制每个值在 0-100 之间
        bounded = max(0.0, min(100.0, float(value or 0)))
        product *= 1.0 - (bounded / 100.0)
    # 最终风险值 = 100 * (1 - product)，保留一位小数
    return round(max(0.0, min(100.0, 100.0 * (1.0 - product))), 1)


def normalize_quick_risk_labels(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    对快速风险标签进行标准化，仅允许 HIGH / LOW
    并在非法时记录 schema 错误

    Args:
        result: 原始快速风险字典，包含 severity 和 confidence

    Returns:
        Dict: 标准化后的字典，可能含 schema_error
    """
    normalized = dict(result)
    severity = str(normalized.get("severity") or "").strip().upper()
    confidence = str(normalized.get("confidence") or "").strip().upper()

    surface_risk_score = float(normalized.get("surface_risk_score") or 0)
    anomalies = normalized.get("anomalies", [])
    has_anomalies = isinstance(anomalies, list) and bool(anomalies)

    if severity not in VALID_SEVERITIES:
        if surface_risk_score >= 70:
            severity = "CRITICAL"
        elif surface_risk_score >= 50:
            severity = "HIGH"
        elif surface_risk_score >= 20 or has_anomalies:
            severity = "MEDIUM"
        else:
            severity = "LOW"
        normalized["severity"] = severity

    if confidence not in QUICK_CONFIDENCES:
        has_assessment_text = bool(
            normalized.get("quick_fact_summary")
            or normalized.get("quick_signal_summary")
            or normalized.get("facts")
            or has_anomalies
        )
        confidence = "HIGH" if has_assessment_text else "LOW"
        normalized["confidence"] = confidence

    schema_errors = []
    if severity not in VALID_SEVERITIES:
        schema_errors.append("missing_or_invalid_severity")
    else:
        normalized["severity"] = severity

    if confidence not in QUICK_CONFIDENCES:
        schema_errors.append("missing_or_invalid_confidence")
    else:
        normalized["confidence"] = confidence

    if schema_errors:
        normalized["schema_error"] = "quick_risk_labels_invalid"
        normalized["schema_errors"] = schema_errors
    return normalized


def normalize_evidence_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    标准化专家证据项：
        - 检查 severity / confidence 是否合法
        - 计算风险值

    Args:
        item: 单个证据字典，可能包含 severity 和 confidence

    Returns:
        Dict: 标准化证据字典，若非法含 schema_error
    """
    severity = str(item.get("severity") or "").strip().upper()
    confidence = str(item.get("confidence") or "").strip().upper()

    normalized = dict(item)
    schema_errors = []
    if severity not in VALID_SEVERITIES:
        schema_errors.append("missing_or_invalid_severity")
    if confidence not in VALID_CONFIDENCES:
        schema_errors.append("missing_or_invalid_confidence")

    if schema_errors:
        normalized["schema_error"] = "specialist_evidence_labels_invalid"
        normalized["schema_errors"] = schema_errors
        return normalized

    normalized["severity"] = severity
    normalized["confidence"] = confidence
    normalized["risk_value"] = effective_risk_value(severity, confidence)
    return normalized


def normalize_specialist_result(result: Any, agent: str) -> Dict[str, Any]:
    """
    标准化专家结果：
        - 规范每条证据
        - 丢弃非法证据并记录
        - 计算总评分（score = 最大 risk_value）

    Args:
        result: 原始专家输出
        agent: 专家名称

    Returns:
        Dict: 标准化后的专家结果
    """
    if not isinstance(result, dict):
        result = {}

    normalized = dict(result)
    normalized["agent"] = agent

    evidence_list = normalized.get("evidence_list", [])
    if not isinstance(evidence_list, list):
        evidence_list = []

    # 标准化每个证据项
    normalized_items = [
        normalize_evidence_item(item)
        for item in evidence_list
        if isinstance(item, dict)
    ]
    invalid_items = [item for item in normalized_items if item.get("schema_error")]
    normalized["evidence_list"] = [
        item for item in normalized_items
        if not item.get("schema_error")
    ]

    # 记录被丢弃的证据
    if invalid_items:
        normalized["schema_error"] = "specialist_evidence_dropped"
        normalized["dropped_evidence_count"] = len(invalid_items)
        normalized["dropped_evidence"] = invalid_items

    # 总分 = 有效证据中最大 risk_value
    normalized["score"] = round(
        max((item["risk_value"] for item in normalized["evidence_list"]), default=0.0),
        1,
    )
    return normalized


def determine_risk_level(lie_index: float) -> str:
    """
    根据谎言指数确定风险等级（低 / 中 / 高）

    Args:
        lie_index: 综合风险值

    Returns:
        str: 风险等级中文
    """
    if lie_index <= config.RISK_LOW_THRESHOLD:
        return "低"
    if lie_index <= config.RISK_HIGH_THRESHOLD:
        return "中"
    return "高"
