# CODE_GUIDE_v3


## 1. 当前架构

`v3` 是一个多轮职业经历/职业身份风险分析 Agent。它以 `v3` 目录本身作为运行根目录，通过自然对话收集信息，维护事实表和异常表，按需调用专家 Agent，最后输出风险指数与报告。

当前架构可以分成五层：

- 入口层：`run_cli.py` 提供命令行交互，`app.py` 提供 Streamlit Web UI。
- 图编排层：`graph.py` 使用 LangGraph 注册节点、条件边和并行专家 fan-out。
- 节点层：`nodes/` 下的 quick preanalysis、routing supervisor、specialists、risk aggregator、strategy supervisor、followup/report generation。
- 记忆层：`memory/` 下的事实表和异常表工具；当前风险判断主要依赖 `anomalies_table`。
- 工具层：`utils/` 下的 JSON 解析、文本格式化、风险分计算、追问策略、节点日志包装等。

当前主流程：

```text
START
  -> quick_preanalysis
  -> lightweight_routing_supervisor
  -> 如果 quick_preanalysis 缺少 severity/confidence 且仍可重试：回跳 quick_preanalysis
  -> 如果 selected_specialists 为空：risk_aggregator
  -> 如果 selected_specialists 非空：并行调用被选中的专家
  -> risk_aggregator
  -> strategy_supervisor
  -> followup_generation 或 report_generation
  -> END
```

注意：这里的 `lightweight_routing_supervisor` 只是“轻量路由监督”，不是旧版已经删除的 `lightweight_risk_aggregator_node.py`。

## 2. 入口文件

### `run_cli.py`

命令行入口。负责：

- 初始化 `DialogueState`。
- 构建 `build_graph()`。
- 先写入系统开场问题：“你平时是做什么方向的工作呀？”
- 在 `for round_num in range(1, MAX_ROUNDS + 1)` 中逐轮读取用户输入并调用 `graph.invoke(state)`。
- 每轮开始前清空 `specialist_results` 和 `called_specialists`，避免并行 reducer 字段把上一轮专家结果带入本轮。
- 打印每轮风险摘要、专家调用、追问和最终报告。
- 使用 `DetailedLogger` 保存 `outputs/logs/session_*.json` 和 `outputs/logs/session_*.md`。
- 如果普通循环跑满 `MAX_ROUNDS` 还没有 `final_report`，会把 `round_id` 设为上限轮次、`next_action` 预置为 `final_report` 后再调用一次图；实际是否进入 `report_generation` 仍取决于本次图执行中 `strategy_supervisor_node.py` 输出的 `next_action`。

运行：

```bash
python run_cli.py
```

### `app.py`

Streamlit 入口。负责：

- 聊天式 Web UI。
- 使用 `graph.stream(..., stream_mode="updates")` 逐节点接收 LangGraph 更新。
- 主对话 Tab 只展示对话和最终报告。
- `Agent 思考监控` Tab 只读展示 `round_records[*]["agent_thoughts"]` 和当前轮 `live_agent_thoughts`，不参与对话输入/输出流程。
- 保存完整会话到 `v3/outputs/reports/session_*.json`。
- 最终报告生成后也调用 `DetailedLogger.finalize_session()`，保存 `outputs/logs/session_*.json/.md`。
- 当 `st.session_state.round_num >= MAX_ROUNDS` 时，自动调用 `_generate_final_report()`；该函数同样会重新 stream 一次图，最终路由仍由 `strategy_supervisor_node.py` 的输出决定。

运行：

```bash
streamlit run app.py
```

两个入口都应在 `v3` 目录内启动，不再使用 `python -m v3.run_cli` 或 `streamlit run v3/app.py` 这种从大目录启动的方式。

## 3. 配置与模型

### `config.py`

核心配置：

