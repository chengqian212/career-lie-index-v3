"""JSON 工具模块：处理 LLM 输出中的 JSON 解析

该模块主要用于：
1. 从 LLM 输出文本中提取 JSON 数据
2. 提供安全解析机制，支持多次尝试与日志记录
3. 兼容各种常见格式：纯 JSON、```json 代码块、文本中嵌入 JSON
"""

import json
import logging
import re
from typing import Any, Optional

# 初始化 logger，用于记录解析成功/失败信息
logger = logging.getLogger(__name__)


def extract_json_from_text(text: str) -> Optional[Any]:
    """
    从 LLM 输出文本中提取 JSON 对象

    支持三种情况：
    1. 文本本身是标准 JSON
    2. 使用 ```json ... ``` 包裹的代码块
    3. 文本中嵌入 { ... } 或 [ ... ] JSON 结构

    Args:
        text (str): LLM 输出的文本

    Returns:
        Optional[Any]: 成功解析返回 Python 对象（dict 或 list），失败返回 None
    """
    if not text or not text.strip():
        return None  # 文本为空或仅空白字符

    # ------------------- 尝试 1：直接解析整个文本 -------------------
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass  # 解析失败则尝试下一种方法

    # ------------------- 尝试 2：提取 ```json ... ``` 代码块 -------------------
    pattern = r"```json\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # ------------------- 尝试 3：提取 { ... } 或 [ ... ] 结构 -------------------
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_idx = text.find(start_char)
        if start_idx != -1:
            end_idx = text.rfind(end_char)  # 从后往前找结束符
            if end_idx > start_idx:
                try:
                    return json.loads(text[start_idx : end_idx + 1])
                except json.JSONDecodeError:
                    pass

    # 三种方式都失败，返回 None
    return None


def safe_json_parse_with_retry(text: str, default: Any = None, node_name: str = "未知节点") -> Any:
    """
    安全的 JSON 解析函数，支持两次尝试并记录日志

    流程：
    1. 第一次解析：调用 extract_json_from_text
    2. 如果失败：
        - 使用 clean_llm_output 清理文本（aggressive=True）
        - 再次尝试解析
    3. 两次均失败返回默认值，并记录错误日志

    Args:
        text (str): LLM 输出文本
        default (Any): 解析失败时的返回值
        node_name (str): 节点名称，用于日志记录

    Returns:
        Any: 成功解析的 Python 对象，或 default
    """
    from utils.text_utils import clean_llm_output  # 动态导入清理函数

    # 第一次解析
    result = extract_json_from_text(text)
    if result is not None:
        logger.info(f"[{node_name}] JSON 解析成功")
        return result

    # 第一次失败，记录警告
    logger.warning(
        f"[{node_name}] 第一次 JSON 解析失败，尝试重新解析。"
        f"原始输出长度: {len(text)} 字符，"
        f"原始输出预览: {text[:200]}..."
    )

    # 第二次尝试：清理文本后再解析
    cleaned_again = clean_llm_output(text, aggressive=True)
    result = extract_json_from_text(cleaned_again)
    if result is not None:
        logger.info(f"[{node_name}] 第二次解析成功")
        return result

    # 两次都失败，记录错误并返回默认值
    logger.error(
        f"[{node_name}] JSON 解析彻底失败。"
        f"已尝试两次解析，均无法提取有效 JSON。"
        f"原始输出: {text}"
    )
    return default
