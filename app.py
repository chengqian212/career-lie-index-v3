"""Streamlit 前端：多 Agent 相亲对话小助手 v3.0

该模块实现了 v3 版本的 Web 交互界面，主要特性包括：
- 美观的聊天界面，大字体显示用户回答和AI提问
- AI提问流式输出效果
- 实时显示分析过程和结果
- 支持中文输出
"""

import json
import os
import sys
import time
from html import escape
from datetime import datetime

import streamlit as st

# 确保 v3 目录作为项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    disable_proxy,
    MAX_ROUNDS,
)
from graph import build_graph
from utils.logger import get_logger, reset_logger
from utils.supabase_outputs import safe_sync_output_file


# ============== 页面配置 ==============
st.set_page_config(
    page_title="多 Agent 相亲对话小助手 v3.0",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============== 自定义CSS样式 ==============
st.markdown("""
<style>
/* 全局字体设置 */
body {
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
}

/* 用户消息样式 - 大字体 */
.user-message {
    font-size: 1.3rem !important;
    line-height: 1.8 !important;
    color: #1a1a2e !important;
    padding: 12px 16px !important;
    border-radius: 12px !important;
    background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%) !important;
    border-left: 4px solid #2196f3 !important;
    margin: 8px 0 !important;
}

/* AI消息样式 - 大字体 */
.ai-message {
    font-size: 1.3rem !important;
    line-height: 1.8 !important;
    color: #1a1a2e !important;
    padding: 12px 16px !important;
    border-radius: 12px !important;
    background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%) !important;
    border-left: 4px solid #9c27b0 !important;
    margin: 8px 0 !important;
}

/* 流式输出光标效果 */
.streaming-cursor {
    display: inline-block;
    width: 2px;
    height: 1.2em;
    background-color: #9c27b0;
    animation: blink 0.8s infinite;
    vertical-align: text-bottom;
    margin-left: 2px;
}

@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}

/* 消息容器 */
.chat-message {
    margin-bottom: 16px;
}

/* 角色标签 */
.role-label {
    font-size: 0.85rem;
    font-weight: 600;
    color: #666;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
}

/* 侧边栏样式 */
.sidebar-title {
    font-size: 1.1rem;
    font-weight: bold;
    color: #333;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 2px solid #e0e0e0;
}

/* 统计卡片 */
.stat-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 16px;
    border-radius: 12px;
    margin-bottom: 12px;
    text-align: center;
}

.stat-value {
    font-size: 2rem;
    font-weight: bold;
}

.stat-label {
    font-size: 0.85rem;
    opacity: 0.9;
}

/* 风险等级指示器 */
.risk-indicator {
    padding: 8px 16px;
    border-radius: 8px;
    font-weight: bold;
    text-align: center;
    margin: 8px 0;
}

.risk-low {
    background-color: #e8f5e9;
    color: #2e7d32;
}

.risk-medium {
    background-color: #fff3e0;
    color: #ef6c00;
}

.risk-high {
    background-color: #ffebee;
    color: #c62828;
}

/* 分析过程折叠面板 */
.analysis-panel {
    background-color: #fafafa;
    border-radius: 8px;
    padding: 12px;
    margin-top: 8px;
}

/* 输入框样式 */
.stTextInput > div > div > input {
    font-size: 1.1rem !important;
    padding: 12px 16px !important;
}

/* 按钮样式 */
.stButton > button {
    font-size: 1rem !important;
    padding: 8px 24px !important;
    border-radius: 8px !important;
}

/* 隐藏默认的streamlit元素 */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

/* 欢迎区域 */
.welcome-area {
    text-align: center;
    padding: 40px 20px;
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    border-radius: 16px;
    margin-bottom: 24px;
}

.welcome-title {
    font-size: 2rem;
    font-weight: bold;
    color: #333;
    margin-bottom: 12px;
}

.welcome-subtitle {
    font-size: 1.1rem;
    color: #666;
}

/* 报告区域 */
.report-area {
    background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%);
    border-radius: 12px;
    padding: 20px;
    margin-top: 16px;
    border-left: 4px solid #ffc107;
}

/* 专家标签 */
.specialist-tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    margin-right: 4px;
    margin-bottom: 4px;
}

.specialist-semantic { background-color: #e3f2fd; color: #1565c0; }
.specialist-logical { background-color: #e8f5e9; color: #2e7d32; }
.specialist-domain { background-color: #fff3e0; color: #ef6c00; }
.specialist-psycho { background-color: #f3e5f5; color: #7b1fa2; }

/* Agent 思考监控 */
.monitor-shell {
    border: 1px solid #e4e7ec;
    border-radius: 8px;
    padding: 14px;
    background: #ffffff;
    margin-bottom: 12px;
}

.thought-card {
    border-left: 4px solid #64748b;
    background: #f8fafc;
    border-radius: 6px;
    padding: 10px 12px;
    margin: 8px 0;
    line-height: 1.65;
    color: #1f2937;
}

.thought-title {
    font-weight: 700;
    margin-right: 4px;
}

.thought-meta {
    color: #667085;
    font-size: 0.86rem;
    margin-left: 4px;
}

.thought-semantic { border-left-color: #1565c0; }
.thought-logical { border-left-color: #2e7d32; }
.thought-domain { border-left-color: #ef6c00; }
.thought-psycho { border-left-color: #7b1fa2; }
.thought-routing { border-left-color: #0f766e; }
.thought-risk { border-left-color: #c2410c; }
.thought-strategy { border-left-color: #7c3aed; }
.thought-report { border-left-color: #b45309; }
</style>
""", unsafe_allow_html=True)


# ============== 初始化函数 ==============
def create_initial_state(max_rounds: int = MAX_ROUNDS) -> dict:
    """创建初始状态"""
    return {
        "round_id": 0,
        "max_rounds": max_rounds,
        "current_user_text": "",
        "dialogue_history": [],
        "current_facts": [],
        "facts_table": [],
        "current_anomalies": [],
        "indicator_history": [],
        "anomalies_table": [],
        "last_followup_question": "",
        "followup_history": [],
        "specialist_results": [],
        "dimension_scores": {},
        "lie_index": 0.0,
        "risk_explanation": [],
        "next_action": "",
        "final_report": None,
        "quick_fact_summary": "",
        "quick_signal_summary": "",
        "surface_risk_score": 0.0,
        "severity": "",
        "confidence": "",
        "schema_error": "",
        "schema_errors": [],
        "quick_preanalysis_retry_count": 0,
        "has_new_fact": False,
        "routing_decision": {},
        "selected_specialists": [],
        "priority_issue": "",
        "followup_strategy": "",
        "called_specialists": [],
        # v3.3 新增字段
        "stop_reason": "",
        "target_anomaly_id": "",
    }


def get_risk_level(lie_index: float) -> tuple[str, str]:
    """根据谎言指数返回风险等级和样式类"""
    if lie_index >= 70:
        return "高风险", "risk-high"
    elif lie_index >= 30:
        return "中风险", "risk-medium"
    else:
        return "低风险", "risk-low"


def get_specialist_name(specialist: str) -> str:
    """获取专家中文名称"""
    mapping = {
        "semantic": "语义分析",
        "logical": "逻辑分析",
        "domain": "职业常识",
        "psycho_linguistic": "心理语言",
    }
    return mapping.get(specialist, specialist)


def get_specialist_class(specialist: str) -> str:
    """获取专家标签样式类"""
    mapping = {
        "semantic": "specialist-semantic",
        "logical": "specialist-logical",
        "domain": "specialist-domain",
        "psycho_linguistic": "specialist-psycho",
    }
    return mapping.get(specialist, "specialist-semantic")


def render_message(msg: dict, is_streaming: bool = False):
    """渲染单条消息

    Args:
        msg: 消息字典，包含 role 和 content
        is_streaming: 是否正在流式输出（显示光标）
    """
    role = msg["role"]
    content = msg["content"]
    cursor_html = '<span class="streaming-cursor"></span>' if is_streaming else ""

    if role == "user":
        st.markdown(f"""
        <div class="chat-message">
            <div class="role-label">👤 用户</div>
            <div class="user-message">{content}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="chat-message">
            <div class="role-label">🤖 AI</div>
            <div class="ai-message">{content}{cursor_html}</div>
        </div>
        """, unsafe_allow_html=True)


def _save_session_to_outputs(state: dict, thinking_history: list, round_records: list) -> str:
    """保存完整测试会话到 outputs/reports 目录

    Args:
        state: 完整的对话状态字典
        thinking_history: 每轮耗时记录列表
        round_records: 每轮的详细记录（包含节点耗时和 agent_thoughts）

    Returns:
        保存后的文件路径
    """
    reports_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "outputs",
        "reports",
    )
    os.makedirs(reports_dir, exist_ok=True)

    data = {
        "round_id": state.get("round_id"),
        "max_rounds": state.get("max_rounds"),
        "round_records": round_records,
        "dialogue_history": state.get("dialogue_history", []),
        "followup_history": state.get("followup_history", []),
        "facts_table": state.get("facts_table", []),
        "anomalies_table": state.get("anomalies_table", []),
        "indicator_history": state.get("indicator_history", []),
        "lie_index": state.get("lie_index", 0.0),
        "dimension_scores": state.get("dimension_scores", {}),
        "risk_explanation": state.get("risk_explanation", []),
        "called_specialists": state.get("called_specialists", []),
        "routing_decision": state.get("routing_decision", {}),
        "final_report": state.get("final_report"),
        "thinking_time_history": thinking_history,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"session_{timestamp}.json"
    filepath = os.path.join(reports_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return filepath


# ============== 新：节点中文标题和自然语言提取 ==============
def get_node_title(node_name: str) -> str:
    """将节点名称映射成友好中文标题"""
    mapping = {
        "quick_preanalysis": "快速预分析",
        "lightweight_routing_supervisor": "路由决策",
        "semantic_agent": "语义分析专家",
        "logical_agent": "逻辑分析专家",
        "domain_agent": "领域知识专家",
        "psycho_linguistic_agent": "心理语言学专家",
        "risk_aggregator": "风险聚合",
        "strategy_supervisor": "策略决策",
        "followup_generation": "追问生成",
        "report_generation": "报告生成",
    }
    return mapping.get(node_name, node_name)


def get_thought_class(node_name: str) -> str:
    """返回监控卡片的节点样式类。"""
    if node_name == "semantic_agent":
        return "thought-semantic"
    if node_name == "logical_agent":
        return "thought-logical"
    if node_name == "domain_agent":
        return "thought-domain"
    if node_name == "psycho_linguistic_agent":
        return "thought-psycho"
    if node_name == "lightweight_routing_supervisor":
        return "thought-routing"
    if node_name == "risk_aggregator":
        return "thought-risk"
    if node_name == "strategy_supervisor":
        return "thought-strategy"
    if node_name in ("followup_generation", "report_generation"):
        return "thought-report"
    return ""


def format_thought_line(thought: dict) -> str:
    """格式化为：节点标题：思考内容（耗时 1.23s）。"""
    title = escape(str(thought.get("title") or thought.get("node") or "节点"))
    content = escape(str(thought.get("content") or ""))
    elapsed = thought.get("elapsed_seconds")
    elapsed_text = ""
    if isinstance(elapsed, (int, float)):
        elapsed_text = f'<span class="thought-meta">（耗时 {elapsed:.2f}s）</span>'
    elif thought.get("time"):
        elapsed_text = f'<span class="thought-meta">（{escape(str(thought["time"]))}）</span>'
    css_class = get_thought_class(str(thought.get("node") or ""))
    return (
        f'<div class="thought-card {css_class}">'
        f'<span class="thought-title">{title}：</span>{content}{elapsed_text}'
        f'</div>'
    )


def render_thought_items(thoughts: list[dict]) -> None:
    """渲染一组思考摘要，不输出原始 JSON。"""
    visible_thoughts = [t for t in thoughts if isinstance(t, dict) and t.get("content")]
    if not visible_thoughts:
        st.info("暂无可展示的 Agent 思考摘要。")
        return
    for thought in visible_thoughts:
        st.markdown(format_thought_line(thought), unsafe_allow_html=True)


def normalize_monitor_record(record: dict) -> dict:
    """让历史监控中的追问展示严格跟随该轮保存的 ai_followup。"""
    if not isinstance(record, dict) or record.get("is_live"):
        return record

    normalized = dict(record)
    thoughts = [
        dict(t)
        for t in normalized.get("agent_thoughts", [])
        if isinstance(t, dict) and t.get("node") != "followup_generation"
    ]

    followup = str(normalized.get("ai_followup") or "").strip()
    if followup:
        thoughts.append({
            "node": "followup_generation",
            "title": get_node_title("followup_generation"),
            "content": f"生成追问：{followup}",
            "elapsed_seconds": normalized.get("node_times", {}).get("followup_generation"),
            "time": normalized.get("time", ""),
        })

    normalized["agent_thoughts"] = thoughts
    return normalized


def get_monitor_records(max_recent: int = 10) -> list[dict]:
    """读取历史轮次和当前实时轮次，供监控 Tab 只读展示。"""
    raw_records = st.session_state.get("round_records", [])
    if isinstance(raw_records, dict):
        records = list(raw_records.values())
    else:
        records = list(raw_records)
    records = [normalize_monitor_record(record) for record in records]

    live_thoughts = st.session_state.get("live_agent_thoughts", [])
    if live_thoughts and st.session_state.get("is_processing", False):
        records.append({
            "round": st.session_state.get("live_agent_round") or st.session_state.get("round_num", 0),
            "time": "进行中",
            "agent_thoughts": live_thoughts,
            "is_live": True,
        })

    def sort_key(record: dict) -> tuple[int, int]:
        round_no = record.get("round", 0)
        try:
            round_no = int(round_no)
        except (TypeError, ValueError):
            round_no = 0
        return (round_no, 1 if record.get("is_live") else 0)

    return sorted(records, key=sort_key)[-max_recent:]


def append_live_agent_thought(agent_thoughts: list[dict], thought_entry: dict, max_live: int = 10) -> None:
    """追加实时思考摘要，并限制监控区当前轮展示数量。"""
    agent_thoughts.append(thought_entry)
    st.session_state.live_agent_thoughts = agent_thoughts[-max_live:]


def render_agent_monitor(max_recent: int = 10) -> None:
    """只读监控页：按轮次展示 Agent 思考摘要。"""
    recent_records = get_monitor_records(max_recent)

    st.markdown('<div class="monitor-shell">', unsafe_allow_html=True)
    st.subheader("Agent 思考监控")
    st.caption("这里只显示节点思考摘要，不显示对话文本、最终报告或原始 JSON。")

    if not recent_records:
        st.info("开始测评后，每个节点返回摘要时会显示在这里。")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    left_col, right_col = st.columns([1, 3])
    labels = [
        f"第 {record.get('round', '?')} 轮{'（进行中）' if record.get('is_live') else ''}"
        for record in recent_records
    ]
    with left_col:
        selected_index = st.radio(
            "轮次",
            range(len(labels)),
            format_func=lambda i: labels[i],
            index=len(labels) - 1,
            key=f"monitor_round_selector_{len(labels)}_{labels[-1]}",
        )
        st.caption(f"最多显示最近 {max_recent} 轮")

    selected_record = recent_records[selected_index]
    with right_col:
        round_no = selected_record.get("round", "?")
        expanded = bool(selected_record.get("is_live")) or selected_index == len(labels) - 1
        with st.expander(f"第 {round_no} 轮 Agent 思考", expanded=expanded):
            render_thought_items(selected_record.get("agent_thoughts") or [])

    st.markdown("</div>", unsafe_allow_html=True)


def render_live_agent_monitor(round_num: int, thoughts: list[dict]) -> None:
    """只渲染当前运行轮次，避免流式刷新时重复创建交互控件。"""
    st.markdown('<div class="monitor-shell">', unsafe_allow_html=True)
    st.subheader("Agent 思考监控")
    st.caption(f"第 {round_num} 轮正在运行，这里只显示本轮已完成节点。")
    render_thought_items(thoughts)
    st.markdown("</div>", unsafe_allow_html=True)


def extract_agent_thoughts(node_name: str, node_update: dict) -> str | None:
    """从节点返回的更新中提取适合展示的自然语言摘要

    返回 None 表示没有可展示的内容。
    """
    if not isinstance(node_update, dict):
        return None

    # 快速预分析
    if node_name == "quick_preanalysis":
        fact = node_update.get("quick_fact_summary", "")
        signal = node_update.get("quick_signal_summary", "")
        parts = []
        if fact:
            parts.append(fact)
        if signal:
            parts.append(signal)
        return "；".join(parts) if parts else None

    # 路由决策
    if node_name == "lightweight_routing_supervisor":
        selected = node_update.get("selected_specialists", [])
        rd = node_update.get("routing_decision", {})
        # 兼容多种原因字段
        reason = rd.get("routing_reason") or rd.get("reason") or rd.get("decision_reason") or rd.get("explanation") or ""
        issue = node_update.get("priority_issue", "")
        strategy = node_update.get("followup_strategy", "")
        lines = []
        if not selected:
            lines.append("系统判定本轮无需调用专家，直接进入风险聚合")
        else:
            names = [get_specialist_name(s) for s in selected if s]
            lines.append(f"调用专家：{', '.join(names) if names else '语义、逻辑'}")
        if reason:
            lines.append(f"原因：{reason}")
        if issue:
            lines.append(f"关注点：{issue}")
        return "；".join(lines) if lines else None

    # specialist agents
    agent_mapping = {
        "semantic_agent": "semantic",
        "logical_agent": "logical",
        "domain_agent": "domain",
        "psycho_linguistic_agent": "psycho_linguistic",
    }
    if node_name in agent_mapping:
        agent_key = agent_mapping[node_name]
        results = node_update.get("specialist_results", [])
        # 优先找对应 agent
        for r in results:
            if not isinstance(r, dict):
                continue
            # 兼容 agent, specialist, dimension, agent_name 等字段
            rid = r.get("agent") or r.get("specialist") or r.get("dimension") or r.get("agent_name") or ""
            if rid == agent_key:
                # 自然语言字段：summary, analysis, reason, conclusion, explanation, rationale
                summary = (r.get("summary") or r.get("analysis") or r.get("reason") or
                           r.get("conclusion") or r.get("explanation") or r.get("rationale"))
                if not summary and isinstance(r.get("evidence_list"), list):
                    evidence_list = r.get("evidence_list", [])
                    if evidence_list and isinstance(evidence_list[0], dict):
                        summary = evidence_list[0].get("description", "")
                if summary:
                    return summary
                score = r.get("score")
                if score is not None:
                    return f"该专家评分：{score}"
                return None
        # 直接看 score
        score = node_update.get("score")
        if score is not None:
            return f"专家评分：{score}"
        return None

    # risk_aggregator
    if node_name == "risk_aggregator":
        lie = node_update.get("lie_index", 0)
        exp = node_update.get("risk_explanation", [])
        exp_text = "；".join(exp) if exp else ""
        parts = [f"风险指数 {lie}"]
        if exp_text:
            parts.append(exp_text)
        return "，".join(parts)

    # strategy_supervisor
    if node_name == "strategy_supervisor":
        next_action = node_update.get("next_action", "")
        stop_reason = node_update.get("stop_reason", "")
        issue = node_update.get("priority_issue", "")
        strategy = node_update.get("followup_strategy", "")
        if next_action == "final_report":
            return f"信息已足够，生成最终报告（{stop_reason}）"
        else:
            return f"继续追问（{stop_reason}），关注：{issue or '待澄清点'}，策略：{strategy or '未指定'}"

    # followup_generation
    if node_name == "followup_generation":
        question = node_update.get("last_followup_question", "")
        return f"生成追问：{question}" if question else None

    # report_generation
    if node_name == "report_generation":
        return "最终测评报告已生成"

    return None


def get_latest_node_elapsed(logger, node_name: str):
    """从 logger 中获取最近一次指定节点的执行耗时

    Args:
        logger: DetailedLogger 实例
        node_name: 节点名称（与日志中的 node_name 字段一致）

    Returns:
        float 或 None
    """
    rounds = logger.session_data.get("rounds", [])
    if not rounds:
        return None
    nodes = rounds[-1].get("nodes", [])
    for node in reversed(nodes):
        if node.get("node_name") == node_name:
            return node.get("elapsed_seconds")
    return None


def merge_node_update(accumulated: dict, node_update: dict) -> dict:
    """安全合并节点更新到累计状态

    对于列表类字段，采用追加合并，避免并行节点结果互相覆盖。
    其他字段直接覆盖。

    Args:
        accumulated: 当前累计的状态
        node_update: 单个节点的部分更新

    Returns:
        合并后的状态（原地修改 accumulated）
    """
    # 需要追加合并的列表字段
    extend_fields = ["specialist_results", "called_specialists", "risk_explanation", "indicator_history"]
    for key in extend_fields:
        if key in node_update and isinstance(node_update[key], list):
            if key not in accumulated or not isinstance(accumulated[key], list):
                accumulated[key] = []
            # 追加列表，简单去重（dict 不能简单用 set）
            existing_ids = set()
            if key == "specialist_results":
                # 按 agent 去重
                for item in accumulated[key]:
                    if isinstance(item, dict):
                        agent = item.get("agent") or item.get("specialist") or item.get("dimension") or ""
                        if agent:
                            existing_ids.add(agent)
                for item in node_update[key]:
                    if isinstance(item, dict):
                        agent = item.get("agent") or item.get("specialist") or item.get("dimension") or ""
                        if agent and agent not in existing_ids:
                            accumulated[key].append(item)
                            existing_ids.add(agent)
                        elif not agent:
                            accumulated[key].append(item)
                    else:
                        accumulated[key].append(item)
            elif key == "called_specialists":
                # 字符串列表去重
                for item in node_update[key]:
                    if item not in accumulated[key]:
                        accumulated[key].append(item)
            else:
                # risk_explanation、indicator_history 直接扩展（去重太复杂，可接受少量重复）
                accumulated[key].extend(node_update[key])
            # 从 node_update 中移除，以免后续覆盖
            continue

    # 其他字段直接合并
    for key, value in node_update.items():
        if key not in extend_fields:
            accumulated[key] = value

    return accumulated


# ============== Streamlit 应用主体 ==============
def main():
    # 关闭代理
    disable_proxy()

    # 初始化 session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "state" not in st.session_state:
        st.session_state.state = create_initial_state()
    if "graph" not in st.session_state:
        st.session_state.graph = build_graph()
    if "round_num" not in st.session_state:
        st.session_state.round_num = 0
    if "started" not in st.session_state:
        st.session_state.started = False
    if "final_report_shown" not in st.session_state:
        st.session_state.final_report_shown = False
    if "current_lie_index" not in st.session_state:
        st.session_state.current_lie_index = 0.0
    if "dimension_scores" not in st.session_state:
        st.session_state.dimension_scores = {}
    if "called_specialists" not in st.session_state:
        st.session_state.called_specialists = []
    if "streaming_text" not in st.session_state:
        st.session_state.streaming_text = ""
    if "is_streaming" not in st.session_state:
        st.session_state.is_streaming = False
    if "thinking_time_history" not in st.session_state:
        st.session_state.thinking_time_history = []
    if "round_records" not in st.session_state:
        st.session_state.round_records = []
    if "live_agent_thoughts" not in st.session_state:
        st.session_state.live_agent_thoughts = []
    if "live_agent_round" not in st.session_state:
        st.session_state.live_agent_round = None
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False

    if "last_thinking_time" not in st.session_state:
        st.session_state.last_thinking_time = 0.0

    if "saved_filepath" not in st.session_state:
        st.session_state.saved_filepath = ""
    if "saved_log_filepath" not in st.session_state:
        st.session_state.saved_log_filepath = ""

    # ============== 侧边栏 ==============
    with st.sidebar:
        st.markdown('<div class="sidebar-title">📊 系统状态</div>', unsafe_allow_html=True)

        # 当前轮次
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{st.session_state.round_num} / {MAX_ROUNDS}</div>
            <div class="stat-label">当前轮次</div>
        </div>
        """, unsafe_allow_html=True)

        # 谎言指数
        lie_index = st.session_state.current_lie_index
        risk_level, risk_class = get_risk_level(lie_index)
        st.markdown(f"""
        <div class="stat-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
            <div class="stat-value">{lie_index:.1f}</div>
            <div class="stat-label">风险指数</div>
        </div>
        """, unsafe_allow_html=True)

        # 风险等级
        st.markdown(f'<div class="risk-indicator {risk_class}">{risk_level}</div>', unsafe_allow_html=True)

        # 维度分数
        st.markdown('<div class="sidebar-title">📈 维度分数</div>', unsafe_allow_html=True)
        dimension_scores = st.session_state.dimension_scores
        if dimension_scores:
            score_names = {
                "semantic": "语义一致性",
                "logical": "逻辑时间线",
                "domain": "职业常识",
                "psycho_linguistic": "心理语言",
                "lightweight_surface": "表层风险",
                "unresolved_anomalies": "未澄清异常",
            }
            for key, score in dimension_scores.items():
                name = score_names.get(key, key)
                st.progress(min(score / 100, 1.0), text=f"{name}: {score}")
        else:
            st.info("暂无维度分数数据")

        # 已调用专家
        st.markdown('<div class="sidebar-title">🤖 已调用专家</div>', unsafe_allow_html=True)
        called = st.session_state.called_specialists
        if called:
            for spec in called:
                st.markdown(f'<span class="specialist-tag {get_specialist_class(spec)}">{get_specialist_name(spec)}</span>', unsafe_allow_html=True)
        else:
            st.info("本轮尚未调用专家")
        # 思考耗时
        st.markdown('<div class="sidebar-title">⏱️ 思考耗时</div>', unsafe_allow_html=True)

        last_time = st.session_state.last_thinking_time
        if last_time > 0:
            st.metric("最近一轮耗时", f"{last_time:.2f} 秒")
        else:
            st.info("暂无耗时记录")

        history = st.session_state.thinking_time_history
        if history:
            with st.expander("查看每轮耗时", expanded=False):
                for item in reversed(history[-10:]):
                    st.write(
                        f"第 {item['round']} 轮：{item['elapsed']:.2f} 秒 "
                        f"（{item['time']}）"
                    )
        # 分隔线
        st.divider()

        # 操作按钮
        if st.button("🔄 重新开始", use_container_width=True):
            st.session_state.messages = []
            st.session_state.state = create_initial_state()
            st.session_state.round_num = 0
            st.session_state.started = False
            st.session_state.final_report_shown = False
            st.session_state.current_lie_index = 0.0
            st.session_state.dimension_scores = {}
            st.session_state.called_specialists = []
            st.session_state.streaming_text = ""
            st.session_state.is_streaming = False
            st.session_state.thinking_time_history = []
            st.session_state.last_thinking_time = 0.0
            st.session_state.saved_filepath = ""
            st.session_state.saved_log_filepath = ""
            st.session_state.round_records = []
            st.session_state.live_agent_thoughts = []
            st.session_state.live_agent_round = None
            st.session_state.is_processing = False
            reset_logger()  # 清空上一轮日志
            st.rerun()

    # ============== 主内容区 ==============
    st.title("🤖 多 Agent 相亲对话小助手 v3.0")
    dialogue_tab, monitor_tab = st.tabs(["对话", "Agent 思考监控"])

    with monitor_tab:
        monitor_placeholder = st.empty()
        with monitor_placeholder.container():
            render_agent_monitor()

    with dialogue_tab:
        render_dialogue_page(monitor_placeholder)


def render_dialogue_page(monitor_placeholder=None):
    """渲染主对话页；Agent 思考展示由监控 Tab 承担。"""

    # 欢迎区域（仅在未开始时显示）
    if not st.session_state.started:
        st.markdown(f"""
        <div class="welcome-area">
            <div class="welcome-title">👋 欢迎使用风险指数测评系统</div>
            <div class="welcome-subtitle">
                本系统通过多 Agent 协作分析，评估对话中的风险指数。<br>
                系统将自动进行语义分析、逻辑验证、领域知识检查和心理语言学分析。<br>
                最大对话轮次：{MAX_ROUNDS}轮
            </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 开始测评", use_container_width=True, type="primary"):
                reset_logger()  # 新会话开始，重置日志
                st.session_state.started = True
                st.session_state.live_agent_thoughts = []
                st.session_state.live_agent_round = None
                # 初始化第一轮
                opening_question = "你平时是做什么方向的工作呀？"
                st.session_state.messages.append({"role": "assistant", "content": opening_question})
                st.session_state.state["last_followup_question"] = opening_question
                st.session_state.state["dialogue_history"].append({
                    "role": "assistant",
                    "content": opening_question,
                })
                st.rerun()
        return

    # ============== 聊天历史显示 ==============
    chat_container = st.container()
    with chat_container:
        for i, msg in enumerate(st.session_state.messages):
            # 最后一条AI消息且正在流式输出时显示光标
            is_last = (i == len(st.session_state.messages) - 1)
            is_streaming = is_last and st.session_state.is_streaming and msg["role"] == "assistant"
            render_message(msg, is_streaming=is_streaming)

    # ============== 最终报告显示 ==============
    if st.session_state.final_report_shown and st.session_state.state.get("final_report"):
        report = st.session_state.state["final_report"]
        st.markdown("""
        <div class="report-area">
            <h3>📋 最终测评报告</h3>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(report.get("report_text", ""))

    # ============== 输入区域 ==============
    if st.session_state.started and not st.session_state.final_report_shown:
        # 检查是否已达到最大轮次
        if st.session_state.round_num >= MAX_ROUNDS:
            st.warning("已达到最大对话轮次，正在生成最终报告...")
            _generate_final_report(monitor_placeholder)
            return

        # 用户输入
        user_input = st.chat_input("请输入您的回答...")

        if user_input:
            # 添加用户消息
            st.session_state.messages.append({"role": "user", "content": user_input})
            st.session_state.state["current_user_text"] = user_input
            st.session_state.state["dialogue_history"].append({
                "role": "user",
                "content": user_input,
            })

            # 增加轮次
            st.session_state.round_num += 1
            round_num = st.session_state.round_num
            st.session_state.state["round_id"] = round_num
            st.session_state.live_agent_round = round_num
            st.session_state.live_agent_thoughts = []
            st.session_state.is_processing = True

            # 清空本轮临时字段，避免上一轮结果残留
            st.session_state.state["specialist_results"] = []
            st.session_state.state["called_specialists"] = []
            st.session_state.state["current_facts"] = []
            st.session_state.state["current_anomalies"] = []
            st.session_state.state["risk_explanation"] = []
            st.session_state.state["dimension_scores"] = {}

            # 开始日志轮次记录
            logger = get_logger()
            logger.start_round(round_num, user_input)

            with st.status("🤔 系统思考中...", expanded=False) as status:
                t_start = time.time()
                accumulated_state = dict(st.session_state.state)
                agent_thoughts = []
                generated_followup = ""

                try:
                    # 使用 stream 代替 invoke，逐个节点获取更新
                    for event in st.session_state.graph.stream(st.session_state.state, stream_mode="updates"):
                        # event 是一个 dict，key 为节点名称，value 为节点输出
                        for node_name, node_update in event.items():
                            # 使用安全合并函数，避免列表覆盖
                            merge_node_update(accumulated_state, node_update)
                            if node_name == "followup_generation":
                                generated_followup = node_update.get("last_followup_question", "") or ""

                            # 更新状态栏标签
                            title = get_node_title(node_name)
                            status.update(label=f"正在分析: {title}")

                            # 提取自然语言展示
                            thought_text = extract_agent_thoughts(node_name, node_update)

                            # 实时阶段不再尝试获取耗时，先记为 None
                            if thought_text:
                                thought_entry = {
                                    "node": node_name,
                                    "title": title,
                                    "content": thought_text,
                                    "elapsed_seconds": None,
                                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                }
                                append_live_agent_thought(agent_thoughts, thought_entry)
                                if monitor_placeholder is not None:
                                    with monitor_placeholder.container():
                                        render_live_agent_monitor(round_num, st.session_state.live_agent_thoughts)

                    # 所有节点执行完毕
                    t_end = time.time()
                    elapsed = t_end - t_start

                    # 更新最终状态
                    st.session_state.state.update(accumulated_state)

                    # 日志记录结束
                    logger.end_round()
                    node_times = {}
                    if logger.session_data.get("rounds"):
                        last_round = logger.session_data["rounds"][-1]
                        for node in last_round.get("nodes", []):
                            node_times[node["node_name"]] = node["elapsed_seconds"]

                    # 回填 agent_thoughts 的耗时
                    for thought in agent_thoughts:
                        node_name = thought.get("node")
                        thought["elapsed_seconds"] = node_times.get(node_name)

                    # 计时
                    st.session_state.last_thinking_time = elapsed
                    st.session_state.thinking_time_history.append({
                        "round": round_num,
                        "elapsed": elapsed,
                        "time": datetime.now().strftime("%H:%M:%S"),
                    })

                    # 构建 round_record
                    round_record = {
                        "round": round_num,
                        "user_input": user_input,
                        "ai_followup": generated_followup,
                        "elapsed": elapsed,
                        "node_times": node_times,
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

                        "lie_index": st.session_state.state.get("lie_index", 0.0),
                        "dimension_scores": st.session_state.state.get("dimension_scores", {}),
                        "risk_explanation": st.session_state.state.get("risk_explanation", []),

                        "quick_fact_summary": st.session_state.state.get("quick_fact_summary", ""),
                        "quick_signal_summary": st.session_state.state.get("quick_signal_summary", ""),
                        "surface_risk_score": st.session_state.state.get("surface_risk_score", 0.0),
                        "has_new_fact": st.session_state.state.get("has_new_fact", False),

                        "selected_specialists": st.session_state.state.get("selected_specialists", []),
                        "called_specialists": st.session_state.state.get("called_specialists", []),
                        "routing_decision": st.session_state.state.get("routing_decision", {}),

                        "priority_issue": st.session_state.state.get("priority_issue", ""),
                        "followup_strategy": st.session_state.state.get("followup_strategy", ""),

                        "current_facts": st.session_state.state.get("current_facts", []),
                        "current_anomalies": st.session_state.state.get("current_anomalies", []),

                        "agent_thoughts": agent_thoughts,
                    }
                    st.session_state.round_records.append(round_record)
                    st.session_state.live_agent_thoughts = []
                    st.session_state.live_agent_round = None
                    st.session_state.is_processing = False

                    # 更新显示数据
                    st.session_state.current_lie_index = st.session_state.state.get("lie_index", 0.0)
                    st.session_state.dimension_scores = st.session_state.state.get("dimension_scores", {})
                    st.session_state.called_specialists = st.session_state.state.get("called_specialists", [])

                    status.update(label=f"✅ 分析完成（耗时 {elapsed:.2f}秒）", state="complete")

                except Exception as e:
                    logger.end_round()  # 即使出错也要结束本轮日志
                    st.session_state.live_agent_thoughts = []
                    st.session_state.live_agent_round = None
                    st.session_state.is_processing = False
                    status.update(label=f"❌ 分析出错: {str(e)}", state="error")
                    st.error(f"运行出错：{e}")
                    return

            # 获取追问或报告
            next_action = st.session_state.state.get("next_action", "")

            if next_action == "final_report":
                _generate_final_report(monitor_placeholder)
            else:
                followup = st.session_state.state.get("last_followup_question", "")
                if followup:
                    _stream_ai_message(followup)

            st.rerun()


def _stream_ai_message(message: str, chunk_size: int = 2, delay: float = 0.03):
    """流式输出AI消息

    使用 Streamlit 的 st.empty() 占位符和 time.sleep() 模拟流式输出效果。
    注意：由于 Streamlit 的运行机制，这里的流式输出是在单次脚本运行中完成的。

    Args:
        message: 要显示的完整消息
        chunk_size: 每次显示的字符数
        delay: 每次显示的延迟（秒）
    """
    # 先添加一个空消息到历史记录（占位）
    st.session_state.messages.append({"role": "assistant", "content": ""})
    msg_index = len(st.session_state.messages) - 1

    # 创建占位符用于流式输出
    placeholder = st.empty()
    displayed_text = ""

    # 模拟流式输出
    for i in range(0, len(message), chunk_size):
        chunk = message[i:i + chunk_size]
        displayed_text += chunk

        # 更新消息内容
        st.session_state.messages[msg_index]["content"] = displayed_text

        # 更新显示，添加光标效果
        placeholder.markdown(f"""
        <div class="chat-message">
            <div class="role-label">🤖 AI</div>
            <div class="ai-message">{displayed_text}<span class="streaming-cursor"></span></div>
        </div>
        """, unsafe_allow_html=True)

        time.sleep(delay)

    # 最终显示（去掉光标）
    st.session_state.messages[msg_index]["content"] = message
    placeholder.markdown(f"""
    <div class="chat-message">
        <div class="role-label">🤖 AI</div>
        <div class="ai-message">{message}</div>
    </div>
    """, unsafe_allow_html=True)

    # 将追问加入对话历史（用于后端状态）
    st.session_state.state["dialogue_history"].append({
        "role": "assistant",
        "content": message,
    })


def _generate_final_report(monitor_placeholder=None):
    """生成并显示最终报告，同时保存完整测试记录"""
    # 保护：避免重复生成
    if st.session_state.final_report_shown:
        return

    display_round = st.session_state.get("round_num", 0)
    # 内部仍用 MAX_ROUNDS 触发 graph 进入 report_generation，不把它作为真实对话轮次展示或保存。
    st.session_state.state["round_id"] = MAX_ROUNDS
    st.session_state.state["specialist_results"] = []
    st.session_state.state["called_specialists"] = []
    st.session_state.state["next_action"] = "final_report"
    st.session_state.live_agent_round = display_round
    st.session_state.live_agent_thoughts = []
    st.session_state.is_processing = True

    # 为最终报告轮次也记录日志
    logger = get_logger()
    logger.start_round(display_round, "（自动生成最终报告）")

    try:
        t_start = time.time()
        accumulated_state = dict(st.session_state.state)
        agent_thoughts = []

        # 使用 stream 获取最终报告过程中的节点分析
        for event in st.session_state.graph.stream(st.session_state.state, stream_mode="updates"):
            for node_name, node_update in event.items():
                merge_node_update(accumulated_state, node_update)

                thought_text = extract_agent_thoughts(node_name, node_update)

                if thought_text:
                    thought_entry = {
                        "node": node_name,
                        "title": get_node_title(node_name),
                        "content": thought_text,
                        "elapsed_seconds": None,
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    append_live_agent_thought(agent_thoughts, thought_entry)
                    if monitor_placeholder is not None:
                        with monitor_placeholder.container():
                            render_live_agent_monitor(display_round, st.session_state.live_agent_thoughts)

        t_end = time.time()
        elapsed = t_end - t_start

        logger.end_round()
        node_times = {}
        if logger.session_data.get("rounds"):
            last_round = logger.session_data["rounds"][-1]
            for node in last_round.get("nodes", []):
                node_times[node["node_name"]] = node["elapsed_seconds"]

        # 回填 agent_thoughts 的耗时
        for thought in agent_thoughts:
            node_name = thought.get("node")
            thought["elapsed_seconds"] = node_times.get(node_name)

        accumulated_state["round_id"] = display_round
        st.session_state.state.update(accumulated_state)
        st.session_state.final_report_shown = True

        # 更新最终数据
        st.session_state.current_lie_index = accumulated_state.get("lie_index", 0.0)
        st.session_state.dimension_scores = accumulated_state.get("dimension_scores", {})

        st.session_state.final_report_agent_thoughts = agent_thoughts
        st.session_state.live_agent_thoughts = []
        st.session_state.live_agent_round = None
        st.session_state.is_processing = False

        # 保存完整 session 数据到 outputs 目录
        saved_path = _save_session_to_outputs(
            st.session_state.state,
            st.session_state.thinking_time_history,
            st.session_state.round_records,
        )
        st.session_state.saved_filepath = saved_path
        safe_sync_output_file(saved_path)
        st.success(f"💾 完整测试记录已保存至：{saved_path}")

        log_path = logger.finalize_session(st.session_state.state)
        st.session_state.saved_log_filepath = log_path
        safe_sync_output_file(log_path)
        st.success(f"📝 详细日志已保存至：{log_path}")

    except Exception as e:
        logger.end_round()
        st.session_state.live_agent_thoughts = []
        st.session_state.live_agent_round = None
        st.session_state.is_processing = False
        st.error(f"生成报告出错：{e}")


if __name__ == "__main__":
    main()

