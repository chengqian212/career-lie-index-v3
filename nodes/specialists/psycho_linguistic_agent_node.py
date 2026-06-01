"""心理语言学线索分析 Agent 节点"""

import logging

from llm_client import get_llm
from prompts import PSYCHO_LINGUISTIC_AGENT_PROMPT
from utils.json_utils import safe_json_parse_with_retry
from utils.score_utils import normalize_specialist_result
from utils.text_utils import (
    format_dialogue_history,
    format_anomalies_table,
    clean_llm_output,
)
from state_schema import DialogueState

logger = logging.getLogger(__name__)


def psycho_linguistic_agent_node(state: DialogueState) -> dict:
    """心理语言学线索分析 Agent

    识别文本中的软性风险信号。
    心理语言学线索只是辅助信号，不能单独造成高风险结论。

    Args:
        state: 当前对话状态
    Returns:
        状态更新字典，包含 specialist_results
    """
    llm = get_llm()

    dialogue_text = format_dialogue_history(state.get("dialogue_history", []))
    anomalies_table = state.get("anomalies_table", [])
    current_anomalies = state.get("current_anomalies", [])
    anomalies_text = format_anomalies_table(anomalies_table) if anomalies_table else "暂无异常记录"

    # 格式化当前异常
    current_anomalies_str = "\n".join([
        f"- {a.get('type', '')}: {a.get('description', '')}（分数:{a.get('score', 0)}）"
        for a in current_anomalies
    ]) if current_anomalies else "本轮无新异常"

    # 调用 LLM（使用 ChatPromptTemplate 的 invoke 方法）
    response = llm.invoke(
        PSYCHO_LINGUISTIC_AGENT_PROMPT.invoke({
            "dialogue_history": dialogue_text,
            "current_user_text": state.get("current_user_text", ""),
            "anomalies_table": anomalies_text,
            "current_anomalies": current_anomalies_str,
        })
    )

    raw_output = clean_llm_output(response.content)
    result = safe_json_parse_with_retry(
        raw_output,
        default={
            "agent": "psycho_linguistic",
            "score": 0,
            "evidence_list": [],
        },
        node_name="心理语言学分析专家"
    )

    result = normalize_specialist_result(result, "psycho_linguistic")
    if result.get("schema_error"):
        logger.warning(
            "[psycho_linguistic_agent] dropped invalid evidence: "
            f"{result.get('dropped_evidence_count', 0)}"
        )
    
    logger.info(
        f"[心理语言学分析专家] 分析完成 - score={result.get('score', 0)}, evidence数量={len(result.get('evidence_list', []))}"
    )

    return {
        "specialist_results": [result],
        "called_specialists": ["psycho_linguistic"],
    }

