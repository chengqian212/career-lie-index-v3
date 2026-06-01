"""CLI 入口：命令行交互式多 Agent 谎言指数测评系统

该模块实现了 v3 版本的 CLI 交互入口，主要特性包括：
- 命令行交互式对话界面
- 轻量预分析 + 条件路由 + 按需专家调用
- 实时显示分析过程和结果
- 支持中文输出（Windows UTF-8 编码）

v3.3 改进：
- 支持显示 stop_reason（策略监督决定继续或结束的原因）
"""

import json
import os
import sys
import time
from datetime import datetime

# -------------------- Windows 终端 UTF-8 编码 --------------------
if sys.platform == "win32":
    # 设置 Windows 控制台代码页为 UTF-8
    os.system("chcp 65001 >nul 2>&1")
    # 重新配置标准输出和错误输出编码
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# -------------------- 确保 v3 目录作为项目根目录在 sys.path 中 --------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# -------------------- 导入项目配置和模块 --------------------
from config import (
    disable_proxy,  # 关闭代理
    MAX_ROUNDS,     # 最大轮次配置
)
from graph import build_graph  # 构建 v3 工作流图
from state_schema import DialogueState  # 全局状态结构
from utils.logger import get_logger, reset_logger  # 日志工具

# =================== 创建初始状态 ===================
def create_initial_state(max_rounds: int = MAX_ROUNDS) -> dict:
    """
    创建初始状态，包括所有对话轮次、事实/异常表、专家结果等字段

    v3 改进：
    - 新增路由决策、专家选择、轻量预分析等字段
    - v3.3 增加 stop_reason

    Args:
        max_rounds: 最大对话轮次，默认使用配置文件中的 MAX_ROUNDS

    Returns:
        初始状态字典
    """
    return {
        # 基础轮次
        "round_id": 0,
        "max_rounds": max_rounds,
        
        # 对话相关
        "current_user_text": "",
        "dialogue_history": [],
        
        # 事实和异常检测
        "current_facts": [],
        "facts_table": [],
        "current_anomalies": [],
        "indicator_history": [],
        "anomalies_table": [],
        
        # 追问机制
        "last_followup_question": "",
        "followup_history": [],
        
        # 专家分析
        "specialist_results": [],
        "dimension_scores": {},
        
        # 最终评估
        "lie_index": 0.0,
        "risk_explanation": [],
        "next_action": "",
        "final_report": None,
        
        # v3 新增：轻量预分析
        "quick_fact_summary": "",
        "quick_signal_summary": "",
        "surface_risk_score": 0.0,
        "severity": "",
        "confidence": "",
        "schema_error": "",
        "schema_errors": [],
        "quick_preanalysis_retry_count": 0,
        "has_new_fact": False,
        
        # v3 新增：路由决策
        "routing_decision": {},
        "selected_specialists": [],
        "priority_issue": "",
        "followup_strategy": "",
        "called_specialists": [],
        
        # v3.3 新增：策略监督
        "stop_reason": "",
        "target_anomaly_id": "",
    }

