"""
快速预分析节点：一次 LLM 调用同时完成事实抽取和表层异常检测

v3.2 合并：
将 quick_fact_extraction_node 和 quick_signal_detection_node
合并为 quick_preanalysis_node，减少一次 LLM 调用，提高整体运行速度。
"""

import logging

# 获取 LLM 客户端
from llm_client import get_llm

# 快速预分析提示词
from prompts import QUICK_PREANALYSIS_PROMPT

# 对话状态类型
from state_schema import DialogueState

# 从 LLM 输出文本中提取 JSON
from utils.json_utils import extract_json_from_text

# 文本格式化与清洗工具
from utils.text_utils import (
    format_dialogue_history,
    format_facts_table,
    format_anomalies_table,
    clean_llm_output,
)
from utils.score_utils import normalize_quick_risk_labels

# 异常表更新工具
from memory.anomaly_table import (
    update_anomalies_status,
    add_anomalies,
)

logger = logging.getLogger(__name__)


def _ensure_list(value) -> list:
    """
    确保输入是列表。

    如果 value 本身是 list，就直接返回。
    如果不是 list，就返回空列表，防止后面遍历时报错。
    """
    return value if isinstance(value, list) else []


def _safe_float(value, default: float = 0.0) -> float:
    """
    安全地把输入转换成 float。

    如果 value 是 None、空字符串，或者无法转换成数字，
    就返回默认值 default。
    """
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def quick_preanalysis_node(state: DialogueState) -> dict:
    """
    快速预分析节点。

    作用：
    一次调用 LLM，同时完成两个任务：
    1. 从当前用户回答中抽取事实；
    2. 检测表层异常信号。

    输入：
        state 是 LangGraph 中传递的全局状态，
        里面包含当前用户回答、历史对话、已有事实表、已有异常表等信息。

    输出：
        返回一个 dict，用于更新 DialogueState。
    """

    # 当前用户的回答
    current_user_text = state.get("current_user_text", "")

    # 上一轮系统提出的问题
    last_followup_question = state.get("last_followup_question", "")

    # 历史对话记录
    dialogue_history = state.get("dialogue_history", [])

    # 已经记录下来的事实表
    facts_table = state.get("facts_table", [])

    # 已经记录下来的异常表
    anomalies_table = state.get("anomalies_table", [])

    # 当前轮次，默认是第 1 轮
    round_id = state.get("round_id", 1)

    # 把历史对话格式化成适合放进 prompt 的字符串
    history_str = format_dialogue_history(dialogue_history)

    # 把已有事实表格式化成字符串；如果没有事实，就写“暂无事实记录”
    facts_str = format_facts_table(facts_table) if facts_table else "暂无事实记录"

    # 把已有异常表格式化成字符串；如果没有异常，就写“暂无异常记录”
    anomalies_str = format_anomalies_table(anomalies_table) if anomalies_table else "暂无异常记录"

    # 获取 LLM 实例
    llm = get_llm()

    # 调用 LLM，让它根据 prompt 完成事实抽取和异常检测
    response = llm.invoke(
        QUICK_PREANALYSIS_PROMPT.invoke({
            "last_followup_question": last_followup_question,
            "dialogue_history": history_str,
            "current_user_text": current_user_text,
            "facts_table": facts_str,
            "anomalies_table": anomalies_str,
        })
    )

    # 清洗 LLM 输出，去掉多余格式
    raw_output = clean_llm_output(response.content)

    # 从 LLM 输出中提取 JSON
    result = extract_json_from_text(raw_output)

    # 如果第一次 JSON 解析失败，就尝试更强力地清洗后再解析一次
    if not result:
        logger.warning(
            f"[快速预分析节点] 第一次 JSON 解析失败，尝试重新解析。"
            f"原始输出长度: {len(raw_output)} 字符，"
            f"原始输出预览: {raw_output[:200]}..."
        )

        # 使用 aggressive=True 进行更强的清洗
        cleaned_again = clean_llm_output(raw_output, aggressive=True)

        # 第二次尝试提取 JSON
        result = extract_json_from_text(cleaned_again)

        # 如果第二次还是失败，就返回默认结果，避免整个流程崩溃
        if not result:
            logger.error(
                f"[快速预分析节点] JSON 解析彻底失败。"
                f"已尝试两次解析，均无法提取有效 JSON。"
                f"原始输出: {raw_output}"
            )

            return {
                "facts_table": facts_table,
                "current_facts": [],
                "has_new_fact": False,
                "anomalies_table": anomalies_table,
                "current_anomalies": [],
                "surface_risk_score": 0.0,
                "quick_fact_summary": "",
                "quick_signal_summary": "",
                "parse_error": "json_parse_failed",
                "original_output_preview": raw_output[:200] + "..." if len(raw_output) > 200 else raw_output,
            }

        logger.info("[快速预分析节点] 第二次解析成功")

    # 如果解析出来的结果不是字典，也说明格式不符合预期
    if not isinstance(result, dict):
        logger.warning(
            f"[快速预分析节点] JSON 解析结果不是 dict，类型为 {type(result)}，返回默认值"
        )
        return {
            "facts_table": facts_table,
            "current_facts": [],
            "has_new_fact": False,
            "anomalies_table": anomalies_table,
            "current_anomalies": [],
            "surface_risk_score": 0.0,
            "quick_fact_summary": "",
            "quick_signal_summary": "",
            "parse_error": "json_not_dict",
        }

    # 从 LLM 返回结果中取出事实列表
    result = normalize_quick_risk_labels(result)
    raw_facts = _ensure_list(result.get("facts", []))
    quick_schema_error = result.get("schema_error")
    if quick_schema_error:
        logger.warning(
            "[quick_preanalysis] invalid severity/confidence schema: "
            f"{result.get('schema_errors', [])}"
        )

    # 从 LLM 返回结果中取出对旧异常的更新信息
    anomaly_updates = _ensure_list(result.get("anomaly_updates", []))

    # 从 LLM 返回结果中取出新发现的异常
    raw_anomalies = [] if quick_schema_error else _ensure_list(result.get("anomalies", []))

    # 获取表层风险分数，并保证它是 float
    surface_risk_score = _safe_float(result.get("surface_risk_score", 0), 0.0)

    # 限制风险分数范围在 0 到 100 之间
    surface_risk_score = max(0.0, min(100.0, surface_risk_score))
    severity = result.get("severity")
    confidence = result.get("confidence")

    # 获取事实摘要
    quick_fact_summary = result.get("quick_fact_summary", "")

    # 获取异常摘要
    quick_signal_summary = result.get("quick_signal_summary", "")

    # 防止摘要不是字符串
    if not isinstance(quick_fact_summary, str):
        quick_fact_summary = str(quick_fact_summary)

    if not isinstance(quick_signal_summary, str):
        quick_signal_summary = str(quick_signal_summary)

    # 记录本次快速预分析的结果
    logger.info(
        f"[快速预分析节点] 预分析成功 - "
        f"抽取到 {len(raw_facts)} 条事实，"
        f"识别到 {len(raw_anomalies)} 个异常，"
        f"更新 {len(anomaly_updates)} 个旧异常，"
        f"surface_risk_score={surface_risk_score}"
    )

    # 允许的事实槽位
    VALID_SLOTS = [
        "occupation",
        "role",
        "work_content",
        "company",
        "time_stage",
        "experience",
        "other",
    ]

    # 用于存放规范化后的当前轮事实
    normalized_current_facts = []

    # 遍历 LLM 抽取出的事实
    for fact in raw_facts:
        # 如果某条 fact 不是字典，就跳过
        if not isinstance(fact, dict):
            logger.warning(f"[快速预分析节点] 跳过非 dict fact: {fact}")
            continue

        # content 是事实内容；如果没有 content，就尝试使用 value
        content = fact.get("content") or fact.get("value") or ""

        # evidence 是支撑该事实的原文证据
        evidence = fact.get("evidence") or fact.get("raw_text") or content

        # slot 是事实类型，默认为 other
        slot = fact.get("slot", "other")

        # 防止 content 不是字符串
        if not isinstance(content, str):
            content = str(content)

        # 防止 evidence 不是字符串
        if not isinstance(evidence, str):
            evidence = str(evidence)

        # 如果槽位不在允许列表里，就统一归为 other
        if slot not in VALID_SLOTS:
            slot = "other"

        # 如果事实内容为空，就跳过
        if not content.strip():
            continue

        # 构造规范化后的事实记录
        normalized_fact = {
            "round_id": round_id,
            "slot": slot,
            "content": content.strip(),
            "evidence": evidence.strip(),
            "source": "quick_preanalysis",
        }

        # 加入当前轮事实列表
        normalized_current_facts.append(normalized_fact)

    # 判断当前轮是否抽取到了新事实
    has_new_fact = bool(normalized_current_facts)

    # 用于存放规范化后的异常更新信息
    normalized_anomaly_updates = []

    # 遍历 LLM 返回的旧异常更新信息
    for update in anomaly_updates:
        # 如果不是 dict，就跳过
        if not isinstance(update, dict):
            logger.warning(f"[快速预分析节点] 跳过非 dict anomaly_update: {update}")
            continue

        normalized_anomaly_updates.append(update)

    # 根据 anomaly_updates 更新已有异常表中旧异常的状态
    updated_anomalies_table = update_anomalies_status(
        anomalies_table=anomalies_table,
        updates=normalized_anomaly_updates,
        round_id=round_id,
    )

    # 用于存放当前轮新发现的异常
    normalized_current_anomalies = []

    # 遍历 LLM 识别出的新异常
    for anomaly in raw_anomalies:
        # 如果异常不是 dict，就跳过
        if not isinstance(anomaly, dict):
            logger.warning(f"[快速预分析节点] 跳过非 dict anomaly: {anomaly}")
            continue

        # 获取异常证据
        evidence = anomaly.get("evidence", [])

        # 如果 evidence 是字符串，就转成单元素列表
        if isinstance(evidence, str):
            evidence = [evidence]

        # 如果 evidence 既不是字符串也不是列表，就置为空列表
        elif not isinstance(evidence, list):
            evidence = []

        # 把 evidence 中的内容全部转成字符串，并去掉 None
        evidence = [str(e) for e in evidence if e is not None]

        # 获取异常分数
        score = _safe_float(anomaly.get("score", 0), 0.0)

        # 限制异常分数范围在 0 到 100 之间
        score = max(0.0, min(100.0, score))

        # 获取相关事实
        related_facts = anomaly.get("related_facts", [])

        # 防止 related_facts 不是列表
        if not isinstance(related_facts, list):
            related_facts = []

        # 构造规范化后的异常记录
        normalized_anomaly = {
            "type": str(anomaly.get("type", "未分类")),
            "description": str(anomaly.get("description", "")),
            "evidence": evidence,
            "score": score,
            "severity": anomaly.get("severity", severity),
            "confidence": anomaly.get("confidence", confidence),
            "related_facts": related_facts,
        }

        # 如果异常既没有描述，也没有证据，就跳过
        if not normalized_anomaly["description"].strip() and not normalized_anomaly["evidence"]:
            continue

        # 加入当前轮异常列表
        normalized_current_anomalies.append(normalized_anomaly)

    # 把当前轮新异常加入异常表
    updated_anomalies_table = add_anomalies(
        anomalies_table=updated_anomalies_table,
        new_anomalies=normalized_current_anomalies,
        round_id=round_id,
        source="quick_preanalysis",
    )

    # 复制已有事实表，避免直接修改原列表
    updated_facts_table = list(facts_table)

    # 把当前轮新事实追加到事实表中
    updated_facts_table.extend(normalized_current_facts)

    # 返回本节点对全局状态的更新内容
    return {
        "facts_table": updated_facts_table,
        "current_facts": normalized_current_facts,
        "has_new_fact": has_new_fact,
        "anomalies_table": updated_anomalies_table,
        "current_anomalies": normalized_current_anomalies,
        "surface_risk_score": surface_risk_score,
        "severity": severity,
        "confidence": confidence,
        "quick_fact_summary": quick_fact_summary,
        "quick_signal_summary": quick_signal_summary,
        "schema_error": quick_schema_error or "",
        "schema_errors": result.get("schema_errors", []),
    }

