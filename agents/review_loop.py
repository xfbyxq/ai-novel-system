"""审查反馈循环 - Writer 与 Editor 间的质量驱动迭代."""

import json
from typing import Any, Dict, List, Optional

from agents.base import (
    BaseReviewLoopHandler,
    ChapterQualityReport,
    JsonExtractor,
    ReviewLoopResult,
)
from agents.base.review_loop_base import (
    IssueTracker,
    QualityLevel,
    ReviewProgressSummary,
)
from agents.team_context import AgentReview, NovelTeamContext
from backend.config import settings
from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient

# ── 审查专用提示词 ──────────────────────────────────────────

EDITOR_REVIEW_SYSTEM = """你是一位资深的网络小说编辑，负责审查章节内容并给出详细评分和润色.

你的工作包含三个部分：
1. 对内容进行多维度精确评分（8个维度）
2. 生成聚合维度评分（连贯性、合理性、趣味性）
3. 润色并输出修改后的完整内容

【精确评分维度】（1-10分）：
- satisfaction_design（爽感设计）：章节是否有明确的爽点（打脸/升级/逆转/揭秘）？爽点是否有足够铺垫（先抑后扬）？释放是否彻底？章末是否有有效卡章？
- foreshadowing（伏笔设计）：伏笔是否埋设合理？是否有铺垫？后续是否可能兑现？悬念设置是否有效？
- character_distinctiveness（角色辨识度）：主角是否有鲜明特征？职业能力是否发挥作用？是否有个人习惯或口头禅？
- plot_logic（情节逻辑）：因果关系是否清晰？动机是否充分？事件发展是否合理？
- character_consistency（角色一致性）：称呼是否统一？行为是否矛盾？性格是否前后一致？
- setting_consistency（设定一致性）：世界观设定是否前后一致？角色设定是否矛盾？时间线是否清晰？
- pacing（节奏把控）：场景节奏是否有变化？是否过于相似？张弛是否有度？
- fluency（语言流畅度）：表达是否流畅？衔接是否自然？用词是否准确？

【跨章节一致性检查清单】（关键！影响setting_consistency评分）：
1. 情节重复检测：本章的核心情节是否与前文重复？（如：破解暗号、发现线索的方式）
2. 时间线检测：是否有明确的时间锚点？时间推进是否合理？是否与前文时间线矛盾？
3. 人物设定演变：人物能力/性格/身份的转变是否有铺垫？转变是否突兀？
4. 事件后果追踪：前文事件（如违纪行为）是否在本章有后续反映？
5. 设定一致性：角色外貌、能力、职业是否与前文描述一致？

【聚合维度评分标准】（根据精确维度计算，以星级展示）：
- 连贯性(coherence)：情节前后衔接是否自然、设定是否一致、角色行为逻辑是否流畅
  ★★★★★(9-10)：完全连贯，无任何矛盾
  ★★★★☆(7-8)：基本连贯，有少量不影响阅读的不一致
  ★★★☆☆(5-6)：存在明显的衔接问题或设定矛盾
  ★★☆☆☆(3-4)：多处不连贯，影响阅读体验
  ★☆☆☆☆(1-2)：严重混乱，无法理解

- 合理性(plausibility)：动机是否充分、因果关系是否清晰、伏笔铺垫是否合理
  ★★★★★：动机充分合理，因果关系清晰，铺垫恰到好处
  ★★★★☆：基本合理，有少量可接受的简化处理
  ★★★☆☆：存在动机不够充分或因果跳跃
  ★★☆☆☆：多处不合理，需要补充铺垫
  ★☆☆☆☆：严重违背逻辑和设定

- 趣味性(engagement)：爽点设计、悬念布局、角色吸引力
  ★★★★★：爽点精彩，悬念布局巧妙，角色魅力十足
  ★★★★☆：有明确的爽点和悬念，节奏紧凑
  ★★★☆☆：趣味性一般，缺少高潮或悬念不足
  ★★☆☆☆：较为平淡，缺少吸引点
  ★☆☆☆☆：毫无吸引力，难以继续阅读

【问题描述格式要求】：
每条问题必须包含：
1. location: 问题位置（type: paragraph/scene/character/global, identifier: 具体标识, excerpt: 可选摘录）
2. description: 问题描述（精炼概括）
3. manifestation: 具体表现（原文中的具体表现，可列举多个）
4. severity: 严重程度（high/medium/low）
5. priority_category: 优先级分类
   - reading_experience: 影响阅读体验（称呼不一致、设定矛盾等）— 必须修改
   - excitement: 提升精彩度（爽点不足、悬念缺失等）— 建议增强
   - polish: 细节打磨（措辞优化、节奏调整等）— 可考虑优化
6. suggestion: 修订建议（具体可操作）
7. related_dimensions: 关联维度（如 ["coherence", "plausibility"]）"""