- `BAILIAN_API_KEY`：百炼 OpenAI-compatible API key，会 `.strip()` 去掉首尾空白。
- `DASHSCOPE_API_KEY`、`LLM_API_KEY`：兼容旧变量名，当前都指向 `BAILIAN_API_KEY`。
- `BAILIAN_BASE_URL`：默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`。
- `MODEL_NAME`：默认 `deepseek-v3`。
- `MAX_ROUNDS`：默认 8，控制 CLI/App 本地最多交互轮次。
- `TEMPERATURE`：默认 0.2。
- 风险等级阈值：`RISK_LOW_THRESHOLD=30`、`RISK_HIGH_THRESHOLD=60`。
- 风险权重：`WEIGHT_SEMANTIC`、`WEIGHT_LOGICAL`、`WEIGHT_DOMAIN`、`WEIGHT_PSYCHO_LINGUISTIC`、`WEIGHT_UNRESOLVED_FOLLOWUP`。
- 未解决追问计分常量：`UNRESOLVED_FOLLOWUP_PER_SCORE=20`。当前风险聚合主要看异常表中的 `risk_value`，不要把它理解成独立的旧版 unresolved 维度。
- 路由配置：`ENABLE_ON_DEMAND_SPECIALISTS`、`LOW_RISK_SKIP_THRESHOLD`、`MEDIUM_RISK_THRESHOLD`、`HIGH_RISK_THRESHOLD`。

当前默认：

```python
MAX_ROUNDS = int(os.getenv("MAX_ROUNDS", "8"))
```

`config.py` 导入时会先加载 `v3/.env`，然后调用 `disable_proxy()` 清理 `http_proxy/https_proxy/all_proxy` 等环境变量，并设置 `NO_PROXY="*"`，避免 OpenAI/httpx 底层误读本机代理。

### `llm_client.py`

统一创建 `ChatOpenAI` 客户端。每次创建前会调用 `config.disable_proxy()`，然后使用：

- `api_key=SecretStr(config.BAILIAN_API_KEY)`
- `base_url=config.BAILIAN_BASE_URL`
- `model=model or config.MODEL_NAME`
- `temperature=temperature if temperature is not None else config.TEMPERATURE`
- `max_retries=2`

如果 `BAILIAN_API_KEY` 为空，会直接抛出 `ValueError`。当前版本不再打印 API key 前缀、base URL、model 等调试信息。

## 4. 全局状态

`state_schema.py` 定义 `DialogueState`。LangGraph 会把同一个全局状态传给每个节点，但每个节点只读取自己代码里 `state.get(...)` 的字段，LLM 也只看到该节点 prompt 中传入的内容。

基础对话字段：

- `round_id`：当前轮次。
- `max_rounds`：最大轮次。入口初始化时来自 `config.MAX_ROUNDS`，默认 8。
- `current_user_text`：当前用户输入。
- `dialogue_history`：完整对话历史，包含 assistant 开场、用户回答、系统追问。

事实与异常字段：

- `current_facts`：当前轮 quick preanalysis 提取的新事实。
- `facts_table`：累计事实表。
- `current_anomalies`：当前轮发现的新异常。
- `anomalies_table`：累计异常表，是后续风险聚合和追问选择的核心输入。
- `indicator_history`：旧版趋势/指标字段，当前仍保留在状态中，但不是主流程核心。
- `has_new_fact`：quick preanalysis 是否识别到新事实。

快速预分析字段：

- `quick_fact_summary`：本轮事实摘要。
- `quick_signal_summary`：本轮信号/异常摘要。
- `surface_risk_score`：路由前的表层风险分。
- `severity`：quick preanalysis 输出的严重程度标签，例如 `CRITICAL/HIGH/MEDIUM/LOW`。
- `confidence`：quick preanalysis 输出的置信度标签，例如 `HIGH/LOW`。
- `schema_error`：节点输出结构错误标记。
- `schema_errors`：结构错误明细列表。
- `quick_preanalysis_retry_count`：当 severity/confidence 缺失时，路由节点回跳 quick preanalysis 的计数。

专家与风险字段：

- `specialist_results`：专家结果，使用 `Annotated[List[Dict], operator.add]` 合并并行结果。
- `called_specialists`：实际调用的专家，使用 `Annotated[List[str], operator.add]` 合并并行结果。
- `dimension_scores`：维度分数，当前主要由异常表 active risk events 聚合得到。
- `lie_index`：综合风险指数。
- `risk_explanation`：风险解释文本列表。

路由与策略字段：

- `routing_decision`：路由决策详情，可能包含 `router_mode`、`routing_reason`、`selected_specialists` 等。
- `selected_specialists`：本轮要调用的专家列表。为空表示跳过专家并直接进入 `risk_aggregator`。
- `next_action`：策略节点输出的下一步动作。`final_report` 进入报告生成，其他值进入追问生成。
- `priority_issue`：追问优先问题。
- `followup_strategy`：追问策略，必须归一化到 `utils/strategy_utils.py` 中的允许集合。
- `stop_reason`：策略节点给出的继续/停止原因。
- `target_anomaly_id`：本轮追问针对的异常 ID，主要供 `followup_generation_node.py` 更新异常追问次数。

追问与报告字段：

- `last_followup_question`：最近一次追问。
- `followup_history`：追问历史。
- `final_report`：最终报告。

Streamlit 额外会话态：

- `round_records`：每轮 UI 记录，包含用户输入、追问、节点耗时、路由、风险、`agent_thoughts` 等。
- `live_agent_thoughts`：当前正在 stream 的节点思考摘要，供监控 Tab 实时读取。
- `live_agent_round`：当前实时监控对应的轮次。

`round_records` 和 `live_agent_thoughts` 属于 `st.session_state`，不是 `DialogueState` 的 LangGraph 字段。

## 5. 图编排

### `graph.py`

注册节点：

- `quick_preanalysis`
- `lightweight_routing_supervisor`
- `semantic_agent`
- `logical_agent`
- `domain_agent`
- `psycho_linguistic_agent`
- `risk_aggregator`
- `strategy_supervisor`
- `followup_generation`
- `report_generation`

路由逻辑：

- `route_after_routing_supervisor()` 先看 `routing_decision["router_mode"]`：
  - `retry_quick_preanalysis`：回跳 `quick_preanalysis`，用于 quick preanalysis 缺失 `severity/confidence` 时重跑一次。
- 如果没有重试分支，再看 `selected_specialists`：
  - 空列表：直接 `risk_aggregator`
  - 非空：并行 fan-out 到对应专家节点
- 所有专家节点完成后直接进入 `risk_aggregator`。
- `route_after_strategy_supervisor()` 只看 `next_action`：
  - `final_report` -> `report_generation`
  - 其他 -> `followup_generation`

所有节点注册前都会经过 `wrap_node()`，用于日志记录。

专家 fan-out 映射：

- `semantic` -> `semantic_agent`
- `logical` -> `logical_agent`
- `domain` -> `domain_agent`
- `psycho_linguistic` -> `psycho_linguistic_agent`

终止边：

- `followup_generation` -> `END`
- `report_generation` -> `END`

这意味着一次 `graph.invoke()` 或一轮 `graph.stream()` 只会跑到“生成追问”或“生成报告”为止；多轮循环由 `run_cli.py` / `app.py` 负责，而不是 LangGraph 自己在图内无限循环。

## 6. 节点说明

### `quick_preanalysis_node.py`

一次 LLM 调用完成：

- 事实提取。
- 当前轮异常检测。
- 旧异常状态更新。
- 表层风险分 `surface_risk_score`。
- 快速事实摘要与信号摘要。

输出重点：

- `current_facts`
- `facts_table`
- `has_new_fact`
- `current_anomalies`
- `anomalies_table`
- `surface_risk_score`
- `quick_fact_summary`
- `quick_signal_summary`

异常表处理顺序：

1. 先调用 `update_anomalies_status()` 更新旧异常。
2. 再调用 `add_anomalies()` 写入新异常。

### `lightweight_routing_supervisor_node.py`

负责“是否跳过专家”和“调用哪些专家”。

关键点：

- 是否跳过专家完全由 Python 规则决定。
- LLM 只在不能跳过专家时选择 `selected_specialists`、`priority_issue`、`followup_strategy`。
- 图路由只看 `selected_specialists` 是否为空。
- 输出的 `followup_strategy` 会通过 `normalize_followup_strategy()` 归一化。

跳过专家的典型条件：

- 当前轮没有新异常。
- 异常表中没有活跃未解决异常。
- `surface_risk_score < 40`。
- 低风险、无核心新事实、事实量较少等情况。

合法专家名：

- `semantic`
- `logical`
- `domain`
- `psycho_linguistic`

LLM 解析失败或选择为空时，会使用 `infer_default_specialists()` 兜底，通常选择 `semantic` + `logical`。

### Specialist 节点

位于 `v3/nodes/specialists/`。

共同输出：

```python
{
    "specialist_results": [result],
    "called_specialists": ["semantic"]
}
```

四个专家：

- `semantic_agent_node.py`：语义一致性，检查职业身份、岗位、工作内容前后是否一致。
- `logical_agent_node.py`：逻辑与时间线，检查时间、因果、经历路径是否自洽。
- `domain_agent_node.py`：职业常识，检查描述是否符合岗位/行业常识。
- `psycho_linguistic_agent_node.py`：心理语言线索，检查回避、模糊、过度解释等软性信号。

专家结果可能包含：

- `score`
- `evidence_list`
- `anomaly_updates`
- `new_anomalies`

后两个字段会由 `risk_aggregator` 写回异常表。

### `risk_aggregator_node.py`

统一风险聚合节点。

聚合前先处理专家对异常表的影响：

1. `apply_specialist_anomaly_updates()`
2. `add_specialist_results_as_anomalies()`
3. `count_unresolved()`

当前聚合逻辑：

- 不再区分“有专家/无专家”的两套计算公式。
- 先把专家对旧异常的更新和新异常写入 `anomalies_table`；如果本轮没有专家结果，这两步不会新增专家异常。
- 从 `anomalies_table` 中提取仍活跃的风险事件。
- 单条风险值来自异常记录中的 `risk_value`，或由 `severity * confidence` 计算。
- 用 `combine_independent_risk_values()` 将风险事件聚合成 `lie_index`。
- `dimension_scores` 按事件来源分组，每个来源取最大的 `risk_value`。
- 没有单独的“未澄清异常数量加分”；未澄清/未解决的异常会因为仍处于 active 状态而继续参与风险聚合。

当前没有 Debate 调整。

### `strategy_supervisor_node.py`

负责决定继续追问还是生成报告。

当前实现是 LLM-as-a-Judge，不包含本地硬规则早停链路。

输入给 `STRATEGY_SUPERVISOR_PROMPT` 的上下文包括：

- `lie_index`
- `dimension_scores`
- `risk_explanation`
- `specialist_results` 的文本摘要
- `anomalies_table`
- `dialogue_history`
- `followup_history`
- `round_id`
- `max_rounds`
- `routing_decision`
- `called_specialists`

LLM 期望返回 JSON，核心字段包括：

- `decision`：`ASK_MORE` 或 `GENERATE_REPORT`
- `priority_issue`
- `followup_strategy`
- `target_anomaly_id`
- `reason_summary`

解析与兜底：

- JSON 解析失败时，默认当作 `ASK_MORE`。
- `decision` 非法时，也兜底为 `ASK_MORE`。
- `decision == "GENERATE_REPORT"` 时，返回 `next_action="final_report"`。
- 其他情况返回 `next_action="generate_followup"`。
- `stop_reason` 使用 `reason_summary`；如果为空，则使用小写后的 decision。

追问策略处理：

- `followup_strategy` 会通过 `utils.strategy_utils.normalize_followup_strategy()` 归一化。
- 当前调用时固定 `has_risk=False`，因此非法策略会兜底为 `daily_routine`。
- 如果决定生成报告，则返回空字符串 `followup_strategy=""`。

注意：`round_id` 和 `max_rounds` 只是传给 LLM 判断的上下文；当前代码没有在本地强制 `round_id >= max_rounds` 直接生成报告。

### `followup_generation_node.py`

负责生成下一句自然追问。

输入重点：

- `priority_issue`
- `followup_strategy`
- `dimension_scores`
- `anomalies_table`
- `dialogue_history`
- `target_anomaly_id`：不传给 prompt，只用于更新对应异常的追问次数。

行为：

- 优先使用 `strategy_supervisor` 给出的 `priority_issue`、`followup_strategy`、`target_anomaly_id`。
- 如果 `priority_issue` 为空或属于无效值，会按顺序推断：
  1. 活跃异常：使用最新活跃异常的 `description`，策略为 `light_clarification`，并带上该异常的 `anomaly_id`。
  2. `risk_explanation`：使用第一条风险解释，策略为 `light_clarification`。
  3. `current_facts`：围绕最新事实轻量了解，策略为 `daily_routine`。
  4. 以上都没有：使用“继续自然聊天”，策略为 `daily_routine`。
- 如果 `followup_strategy` 为空，先置为 `daily_routine`。
- 再根据 `_has_risk_signal()` 调用 `normalize_followup_strategy(followup_strategy, has_risk)`。
- `FOLLOWUP_GENERATION_PROMPT` 的模板变量为：
  - `priority_issue`
  - `followup_strategy`
  - `dimension_scores`
  - `anomalies_table`
  - `dialogue_history`
- 注意这里的 `anomalies_table` 和 `dialogue_history` 不是单个原始字段值，而是分别经过 `format_anomalies_table()`、`format_dialogue_history()` 格式化后的完整上下文文本。
- 节点还会读取 `risk_explanation`、`current_anomalies`、`current_facts`、`lie_index`、`target_anomaly_id` 等状态字段做本地推断、风险判断和追问计数更新；这些字段不会以独立模板变量的形式传入 prompt。
- LLM 输出经 `clean_llm_output()` 清洗；如果为空，兜底为“能再具体聊聊你的学习或项目经历吗？”。
- 生成后写入 `followup_history`，记录 `round_id`、`question`、`priority_issue`、`followup_strategy`。
- 如果有 `target_anomaly_id`，在 `anomalies_table` 中找到同 ID 异常并将 `followup_count += 1`。
- 当该异常的 `followup_count >= 2` 时，设置 `stop_followup=True`、`followup_needed=False`。
- 返回字段包括 `last_followup_question`、`followup_history`、`priority_issue`、`followup_strategy`、`next_action="generate_followup"`、`anomalies_table`。

追问策略不在本节点单独维护，统一来自 `utils/strategy_utils.py`：

- `daily_routine`
- `entry_experience`
- `work_style`
- `recent_memory`
- `light_clarification`
- `topic_shift_buffer`
- `experience_probe`
- `knowledge_probe`
- `tool_workflow_probe`
- `scenario_judgment_probe`

归一化规则：

- 如果上游策略在允许集合中，原样使用。
- 如果上游策略不合法且当前有风险，兜底为 `light_clarification`。
- 如果上游策略不合法且当前无明显风险，兜底为 `daily_routine`。

当前调用同一归一化逻辑的节点：

- `lightweight_routing_supervisor_node.py`
- `strategy_supervisor_node.py`
- `followup_generation_node.py`

### `report_generation_node.py`

负责最终报告。

读取状态：

- `lie_index`
- `dimension_scores`
- `specialist_results`
- `anomalies_table`

本地格式化：

- `dimension_scores` 会转成逐行文本：`- 维度名: 分数`。
- `specialist_results` 会转成逐个专家的分数和 `evidence_list` JSON 文本。
- `unresolved_anomalies` 不是状态里的原始字段，而是通过 `get_unresolved_anomalies(anomalies_table)` 取出 active/未解决异常后格式化为待澄清问题列表。
- 如果没有待澄清异常，`unresolved_anomalies` 文本为“暂无明显待澄清点”。

传给 `FINAL_REPORT_PROMPT` 的模板变量：

- `lie_index`
- `dimension_scores`：格式化后的维度分数文本。
- `specialist_results`：格式化后的专家发现文本。
- `unresolved_anomalies`：格式化后的待澄清问题文本。

输出：

```python
{
    "final_report": {
        "lie_index": lie_index,
        "dimension_scores": dimension_scores,
        "report_text": report_text,
    },
    "next_action": "final_report",
}
```

`report_text` 来自 LLM 输出并经过 `clean_llm_output()` 清洗。本节点只返回状态更新，不负责把报告写入文件；CLI 或 Streamlit 外层入口负责保存 session/report。

## 7. 记忆表

### `memory/fact_table.py`

事实表工具，保留兼容函数：

- `init_fact_table()`
- `add_facts()`
- `get_facts_by_round()`
- `get_facts_by_category()`
- `get_facts_summary()`

注意：

- 主流程里 `quick_preanalysis_node` 直接扩展 `facts_table`，不依赖 `add_facts()`。
- `add_facts()` 兼容旧字段 `category`、`raw_text`。
- 当前 `quick_preanalysis_node` 新事实主要使用 `slot`、`content`、`evidence`、`source`。
- 因此 `fact_table.py` 是兼容工具，实际主流程事实结构以 `quick_preanalysis_node` 写入为准。

### `memory/anomaly_table.py`

异常表是当前风险聚合、追问计数和报告待澄清点的核心表。

标准异常字段：

- `anomaly_id`
- `round_id`
- `source`
- `type`
- `description`
- `evidence`
- `score`
- `severity`
- `confidence`
- `risk_value`
- `schema_error`
- `status`
- `clarification_status`
- `followup_needed`
- `followup_count`
- `stop_followup`
- `related_facts`
- `created_round`
- `last_update_round`
- `update_history`

字段说明：

- `source` 表示异常来源，常见值包括 `quick_preanalysis`、`semantic`、`logical`、`domain`、`psycho_linguistic`。部分兼容常量里仍保留 `quick_detection`。
- `severity` 和 `confidence` 必须合法，才会计算 `risk_value`。
- `risk_value = effective_risk_value(severity, confidence)`，供 `risk_aggregator_node` 聚合使用。
- `schema_error="anomaly_risk_labels_invalid"` 表示该异常缺少合法风险标签，聚合时会被跳过或风险值为 0。
- `status` 常见值：`unresolved`、`reinforced`、`resolved`。
- `clarification_status` 常见值：`none`、`partial`、`insufficient`、`sufficient`。
- `followup_needed` 表示是否仍建议追问。
- `followup_count` 由 `followup_generation_node.py` 在追问目标异常后递增。
- `stop_followup=True` 后，该异常即使仍是 unresolved/reinforced，也不会再被视为 active anomaly。

关键函数：

- `init_anomaly_table()`
- `normalize_anomaly()`
- `add_anomalies()`
- `update_anomalies_status()`
- `get_active_anomalies()`
- `get_unresolved_anomalies()`
- `count_unresolved()`
- `apply_specialist_anomaly_updates()`
- `convert_legacy_items_to_anomalies()`
- `add_specialist_results_as_anomalies()`

新增异常写入：

- `add_anomalies()` 会对新异常调用 `normalize_anomaly()`。
- `normalize_anomaly()` 会补齐字段、规范 evidence 为列表、生成 `anomaly_id`。
- 如果 `severity/confidence` 合法，会写入 `risk_value`；否则写入 schema 错误。

旧异常更新：

- `update_anomalies_status()` 按 `target_anomaly_id` 更新旧异常。
- 一个异常如果收到多个更新，会先按 `update_type` 优先级裁决，再按来源优先级和分数裁决。

异常更新优先级：

```text
reinforce > remain_unresolved > clarify > resolve
```

来源优先级：

```text
semantic = logical > domain > psycho_linguistic > quick_detection
```

分数裁决：

- `resolve`：最高 20 分，停止追问。
- `clarify`：至少 30 分，继续关注。
- `reinforce`：不能低于旧分。
- `remain_unresolved`：不能低于旧分。

active anomaly：

- `get_active_anomalies()` 返回仍需关注的异常。
- 排除 `stop_followup=True` 的异常。
- 保留条件是 `status in ["unresolved", "reinforced"]` 或 `followup_needed is True`。
- `count_unresolved()` 和 `get_unresolved_anomalies()` 都基于 active anomaly。

专家结果写入异常表：

- `apply_specialist_anomaly_updates()` 从 `specialist_results[*].anomaly_updates` 提取旧异常更新。
- `add_specialist_results_as_anomalies()` 按 `semantic -> logical -> domain -> psycho_linguistic` 顺序写入专家新证据。
- 当前规范来源是 `evidence_list`，如果没有则尝试 `new_anomalies`。
- 专家新异常必须有合法 `severity/confidence`，否则会被丢弃并记录 warning。
- 同一轮、同一来源、同一 `type`、同一 `evidence` 的异常不会重复写入。

## 8. 工具模块

### `utils/json_utils.py`

用于解析 LLM 输出中的 JSON。

主要函数：

- `extract_json_from_text(text)`：依次尝试解析纯 JSON、Markdown ```json 代码块、文本中嵌入的 `{...}` 或 `[...]`。
- `safe_json_parse_with_retry(text, default, node_name)`：第一次解析失败后，会调用 `clean_llm_output(..., aggressive=True)` 再试一次；两次失败返回 `default` 并写日志。

