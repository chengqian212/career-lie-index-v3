"""状态更新节点：更新事实表和异常表

v3: 已废弃
新流程中，quick_preanalysis_node 一次 LLM 调用同时完成事实抽取和异常检测，
直接更新 facts_table 和 anomalies_table。
本节点保留用于兼容旧版本，不再注册到 graph.py。
"""

from state_schema import DialogueState
from memory.fact_table import add_facts
from memory.anomaly_table import add_anomalies


def state_update_node(state: DialogueState) -> dict:
    """状态更新节点

    v3: 负责将当前抽取的事实和异常更新到全局表中

    工作流程：
    1. 从 state 中获取 current_facts 和 current_anomalies
    2. 将 current_facts 添加到 facts_table
    3. 将 current_anomalies 添加到 anomalies_table
    4. 返回更新后的 facts_table 和 anomalies_table

    Args:
        state: 当前对话状态
    Returns:
        状态更新字典，包含 facts_table 和 anomalies_table
    """
    # 获取当前轮次
    round_id = state.get("round_id", 1)

    # 获取当前抽取的事实和异常
    current_facts = state.get("current_facts", [])
    current_anomalies = state.get("current_anomalies", [])

    # 获取当前的 facts_table 和 anomalies_table
    facts_table = state.get("facts_table", [])
    anomalies_table = state.get("anomalies_table", [])

    # 更新 facts_table
    updated_facts_table = add_facts(
        facts_table=facts_table,
        new_facts=current_facts,
        round_id=round_id,
    )

    # 更新 anomalies_table
    updated_anomalies_table = add_anomalies(
        anomalies_table=anomalies_table,
        new_anomalies=current_anomalies,
        round_id=round_id,
    )

    # 返回更新后的表
    return {
        "facts_table": updated_facts_table,
        "anomalies_table": updated_anomalies_table,
    }
