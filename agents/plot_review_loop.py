"""大纲审查反馈循环 - 确保情节架构的完整性和吸引力

通过 Architect-Reviewer 循环迭代，确保大纲具有：
- 结构完整性（清晰的起承转合）
- 节奏把控（张弛有度）
- 冲突张力（足够的戏剧冲突）
- 角色利用度（充分发挥角色作用）
- 伏笔设计（合理的铺垫和回收）
"""

import json
from typing import Any, Dict, List, Optional

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient

from agents.base import (
    BaseReviewLoopHandler,
    JsonExtractor,
    PlotQualityReport,
    PlotReviewResult,
    ReviewLoopConfig,
)


# ── 大纲审查专用提示词 ──────────────────────────────────────────

PLOT_REVIEWER_SYSTEM = """你是一位资深的网络小说情节架构评审专家，专注于大纲设计的完整性、节奏和吸引力。

你需要从以下维度严格评估大纲设计：

1. **结构完整性** (structure)：
   - 是否有清晰的开头、发展、高潮、结局？
   - 各卷之间是否有递进关系？
   - 主线是否贯穿始终？

2. **节奏把控** (pacing)：
   - 情节推进是否张弛有度？
   - 高潮点分布是否合理？
   - 是否有足够的"爽点"和"低谷"交替？

3. **冲突张力** (conflict)：
   - 核心冲突是否足够吸引人？
   - 每卷是否有独立的冲突？
   - 敌对势力是否有威胁感？

4. **角色利用度** (character_usage)：
   - 主要角色是否都有戏份？
   - 角色成长是否与情节紧密结合？
   - 配角和反派是否有发挥空间？

5. **伏笔设计** (foreshadowing)：
   - 是否有合理的伏笔铺垫？
   - 关键转折是否有预兆？
   - 是否有未来可回收的悬念？

6. **爽感节奏设计** (satisfaction_rhythm)：
   - 黄金三章：第一卷前三章是否有明确的强钩子 → 金手指首亮 → 首个小高潮？
   - 欲扬先抑分布：每卷是否有完整的"抑→扬"循环？压制期是否控制在 3 章以内？
   - 升级节奏：主角的实力/地位提升是否有明确的可感知里程碑？
   - 卡章设计：每卷结尾是否有强悬念驱动读者继续？

7. **主线剧情深度** (main_plot_depth)：
   - 核心冲突是否有多个层次（表面→深层→哲学）？
   - 主角动机是否纯粹强烈，有明确心理根源？
   - 反派/阻碍力量是否有合理动机和强大实力？
   - 冲突升级路径是否清晰（个人→组织→世界）？
   - 情感弧光是否有起伏变化？
   - 主题表达是否贯穿始终？
   - 关键揭示点是否精心布置？
   - 主角成长轨迹是否清晰有代价？

【重要】评分原则：
- 你必须给出精确的评分，不要给出"安全"的中间分数
- 如果大纲结构完整且有吸引力，应给 8.0 以上
- 如果有明显问题未解决，应给 7.0 以下
- 评分应该反映真实质量，而不是折中

评分标准：
- 9-10 分：卓越，结构精妙、节奏完美、引人入胜
- 8-9 分：优秀，结构完整、节奏紧凑、冲突强烈
- 7-8 分：良好，基本完整但有改进空间
- 6-7 分：及格，存在明显问题需要修改
- 6 分以下：不合格，需要大幅重做"""

