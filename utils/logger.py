"""详细日志模块：记录每轮分析的所有节点执行结果

功能：
1. 记录每轮对话中每个节点的输入、输出、耗时和错误信息
2. 支持会话级别日志，生成 JSON 文件和 Markdown 可读报告
3. 可对对话历史、专家结果、事实表/异常表做精简快照
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from typing import get_type_hints


class DetailedLogger:
    """详细日志记录器
    
    记录每轮对话中每个节点的执行过程和结果，
    包括输入、输出、耗时、错误信息。
    """
    
    def __init__(self, log_dir: Optional[str] = None):
        """初始化日志记录器
        
        Args:
            log_dir: 日志存储目录，默认 v3/outputs/logs
        """
        if log_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_dir = os.path.join(base_dir, "outputs", "logs")
        
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        # 会话级数据
        self.session_data = {
            "session_start_time": datetime.now().isoformat(),
            "rounds": [],
        }
        
        # 当前轮次数据
        self.current_round: Optional[Dict] = None
        self.current_round_id: int = 0
    
    def start_round(self, round_id: int, user_input: str):
        """开始新轮次日志记录
        
        Args:
            round_id: 当前轮次编号
            user_input: 用户输入文本
        """
        self.current_round_id = round_id
        self.current_round = {
            "round_id": round_id,
            "start_time": datetime.now().isoformat(),
            "user_input": user_input,
            "nodes": [],
            "end_time": None,
            "total_elapsed_seconds": 0,
        }
    
    def log_node(
        self,
        node_name: str,
        input_state: Dict,
        output_updates: Dict,
        elapsed_seconds: float,
        error: Optional[str] = None,
    ):
        """记录单个节点执行信息
        
        Args:
            node_name: 节点名称
            input_state: 节点输入状态（精简关键字段）
            output_updates: 节点输出更新
            elapsed_seconds: 执行耗时（秒）
            error: 错误信息（如果有）
        """
        if self.current_round is None:
            return
        
        # 对输入输出做精简快照
        input_snapshot = self._snapshot_state(input_state)
        output_snapshot = self._snapshot_state(output_updates)
        
        node_log = {
            "node_name": node_name,
            "elapsed_seconds": round(elapsed_seconds, 3),
            "input": input_snapshot,
            "output": output_snapshot,
            "success": error is None,
        }
        
        if error:
            node_log["error"] = error
        
        self.current_round["nodes"].append(node_log)
    
    def end_round(self):
        """结束当前轮次日志记录"""
        if self.current_round is None:
            return
        
        self.current_round["end_time"] = datetime.now().isoformat()
        
        # 计算总耗时
        start = datetime.fromisoformat(self.current_round["start_time"])
        end = datetime.fromisoformat(self.current_round["end_time"])
        self.current_round["total_elapsed_seconds"] = round((end - start).total_seconds(), 3)
        
        # 添加到会话数据
        self.session_data["rounds"].append(self.current_round)
        self.current_round = None
    
    def finalize_session(self, final_state: Dict):
        """完成会话日志记录并保存文件
        
        Args:
            final_state: 会话结束后的最终状态
        Returns:
            log_filepath: JSON 日志文件路径
        """
        self.session_data["session_end_time"] = datetime.now().isoformat()
        self.session_data["final_state_snapshot"] = self._snapshot_state(final_state)
        
        # 保存 JSON 日志
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"session_{timestamp}.json"
        log_filepath = os.path.join(self.log_dir, log_filename)
        with open(log_filepath, "w", encoding="utf-8") as f:
            json.dump(self.session_data, f, ensure_ascii=False, indent=2)
        
        # 生成 Markdown 可读报告
        self._generate_markdown_report(log_filepath)
        
        return log_filepath
    
    def _snapshot_state(self, state: Dict) -> Dict:
        """生成状态快照，仅保留关键字段
        
        Args:
            state: 完整状态字典
        Returns:
            snapshot: 精简状态
        """
        tracked_fields = [
            # 基础字段
            "round_id", "max_rounds", "current_user_text", "last_followup_question", "next_action",
            # 核心结果字段
            "lie_index", "risk_explanation", "dimension_scores",
            # 路由与策略
            "routing_decision", "selected_specialists", "called_specialists", "priority_issue",
            "followup_strategy", "stop_reason", "target_anomaly_id",
            # 摘要与快速分析
            "quick_fact_summary", "quick_signal_summary", "surface_risk_score", "severity",
            "confidence", "schema_error", "schema_errors", "has_new_fact",
            # 对话历史
            "dialogue_history",
            # 专家结果
            "specialist_results",
            # 表数据
            "facts_table", "anomalies_table", "anomalies",
        ]
        
        snapshot = {}
        for field in tracked_fields:
            if field not in state:
                continue
            value = state[field]
            
            # 对话历史，只保留最近 5 条
            if field == "dialogue_history" and isinstance(value, list):
                snapshot[field] = value[-5:] if len(value) > 5 else value
                snapshot[f"{field}_count"] = len(value)
                continue
            
            # 专家结果，保留列表和数量
            if field == "specialist_results" and isinstance(value, list):
                snapshot[field] = value
                snapshot[f"{field}_count"] = len(value)
                continue
            
            # 表数据，只保留数量和最近几条示例
            if field in ("facts_table", "anomalies_table", "anomalies") and isinstance(value, list):
                snapshot[f"{field}_count"] = len(value)
                snapshot[f"{field}_recent"] = value[-3:] if len(value) > 3 else value
                continue
            
            # 普通字段直接记录
            snapshot[field] = value
        
        return snapshot
    
    def _generate_markdown_report(self, json_log_path: str):
        """生成 Markdown 可读报告
        
        Args:
            json_log_path: JSON 日志文件路径
        """
        md_path = json_log_path[:-5] + ".md" if json_log_path.endswith(".json") else json_log_path + ".md"
        lines = []
        lines.append("# 📊 会话详细日志报告")
        lines.append("")
        lines.append(f"**会话开始时间**: {self.session_data['session_start_time']}")
        lines.append(f"**会话结束时间**: {self.session_data.get('session_end_time', '进行中')}")
        lines.append(f"**总轮次数**: {len(self.session_data['rounds'])}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        for round_data in self.session_data["rounds"]:
            lines.append(f"## 🔄 轮次 {round_data['round_id']}")
            lines.append("")
            lines.append(f"**用户输入**: `{round_data['user_input']}`")
            lines.append(f"**开始时间**: {round_data['start_time']}")
            lines.append(f"**结束时间**: {round_data['end_time']}")
            lines.append(f"**总耗时**: {round_data['total_elapsed_seconds']} 秒")
            lines.append("")
            
            for node in round_data["nodes"]:
                lines.append(f"### 🔹 节点: {node['node_name']}")
                lines.append(f"- **耗时**: {node['elapsed_seconds']} 秒")
                lines.append(f"- **状态**: {'✅ 成功' if node['success'] else '❌ 失败'}")
                if node.get("error"):
                    lines.append(f"- **错误**: {node['error']}")
                if node["output"]:
                    lines.append("**关键输出**:")
                    lines.append("```")
                    lines.append(self._format_output(node["output"]))
                    lines.append("```")
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        # 最终状态摘要
        if "final_state_snapshot" in self.session_data:
            lines.append("## 📋 最终状态摘要")
            lines.append("```json")
            lines.append(json.dumps(self.session_data["final_state_snapshot"], ensure_ascii=False, indent=2))
            lines.append("```")
            lines.append("")
        
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    
    def _format_output(self, output: Dict) -> str:
        """格式化节点输出为可读文本
        
        Args:
            output: 输出字典
        Returns:
            str: 格式化字符串
        """
        lines = []
        priority_fields = [
            ("lie_index", "谎言指数"),
            ("dimension_scores", "维度分数"),
            ("called_specialists", "调用专家"),
            ("selected_specialists", "选中专家"),
            ("last_followup_question", "追问问题"),
            ("next_action", "下一步动作"),
            ("followup_strategy", "追问策略"),
            ("priority_issue", "优先问题"),
            ("quick_fact_summary", "事实摘要"),
            ("quick_signal_summary", "信号摘要"),
            ("surface_risk_score", "表面风险分"),
            ("severity", "严重度"),
            ("confidence", "置信度"),
            ("schema_error", "Schema 异常"),
            ("has_new_fact", "是否有新事实"),
            ("stop_reason", "决策原因"),
            ("risk_explanation", "风险解释"),
        ]
        
        for field, name in priority_fields:
            if field in output:
                value = output[field]
                lines.append(f"{name}: {value}")
        
        if "specialist_results" in output:
            lines.append("")
            lines.append("专家分析结果:")
            for result in output["specialist_results"]:
                if isinstance(result, dict):
                    agent = result.get("agent", "unknown")
                    score = result.get("score", 0)
                    lines.append(f"  - [{agent}] 分数: {score}")
        
        return "\n".join(lines)


# 全局日志实例
_logger_instance: Optional[DetailedLogger] = None


def get_logger() -> DetailedLogger:
    """获取全局日志实例"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = DetailedLogger()
    return _logger_instance


def reset_logger():
    """重置全局日志实例（用于新会话）"""
    global _logger_instance
    _logger_instance = None

