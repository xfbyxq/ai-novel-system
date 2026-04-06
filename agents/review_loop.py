"""审查反馈循环 - Writer 与 Editor 间的质量驱动迭代."""

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

你的工作包含两个部分：
1. 对内容进行多维度精确评分（5个维度）
2. 润色并输出修改后的完整内容

【精确评分维度】（1-10分）：
- accuracy（准确度）：情节因果关系是否清晰严密？角色行为动机是否合理？事件发展是否符合已建立规则？有无逻辑漏洞？
- vividness（画面感）：场景描写是否生动具体？是否运用了多感官细节（视觉/听觉/触觉/嗅觉）？环境氛围与情绪是否融合？读者能否"看到"画面？
- pacing（节奏感）：叙事张弛是否有度？紧张与舒缓是否交替得当？详略安排是否合理？场景切换是否流畅？情绪曲线是否有起伏？
- setting_consistency（设定一致性）：世界观是否前后一致？时间线是否清晰？力量体系是否遵循规则？
- immersion（代入感）：角色内心活动是否真实可信？情感铺垫是否到位？读者是否能产生共鸣？对话是否推动情感发展？

【评分锚点示例】：
- 6.0分：基本合格，逻辑无硬伤，但描写平淡、节奏平板、情感苍白
- 7.0分：合格，逻辑通顺，有一定画面感，节奏基本流畅，情感有铺垫
- 7.5分：良好，因果关系清晰，场景描写具体生动，详略安排合理，角色情感真实
- 8.0分：优秀，逻辑严密，画面跃然纸上，节奏张弛有度，读者有强烈代入感
- 8.5分：出色，情节因果精巧，感官描写丰富立体，情绪曲线起伏有力，读者完全沉浸

【问题定位要求】：
描述问题时要明确位置（如：第3段、开篇场景、结尾转折），便于定位修改。

【问题描述格式】：
每条问题包含4个字段：
1. location: 问题位置（如：第3段、开篇场景、结尾转折）
2. description: 问题描述（精炼概括，20字以内）
3. severity: 严重程度（high/medium/low）
4. suggestion: 修订建议（具体可操作）"""

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
    "overall_score": 综合评分(1-10浮点数)，参考评分锚点,
    "dimension_scores": {{
        "accuracy": 分数,
        "vividness": 分数,
        "pacing": 分数,
        "setting_consistency": 分数,
        "immersion": 分数
    }},
    "overall_assessment": "整体评价（1-2句话概括章节质量）",
    "issues": [
        {{
            "location": "问题位置（如第3段、开篇场景、结尾转折）",
            "description": "问题描述（20字以内）",
            "severity": "high/medium/low",
            "suggestion": "修订建议"
        }}
    ],
    "edited_content": "润色后的完整章节内容"
}}"""

WRITER_REVISION_TASK = """你之前写的第{chapter_number}章（{chapter_title}）需要修订。

**编辑评分**：{score}/10（目标：≥7.5）

**核心问题**（按严重程度排序）：
{suggestions}

**修订原则**：
1. 优先修复 [HIGH] 标记的问题
2. 保持原文风格，不要大幅改写
3. 确保修订后情节衔接自然

你的上一版内容：
{previous_content}

章节计划：
{chapter_plan}

请直接输出修订后的完整章节内容."""


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
        graph_conflicts_context: str = "",
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
            graph_conflicts_context: 图数据库冲突信息（用于连贯性检查）

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
        self._graph_conflicts_context = graph_conflicts_context

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
            graph_conflicts_context=graph_conflicts_context,
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
            "accuracy": "准确度",
            "vividness": "画面感",
            "pacing": "节奏感",
            "setting_consistency": "设定一致性",
            "immersion": "代入感",
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

        支持注入前文摘要、时间线锚点和图数据库冲突信息，提升跨章节一致性检查能力。
        """
        chapter_number = context.get("chapter_number", 1)
        chapter_title = context.get("chapter_title", "")
        chapter_summary = context.get("chapter_summary", "")
        previous_chapters_summary = context.get("previous_chapters_summary", "")
        timeline_anchor = context.get("timeline_anchor", "")
        graph_conflicts_context = context.get("graph_conflicts_context", "")

        # 构建前文章节摘要部分
        if previous_chapters_summary:
            previous_chapters_section = f"""## 前文关键信息（用于跨章节一致性检查）
{previous_chapters_summary}

**【关键】章节边界检查**：
- 本章开篇是否自然承接上一章结尾的场景/状态？
- 是否存在"跳跃"或"重复"？
- 本章情节是否有实质性推进？

