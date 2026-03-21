"""角色审查反馈循环 - 确保角色设计的深度和质量

通过 Designer-Reviewer 循环迭代，确保角色具有：
- 心理深度和内在矛盾
- 独特性（与其他角色区分）
- 成长弧线的合理性
- 关系网络的复杂性
"""

import json
from typing import Any, Dict, List, Optional

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient

from agents.base import (
    BaseReviewLoopHandler,
    CharacterQualityReport,
    CharacterReviewResult,
    JsonExtractor,
    ReviewLoopConfig,
)

# ── 角色审查专用提示词 ──────────────────────────────────────────

CHARACTER_REVIEWER_SYSTEM = """你是一位资深的网络小说角色评审专家，专注于角色设计的深度和质量。

你需要从以下维度严格评估角色设计：

1. **心理深度** (psychological_depth)：
   - 角色是否有内在矛盾和挣扎？
   - 动机是否复杂而非单一？
   - 是否有隐藏的恐惧、欲望或秘密？

2. **独特性** (uniqueness)：
   - 角色之间是否有足够的区分度？
   - 是否避免了脸谱化和刻板印象？
   - 每个角色是否有独特的说话方式或行为习惯？

3. **成长潜力** (growth_potential)：
   - 成长弧线是否合理、有说服力？
   - 是否有足够的挑战和转折点？
   - 角色的弱点是否会在故事中被考验？

4. **关系复杂性** (relationship_complexity)：
   - 角色之间的关系是否多层次？
   - 是否有潜在的冲突和张力？
   - 关系是否会随剧情发展而变化？

5. **世界观契合度** (world_fit)：
   - 角色背景是否与世界观设定一致？
   - 角色能力是否符合力量体系？
   - 角色在世界中的位置是否合理？

6. **网文人设功能性** (webnovel_functionality)：
   - 主角代入感：动机是否纯粹强烈？是否有明确"流派标签"（苟道流/迪化流/无敌流等）？是否存在圣母/犹豫/降智？读者能否快速产生代入感？
   - 反派工具性：是否有足够"欠打"属性？能否激发读者期待主角反杀？是否在不抢主角风头的前提下有存在感？
   - 配角标签化：是否有鲜明的"记忆标签"？功能是否明确（信息提供/喜剧担当/情感支点/实力参照）？

【重要】评分原则：
- 你必须给出精确的评分，不要给出"安全"的中间分数
- 如果角色有明显深度和创新设计，应给 8.0 以上
- 如果有明显问题未解决，应给 7.0 以下
- 评分应该反映真实质量，而不是折中

评分标准：
- 9-10分：卓越，角色极具魅力和深度
- 8-9分：优秀，角色立体丰满，有深度
- 7-8分：良好，基本立体但有改进空间
- 6-7分：及格，存在明显问题需要修改
- 6分以下：不合格，需要大幅重做"""

CHARACTER_REVIEWER_TASK = """请对以下角色设计进行全面质量评估。

{iteration_context}

世界观设定：
{world_setting}

角色列表：
{characters}

请以JSON格式输出评估结果（不要输出其他内容）：
{{
    "overall_score": 综合评分(1-10浮点数，请给出精确分数如7.3、8.1等，不要总是给7.0或7.5这样的整数),
    "dimension_scores": {{
        "psychological_depth": 心理深度分数,
        "uniqueness": 独特性分数,
        "growth_potential": 成长潜力分数,
        "relationship_complexity": 关系复杂性分数,
        "world_fit": 世界观契合度分数,
        "webnovel_functionality": 网文人设功能性分数
    }},
    "improvement_assessment": {{
        "issues_resolved": ["已解决的问题"],
        "issues_remaining": ["仍存在的问题"],
        "new_issues": ["新发现的问题"],
        "improvement_score": 改进程度分数(1-10，仅在非首轮审查时填写)
    }},
    "character_assessments": [
        {{
            "name": "角色名",
            "score": 该角色评分,
            "strengths": ["优点1", "优点2"],
            "weaknesses": ["问题1", "问题2"],
            "improvement_suggestions": ["具体改进建议"],
            "character_tag": "该角色的记忆标签",
            "reader_function": "该角色对读者的功能评价"
        }}
    ],
    "uniqueness_analysis": {{
        "similar_pairs": [["角色A", "角色B", "相似之处"]],
        "missing_archetypes": ["缺少的角色类型"],
        "relationship_gaps": ["缺失的关系维度"],
        "protagonist_immersion": "主角代入感评价",
        "villain_effectiveness": "反派工具性评价"
    }},
    "critical_issues": [
        {{"character": "角色名", "issue": "严重问题", "severity": "high/medium/low"}}
    ],
    "summary": "整体评价（50字以内）"
}}"""