注意：当前代码中没有 `safe_json_parse()` 函数，文档和调用不要再引用它。

### `utils/text_utils.py`

用于把状态转成 prompt 可读文本，以及清理 LLM 输出。

主要函数：

- `format_dialogue_history(history, max_rounds=None)`：将 `role/content` 对话历史转为中文标注文本。
- `format_facts_table(facts_table)`：将事实表转为文本；当前主要读取 `category` 与 `content`，而主流程新事实多使用 `slot`。
- `format_anomalies_table(anomalies_table)`：输出 `anomaly_id/source/type/score/status/clarification_status/followup_needed/description`。
- `extract_content_str(content)`：兼容 `str`、`list[str|dict]`、`None` 的 LLM content。
- `clean_llm_output(text, aggressive=False)`：去掉 `<think>`、Markdown JSON 标记和解释性噪音。

维护注意：如果事实结构统一到 `slot`，这里的 `format_facts_table()` 也要同步改。

### `utils/score_utils.py`

风险标签和分值工具。

主要常量：

- `SEVERITY_BASE_SCORE`：`CRITICAL=45`、`HIGH=25`、`MEDIUM=10`、`LOW=3`。
- `CONFIDENCE_WEIGHT`：`CRITICAL=1.0`、`HIGH=0.8`、`MEDIUM=0.5`、`LOW=0.2`。
- `QUICK_CONFIDENCES = {"HIGH", "LOW"}`：快速预分析只允许 HIGH/LOW 置信度。