PLOT_REVIEWER_TASK = """请对以下情节大纲进行全面质量评估。

{iteration_context}

世界观设定：
{world_setting}

角色设定：
{characters}

情节大纲：
{plot_outline}

请以 JSON 格式输出评估结果（不要输出其他内容）：
{{
    "overall_score": 综合评分 (1-10 浮点数，请给出精确分数如 7.3、8.1 等，不要总是给 7.0 或 7.5 这样的整数),
    "dimension_scores": {{
        "structure": 结构完整性分数，
        "pacing": 节奏把控分数，
        "conflict": 冲突张力分数，
        "character_usage": 角色利用度分数，
        "foreshadowing": 伏笔设计分数，
        "satisfaction_rhythm": 爽感节奏设计分数，
        "main_plot_depth": 主线剧情深度分数
    }},
    "improvement_assessment": {{
        "issues_resolved": ["已解决的问题"],
        "issues_remaining": ["仍存在的问题"],
        "new_issues": ["新发现的问题"],
        "improvement_score": 改进程度分数 (1-10，仅在非首轮审查时填写)
    }},
    "structure_analysis": {{
        "opening_hook": "开篇吸引力评价",
        "climax_strength": "高潮张力评价",
        "ending_satisfaction": "结局满意度评价",
        "volume_balance": "各卷平衡性评价",
        "golden_three_chapters": "前三章黄金钩子评价",
        "suppress_release_distribution": "欲扬先抑分布评价",
        "upgrade_pacing": "升级节奏评价"
    }},
    "main_plot_depth_analysis": {{
        "conflict_layers": "核心冲突层次评价（表面/深层/哲学三层是否完整）",
        "protagonist_motivation": "主角动机评价（是否纯粹强烈、有心理根源）",
        "antagonist_strength": "反派/阻碍力量评价（动机合理性、实力威胁）",
        "escalation_path": "冲突升级路径评价（个人→组织→世界是否清晰）",
        "emotional_arc": "情感弧光评价（是否有起伏变化）",
        "theme_expression": "主题表达评价（是否贯穿始终）",
        "key_revelations": "关键揭示点评价（布置是否精心、影响是否重大）",
        "character_growth": "主角成长轨迹评价（是否清晰、有代价有收获）",
        "depth_issues": ["主线深度方面的问题"]
    }},
    "volume_assessments": [
        {{
            "volume_num": 卷号，
            "strengths": ["优点"],
            "weaknesses": ["问题"],
            "pacing_issue": "节奏问题（如有）"
        }}
    ],
    "unused_elements": {{
        "characters": ["未充分利用的角色"],
        "world_settings": ["未利用的世界观元素"],
        "potential_conflicts": ["潜在但未使用的冲突"]
    }},
    "critical_issues": [
        {{"area": "问题领域", "issue": "具体问题", "severity": "high/medium/low", "suggestion": "改进建议"}}
    ],
    "missing_elements": ["缺失的重要情节元素"],
    "summary": "整体评价（50 字以内）"
}}"""

PLOT_REVISION_TASK = """你之前设计的情节大纲经过专家评审，需要优化。

评审评分：{score}/10

评审反馈：
{feedback}

发现的问题：
{issues}

结构分析：
{structure_analysis}

未充分利用的元素：
{unused_elements}

原情节大纲：
{original_plot}

世界观设定（供参考）：
{world_setting}

角色设定（供参考）：
{characters}

请根据评审意见优化情节大纲，重点解决以下问题：
1. 完善结构，确保有清晰的起承转合
2. 优化节奏，增加高潮点和悬念
3. 强化冲突，提升情节张力
4. 充分利用角色和世界观设定
5. 增加伏笔和悬念

请以JSON格式输出优化后的完整情节大纲：
{{
    "structure_type": "叙事结构类型",
    "main_plot": {{
        "core_conflict": "核心冲突（具体、有张力）",
        "resolution_path": "解决路径（有波折、不直线）",
        "theme": "主题",
        "central_question": "故事的核心问题（读者最想知道的答案）"
    }},
    "volumes": [
        {{
            "volume_num": 卷号,
            "title": "卷名",
            "summary": "本卷概要（100字）",
            "chapters_range": [起始章, 结束章],
            "volume_conflict": "本卷主要冲突",
            "key_events": ["关键事件1", "关键事件2", "关键事件3"],
            "power_level": "主角当前实力",
            "emotional_arc": "情感线发展",
            "cliffhanger": "本卷结尾悬念"
        }}
    ],
    "sub_plots": [
        {{"name": "支线名", "description": "描述", "involved_characters": ["角色名"], "resolution_volume": 解决卷号}}
    ],
    "key_turning_points": [
        {{"chapter": 章节号, "event": "转折事件", "impact": "对主角/剧情的影响", "foreshadowing_chapter": 伏笔章节号}}
    ],
    "foreshadowing_map": [
        {{"setup_chapter": 埋设章节, "payoff_chapter": 回收章节, "content": "伏笔内容"}}
    ],
    "climax_chapter": 全书最大高潮章节号,
    "hooks_and_mysteries": ["悬念和谜团（保持读者兴趣）"]
}}"""


