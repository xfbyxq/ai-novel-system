"""
上下文携带器.

将推断的约束转化为下一章生成的提示词增强。
使用"读者期待"表述，引导而非强制创作方向。
"""

from typing import Any, Dict, List, Optional

from core.logging_config import logger

from agents.continuity_models import ContinuityConstraint, ConstraintList


class ContextPropagator:
    """
    上下文携带器.

    将推断的约束转化为下一章生成的提示词增强。

    关键设计：
    1. 不直接说"你必须...", 而是说"读者期待..."
    2. 提供正面示例（few-shot），而非负面约束
    3. 保持创作自由度，只引导不强制
    """

    # 约束指导模板
    CONSTRAINT_GUIDANCE_TEMPLATE = """### 读者期待（基于上一章的自然推断）

{constraints_list}

**创作自由度说明**：
以上"读者期待"仅供参考，您有完全的创作自由。关键是保持故事的连贯性和吸引力，
而非机械地满足所有期待。有时打破期待也能产生出色的戏剧效果。
"""

    # Few-shot 示例模板
    FEWSHOT_EXAMPLE_TEMPLATE = """### 过渡技巧参考（仅供启发，不要模仿）

{examples}

注意：这些示例仅展示可能的过渡方式，请根据具体情节选择合适的手法。
"""

    def __init__(self):
        """初始化上下文携带器."""
        logger.info("ContextPropagator initialized")

    def build_enhanced_prompt(
        self,
        next_chapter_outline: str,
        constraints: ConstraintList,
        previous_ending: Optional[str] = None,
        include_fewshot: bool = False,
    ) -> str:
        """
        构建增强型生成提示词.

        Args:
            next_chapter_outline: 下一章情节大纲
            constraints: 推断的约束列表
            previous_ending: 上一章结尾（用于生成 few-shot 示例）
            include_fewshot: 是否包含 few-shot 示例

        Returns:
            增强后的提示词
        """
        logger.info(f"构建增强提示词，包含 {len(constraints)} 个约束")

        # 构建约束指导部分
        constraint_guidance = self._format_constraints_as_guidance(constraints)

        # 构建完整提示词
        enhanced_prompt = f"""## 下一章创作要求.

### 基本情节.
{next_chapter_outline}

{constraint_guidance}
"""

        # 可选：添加 few-shot 示例
        if include_fewshot and previous_ending:
            examples = self._generate_transition_examples(previous_ending, constraints)
            if examples:
                enhanced_prompt += self.FEWSHOT_EXAMPLE_TEMPLATE.format(
                    examples=examples
                )

        return enhanced_prompt

    def _format_constraints_as_guidance(self, constraints: ConstraintList) -> str:
        """
        将约束转化为创作指导（而非硬性要求）.

        关键：用"读者期待"的表述，而非"你必须"

        Args:
            constraints: 约束列表

        Returns:
            格式化的创作指导文本
        """
        if not constraints:
            return ""

        lines = []
        for i, constraint in enumerate(constraints, 1):
            # 将约束转化为读者期待的表述
            expectation = self._constraint_to_expectation(constraint)
            lines.append(f"{i}. {expectation}")

        constraints_list = "\n".join(lines)

        return self.CONSTRAINT_GUIDANCE_TEMPLATE.format(
            constraints_list=constraints_list
        )

    def _constraint_to_expectation(self, constraint: ContinuityConstraint) -> str:
        """
        将约束转化为读者期待的表述.

        示例：
        - 约束："场景转换需要过渡"
        - 转化："基于叙事节奏，读者可能期待场景转换时有平滑的过渡描写"

        Args:
            constraint: 约束对象

        Returns:
            读者期待的表述
        """
        templates = {
            "logical": "基于逻辑，读者可能期待...",
            "narrative": "基于叙事节奏，读者可能期待...",
            "emotional": "基于情绪基调，读者可能期待...",
            "other": "读者可能期待...",
        }

        template = templates.get(constraint.constraint_type, templates["other"])

        # 组合成完整的期待表述
        expectation = f"{template}{constraint.description}"

        # 添加来源文本引用（可选）
        if constraint.source_text and len(constraint.source_text) < 100:
            expectation += f'（源自："{constraint.source_text}..."）'

        return expectation

    def _generate_transition_examples(
        self, previous_ending: str, constraints: ConstraintList
    ) -> str:
        """
        生成 few-shot 过渡示例.

        这部分可以根据约束类型生成通用的过渡示例，
        或者从文学作品中提取经典的过渡手法作为参考。

        Args:
            previous_ending: 上一章结尾
            constraints: 约束列表

        Returns:
            示例文本
        """
        # 简单实现：提供通用示例
        # 实际使用时可以从文学作品库中提取或让 LLM 生成

        examples = []

        # 根据约束类型提供示例
        has_logical = any(c.constraint_type == "logical" for c in constraints)
        has_narrative = any(c.constraint_type == "narrative" for c in constraints)
        has_emotional = any(c.constraint_type == "emotional" for c in constraints)

        if has_logical:
            examples.append(
                "示例 1（逻辑衔接）：\n"
                "上一章结尾：他推开门，看到了令人震惊的一幕...\n"
                "下一章开头：门后的景象让林默倒吸一口凉气。房间里..."
            )

        if has_narrative:
            examples.append(
                "示例 2（叙事过渡）：\n"
                "上一章结尾：三天后...\n"
                "下一章开头：这三天的等待漫长如年。当第四天的黎明降临时..."
            )

        if has_emotional:
            examples.append(
                "示例 3（情绪延续）：\n"
                "上一章结尾：她泪流满面，转身冲入雨中...\n"
                "下一章开头：雨水模糊了视线，但她感觉不到冷。心中的痛楚..."
            )

        if not examples:
            examples.append(
                "通用示例：\n"
                "上一章结尾：[场景 A]\n"
                "下一章开头：[自然过渡到场景 B，保持叙事流畅]"
            )

        return "\n\n".join(examples)

    def create_minimal_guidance(
        self, constraints: ConstraintList, max_items: int = 3
    ) -> str:
        """
        创建最小化的约束指导（用于提示词空间有限的情况）.

        Args:
            constraints: 约束列表
            max_items: 最多显示的约束数量

        Returns:
            最小化指导文本
        """
        if not constraints:
            return ""

        # 选择优先级最高的 N 个约束
        top_constraints = sorted(constraints, key=lambda c: c.priority, reverse=True)[
            :max_items
        ]

        lines = []
        for constraint in top_constraints:
            expectation = self._constraint_to_expectation(constraint)
            lines.append(f"- {expectation}")

        if lines:
            return "\n\n### 关键读者期待\n" + "\n".join(lines)

        return ""


# 便捷函数
def propagate_constraints(
    outline: str, constraints: ConstraintList, previous_ending: Optional[str] = None
) -> str:
    """
    便捷函数：将约束传播到提示词.

    Args:
        outline: 下一章大纲
        constraints: 约束列表
        previous_ending: 上一章结尾

    Returns:
        增强后的提示词
    """
    propagator = ContextPropagator()
    return propagator.build_enhanced_prompt(
        next_chapter_outline=outline,
        constraints=constraints,
        previous_ending=previous_ending,
    )
