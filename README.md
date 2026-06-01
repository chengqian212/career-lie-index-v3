# 多 Agent 相亲职业身份风险识别助手 v3.0

面向相亲交友场景，使用多智能体分析对方关于职业、身份、履历和工作状态的回答，评估职业身份风险并生成可追溯报告。

## 项目简介

本项目是一个基于 Streamlit、LangGraph 和大语言模型的多 Agent 对话分析系统，重点服务于相亲交友场景下的职业身份风险识别。系统通过多轮自然对话收集对方关于职业、公司、岗位、收入区间、工作经历、时间线和日常工作细节等回答，维护事实表与异常表，按需调用不同专家 Agent 进行语义、逻辑、职业常识和心理语言学分析，最后生成职业身份风险指数与最终报告。

项目适合用于相亲聊天中的职业身份一致性判断、疑点追问辅助、多 Agent 工作流实验，以及 LangGraph 流式节点监控示例。当前版本支持主对话界面与独立的 Agent 思考监控 Tab，方便观察每轮节点执行过程。

## 功能

- 实时相亲交友对话模拟，用户可以逐轮输入对方回答。
- 多 Agent 协作分析：
  - 职业身份语义一致性分析
  - 工作经历与时间线逻辑验证
  - 岗位、行业、公司和工作内容常识检测
  - 回答风格与回避信号的心理语言学分析
- 快速预分析：提取职业身份事实、识别异常、生成表层风险信号。
- 按需路由专家：低风险时可跳过专家，高风险时并行调用相关专家。
- 风险聚合：根据异常表和专家结果计算职业身份综合风险指数。
- 自动生成追问：围绕当前职业身份疑点和追问策略生成下一轮问题。
- 自动生成最终报告：输出职业身份风险指数、维度分数、风险解释和总结建议。
- Agent 思考监控 Tab：只展示每轮 Agent 思考摘要，不混入对话文本或最终报告。
- 会话记录保存：支持保存报告 JSON、详细日志 JSON 和 Markdown 日志。

## 安装与运行

1. 克隆仓库：

   ```bash
   git clone https://github.com/chengqian212/project.git
   cd project/v3
   ```

2. 创建虚拟环境：

   ```bash
   conda create -n lieindex python=3.13
   conda activate lieindex
   ```

3. 安装核心依赖：

   ```bash
   pip install streamlit langgraph langchain-openai python-dotenv pydantic
   ```

4. 配置 API Key：

   在 `v3` 目录下创建或修改 `.env` 文件：

   ```env
   BAILIAN_API_KEY=你的百炼APIKey
   BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
   MODEL_NAME=deepseek-v3
   MAX_ROUNDS=8
   TEMPERATURE=0.2
   ```

5. 启动 Streamlit 前端：

   ```bash
   streamlit run app.py
   ```

6. 或启动命令行版本：

   ```bash
   python run_cli.py
   ```

注意：当前代码以 `v3` 目录作为项目根目录运行。请先进入 `v3`，再运行 `streamlit run app.py` 或 `python run_cli.py`。

## 目录结构

- `app.py`：Streamlit 前端入口，包含相亲交友对话页面和 Agent 思考监控 Tab。
- `run_cli.py`：命令行入口，用于终端交互式运行。
- `graph.py`：LangGraph 工作流编排，负责节点注册、条件路由和专家 fan-out。
- `state_schema.py`：全局 `DialogueState` 状态结构定义。
- `config.py`：模型、API、轮次、风险阈值和路由参数配置。
- `llm_client.py`：统一创建 `ChatOpenAI` 客户端。
- `prompts.py`：各节点使用的 Prompt 模板。
- `nodes/`：各个 Agent 节点和监督节点实现。
- `nodes/specialists/`：语义、逻辑、领域、心理语言学专家节点。
- `memory/`：事实表和异常表相关工具。
- `utils/`：JSON 解析、文本格式化、评分、追问策略、日志和节点包装工具。
- `outputs/reports/`：保存 Streamlit 会话记录和职业身份风险报告。
- `outputs/logs/`：保存详细节点执行日志。
- `CODE_GUIDE_v3.md`：代码结构和节点逻辑说明文档。
- `AGENT_FLOWCHART.md`：当前 LangGraph 流程图说明。

## 技术栈 / 依赖

- Python 3.13
- Streamlit：Web UI 与流式展示
- LangGraph：多节点 Agent 工作流编排
- LangChain OpenAI：OpenAI-compatible 模型调用
- 阿里云百炼 DashScope OpenAI-compatible API
- python-dotenv：读取 `.env` 环境变量
- Pydantic：安全保存 API Key 等配置对象

核心模型配置默认值：

```python
MODEL_NAME = "deepseek-v3"
MAX_ROUNDS = 8
TEMPERATURE = 0.2
```

## 作者 / 联系方式

- 作者：cq
- GitHub：https://github.com/chengqian212
- 邮箱：19568712707@163.com

## License

MIT License
