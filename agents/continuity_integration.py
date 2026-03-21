"""
章节连贯性保障集成模块.

将连贯性保障系统集成到章节生成流程中。
提供装饰器和辅助函数，用于增强现有的 generation_service。
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from core.logging_config import logger
from llm.qwen_client import QwenClient

from agents.continuity_inference import ConstraintInferenceEngine
from agents.context_propagator import ContextPropagator
from agents.continuity_validation import ValidationEngine
from agents.continuity_models import (
    ValidationReport,
    ChapterTransition,
    ConstraintList,
)


class ContinuityAssuranceIntegration:
    """
    连贯性保障集成器.

    将连贯性检查集成到章节生成流程中，提供：
    1. 约束推断
    2. 提示词增强
    3. 验证和重新生成
    4. 过渡记录保存
    """

    def __init__(self, qwen_client: Optional[QwenClient] = None):
        """
        初始化集成器.

        Args:
            qwen_client: 通义千问客户端
        """
        self.client = qwen_client or QwenClient()
        self.inference_engine = ConstraintInferenceEngine(self.client)
        self.propagator = ContextPropagator()
        self.validation_engine = ValidationEngine(self.client)

        logger.info("ContinuityAssuranceIntegration initialized")

    async def enforce_continuity(
        self,
        novel_id: UUID,
        chapter_number: int,
        previous_chapter_content: str,
        next_chapter_outline: str,
        generation_callback: callable,
        max_regeneration_attempts: int = 3,
        min_quality_score: float = 70.0,
    ) -> Dict[str, Any]:
        """
        强制执行连贯性保障.

        Args:
            novel_id: 小说 ID
            chapter_number: 要生成的章节号
            previous_chapter_content: 上一章完整内容
            next_chapter_outline: 下一章大纲
            generation_callback: 章节生成回调函数
                签名：async def generate(enhanced_prompt: str) -> str
            max_regeneration_attempts: 最大重新生成次数
            min_quality_score: 最低质量评分阈值

        Returns:
            生成结果字典，包含：
            - content: 生成的章节内容
            - transition_record: 过渡记录
            - quality_score: 质量评分
            - regeneration_count: 重新生成次数
        """
        logger.info(f"开始连贯性保障流程：小说={novel_id}, 章节={chapter_number}")

        # Step 1: 推断连贯性约束
        previous_ending = self._extract_ending(previous_chapter_content)
        constraints = await self.inference_engine.infer_constraints(
            previous_chapter_ending=previous_ending
        )

        logger.info(f"推断出 {len(constraints)} 个连贯性约束")

        # Step 2: 构建增强提示词
        enhanced_prompt = self.propagator.build_enhanced_prompt(
            next_chapter_outline=next_chapter_outline,
            constraints=constraints,
            previous_ending=previous_ending,
            include_fewshot=True,
        )

        # Step 3: 生成章节内容（可能重新生成）
        regeneration_count = 0
        last_report = None
        final_content = None

        for attempt in range(max_regeneration_attempts + 1):
            # 调用生成回调
            final_content = await generation_callback(enhanced_prompt)

            # Step 4: 验证连贯性
            chapter_beginning = self._extract_beginning(final_content)
            report = await self.validation_engine.validate(
                previous_ending=previous_ending,
                new_chapter_beginning=chapter_beginning,
                constraints=constraints,
            )

            last_report = report

            # 检查是否通过验证
            if (
                report.quality_score >= min_quality_score
                and not report.needs_regeneration
            ):
                logger.info(
                    f"连贯性验证通过：质量评分={report.quality_score:.1f}, "
                    f"尝试次数={attempt + 1}"
                )
                break

            # 未通过，准备重新生成
            regeneration_count += 1
            logger.warning(
                f"连贯性验证未通过，重新生成 ({regeneration_count}/{max_regeneration_attempts}): "
                f"质量评分={report.quality_score:.1f}"
            )

            # 添加改进建议到提示词
            if report.suggestions:
                enhanced_prompt = self._add_improvement_suggestions(
                    enhanced_prompt, report.suggestions
                )

        # Step 5: 创建过渡记录
        transition_record = self._create_transition_record(
            novel_id=str(novel_id),
            from_chapter=chapter_number - 1,
            to_chapter=chapter_number,
            inferred_constraints=constraints,
            validation_report=last_report,
            final_content=final_content,
            regeneration_count=regeneration_count,
        )

        # Step 6: 保存过渡记录（可选）
        await self._save_transition_record(transition_record)

        return {
            "content": final_content,
            "transition_record": transition_record,
            "quality_score": last_report.quality_score if last_report else 0.0,
            "regeneration_count": regeneration_count,
            "constraints_applied": len(constraints),
        }

    def _extract_ending(self, content: str, max_length: int = 800) -> str:
        """
        提取章节结尾.

        Args:
            content: 章节内容
            max_length: 最大长度

        Returns:
            结尾部分
        """
        if not content:
            return ""

        # 取最后 max_length 字
        ending = content[-max_length:]

        # 尝试从句子开头开始
        first_period = ending.find(".")
        if 0 < first_period < 100:
            ending = ending[first_period + 1 :]

        return ending.strip()

    def _extract_beginning(self, content: str, max_length: int = 800) -> str:
        """
        提取章节开头.

        Args:
            content: 章节内容
            max_length: 最大长度

        Returns:
            开头部分
        """
        if not content:
            return ""

        # 取前 max_length 字
        beginning = content[:max_length]

        return beginning.strip()

    def _add_improvement_suggestions(
        self, original_prompt: str, suggestions: List[str]
    ) -> str:
        """
        添加改进建议到提示词.

        Args:
            original_prompt: 原始提示词
            suggestions: 改进建议列表

        Returns:
            增强后的提示词
        """
        if not suggestions:
            return original_prompt

        suggestions_text = "\n".join(f"- {s}" for s in suggestions)

        enhancement = f"""
