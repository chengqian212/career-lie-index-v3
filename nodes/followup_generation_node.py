"""
追问生成节点（Followup Generation Node）：
根据当前对话状态、风险信息和异常分析结果，
生成下一轮自然追问或继续对话。适用于多轮交互和多智能体评测场景。

v3 改进：
- 升级职责：选择追问焦点 + 生成追问
- 优先使用 strategy_supervisor 输出的 priority_issue 和 followup_strategy
- 当策略输出无效时按优先级自动选择追问方向
- 返回 next_action="generate_followup" 供 CLI 流程判断

v3.3 改进：
- 更新对应异常的 followup_count
- 超过上限后标记 stop_followup=True
- _infer_priority_issue 额外返回 target_anomaly_id
- 优先使用 strategy_supervisor 输出的状态字段
"""

from llm_client import get_llm
from prompts import FOLLOWUP_GENERATION_PROMPT, FOLLOWUP_POLISH_PROMPT
from state_schema import DialogueState
from utils.text_utils import (
    clean_llm_output,           # 清理 LLM 输出
    format_anomalies_table,     # 格式化异常表
    format_dialogue_history,    # 格式化对话历史
)
from utils.strategy_utils import normalize_followup_strategy  # 归一化策略

# -------------------------
# 低风险排除词
# -------------------------
_LOW_RISK_PHRASES = [
    "暂无明显风险",
    "未发现明显风险",
    "本轮未发现明显风险",
    "当前轮次未发现明显风险信号",
    "暂无明显不一致",
]

def _polish_followup_question(
    raw_question: str,
    dialogue_text: str,
    priority_issue: str,
    followup_strategy: str,
) -> str:
    """用低温编辑器做通用质检，修正错词、语义漂移和突兀术语。"""
    raw_question = clean_llm_output(raw_question)
    if not raw_question:
        return ""

    editor_llm = get_llm(temperature=0.0)
    try:
        response = editor_llm.invoke(
            FOLLOWUP_POLISH_PROMPT.invoke({
                "raw_question": raw_question,
                "dialogue_history": dialogue_text,
                "priority_issue": priority_issue,
                "followup_strategy": followup_strategy,
            })
        )
        polished = clean_llm_output(response.content)
    except Exception:
        return raw_question

    return polished or raw_question

# -------------------------
# 判断异常是否仍活跃
# -------------------------
def _is_active_anomaly(anomaly: dict) -> bool:
    """
    活跃条件：
    1. status 为 'unresolved' 或 'reinforced'
    2. followup_needed 为 True
    3. stop_followup 不为 True
    """
    if not isinstance(anomaly, dict):
        return False
    if anomaly.get("stop_followup") is True:
        return False
    status = anomaly.get("status", "")
    if status in ("unresolved", "reinforced"):
        return True
    if anomaly.get("followup_needed", False):
        return True
    return False

# -------------------------
# 判断当前状态是否存在风险信号
# -------------------------
def _has_risk_signal(state: DialogueState) -> bool:
    """
    风险判断条件：
    1. anomalies_table 有活跃异常
    2. risk_explanation 不为空，且不含低风险排除词
    3. current_anomalies 不为空
    4. lie_index > 30
    """
    anomalies_table = state.get("anomalies_table", [])
    risk_explanation = state.get("risk_explanation", [])
    current_anomalies = state.get("current_anomalies", [])
    lie_index = state.get("lie_index", 0)

    if any(_is_active_anomaly(a) for a in anomalies_table):
        return True

    if risk_explanation:
        risk_text = str(risk_explanation)
        if risk_text.strip() and not any(phrase in risk_text for phrase in _LOW_RISK_PHRASES):
            return True

    if current_anomalies:
        return True

    if lie_index and lie_index > 30:
        return True

    return False

# -------------------------
# 推断 priority_issue 和策略
# -------------------------
def _infer_priority_issue(state: DialogueState) -> tuple[str, str, str]:
    """
    推断逻辑顺序：
    1. 活跃的异常 → light_clarification
    2. risk_explanation → light_clarification
    3. current_facts → daily_routine
    4. 默认 → 继续自然聊天
    返回：
    (priority_issue, followup_strategy, target_anomaly_id)
    """
    anomalies_table = state.get("anomalies_table", [])
    risk_explanation = state.get("risk_explanation", [])
    current_facts = state.get("current_facts", [])

    active = [a for a in anomalies_table if _is_active_anomaly(a)]
    if active:
        latest = active[-1]
        issue = latest.get("description") or "待澄清的异常点"
        anomaly_id = latest.get("anomaly_id", "")
        return f"温和澄清：{issue}", "light_clarification", anomaly_id

    if risk_explanation:
        issue = str(risk_explanation[0])
        return f"温和了解：{issue}", "light_clarification", ""

    if current_facts:
        latest_fact = current_facts[-1]
        content = latest_fact.get("content", "")
        if content:
            return f"围绕事实轻量了解：{content}", "daily_routine", ""

    return "继续自然聊天", "daily_routine", ""