EDITOR_REVIEW_TASK = """请审查并润色以下章节内容.

{previous_chapters_section}

## 当前章节信息
- 章节号：第{chapter_number}章
- 标题：{chapter_title}
- 章节目标：{chapter_summary}

{timeline_anchor_section}

原文：
{draft_content}

请以JSON格式输出（不要输出其他内容）：
{{
    "overall_score": 综合评分(1-10浮点数),
    "dimension_scores": {{
        "satisfaction_design": 分数,
        "foreshadowing": 分数,
        "character_distinctiveness": 分数,
        "plot_logic": 分数,
        "character_consistency": 分数,
        "setting_consistency": 分数,
        "pacing": 分数,
        "fluency": 分数
    }},
    "aggregate_dimension_ratings": {{
        "coherence": "★★★☆☆格式",
        "plausibility": "★★★☆☆格式",
        "engagement": "★★★★☆格式"
    }},
    "overall_assessment": "整体评价文本（2-3句话概括章节质量）",
    "detailed_issues": [
        {{
            "location": {{
                "type": "paragraph/scene/character/global",
                "identifier": "具体位置标识（如第3段、开篇场景、主角王明）",
                "excerpt": "问题片段摘录（可选，50字以内）"
            }},
            "description": "问题描述（精炼概括）",
            "manifestation": ["具体表现1", "具体表现2"],
            "severity": "high/medium/low",
            "priority_category": "reading_experience/excitement/polish",
            "suggestion": "修订建议",
            "related_dimensions": ["coherence/plausibility/engagement"]
        }}
    ],
    "revision_by_priority": {{
        "reading_experience": ["影响阅读体验的修订建议"],
        "excitement": ["提升精彩度的修订建议"],
        "polish": ["细节打磨的修订建议"]
    }},
    "edited_content": "润色后的完整章节内容"
}}"""

WRITER_REVISION_TASK = """你之前写的第{chapter_number}章（{chapter_title}）经过编辑审查，需要修订.

编辑评分：{score}/10
编辑反馈：
{suggestions}

你的上一版内容：
{previous_content}

章节计划：
{chapter_plan}

请根据编辑的反馈修订内容，重点解决指出的问题。
直接输出修订后的完整章节内容，不要输出JSON或其他格式标记。"""