主要函数：

- `normalize_severity()` / `normalize_confidence()`：标准化标签，非法时回落到默认值。
- `effective_risk_value(severity, confidence)`：计算单条风险值。
- `combine_independent_risk_values(values)`：用 `100 * (1 - product(1 - value/100))` 聚合多个风险事件。
- `normalize_quick_risk_labels(result)`：校验 quick preanalysis 的 `severity/confidence`。
- `normalize_evidence_item(item)`：校验专家证据项并写入 `risk_value`。
- `normalize_specialist_result(result, agent)`：规范专家输出，丢弃非法证据，`score` 取有效证据最大 `risk_value`。
- `determine_risk_level(lie_index)`：按配置阈值返回低/中/高。

### `utils/strategy_utils.py`

统一维护追问策略集合。

- `ALLOWED_FOLLOWUP_STRATEGIES`：当前合法策略集合。
- `normalize_followup_strategy(strategy, has_risk=False)`：合法则原样返回；非法且有风险返回 `light_clarification`；非法且无风险返回 `daily_routine`。

调用方：`lightweight_routing_supervisor_node.py`、`strategy_supervisor_node.py`、`followup_generation_node.py`。

### `utils/node_wrapper.py`

`wrap_node(node_func)` 给 LangGraph 节点增加日志包装。

