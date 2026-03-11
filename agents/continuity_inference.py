"""
连贯性约束推断引擎

从上一章内容中自动推断读者期待和连贯性约束。
完全基于 LLM 自适应推断，不预设具体规则。
"""
import json
from typing import Any, Dict, List, Optional

from core.logging_config import logger
from llm.qwen_client import QwenClient

from agents.continuity_models import ContinuityConstraint, ConstraintList


class ConstraintInferenceEngine:
    """
    连贯性约束推断引擎
    
    核心方法：
    1. 分析上一章文本，识别"未完成状态"（open states）
    2. 识别"叙事期望"（narrative expectations）
    3. 识别"逻辑约束"（logical constraints）
    
    关键：不预设"什么是悬念"、"什么是伏笔"，
    而是让 LLM 描述"读者在读完这一章后，会期待下一章发生什么"
    """
    
    # 推断提示词模板
    INFERENCE_PROMPT = """请分析以下文本的结尾部分，推断读者会对下一章产生哪些期待。

## 文本结尾
{previous_chapter_ending}

## 分析维度（仅供参考，不限制你的推断）
1. 逻辑期待：基于已发生事件，下一章必须交代什么？
2. 叙事期待：基于叙事节奏，下一章应该延续什么？
3. 情感期待：基于情绪基调，下一章应该保持什么？

## 输出格式
请以 JSON 格式输出推断结果：
{{
    "inferred_constraints": [
        {{
            "type": "logical|narrative|emotional|other",
            "description": "用自然语言描述这个约束",
            "priority": 1-10,
            "source_text": "触发这个约束的原文片段",
            "validation_hint": "如何用自然语言验证下一章是否满足这个约束"
        }}
    ]
}}

## 示例（仅供参考，不要局限于此）
- 如果结尾是"他推开门，看到了...", 可能推断出："需要立即揭示门后的内容"
- 如果结尾是"三天后...", 可能推断出："需要说明这三天内发生了什么"
- 如果结尾是情绪激动的场景，可能推断出："需要延续这种情绪基调"

现在请分析提供的文本：
"""

    def __init__(self, qwen_client: Optional[QwenClient] = None):
        """
        初始化推断引擎
        
        Args:
            qwen_client: 通义千问客户端，如不提供则创建默认实例
        """
        self.client = qwen_client or QwenClient()
        logger.info("ConstraintInferenceEngine initialized")
    
    async def infer_constraints(
        self,
        previous_chapter_ending: str,
        previous_chapter_full: Optional[str] = None,
        max_constraints: int = 8,
        min_priority: int = 6
    ) -> ConstraintList:
        """
        从上一章推断连贯性约束
        
        Args:
            previous_chapter_ending: 上一章结尾（最后 500-1000 字）
            previous_chapter_full: 上一章完整内容（可选，用于全局约束推断）
            max_constraints: 最大约束数量
            min_priority: 最小优先级阈值，低于此值的约束会被过滤
            
        Returns:
            推断出的约束列表，按优先级降序排列
        """
        logger.info(f"开始推断连贯性约束，结尾长度：{len(previous_chapter_ending)} 字")
        
        try:
            # 调用 LLM 推断
            response = await self.client.chat(
                prompt=self.INFERENCE_PROMPT.format(
                    previous_chapter_ending=previous_chapter_ending
                ),
                system="你是一位专业的文学编辑，擅长分析读者期待和叙事连贯性。",
                temperature=0.3,  # 较低温度确保稳定性
                max_tokens=2048,
            )
            
            # 解析结果
            content = response.get("content", "")
            constraints_data = self._parse_llm_response(content)
            
            # 转换为 ContinuityConstraint 对象
            constraints = []
            for item in constraints_data.get("inferred_constraints", []):
                try:
                    constraint = ContinuityConstraint(
                        constraint_type=item.get("type", "other"),
                        description=item.get("description", ""),
                        priority=int(item.get("priority", 5)),
                        source_text=item.get("source_text", ""),
                        validation_hint=item.get("validation_hint", ""),
                        confidence=0.9,  # 默认置信度
                    )
                    constraints.append(constraint)
                except (ValueError, KeyError) as e:
                    logger.warning(f"解析单个约束失败：{e}")
                    continue
            
            # 过滤低优先级约束
            high_priority = [c for c in constraints if c.priority >= min_priority]
            
            # 按优先级降序排序
            high_priority.sort(key=lambda c: c.priority, reverse=True)
            
            # 限制最大数量
            result = high_priority[:max_constraints]
            
            logger.info(
                f"推断完成：原始 {len(constraints)} 个，"
                f"高优先级 {len(high_priority)} 个，最终 {len(result)} 个"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"推断约束失败：{e}", exc_info=True)
            # 返回空列表而非抛出异常，确保流程可以继续
            return []
    
    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """
        解析 LLM 响应
        
        尝试多种解析策略：
        1. 直接解析 JSON
        2. 提取代码块中的 JSON
        3. 提取花括号内的 JSON
        
        Args:
            content: LLM 响应的原始内容
            
        Returns:
            解析后的字典，如失败则返回空字典
        """
        # 策略 1: 直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # 策略 2: 提取代码块中的 JSON
        import re
        json_block_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            content,
            re.DOTALL
        )
        if json_block_match:
            try:
                return json.loads(json_block_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 策略 3: 提取花括号内的 JSON
        brace_match = re.search(r"(\{.*?\})", content, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(1))
            except json.JSONDecodeError:
                pass
        
        logger.warning("无法解析 LLM 响应，返回空字典")
        return {"inferred_constraints": []}
    
    async def infer_with_context(
        self,
        previous_chapter_full: str,
        chapter_number: int,
        novel_context: Optional[str] = None
    ) -> ConstraintList:
        """
        结合上下文推断约束（增强版）
        
        Args:
            previous_chapter_full: 上一章完整内容
            chapter_number: 章节号
            novel_context: 小说整体上下文（可选）
            
        Returns:
            推断出的约束列表
        """
        # 提取结尾部分（最后 800 字）
        ending = previous_chapter_full[-800:] if len(previous_chapter_full) > 800 else previous_chapter_full
        
        # 基础推断
        constraints = await self.infer_constraints(ending)
        
        # 如果有小说整体上下文，可以进行额外推断
        if novel_context and chapter_number == 1:
            # 第一章后的特殊处理：考虑整体设定
            logger.info("结合小说整体设定进行约束推断")
            # 这里可以添加额外的推断逻辑
        
        return constraints
    
    def get_constraint_statistics(self, constraints: ConstraintList) -> Dict[str, Any]:
        """
        获取约束统计信息
        
        Args:
            constraints: 约束列表
            
        Returns:
            统计信息字典
        """
        if not constraints:
            return {
                "total": 0,
                "by_type": {},
                "avg_priority": 0,
                "avg_confidence": 0,
            }
        
        # 按类型分组
        by_type: Dict[str, int] = {}
        for c in constraints:
            by_type[c.constraint_type] = by_type.get(c.constraint_type, 0) + 1
        
        return {
            "total": len(constraints),
            "by_type": by_type,
            "avg_priority": sum(c.priority for c in constraints) / len(constraints),
            "avg_confidence": sum(c.confidence for c in constraints) / len(constraints),
        }


# 便捷函数
async def infer_chapter_constraints(
    previous_ending: str,
    qwen_client: Optional[QwenClient] = None
) -> ConstraintList:
    """
    便捷函数：从上一章结尾推断约束
    
    Args:
        previous_ending: 上一章结尾内容
        qwen_client: 通义千问客户端
        
    Returns:
        推断出的约束列表
    """
    engine = ConstraintInferenceEngine(qwen_client)
    return await engine.infer_constraints(previous_ending)
