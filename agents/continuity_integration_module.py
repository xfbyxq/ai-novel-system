"""
ContinuityIntegrationModule - 连贯性保障集成模块.

将所有连贯性保障组件集成到一个统一的接口中，
方便 GenerationService 和 CrewManager 调用。

整合的组件：
1. EnhancedContextManager - 增强上下文管理
2. ThemeGuardian - 主题守护者
3. ChapterOutlineMapper - 章节大纲映射器
4. CharacterConsistencyTracker - 角色一致性追踪器
5. ForeshadowingAutoInjector - 伏笔自动注入器
6. PreventionContinuityChecker - 预防式连贯性检查器
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agents.character_relationship_tracker import CharacterRelationshipTracker
from agents.coherence_scorecard import CoherenceScorecard, CoherenceScorecardBuilder
from agents.continuity_models import IntentionalInconsistency
from agents.foreshadowing_auto_detector import ForeshadowingAutoDetector
from agents.spatial_tracker import SpatialTracker
from agents.world_evolution_tracker import WorldEvolutionTracker
from core.logging_config import logger

from .chapter_outline_mapper import (
    ChapterOutlineMapper,
    ChapterOutlineTask,
    OutlineValidationReport,
)
from .character_consistency_tracker import (
    CharacterConsistencyTracker,
    CharacterProfile,
    ConsistencyValidation,
)
from .enhanced_context_manager import EnhancedContext, EnhancedContextManager
from .foreshadowing_auto_injector import ForeshadowingAutoInjector, ForeshadowingReport
from .prevention_continuity_checker import PreventionContinuityChecker, PreventionReport
from .theme_guardian import ThemeConsistencyReport, ThemeDefinition, ThemeGuardian


@dataclass
class ContinuityIntegrationResult:
    """连贯性集成结果."""

    chapter_number: int

    # 各组件结果
    enhanced_context: Optional[EnhancedContext] = None
    theme_report: Optional[ThemeConsistencyReport] = None
    outline_task: Optional[ChapterOutlineTask] = None
    outline_validation: Optional[OutlineValidationReport] = None
    character_validations: Dict[str, ConsistencyValidation] = field(
        default_factory=dict
    )
    foreshadowing_report: Optional[ForeshadowingReport] = None
    prevention_report: Optional[PreventionReport] = None

    # 综合评分
    overall_score: float = 0.0

    # 是否通过
    passed: bool = False

    # 问题汇总
    issues: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    # 新增字段 - 世界观演变追踪
    world_evolution_issues: List[Dict[str, Any]] = field(default_factory=list)
    # 新增字段 - 空间一致性检查
    spatial_issues: List[Dict[str, Any]] = field(default_factory=list)
    # 新增字段 - 角色关系问题
    relationship_issues: List[Dict[str, Any]] = field(default_factory=list)
    # 新增字段 - 自动检测的伏笔
    detected_foreshadowings: List[Dict[str, Any]] = field(default_factory=list)
    # 新增字段 - 统一连贯性评分卡
    scorecard: Optional[CoherenceScorecard] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "chapter_number": self.chapter_number,
            "passed": self.passed,
            "overall_score": round(self.overall_score, 2),
            "components": {
                "theme": self.theme_report.to_dict() if self.theme_report else None,
                "outline": (
                    self.outline_validation.to_dict()
                    if self.outline_validation
                    else None
                ),
                "characters": {
                    k: v.to_dict() for k, v in self.character_validations.items()
                },
                "foreshadowing": (
                    self.foreshadowing_report.to_dict()
                    if self.foreshadowing_report
                    else None
                ),
                "prevention": (
                    self.prevention_report.to_dict() if self.prevention_report else None
                ),
            },
            "issues": self.issues,
            "suggestions": self.suggestions,
            "world_evolution_issues": self.world_evolution_issues,
            "spatial_issues": self.spatial_issues,
            "relationship_issues": self.relationship_issues,
            "detected_foreshadowings": self.detected_foreshadowings,
            "scorecard": self.scorecard.to_dict() if self.scorecard else None,
        }


class ContinuityIntegrationModule:
    """
    连贯性保障集成模块.

    提供统一的接口来管理所有连贯性保障组件

    使用方式：
    1. 初始化模块
    2. 在章节生成前调用 prepare_chapter_generation
    3. 在章节策划后调用 review_chapter_plan
    4. 在章节生成后调用 validate_chapter_content
    """

    def __init__(self, novel_id: str, novel_data: Dict[str, Any]):
        """
        初始化集成模块.

        Args:
            novel_id: 小说 ID
            novel_data: 小说数据（包含主题、大纲、角色等）
        """
        self.novel_id = novel_id
        self.novel_data = novel_data

        # 初始化各组件
        logger.info(f"Initializing ContinuityIntegrationModule for novel {novel_id}")

        # 1. 上下文管理器
        self.context_manager = EnhancedContextManager(novel_id)

        # 2. 主题守护者
        theme_def = ThemeDefinition.from_novel_data(novel_data)
        self.theme_guardian = ThemeGuardian(novel_id, theme_def)

        # 3. 大纲映射器
        self.outline_mapper = ChapterOutlineMapper(novel_id)
        self._load_volume_outlines(novel_data)

        # 4. 角色追踪器（按角色）
        self.character_trackers: Dict[str, CharacterConsistencyTracker] = {}
        self._initialize_character_trackers(novel_data)

        # 5. 伏笔注入器
        self.foreshadowing_injector = ForeshadowingAutoInjector(novel_id)
        self._initialize_foreshadowings(novel_data)

        # 6. 预防式检查器
        self.prevention_checker = PreventionContinuityChecker(novel_id)

        # === 新增连贯性组件 ===
        # 世界观演变追踪器
        self.world_tracker = WorldEvolutionTracker(
            novel_data=novel_data,
        )
        # 空间位置追踪器
        self.spatial_tracker = SpatialTracker(
            novel_data=novel_data,
        )
        # 角色关系追踪器
        self.relationship_tracker = CharacterRelationshipTracker()
        # 伏笔自动检测器
        self.foreshadowing_detector = ForeshadowingAutoDetector()
        # 连贯性评分卡构建器
        self.scorecard_builder = CoherenceScorecardBuilder()
        # 有意不一致列表
        self.intentional_inconsistencies: List[IntentionalInconsistency] = []

        logger.info(
            "连贯性增强组件初始化完成: 世界观追踪、空间追踪、关系追踪、伏笔检测、评分体系"
        )

    def _load_volume_outlines(self, novel_data: Dict[str, Any]):
        """加载卷大纲."""
        plot_outline = novel_data.get("plot_outline", {})
        if not plot_outline:
            logger.warning("No plot outline found in novel data")
            return

        volumes = plot_outline.get("volumes", [])
        for vol in volumes:
            vol_num = vol.get("volume_num", 1)
            chapters_range = vol.get("chapters_range", [1, 10])

            self.outline_mapper.load_volume_outline(
                volume_number=vol_num,
                volume_outline=vol,
                total_chapters_in_volume=chapters_range[1] - chapters_range[0] + 1,
            )

    def _initialize_character_trackers(self, novel_data: Dict[str, Any]):
        """初始化角色追踪器."""
        characters = novel_data.get("characters", [])

        for char_data in characters:
            name = char_data.get("name", "")
            if not name:
                continue

            profile = CharacterProfile.from_character_data(char_data)
            tracker = CharacterConsistencyTracker(profile)
            self.character_trackers[name] = tracker

            logger.info(f"Initialized character tracker for: {name}")

    def _initialize_foreshadowings(self, novel_data: Dict[str, Any]):
        """初始化伏笔."""
        # 从小说数据中提取已有伏笔
        foreshadowings = novel_data.get("foreshadowings", [])

        for fb_data in foreshadowings:
            from .foreshadowing_auto_injector import Foreshadowing, ForeshadowingStatus

            foreshadow = Foreshadowing(
                id=fb_data.get("id", ""),
                content=fb_data.get("content", ""),
                planted_chapter=fb_data.get("planted_chapter", 0),
                expected_resolve_chapter=fb_data.get("expected_resolve_chapter", 0),
                importance=fb_data.get("importance", 5),
                status=ForeshadowingStatus(fb_data.get("status", "pending")),
            )
            self.foreshadowing_injector.add_foreshadowing(foreshadow)

    async def prepare_chapter_generation(
        self,
        chapter_number: int,
        volume_number: int = 1,
        chapter_summaries: Optional[Dict[int, Dict[str, Any]]] = None,
        chapter_contents: Optional[Dict[int, str]] = None,
        conflicts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        准备章节生成：构建上下文和任务.

        Args:
            chapter_number: 章节号
            volume_number: 卷号
            chapter_summaries: 章节摘要
            chapter_contents: 章节内容
            conflicts: 冲突列表

        Returns:
            包含上下文、大纲任务、伏笔要求等的字典
        """
        logger.info(f"Preparing chapter generation for chapter {chapter_number}")

        result = {}

        # 1. 构建增强的上下文
        foreshadowings_data = [
            fb.to_dict() for fb in self.foreshadowing_injector.foreshadowings.values()
        ]

        enhanced_context = self.context_manager.build_context_for_chapter(
            chapter_number=chapter_number,
            novel_data=self.novel_data,
            chapter_summaries=chapter_summaries or {},
            chapter_contents=chapter_contents or {},
            foreshadowings=foreshadowings_data,
            conflicts=conflicts or [],
        )

        result["enhanced_context"] = enhanced_context
        result["context_prompt"] = enhanced_context.to_prompt()

        # 2. 获取大纲任务
        outline_task = self.outline_mapper.map_outline_to_chapter(
            volume_number=volume_number,
            chapter_number=chapter_number,
            foreshadowings=foreshadowings_data,
        )

        result["outline_task"] = outline_task
        result["outline_task_prompt"] = outline_task.to_prompt()

        # 3. 获取主题指导
        theme_guidance = self.theme_guardian.build_theme_guidance_prompt()
        result["theme_guidance"] = theme_guidance

        # 4. 获取伏笔要求
        plot_outline = self.novel_data.get("plot_outline", {})
        foreshadowing_prompt = self.foreshadowing_injector.build_foreshadowing_prompt(
            current_chapter=chapter_number, plot_outline=plot_outline
        )
        result["foreshadowing_requirements"] = foreshadowing_prompt

        # 5. 获取角色一致性要求（针对本章可能出场的角色）
        character_prompts = []
        for name, tracker in self.character_trackers.items():
            character_prompts.append(tracker.build_character_prompt())

        result["character_consistency_requirements"] = "\n\n".join(character_prompts)

        # 新增上下文信息
        result["world_setting_context"] = self.world_tracker.get_settings_summary()
        result["spatial_context"] = self.spatial_tracker.build_spatial_context(chapter_number)

        # 获取已知角色列表（从 character_trackers 中获取）
        known_characters = (
            list(self.character_trackers.keys())
            if hasattr(self, "character_trackers")
            else []
        )
        result["relationship_context"] = self.relationship_tracker.build_relationship_context(
            characters=known_characters
        )

        logger.info(f"Chapter {chapter_number} preparation completed")

        return result

    async def review_chapter_plan(
        self,
        chapter_plan: Dict[str, Any],
        chapter_number: int,
        previous_chapter: Optional[Dict[str, Any]] = None,
    ) -> ContinuityIntegrationResult:
        """
        审查章节策划.

        Args:
            chapter_plan: 章节策划
            chapter_number: 章节号
            previous_chapter: 上一章信息

        Returns:
            ContinuityIntegrationResult
        """
        logger.info(f"Reviewing chapter {chapter_number} plan")

        result = ContinuityIntegrationResult(chapter_number=chapter_number)

        # 1. 主题一致性审查
        theme_report = self.theme_guardian.review_chapter_plan(
            chapter_plan=chapter_plan, chapter_number=chapter_number
        )
        result.theme_report = theme_report

        # 2. 大纲任务验证
        outline_validation = self.outline_mapper.validate_chapter_against_outline(
            chapter_plan=chapter_plan, chapter_number=chapter_number
        )
        result.outline_validation = outline_validation

        # 3. 角色一致性验证
        character_actions = chapter_plan.get("character_actions", [])
        for action in character_actions:
            char_name = action.get("name", "")
            if char_name not in self.character_trackers:
                continue

            tracker = self.character_trackers[char_name]
            validation = tracker.validate_action(
                proposed_action=action.get("action", ""),
                context=action.get("context", ""),
                chapter_number=chapter_number,
            )
            result.character_validations[char_name] = validation

            # 记录决策
            if action.get("decision"):
                tracker.record_decision(
                    chapter_number=chapter_number,
                    decision=action.get("action", ""),
                    reason=action.get("motivation", ""),
                )

        # 4. 伏笔任务验证
        foreshadowing_report = (
            self.foreshadowing_injector.get_chapter_foreshadowing_tasks(
                current_chapter=chapter_number,
                plot_outline=self.novel_data.get("plot_outline", {}),
            )
        )
        result.foreshadowing_report = foreshadowing_report

        # 5. 预防式连贯性检查
        if previous_chapter:
            # 从约束生成 ContinuityConstraint 对象
            constraints = self._extract_constraints_from_previous(previous_chapter)

            prevention_report = await self.prevention_checker.check_chapter_plan(
                chapter_plan=chapter_plan,
                previous_chapter=previous_chapter,
                constraints=constraints,
                chapter_number=chapter_number,
            )
            result.prevention_report = prevention_report

        # === 新增检查步骤 ===

        # 1. 世界观演变检查
        world_issues = []
        try:
            world_issues_raw = await self.world_tracker.validate_chapter_against_settings(
                chapter_content=str(chapter_plan),
                chapter_number=chapter_number,
            )
            world_issues = [issue.to_dict() for issue in world_issues_raw]
        except Exception as e:
            logger.warning(f"世界观验证失败: {e}")

        # 2. 空间一致性检查
        spatial_issues = []
        spatial_issues_raw = []
        try:
            spatial_issues_raw = self.spatial_tracker.validate_spatial_continuity(
                chapter_content=str(chapter_plan),
                chapter_number=chapter_number,
            )
            spatial_issues = [issue.to_dict() for issue in spatial_issues_raw]
        except Exception as e:
            logger.warning(f"空间一致性检查失败: {e}")

        # 3. 角色关系检查
        relationship_issues = []
        try:
            rel_issues_raw = self.relationship_tracker.detect_relationship_issues(
                chapter_number=chapter_number,
            )
            relationship_issues = [issue.to_dict() for issue in rel_issues_raw]
        except Exception as e:
            logger.warning(f"角色关系检查失败: {e}")

        # 4. 伏笔自动检测
        detected_foreshadowings = []
        try:
            detected_raw = await self.foreshadowing_detector.detect_foreshadowings(
                chapter_content=str(chapter_plan),
                chapter_number=chapter_number,
            )
            detected_foreshadowings = [d.to_dict() for d in detected_raw]
            # 将高置信度伏笔合并到追踪器
            if hasattr(self, "foreshadowing_injector") and hasattr(
                self.foreshadowing_injector, "tracker"
            ):
                self.foreshadowing_detector.merge_with_tracker(
                    detected=detected_raw,
                    tracker=self.foreshadowing_injector.tracker,
                )
        except Exception as e:
            logger.warning(f"伏笔自动检测失败: {e}")

        # 5. 构建统一评分卡
        scorecard = None
        try:
            scorecard = self.scorecard_builder.build_scorecard(
                chapter_number=chapter_number,
                continuity_result=result if isinstance(result, dict) else None,
                character_validations=result.character_validations
                if hasattr(result, "character_validations")
                else None,
                foreshadowing_report=result.foreshadowing_report
                if hasattr(result, "foreshadowing_report")
                else None,
                spatial_issues=spatial_issues_raw if spatial_issues else None,
            )
        except Exception as e:
            logger.warning(f"评分卡构建失败: {e}")

        # 设置新增字段到 result
        result.world_evolution_issues = world_issues
        result.spatial_issues = spatial_issues
        result.relationship_issues = relationship_issues
        result.detected_foreshadowings = detected_foreshadowings
        result.scorecard = scorecard

        # 将新发现的问题也追加到 result.issues 中
        for wi in world_issues:
            result.issues.append({"source": "world_evolution", **wi})
        for si in spatial_issues:
            result.issues.append({"source": "spatial", **si})
        for ri in relationship_issues:
            result.issues.append({"source": "relationship", **ri})

        # 6. 综合评分
        scores = []
        if theme_report:
            scores.append(theme_report.overall_score)
        if outline_validation:
            scores.append(outline_validation.quality_score)
        if result.character_validations:
            char_scores = [
                v.overall_score for v in result.character_validations.values()
            ]
            scores.extend(char_scores)
        if prevention_report:
            scores.append(prevention_report.overall_score)

        result.overall_score = sum(scores) / len(scores) if scores else 0
        result.passed = result.overall_score >= 7.0

        # 7. 汇总问题和建议
        self._aggregate_issues_and_suggestions(result)

        logger.info(
            f"Chapter {chapter_number} plan review completed: "
            f"score={result.overall_score:.1f}, passed={result.passed}"
        )

        return result

    def _extract_constraints_from_previous(
        self, previous_chapter: Dict[str, Any]
    ) -> List:
        """从上一章提取约束."""
        from .prevention_continuity_checker import ContinuityConstraint

        constraints = []

        # 从上一章的结尾状态提取期待
        ending_state = previous_chapter.get("ending_state", "")
        if ending_state:
            constraints.append(
                ContinuityConstraint(
                    id="ending_expectation",
                    type="expectation",
                    description=f"读者期待回应上一章的结尾：{ending_state[:100]}",
                    source_chapter=previous_chapter.get("chapter_number", 0),
                    priority=8,
                    category="plot",
                )
            )

        # 从未解决的冲突提取
        unresolved_conflicts = previous_chapter.get("unresolved_conflicts", [])
        for conflict in unresolved_conflicts:
            constraints.append(
                ContinuityConstraint(
                    id=f"conflict_{conflict.get('id', '')}",
                    type="conflict",
                    description=conflict.get("description", ""),
                    source_chapter=conflict.get("start_chapter", 0),
                    priority=conflict.get("importance", 7),
                    category="plot",
                    related_characters=conflict.get("characters", []),
                )
            )

        return constraints

    def _aggregate_issues_and_suggestions(self, result: ContinuityIntegrationResult):
        """汇总问题和建议."""
        issues = []
        suggestions = set()

        # 主题问题
        if result.theme_report:
            if not result.theme_report.passed:
                issues.append(
                    {
                        "component": "theme",
                        "description": "主题一致性审查未通过",
                        "score": result.theme_report.overall_score,
                    }
                )
                suggestions.update(result.theme_report.improvement_suggestions)

        # 大纲问题
        if result.outline_validation:
            if not result.outline_validation.passed:
                issues.append(
                    {
                        "component": "outline",
                        "description": "大纲任务未完成",
                        "completion_rate": result.outline_validation.completion_rate,
                    }
                )
                suggestions.update(result.outline_validation.suggestions)

        # 角色问题
        for char_name, validation in result.character_validations.items():
            if not validation.passed:
                issues.append(
                    {
                        "component": "character",
                        "character": char_name,
                        "description": f"{char_name}的行为不一致",
                        "score": validation.overall_score,
                    }
                )
                suggestions.update(validation.suggestions)

        # 伏笔问题
        if result.foreshadowing_report:
            if result.foreshadowing_report.must_payoff_tasks:
                task_count = len(result.foreshadowing_report.must_payoff_tasks)
                issues.append(
                    {
                        "component": "foreshadowing",
                        "description": f"有{task_count}个关键伏笔必须回收",
                    }
                )
                suggestions.update(result.foreshadowing_report.suggestions)

        # 预防检查问题
        if result.prevention_report:
            if not result.prevention_report.passed:
                issues.extend(
                    [
                        {"component": "prevention", **issue}
                        for issue in result.prevention_report.ignored_constraints
                    ]
                )
                suggestions.update(result.prevention_report.suggestions)

        result.issues = issues
        result.suggestions = list(suggestions)

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息."""
        return {
            "theme_guardian": self.theme_guardian.get_statistics(),
            "outline_mapper": {},  # 大纲映射器无统计方法
            "character_trackers": {
                name: tracker.get_statistics()
                for name, tracker in self.character_trackers.items()
            },
            "foreshadowing_injector": self.foreshadowing_injector.get_statistics(),
            "prevention_checker": self.prevention_checker.get_statistics(),
        }


# 便捷函数
async def create_continuity_module(
    novel_id: str, novel_data: Dict[str, Any]
) -> ContinuityIntegrationModule:
    """便捷函数：创建连贯性模块."""
    module = ContinuityIntegrationModule(novel_id, novel_data)
    return module


async def prepare_for_chapter_generation(
    novel_id: str, novel_data: Dict[str, Any], chapter_number: int, **kwargs
) -> Dict[str, Any]:
    """便捷函数：准备章节生成."""
    module = await create_continuity_module(novel_id, novel_data)
    return await module.prepare_chapter_generation(
        chapter_number=chapter_number, **kwargs
    )