记录内容：

- 节点函数名。
- 输入状态快照。
- 输出更新快照。
- 耗时。
- 错误信息。

如果节点抛异常，wrapper 会先记录失败日志，再重新抛出异常，不吞错。

### `utils/logger.py`

`DetailedLogger` 负责节点级执行日志。

关键行为：

- `start_round(round_id, user_input)`：开始记录一轮。
- `log_node(...)`：由 `wrap_node()` 调用，写入节点输入/输出快照和耗时。
- `end_round()`：把当前轮归档到 `session_data["rounds"]`。
- `finalize_session(final_state)`：写出 `outputs/logs/session_*.json`，并生成同名 `.md` 可读报告。
- `_snapshot_state()`：只保留关键字段，长表只保留数量和最近示例。

注意：logger 只负责 `outputs/logs/`；`outputs/reports/` 是 app/CLI 外层保存业务结果。

## 9. Prompt

Prompt 集中在 `prompts.py`，使用 `ChatPromptTemplate.from_messages([("system", TEMPLATE)])`。

当前主流程使用：

- `QUICK_PREANALYSIS_PROMPT`
- `LIGHTWEIGHT_ROUTING_SUPERVISOR_PROMPT`
- `SEMANTIC_AGENT_PROMPT`
- `LOGICAL_AGENT_PROMPT`
- `DOMAIN_AGENT_PROMPT`
- `PSYCHO_LINGUISTIC_AGENT_PROMPT`
- `STRATEGY_SUPERVISOR_PROMPT`
- `FOLLOWUP_GENERATION_PROMPT`
- `FINAL_REPORT_PROMPT`

