# 多 Agent 职业身份风险识别助手 v3.0

面向相亲交友场景，使用多智能体协作分析对方关于职业、身份、经历和工作状态的回答，评估职业身份可信度并生成可追溯的结构化报告。

## 项目简介

本项目是一个基于 **LangGraph + Streamlit + DeepSeek** 的多 Agent 对话分析系统。系统通过多轮自然对话收集对方关于职业、公司、岗位、工作经历、时间线和日常工作细节等回答，维护事实表与异常表，按需调用语义、逻辑、领域常识和心理语言学四个维度的专家 Agent 进行并行分析，最终通过概率叠加公式计算 **LieIndex（谎言指数）** 并生成评估报告。

系统设计遵循 **按需深度分析** 原则：低风险回答跳过专家节点以节省 LLM 调用成本，高风险回答触发全部四个专家并行分析以确保全面评估。

## 功能

- **双入口**：Streamlit Web UI（含 Agent 思考监控面板）和 CLI 命令行模式
- **快速预分析**：单次 LLM 调用完成事实抽取、异常检测和表层风险标签生成
- **按需专家路由**：四档风险分级（<30 / 30-50 / 50-70 / ≥70），自动决定调用哪些专家
- **四维并行分析**：
  - 语义一致性分析 — 职业/岗位/工作内容表述前后是否一致
  - 逻辑时间线分析 — 时间、因果、职业路径是否自洽
  - 职业常识分析 — 职业内容描述是否符合行业基本常识
  - 心理语言学分析 — 识别回避、过度解释等软信号
- **风险聚合**：基于独立事件叠加公式 `LieIndex = 100 × (1 - ∏(1 - V_i/100))` 计算综合风险指数
- **策略监督**：LLM-as-Judge 判断继续追问或终止对话（最少 5 轮才能结束）
- **9 种追问策略**：包含低风险扩展、泛泛回答澄清、广泛探索和经验链（6 角度轮转）四类策略
- **事-异双表记忆**：事实表（全局累计）和异常表（带状态生命周期：unresolved → clarified/resolved/reinforced）
- **最终报告**：输出 LieIndex、维度分数、证据摘要和未解决疑点
- **Agent 思考监控**：每轮展示各节点分析摘要，清晰可追溯
- **基准评测**：准确率 / 虚假召回率 / 误报率 / 风险分差四项指标
- **会话存档**：JSON 报告 + 详细节点级执行日志
- **Supabase 同步**（可选）：输出自动上传云端存储

## 安装与运行

### 1. 克隆仓库

```bash
git clone https://github.com/chengqian212/project.git
cd project/v3
```

### 2. 创建虚拟环境

```bash
conda create -n lieindex python=3.13
conda activate lieindex
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置 API Key

在项目根目录创建 `.env` 文件：

```env
DEEPSEEK_API_KEY=你的DeepSeek_API_Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-chat
MAX_ROUNDS=8
MIN_FOLLOWUP_ROUNDS=5
TEMPERATURE=0.2
```

系统默认使用 **DeepSeek 官方 OpenAI 兼容 API**。也可配置为任意兼容 OpenAI API 格式的端点（如阿里云百炼 DashScope），修改 `DEEPSEEK_BASE_URL` 和 `MODEL_NAME` 即可。

如需 Supabase 云端存档，额外添加：
```env
SUPABASE_URL=你的Supabase实例URL
SUPABASE_SERVICE_ROLE_KEY=你的Service_Role_Key
```

### 5. 启动

```bash
# Web 界面
streamlit run app.py

