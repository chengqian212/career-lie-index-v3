"""职业常识分析 Agent 节点"""

import logging

from llm_client import get_llm
from prompts import DOMAIN_AGENT_PROMPT
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


def domain_agent_node(state: DialogueState) -> dict:
    """职业常识分析 Agent

    v3 改进：记录被调用的专家信息

    判断用户对职业内容的描述是否符合基本职业常识。

    Args:
        state: 当前对话状态
    Returns:
        状态更新字典，包含 specialist_results 和 called_specialists
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
        DOMAIN_AGENT_PROMPT.invoke({
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
            "agent": "domain",
            "score": 0,
            "evidence_list": [],
        },
        node_name="职业常识分析专家"
    )

    result = normalize_specialist_result(result, "domain")
    if result.get("schema_error"):
        logger.warning(
            "[domain_agent] dropped invalid evidence: "
            f"{result.get('dropped_evidence_count', 0)}"
        )
    
    logger.info(
        f"[职业常识分析专家] 分析完成 - score={result.get('score', 0)}, evidence数量={len(result.get('evidence_list', []))}"
    )

    return {
        "specialist_results": [result],
        "called_specialists": ["domain"],
    }

