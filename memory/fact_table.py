"""事实表模块：管理对话中提取的事实记录"""

from typing import List, Dict


def init_fact_table() -> List[Dict]:
    """初始化空事实表

    Returns:
        空事实表
    """
    return []


def add_facts(
    facts_table: List[Dict],
    new_facts: List[Dict],
    round_id: int,
) -> List[Dict]:
    """向事实表中添加新事实

    每条事实格式：
    {
        "round_id": int,
        "content": str,
        "category": str,  # 如 "职业身份", "工作内容", "时间经历" 等
        "raw_text": str,   # 原文引用
    }

    Args:
        facts_table: 当前事实表
        new_facts: 新提取的事实列表
        round_id: 当前轮次
    Returns:
        更新后的事实表
    """
    updated = list(facts_table)
    for fact in new_facts:
        entry = {
            "round_id": fact.get("round_id", round_id),
            "content": fact.get("content", ""),
            "category": fact.get("category", "未分类"),
            "raw_text": fact.get("raw_text", ""),
        }
        updated.append(entry)
    return updated


def get_facts_by_round(facts_table: List[Dict], round_id: int) -> List[Dict]:
    """获取指定轮次的事实

    Args:
        facts_table: 事实表
        round_id: 轮次 ID
    Returns:
        该轮次的事实列表
    """
    return [f for f in facts_table if f.get("round_id") == round_id]


def get_facts_by_category(facts_table: List[Dict], category: str) -> List[Dict]:
    """获取指定类别的事实

    Args:
        facts_table: 事实表
        category: 类别
    Returns:
        该类别的事实列表
    """
    return [f for f in facts_table if f.get("category") == category]


def get_facts_summary(facts_table: List[Dict]) -> str:
    """生成事实表摘要文本

    Args:
        facts_table: 事实表
    Returns:
        摘要文本
    """
    if not facts_table:
        return "暂无事实记录"

    categories = {}
    for fact in facts_table:
        cat = fact.get("category", "未分类")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f"第{fact.get('round_id', '?')}轮: {fact.get('content', '')}")

    lines = []
    for cat, items in categories.items():
        lines.append(f"【{cat}】")
        for item in items:
            lines.append(f"  - {item}")

    return "\n".join(lines)

