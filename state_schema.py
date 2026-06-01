"""状态定义模块：定义 LangGraph State 的 TypedDict"""

from typing import TypedDict, List, Dict, Optional, Annotated
import operator


class DialogueState(TypedDict):
    """
    多 Agent 谎言指数测评系统的全局状态
    
    说明：
    - 使用 TypedDict 定义状态结构，字段在 LangGraph 的各个节点间传递
    - 使用 Annotated[operator.add] 的字段会被自动合并（如 specialist_results、called_specialists）
    - 版本演进：v1 -> v2 -> v3，逐步增加智能路由和并行分析能力
    """

    # ==================== 基础对话状态 ====================
    round_id: int                      # 当前对话轮次编号，从 0 或 1 开始
    max_rounds: int                    # 最大对话轮次数限制
    current_user_text: str             # 用户当前输入的原始文本
    dialogue_history: List[Dict]       # 完整对话历史记录，包含用户和AI的交互

    # ==================== 第一版已有字段 ====================
    current_facts: List[Dict]          # 当前提取到的事实信息列表
    facts_table: List[Dict]            # 全局事实表，存储所有已验证事实
    current_anomalies: List[Dict]      # 当前检测到的不一致/矛盾点
    indicator_history: List[Dict]      # 历史指标检测结果，用于趋势分析
    anomalies_table: List[Dict]        # 全局异常表，记录所有检测到的问题
    last_followup_question: str        # 最近生成的追问问题
    followup_history: List[Dict]       # 追问历史记录

    # ==================== 第二版新增字段 ====================
    specialist_results: Annotated[List[Dict], operator.add]  # 专家分析结果，使用 add reducer 自动合并并行结果
    dimension_scores: Dict[str, float]  # 各维度评分（如逻辑性、情感度等）
    # ==================== 谎言指数相关 ====================
    lie_index: float                    # 谎言指数（0-100，越高越可疑）
    risk_explanation: List[str]         # 风险解释说明列表

    # ==================== 路由控制 ====================
    next_action: str                    # 下一步动作标识，用于图路由
    final_report: Optional[Dict]        # 最终评估报告

    # ==================== v3 新增：轻量预分析结果 ====================
    quick_fact_summary: str             # 快速事实摘要，用于初步理解
    quick_signal_summary: str           # 快速信号摘要，标识异常信号
    surface_risk_score: float           # 表面风险评分，快速评估风险程度
    severity: str                       # 快速预分析严重度：CRITICAL/HIGH/MEDIUM/LOW
    confidence: str                     # 快速预分析置信度：HIGH/LOW
    schema_error: str                   # 节点输出结构错误标记
    schema_errors: List[str]            # 节点输出结构错误明细
    quick_preanalysis_retry_count: int  # quick_preanalysis schema 重试次数
    has_new_fact: bool                  # 是否检测到新事实

    # ==================== v3 新增：路由决策 ====================
    routing_decision: Dict              # 路由决策详情，包含决策依据
    selected_specialists: List[str]     # 选择调用的专家列表
    priority_issue: str                 # 优先关注的问题描述
    followup_strategy: str              # 追问策略（如深入/澄清/验证）

    # ==================== v3.3 新增：策略监督相关字段 ====================
    stop_reason: str                    # strategy_supervisor 决定继续或结束的原因
    target_anomaly_id: str              # 本轮追问针对的具体异常ID，用于更新 followup_count

    # ==================== v3 新增：记录实际调用的专家 ====================
    called_specialists: Annotated[List[str], operator.add]  # 已调用专家记录，使用 add reducer 自动累加