class ReviewLoopHandler(BaseReviewLoopHandler[str, ReviewLoopResult, ChapterQualityReport]):
    """Writer-Editor 审查反馈循环处理器.

    流程：
    1. Writer 生成/修订内容
    2. Editor 审查 + 评分 + 润色
    3. 如果 score < threshold 且未达上限 → 将 suggestions 注入 Writer prompt → 回到 1
    4. 返回最终内容 + 迭代历史
    """

    def __init__(
        self,
        client: QwenClient,
        cost_tracker: CostTracker,
        quality_threshold: float = 7.5,
        max_iterations: int = 3,
        timeout: float = None,
    ):
        """初始化章节审查处理器.

        Args:
            client: LLM 客户端
            cost_tracker: 成本追踪器
            quality_threshold: 质量阈值（默认 7.5，比其他审查略高）
            max_iterations: 最大迭代次数
            timeout: 单次迭代超时时间（秒），默认从配置读取
        """
        if timeout is None:
            timeout = settings.CHAPTER_REVIEW_TIMEOUT

        super().__init__(
            client=client,
            cost_tracker=cost_tracker,
            quality_threshold=quality_threshold,
            max_iterations=max_iterations,
            timeout=timeout,
        )

    async def execute(
        self,
        initial_draft: str,
        chapter_number: int,
        chapter_title: str,
        chapter_summary: str,
        chapter_plan_json: str,
        writer_system_prompt: str,
        team_context: Optional[NovelTeamContext] = None,
        previous_chapters_summary: str = "",
        timeline_anchor: str = "",
    ) -> ReviewLoopResult:
        """执行 Writer-Editor 反馈循环.

        Args:
            initial_draft: Writer 的首版初稿
            chapter_number: 章节号
            chapter_title: 章节标题
            chapter_summary: 章节概要
            chapter_plan_json: 章节计划 JSON 字符串
            writer_system_prompt: Writer 的 system prompt（含风格）
            team_context: 团队上下文（可选，用于记录审查反馈）
            previous_chapters_summary: 前文章节摘要（用于跨章节一致性检查）
            timeline_anchor: 时间线锚点信息（用于时间一致性检查）

        Returns:
            ReviewLoopResult
        """
        # 保存上下文供内部方法使用
        self._chapter_number = chapter_number
        self._chapter_title = chapter_title
        self._chapter_summary = chapter_summary
        self._chapter_plan_json = chapter_plan_json
        self._writer_system_prompt = writer_system_prompt
        self._team_context = team_context
        self._previous_chapters_summary = previous_chapters_summary
        self._timeline_anchor = timeline_anchor

        return await super().execute(
            initial_content=initial_draft,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_summary=chapter_summary,
            chapter_plan_json=chapter_plan_json,
            writer_system_prompt=writer_system_prompt,
            team_context=team_context,
            previous_chapters_summary=previous_chapters_summary,
            timeline_anchor=timeline_anchor,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # 实现抽象方法
    # ══════════════════════════════════════════════════════════════════════════

    def _get_loop_name(self) -> str:
        return "ReviewLoop"

    def _create_result(self) -> ReviewLoopResult:
        return ReviewLoopResult()

    def _create_quality_report(self, review_data: Dict[str, Any]) -> ChapterQualityReport:
        return ChapterQualityReport.from_llm_response(
            review_data,
            quality_threshold=self.quality_threshold,
        )

    async def _validate_edited_content(
        self,
        original_content: str,
        edited_content: str,
        review_data: Dict[str, Any],
    ) -> float:
        """验证 Editor 润色后的内容质量.

        Args:
            original_content: 原始内容
            edited_content: Editor 润色后的内容
            review_data: Editor 审查数据（包含评分和建议）

        Returns:
            润色后内容的质量评分
        """
        # 使用 QualityEvaluator 对润色内容进行独立评估
        from agents.quality_evaluator import QualityEvaluator

        evaluator = QualityEvaluator(
            client=self.client,
            cost_tracker=self.cost_tracker,
            default_threshold=self.quality_threshold,
        )

        # 提取章节计划
        chapter_plan = ""
        try:
            plan_data = json.loads(self._chapter_plan_json)
            chapter_plan = plan_data.get("content", str(plan_data))
        except (json.JSONDecodeError, AttributeError):
            chapter_plan = self._chapter_plan_json or ""

        # 评估润色内容
        edited_score = await evaluator.evaluate(
            content=edited_content,
            chapter_plan=chapter_plan,
            threshold=self.quality_threshold,
        )

        # 计算改进幅度
        original_score = float(review_data.get("overall_score", 0))
        improvement = edited_score.overall_score - original_score

        # 记录指标
        self.metrics["editor_improvement"] = improvement
        self.metrics["editor_edit_applied"] = 1 if improvement > 0.5 else 0

        logger.info(
            f"[ReviewLoop] Editor 润色验证：original={original_score:.2f}, "
            f"edited={edited_score.overall_score:.2f}, improvement={improvement:.2f}"
        )

        return edited_score.overall_score

    def _get_reviewer_system_prompt(self) -> str:
        return EDITOR_REVIEW_SYSTEM

    def _get_builder_system_prompt(self) -> str:
        return self._writer_system_prompt

    def _get_reviewer_agent_name(self) -> str:
        return "编辑(审查)"

    def _get_builder_agent_name(self) -> str:
        return "作家(修订)"

    def _get_dimension_names(self) -> Dict[str, str]:
        return {
            "fluency": "语言流畅度",
            "plot_logic": "情节逻辑",
            "character_consistency": "角色一致性",
            "pacing": "节奏把控",
            "satisfaction_design": "爽感设计",
        }

    def _build_reviewer_task_prompt(
        self,
        content: str,
        iteration: int,
        previous_score: float,
        previous_issues: List[str],
        **context,
    ) -> str:
        """构建 Editor 审查任务提示词.

        支持注入前文摘要和时间线锚点，提升跨章节一致性检查能力。
        """
        chapter_number = context.get("chapter_number", 1)
        chapter_title = context.get("chapter_title", "")
        chapter_summary = context.get("chapter_summary", "")
        previous_chapters_summary = context.get("previous_chapters_summary", "")
        timeline_anchor = context.get("timeline_anchor", "")

        # 构建前文章节摘要部分
        if previous_chapters_summary:
            previous_chapters_section = f"""## 前文关键信息（用于跨章节一致性检查）
{previous_chapters_summary}

**特别提醒**：请检查本章是否与前文存在：
1. 情节重复（如相同的解谜方式、相似的对抗模式）
2. 时间线矛盾（如时间推进不合理、时间标记冲突）
3. 角色设定不一致（如能力/身份/性格的突变无铺垫）
4. 事件后果缺失（前文重要事件在本章无后续反映）"""
        else:
            previous_chapters_section = "<!-- 本章为第一章，无前文摘要 -->"

        # 构建时间线锚点部分
        if timeline_anchor:
            timeline_anchor_section = f"""## 时间线锚点
{timeline_anchor}

**检查要点**：本章的时间推进是否合理？是否与前文时间线矛盾？"""
        else:
            timeline_anchor_section = ""

        return EDITOR_REVIEW_TASK.format(
            draft_content=content,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_summary=chapter_summary,
            previous_chapters_section=previous_chapters_section,
            timeline_anchor_section=timeline_anchor_section,
        )

    def _build_revision_prompt(
        self,
        score: float,
        feedback: str,
        issues: str,
        original_content: str,
        report: ChapterQualityReport,
        review_data: Dict[str, Any],
        **context,
    ) -> str:
        """构建 Writer 修订任务提示词."""
        chapter_number = context.get("chapter_number", 1)
        chapter_title = context.get("chapter_title", "")
        chapter_plan_json = context.get("chapter_plan_json", "{}")

        # 使用修订建议构建 suggestions 文本
        suggestions = review_data.get("revision_suggestions", [])
        suggestions_text = (
            "\n".join(
                f"- [{s.get('severity', 'medium')}] {s.get('issue', '')}: {s.get('suggestion', '')}"
                for s in suggestions
            )
            or "（无具体建议）"
        )

        return WRITER_REVISION_TASK.format(
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            score=score,
            suggestions=suggestions_text,
            previous_content=original_content,
            chapter_plan=chapter_plan_json,
        )

    def _validate_revision(self, revised: str, original: str) -> bool:
        """验证修订结果是否有效."""
        if not revised:
            return False
        # 修订后内容应该至少是原内容的 30%
        return len(revised) > len(original) * 0.3

    def _finalize_result(
        self,
        result: ReviewLoopResult,
        final_content: str,
        last_report: Optional[ChapterQualityReport],
    ) -> None:
        """填充最终结果."""
        result.final_content = final_content
        result.final_output = final_content
        result.final_score = last_report.overall_score if last_report else 0
        result.total_iterations = len(result.iterations)
        result.converged = last_report.passed if last_report else False
        result.quality_report = last_report

        # 添加 Editor 效果统计
        editor_stats = self._get_editor_stats(result.iterations)
        result.editor_stats = editor_stats

    def _get_editor_stats(self, iterations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取 Editor 效果统计信息.

        Args:
            iterations: 迭代历史记录

        Returns:
            Editor 统计信息字典
        """
        total_edits = sum(1 for it in iterations if it.get("editor_edit_applied"))
        rejected_edits = sum(1 for it in iterations if it.get("editor_edit_rejected"))

        improvements = [
            it.get("editor_improvement_delta", 0)
            for it in iterations
            if it.get("editor_edit_applied")
        ]
        avg_improvement = sum(improvements) / len(improvements) if improvements else 0.0

        return {
            "total_edits": total_edits,
            "rejected_edits": rejected_edits,
            "avg_improvement": round(avg_improvement, 2),
            "acceptance_rate": (
                round(total_edits / (total_edits + rejected_edits), 2)
                if (total_edits + rejected_edits) > 0
                else 0.0
            ),
        }

    def _get_empty_content(self) -> str:
        """获取空内容."""
        return ""

    def _parse_builder_response(self, response_text: str) -> str:
        """解析 Writer 修订响应（纯文本，不需要 JSON 解析）."""
        return response_text.strip()

    # ══════════════════════════════════════════════════════════════════════════
    # 覆盖方法以支持 Editor 润色和 TeamContext 记录
    # ══════════════════════════════════════════════════════════════════════════

    async def _call_reviewer(
        self,
        content: str,
        iteration: int,
        previous_score: float,
        previous_issues: List[str],
        **context,
    ) -> Dict[str, Any]:
        """调用 Editor 进行审查评分+润色."""
        task_prompt = self._build_reviewer_task_prompt(
            content=content,
            iteration=iteration,
            previous_score=previous_score,
            previous_issues=previous_issues,
            **context,
        )

        try:
            # 非首轮审查时追加追踪指引到 system prompt
            system_prompt = self._get_reviewer_system_prompt()
            if iteration > 1:
                system_prompt += self._get_enhanced_reviewer_system_suffix()

            # 使用动态 max_tokens，让 QwenClient 根据输入 tokens 自动计算合理的输出空间
            # 公式：available = MODEL_CONTEXT_WINDOW - input_tokens - 512
            response = await self.client.chat(
                prompt=task_prompt,
                system=system_prompt,
                temperature=self.config.reviewer_temperature,
                max_tokens=None,  # 动态计算，避免响应被截断
            )

            usage = response["usage"]
            self.cost_tracker.record(
                agent_name=self._get_reviewer_agent_name(),
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )

            return JsonExtractor.extract_object(
                response["content"],
                default={
                    "overall_score": self.quality_threshold,
                    "revision_suggestions": [],
                },
            )

        except Exception as e:
            logger.error(f"[{self._get_loop_name()}] Editor 审查失败: {e}")
            return {"overall_score": self.quality_threshold, "revision_suggestions": []}

    def _record_iteration(
        self,
        result: ReviewLoopResult,
        iteration: int,
        score: float,
        report: ChapterQualityReport,
        review_data: Dict[str, Any],
        **kwargs,
    ) -> None:
        """记录迭代历史，并同步到 TeamContext."""
        # 调用基类实现
        result.add_iteration(
            iteration=iteration,
            score=score,
            passed=report.passed,
            issue_count=len(report.suggestions),
            dimension_scores=report.dimension_scores,
            **kwargs,
        )

        # 记录到 TeamContext
        team_context = getattr(self, "_team_context", None)
        chapter_number = getattr(self, "_chapter_number", 0)

        if team_context:
            review = AgentReview(
                reviewer="编辑",
                target_agent="作家",
                task_desc=f"第{chapter_number}章-第{iteration}轮审查",
                score=score,
                passed=report.passed,
                suggestions=report.suggestions,
                chapter_number=chapter_number,
            )
            team_context.add_review(review)
            team_context.add_iteration_log(
                {
                    "type": "review_loop",
                    "chapter": chapter_number,
                    "iteration": iteration,
                    "score": score,
                    "passed": report.passed,
                    "suggestion_count": len(report.suggestions),
                }
            )

    def _build_issues_text(self, report: ChapterQualityReport, review_data: Dict[str, Any]) -> str:
        """构建问题列表文本，按优先级分组输出.

        支持新旧两种格式：
        - 新格式：detailed_issues（包含位置、具体表现、优先级）
        - 旧格式：revision_suggestions
        """
        lines = []

        # 优先使用新格式的 detailed_issues
        detailed_issues = review_data.get("detailed_issues", [])
        if detailed_issues:
            # 按优先级分组
            by_priority = {
                "reading_experience": [],
                "excitement": [],
                "polish": [],
            }
            for issue in detailed_issues:
                category = issue.get("priority_category", "polish")
                if category in by_priority:
                    by_priority[category].append(issue)
                else:
                    by_priority["polish"].append(issue)

            # 优先级一：影响阅读体验
            if by_priority["reading_experience"]:
                lines.append("【优先级一：影响阅读体验 - 必须修改】")
                for issue in by_priority["reading_experience"]:
                    location = issue.get("location", {})
                    location_str = ""
                    if location:
                        loc_type = {
                            "paragraph": "段落",
                            "scene": "场景",
                            "character": "角色",
                            "global": "整体",
                        }.get(location.get("type", "global"), "整体")
                        location_str = f"[{loc_type}]{location.get('identifier', '')}"
                    else:
                        location_str = "[整体]"

                    lines.append(f"位置{location_str}: {issue.get('description', '')}")
                    manifestation = issue.get("manifestation", [])
                    if manifestation:
                        lines.append(f"  表现: {', '.join(manifestation)}")
                    suggestion = issue.get("suggestion", "")
                    if suggestion:
                        lines.append(f"  建议: {suggestion}")

            # 优先级二：提升精彩度
            if by_priority["excitement"]:
                lines.append("\n【优先级二：提升精彩度 - 建议增强】")
                for issue in by_priority["excitement"]:
                    location = issue.get("location", {})
                    location_str = ""
                    if location:
                        loc_type = {
                            "paragraph": "段落",
                            "scene": "场景",
                            "character": "角色",
                            "global": "整体",
                        }.get(location.get("type", "global"), "整体")
                        location_str = f"[{loc_type}]{location.get('identifier', '')}"
                    else:
                        location_str = "[整体]"

                    lines.append(f"位置{location_str}: {issue.get('description', '')}")
                    suggestion = issue.get("suggestion", "")
                    if suggestion:
                        lines.append(f"  建议: {suggestion}")

            # 优先级三：细节打磨
            if by_priority["polish"]:
                lines.append("\n【优先级三：细节打磨 - 可考虑优化】")
                for issue in by_priority["polish"]:
                    lines.append(f"- {issue.get('description', '')}")
                    suggestion = issue.get("suggestion", "")
                    if suggestion:
                        lines.append(f"  建议: {suggestion}")

            return "\n".join(lines) if lines else "（无具体问题）"

        # 回退到旧格式
        suggestions = review_data.get("revision_suggestions", [])
        if not suggestions:
            return "（无具体问题）"

        for s in suggestions:
            severity = s.get("severity", "medium")
            issue = s.get("issue", "")
            suggestion = s.get("suggestion", "")
            lines.append(f"[{severity.upper()}] {issue}")
            if suggestion:
                lines.append(f"  建议: {suggestion}")

        return "\n".join(lines)

    async def execute_with_editor_content(
        self,
        initial_draft: str,
        chapter_number: int,
        chapter_title: str,
        chapter_summary: str,
        chapter_plan_json: str,
        writer_system_prompt: str,
        team_context: Optional[NovelTeamContext] = None,
        chapter_type: Optional[str] = None,
        previous_chapters_summary: str = "",
        timeline_anchor: str = "",
    ) -> ReviewLoopResult:
        """执行审查循环，支持使用 Editor 润色后的内容.

        这是原始 execute 方法的增强版本，会优先使用 Editor 返回的润色内容。

        Args:
            initial_draft: 初始草稿
            chapter_number: 章节号
            chapter_title: 章节标题
            chapter_summary: 章节摘要
            chapter_plan_json: 章节计划 JSON
            writer_system_prompt: Writer 系统提示词
            team_context: 团队上下文
            chapter_type: 章节类型（可选，支持动态迭代策略）
            previous_chapters_summary: 前文章节摘要（用于跨章节一致性检查）
            timeline_anchor: 时间线锚点信息（用于时间一致性检查）
        """
        self._chapter_number = chapter_number
        self._chapter_title = chapter_title
        self._chapter_summary = chapter_summary
        self._chapter_plan_json = chapter_plan_json
        self._writer_system_prompt = writer_system_prompt
        self._team_context = team_context
        self._previous_chapters_summary = previous_chapters_summary
        self._timeline_anchor = timeline_anchor

        # 根据章节类型创建迭代控制器（支持动态策略）
        from agents.iteration_controller import ChapterType, IterationController

        # 解析章节类型
        if chapter_type:
            try:
                chapter_type_enum = ChapterType(chapter_type.lower())
            except ValueError:
                logger.warning(f"未知的章节类型：{chapter_type}，使用默认类型 NORMAL")
                chapter_type_enum = ChapterType.NORMAL
        else:
            chapter_type_enum = ChapterType.NORMAL

        controller = IterationController(
            chapter_type=chapter_type_enum,
            cost_limit=None,  # 暂不使用成本限制
        )

        logger.info(
            f"[ReviewLoop] 使用动态迭代策略：type={chapter_type_enum.value}, "
            f"max_iterations={controller.max_iterations}, threshold={controller.quality_threshold}"
        )

        current_content = initial_draft
        result = ReviewLoopResult()
        last_report: Optional[ChapterQualityReport] = None

        # 最佳记录追踪 & 停滞检测
        best_score = 0.0
        best_content = initial_draft
        best_report: Optional[ChapterQualityReport] = None
        stagnation_count = 0

        # 初始化增强组件（与基类 execute() 保持同步）
        self._issue_tracker = (
            IssueTracker(match_threshold=self.config.issue_match_threshold)
            if self.config.enable_issue_tracking
            else None
        )
        self._progress_summary = (
            ReviewProgressSummary() if self.config.enable_progress_summary else None
        )
        self._quality_level = QualityLevel.MEDIUM

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"[ReviewLoop] 第 {iteration}/{self.max_iterations} 轮审查")

            # Editor 审查 + 评分 + 润色
            review_data = await self._call_reviewer(
                content=current_content,
                iteration=iteration,
                previous_score=0,
                previous_issues=[],
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                chapter_summary=chapter_summary,
                previous_chapters_summary=previous_chapters_summary,
                timeline_anchor=timeline_anchor,
            )

            score = float(review_data.get("overall_score", 0))
            # 防止 overall_score 缺失时降为 0，使用维度平均分降级
            if score == 0 and "dimension_scores" in review_data:
                dim = review_data["dimension_scores"]
                if dim and isinstance(dim, dict):
                    try:
                        score = sum(float(v) for v in dim.values()) / len(dim)
                    except (ValueError, TypeError):
                        pass
            review_data.get("revision_suggestions", [])
            edited_content = review_data.get("edited_content", "")

            # 如果 Editor 返回了润色后的内容，进行质量验证
            if edited_content:
                # 验证润色内容质量
                edited_score = await self._validate_edited_content(
                    original_content=current_content,
                    edited_content=edited_content,
                    review_data=review_data,
                )

                # 只有润色后质量更高才使用（允许 0.5 分的误差）
                if edited_score > score + 0.5:
                    current_content = edited_content
                    self.metrics["editor_edit_applied"] = 1
                    self.metrics["editor_improvement_delta"] = edited_score - score
                    logger.info(
                        f"[ReviewLoop] 应用 Editor 润色：quality improved from {score:.2f} to {edited_score:.2f}"
                    )
                else:
                    # 保留原始内容
                    self.metrics["editor_edit_rejected"] = 1
                    self.metrics["editor_reason"] = f"质量未提升：{edited_score:.2f} vs {score:.2f}"
                    logger.info(
                        f"[ReviewLoop] 拒绝 Editor 润色：edited={edited_score:.2f} <= original={score:.2f}"
                    )

            # 构造质量报告
            last_report = self._create_quality_report(review_data)
            # 使用报告中经过降级处理的分数，确保 score 与 last_report 一致
            if score == 0 and last_report.overall_score > 0:
                score = last_report.overall_score

            # 更新问题跟踪和进度摘要（与基类 execute() 保持同步）
            self._quality_level = self._determine_quality_level(score)
            if self._issue_tracker:
                self._issue_tracker.update_round(iteration, last_report, review_data)
            if self._progress_summary:
                self._progress_summary.update(iteration, score, self._issue_tracker)

            # 记录迭代
            self._record_iteration(
                result,
                iteration,
                score,
                last_report,
                review_data,
                quality_level=self._quality_level.value,
                issues_resolved=(
                    len(self._issue_tracker.get_resolved_this_round()) if self._issue_tracker else 0
                ),
                issues_new=(
                    len(self._issue_tracker.get_new_this_round()) if self._issue_tracker else 0
                ),
                issues_recurring=(
                    len(self._issue_tracker.get_recurring_issues()) if self._issue_tracker else 0
                ),
            )

            prev_score = result.iterations[-2]["score"] if len(result.iterations) > 1 else 0
            logger.info(
                f"[ReviewLoop] score={score:.1f}"
                + (f" (prev={prev_score:.1f})" if prev_score else "")
                + f", passed={last_report.passed}"
            )

            # 更新最佳记录
            if score > best_score:
                best_score = score
                best_content = current_content
                best_report = last_report

            # 判断是否继续迭代
            if not controller.should_continue(score, iteration):
                break

            # 评分停滞检测：连续 2 轮改善 < 0.3 则提前终止
            if iteration > 1 and prev_score > 0:
                improvement = score - prev_score
                if improvement < 0.3:
                    stagnation_count += 1
                else:
                    stagnation_count = 0

                if stagnation_count >= 2:
                    logger.warning(
                        f"[ReviewLoop] 评分连续{stagnation_count}轮无明显改善"
                        f"(score={score:.1f})，提前终止"
                    )
                    break

            # Writer 修订
            logger.info("[ReviewLoop] 质量未达标，请求 Writer 修订...")
            feedback = self._build_feedback_text(last_report, review_data)
            issues = self._build_issues_text(last_report, review_data)

            revised = await self._call_builder(
                score=score,
                feedback=feedback,
                issues=issues,
                original_content=current_content,
                report=last_report,
                review_data=review_data,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                chapter_plan_json=chapter_plan_json,
            )

            if revised and len(revised) > len(current_content) * 0.3:
                current_content = revised
                logger.info(f"[ReviewLoop] Writer 修订完成，{len(revised)} 字符")
            else:
                logger.warning("[ReviewLoop] Writer 修订失败")
                break

        # 组装最终结果（使用最佳分数对应的内容）
        final_content = best_content if best_score > 0 else current_content
        final_report = best_report if best_report else last_report
        self._finalize_result(result, final_content, final_report)

        # 短期反思钩子
        if hasattr(self, "_run_reflection_hook"):
            await self._run_reflection_hook(
                result,
                {
                    "chapter_number": chapter_number,
                    "chapter_type": chapter_type or "normal",
                },
            )

        return result
