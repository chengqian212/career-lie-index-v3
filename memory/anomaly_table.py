"""异常表模块：管理对话中发现的异常记录

v3 改进：
- 支持五类来源：quick_detection / semantic / logical / domain / psycho_linguistic
- 统一使用 score 表示风险强度，删除 severity
- 新增 update_anomalies_status、get_active_anomalies 等函数
- 新增 apply_specialist_anomaly_updates、add_specialist_results_as_anomalies

v3.3 改进：
- 新增 followup_count 和 stop_followup 字段，用于追踪对该异常的追问次数
- get_active_anomalies 排除 stop_followup=True 的异常
"""

import logging
from typing import List, Dict, Optional

from utils.score_utils import (
    VALID_CONFIDENCES,
    VALID_SEVERITIES,
    effective_risk_value,
)

logger = logging.getLogger(__name__)


# ============================================================
# v3 新增常量
# ============================================================

VALID_SOURCES = [
    "quick_detection",
    "semantic",
    "logical",
    "domain",
    "psycho_linguistic",
]

UPDATE_TYPE_PRIORITY = {
    "reinforce": 4,
    "remain_unresolved": 3,
    "clarify": 2,
    "resolve": 1,
}

SOURCE_PRIORITY = {
    "semantic": 100,
    "logical": 100,
    "domain": 80,
    "psycho_linguistic": 60,
    "quick_detection": 40,
}

SPECIALIST_WRITE_ORDER = [
    "semantic",
    "logical",
    "domain",
    "psycho_linguistic",
]


# ============================================================
# 基础函数（保持兼容）
# ============================================================


def init_anomaly_table() -> List[Dict]:
    """初始化空异常表

    Returns:
        空异常表
    """
    return []


def normalize_anomaly(
    anomaly: dict,
    round_id: int,
    source: str,
    index: int | None = None,
) -> dict:
    """v3 新增：归一化异常记录格式
    
    补齐异常记录的所有必需字段，包括 v3.3 的 followup_count / stop_followup
    
    Args:
        anomaly: 原始异常数据
        round_id: 当前轮次
        source: 异常来源
        index: 在表中的索引（用于生成 anomaly_id）
    
    Returns:
        归一化后的异常记录
    """
    # 生成 anomaly_id
    anomaly_id = anomaly.get("anomaly_id")
    if not anomaly_id:
        if index is not None:
            anomaly_id = f"a_{round_id}_{source}_{index}"
        else:
            anomaly_id = f"a_{round_id}_{source}_unknown"
    
    # 确保 evidence 是 list
    evidence = anomaly.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    elif not isinstance(evidence, list):
        evidence = []
    
    # 确保 score 是 float
    score = float(anomaly.get("score", 0))
    severity = str(anomaly.get("severity") or "").strip().upper()
    confidence = str(anomaly.get("confidence") or "").strip().upper()
    has_valid_labels = severity in VALID_SEVERITIES and confidence in VALID_CONFIDENCES
    
    return {
        "anomaly_id": anomaly_id,
        "round_id": round_id,
        "source": source,
        "type": anomaly.get("type", "未分类"),
        "description": anomaly.get("description", ""),
        "evidence": evidence,
        "score": score,
        "severity": severity if has_valid_labels else "",
        "confidence": confidence if has_valid_labels else "",
        "risk_value": effective_risk_value(severity, confidence) if has_valid_labels else 0.0,
        "schema_error": "" if has_valid_labels else "anomaly_risk_labels_invalid",
        "status": anomaly.get("status", "unresolved"),
        "clarification_status": anomaly.get("clarification_status", "none"),
        "followup_needed": anomaly.get("followup_needed", True),
        "followup_count": anomaly.get("followup_count", 0),          # v3.3 新增
        "stop_followup": anomaly.get("stop_followup", False),        # v3.3 新增
        "related_facts": anomaly.get("related_facts", []),
        "created_round": round_id,
        "last_update_round": round_id,
        "update_history": [],
    }


def add_anomalies(
    anomalies_table: List[Dict],
    new_anomalies: List[Dict],
    round_id: int,
    source: str = "quick_detection",
) -> List[Dict]:
    """v3 改进：向异常表中添加新异常（使用归一化）

    每条异常格式：
    {
        "anomaly_id": str,
        "round_id": int,
        "source": str,
        "type": str,
        "description": str,
        "evidence": List[str],
        "score": float,
        "status": str,
        "clarification_status": str,
        "followup_needed": bool,
        "followup_count": int,            # v3.3
        "stop_followup": bool,            # v3.3
        "related_facts": List,
        "created_round": int,
        "last_update_round": int,
        "update_history": List,
    }

    Args:
        anomalies_table: 当前异常表
        new_anomalies: 新发现的异常列表
        round_id: 当前轮次
        source: 异常来源
    Returns:
        更新后的异常表
    """
    updated = list(anomalies_table)

    for idx, anomaly in enumerate(new_anomalies):
        normalized = normalize_anomaly(
            anomaly=anomaly,
            round_id=round_id,
            source=source,
            index=len(updated) + idx,
        )
        updated.append(normalized)

    return updated


