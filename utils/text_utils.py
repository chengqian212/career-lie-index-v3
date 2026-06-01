"""文本工具模块：处理文本的通用辅助函数

本模块提供多种辅助函数，用于：
1. 截断过长文本
2. 格式化对话历史、事实表、异常表
3. 统一提取 LLM 输出的文本
4. 清理 LLM 输出中的常见噪音
"""

import re
from typing import List, Any

def format_dialogue_history(history: List[dict], max_rounds: int | None = None) -> str:
    """格式化对话历史为可读文本，每条记录显示角色和内容

    Args:
        history: 对话历史列表，每项包含 'role' 和 'content'
        max_rounds: 最多格式化几轮，None 表示全部

    Returns:
        str: 格式化后的对话文本
    """
    if not history:
        return "（暂无对话历史）"

    entries = history if max_rounds is None else history[-max_rounds:]
    lines = []
    for entry in entries:
        role = entry.get("role", "unknown")
        content = entry.get("content", "")
        if role == "user":
            lines.append(f"【用户】：{content}")
        elif role == "assistant":
            lines.append(f"【系统】：{content}")
        else:
            lines.append(f"【{role}】：{content}")
    return "\n".join(lines)


def format_facts_table(facts_table: List[dict]) -> str:
    """格式化事实表为可读文本，每条记录显示轮次、类别和内容

    Args:
        facts_table: 事实表列表，每项包含 'round_id', 'category', 'content'

    Returns:
        str: 格式化后的事实列表
    """
    if not facts_table:
        return "（暂无事实记录）"

    lines = []
    for i, fact in enumerate(facts_table, 1):
        round_id = fact.get("round_id", "?")
        content = fact.get("content", "")
        category = fact.get("category", "")#抽取到哪种类型的事实
        lines.append(f"  [{i}] 第{round_id}轮 | {category} | {content}")
    return "\n".join(lines)


def format_anomalies_table(anomalies_table: List[dict]) -> str:
    """格式化异常表为可读文本

    v3 改进：输出 anomaly_id、source、score、clarification_status、followup_needed 等字段

    Args:
        anomalies_table: 异常表列表，每项包含多维字段

    Returns:
        str: 格式化后的异常列表
    """
    if not anomalies_table:
        return "（暂无异常记录）"

    lines = []
    for i, anomaly in enumerate(anomalies_table, 1):
        anomaly_id = anomaly.get("anomaly_id", "")
        round_id = anomaly.get("round_id", "?")
        source = anomaly.get("source", "")#争议来自哪一个agent
        atype = anomaly.get("type", "")
        desc = anomaly.get("description", "")
        score = anomaly.get("score", 0)
        status = anomaly.get("status", "unresolved")
        clarification_status = anomaly.get("clarification_status", "none")
        followup_needed = anomaly.get("followup_needed", True)

        # 输出格式化一行
        lines.append(
            f"  [{i}] [{anomaly_id}] 第{round_id}轮 | 来源:{source} | 类型:{atype} | "
            f"分数:{score} | 状态:{status} | 澄清:{clarification_status} | "
            f"需追问:{followup_needed} | {desc}"
        )
    return "\n".join(lines)


def extract_content_str(content: str | list[str | dict] | None) -> str:
    """将 LLM response.content 统一转为纯文本字符串

    LLM 的 content 可能是 str、list[str | dict] 或 None，本函数统一提取文本

    Args:
        content: LLM 返回内容

    Returns:
        str: 纯文本字符串
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                # 常见 dict 格式 {"type":"text","text":"..."}
                parts.append(item.get("text", str(item)))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def clean_llm_output(text: str | list[str | dict] | None, aggressive: bool = False) -> str:
    """清理 LLM 输出的噪音，包括标签、Markdown 标记和解释性行

    Args:
        text: 原始 LLM 输出，可为 str 或 list
        aggressive: 是否使用激进清理策略，去除更多可能的干扰行

    Returns:
        str: 清理后的文本
    """
    # 统一转为 str
    text = extract_content_str(text)
    text = text.strip()

    # 移除 <think/> 标签及内容
    text = re.sub(r"<think.*?>.*?</think\s*>", "", text, flags=re.DOTALL)

    if aggressive:
        # 移除 Markdown 代码块标记
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
        # 去掉纯解释性行（没有结构字符）
        lines = text.split("\n")
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and not any(c in stripped for c in ["{", "}", "[", "]", '"', "'"]):
                continue
            cleaned_lines.append(line)
        text = "\n".join(cleaned_lines)

    return text.strip()
