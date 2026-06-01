"""
LLM-as-a-Judge strategy supervisor

本节点用于多智能体系统中充当策略监督者：
- 根据当前状态（风险分数、异常、专家结果、历史追问等）判断
  是否需要继续生成追问（ASK_MORE）或直接生成最终报告（GENERATE_REPORT）
- 返回的字段会被 followup_generation_node 或 report_generation_node 使用
"""

import logging

import config
from llm_client import get_llm
from prompts import STRATEGY_SUPERVISOR_PROMPT
from state_schema import DialogueState
from utils.json_utils import extract_json_from_text
from utils.strategy_utils import normalize_followup_strategy
from utils.text_utils import (
    clean_llm_output,
    format_anomalies_table,
    format_dialogue_history,
)

# 创建日志对象，用于记录策略监督节点运行情况
logger = logging.getLogger(__name__)

# -------------------------
# 内部函数：格式化历史追问
# -------------------------
def _format_followup_history(history: list[dict]) -> str:
    """
    将历史追问列表格式化成字符串，用于传给 LLM
    """
    if not history:
        return "None"

    lines = []
    for item in history:
        if not isinstance(item, dict):
            continue
        # 格式化每条追问，包括轮次、目标异常、问题内容
        lines.append(
            f"- round={item.get('round_id', '?')} "
            f"target={item.get('target_anomaly_id', '')} "
            f"question={item.get('question', item.get('content', ''))}"
        )
    return "\n".join(lines) if lines else "None"

# -------------------------
# 内部函数：格式化专家结果
# -------------------------
def _specialist_results_text(results: list[dict]) -> str:
    """
    将专家节点返回的结果列表格式化为文本，用于 LLM prompt
    包含：
        - agent 名称
        - 分数
        - 证据数量
        - 每条证据的类型、描述、严重度和置信度
    """
    if not results:
        return "None"

    lines = []
    for result in results:
        if not isinstance(result, dict):
            continue
        evidence_list = result.get("evidence_list", [])
        # 输出每个专家的分数和证据数量
        lines.append(
            f"[{result.get('agent', '?')}] score={result.get('score', 0)} "
            f"evidence_count={len(evidence_list) if isinstance(evidence_list, list) else 0}"
        )
        if isinstance(evidence_list, list):
            for item in evidence_list:
                if isinstance(item, dict):
                    lines.append(
                        f"  - {item.get('type', '')}: {item.get('description', '')} "
                        f"severity={item.get('severity', '')} confidence={item.get('confidence', '')}"
                    )
    return "\n".join(lines) if lines else "None"

# -------------------------
# 主函数：策略监督节点
# -------------------------
def strategy_supervisor_node(state: DialogueState) -> dict:
    """
    1. 根据当前状态向 LLM 提问：继续追问还是生成报告
    2. 解析 LLM 返回结果
    3. 规范化决策，输出给后续节点使用
    """

    # 获取轮次和最大轮次
    round_id = state.get("round_id", 1)
    max_rounds = state.get("max_rounds", config.MAX_ROUNDS)
    min_followup_rounds = min(config.MIN_FOLLOWUP_ROUNDS, max_rounds)

    # 创建 LLM 客户端
    llm = get_llm()

    # 调用 LLM 生成策略判断
    response = llm.invoke(
        STRATEGY_SUPERVISOR_PROMPT.invoke({
            "lie_index": state.get("lie_index", 0),  # 当前综合风险分
            "dimension_scores": state.get("dimension_scores", {}),  # 各维度分数
            "risk_explanation": "\n".join(state.get("risk_explanation", [])),  # 风险说明
            "specialist_results": _specialist_results_text(state.get("specialist_results", [])),
            "anomalies_table": format_anomalies_table(state.get("anomalies_table", [])),
            "dialogue_history": format_dialogue_history(state.get("dialogue_history", [])),
            "followup_history": _format_followup_history(state.get("followup_history", [])),
            "round_id": round_id,
            "max_rounds": max_rounds,
            "routing_decision": str(state.get("routing_decision", {}) or "None"),
            "called_specialists": ", ".join(state.get("called_specialists", [])) or "None",
        })
    )

    # 尝试解析 LLM 输出的 JSON
    result = extract_json_from_text(clean_llm_output(response.content))
    if not isinstance(result, dict):
        logger.warning("[strategy_supervisor] LLM JSON parse failed; fallback to ASK_MORE")
        result = {}

    # 获取决策结果，默认为 ASK_MORE
    decision = str(result.get("decision", "ASK_MORE")).strip().upper()
    if decision not in {"ASK_MORE", "GENERATE_REPORT"}:
        logger.warning("[strategy_supervisor] invalid decision from LLM: %s", decision)
        decision = "ASK_MORE"

    # Code-level round guardrail: before the minimum round, always keep asking;
    # at or beyond the maximum round, always generate the final report.
    if round_id < min_followup_rounds:
        if decision == "GENERATE_REPORT":
            logger.info(
                "[strategy_supervisor] overriding GENERATE_REPORT before min rounds: "
                "round_id=%s, min_followup_rounds=%s",
                round_id,
                min_followup_rounds,
            )
        decision = "ASK_MORE"
    elif round_id >= max_rounds:
        if decision != "GENERATE_REPORT":
            logger.info(
                "[strategy_supervisor] forcing GENERATE_REPORT at max rounds: "
                "round_id=%s, max_rounds=%s",
                round_id,
                max_rounds,
            )
        decision = "GENERATE_REPORT"

    # 规范化 followup_strategy
    followup_strategy = normalize_followup_strategy(
        result.get("followup_strategy", "daily_routine"),
        has_risk=False,  # 这里没有使用风险信号判断
    )

    # 获取 LLM 给出的原因总结
    reason_summary = result.get("reason_summary", "")
    if not isinstance(reason_summary, str):
        reason_summary = str(reason_summary)

    # 返回给后续节点的字典
    return {
        "next_action": "final_report" if decision == "GENERATE_REPORT" else "generate_followup",
        "priority_issue": result.get("priority_issue", ""),
        "followup_strategy": "" if decision == "GENERATE_REPORT" else followup_strategy,
        "stop_reason": reason_summary or decision.lower(),
        "target_anomaly_id": result.get("target_anomaly_id", ""),
    }