CHARACTER_REVISION_TASK = """你之前设计的角色经过专家评审，需要优化。

评审评分：{score}/10

评审反馈：
{feedback}

各角色的具体问题：
{character_issues}

原角色设计：
{original_characters}

世界观设定（供参考）：
{world_setting}

请根据评审意见优化角色设计，重点解决以下问题：
1. 增加角色的心理深度和内在矛盾
2. 强化角色之间的差异性
3. 完善成长弧线，添加具体的转折点
4. 丰富角色关系，增加潜在冲突

请以JSON数组格式输出优化后的完整角色列表：
[
    {{
        "name": "姓名",
        "role_type": "protagonist/supporting/antagonist",
        "gender": "male/female",
        "age": 年龄,
        "appearance": "外貌描述（具体、有特点）",
        "personality": "性格特点（包含优点和缺点）",
        "inner_conflict": "内在矛盾或心理挣扎（新增）",
        "background": "背景故事（详细、有创伤或特殊经历）",
        "goals": "目标与动机（表层目标和深层需求）",
        "fears": "恐惧或弱点（新增）",
        "secrets": "角色秘密（可选，新增）",
        "speech_pattern": "说话方式或口头禅（新增）",
        "abilities": {{"main_ability": "主要能力", "special_trait": "特殊特质", "limitation": "能力限制"}},
        "relationships": {{"角色名": "关系描述（包含情感和潜在冲突）"}},
        "growth_arc": {{
            "start": "初始状态（性格缺陷或困境）",
            "catalyst": "触发改变的事件",
            "middle": "中期发展（面临的考验）",
            "crisis": "最大危机点",
            "end": "最终状态（成长或改变）"
        }}
    }}
]"""