def update_anomalies_status(
    anomalies_table: List[Dict],
    updates: List[Dict],
    round_id: int,
) -> List[Dict]:
    """v3 新增：更新旧异常状态
    
    根据专家的 anomaly_updates 更新现有异常的状态
    
    Args:
        anomalies_table: 当前异常表
        updates: 异常更新列表，每项包含：
            - target_anomaly_id: 目标异常ID
            - update_type: clarify|resolve|reinforce|remain_unresolved
            - explanation: 更新原因
            - new_score: 新分数
            - followup_needed: 是否仍需关注
        round_id: 当前轮次
    
    Returns:
        更新后的异常表
    """
    updated = list(anomalies_table)
    
    # 按 target_anomaly_id 分组更新
    updates_by_target: Dict[str, List[Dict]] = {}
    for update in updates:
        target_id = update.get("target_anomaly_id")
        if target_id:
            if target_id not in updates_by_target:
                updates_by_target[target_id] = []
            updates_by_target[target_id].append(update)
    
    # 对每个目标异常进行更新
    for i, anomaly in enumerate(updated):
        anomaly_id = anomaly.get("anomaly_id")
        if anomaly_id not in updates_by_target:
            continue
        
        # 获取该异常的所有更新
        target_updates = updates_by_target[anomaly_id]
        
        # v3: 如果有多个更新，按优先级裁决
        if len(target_updates) > 1:
            # 按优先级排序：reinforce > remain_unresolved > clarify > resolve
            # 同一 update_type 下，按 source 优先级
            def sort_key(u):
                update_type = u.get("update_type", "remain_unresolved")
                source = u.get("source", "quick_detection")
                score = float(u.get("new_score", 0))
                return (
                    UPDATE_TYPE_PRIORITY.get(update_type, 0),
                    SOURCE_PRIORITY.get(source, 0),
                    score,
                )
            
            final_update = max(target_updates, key=sort_key)
        else:
            final_update = target_updates[0]
        
        # 映射 update_type 到 status
        # v3 补充修改：先保留原分数，再根据 update_type 裁决分数
        old_score = float(anomaly.get("score", 0) or 0)
        raw_new_score = float(final_update.get("new_score", old_score) or 0)
        
        update_type = final_update.get("update_type", "remain_unresolved")
        followup_needed = final_update.get("followup_needed", True)
        explanation = final_update.get("explanation", "")
        
        if update_type == "resolve":
            status = "resolved"
            clarification_status = "sufficient"
            followup_needed = False
            new_score = min(20.0, raw_new_score)  # resolve：分数最多 20
        elif update_type == "clarify":
            status = "unresolved"
            clarification_status = "partial"
            followup_needed = True
            new_score = max(30.0, raw_new_score)  # clarify：分数至少 30
        elif update_type == "reinforce":
            status = "reinforced"
            clarification_status = "insufficient"
            followup_needed = True
            new_score = max(old_score, raw_new_score)  # reinforce：不能比原分更低
        else:  # remain_unresolved
            status = "unresolved"
            clarification_status = "none"
            followup_needed = True
            new_score = max(old_score, raw_new_score)  # remain_unresolved：不能比原分更低
        
        # 更新异常记录
        updated[i] = dict(anomaly)
        updated[i]["status"] = status
        updated[i]["clarification_status"] = clarification_status
        updated[i]["followup_needed"] = followup_needed
        updated[i]["score"] = new_score
        updated[i]["last_update_round"] = round_id
        
        # 追加更新历史
        update_history_entry = {
            "round_id": round_id,
            "update_type": update_type,
            "explanation": explanation,
            "new_score": new_score,
            "followup_needed": followup_needed,
        }
        if "update_history" not in updated[i]:
            updated[i]["update_history"] = []
        updated[i]["update_history"].append(update_history_entry)
    
    return updated


def get_active_anomalies(anomalies_table: List[Dict]) -> List[Dict]:
    """v3.3 改进：获取仍需关注的异常

    排除 stop_followup=True 的异常，即便其状态为 unresolved / reinforced

    Args:
        anomalies_table: 异常表
    
    Returns:
        仍需关注的异常列表
    """
    return [
        a for a in anomalies_table
        if a.get("stop_followup") is not True
        and (
            a.get("status") in ["unresolved", "reinforced"]
            or a.get("followup_needed") is True
        )
    ]


def count_unresolved(anomalies_table: List[Dict]) -> int:
    """统计未解决的异常数量

    v3.3 改进：统计 active anomalies（仍需关注的异常，排除 stop_followup=True）

    Args:
        anomalies_table: 异常表
    Returns:
        未解决异常数量
    """
    return len(get_active_anomalies(anomalies_table))


