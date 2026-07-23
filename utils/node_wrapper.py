"""节点执行包装器：监控节点执行并记录日志"""

import time
from typing import Callable, Dict
from utils.logger import get_logger


def wrap_node(node_func: Callable) -> Callable:
    """包装节点函数，添加执行监控和日志记录
    
    每个被包装的节点在执行时会自动：
    1. 记录执行开始时间
    2. 捕获执行结果或错误
    3. 计算耗时
    4. 将节点执行信息写入日志记录器
    
    Args:
        node_func: 原始节点函数
        
    Returns:
        包装后的节点函数，行为与原始函数一致
    """
    def wrapped(state: Dict) -> Dict:
        """包装后的执行函数
        
        Args:
            state: 输入状态
            
        Returns:
            输出更新字典
        """
        node_name = node_func.__name__
        logger = get_logger()
        
        # 记录开始时间
        start_time = time.time()
        error = None
        output = {}
        
        try:
            # 执行原始节点函数
            output = node_func(state)
            
            # 确保输出是字典
            if not isinstance(output, dict):
                error = f"节点返回非字典类型: {type(output)}"
                output = {}
            
        except Exception as e:
            error = str(e)
            elapsed = time.time() - start_time
            
            # 记录日志（包括错误信息）
            logger.log_node(
                node_name=node_name,
                input_state=state,
                output_updates={},
                elapsed_seconds=elapsed,
                error=error,
            )
            
            # 重新抛出原始异常，不吞掉
            raise
        
        # 计算耗时
        elapsed = time.time() - start_time
        
        # 记录日志（成功情况）
        logger.log_node(
            node_name=node_name,
            input_state=state,
            output_updates=output,
            elapsed_seconds=elapsed,
            error=error,
        )
        
        return output
    
    # 保留原始函数的元信息
    wrapped.__name__ = node_func.__name__
    wrapped.__doc__ = node_func.__doc__
    wrapped.__module__ = node_func.__module__
    
    return wrapped

