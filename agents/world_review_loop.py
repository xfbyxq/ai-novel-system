"""世界观审查反馈循环 - 确保世界观设计的深度和一致性

通过 Builder-Reviewer 循环迭代，确保世界观具有：
- 内在一致性（设定自洽）
- 深度与广度（足够的细节）
- 独特性与创新
- 可扩展性（支撑长期连载）
- 力量体系完整性
"""

import json
from typing import Any, Dict, List, Optional

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient

from agents.base import (
    BaseReviewLoopHandler,
    JsonExtractor,
    ReviewLoopConfig,
    WorldQualityReport,
    WorldReviewResult,
)


# ── 世界观审查专用提示词 ──────────────────────────────────────────

WORLD_REVIEWER_SYSTEM = """你是一位资深的网络小说世界观评审专家，专注于世界观设计的深度、一致性和创新性。

你需要从以下维度严格评估世界观设计：

1. **内在一致性** (consistency)：
   - 各个设定之间是否自洽？
   - 力量体系与世界规则是否矛盾？
   - 历史事件与当前状态是否匹配？

2. **深度与广度** (depth_breadth)：
   - 力量体系是否有足够的层次和细节？
   - 地理设定是否丰富且有特色？
   - 势力组织是否有清晰的架构和关系？

3. **独特性** (uniqueness)：
   - 是否有独特的世界观元素？
   - 是否避免了常见套路和模板化？
   - 创新点是否足以吸引读者？

4. **可扩展性** (expandability)：
   - 世界观是否有足够的发展空间？
   - 是否预留了未探索的区域和势力？
   - 力量体系是否有上升空间？

5. **力量体系完整性** (power_system)：
   - 等级划分是否清晰合理？
   - 升级机制是否有逻辑？
   - 是否有明确的能力上限和限制？

【重要】评分原则：
- 你必须给出精确的评分，不要给出"安全"的中间分数
- 如果世界观有明显创新和完善的细节，应给 8.0 以上
- 如果有明显问题未解决，应给 7.0 以下
- 评分应该反映真实质量，而不是折中

评分标准：
- 9-10分：卓越，世界观独特、完整、令人印象深刻
- 8-9分：优秀，世界观完整、一致、有创新
- 7-8分：良好，基本完整但有改进空间
- 6-7分：及格，存在明显问题需要修改
- 6分以下：不合格，需要大幅重做"""

WORLD_REVIEWER_TASK = """请对以下世界观设计进行全面质量评估。

{iteration_context}

题材信息：
{topic_analysis}

世界观设定：
{world_setting}

请以JSON格式输出评估结果（不要输出其他内容）：
{{
    "overall_score": 综合评分(1-10浮点数，请给出精确分数如7.3、8.1等，不要总是给7.0或7.5这样的整数),
    "dimension_scores": {{
        "consistency": 内在一致性分数,
        "depth_breadth": 深度与广度分数,
        "uniqueness": 独特性分数,
        "expandability": 可扩展性分数,
        "power_system": 力量体系完整性分数
    }},
    "improvement_assessment": {{
        "issues_resolved": ["已解决的问题"],
        "issues_remaining": ["仍存在的问题"],
        "new_issues": ["新发现的问题"],
        "improvement_score": 改进程度分数(1-10，仅在非首轮审查时填写)
    }},
    "consistency_analysis": {{
        "contradictions": ["发现的矛盾点"],
        "logic_gaps": ["逻辑漏洞"],
        "timeline_issues": ["时间线问题"]
    }},
    "strengths": ["世界观的优点"],
    "weaknesses": ["世界观的问题"],
    "missing_elements": ["缺失的重要元素"],
    "critical_issues": [
        {{"area": "问题领域", "issue": "具体问题", "severity": "high/medium/low", "suggestion": "改进建议"}}
    ],
    "summary": "整体评价（50字以内）"
}}"""

WORLD_REVISION_TASK = """你之前设计的世界观经过专家评审，需要优化。

评审评分：{score}/10

评审反馈：
{feedback}

发现的问题：
{issues}

一致性分析：
{consistency_analysis}

原世界观设定：
{original_world}

题材信息（供参考）：
{topic_analysis}

请根据评审意见优化世界观设计，重点解决以下问题：
1. 修复逻辑矛盾和设定冲突
2. 补充缺失的重要元素
3. 增加世界观的深度和独特性
4. 完善力量体系的细节

请以JSON格式输出优化后的完整世界观：
{{
    "world_name": "世界名称",
    "world_type": "世界类型",
    "core_concept": "核心概念（一句话描述世界的独特之处）",
    "power_system": {{
        "name": "体系名称",
        "core_principle": "核心原理（修炼/升级的底层逻辑）",
        "levels": [
            {{"level": 1, "name": "等级名", "description": "描述", "typical_abilities": ["能力"], "breakthrough_condition": "突破条件"}}
        ],
        "special_abilities": ["特殊能力类型"],
        "limitations": ["体系限制和代价"],
        "unique_elements": ["独特元素"]
    }},
    "geography": {{
        "overview": "地理概述",
        "major_regions": [
            {{"name": "地名", "description": "描述", "importance": "重要性", "unique_feature": "独特特征", "controlling_force": "控制势力"}}
        ],
        "unexplored_areas": ["未探索区域（为后续剧情预留）"]
    }},
    "factions": [
        {{"name": "势力名", "type": "类型", "description": "描述", "power_level": "实力等级", "internal_conflicts": "内部矛盾", "external_relations": "外部关系"}}
    ],
    "rules": ["世界规则（不可违背的底层法则）"],
    "timeline": [
        {{"era": "时代", "event": "事件", "impact": "影响", "related_mysteries": "相关谜团"}}
    ],
    "special_elements": ["特殊元素"],
    "mysteries": ["未解之谜（可作为后续剧情钩子）"],
    "taboos": ["禁忌或危险区域"]
}}"""