Prompt 获取辅助：

- `PROMPT_MAP` 将节点名映射到 prompt。
- `get_prompt(prompt_name)` 返回对应 prompt，未知名称会抛 `ValueError`。

重要维护点：

- `STRATEGY_SUPERVISOR_TEMPLATE` 在文件中出现两次赋值，后面的英文 LLM-as-a-Judge 模板会覆盖前面的中文模板；实际生效的是后者。
- 修改 `followup_strategy` 合法集合时，需要同步 `utils/strategy_utils.py` 和 prompts 中的策略说明。
- Prompt 输入变量必须与对应节点 `.invoke({...})` 的字段一致。
- 专家 Prompt 要求输出 JSON；followup/report prompt 输出自然语言文本。

## 10. 输出目录

```text
outputs/
  logs/
    session_*.json
    session_*.md
  reports/
    session_*.json
    report_*.json
```

含义：

- `outputs/logs/`：`DetailedLogger.finalize_session()` 写出的节点级执行日志，包含每轮节点快照、耗时、错误和最终状态摘要。
- `outputs/reports/session_*.json`：Streamlit app 的 `_save_session_to_outputs()` 写出的完整业务会话记录，包含 `round_records`、对话历史、事实/异常表、最终报告等。
- `outputs/reports/report_*.json`：CLI 的 `save_report()` 写出的最终报告文件。
- 旧的 `outputs/reports/session_20260524_*.json` 是历史会话产物，不是代码依赖。

