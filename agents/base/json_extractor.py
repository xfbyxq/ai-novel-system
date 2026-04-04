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
    def extract_object(cls, text: str, default: Optional[Dict] = None) -> Dict[str, Any]:
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
        """内部提取方法，按优先级尝试各策略.

        策略优先级：
        1. 直接解析（最快）
        2. 代码块提取（完整匹配）
        3. 未闭合代码块提取
        4. 数组边界提取
        5. 对象边界提取
        6. 清理后解析
        7. 截断修复
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

        # 按优先级尝试各策略
        strategies = [
            cls._strategy_direct_parse,
            cls._strategy_closed_code_block,
            cls._strategy_unclosed_code_block,
            cls._strategy_array_boundary,
            cls._strategy_object_boundary,
            cls._strategy_clean_and_parse,
            cls._strategy_truncation_repair,
        ]

        for strategy in strategies:
            result = strategy(text)
            if result is not None:
                return result

        # 所有策略都失败
        raise ValueError(
            f"无法从响应中提取 JSON, 响应长度: {len(text)}, " f"前200字符: {text[:200]}..."
        )

    @classmethod
    def _strategy_direct_parse(cls, text: str) -> Optional[Any]:
        """策略1：直接解析纯 JSON 文本.

        Args:
            text: 待解析的文本

        Returns:
            解析成功返回 JSON 对象，失败返回 None
        """
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @classmethod
    def _strategy_closed_code_block(cls, text: str) -> Optional[Any]:
        """策略2：从完整闭合的代码块中提取 JSON.

        处理格式：```json ... ``` 或 ``` ... ```
        手动查找第一个和最后一个 ``` 以避免惰性匹配问题。

        Args:
            text: 可能包含代码块的文本

        Returns:
            解析成功返回 JSON 对象，失败返回 None
        """
        first_fence = text.find("```")
        last_fence = text.rfind("```")

        # 没有代码块或只有一个反引号标记（未闭合）
        if first_fence == -1 or last_fence <= first_fence:
            return None

        # 跳过开头的 ```json\n 或 ```\n
        content_start = first_fence + 3
        newline_after_fence = text.find("\n", content_start)
        if newline_after_fence != -1 and newline_after_fence < content_start + 10:
            content_start = newline_after_fence + 1

        json_str = text[content_start:last_fence].strip()
        logger.debug(f"[JSON解析] 策略2-手动提取代码块内容长度: {len(json_str)}")

        # 尝试直接解析
        try:
            result = json.loads(json_str)
            logger.info("[JSON解析] 策略2-成功解析代码块中的JSON")
            return result
        except json.JSONDecodeError as e:
            logger.debug(f"[JSON解析] 策略2-JSON解析失败: {e}")
            # 尝试修复后再解析
            repaired = cls._try_repair_and_parse(json_str)
            if repaired is not None:
                logger.info("[JSON解析] 策略2-修复后成功解析代码块中的JSON")
                return repaired
            return None

    @classmethod
    def _strategy_unclosed_code_block(cls, text: str) -> Optional[Any]:
        """策略3：从未闭合的代码块中提取 JSON.

        处理截断场景：只有一个 ``` 标记，缺少闭合的 ```。
        提取代码块内的 JSON 对象边界。

        Args:
            text: 可能包含未闭合代码块的文本

        Returns:
            解析成功返回 JSON 对象，失败返回 None
        """
        first_fence = text.find("```")
        last_fence = text.rfind("```")

        # 只有存在且仅存在一个反引号标记时才处理
        if first_fence == -1 or first_fence != last_fence:
            return None

        logger.debug(f"[JSON解析] 策略3-尝试未闭合代码块提取, 起始位置: {first_fence}")

        # 跳过 ```json 或 ```
        after_code_block = text[first_fence + 3 :]
        newline_pos = after_code_block.find("\n")
        json_content = (
            after_code_block[newline_pos + 1 :] if newline_pos != -1 else after_code_block
        )

        # 找到 JSON 对象边界
        obj_start = json_content.find("{")
        if obj_start == -1:
            return None

        obj_end = json_content.rfind("}")
        if obj_end <= obj_start:
            return None

        extracted = json_content[obj_start : obj_end + 1]
        logger.debug(
            f"[JSON解析] 策略3-提取范围: [{obj_start}:{obj_end + 1}], "
            f"长度: {len(extracted)}"
        )

        # 尝试直接解析
        try:
            result = json.loads(extracted)
            logger.info("[JSON解析] 策略3-成功解析未闭合代码块中的JSON")
            return result
        except json.JSONDecodeError as e:
            logger.debug(f"[JSON解析] 策略3-JSON解析失败: {e}")
            # 尝试修复后再解析
            repaired = cls._try_repair_and_parse(extracted)
            if repaired is not None:
                logger.info("[JSON解析] 策略3-修复后成功解析未闭合代码块中的JSON")
                return repaired
            return None

    @classmethod
    def _strategy_array_boundary(cls, text: str) -> Optional[Any]:
        """策略4：按数组边界提取 JSON.

        查找文本中第一个 [ 和最后一个 ] 之间的内容。

        Args:
            text: 可能包含 JSON 数组的文本

        Returns:
            解析成功返回 JSON 数组，失败返回 None
        """
        array_start = text.find("[")
        if array_start == -1:
            return None

        array_end = text.rfind("]")
        if array_end <= array_start:
            return None

        logger.debug(f"[JSON解析] 策略4-尝试数组提取, 范围: [{array_start}:{array_end + 1}]")

        array_text = text[array_start : array_end + 1]

        # 尝试直接解析
        try:
            result = json.loads(array_text)
            logger.info("[JSON解析] 策略4-成功解析数组JSON")
            return result
        except json.JSONDecodeError as e:
            logger.debug(f"[JSON解析] 策略4-JSON解析失败: {e}")
            # 尝试修复后再解析
            repaired = cls._try_repair_and_parse(array_text)
            if repaired is not None:
                logger.info("[JSON解析] 策略4-修复后成功解析数组JSON")
                return repaired
            return None

    @classmethod
    def _strategy_object_boundary(cls, text: str) -> Optional[Any]:
        """策略5：按对象边界提取 JSON.

        查找文本中第一个 { 和最后一个 } 之间的内容。

        Args:
            text: 可能包含 JSON 对象的文本

        Returns:
            解析成功返回 JSON 对象，失败返回 None
        """
        obj_start = text.find("{")
        if obj_start == -1:
            return None

        obj_end = text.rfind("}")
        if obj_end <= obj_start:
            return None

        logger.debug(f"[JSON解析] 策略5-尝试对象提取, 范围: [{obj_start}:{obj_end + 1}]")

        obj_text = text[obj_start : obj_end + 1]

        # 尝试直接解析
        try:
            result = json.loads(obj_text)
            logger.info("[JSON解析] 策略5-成功解析对象JSON")
            return result
        except json.JSONDecodeError as e:
            logger.debug(f"[JSON解析] 策略5-JSON解析失败: {e}")
            # 尝试修复后再解析
            repaired = cls._try_repair_and_parse(obj_text)
            if repaired is not None:
                logger.info("[JSON解析] 策略5-修复后成功解析对象JSON")
                return repaired
            return None

    @classmethod
    def _strategy_clean_and_parse(cls, text: str) -> Optional[Any]:
        """策略6：清理格式问题后解析.

        处理常见的 JSON 格式问题：
        - 移除注释
        - 移除尾部逗号
        - 处理单引号

        Args:
            text: 可能包含格式问题的 JSON 文本

        Returns:
            解析成功返回 JSON 对象，失败返回 None
        """
        cleaned = cls._clean_json_string(text)
        if cleaned == text:
            return None

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None

    @classmethod
    def _strategy_truncation_repair(cls, text: str) -> Optional[Any]:
        """策略7：截断修复策略.

        检测并修复被截断的 JSON，当 LLM 输出被截断时，
        JSON 可能缺少闭合的 } 或 ]。

        Args:
            text: 可能被截断的 JSON 文本

        Returns:
            解析成功返回 JSON 对象，失败返回 None
        """
        repaired = cls._repair_truncated_json(text)
        if not repaired:
            return None

        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e:
            logger.debug(f"截断修复后仍解析失败: {e}")
            return None

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

        logger.debug(f"检测到 JSON 截断: 缺失 {missing_braces} 个 }} 和 {missing_brackets} 个 ]")

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
                if i > 0 and text[i - 1] == "\\":
                    # 检查是否是双重转义 \\\\"（此时引号有效）
                    backslash_count = 0
                    j = i - 1
                    while j >= 0 and text[j] == "\\":
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
    def _try_repair_and_parse(cls, json_str: str) -> Optional[Any]:
        """对提取出的 JSON 字符串尝试多种修复策略.

        依次尝试：
        1. 清理常见格式问题（注释、尾部逗号、单引号）
        2. 修复截断（补充闭合符号）
        3. 先清理再修复截断
        4. 激进修复（移除最后一个不完整的键值对）

        Args:
            json_str: 提取出的 JSON 字符串（可能被截断或格式不规范）

        Returns:
            解析成功返回 JSON 对象，所有修复策略都失败返回 None
        """
        # 尝试1：清理格式问题
        cleaned = cls._clean_json_string(json_str)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 尝试2：修复截断
        repaired = cls._repair_truncated_json(json_str)
        if repaired:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

        # 尝试3：先清理再修复截断
        repaired = cls._repair_truncated_json(cleaned)
        if repaired:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

        # 尝试4：激进修复 - 移除最后一个不完整的键值对
        aggressive = cls._aggressive_truncation_repair(json_str)
        if aggressive:
            try:
                return json.loads(aggressive)
            except json.JSONDecodeError:
                pass

        return None

    @classmethod
    def _aggressive_truncation_repair(cls, text: str) -> Optional[str]:
        """激进的截断修复策略.

        当标准修复失败时，尝试移除最后一个不完整的键值对，
        然后补充闭合符号。适用于 JSON 被深度截断导致
        字段名或字段值被切断的场景。

        例如：{"a": 1, "b": {"c": "ch  ->  {"a": 1}

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

        # 策略：逐步从尾部回退，找到最后一个可以构成有效 JSON 的截断点
        # 尝试在最后一个逗号处截断
        last_comma = json_part.rfind(",")
        while last_comma > 0:
            truncated = json_part[:last_comma]
            # 补充闭合符号
            open_braces = truncated.count("{") - truncated.count("}")
            open_brackets = truncated.count("[") - truncated.count("]")

            if open_braces >= 0 and open_brackets >= 0:
                repaired = truncated + "]" * open_brackets + "}" * open_braces
                try:
                    json.loads(repaired)
                    logger.info(
                        f"[JSON解析] 激进修复成功: 在位置 {last_comma} 处截断, "
                        f"补充了 {open_brackets} 个 ] 和 {open_braces} 个 }}"
                    )
                    return repaired
                except json.JSONDecodeError:
                    pass

            # 继续回退到上一个逗号
            last_comma = json_part.rfind(",", 0, last_comma)

        return None

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