# =================== 打印每轮分析摘要 ===================
def print_round_summary(state: dict, elapsed: float = 0.0) -> None:
    """
    打印本轮分析摘要，包括：
    - 当前轮次
    - 调用的专家
    - 谎言指数与各维度分数
    - 风险解释
    - 路由原因 & stop_reason
    - 系统追问与耗时

    v3.3 改进：显示 stop_reason
    """
    round_id = state.get("round_id", 0)
    lie_index = state.get("lie_index", 0)
    dimension_scores = state.get("dimension_scores", {})
    risk_explanation = state.get("risk_explanation", [])
    followup = state.get("last_followup_question", "")
    
    called_specialists = state.get("called_specialists", [])
    routing_reason = state.get("routing_decision", {}).get("routing_reason", "")
    stop_reason = state.get("stop_reason", "")

    print("\n" + "=" * 60)
    print(f"📊 当前轮次：{round_id} / {MAX_ROUNDS}")
    
    # 本轮调用的专家
    if called_specialists:
        specialist_names = {
            "semantic": "语义分析",
            "logical": "逻辑分析",
            "domain": "职业常识",
            "psycho_linguistic": "心理语言",
        }
        called_names = [str(specialist_names.get(s) or s) for s in called_specialists]
        print(f"🤖 本轮调用专家：{', '.join(called_names)}")
    else:
        print(f"🤖 本轮调用专家：无，使用轻量预分析结果")
    
    print("-" * 60)
    print(f"📈 当前谎言指数：{lie_index} / 100")
    print("-" * 60)

    # 各维度分数
    if dimension_scores:
        print("📊 各维度分数：")
        score_names = {
            "semantic": "语义一致性",
            "logical": "逻辑时间线",
            "domain": "职业常识",
            "psycho_linguistic": "心理语言",
            "lightweight_surface": "表层风险",
            "unresolved_anomalies": "未澄清异常",
        }
        for key, score in dimension_scores.items():
            name = score_names.get(key) or key
            print(f"   {name}：{score}")

    print("-" * 60)

    # 路由原因
    if routing_reason:
        print(f"🔍 选择调用专家原因：{routing_reason}")

    # 停止/继续原因
    if stop_reason:
        reason_explanations = {
            "max_rounds": "已达最大轮次",
            "enough_information_no_active_anomaly": "信息充分且无活跃疑点",
            "anomaly_resolved": "疑点已被澄清",
            "followup_exhausted": "疑点追问次数已达上限",
            "anomaly_confirmed": "疑点已基本坐实",
            "need_more_information_or_clarification": "仍需继续追问",
        }
        reason_text = reason_explanations.get(stop_reason, stop_reason)
        print(f"🛑 决策原因：{reason_text}")

    # 风险原因
    if risk_explanation:
        print("⚠️  主要分析原因：")
        for exp in risk_explanation:
            print(f"   - {exp}")

    print("-" * 60)

    # 系统追问与耗时
    if followup:
        print(f"❓ 系统追问：{followup}")
    if elapsed > 0:
        print(f"⏱️  系统思考耗时：{elapsed:.2f} 秒")
    print("=" * 60)

# =================== 打印最终报告 ===================
def print_final_report(state: dict) -> None:
    """打印最终报告并保存"""
    final_report = state.get("final_report")
    if not final_report:
        print("\n❌ 未生成最终报告")
        return

    print("\n" + "=" * 60)
    print("📋 最终测评报告")
    print("=" * 60)
    print(final_report.get("report_text", ""))
    print("=" * 60)

    save_report(final_report)