注意：运行 app 完整结束后应同时有 reports 和 logs；CLI 结束时会保存 logs，并在最终报告生成时保存 `report_*.json`。

## 11. 测试

当前仓库没有保留独立 pytest/单元测试文件，已删除旧的 patch 测试脚本。

当前可做的基础验证：

```bash
python -m compileall .
python -c "from graph import build_graph; build_graph(); print('graph ok')"
python -c "import run_cli; print('run_cli import ok')"
```

Streamlit 入口可用：

```bash
streamlit run app.py
```

说明：

- `python -m compileall .` 只验证语法和导入路径，不验证 LLM 调用质量。
- `build_graph()` 验证节点导入、wrapper 注册和 LangGraph 编译。
- 真正端到端运行需要 `.env` 中有 `BAILIAN_API_KEY`，且网络/API 可用。
- 不要再引用已删除的 `test_v3_modifications.py`、`test_v3_patch.py`、`test_followup_strategy_patch.py`。

## 12. 维护注意点

1. `v3` 目录就是项目根目录。启动时先进入 `v3`，再运行 `python run_cli.py` 或 `streamlit run app.py`；代码导入使用 `from graph import ...`、`from nodes...`、`from utils...`，不要再写 `from v3...` 或包相对导入。
2. 跳过专家只看 `selected_specialists` 是否为空；`need_specialist` 已移除。
3. `strategy_supervisor_node.py` 当前没有本地 `min_rounds` 或 `round_id >= max_rounds` 硬规则；`max_rounds` 只是传给 prompt，Streamlit/CLI 外层负责最大轮次控制。
4. 所有节点共享同一个 `DialogueState`，但 LLM 只能看到对应 prompt 中传入的字段或格式化文本。
5. `risk_aggregator_node.py` 不再有 lightweight 聚合分支，不再使用 `calculate_lightweight_risk_score()`、`lightweight_surface`、`unresolved_anomalies` 旧维度。
6. `anomalies_table` 是风险聚合、追问计数、报告待澄清点的核心表；修改异常字段时必须同步 `memory/anomaly_table.py`、`utils/text_utils.py`、`risk_aggregator_node.py`、报告/追问相关文档。
7. `followup_strategy` 合法值统一维护在 `utils/strategy_utils.py`；改策略时同步 prompts 和 Code Guide。
8. `fact_table.py` 仍保留旧兼容函数；主流程事实结构目前以 `quick_preanalysis_node.py` 写入的 `slot/content/evidence/source` 为准，`format_facts_table()` 仍偏旧字段 `category`，这是后续可统一的点。
9. `config.py` 与 `llm_client.py` 不应打印 API Key 或密钥片段；需要排查配置时只检查环境变量是否存在。
10. 修改 Mermaid 文档时要闭合 ```mermaid 代码块，否则渲染器会把后续 HTML 当 Mermaid 解析。