# 命令行模式
python run_cli.py
```

## 目录结构

```
v3/
├── app.py                              # Streamlit Web UI 入口
├── run_cli.py                          # CLI 命令行入口
├── graph.py                            # LangGraph 图定义与路由
├── state_schema.py                     # DialogueState 全局状态结构
├── config.py                           # 配置管理（.env / Streamlit Secrets）
├── llm_client.py                       # LLM 客户端工厂
├── prompts.py                          # 所有节点 Prompt 模板集合
├── build_su.py                         # Streamlit Cloud 构建辅助
│
├── nodes/                              # 工作流节点
│   ├── quick_preanalysis_node.py       # 快速预分析
│   ├── lightweight_routing_supervisor_node.py  # 路由监督器
│   ├── risk_aggregator_node.py         # 风险聚合（LieIndex）
│   ├── strategy_supervisor_node.py     # 策略监督器
│   ├── followup_generation_node.py     # 追问生成
│   ├── report_generation_node.py       # 最终报告
│   ├── state_update_node.py            # 状态更新
│   └── specialists/                    # 四维专家
│       ├── semantic_agent_node.py      #   语义一致性
│       ├── logical_agent_node.py       #   逻辑时间线
│       ├── domain_agent_node.py        #   职业常识
│       └── psycho_linguistic_agent_node.py  # 心理语言学
│
├── memory/                             # 记忆系统
│   ├── fact_table.py                   # 事实表
│   └── anomaly_table.py               # 异常表（多来源合并+状态生命周期）
│
├── utils/                              # 工具库
│   ├── score_utils.py                  # 风险评分与 LieIndex 计算
│   ├── strategy_utils.py               # 追问策略注册表
│   ├── text_utils.py                   # 文本格式化
│   ├── json_utils.py                   # LLM 输出 JSON 安全解析
│   ├── node_wrapper.py                 # 节点包装器（日志+耗时监控）
│   ├── logger.py                       # 详细日志记录器
│   └── supabase_outputs.py             # Supabase 同步
│
├── benchmark/                          # 基准评测
│   ├── run_benchmark.py                # 评测主脚本
│   ├── benchmark_annotation_template.csv  # 标注数据集
│   ├── sync_from_supabase.py           # 云端数据同步
│   └── baseline/                       # 基础 Prompt 对比
│       └── run_baseline.py
│
├── outputs/                            # 输出
│   ├── reports/                        # 会话报告 JSON
│   └── logs/                           # 节点执行日志
│
├── scripts/                            # 运维脚本
│   └── upload_outputs_to_supabase.py
│
├── docs/                               # 文档
│   ├── 功能说明.md
│   ├── 软件设计结构说明.md
│   └── ONBOARDING.md
│
├── supabase_schema.sql                 # Supabase 表结构
└── requirements.txt                    # Python 依赖
```

## 技术栈

| 组件 | 用途 |
|------|------|
| Python 3.13 | 主语言 |
| LangGraph | 多节点 Agent 工作流编排（条件路由 + Fan-out 并行） |
| LangChain OpenAI | DeepSeek 及其他 OpenAI 兼容 API 调用 |
| Streamlit | Web 交互界面 |
| DeepSeek V3 (`deepseek-chat`) | 核心推理模型 |
| python-dotenv | 环境变量管理 |
| Pydantic | API Key 安全传递 |
| Supabase（可选） | 云端输出归档 |

## 配置参考

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DEEPSEEK_API_KEY` | - | DeepSeek API 密钥 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 端点 |
| `MODEL_NAME` | `deepseek-chat` | 模型名称 |
| `MAX_ROUNDS` | `8` | 最大对话轮次 |
| `MIN_FOLLOWUP_ROUNDS` | `5` | 最少追问轮次 |
| `TEMPERATURE` | `0.2` | LLM 温度参数 |
| `SUPABASE_URL` | - | Supabase 实例 URL（可选） |
| `SUPABASE_SERVICE_ROLE_KEY` | - | Supabase Service Role Key（可选） |

## 核心架构

```
用户输入 → 快速预分析 → 路由监督 → [4专家并行分析] → 风险聚合(LieIndex) → 策略监督 → 追问/报告
```

详见 `docs/软件设计结构说明.md` 和 `docs/功能说明.md`。

## 作者 / 联系方式

- 作者：cq
- GitHub：https://github.com/chengqian212
- 邮箱：9568712707@163.com

## License

MIT License
