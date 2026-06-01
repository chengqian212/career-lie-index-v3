"""轻量级路由监督器（Lightweight Routing Supervisor）
作用：根据当前对话状态决定是否调用专家，以及调用哪些专家。
"""
import random

import logging
from langchain_core.messages import HumanMessage
from config import ENABLE_ON_DEMAND_SPECIALISTS
from llm_client import get_llm
from memory.anomaly_table import count_unresolved
from prompts import LIGHTWEIGHT_ROUTING_SUPERVISOR_PROMPT
from state_schema import DialogueState
from utils.strategy_utils import normalize_followup_strategy
from utils.json_utils import extract_json_from_text
from utils.text_utils import clean_llm_output, format_anomalies_table, format_facts_table

logger = logging.getLogger(__name__)

# 定义合法专家列表
VALID_SPECIALISTS = ["semantic", "logical", "domain", "psycho_linguistic"]

# 默认核心专家（语义 + 逻辑），用于兜底
DEFAULT_CORE_SPECIALISTS = ["semantic", "logical"]

def _has_valid_quick_labels(state: DialogueState) -> bool:
    """
    检查当前状态的快速风险标签是否有效
    输入：
        state: 当前 DialogueState
    输出：
        True/False
    说明：
        - severity 必须在 CRITICAL/HIGH/MEDIUM/LOW
        - confidence 必须在 HIGH/LOW
    """
    severity = str(state.get("severity") or "").strip().upper()
    confidence = str(state.get("confidence") or "").strip().upper()
    return severity in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} and confidence in {"HIGH", "LOW"}


def should_skip_specialist(state: DialogueState) -> bool:
    """
    规则判断是否可以跳过专家节点
    输入：
        state: 当前 DialogueState
    输出：
        True / False
    说明：
        通过 severity/confidence/异常状态/事实数量判断
        - CRITICAL/HIGH -> 不跳过
        - 有未解决历史异常 -> 不跳过
        - 核心事实且中等风险 -> 不跳过
        - 低风险且无新核心事实 -> 跳过
        - facts_table 小于 3 条 -> 跳过
    """
    severity = str(state.get("severity") or "").strip().upper()
    confidence = str(state.get("confidence") or "").strip().upper()
    anomalies_table = state.get("anomalies_table", [])
    current_facts = state.get("current_facts", [])
    facts_table = state.get("facts_table", [])
    has_new_fact = state.get("has_new_fact", False)
    round_id = state.get("round_id", 1)

    # 筛选历史未解决异常
    historical_unresolved = [
        a for a in anomalies_table
        if isinstance(a, dict)
        and a.get("round_id") != round_id
        and a.get("stop_followup") is not True
        and (
            a.get("status") in ("unresolved", "reinforced")
            or a.get("followup_needed") is True
        )
    ]

    # 第一层硬红线判断
    if severity in {"CRITICAL", "HIGH"}:
        return False
    if historical_unresolved:
        return False

    # 核心事实判断
    core_slots = {"occupation", "role", "company", "time_stage", "experience", "work_content"}
    has_core_new_fact = any(
        isinstance(f, dict) and f.get("slot") in core_slots
        for f in current_facts
    )
    if has_core_new_fact and severity == "MEDIUM" and confidence == "HIGH":
        return False

    # 安全释放条件
    if has_new_fact and not has_core_new_fact and severity == "LOW":
        return True
    if not has_new_fact and severity == "LOW":
        return True
    if len(facts_table) < 3:
        return True

    return random.random() < 0.5  # 50%概率跳过专家


def infer_default_specialists(state: DialogueState) -> list[str]:
    """
    根据当前状态推断默认专家列表（兜底逻辑）
    输入：
        state: DialogueState
    输出：
        selected: list[str] 要调用的专家名
    说明：
        - 有新事实或事实表>=2条 -> 默认核心专家
        - 异常文本中含 domain 或心理线索 -> 添加 domain/psycho_linguistic
        - 表层风险分>=50 且没有选择 -> 强制核心专家
        - 兜底选择默认核心专家
    """
    current_anomalies = state.get("current_anomalies", [])
    has_new_fact = state.get("has_new_fact", False)
    facts_table = state.get("facts_table", [])
    surface_risk_score = state.get("surface_risk_score", 0)

    selected: list[str] = []

    if has_new_fact or len(facts_table) >= 2:
        selected.extend(DEFAULT_CORE_SPECIALISTS)

    anomaly_types = [
        str(a.get("type", ""))
        for a in current_anomalies
        if isinstance(a, dict)
    ]
    anomaly_text = " ".join(anomaly_types)

    if any(k in anomaly_text for k in ["职业常识", "岗位职责", "domain", "responsibility", "industry"]):
        selected.append("domain")

    if any(k in anomaly_text for k in ["回避", "模糊", "过度解释", "答非所问", "细节缺失", "self_correction", "avoidance", "vague"]):
        selected.append("psycho_linguistic")

    if surface_risk_score >= 50 and not selected:
        selected.extend(DEFAULT_CORE_SPECIALISTS)

    if not selected:
        selected.extend(DEFAULT_CORE_SPECIALISTS)

    # 去重返回
    return list(dict.fromkeys(selected))


