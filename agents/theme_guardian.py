"""
ThemeGuardian - 主题守护者

职责：
1. 定义小说的核心主题和主线冲突
2. 审查每章内容是否偏离主题
3. 为偏离主题的内容提供修正建议

解决根本原因 2：主题一致性校验缺失
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.logging_config import logger


@dataclass
class ThemeDefinition:
    """主题定义."""

    core_theme: str  # 核心主题，如"成长与牺牲"
    central_question: str  # 核心问题，如"主角能否拯救世界？"
    main_conflict: str  # 主线冲突，如"正义 vs 力量"
    protagonist_goal: str  # 主角终极目标
    sub_themes: List[str] = field(default_factory=list)  # 次要主题
    theme_statements: List[str] = field(default_factory=list)  # 主题陈述

    def to_prompt(self) -> str:
        """转换为提示词格式."""
        parts = [
            "## 本小说的核心主题",
            f"**核心主题**: {self.core_theme}",
            f"**核心问题**: {self.central_question}",
            f"**主线冲突**: {self.main_conflict}",
            f"**主角目标**: {self.protagonist_goal}",
        ]

        if self.sub_themes:
            parts.append(f"**次要主题**: {', '.join(self.sub_themes)}")

        if self.theme_statements:
            parts.append("**主题阐述**:")
            for stmt in self.theme_statements:
                parts.append(f"- {stmt}")

        return "\n".join(parts)

    @classmethod
    def from_novel_data(cls, novel_data: Dict[str, Any]) -> "ThemeDefinition":
        """从小说数据创建主题定义."""
        topic_analysis = novel_data.get("topic_analysis", {})
        plot_outline = novel_data.get("plot_outline", {})

        # 提取核心主题
        core_theme = topic_analysis.get("core_theme", "")
        if not core_theme:
            # 从类型和标签推断
            genre = novel_data.get("genre", "")
            tags = novel_data.get("tags", [])
            core_theme = cls._infer_theme_from_genre(genre, tags)

        # 提取核心问题
        central_question = topic_analysis.get("central_question", "")
        if not central_question:
            # 从主角目标推断
            main_plot = (
                plot_outline.get("main_plot", {})
                if isinstance(plot_outline, dict)
                else {}
            )
            protagonist_goal = main_plot.get("protagonist_goal", "")
            if protagonist_goal:
                central_question = f"主角能否实现{protagonist_goal}？"

        # 提取主线冲突
        main_conflict = ""
        if isinstance(plot_outline, dict):
            main_plot = plot_outline.get("main_plot", {})
            main_conflict = main_plot.get("core_conflict", "")

        # 提取主角目标
        protagonist_goal = ""
        if isinstance(plot_outline, dict):
            main_plot = plot_outline.get("main_plot", {})
            protagonist_goal = main_plot.get("protagonist_goal", "")

        return cls(
            core_theme=core_theme,
            central_question=central_question,
            main_conflict=main_conflict,
            protagonist_goal=protagonist_goal,
            sub_themes=topic_analysis.get("sub_themes", []),
            theme_statements=topic_analysis.get("theme_statements", []),
        )

    @staticmethod
    def _infer_theme_from_genre(genre: str, tags: List[str]) -> str:
        """从类型和标签推断主题."""
        genre_themes = {
            "玄幻": "力量与责任",
            "都市": "现实与理想",
            "科幻": "人性与科技",
            "历史": "命运与选择",
            "武侠": "义与利的抉择",
            "仙侠": "道心与欲望",
        }
        return genre_themes.get(genre, "成长与挑战")


@dataclass
class ThemeConsistencyReport:
    """主题一致性审查报告."""

    chapter_number: int = 0
    overall_score: float = 0.0
    passed: bool = False

    # 审查维度
    main_plot_advancement: float = 0.0  # 主线推进度 (0-10)
    character_motivation_alignment: float = 0.0  # 角色动机一致性 (0-10)
    subplot_relevance: float = 0.0  # 支线相关度 (0-10)
    theme_expression: float = 0.0  # 主题表达度 (0-10)

    # 问题列表
    motivation_issues: List[Dict[str, Any]] = field(default_factory=list)
    irrelevant_subplots: List[Dict[str, Any]] = field(default_factory=list)
    theme_deviations: List[Dict[str, Any]] = field(default_factory=list)

    # 建议
    improvement_suggestions: List[str] = field(default_factory=list)

    # 详细分析
    main_plot_analysis: str = ""
    character_analysis: str = ""
    subplot_analysis: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "chapter_number": self.chapter_number,
            "overall_score": self.overall_score,
            "passed": self.passed,
            "dimension_scores": {
                "main_plot_advancement": self.main_plot_advancement,
                "character_motivation_alignment": self.character_motivation_alignment,
                "subplot_relevance": self.subplot_relevance,
                "theme_expression": self.theme_expression,
            },
            "issues": {
                "motivation_issues": self.motivation_issues,
                "irrelevant_subplots": self.irrelevant_subplots,
                "theme_deviations": self.theme_deviations,
            },
            "suggestions": self.improvement_suggestions,
            "analysis": {
                "main_plot": self.main_plot_analysis,
                "character": self.character_analysis,
                "subplot": self.subplot_analysis,
            },
        }


class ThemeGuardian:
    """
    主题守护者

    核心方法：
    1. 定义主题
    2. 审查章节计划
    3. 提供修正建议
    4. 生成主题指导提示词
    """

    # 审查提示词模板
    REVIEW_PROMPT = """请作为专业编辑，审查以下章节计划是否符合小说的核心主题。