**其他检查要点**：
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

        # 构建图数据库冲突信息部分
        if graph_conflicts_context:
            graph_conflicts_section = f"""## 图数据库冲突警告（自动检测）
{graph_conflicts_context}

**检查要点**：以上是系统自动检测到的潜在连贯性问题，请在评分时重点考虑。"""
        else:
            graph_conflicts_section = ""

        # 构建完整的任务提示词
        task_prompt = EDITOR_REVIEW_TASK.format(
            draft_content=content,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_summary=chapter_summary,
            previous_chapters_section=previous_chapters_section,
            timeline_anchor_section=timeline_anchor_section,
        )

        # 追加图数据库冲突信息
        if graph_conflicts_section:
            task_prompt = task_prompt.replace(
                "请以JSON格式输出", f"{graph_conflicts_section}\n\n请以JSON格式输出"
            )

        return task_prompt

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
        # 统计总迭代次数和最终收敛状态
        total_iterations = len(iterations)
        converged = any(it.get("passed", False) for it in iterations)

        return {
            "total_iterations": total_iterations,
            "converged": converged,
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
        """构建问题列表文本，按严重程度分组输出.

        支持新旧两种格式：
        - 新格式：issues（包含 location、description、severity、suggestion）
        - 旧格式：revision_suggestions 或 detailed_issues
        """
        lines = []

        # 优先使用新格式的 issues
        issues = review_data.get("issues", [])
        if issues:
            # 按严重程度分组
            high_issues = [i for i in issues if i.get("severity") == "high"]
            medium_issues = [i for i in issues if i.get("severity") == "medium"]
            low_issues = [i for i in issues if i.get("severity") == "low"]

            # 高优先级问题
            if high_issues:
                lines.append("[HIGH] 必须修改：")
                for issue in high_issues:
                    location = issue.get("location", "")
                    desc = issue.get("description", "")
                    suggestion = issue.get("suggestion", "")
                    lines.append(f"  - {location}：{desc}")
                    if suggestion:
                        lines.append(f"    建议：{suggestion}")

            # 中优先级问题
            if medium_issues:
                lines.append("\n[MEDIUM] 建议修改：")
                for issue in medium_issues:
                    location = issue.get("location", "")
                    desc = issue.get("description", "")
                    suggestion = issue.get("suggestion", "")
                    lines.append(f"  - {location}：{desc}")
                    if suggestion:
                        lines.append(f"    建议：{suggestion}")

            # 低优先级问题
            if low_issues:
                lines.append("\n[LOW] 可考虑优化：")
                for issue in low_issues:
                    location = issue.get("location", "")
                    desc = issue.get("description", "")
                    lines.append(f"  - {location}：{desc}")

            return "\n".join(lines) if lines else "（无具体问题）"

        # 回退到旧格式 detailed_issues（兼容）
        detailed_issues = review_data.get("detailed_issues", [])
        if detailed_issues:
            for issue in detailed_issues:
                severity = issue.get("severity", "medium").upper()
                location = issue.get("location", {})
                if isinstance(location, dict):
                    location_str = location.get("identifier", "")
                else:
                    location_str = str(location)
                desc = issue.get("description", "")
                suggestion = issue.get("suggestion", "")
                lines.append(f"[{severity}] {location_str}：{desc}")
                if suggestion:
                    lines.append(f"  建议：{suggestion}")
            return "\n".join(lines) if lines else "（无具体问题）"

        # 回退到旧格式 revision_suggestions
        suggestions = review_data.get("revision_suggestions", [])
        if not suggestions:
            return "（无具体问题）"

        for s in suggestions:
            severity = s.get("severity", "medium").upper()
            issue_text = s.get("issue", "")
            suggestion = s.get("suggestion", "")
            lines.append(f"[{severity}] {issue_text}")
            if suggestion:
                lines.append(f"  建议：{suggestion}")

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

            # 直接信任 Editor 的润色结果，不进行独立验证
            # Editor 的评分已经反映了内容质量，额外验证是冗余的 LLM 调用
            if edited_content:
                current_content = edited_content
                logger.info(f"[ReviewLoop] Editor 润色内容已采纳（score={score:.2f}）")

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

            # 快速通过逻辑：score >= 7.5 且无 high severity 问题 → 直接采纳 Editor 润色内容
            issues = review_data.get("issues", [])
            has_high_severity = any(i.get("severity") == "high" for i in issues)
            if score >= 7.5 and not has_high_severity:
                logger.info(
                    f"[ReviewLoop] 快速通过：score={score:.1f}>=7.5 且无high问题，" "跳过Writer修订"
                )
                break

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
