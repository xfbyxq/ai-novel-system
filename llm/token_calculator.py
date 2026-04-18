"""Token 计算工具 - 基于 tiktoken 精确计算 token 数量并动态分配输出空间"""

import tiktoken
from core.logging_config import logger


class TokenCalculator:
    """基于 tiktoken 的 token 计算器
    
    用于精确计算输入文本的 token 数量，并根据模型上下文窗口
    动态计算推荐的 max_tokens 值，避免固定值导致的截断或超限问题。
    """
    
    def __init__(self, encoding_name: str = "cl100k_base"):
        """初始化 token 计算器
        
        Args:
            encoding_name: tiktoken 编码方式，默认 cl100k_base
        """
        try:
            self.enc = tiktoken.get_encoding(encoding_name)
        except Exception as e:
            logger.warning(f"tiktoken 编码 {encoding_name} 加载失败: {e}，使用简化估算")
            self.enc = None
    
    def count_tokens(self, text: str) -> int:
        """精确计算文本的 token 数
        
        Args:
            text: 待计算的文本
            
        Returns:
            token 数量
        """
        if not text:
            return 0
        if self.enc is not None:
            return len(self.enc.encode(text))
        # 降级方案：简化估算（中文约 1.3 字符/token）
        return int(len(text) / 1.3)
    
    def calculate_max_tokens(
        self,
        prompt: str,
        system: str = "",
        context_window: int = 196608,
        min_output: int = 1024,
        max_output: int = 16384,
        buffer: int = 512,
    ) -> int:
        """根据输入动态计算推荐的 max_tokens
        
        公式: available = context_window - input_tokens - buffer
        结果限制在 [min_output, max_output] 范围内
        
        Args:
            prompt: 用户 prompt 文本
            system: 系统提示文本
            context_window: 模型上下文窗口大小
            min_output: 最小输出 token 数（保底值）
            max_output: 最大输出 token 数（控制成本）
            buffer: 安全缓冲区
            
        Returns:
            推荐的 max_tokens 值
        """
        input_tokens = self.count_tokens(prompt) + self.count_tokens(system)
        available = context_window - input_tokens - buffer
        result = max(min_output, min(max_output, available))
        
        logger.debug(
            f"动态 max_tokens 计算: 输入={input_tokens} tokens, "
            f"可用={available}, 结果={result} "
            f"(窗口={context_window}, 缓冲={buffer})"
        )
        
        # 如果可用空间不足 min_output，发出警告
        if available < min_output:
            logger.warning(
                f"输入过大，可用输出空间不足: 输入={input_tokens} tokens, "
                f"可用={available} < 最小输出={min_output}。"
                f"输出可能被截断，建议压缩输入内容。"
            )
        
        return result