{theme_definition}

## 待审查的章节计划

章节号：第{chapter_number}章
章节标题：{chapter_title}

章节计划：
{chapter_plan}

## 审查任务

请从以下维度审查：

1. **主线推进度**：本章事件是否推进了核心问题「{central_question}」的发展？
2. **角色动机一致性**：角色的行为是否符合其核心动机？
3. **支线相关度**：支线情节是否服务于核心主题？
4. **主题表达**：本章是否深化了「{core_theme}」的表达？

## 输出格式

请以 JSON 格式输出审查结果：
{{
    "overall_score": 0-10,
    "dimension_scores": {{
        "main_plot_advancement": 0-10,
        "character_motivation_alignment": 0-10,
        "subplot_relevance": 0-10,
        "theme_expression": 0-10
    }},
    "motivation_issues": [
        {{"character": "角色名", "action": "行为", "reason": "为什么不符合动机"}}
    ],
    "irrelevant_subplots": [
        {{"subplot": "支线描述", "relevance_score": 0-1, "suggestion": "如何改进"}}
    ],
    "theme_deviations": [
        {{"description": "偏离描述", "severity": "high/medium/low", "suggestion": "修正建议"}}
    ],
    "improvement_suggestions": ["建议 1", "建议 2"],
    "main_plot_analysis": "主线推进分析",
    "character_analysis": "角色动机分析",
    "subplot_analysis": "支线相关性分析"
}}
"""

    def __init__(self, novel_id: str, theme_definition: ThemeDefinition):
        """
        初始化主题守护者

        Args:
            novel_id: 小说 ID
            theme_definition: 主题定义
        """
        self.novel_id = novel_id
        self.theme = theme_definition
        self.review_history: List[ThemeConsistencyReport] = []
        logger.info(f"ThemeGuardian initialized for novel {novel_id}")
        logger.info(f"Core theme: {self.theme.core_theme}")

    def review_chapter_plan(
        self, chapter_plan: Dict[str, Any], chapter_number: int
    ) -> ThemeConsistencyReport:
        """
        审查章节计划是否符合主题

        Args:
            chapter_plan: 章节计划
            chapter_number: 章节号

        Returns:
            ThemeConsistencyReport
        """
        logger.info(f"Reviewing chapter {chapter_number} plan for theme consistency")

        report = ThemeConsistencyReport(chapter_number=chapter_number)

        # 维度 1：主线推进度
        main_plot_progress = self._calculate_main_plot_progress(
            chapter_plan, self.theme.central_question
        )
        report.main_plot_advancement = main_plot_progress["score"]
        report.main_plot_analysis = main_plot_progress["analysis"]

        # 维度 2：角色动机一致性
        motivation_analysis = self._analyze_character_motivations(
            chapter_plan, chapter_number
        )
        report.character_motivation_alignment = motivation_analysis["score"]
        report.motivation_issues = motivation_analysis["issues"]
        report.character_analysis = motivation_analysis["analysis"]

        # 维度 3：支线相关度
        subplot_analysis = self._analyze_subplots(chapter_plan)
        report.subplot_relevance = subplot_analysis["score"]
        report.irrelevant_subplots = subplot_analysis["irrelevant_subplots"]
        report.subplot_analysis = subplot_analysis["analysis"]

        # 维度 4：主题表达度
        theme_expression = self._evaluate_theme_expression(chapter_plan)
        report.theme_expression = theme_expression["score"]
        report.theme_deviations = theme_expression["deviations"]

        # 综合评分
        report.overall_score = self._calculate_overall_score(report)
        report.passed = report.overall_score >= 7.0

        # 生成改进建议
        if not report.passed:
            report.improvement_suggestions = self._generate_suggestions(report)

        # 记录历史
        self.review_history.append(report)

        logger.info(
            f"Theme review completed: score={report.overall_score:.1f}, "
            f"passed={report.passed}"
        )

        return report

    def _calculate_main_plot_progress(
        self, chapter_plan: Dict[str, Any], central_question: str
    ) -> Dict[str, Any]:
        """
        计算主线推进度

        检查：
        - 本章事件是否与核心问题相关
        - 是否让主角更接近或远离目标
        - 是否推进了主线冲突
        """
        score = 5.0  # 基础分
        analysis_parts = []

        # 提取本章主要事件
        main_events = chapter_plan.get("main_events", [])
        plot_points = chapter_plan.get("plot_points", [])
        all_events = main_events + plot_points

        if not all_events:
            return {"score": 3.0, "analysis": "章节计划缺少明确的事件描述"}

        # 检查与核心问题的关联
        relevant_events = 0
        for event in all_events:
            event_str = str(event)
            # 简单关键词匹配（实际应该用 LLM 语义分析）
            if any(
                keyword in event_str
                for keyword in [central_question.split("？")[0], "目标", "冲突", "主线"]
            ):
                relevant_events += 1

        # 计算相关性分数
        if relevant_events > 0:
            relevance_ratio = relevant_events / len(all_events)
            score += relevance_ratio * 3  # 最多 +3 分
            analysis_parts.append(
                f"本章有{relevant_events}/{len(all_events)}个事件直接关联核心问题"
            )

        # 检查是否有明确的目标推进
        if chapter_plan.get("goal_progress"):
            score += 2.0
            analysis_parts.append("本章明确了主角目标的进展")

        return {
            "score": min(10.0, score),
            "analysis": (
                "。".join(analysis_parts)
                if analysis_parts
                else "本章对主线推进作用不明显"
            ),
        }

    def _analyze_character_motivations(
        self, chapter_plan: Dict[str, Any], chapter_number: int
    ) -> Dict[str, Any]:
        """
        分析角色动机一致性

        检查：
        - 角色行为是否符合其核心动机
        - 决策是否与性格一致
        """
        issues = []
        score = 8.0
        analysis_parts = []

        character_actions = chapter_plan.get("character_actions", [])

        if not character_actions:
            return {"score": 7.0, "issues": [], "analysis": "章节计划缺少角色行为描述"}

        # 简化检查：标记可疑但不确定的行为
        for action in character_actions:
            char_name = action.get("name", "")
            action_desc = action.get("action", "")
            motivation = action.get("motivation", "")

            # 如果没有提供动机，标记为需要审查
            if not motivation:
                issues.append(
                    {
                        "character": char_name,
                        "action": action_desc,
                        "reason": "未说明行为动机，需确认是否符合角色设定",
                    }
                )
                score -= 0.5

        if issues:
            analysis_parts.append(f"发现{len(issues)}个需要确认的角色行为")
        else:
            analysis_parts.append("角色行为动机清晰")

        return {
            "score": max(5.0, score),
            "issues": issues,
            "analysis": "。".join(analysis_parts),
        }

    def _analyze_subplots(self, chapter_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析支线情节相关度

        检查：
        - 支线是否服务于主题
        - 是否喧宾夺主
        """
        irrelevant_subplots = []
        score = 8.0
        analysis_parts = []

        subplots = chapter_plan.get("subplots", [])

        if not subplots:
            return {
                "score": 8.0,
                "irrelevant_subplots": [],
                "analysis": "本章无支线情节",
            }

        # 评估每个支线的相关度
        for subplot in subplots:
            subplot_str = str(subplot)

            # 简单评估：检查是否包含主题关键词
            relevance_score = 0.5  # 默认中等相关

            if any(
                keyword in subplot_str
                for keyword in [
                    self.theme.core_theme,
                    self.theme.main_conflict.split(" vs ")[0],
                ]
            ):
                relevance_score = 0.8

            if relevance_score < 0.3:
                irrelevant_subplots.append(
                    {
                        "subplot": subplot,
                        "relevance_score": relevance_score,
                        "suggestion": "建议删除或增加与主题的联系",
                    }
                )
                score -= 1.0

        if irrelevant_subplots:
            analysis_parts.append(f"发现{len(irrelevant_subplots)}个相关性较弱的支线")
        else:
            analysis_parts.append("支线情节与主题关联良好")

        return {
            "score": max(5.0, score),
            "irrelevant_subplots": irrelevant_subplots,
            "analysis": "。".join(analysis_parts),
        }

    def _evaluate_theme_expression(
        self, chapter_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        评估主题表达度

        检查：
        - 是否深化了主题
        - 是否有偏离主题的内容
        """
        deviations = []
        score = 7.0

        # 检查章节摘要/主题
        chapter_theme = chapter_plan.get("theme", "")
        chapter_summary = chapter_plan.get("summary", "")

        if chapter_theme:
            # 检查章节主题是否与核心主题一致
            if self.theme.core_theme not in chapter_theme:
                deviations.append(
                    {
                        "description": "章节主题与核心主题关联不明确",
                        "severity": "medium",
                        "suggestion": "建议在章节中增加与核心主题的联系",
                    }
                )
                score -= 1.0

        # 检查是否有明显偏离的内容
        content_text = json.dumps(chapter_plan, ensure_ascii=False)

        # 简单检查：是否包含大量与主题无关的元素
        # （实际应该用 LLM 进行语义分析）

        return {"score": max(5.0, score), "deviations": deviations}

    def _calculate_overall_score(self, report: ThemeConsistencyReport) -> float:
        """
        计算综合评分

        权重：
        - 主线推进度：40%
        - 角色动机：25%
        - 支线相关度：20%
        - 主题表达：15%
        """
        weights = {
            "main_plot_advancement": 0.4,
            "character_motivation_alignment": 0.25,
            "subplot_relevance": 0.2,
            "theme_expression": 0.15,
        }

        score = (
            report.main_plot_advancement * weights["main_plot_advancement"]
            + report.character_motivation_alignment
            * weights["character_motivation_alignment"]
            + report.subplot_relevance * weights["subplot_relevance"]
            + report.theme_expression * weights["theme_expression"]
        )

        return round(score, 1)

    def _generate_suggestions(self, report: ThemeConsistencyReport) -> List[str]:
        """生成改进建议."""
        suggestions = []

        if report.main_plot_advancement < 6.0:
            suggestions.append("建议增加与核心问题直接相关的事件，明确推进主线剧情")

        if report.character_motivation_alignment < 6.0:
            suggestions.append("建议为角色行为提供更清晰的动机说明，确保符合角色设定")

        if report.subplot_relevance < 6.0:
            suggestions.append("建议删除或修改与主题关联较弱的支线情节")

        if report.theme_expression < 6.0:
            suggestions.append(f"建议在章节中深化「{self.theme.core_theme}」主题的表达")

        return suggestions

    def build_theme_guidance_prompt(self) -> str:
        """
        构建主题指导提示词

        用于在生成前提醒作家
        """
        return f"""
{self.theme.to_prompt()}

## 创作要求

每一章都应该：

1. **推进主线冲突**
   - 让主角更接近或远离终极目标
   - 深化核心冲突的展现
   - 回答或部分回答核心问题

2. **保持角色一致性**
   - 角色行为必须符合其核心动机
   - 决策风格应体现性格特点
   - 避免为"有趣"而违背人设

3. **深化主题表达**
   - 通过情节展现主题
   - 避免与主题无关的支线
   - 每个场景都应该服务于主题

## ⚠️ 警告

避免以下常见问题：
- 为了"爽点"而添加与主题无关的情节
- 角色行为前后不一致
- 支线情节喧宾夺主
- 忘记核心问题和主线冲突

**记住**：好的章节不是"有趣"，而是让读者更接近答案！
"""

    def get_statistics(self) -> Dict[str, Any]:
        """获取审查统计."""
        if not self.review_history:
            return {"total_reviews": 0, "average_score": 0, "pass_rate": 0}

        total = len(self.review_history)
        passed = sum(1 for r in self.review_history if r.passed)
        avg_score = sum(r.overall_score for r in self.review_history) / total

        return {
            "total_reviews": total,
            "average_score": round(avg_score, 1),
            "pass_rate": round(passed / total, 2) if total > 0 else 0,
        }


# 便捷函数
def create_theme_guardian(novel_id: str, novel_data: Dict[str, Any]) -> ThemeGuardian:
    """便捷函数：创建主题守护者."""
    theme = ThemeDefinition.from_novel_data(novel_data)
    return ThemeGuardian(novel_id, theme)


def review_chapter_theme_consistency(
    novel_id: str,
    novel_data: Dict[str, Any],
    chapter_plan: Dict[str, Any],
    chapter_number: int,
) -> ThemeConsistencyReport:
    """便捷函数：审查章节主题一致性."""
    guardian = create_theme_guardian(novel_id, novel_data)
    return guardian.review_chapter_plan(chapter_plan, chapter_number)