def invoke_router_with_retry(llm, prompt_input: dict, max_retries: int = 2):
    """
    调用 LLM 做路由决策，并在 JSON 解析失败时进行重试
    输入：
        llm: LLM 客户端对象
        prompt_input: prompt 所需输入字典
        max_retries: 最大重试次数
    输出：
        dict 或 None: LLM 返回的 JSON 结果
    说明：
        - 每轮失败会提示 LLM 输出标准 JSON
        - 如果重试后仍失败，返回 None
    """
    for attempt in range(max_retries + 1):
        prompt_value = LIGHTWEIGHT_ROUTING_SUPERVISOR_PROMPT.invoke(prompt_input)
        messages = prompt_value.to_messages()

        if attempt > 0:
            messages.append(
                HumanMessage(content=(
                    "你上一次输出不是合法 JSON，无法解析。"
                    "请重新输出，只输出一个标准 JSON 对象。"
                    "不要 Markdown，不要解释，不要代码块。"
                    "必须包含字段：selected_specialists, routing_reason, "
                    "priority_issue, followup_strategy。"
                    "selected_specialists 只能从 semantic、logical、domain、"
                    "psycho_linguistic 中选择。"
                ))
            )

        response = llm.invoke(messages)
        raw_output = clean_llm_output(response.content)

        result = extract_json_from_text(raw_output)
        if isinstance(result, dict):
            if attempt > 0:
                logger.info("[路由监督节点] retry 后 JSON 解析成功")
            return result

        # 激进清理尝试
        cleaned_again = clean_llm_output(raw_output, aggressive=True)
        result = extract_json_from_text(cleaned_again)
        if isinstance(result, dict):
            if attempt > 0:
                logger.info("[路由监督节点] retry 后激进清理解析成功")
            return result

        logger.warning(
            f"[路由监督节点] 第 {attempt + 1} 次 JSON 解析失败"
            f"（输出长度: {len(raw_output)} 字符，预览: {raw_output[:200]}...）"
        )

    return None


