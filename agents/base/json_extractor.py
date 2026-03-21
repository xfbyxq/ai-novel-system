"""JSON 提取工具类.

统一处理 LLM 响应中的 JSON 提取，支持多种格式：
- 纯 JSON 文本
- Markdown 代码块包裹的 JSON
- 混合文本中的 JSON 对象/数组
"""

import json
import re
from typing import Any, Dict, List, Optional, Union

from core.logging_config import logger


class JsonExtractor:
    """LLM 响应 JSON 提取器.

    提供多种策略从 LLM 响应中提取 JSON：
    1. 直接解析（纯 JSON）
    2. 代码块提取（```json ... ```）
    3. 边界查找（找到 { 和 } 或 [ 和 ]）

    使用示例：
        extractor = JsonExtractor()
        data = extractor.extract(response_text)

        # 或使用静态方法
        data = JsonExtractor.extract_json(response_text)
    """

    # 代码块正则：匹配 ```json ... ``` 或 ``` ... ```
    CODE_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)```")

    @classmethod
    def extract_json(cls, text: str, default: Any = None) -> Any:
        """从文本中提取 JSON（静态方法）.

        Args:
            text: LLM 响应文本
            default: 提取失败时的默认值（如果为 None 则抛出异常）

        Returns:
            解析后的 JSON 对象（dict 或 list）

        Raises:
            ValueError: 当无法提取 JSON 且未提供默认值时
        """
        try:
            return cls._extract(text)
        except ValueError as e:
            if default is not None:
                logger.warning(f"JSON 提取失败，使用默认值: {e}")
                return default
            raise

    @classmethod
    def extract_object(
        cls, text: str, default: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """提取 JSON 对象（字典）.

        Args:
            text: LLM 响应文本
            default: 提取失败时的默认值

        Returns:
            解析后的字典
        """
        result = cls.extract_json(text, default)
        if isinstance(result, dict):
            return result
        if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
            # 如果是数组，返回第一个元素
            return result[0]
        if default is not None:
            return default
        raise ValueError(f"提取结果不是对象类型: {type(result)}")

    @classmethod
    def extract_array(cls, text: str, default: Optional[List] = None) -> List[Any]:
        """提取 JSON 数组.

        Args:
            text: LLM 响应文本
            default: 提取失败时的默认值

        Returns:
            解析后的列表
        """
        result = cls.extract_json(text, default)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # 如果是对象，包装为数组
            return [result]
        if default is not None:
            return default
        raise ValueError(f"提取结果不是数组类型: {type(result)}")

    @classmethod
    def _extract(cls, text: str) -> Any:
        """内部提取方法，尝试多种策略.

        策略优先级：
        1. 直接解析（最快）
        2. 代码块提取
        3. 边界查找（最宽松）
        """
        if not text:
            raise ValueError("输入文本为空")

        text = text.strip()

        # 策略1：直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 策略2：代码块提取
        match = cls.CODE_BLOCK_PATTERN.search(text)
        if match:
            json_str = match.group(1).strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 策略3a：尝试找 JSON 数组
        array_start = text.find("[")
        if array_start != -1:
            array_end = text.rfind("]")
            if array_end > array_start:
                try:
                    return json.loads(text[array_start : array_end + 1])
                except json.JSONDecodeError:
                    pass

        # 策略3b：尝试找 JSON 对象
        obj_start = text.find("{")
        if obj_start != -1:
            obj_end = text.rfind("}")
            if obj_end > obj_start:
                try:
                    return json.loads(text[obj_start : obj_end + 1])
                except json.JSONDecodeError:
                    pass

        # 策略4：尝试修复常见问题后解析
        cleaned = cls._clean_json_string(text)
        if cleaned != text:
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

        # 所有策略都失败
        raise ValueError(f"无法从响应中提取 JSON: {text[:200]}...")

    @classmethod
    def _clean_json_string(cls, text: str) -> str:
        """尝试修复常见的 JSON 格式问题.

        处理：
        - 移除注释
        - 移除尾部逗号
        - 处理单引号
        """
        # 移除单行注释
        text = re.sub(r"//.*$", "", text, flags=re.MULTILINE)

        # 移除多行注释
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)

        # 找到 JSON 边界
        start = text.find("{")
        if start == -1:
            start = text.find("[")
        if start == -1:
            return text

        end = max(text.rfind("}"), text.rfind("]"))
        if end == -1 or end <= start:
            return text

        json_part = text[start : end + 1]

        # 移除尾部逗号（如 [1, 2, 3,] 或 {"a": 1,}）
        json_part = re.sub(r",\s*([}\]])", r"\1", json_part)

        return json_part

    @classmethod
    def safe_extract(cls, text: str, context: str = "") -> Dict[str, Any]:
        """安全提取，失败时返回空字典并记录日志.

        Args:
            text: LLM 响应文本
            context: 上下文信息（用于日志）

        Returns:
            解析后的字典，失败时返回空字典
        """
        try:
            result = cls._extract(text)
            if isinstance(result, dict):
                return result
            if isinstance(result, list):
                return {"items": result}
            return {"value": result}
        except Exception as e:
            if context:
                logger.warning(f"[{context}] JSON 提取失败: {e}")
            else:
                logger.warning(f"JSON 提取失败: {e}")
            return {}


# 便捷函数（向后兼容）
def extract_json(text: str) -> Any:
    """从 LLM 响应中提取 JSON（便捷函数）.

    这是 JsonExtractor.extract_json 的快捷方式，
    用于替换原有的 _extract_json 静态方法。

    Args:
        text: LLM 响应文本

    Returns:
        解析后的 JSON 对象

    Raises:
        ValueError: 当无法提取 JSON 时
    """
    return JsonExtractor.extract_json(text)