\n\n### 改进建议（基于上一版评估）
为了提高章节过渡的连贯性，请特别注意以下几点：
{suggestions_text}

注意：这些建议仅供参考，请根据情节需要灵活处理。
"""

        return original_prompt + enhancement

    def _create_transition_record(
        self,
        novel_id: str,
        from_chapter: int,
        to_chapter: int,
        inferred_constraints: ConstraintList,
        validation_report: ValidationReport,
        final_content: str,
        regeneration_count: int,
    ) -> ChapterTransition:
        """
        创建过渡记录.

        Args:
            novel_id: 小说 ID
            from_chapter: 起始章节号
            to_chapter: 目标章节号
            inferred_constraints: 推断的约束
            validation_report: 验证报告
            final_content: 最终生成的内容
            regeneration_count: 重新生成次数

        Returns:
            ChapterTransition 对象
        """
        # 决定最终决策
        if validation_report.quality_score >= 90:
            final_decision = "直接采用"
            modification_notes = (
                f"质量评分 {validation_report.quality_score:.1f}，无需修改"
            )
        elif validation_report.quality_score >= 70:
            final_decision = "修改后采用"
            modification_notes = (
                f"质量评分 {validation_report.quality_score:.1f}，"
                f"根据建议进行了 {regeneration_count} 次重新生成"
            )
        else:
            final_decision = "重新生成"
            modification_notes = (
                f"质量评分 {validation_report.quality_score:.1f}，"
                f"重新生成 {regeneration_count} 次后仍未达标，建议人工审核"
            )

        return ChapterTransition(
            novel_id=novel_id,
            from_chapter=from_chapter,
            to_chapter=to_chapter,
            inferred_constraints=inferred_constraints,
            validation_report=validation_report,
            final_decision=final_decision,
            modification_notes=modification_notes,
        )

    async def _save_transition_record(self, transition: ChapterTransition) -> None:
        """
        保存过渡记录.

        当前实现：仅记录日志
        未来实现：可以保存到数据库或文件系统

        Args:
            transition: 过渡记录
        """
        logger.info(
            f"保存过渡记录：{transition.novel_id}, "
            f"第{transition.from_chapter}章 -> 第{transition.to_chapter}章, "
            f"决策：{transition.final_decision}"
        )

        # FIXME: 实现持久化存储 - 跟踪于 GitHub Issue #22
        # 可以保存到数据库的 chapter_transitions 表
        # 或者保存到 JSON 文件


# 便捷函数
async def generate_chapter_with_continuity(
    novel_id: UUID,
    chapter_number: int,
    previous_content: str,
    outline: str,
    generate_func: callable,
    qwen_client: Optional[QwenClient] = None,
) -> Dict[str, Any]:
    """
    便捷函数：带连贯性保障的章节生成.

    Args:
        novel_id: 小说 ID
        chapter_number: 章节号
        previous_content: 上一章内容
        outline: 本章大纲
        generate_func: 生成函数
        qwen_client: 通义千问客户端

    Returns:
        生成结果
    """
    integrator = ContinuityAssuranceIntegration(qwen_client)

    return await integrator.enforce_continuity(
        novel_id=novel_id,
        chapter_number=chapter_number,
        previous_chapter_content=previous_content,
        next_chapter_outline=outline,
        generation_callback=generate_func,
    )