def lightweight_routing_supervisor_node(state: DialogueState) -> dict:
    """
    路由监督器主节点
    输入：
        state: DialogueState
    输出：
        dict: 包含 routing_decision, selected_specialists, followup_strategy 等
    功能：
        1. 判断是否启用按需专家
        2. 检查快速预分析标签是否有效
        3. 规则跳过专家 / 调用 LLM 选择专家
        4. 如果 LLM 未返回专家，使用 infer_default_specialists 兜底
        5. 规范化 followup_strategy
    """
    if not ENABLE_ON_DEMAND_SPECIALISTS:
        # 未启用按需模式，直接调用全部专家
        selected = ["semantic", "logical", "domain", "psycho_linguistic"]
        return {
            "routing_decision": {
                "selected_specialists": selected,
                "routing_reason": "未启用按需专家模式，默认调用全部专家",
                "priority_issue": "完整分析",
                "followup_strategy": "light_clarification",
                "router_mode": "all_specialists",
            },
            "selected_specialists": selected,
            "priority_issue": "完整分析",
            "followup_strategy": "light_clarification",
        }

    # 提取状态信息
    current_user_text = state.get("current_user_text", "")
    current_facts = state.get("current_facts", [])
    current_anomalies = state.get("current_anomalies", [])
    facts_table = state.get("facts_table", [])
    anomalies_table = state.get("anomalies_table", [])
    surface_risk_score = state.get("surface_risk_score", 0)

    # 快速预分析标签无效，尝试重跑
    if not _has_valid_quick_labels(state):
        retry_count = int(state.get("quick_preanalysis_retry_count", 0) or 0)
        logger.warning(
            "[lightweight_routing] quick_preanalysis missing severity/confidence; "
            f"retry_count={retry_count}, schema_error={state.get('schema_error', '')}"
        )
        if retry_count < 1:
            return {
                "routing_decision": {
                    "selected_specialists": [],
                    "routing_reason": "quick_preanalysis 缺少 severity/confidence，回跳重跑一次",
                    "priority_issue": "",
                    "followup_strategy": "daily_routine",
                    "router_mode": "retry_quick_preanalysis",
                },
                "selected_specialists": [],
                "priority_issue": "",
                "followup_strategy": "daily_routine",
                "quick_preanalysis_retry_count": retry_count + 1,
                "schema_error": "quick_risk_labels_invalid",
            }

        return {
            "routing_decision": {
                "selected_specialists": [],
                "routing_reason": "quick_preanalysis 二次输出仍缺少 severity/confidence，丢弃本轮风险证据",
                "priority_issue": "",
                "followup_strategy": "daily_routine",
                "router_mode": "schema_error_drop_quick_evidence",
            },
            "selected_specialists": [],
            "priority_issue": "",
            "followup_strategy": "daily_routine",
            "current_anomalies": [],
            "schema_error": "quick_risk_labels_invalid_after_retry",
        }

    # 规则跳过专家判断
    if should_skip_specialist(state):
        routing_decision = {
            "selected_specialists": [],
            "routing_reason": "规则判定为极低风险：无当前异常、无未解决异常，跳过专家分析",
            "priority_issue": "无明显待澄清点",
            "followup_strategy": "daily_routine",
            "router_mode": "rule_skip",
        }
        logger.info(
            f"[路由监督节点] 规则跳过专家 - "
            f"surface_risk_score={surface_risk_score}, "
            f"has_new_fact={state.get('has_new_fact', False)}, "
            f"current_anomalies={len(current_anomalies)}, "
            f"unresolved_count={count_unresolved(anomalies_table)}"
        )
        return {
            "routing_decision": routing_decision,
            "selected_specialists": [],
            "priority_issue": routing_decision["priority_issue"],
            "followup_strategy": routing_decision["followup_strategy"],
        }

    # 将 facts_table/anomalies_table 转为文本供 LLM 使用
    facts_str = format_facts_table(facts_table) if facts_table else "暂无事实记录"
    current_facts_str = "\n".join([
        f"- {f.get('content', '')}（类型:{f.get('slot', '')}）"
        for f in current_facts
    ]) if current_facts else "本轮无新事实"
    current_anomalies_str = "\n".join([
        f"- {a.get('type', '')}: {a.get('description', '')}（分数:{a.get('score', 0)}）"
        for a in current_anomalies
    ]) if current_anomalies else "本轮无新异常"
    anomalies_str = format_anomalies_table(anomalies_table) if anomalies_table else "暂无异常记录"

    llm = get_llm()
    result = invoke_router_with_retry(
        llm,
        {
            "current_user_text": current_user_text,
            "current_facts": current_facts_str,
            "current_anomalies": current_anomalies_str,
            "facts_table": facts_str,
            "anomalies_table": anomalies_str,
            "surface_risk_score": surface_risk_score,
        },
        max_retries=2,
    )

    # LLM 返回为空时，使用默认推断
    if not result:
        selected_specialists = infer_default_specialists(state)
        routing_decision = {
            "selected_specialists": selected_specialists,
            "routing_reason": "[解析错误兜底] 不满足跳过条件，调用默认核心专家",
            "priority_issue": "需要进一步澄清当前事实或异常",
            "followup_strategy": "light_clarification",
            "parse_error": "json_parse_failed",
            "fallback_used": True,
            "router_mode": "rule_force_after_parse_error",
        }
        return {
            "routing_decision": routing_decision,
            "selected_specialists": selected_specialists,
            "priority_issue": routing_decision["priority_issue"],
            "followup_strategy": routing_decision["followup_strategy"],
            "parse_error": routing_decision["parse_error"],
        }

    # 过滤合法专家
    selected_specialists = [
        s for s in result.get("selected_specialists", [])
        if s in VALID_SPECIALISTS
    ]
    if not selected_specialists:
        logger.info("[路由监督节点] LLM 未选择专家，使用默认推断")
        selected_specialists = infer_default_specialists(state)

    # 判断当前是否有风险
    has_risk = bool(
        current_anomalies
        or any(
            isinstance(a, dict)
            and (
                a.get("status") in ("unresolved", "reinforced")
                or a.get("followup_needed") is True
            )
            for a in anomalies_table
        )
        or surface_risk_score >= 40
    )
    # 规范化 followup_strategy
    followup_strategy = normalize_followup_strategy(
        result.get("followup_strategy", ""),
        has_risk,
    )
    routing_reason = result.get("routing_reason", "")
    priority_issue = result.get("priority_issue", "")

    return {
        "routing_decision": {
            "selected_specialists": selected_specialists,
            "routing_reason": routing_reason,
            "priority_issue": priority_issue,
            "followup_strategy": followup_strategy,
            "router_mode": "rule_force_llm_select",
        },
        "selected_specialists": selected_specialists,
        "priority_issue": priority_issue,
        "followup_strategy": followup_strategy,
    }

