"""JSON 提取工具类.

统一处理 LLM 响应中的 JSON 提取，支持多种格式：
- 纯 JSON 文本
- Markdown 代码块包裹的 JSON
- 混合文本中的 JSON 对象/数组
"""

import json
import re
from typing import Any, Dict, List, Optional

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

        # 排查日志：记录原始响应信息
        logger.info(
            f"[JSON解析] 原始响应长度: {len(text)}, "
            f"前100字符: {text[:100]!r}, "
            f"后50字符: {text[-50:]!r}"
        )

        # 策略1：直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 策略2：代码块提取（完整匹配，有闭合标记）
        match = cls.CODE_BLOCK_PATTERN.search(text)
        logger.debug(f"[JSON解析] 策略2-正则匹配结果: {match is not None}")
        if match:
            json_str = match.group(1).strip()
            logger.debug(f"[JSON解析] 策略2-提取到的代码块内容长度: {len(json_str)}")
            try:
                result = json.loads(json_str)
                logger.info("[JSON解析] 策略2-成功解析代码块中的JSON")
                return result
            except json.JSONDecodeError as e:
                logger.debug(f"[JSON解析] 策略2-JSON解析失败: {e}")
        else:
            # 正则未匹配，检查是否存在未闭合的代码块
            has_opening = "```" in text
            closing_count = text.count("```")
            logger.debug(
                f"[JSON解析] 策略2-正则未匹配, "
                f"存在反引号: {has_opening}, "
                f"反引号出现次数: {closing_count}"
            )

        # 策略2b：未闭合的代码块（截断场景）
        # 如果响应以 ```json 或 ``` 开头但没有闭合的 ```，尝试提取代码块内的 JSON
        code_block_start = text.find("```")
        if code_block_start != -1:
            logger.debug(f"[JSON解析] 策略2b-尝试未闭合代码块提取, 起始位置: {code_block_start}")
            # 跳过 ```json 或 ```
            after_code_block = text[code_block_start + 3:]
            # 跳过语言标识（如 json）
            newline_pos = after_code_block.find("\n")
            if newline_pos != -1:
                json_content = after_code_block[newline_pos + 1:]
            else:
                json_content = after_code_block
            # 找到 JSON 对象边界
            obj_start = json_content.find("{")
            if obj_start != -1:
                obj_end = json_content.rfind("}")
                if obj_end > obj_start:
                    extracted = json_content[obj_start:obj_end + 1]
                    logger.debug(
                        f"[JSON解析] 策略2b-提取范围: [{obj_start}:{obj_end + 1}], "
                        f"长度: {len(extracted)}"
                    )
                    try:
                        result = json.loads(extracted)
                        logger.info("[JSON解析] 策略2b-成功解析未闭合代码块中的JSON")
                        return result
                    except json.JSONDecodeError as e:
                        logger.debug(f"[JSON解析] 策略2b-JSON解析失败: {e}")

        # 策略3a：尝试找 JSON 数组
        array_start = text.find("[")
        if array_start != -1:
            array_end = text.rfind("]")
            if array_end > array_start:
                logger.debug(f"[JSON解析] 策略3a-尝试数组提取, 范围: [{array_start}:{array_end + 1}]")
                try:
                    result = json.loads(text[array_start : array_end + 1])
                    logger.info("[JSON解析] 策略3a-成功解析数组JSON")
                    return result
                except json.JSONDecodeError as e:
                    logger.debug(f"[JSON解析] 策略3a-JSON解析失败: {e}")

        # 策略3b：尝试找 JSON 对象
        obj_start = text.find("{")
        if obj_start != -1:
            obj_end = text.rfind("}")
            if obj_end > obj_start:
                logger.debug(f"[JSON解析] 策略3b-尝试对象提取, 范围: [{obj_start}:{obj_end + 1}]")
                try:
                    result = json.loads(text[obj_start : obj_end + 1])
                    logger.info("[JSON解析] 策略3b-成功解析对象JSON")
                    return result
                except json.JSONDecodeError as e:
                    logger.debug(f"[JSON解析] 策略3b-JSON解析失败: {e}")

        # 策略4：尝试修复常见问题后解析
        cleaned = cls._clean_json_string(text)
        if cleaned != text:
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

        # 策略5：截断修复策略 - 检测并修复被截断的 JSON
        # 当 LLM 输出被截断时，JSON 可能缺少闭合的 } 或 ]
        repaired = cls._repair_truncated_json(text)
        if repaired:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError as e:
                logger.debug(f"截断修复后仍解析失败: {e}")

        # 所有策略都失败
        raise ValueError(
            f"无法从响应中提取 JSON, 响应长度: {len(text)}, "
            f"前200字符: {text[:200]}..."
        )

    @classmethod
    def _clean_json_string(cls, text: str) -> str:
        """尝试修复常见的 JSON 格式问题.

        处理：
        - 移除注释
        - 移除尾部逗号
        - 处理单引号（转换为双引号）
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

        # 处理单引号：将键和字符串值的单引号转换为双引号
        # 匹配键名：'key': -> "key":
        json_part = re.sub(r"'([^']+)'\s*:", r'"\1":', json_part)
        # 匹配字符串值：: 'value' -> : "value" (简单场景)
        json_part = re.sub(r":\s*'([^']*)'(,|}|\])", r':"\1"\2', json_part)

        return json_part

    @classmethod
    def _repair_truncated_json(cls, text: str) -> Optional[str]:
        """尝试修复被截断的 JSON.

        当 LLM 输出被截断时，JSON 可能缺少闭合的 } 或 ]。
        此方法检测截断并尝试补充缺失的闭合符号。

        修复策略：
        1. 计算 { 和 } 的数量差，以及 [ 和 ] 的数量差
        2. 如果检测到未闭合，先处理可能未闭合的字符串值
        3. 按正确顺序补充缺失的 ] 和 }

        Args:
            text: 可能被截断的 JSON 文本

        Returns:
            修复后的 JSON 字符串，如果无法修复则返回 None
        """
        # 找到 JSON 起始位置
        json_start = text.find("{")
        if json_start == -1:
            json_start = text.find("[")
        if json_start == -1:
            return None

        json_part = text[json_start:]

        # 计算括号数量差
        open_braces = json_part.count("{")
        close_braces = json_part.count("}")
        open_brackets = json_part.count("[")
        close_brackets = json_part.count("]")

        missing_braces = open_braces - close_braces
        missing_brackets = open_brackets - close_brackets

        # 如果没有缺失的闭合符号，不需要修复
        if missing_braces <= 0 and missing_brackets <= 0:
            return None

        logger.debug(
            f"检测到 JSON 截断: 缺失 {missing_braces} 个 }} 和 {missing_brackets} 个 ]"
        )

        # 尝试修复
        repaired = json_part

        # 先处理可能未闭合的字符串值
        # 检查最后一个 \" 后面是否有闭合的 \"
        repaired = cls._close_unclosed_string(repaired)

        # 补充缺失的闭合符号（先 ] 后 }，符合 JSON 嵌套规范）
        # 注意：这里使用简化的顺序补充，对于复杂的嵌套可能不完全准确
        # 但作为尽力而为的策略，通常能有效处理常见的截断场景
        repaired = repaired + "]" * missing_brackets + "}" * missing_braces

        return repaired

    @classmethod
    def _close_unclosed_string(cls, text: str) -> str:
        """尝试闭合未闭合的字符串值.

        检查 JSON 中最后一个未闭合的字符串值，并补充闭合引号。
        这是处理截断场景中字符串值被切断的情况.

        Args:
            text: JSON 文本

        Returns:
            处理后的 JSON 文本
        """
        # 找到最后一个 \" 的位置
        last_quote = text.rfind('"')
        if last_quote == -1:
            return text

        # 从最后位置往前扫描，检查这个引号是否已闭合
        # 统计引号数量（偶数表示闭合，奇数表示未闭合）
        quote_count = 0
        i = 0
        while i < len(text):
            if text[i] == '"':
                # 检查是否是转义引号
                if i > 0 and text[i - 1] == '\\':
                    # 检查是否是双重转义 \\\\"（此时引号有效）
                    backslash_count = 0
                    j = i - 1
                    while j >= 0 and text[j] == '\\':
                        backslash_count += 1
                        j -= 1
                    if backslash_count % 2 == 0:
                        # 偶数个反斜杠，说明这个引号是转义的，不计数
                        pass
                    else:
                        # 奇数个反斜杠，这个引号有效
                        quote_count += 1
                else:
                    quote_count += 1
            i += 1

        # 如果引号数量为奇数，说明有未闭合的字符串
        if quote_count % 2 == 1:
            # 补充闭合引号
            # 首先截断到最后一个有效字符（去除可能的乱码）
            # 然后添加闭合引号
            text = text + '"'
            logger.debug("检测到未闭合的字符串值，已补充闭合引号")

        return text

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