class WorldReviewHandler(
    BaseReviewLoopHandler[Dict[str, Any], WorldReviewResult, WorldQualityReport]
):
    """世界观设计审查循环处理器

    流程：
    1. Builder 生成/修订世界观
    2. Reviewer 多维度评估 + 一致性检查
    3. 如果 score < threshold 且未达上限 → 反馈给 Builder → 回到 1
    4. 返回最终世界观 + 迭代历史
    """

    def __init__(
        self,
        client: QwenClient,
        cost_tracker: CostTracker,
        quality_threshold: float = 7.0,
        max_iterations: int = 2,
    ):
        """初始化世界观审查处理器

        Args:
            client: LLM 客户端
            cost_tracker: 成本追踪器
            quality_threshold: 质量阈值（默认7.0）
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
        initial_world_setting: Dict[str, Any],
        topic_analysis: Dict[str, Any],
    ) -> WorldReviewResult:
        """执行世界观设计审查循环

        Args:
            initial_world_setting: 初始世界观设定
            topic_analysis: 主题分析结果

        Returns:
            WorldReviewResult
        """
        # 调用基类的模板方法，传递上下文参数
        return await super().execute(
            initial_content=initial_world_setting,
            topic_analysis=topic_analysis,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # 实现抽象方法
    # ══════════════════════════════════════════════════════════════════════════

    def _get_loop_name(self) -> str:
        return "WorldReview"

    def _create_result(self) -> WorldReviewResult:
        return WorldReviewResult()

    def _create_quality_report(self, review_data: Dict[str, Any]) -> WorldQualityReport:
        return WorldQualityReport.from_llm_response(
            review_data,
            quality_threshold=self.quality_threshold,
        )

    def _get_reviewer_system_prompt(self) -> str:
        return WORLD_REVIEWER_SYSTEM

    def _get_builder_system_prompt(self) -> str:
        from llm.prompt_manager import PromptManager
        return PromptManager.WORLD_BUILDER_SYSTEM

    def _get_reviewer_agent_name(self) -> str:
        return "世界观审查员"

    def _get_builder_agent_name(self) -> str:
        return "世界观架构师(修订)"

    def _get_dimension_names(self) -> Dict[str, str]:
        return {
            "consistency": "内在一致性",
            "depth_breadth": "深度与广度",
            "uniqueness": "独特性",
            "expandability": "可扩展性",
            "power_system": "力量体系完整性",
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
        topic_analysis = context.get("topic_analysis", {})

        iteration_context = self._build_iteration_context(
            iteration, previous_score, previous_issues
        )

        return WORLD_REVIEWER_TASK.format(
            iteration_context=iteration_context,
            topic_analysis=self.to_json(topic_analysis),
            world_setting=self.to_json(content),
        )

    def _build_revision_prompt(
        self,
        score: float,
        feedback: str,
        issues: str,
        original_content: Dict[str, Any],
        report: WorldQualityReport,
        review_data: Dict[str, Any],
        **context,
    ) -> str:
        """构建修订任务提示词"""
        topic_analysis = context.get("topic_analysis", {})
        consistency_analysis = review_data.get("consistency_analysis", {})

        consistency_text = (
            self.to_json(consistency_analysis)
            if consistency_analysis
            else "（无）"
        )

        return WORLD_REVISION_TASK.format(
            score=f"{score:.1f}",
            feedback=feedback,
            issues=issues,
            consistency_analysis=consistency_text,
            original_world=self.to_json(original_content),
            topic_analysis=self.to_json(topic_analysis, max_length=1500),
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
        return bool(revised.get("world_name"))

    def _finalize_result(
        self,
        result: WorldReviewResult,
        final_content: Dict[str, Any],
        last_report: Optional[WorldQualityReport],
    ) -> None:
        """填充最终结果"""
        result.final_world_setting = final_content
        result.final_output = final_content
        result.final_score = last_report.overall_score if last_report else 0
        result.total_iterations = len(result.iterations)
        result.converged = last_report.passed if last_report else False
        result.quality_report = last_report

    def _get_empty_content(self) -> Dict[str, Any]:
        """获取空内容"""
        return {}

    # ══════════════════════════════════════════════════════════════════════════
    # 覆盖钩子方法以添加一致性分析
    # ══════════════════════════════════════════════════════════════════════════

    def _build_issues_text(
        self, report: WorldQualityReport, review_data: Dict[str, Any]
    ) -> str:
        """构建问题列表文本，包含一致性分析"""
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

        return "\n".join(lines) if lines else "（无具体问题）"
