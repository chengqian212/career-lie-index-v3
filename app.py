"""Streamlit 前端：多 Agent 相亲对话小助手 v3.0

该模块实现了 v3 版本的 Web 交互界面，主要特性包括：
- 美观的聊天界面，大字体显示用户回答和AI提问
- AI提问流式输出效果
- 实时显示分析过程和结果
- 支持中文输出
"""

import json
import copy
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
from nodes.report_generation_node import report_generation_node
from utils.logger import get_logger, reset_logger
from utils.supabase_outputs import safe_sync_output_file


# ============== 页面配置 ==============
st.set_page_config(
    page_title="织心守护·多 Agent 相亲对话小助手 v3.0",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============== 自定义CSS样式 ==============
st.markdown("""
<style>
:root {
    /* 严格参考原图调色盘 */
    --pure-white: #FFFFFF;
    --bg-pearl: #FCFAF7;          /* 更加白皙清透的底色 */
    --japan-red: #E6002D;         /* 灵魂鲜红 */
    --japan-red-hover: #C80024;
    --navy-blue: #2B577A;         /* 稳重深海蓝 */
    --ink-dark: #2B2525;          /* 雅致排版墨黑 */
    --text-muted: #8E8585;        /* 辅助文字灰 */
    
    /* 极其细腻的日系阴影 */
    --clean-line: 1px solid #EFEAE4;
    --soft-shadow: 0 16px 40px rgba(230, 0, 45, 0.03), 0 2px 6px rgba(43, 37, 37, 0.01);
    --hover-shadow: 0 24px 48px rgba(230, 0, 45, 0.06), 0 4px 12px rgba(43, 37, 37, 0.03);
}

/* 全局基调 */
html, body, [class*="css"] {
    font-family: "Hiragino Sans", "Yu Gothic", "PingFang SC", sans-serif;
    color: var(--ink-dark);
}

/* 锁定横向，允许纵向滚动，解决空白和截断问题 */
.stApp {
    background-color: var(--bg-pearl);
    overflow-x: hidden !important;
    overflow-y: auto !important;
}

/* 2. 略微加深右侧粉红波浪的权重（从0.035调至0.07），让浪漫的有机曲线清晰显现 */
.stApp::before {
    content: "";
    position: fixed;
    top: 0;
    right: 0;
    width: 60vw;
    height: 70vh;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 600'%3E%3Cpath fill='%23E6002D' fill-opacity='0.07' d='M550,0 C650,120 720,180 800,220 L800,0 Z M350,0 C450,180 620,280 800,380 L800,0 Z'/%3E%3C/svg%3E");
    background-size: cover;
    background-repeat: no-repeat;
    background-position: top right;
    pointer-events: none;
    z-index: -1;
}

/* 3. 略微加深左侧深蓝波浪的权重（从0.02调至0.04），与底部的大字呼应 */
.stApp::after {
    content: "";
    position: fixed;
    bottom: 0;
    left: 0;
    width: 50vw;
    height: 60vh;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 600'%3E%3Cpath fill='%232B577A' fill-opacity='0.04' d='M0,350 C120,400 250,320 380,450 C450,520 520,550 600,600 L0,600 Z'/%3E%3C/svg%3E");
    background-size: cover;
    background-repeat: no-repeat;
    background-position: bottom left;
    pointer-events: none;
    z-index: -1;
}

/* 1. 裁剪顶部的原生空白，让大标题往上提，显得排版紧凑专业 */
.main .block-container {
    max-width: 1180px;
    padding-top: 1.5rem !important; /* 强制将原来的大空白压缩 */
    position: relative;
    z-index: 2; 
}

/* 侧边栏：清爽且自带微弱透光感 */
section[data-testid="stSidebar"] {
    background-color: rgba(249, 246, 242, 0.92) !important;
    border-right: var(--clean-line) !important;
    box-shadow: 6px 0 30px rgba(34, 30, 30, 0.01) !important;
    z-index: 3 !important; /* 确保侧边栏在最前方 */
}

section[data-testid="stSidebar"] > div {
    padding-top: 2.5rem;
}

/* 标题：纯正明朝体气韵 */
h1, h2, h3 {
    color: var(--ink-dark) !important;
    font-weight: 700 !important;
    letter-spacing: 0.03em !important;
}

h1 {
    font-size: clamp(2.2rem, 3.8vw, 3.2rem) !important;
    font-family: "Hiragino Mincho ProN", serif !important;
    color: var(--ink-dark) !important;
    margin-bottom: 2.5rem !important;
}

/* Tabs 标签页 */
div[data-testid="stTabs"] [role="tablist"] {
    border-bottom: var(--clean-line);
}

div[data-testid="stTabs"] [role="tab"] {
    color: var(--text-muted);
    font-size: 1.05rem;
    padding: 10px 20px;
    background: transparent !important;
}

div[data-testid="stTabs"] [aria-selected="true"] {
    color: var(--japan-red) !important;
    font-weight: 700;
}

div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
    background: var(--japan-red) !important;
    height: 3px !important;
}

/* 聊天气泡：纯白卡片，全面向原图质感靠拢 */
.chat-message {
    margin-bottom: 24px;
}

.role-label {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-muted);
    margin-left: 8px;
    margin-bottom: 6px;
}

.user-message,
.ai-message {
    background-color: var(--pure-white) !important;
    font-size: 1.15rem !important;
    line-height: 1.8 !important;
    padding: 22px 26px !important;
    border-radius: 16px !important;
    border: var(--clean-line) !important;
    box-shadow: var(--soft-shadow) !important;
    transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.user-message:hover, .ai-message:hover {
    transform: translateY(-2px);
    box-shadow: var(--hover-shadow) !important;
}

.ai-message { border-left: 5px solid var(--japan-red) !important; }
.user-message { border-left: 5px solid var(--navy-blue) !important; }

/* 打字机细光标 */
.streaming-cursor {
    display: inline-block;
    width: 2px;
    height: 1.1em;
    background: var(--japan-red);
    animation: blink 0.9s infinite;
    vertical-align: text-bottom;
    margin-left: 4px;
}

@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}

/* 侧边栏卡片：重点突出数字 */
.sidebar-title {
    font-size: 1rem;
    font-weight: 700;
    color: var(--ink-dark);
    border-bottom: var(--clean-line);
    padding-bottom: 8px;
    margin-top: 1.8rem;
}

.stat-card {
    background: var(--pure-white) !important;
    padding: 20px 14px;
    border-radius: 14px;
    margin-bottom: 14px;
    text-align: center;
    border: var(--clean-line) !important;
    box-shadow: var(--soft-shadow) !important;
}

.stat-value {
    font-size: 2.2rem;
    font-weight: 700;
    color: var(--japan-red);
}

.stat-label {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-top: 4px;
}

/* 风险状态胶囊 */
.risk-indicator {
    padding: 12px;
    border-radius: 99px;
    font-weight: 700;
    font-size: 0.9rem;
    text-align: center;
    margin: 15px 0;
}

.risk-low { background-color: #E6F4EA !important; color: #137333 !important; }
.risk-medium { background-color: #FEF7E0 !important; color: #B06000 !important; }
.risk-high { background-color: #FCE8E6 !important; color: #C5221F !important; }

/* 核心看板区组件 */
.analysis-panel,
.report-area,
.monitor-shell,
div[data-testid="stExpander"] {
    background: var(--pure-white) !important;
    border: var(--clean-line) !important;
    border-radius: 18px !important;
    box-shadow: var(--soft-shadow) !important;
}

.report-area {
    padding: 32px;
    border-left: 6px solid var(--japan-red) !important;
}

/* 输入框 */
.stTextInput > div > div > input {
    font-size: 1.05rem !important;
    padding: 14px 18px !important;
    border-radius: 14px !important;
    background: var(--pure-white) !important;
    border: var(--clean-line) !important;
}

.stTextInput > div > div > input:focus {
    border-color: var(--japan-red) !important;
    box-shadow: 0 0 0 3px rgba(230, 0, 45, 0.08) !important;
}

/* 胶囊型经典日式按钮 */
.stButton > button {
    font-size: 1rem !important;
    font-weight: 600 !important;
    padding: 12px 32px !important;
    border-radius: 99px !important;
    color: var(--pure-white) !important;
    border: none !important;
    background: var(--japan-red) !important;
    box-shadow: 0 6px 20px rgba(230, 0, 45, 0.2) !important;
    transition: all 0.25s ease;
}

.stButton > button:hover {
    transform: translateY(-2px);
    background: var(--japan-red-hover) !important;
    box-shadow: 0 8px 26px rgba(230, 0, 45, 0.3) !important;
}

/* 欢迎页 */
.welcome-area {
    text-align: center;
    padding: 60px 40px;
    background: var(--pure-white) !important;
    border-radius: 24px;
    margin-bottom: 35px;
    border: var(--clean-line) !important;
    box-shadow: var(--soft-shadow);
}

.welcome-title {
    font-family: "Hiragino Mincho ProN", serif;
    font-size: 2rem;
    font-weight: 700;
    color: var(--japan-red);
    margin-bottom: 18px;
}

.welcome-subtitle {
    font-size: 1.05rem;
    color: var(--text-muted);
    line-height: 1.8;
}

/* 统一收口突兀的 Streamlit 组件 */
div[data-testid="stAlert"], div[data-testid="stNotification"] {
    background-color: #FDFBF9 !important;
    color: var(--ink-dark) !important;
    border: var(--clean-line) !important;
    border-radius: 12px !important;
}
div[data-testid="stAlert"] div { color: var(--ink-dark) !important; }

/* 便签便签化标签 */
.specialist-tag {
    display: inline-block;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    margin-right: 6px;
    margin-bottom: 8px;
    border: var(--clean-line);
}
.specialist-semantic { background: #EBF4FA; color: #4A6B82; }
.specialist-logical { background: #EEF5F1; color: #4A7356; }
.specialist-domain { background: #F9F2EB; color: #8A653E; }
.specialist-psycho { background: #F5EFF9; color: #724A82; }

/* 思考卡片 */
.thought-card {
    border-left: 3px solid var(--text-muted);
    background: #FAF8F5;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 12px 0;
    font-size: 0.95rem;
    color: var(--ink-dark);
}
.thought-semantic { border-left-color: var(--navy-blue); }
.thought-logical { border-left-color: #4A7356; }
.thought-domain { border-left-color: #8A653E; }
.thought-psycho { border-left-color: #724A82; }

/* 进度条 */
div[data-testid="stProgress"] > div > div > div > div {
    background-color: var(--japan-red) !important;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
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
        "specificity_level": "MEDIUM",
        "experience_density": "MEDIUM",
        "generic_answer_flag": False,
        "generic_answer_reason": "",
        "suggested_probe_angle": "",
        "generic_answer_streak": 0,
        "generic_answer_count": 0,
        "last_probe_angle": "",
        "used_probe_angles": [],
        "routing_decision": {},
        "selected_specialists": [],
        "priority_issue": "",
        "followup_strategy": "",
        "called_specialists": [],
        # v3.3 新增字段
        "stop_reason": "",
        "target_anomaly_id": "",
        "identity_label": "",   # "real" or "fake"
    }


def get_risk_level(lie_index: float) -> tuple[str, str]:
    """根据谎言指数返回风险等级和样式类"""
    if lie_index >= 60:
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
        "experience_density": state.get("experience_density", ""),
        "specificity_level": state.get("specificity_level", ""),
        "generic_answer_flag": state.get("generic_answer_flag", False),
        "generic_answer_reason": state.get("generic_answer_reason", ""),
        "suggested_probe_angle": state.get("suggested_probe_angle", ""),
        "generic_answer_streak": state.get("generic_answer_streak", 0),
        "generic_answer_count": state.get("generic_answer_count", 0),
        "used_probe_angles": state.get("used_probe_angles", []),
        "called_specialists": state.get("called_specialists", []),
        "routing_decision": state.get("routing_decision", {}),
        "final_report": state.get("final_report"),
        "thinking_time_history": thinking_history,
        "identity_label": state.get("identity_label", ""),
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
    """用每轮快照字段重建监控内容，避免历史轮次被当前全局状态污染。"""
    if not isinstance(record, dict) or record.get("is_live"):
        return record

    normalized = dict(record)
    time_text = normalized.get("time", "")
    node_times = normalized.get("node_times", {}) if isinstance(normalized.get("node_times"), dict) else {}
    thoughts = []

    quick_parts = []
    if normalized.get("quick_fact_summary"):
        quick_parts.append(str(normalized.get("quick_fact_summary")))
    if normalized.get("quick_signal_summary"):
        quick_parts.append(str(normalized.get("quick_signal_summary")))
    if normalized.get("experience_density"):
        quick_parts.append(f"经验密度：{normalized.get('experience_density')}")
    if normalized.get("generic_answer_flag") and normalized.get("generic_answer_reason"):
        quick_parts.append(f"泛泛回答：{normalized.get('generic_answer_reason')}")
    if quick_parts:
        thoughts.append({
            "node": "quick_preanalysis",
            "title": get_node_title("quick_preanalysis"),
            "content": "；".join(quick_parts),
            "elapsed_seconds": node_times.get("quick_preanalysis_node"),
            "time": time_text,
        })

    rd = normalized.get("routing_decision", {})
    if isinstance(rd, dict):
        selected = normalized.get("selected_specialists", []) or rd.get("selected_specialists", [])
        route_parts = []
        if selected:
            names = [get_specialist_name(s) for s in selected if s]
            route_parts.append(f"调用专家：{', '.join(names) if names else '语义、逻辑'}")
        else:
            route_parts.append("系统判定本轮无需调用专家，直接进入风险聚合")
        reason = rd.get("routing_reason") or rd.get("reason") or rd.get("decision_reason") or ""
        if reason:
            route_parts.append(f"原因：{reason}")
        if normalized.get("priority_issue"):
            route_parts.append(f"关注点：{normalized.get('priority_issue')}")
        thoughts.append({
            "node": "lightweight_routing_supervisor",
            "title": get_node_title("lightweight_routing_supervisor"),
            "content": "；".join(route_parts),
            "elapsed_seconds": node_times.get("lightweight_routing_supervisor_node"),
            "time": time_text,
        })

    original_thoughts = normalized.get("agent_thoughts", [])
    specialist_nodes = {
        "semantic_agent",
        "logical_agent",
        "domain_agent",
        "psycho_linguistic_agent",
    }
    for thought in original_thoughts:
        if isinstance(thought, dict) and thought.get("node") in specialist_nodes:
            thoughts.append(dict(thought))

    risk_explanation = normalized.get("risk_explanation", [])
    if isinstance(risk_explanation, list):
        risk_text = "；".join(str(item) for item in risk_explanation)
    else:
        risk_text = str(risk_explanation or "")
    risk_parts = [f"风险指数 {normalized.get('lie_index', 0.0)}"]
    if risk_text:
        risk_parts.append(risk_text)
    thoughts.append({
        "node": "risk_aggregator",
        "title": get_node_title("risk_aggregator"),
        "content": "，".join(risk_parts),
        "elapsed_seconds": node_times.get("risk_aggregator_node"),
        "time": time_text,
    })

    stop_reason = str(normalized.get("stop_reason") or "")
    priority_issue = str(normalized.get("priority_issue") or "")
    followup_strategy = str(normalized.get("followup_strategy") or "")
    next_action = str(normalized.get("next_action") or "")
    if next_action == "final_report":
        strategy_content = f"信息已足够，生成最终报告（{stop_reason}）"
    else:
        strategy_content = (
            f"继续追问（{stop_reason or '本轮仍有可追问信息'}），"
            f"关注：{priority_issue or '待澄清点'}，策略：{followup_strategy or '未指定'}"
        )
    thoughts.append({
        "node": "strategy_supervisor",
        "title": get_node_title("strategy_supervisor"),
        "content": strategy_content,
        "elapsed_seconds": node_times.get("strategy_supervisor_node"),
        "time": time_text,
    })

    followup = str(normalized.get("ai_followup") or "").strip()
    if followup:
        thoughts.append({
            "node": "followup_generation",
            "title": get_node_title("followup_generation"),
            "content": f"生成追问：{followup}",
            "elapsed_seconds": node_times.get("followup_generation_node"),
            "time": time_text,
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
        density = node_update.get("experience_density", "")
        generic = node_update.get("generic_answer_flag", False)
        generic_reason = node_update.get("generic_answer_reason", "")
        parts = []
        if fact:
            parts.append(fact)
        if signal:
            parts.append(signal)
        if density:
            parts.append(f"经验密度：{density}")
        if generic and generic_reason:
            parts.append(f"泛泛回答：{generic_reason}")
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

                return None

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
                "experience_density": "经验密度",
                "quick_preanalysis": "表层风险",
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
        if st.button("重新开始", use_container_width=True):
            st.session_state.identity_label = "真实身份"
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
    st.markdown("""
        <h1 style='position: relative; z-index: 2;'>
             织心守护 <span style='font-size: 1.6rem; font-weight: 400; color: var(--text-muted); vertical-align: middle;'>· 多 Agent 职业身份真实性分析系统 v3.0</span>
        </h1>
    """, unsafe_allow_html=True)
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
            <div class="welcome-title">✨ 欢迎使用 织心守护 · 多 Agent 职业身份真实性分析系统</div>
            <div class="welcome-subtitle" style="margin-top: 12px;">  
                本系统采用多 Agent 协同架构，从语义、逻辑、常识及行为特征四个维度为您客观分析职业身份的真实性。<br><br>
                <strong>为了让算法评估更精准，请在接下来的对话中尽可能详细、充分地回答每一个问题。</strong>您提供的细节信息越丰富，系统推演的确定性就越高。<br><br>
                <strong>建议对话轮次：{MAX_ROUNDS}轮</strong>
            </div>
        </div>
        """, unsafe_allow_html=True)

        identity = st.radio(
            "您的回答将基于？",
            ["真实身份", "虚假身份"],
            horizontal=True,
            key="identity_label"
        )
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("开始测评", use_container_width=True, type="primary"):
                reset_logger()  # 新会话开始，重置日志
                st.session_state.state["identity_label"] = ("real" if st.session_state.identity_label == "真实身份" else "fake")
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
                    frozen_agent_thoughts = copy.deepcopy(agent_thoughts)
                    round_record = {
                        "round": round_num,
                        "user_input": user_input,
                        "ai_followup": generated_followup,
                        "elapsed": elapsed,
                        "node_times": node_times,
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

                        "lie_index": st.session_state.state.get("lie_index", 0.0),
                        "dimension_scores": copy.deepcopy(st.session_state.state.get("dimension_scores", {})),
                        "risk_explanation": copy.deepcopy(st.session_state.state.get("risk_explanation", [])),

                        "quick_fact_summary": st.session_state.state.get("quick_fact_summary", ""),
                        "quick_signal_summary": st.session_state.state.get("quick_signal_summary", ""),
                        "surface_risk_score": st.session_state.state.get("surface_risk_score", 0.0),
                        "has_new_fact": st.session_state.state.get("has_new_fact", False),
                        "specificity_level": st.session_state.state.get("specificity_level", ""),
                        "experience_density": st.session_state.state.get("experience_density", ""),
                        "generic_answer_flag": st.session_state.state.get("generic_answer_flag", False),
                        "generic_answer_reason": st.session_state.state.get("generic_answer_reason", ""),
                        "suggested_probe_angle": st.session_state.state.get("suggested_probe_angle", ""),
                        "generic_answer_streak": st.session_state.state.get("generic_answer_streak", 0),
                        "generic_answer_count": st.session_state.state.get("generic_answer_count", 0),

                        "selected_specialists": copy.deepcopy(st.session_state.state.get("selected_specialists", [])),
                        "called_specialists": copy.deepcopy(st.session_state.state.get("called_specialists", [])),
                        "routing_decision": copy.deepcopy(st.session_state.state.get("routing_decision", {})),

                        "priority_issue": st.session_state.state.get("priority_issue", ""),
                        "followup_strategy": st.session_state.state.get("followup_strategy", ""),
                        "stop_reason": st.session_state.state.get("stop_reason", ""),
                        "next_action": st.session_state.state.get("next_action", ""),

                        "current_facts": copy.deepcopy(st.session_state.state.get("current_facts", [])),
                        "current_anomalies": copy.deepcopy(st.session_state.state.get("current_anomalies", [])),

                        "agent_thoughts": frozen_agent_thoughts,
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
    # 最终报告只汇总当前状态，不再重跑整张图，避免最后一条输入覆盖历史风险。
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

        report_update = report_generation_node(st.session_state.state)
        merge_node_update(accumulated_state, report_update)

        thought_text = extract_agent_thoughts("report_generation", report_update)
        if thought_text:
            thought_entry = {
                "node": "report_generation",
                "title": get_node_title("report_generation"),
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
        report_synced, report_sync_msg = safe_sync_output_file(saved_path)
        if report_synced:
            st.success("☁️ 报告已同步到 Supabase")
        else:
            st.warning(f"☁️ 报告未同步到 Supabase：{report_sync_msg}")
        st.success(f"💾 完整测试记录已保存至：{saved_path}")

        log_path = logger.finalize_session(st.session_state.state)
        st.session_state.saved_log_filepath = log_path
        st.success(f"📝 详细日志已保存至：{log_path}")

    except Exception as e:
        logger.end_round()
        st.session_state.live_agent_thoughts = []
        st.session_state.live_agent_round = None
        st.session_state.is_processing = False
        st.error(f"生成报告出错：{e}")


if __name__ == "__main__":
    main()

