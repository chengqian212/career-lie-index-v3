"""逻辑与时间线分析 Agent 节点"""

import logging

from llm_client import get_llm
from prompts import LOGICAL_AGENT_PROMPT
from utils.json_utils import safe_json_parse_with_retry
from utils.score_utils import normalize_specialist_result
from utils.text_utils import (
    format_dialogue_history,
    format_facts_table,
    format_anomalies_table,
    clean_llm_output,
)
from state_schema import DialogueState

logger = logging.getLogger(__name__)


def logical_agent_node(state: DialogueState) -> dict:
    """逻辑与时间线分析 Agent

    判断职业叙述中的时间、因果、职业路径是否自洽。

    Args:
        state: 当前对话状态
    Returns:
        状态更新字典，包含 specialist_results
    """
    llm = get_llm()

    dialogue_text = format_dialogue_history(state.get("dialogue_history", []))
    facts_text = format_facts_table(state.get("facts_table", []))
    current_facts = state.get("current_facts", [])
    anomalies_table = state.get("anomalies_table", [])
    current_anomalies = state.get("current_anomalies", [])

    current_facts_text = "\n".join(
        f"  - {f.get('content', '')} ({f.get('category', '')})"
        for f in current_facts
    ) if current_facts else "（当前轮次无新事实）"

    # 格式化异常表
    anomalies_str = format_anomalies_table(anomalies_table) if anomalies_table else "暂无异常记录"

    # 格式化当前异常
    current_anomalies_str = "\n".join([
        f"- {a.get('type', '')}: {a.get('description', '')}（分数:{a.get('score', 0)}）"
        for a in current_anomalies
    ]) if current_anomalies else "本轮无新异常"

    # 调用 LLM（使用 ChatPromptTemplate 的 invoke 方法）
    response = llm.invoke(
        LOGICAL_AGENT_PROMPT.invoke({
            "dialogue_history": dialogue_text,
            "facts_table": facts_text,
            "current_facts": current_facts_text,
            "anomalies_table": anomalies_str,
            "current_anomalies": current_anomalies_str,
        })
    )

    raw_output = clean_llm_output(response.content)
    result = safe_json_parse_with_retry(
        raw_output,
        default={
            "agent": "logical",
            "score": 0,
            "evidence_list": [],
        },
        node_name="逻辑分析专家"
    )

    result = normalize_specialist_result(result, "logical")
    if result.get("schema_error"):
        logger.warning(
            "[logical_agent] dropped invalid evidence: "
            f"{result.get('dropped_evidence_count', 0)}"
        )
    
    logger.info(
        f"[逻辑分析专家] 分析完成 - score={result.get('score', 0)}, evidence数量={len(result.get('evidence_list', []))}"
    )

    return {
        "specialist_results": [result],
        "called_specialists": ["logical"],
    }