# -------------------------
# 判断 priority_issue 是否无效
# -------------------------
def _is_invalid_priority_issue(priority_issue: str) -> bool:
    """
    判断条件：空字符串或集合中的无效值
    """
    if not priority_issue:
        return True
    invalid_values = {
        "",
        "无明显待澄清点",
        "无",
        "暂无",
        "无明显问题",
        "无明显风险",
        "继续",
    }
    return priority_issue.strip() in invalid_values

# -------------------------
# 主函数：生成追问
# -------------------------
def followup_generation_node(state: DialogueState) -> dict:
    """
    功能：
    1. 根据 strategy_supervisor 输出 / 风险信息 / 当前事实确定追问焦点
    2. 调用 LLM 生成自然追问
    3. 更新 followup_history
    4. 更新 target_anomaly_id 对应异常的 followup_count
    5. 返回 next_action="generate_followup"
    """
    llm = get_llm()

    priority_issue = state.get("priority_issue", "")
    followup_strategy = state.get("followup_strategy", "")
    target_anomaly_id = state.get("target_anomaly_id", "")

    # 自动推断 priority_issue
    if _is_invalid_priority_issue(priority_issue):
        inferred_issue, inferred_strategy, inferred_aid = _infer_priority_issue(state)
        priority_issue = inferred_issue
        followup_strategy = inferred_strategy
        if not target_anomaly_id:
            target_anomaly_id = inferred_aid

    if not followup_strategy:
        followup_strategy = "daily_routine"

    # 策略合法性校验
    has_risk = _has_risk_signal(state)
    followup_strategy = normalize_followup_strategy(followup_strategy, has_risk)

    # 准备 LLM prompt 输入
    dimension_scores = state.get("dimension_scores", {})
    anomalies_text = format_anomalies_table(state.get("anomalies_table", []))
    dialogue_text = format_dialogue_history(state.get("dialogue_history", []))

    # 调用 LLM 生成追问
    response = llm.invoke(
        FOLLOWUP_GENERATION_PROMPT.invoke({
            "priority_issue": priority_issue,
            "followup_strategy": followup_strategy,
            "dimension_scores": dimension_scores,
            "anomalies_table": anomalies_text,
            "dialogue_history": dialogue_text,
        })
    )

    # 二次质检：修正错词、语义漂移和突兀术语，同时保留聊天感
    followup_question = _polish_followup_question(
        response.content,
        dialogue_text,
        priority_issue,
        followup_strategy,
    )
    if not followup_question:
        followup_question = "能再具体聊聊你的学习或项目经历吗？"

    # 更新历史追问
    followup_history = list(state.get("followup_history", []))
    followup_history.append({
        "round_id": state.get("round_id", 1),
        "question": followup_question,
        "priority_issue": priority_issue,
        "followup_strategy": followup_strategy,
    })

    # v3.3 更新 target_anomaly_id 对应异常的 followup_count
    updated_anomalies_table = list(state.get("anomalies_table", []))
    if target_anomaly_id:
        for i, anomaly in enumerate(updated_anomalies_table):
            if anomaly.get("anomaly_id") == target_anomaly_id:
                updated_anomalies_table[i] = dict(anomaly)  # 浅拷贝
                old_count = int(updated_anomalies_table[i].get("followup_count", 0) or 0)
                updated_anomalies_table[i]["followup_count"] = old_count + 1
                if updated_anomalies_table[i]["followup_count"] >= 2:
                    updated_anomalies_table[i]["stop_followup"] = True
                    updated_anomalies_table[i]["followup_needed"] = False
                break

    return {
        "last_followup_question": followup_question,
        "followup_history": followup_history,
        "priority_issue": priority_issue,
        "followup_strategy": followup_strategy,
        "next_action": "generate_followup",
        "anomalies_table": updated_anomalies_table,
    }