class CharacterReviewHandler(
    BaseReviewLoopHandler[
        List[Dict[str, Any]], CharacterReviewResult, CharacterQualityReport
    ]
):
    """角色设计审查循环处理器

    流程：
    1. Designer 生成/修订角色
    2. Reviewer 多维度评估 + 问题识别
    3. 如果 score < threshold 且未达上限 → 反馈给 Designer → 回到 1
    4. 返回最终角色列表 + 迭代历史
    """

    def __init__(
        self,
        client: QwenClient,
        cost_tracker: CostTracker,
        quality_threshold: float = 7.0,
        max_iterations: int = 2,
    ):
        """初始化角色审查处理器

        Args:
            client: LLM 客户端
            cost_tracker: 成本追踪器
            quality_threshold: 质量阈值（默认7.0，比章节略低）
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
        initial_characters: List[Dict[str, Any]],
        world_setting: Dict[str, Any],
        topic_analysis: Dict[str, Any],
    ) -> CharacterReviewResult:
        """执行角色设计审查循环

        Args:
            initial_characters: 初始角色列表
            world_setting: 世界观设定
            topic_analysis: 主题分析结果

        Returns:
            CharacterReviewResult
        """
        return await super().execute(
            initial_content=initial_characters,
            world_setting=world_setting,
            topic_analysis=topic_analysis,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # 实现抽象方法
    # ══════════════════════════════════════════════════════════════════════════

    def _get_loop_name(self) -> str:
        return "CharacterReview"

    def _create_result(self) -> CharacterReviewResult:
        return CharacterReviewResult()

    def _create_quality_report(
        self, review_data: Dict[str, Any]
    ) -> CharacterQualityReport:
        return CharacterQualityReport.from_llm_response(
            review_data,
            quality_threshold=self.quality_threshold,
        )

    def _get_reviewer_system_prompt(self) -> str:
        return CHARACTER_REVIEWER_SYSTEM

    def _get_builder_system_prompt(self) -> str:
        from llm.prompt_manager import PromptManager

        return PromptManager.CHARACTER_DESIGNER_SYSTEM

    def _get_reviewer_agent_name(self) -> str:
        return "角色审查员"

    def _get_builder_agent_name(self) -> str:
        return "角色设计师(修订)"

    def _get_dimension_names(self) -> Dict[str, str]:
        return {
            "psychological_depth": "心理深度",
            "uniqueness": "独特性",
            "growth_potential": "成长潜力",
            "relationship_complexity": "关系复杂性",
            "world_fit": "世界观契合度",
            "webnovel_functionality": "网文人设功能性",
        }

    def _build_reviewer_task_prompt(
        self,
        content: List[Dict[str, Any]],
        iteration: int,
        previous_score: float,
        previous_issues: List[str],
        **context,
    ) -> str:
        """构建 Reviewer 任务提示词"""
        world_setting = context.get("world_setting", {})

        iteration_context = self._build_iteration_context(
            iteration, previous_score, previous_issues
        )

        return CHARACTER_REVIEWER_TASK.format(
            iteration_context=iteration_context,
            world_setting=self.to_json(world_setting),
            characters=self.to_json(content),
        )

    def _build_revision_prompt(
        self,
        score: float,
        feedback: str,
        issues: str,
        original_content: List[Dict[str, Any]],
        report: CharacterQualityReport,
        review_data: Dict[str, Any],
        **context,
    ) -> str:
        """构建修订任务提示词"""
        world_setting = context.get("world_setting", {})

        return CHARACTER_REVISION_TASK.format(
            score=f"{score:.1f}",
            feedback=feedback,
            character_issues=issues,
            original_characters=self.to_json(original_content),
            world_setting=self.to_json(world_setting, max_length=2000),
        )

    def _validate_revision(
        self, revised: List[Dict[str, Any]], original: List[Dict[str, Any]]
    ) -> bool:
        """验证修订结果是否有效"""
        if not revised:
            return False
        if not isinstance(revised, list):
            return False
        return len(revised) > 0

    def _finalize_result(
        self,
        result: CharacterReviewResult,
        final_content: List[Dict[str, Any]],
        last_report: Optional[CharacterQualityReport],
    ) -> None:
        """填充最终结果"""
        result.final_characters = final_content
        result.final_output = final_content
        result.final_score = last_report.overall_score if last_report else 0
        result.total_iterations = len(result.iterations)
        result.converged = last_report.passed if last_report else False
        result.quality_report = last_report

    def _get_empty_content(self) -> List[Dict[str, Any]]:
        """获取空内容"""
        return []

    def _parse_builder_response(self, response_text: str) -> List[Dict[str, Any]]:
        """解析 Builder 响应"""
        result = JsonExtractor.extract_json(response_text, default=[])
        # 确保返回列表
        if isinstance(result, dict):
            return [result]
        return result if isinstance(result, list) else []

    # ══════════════════════════════════════════════════════════════════════════
    # 覆盖钩子方法以添加角色评估细节
    # ══════════════════════════════════════════════════════════════════════════

    def _build_issues_text(
        self, report: CharacterQualityReport, review_data: Dict[str, Any]
    ) -> str:
        """构建问题列表文本，包含各角色具体问题"""
        lines = []

        # 添加各角色评估
        character_assessments = review_data.get("character_assessments", [])
        for assessment in character_assessments:
            char_name = assessment.get("name", "未知")
            weaknesses = assessment.get("weaknesses", [])
            suggestions = assessment.get("improvement_suggestions", [])
            if weaknesses or suggestions:
                lines.append(f"\n【{char_name}】")
                for w in weaknesses:
                    lines.append(f"  - 问题：{w}")
                for s in suggestions:
                    lines.append(f"  - 建议：{s}")

        # 添加严重问题
        for issue in report.issues:
            char = issue.get("character", "")
            desc = issue.get("issue", "")
            severity = issue.get("severity", "medium")
            lines.append(f"\n[{severity.upper()}] {char}: {desc}")

        return "\n".join(lines) if lines else "（无具体问题）"

    def _collect_issues_for_next_round(
        self, report: CharacterQualityReport, review_data: Dict[str, Any]
    ) -> List[str]:
        """收集问题用于下一轮审查"""
        issues = []

        # 添加严重问题
        for issue in report.issues:
            char = issue.get("character", "")
            desc = issue.get("issue", "")
            issues.append(f"{char}: {desc}" if char else desc)

        # 添加角色评估中的问题
        character_assessments = review_data.get("character_assessments", [])
        for assessment in character_assessments:
            char_name = assessment.get("name", "")
            for w in assessment.get("weaknesses", []):
                issues.append(f"{char_name}: {w}")

        return issues