# =================== 保存报告 ===================
def save_report(report: dict) -> None:
    """保存报告到 outputs/reports/ 文件夹，以时间戳命名"""
    reports_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "outputs",
        "reports",
    )
    os.makedirs(reports_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{timestamp}.json"
    filepath = os.path.join(reports_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n💾 报告已保存至：{filepath}")


def get_specialist_label(name: str) -> str:
    """返回专家标识的中文名称。"""
    labels = {
        "semantic": "语义",
        "logical": "逻辑",
        "domain": "领域",
        "psycho_linguistic": "心理语言",
    }
    return str(labels.get(name) or name)


# =================== 打印详细节点日志 ===================
def print_detailed_node_log(logger, round_id: int) -> None:
    """
    打印每轮各节点的详细执行日志：
    - 输入/输出
    - 耗时
    - 调用专家
    - stop_reason
    """
    # 查找本轮节点日志
    nodes = []
    for r in logger.session_data.get("rounds", []):
        if r.get("round_id") == round_id:
            nodes = r.get("nodes", [])
            break
    if not nodes and logger.current_round and logger.current_round.get("round_id") == round_id:
        nodes = logger.current_round.get("nodes", [])
    if not nodes:
        return

    # 英文名 → 中文名映射
    node_name_map = {
        "quick_preanalysis_node": "快速预分析",
        "lightweight_routing_supervisor_node": "轻量路由监督",
        "semantic_agent_node": "语义一致性分析",
        "logical_agent_node": "逻辑时间线分析",
        "domain_agent_node": "职业常识分析",
        "psycho_linguistic_agent_node": "心理语言学分析",
        "risk_aggregator_node": "风险计算",
        "strategy_supervisor_node": "下一步策略",
        "followup_generation_node": "追问生成",
        "report_generation_node": "报告生成",
    }

    print("\n" + "┌" + "─" * 58 + "┐")
    print(f"│ 📝 轮次 {round_id} 详细节点执行日志{' ' * (58 - 17 - len(str(round_id)))}│")
    print("├" + "─" * 58 + "┤")

    for i, node in enumerate(nodes):
        name = node.get("node_name", "")
        cn_name = str(node_name_map.get(name) or name)
        elapsed = node.get("elapsed_seconds", 0)
        success = node.get("success", False)
        status_icon = "✅" if success else "❌"
        output = node.get("output", {}) or {}

        print(f"│ {status_icon} [{i + 1}] {cn_name} ({name})")
        print(f"│     耗时: {elapsed:.3f}s")

        if node.get("error"):
            print(f"│     错误: {node['error']}")

        if output.get("quick_fact_summary"):
            summary = str(output["quick_fact_summary"])
            print(f"│     事实摘要: {summary[:77] + '...' if len(summary) > 80 else summary}")
        if output.get("quick_signal_summary"):
            summary = str(output["quick_signal_summary"])
            print(f"│     信号摘要: {summary[:77] + '...' if len(summary) > 80 else summary}")
        if "surface_risk_score" in output:
            print(f"│     表面风险分: {output['surface_risk_score']}")
        if output.get("schema_error"):
            print(f"│     Schema 异常: {output['schema_error']}")

        if "selected_specialists" in output:
            selected = output.get("selected_specialists") or []
            if selected:
                names = [get_specialist_label(s) for s in selected]
                print(f"│     选中专家: {', '.join(names)}")
            else:
                print("│     选中专家: 无")

        if output.get("called_specialists"):
            names = [get_specialist_label(s) for s in output["called_specialists"]]
            print(f"│     已调用专家: {', '.join(names)}")

        if output.get("specialist_results"):
            for result in output["specialist_results"]:
                if not isinstance(result, dict):
                    continue
                agent = get_specialist_label(result.get("agent", "?"))
                score = result.get("score", "?")
                print(f"│     [{agent}] 分数: {score}")
                evidence = result.get("evidence_list") or result.get("findings") or []
                if isinstance(evidence, list):
                    for item in evidence[:2]:
                        if isinstance(item, dict):
                            desc = item.get("description") or item.get("explanation") or item.get("finding")
                        else:
                            desc = str(item)
                        if desc:
                            desc = str(desc)
                            print(f"│       → {desc[:57] + '...' if len(desc) > 60 else desc}")

        if "lie_index" in output:
            print(f"│     谎言指数: {output['lie_index']}")
        if output.get("dimension_scores"):
            parts = [f"{key}:{value}" for key, value in output["dimension_scores"].items()]
            print(f"│     维度分数: {', '.join(parts)}")
        if output.get("risk_explanation"):
            for exp in output["risk_explanation"][:3]:
                exp = str(exp)
                print(f"│     ⚠ {exp[:52] + '...' if len(exp) > 55 else exp}")

        if output.get("stop_reason"):
            print(f"│     决策原因: {output['stop_reason']}")
        if output.get("next_action"):
            action_map = {"final_report": "生成报告", "generate_followup": "继续追问"}
            print(f"│     下一步: {action_map.get(output['next_action'], output['next_action'])}")
        if output.get("last_followup_question"):
            question = str(output["last_followup_question"])
            print(f"│     追问: {question[:52] + '...' if len(question) > 55 else question}")

        if i < len(nodes) - 1:
            print("│")

    print("└" + "─" * 58 + "┘")

# =================== 主 CLI 循环 ===================
def run_cli():
    """
    CLI 交互循环：
    1. 初始化日志和图结构
    2. 系统开场问题
    3. 逐轮获取用户输入并调用工作流分析
    4. 打印轮次摘要和详细节点日志
    5. 根据 next_action 或轮次生成最终报告
    """
    disable_proxy()      # 关闭代理
    reset_logger()       # 重置日志
    logger = get_logger()  # 获取日志实例

    print("🤖 多 Agent 职业风险测评系统 v3.3")
    print(f"   最大对话轮次：{MAX_ROUNDS}")

    graph = build_graph()            # 构建工作流图
    state = create_initial_state()   # 初始化状态

    # 第一轮系统开场
    opening_question = "你平时是做什么方向的工作呀？"
    print(f"系统：{opening_question}")
    state["last_followup_question"] = opening_question
    state["dialogue_history"].append({"role": "assistant", "content": opening_question})

    # ------------------ 主循环 ------------------
    for round_num in range(1, MAX_ROUNDS + 1):
        state["round_id"] = round_num
        state["specialist_results"] = []
        state["called_specialists"] = []

        user_input = input("\n用户：").strip()
        if user_input.lower() == "quit":
            print("退出系统。")
            break
        if user_input.lower() == "skip" or not user_input:
            print("（跳过本轮）")
            continue

        # 更新状态
        state["current_user_text"] = user_input
        state["dialogue_history"].append({"role": "user", "content": user_input})

        # ------------------ 调用工作流 ------------------
        logger.start_round(round_num, user_input)
        try:
            print("⏳ 系统思考中...")
            t_start = time.time()
            result = graph.invoke(state)  # 执行整个 v3 workflow
            t_end = time.time()
            elapsed = t_end - t_start

            state.update(result)  # 更新状态
            logger.end_round()     # 结束日志
            print_round_summary(state, elapsed)
            print_detailed_node_log(logger, round_num)

            # 保存追问到历史
            followup = state.get("last_followup_question", "")
            if followup and state.get("next_action") != "final_report":
                state["dialogue_history"].append({"role": "assistant", "content": followup})

            # 最终报告
            if state.get("next_action") == "final_report":
                print_final_report(state)
                break

        except Exception as e:
            logger.end_round()
            print(f"\n❌ 运行出错：{e}")
            import traceback
            traceback.print_exc()
            continue

    # ------------------ 自动生成最终报告（如果达到 MAX_ROUNDS） ------------------
    else:
        print("\n🔄 已达到最大轮次，正在生成最终报告...")
        state["round_id"] = MAX_ROUNDS
        state["specialist_results"] = []
        state["called_specialists"] = []
        state["next_action"] = "final_report"

        logger.start_round(MAX_ROUNDS + 1, "（自动生成最终报告）")
        try:
            t_start = time.time()
            result = graph.invoke(state)
            t_end = time.time()
            elapsed = t_end - t_start
            state.update(result)
            logger.end_round()
            print(f"⏱️  报告生成耗时：{elapsed:.2f} 秒")
            print_final_report(state)
        except Exception as e:
            logger.end_round()
            print(f"\n❌ 生成报告出错：{e}")
            import traceback
            traceback.print_exc()

    # 保存会话日志
    try:
        log_path = logger.finalize_session(state)
        print(f"\n📝 详细日志已保存至：{log_path}")
        md_path = log_path[:-5] + ".md" if log_path.endswith(".json") else log_path + ".md"
        print(f"📄 可读报告已保存至：{md_path}")
    except Exception as e:
        print(f"\n⚠️  日志保存失败：{e}")

    print("\n👋 感谢使用！")

# ------------------ 脚本直接运行 ------------------
if __name__ == "__main__":
    run_cli()

