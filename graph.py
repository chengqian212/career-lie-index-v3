"""LangGraph workflow definition for the v3 agent."""
# 该文件定义了 v3 版本多智能体谎言指数测评系统的工作流
# 使用 LangGraph 构建节点（Agent、Supervisor、Aggregator等）和路由逻辑

from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from state_schema import DialogueState  # 定义全局状态结构
from utils.node_wrapper import wrap_node  # 包装节点为可执行形式

# 导入各节点
from nodes.quick_preanalysis_node import quick_preanalysis_node
from nodes.lightweight_routing_supervisor_node import lightweight_routing_supervisor_node

from nodes.specialists.semantic_agent_node import semantic_agent_node
from nodes.specialists.logical_agent_node import logical_agent_node
from nodes.specialists.domain_agent_node import domain_agent_node
from nodes.specialists.psycho_linguistic_agent_node import psycho_linguistic_agent_node

from nodes.risk_aggregator_node import risk_aggregator_node
from nodes.strategy_supervisor_node import strategy_supervisor_node
from nodes.followup_generation_node import followup_generation_node
from nodes.report_generation_node import report_generation_node

# =================== 节点包装 ===================
# wrap_node 的作用是将函数/对象包装为 LangGraph 可执行节点
quick_preanalysis_node = wrap_node(quick_preanalysis_node)
lightweight_routing_supervisor_node = wrap_node(lightweight_routing_supervisor_node)
semantic_agent_node = wrap_node(semantic_agent_node)
logical_agent_node = wrap_node(logical_agent_node)
domain_agent_node = wrap_node(domain_agent_node)
psycho_linguistic_agent_node = wrap_node(psycho_linguistic_agent_node)
risk_aggregator_node = wrap_node(risk_aggregator_node)
strategy_supervisor_node = wrap_node(strategy_supervisor_node)
followup_generation_node = wrap_node(followup_generation_node)
report_generation_node = wrap_node(report_generation_node)


# =================== 路由函数 ===================
def route_specialists(state: DialogueState) -> list[Send]:
    """
    Fan out to the specialists selected by the routing supervisor.
    根据轻量路由 Supervisor 的决策，将任务分发给选中的专家节点
    """
    selected = state.get("selected_specialists", [])  # 获取 supervisor 决定的专家列表
    mapping = {
        "semantic": "semantic_agent",
        "logical": "logical_agent",
        "domain": "domain_agent",
        "psycho_linguistic": "psycho_linguistic_agent",
    }
    # 返回 Send 对象列表，Send 用于将 state 发送到指定节点
    return [Send(mapping[s], state) for s in selected if s in mapping]


def route_after_routing_supervisor(state: DialogueState) -> list[Send]:
    """
    Route to selected specialists, or skip directly to risk aggregation.
    根据路由结果选择专家，如果不需要专家，则直接走风险聚合
    """
    routing_decision = state.get("routing_decision", {})
    if isinstance(routing_decision, dict) and routing_decision.get("router_mode") == "retry_quick_preanalysis":
        return [Send("quick_preanalysis", state)]
    if not state.get("selected_specialists", []):
        return [Send("risk_aggregator", state)]  # 无专家时直接聚合
    return route_specialists(state)


def route_after_strategy_supervisor(state: DialogueState) -> str:
    """
    Route to follow-up generation or final report generation.
    根据策略 Supervisor 的决策选择后续行动
    """
    if state.get("next_action") == "final_report":
        return "report_generation"
    return "followup_generation"


# =================== 图构建函数 ===================
def build_graph() -> CompiledStateGraph:
    """
    Build the v3 workflow graph.
    构建完整的 v3 工作流图，包括节点、边和条件路由
    """
    builder = StateGraph(DialogueState)  # 使用 DialogueState 作为全局状态结构

    # ------------------- 添加节点 -------------------
    # 第一层：快速预分析与路由
    builder.add_node("quick_preanalysis", quick_preanalysis_node)
    builder.add_node("lightweight_routing_supervisor", lightweight_routing_supervisor_node)

    # 第二层：专家 Agent
    builder.add_node("semantic_agent", semantic_agent_node)
    builder.add_node("logical_agent", logical_agent_node)
    builder.add_node("domain_agent", domain_agent_node)
    builder.add_node("psycho_linguistic_agent", psycho_linguistic_agent_node)

    # 第三层：风险聚合与策略决策
    builder.add_node("risk_aggregator", risk_aggregator_node)
    builder.add_node("strategy_supervisor", strategy_supervisor_node)

    # 第四层：后续生成
    builder.add_node("followup_generation", followup_generation_node)
    builder.add_node("report_generation", report_generation_node)

    # ------------------- 添加边 -------------------
    builder.add_edge(START, "quick_preanalysis")  # 开始节点 → 快速预分析
    builder.add_edge("quick_preanalysis", "lightweight_routing_supervisor")  # 分析完成 → 路由 Supervisor
    builder.add_conditional_edges("lightweight_routing_supervisor", route_after_routing_supervisor)  # 条件路由到专家或风险聚合

    # 专家节点 → 风险聚合节点（并行执行）
    for agent in ("semantic_agent", "logical_agent", "domain_agent", "psycho_linguistic_agent"):
        builder.add_edge(agent, "risk_aggregator")

    # 风险聚合 → 策略 Supervisor
    builder.add_edge("risk_aggregator", "strategy_supervisor")

    # 策略 Supervisor 条件路由到追问或报告生成
    builder.add_conditional_edges(
        "strategy_supervisor",
        route_after_strategy_supervisor,
        {
            "followup_generation": "followup_generation",
            "report_generation": "report_generation",
        },
    )

    # 最终节点
    builder.add_edge("followup_generation", END)
    builder.add_edge("report_generation", END)

    return builder.compile()  # 返回编译后的 StateGraph，可直接执行