class PlotReviewHandler(
    BaseReviewLoopHandler[Dict[str, Any], PlotReviewResult, PlotQualityReport]
):
    """情节大纲审查循环处理器

    流程：
    1. Architect 生成/修订大纲
    2. Reviewer 多维度评估 + 结构分析
    3. 如果 score < threshold 且未达上限 → 反馈给 Architect → 回到 1
    4. 返回最终大纲 + 迭代历史
    """

    def __init__(
        self,
        client: QwenClient,
        cost_tracker: CostTracker,
        quality_threshold: float = 7.0,
        max_iterations: int = 2,
    ):
        """初始化情节大纲审查处理器

        Args:
            client: LLM 客户端
            cost_tracker: 成本追踪器
            quality_threshold: 质量阈值
            max_iterations: 最大迭代次数
        """
        super().__init__(
            client=client,
            cost_tracker=cost_tracker,
            quality_threshold=quality_threshold,
            max_iterations=max_iterations,
        )

    async def execute(
        self,
        initial_plot_outline: Dict[str, Any],
        world_setting: Dict[str, Any],
        characters: List[Dict[str, Any]],
    ) -> PlotReviewResult:
        """执行情节大纲审查循环

        Args:
            initial_plot_outline: 初始情节大纲
            world_setting: 世界观设定
            characters: 角色列表

        Returns:
            PlotReviewResult
        """
        return await super().execute(
            initial_content=initial_plot_outline,
            world_setting=world_setting,
            characters=characters,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # 实现抽象方法
    # ══════════════════════════════════════════════════════════════════════════

    def _get_loop_name(self) -> str:
        return "PlotReview"

    def _create_result(self) -> PlotReviewResult:
        return PlotReviewResult()

    def _create_quality_report(self, review_data: Dict[str, Any]) -> PlotQualityReport:
        return PlotQualityReport.from_llm_response(
            review_data,
            quality_threshold=self.quality_threshold,
        )

    def _get_reviewer_system_prompt(self) -> str:
        return PLOT_REVIEWER_SYSTEM

    def _get_builder_system_prompt(self) -> str:
        from llm.prompt_manager import PromptManager
        return PromptManager.PLOT_ARCHITECT_SYSTEM

    def _get_reviewer_agent_name(self) -> str:
        return "大纲审查员"

    def _get_builder_agent_name(self) -> str:
        return "情节架构师(修订)"

    def _get_dimension_names(self) -> Dict[str, str]:
        return {
            "structure": "结构完整性",
            "pacing": "节奏把控",
            "conflict": "冲突张力",
            "character_usage": "角色利用度",
            "foreshadowing": "伏笔设计",
            "satisfaction_rhythm": "爽感节奏设计",
        }

    def _build_reviewer_task_prompt(
        self,
        content: Dict[str, Any],
        iteration: int,
        previous_score: float,
        previous_issues: List[str],
        **context,
    ) -> str:
        """构建 Reviewer 任务提示词"""
        world_setting = context.get("world_setting", {})
        characters = context.get("characters", [])

        iteration_context = self._build_iteration_context(
            iteration, previous_score, previous_issues
        )

        return PLOT_REVIEWER_TASK.format(
            iteration_context=iteration_context,
            world_setting=self.to_json(world_setting, max_length=2000),
            characters=self.to_json(characters, max_length=2000),
            plot_outline=self.to_json(content),
        )

    def _build_revision_prompt(
        self,
        score: float,
        feedback: str,
        issues: str,
        original_content: Dict[str, Any],
        report: PlotQualityReport,
        review_data: Dict[str, Any],
        **context,
    ) -> str:
        """构建修订任务提示词"""
        world_setting = context.get("world_setting", {})
        characters = context.get("characters", [])

        structure_analysis = review_data.get("structure_analysis", {})
        structure_text = (
            self.to_json(structure_analysis)
            if structure_analysis
            else "（无）"
        )

        unused_elements = review_data.get("unused_elements", {})
        unused_text = (
            self.to_json(unused_elements)
            if unused_elements
            else "（无）"
        )

        return PLOT_REVISION_TASK.format(
            score=f"{score:.1f}",
            feedback=feedback,
            issues=issues,
            structure_analysis=structure_text,
            unused_elements=unused_text,
            original_plot=self.to_json(original_content),
            world_setting=self.to_json(world_setting, max_length=1500),
            characters=self.to_json(characters, max_length=1500),
        )

    def _validate_revision(
        self, revised: Dict[str, Any], original: Dict[str, Any]
    ) -> bool:
        """验证修订结果是否有效"""
        if not revised:
            return False
        if not isinstance(revised, dict):
            return False
        # 检查是否有关键字段
        return bool(revised.get("volumes") or revised.get("main_plot"))

    def _finalize_result(
        self,
        result: PlotReviewResult,
        final_content: Dict[str, Any],
        last_report: Optional[PlotQualityReport],
    ) -> None:
        """填充最终结果"""
        result.final_plot_outline = final_content
        result.final_output = final_content
        result.final_score = last_report.overall_score if last_report else 0
        result.total_iterations = len(result.iterations)
        result.converged = last_report.passed if last_report else False
        result.quality_report = last_report

    def _get_empty_content(self) -> Dict[str, Any]:
        """获取空内容"""
        return {}

    def _parse_builder_response(self, response_text: str) -> Dict[str, Any]:
        """解析 Builder 响应"""
        result = JsonExtractor.extract_json(response_text, default={})

        # 如果返回的是数组（卷列表），包装为标准格式
        if isinstance(result, list):
            return {"volumes": result, "structure_type": "multi_volume"}

        return result if isinstance(result, dict) else {}

    # ══════════════════════════════════════════════════════════════════════════
    # 覆盖钩子方法以添加大纲评估细节
    # ══════════════════════════════════════════════════════════════════════════

    def _build_issues_text(
        self, report: PlotQualityReport, review_data: Dict[str, Any]
    ) -> str:
        """构建问题列表文本，包含各卷问题"""
        lines = []

        # 添加严重问题
        for issue in report.issues:
            area = issue.get("area", "")
            desc = issue.get("issue", "")
            severity = issue.get("severity", "medium")
            suggestion = issue.get("suggestion", "")

            lines.append(f"[{severity.upper()}] {area}: {desc}")
            if suggestion:
                lines.append(f"  建议: {suggestion}")

        # 添加缺失元素
        missing = review_data.get("missing_elements", [])
        if missing:
            lines.append("\n缺失的重要元素：")
            for m in missing:
                lines.append(f"  - {m}")

        # 添加各卷问题
        volume_assessments = review_data.get("volume_assessments", [])
        for va in volume_assessments:
            weaknesses = va.get("weaknesses", [])
            if weaknesses:
                lines.append(f"\n第{va.get('volume_num', '?')}卷问题：")
                for w in weaknesses:
                    lines.append(f"  - {w}")

        return "\n".join(lines) if lines else "（无具体问题）"

    def _collect_issues_for_next_round(
        self, report: PlotQualityReport, review_data: Dict[str, Any]
    ) -> List[str]:
        """收集问题用于下一轮审查"""
        issues = []

        # 添加严重问题
        for issue in report.issues:
            area = issue.get("area", "")
            desc = issue.get("issue", "")
            issues.append(f"{area}: {desc}" if area else desc)

        # 添加缺失元素
        missing = review_data.get("missing_elements", [])
        for m in missing:
            issues.append(f"缺失: {m}")

        # 添加各卷问题
        volume_assessments = review_data.get("volume_assessments", [])
        for va in volume_assessments:
            vol_num = va.get("volume_num", "?")
            for w in va.get("weaknesses", []):
                issues.append(f"第{vol_num}卷: {w}")

        return issues