def get_unresolved_anomalies(anomalies_table: List[Dict]) -> List[Dict]:
    """获取所有未解决的异常

    v3.3 改进：返回 active anomalies

    Args:
        anomalies_table: 异常表
    Returns:
        未解决的异常列表
    """
    return get_active_anomalies(anomalies_table)


# ============================================================
# v3 新增：专家结果处理函数
# ============================================================


def apply_specialist_anomaly_updates(
    anomalies_table: List[Dict],
    specialist_results: List[Dict],
    round_id: int,
) -> List[Dict]:
    """v3 新增：应用专家的 anomaly_updates

    1. 遍历 specialist_results
    2. 提取 agent 和 anomaly_updates
    3. 按 target_anomaly_id 分组
    4. 对同一个 target_anomaly_id 的多个更新进行优先级裁决
    5. 选择最高优先级更新
    6. 更新 anomalies_table

    优先级规则：
    - reinforce > remain_unresolved > clarify > resolve
    - 同一 update_type 下：semantic = logical > domain > psycho_linguistic > quick_detection
    
    Args:
        anomalies_table: 当前异常表
        specialist_results: 专家结果列表
        round_id: 当前轮次
    
    Returns:
        更新后的异常表
    """
    # 收集所有更新
    all_updates: List[Dict] = []
    
    for result in specialist_results:
        if not isinstance(result, dict):
            continue
        
        agent = result.get("agent", "")
        anomaly_updates = result.get("anomaly_updates", [])
        
        for update in anomaly_updates:
            if isinstance(update, dict):
                update["source"] = agent
                all_updates.append(update)
    
    # 应用更新
    return update_anomalies_status(
        anomalies_table=anomalies_table,
        updates=all_updates,
        round_id=round_id,
    )


def convert_legacy_items_to_anomalies(legacy_items: List[Dict], result: Dict) -> List[Dict]:
    """Convert legacy evidence-like items to anomalies.

    用于兼容旧版 expert 输出格式

    Args:
        legacy_items: legacy item list
        result: 专家结果，包含 agent 和 score
    
    Returns:
        转换后的 anomalies 列表
    """
    source = result.get("agent", "unknown")
    base_score = result.get("score", 0)
    
    anomalies = []
    for legacy_item in legacy_items:
        if not isinstance(legacy_item, dict):
            continue
        
        anomalies.append({
            "source": source,
            "type": legacy_item.get("type", "specialist_evidence"),
            "description": legacy_item.get("description", ""),
            "evidence": legacy_item.get("evidence", []),
            "severity": legacy_item.get("severity"),
            "confidence": legacy_item.get("confidence"),
            "score": base_score,
            "related_facts": legacy_item.get("related_facts", []),
        })
    
    return anomalies


def add_specialist_results_as_anomalies(
    anomalies_table: List[Dict],
    specialist_results: List[Dict],
    round_id: int,
) -> List[Dict]:
    """v3 新增：将专家的 evidence_list/new_anomalies 添加到异常表

    处理顺序：semantic → logical → domain → psycho_linguistic

    Args:
        anomalies_table: 当前异常表
        specialist_results: 专家结果列表
        round_id: 当前轮次
    
    Returns:
        更新后的异常表
    """
    updated = list(anomalies_table)
    
    # 按指定顺序处理
    for source in SPECIALIST_WRITE_ORDER:
        # 查找该专家的结果
        result = None
        for r in specialist_results:
            if isinstance(r, dict) and r.get("agent") == source:
                result = r
                break
        
        if not result:
            continue
        
        # 优先读取 new_anomalies
        new_anomalies = result.get("evidence_list", [])
        if not new_anomalies:
            new_anomalies = result.get("new_anomalies", [])
        
        # No legacy field fallback; evidence_list is the canonical source.
        if not new_anomalies:
            new_anomalies = []
        
        # 写入 anomalies_table
        # 同一 round_id + source + type + evidence 相同则不重复写入
        for idx, new_anomaly in enumerate(new_anomalies):
            severity = str(new_anomaly.get("severity") or "").strip().upper()
            confidence = str(new_anomaly.get("confidence") or "").strip().upper()
            if severity not in VALID_SEVERITIES or confidence not in VALID_CONFIDENCES:
                logger.warning(
                    "[anomaly_table] dropped specialist anomaly with invalid "
                    f"severity/confidence: source={source}, "
                    f"type={new_anomaly.get('type', '')}, "
                    f"severity={new_anomaly.get('severity')}, "
                    f"confidence={new_anomaly.get('confidence')}"
                )
                continue
            # 检查是否重复
            is_duplicate = False
            atype = new_anomaly.get("type", "")
            evidence = new_anomaly.get("evidence", [])
            
            for existing in updated:
                if (existing.get("round_id") == round_id
                    and existing.get("source") == source
                    and existing.get("type") == atype
                    and existing.get("evidence") == evidence):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                normalized = normalize_anomaly(
                    anomaly=new_anomaly,
                    round_id=round_id,
                    source=source,
                    index=len(updated),
                )
                updated.append(normalized)
    
    return updated

