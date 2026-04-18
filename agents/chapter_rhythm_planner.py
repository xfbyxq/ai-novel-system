"""ChapterRhythmPlanner - 章节节奏规划器.

在章节策划之前调用，为每章分配类型标签，确保节奏多样化。
防止连续战斗章节、确保日常/情感章节的适当穿插。

解决根本问题：
- 6章中4章包含战斗，节奏全部高紧张
- 缺乏支线缓冲
- "敌人来袭→秒杀→发现线索"固定模式
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from core.logging_config import logger


class ChapterType(str, Enum):
    """章节类型枚举."""

    BATTLE = "战斗"  # 高紧张，动作驱动
    DAILY = "日常"  # 低紧张，情感/互动驱动
    TRAINING = "修炼"  # 中紧张，成长驱动
    EXPLORATION = "探索"  # 中紧张，世界观驱动
    PLOT_TWIST = "转折"  # 高紧张，信息驱动
    EMOTIONAL = "情感"  # 中紧张，关系驱动
    SETUP = "铺垫"  # 低紧张，伏笔驱动


@dataclass
class TensionLevel:
    """紧张度级别."""

    name: str
    value: int  # 1-10

    @classmethod
    def for_type(cls, chapter_type: ChapterType) -> "TensionLevel":
        """根据章节类型返回默认紧张度."""
        mapping = {
            ChapterType.BATTLE: ("高", 9),
            ChapterType.PLOT_TWIST: ("高", 8),
            ChapterType.TRAINING: ("中", 6),
            ChapterType.EXPLORATION: ("中", 5),
            ChapterType.EMOTIONAL: ("中", 5),
            ChapterType.DAILY: ("低", 3),
            ChapterType.SETUP: ("低", 3),
        }
        name, value = mapping.get(chapter_type, ("中", 5))
        return cls(name=name, value=value)


@dataclass
class ChapterRhythmPlan:
    """单章节奏规划.

    为每章分配类型、紧张度、节奏建议。
    """

    chapter_number: int
    chapter_type: ChapterType
    tension_level: TensionLevel
    recommended_payoff_type: str  # 爽感类型
    recommended_emotional_arc: str  # 情绪弧线
    notes: str = ""  # 规划说明
    subplot_reminder: str = ""  # 支线提醒

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_number": self.chapter_number,
            "chapter_type": self.chapter_type.value,
            "tension_level": self.tension_level.name,
            "tension_value": self.tension_level.value,
            "recommended_payoff_type": self.recommended_payoff_type,
            "recommended_emotional_arc": self.recommended_emotional_arc,
            "notes": self.notes,
            "subplot_reminder": self.subplot_reminder,
        }

    def to_writer_prompt(self) -> str:
        """转换为注入 Writer 提示词的格式."""
        lines = [
            "## 本章节奏规划",
            f"- 章节类型：{self.chapter_type.value}",
            f"- 紧张度：{self.tension_level.name}",
            f"- 推荐爽感类型：{self.recommended_payoff_type}",
            f"- 情绪弧线：{self.recommended_emotional_arc}",
        ]
        if self.notes:
            lines.append(f"- 说明：{self.notes}")
        if self.subplot_reminder:
            lines.append(f"- 支线提醒：{self.subplot_reminder}")
        return "\n".join(lines)


@dataclass
class VolumeRhythmPlan:
    """整卷节奏规划."""

    volume_number: int
    chapter_plans: List[ChapterRhythmPlan] = field(default_factory=list)
    tension_curve: List[int] = field(default_factory=list)
    type_distribution: Dict[str, int] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """检查节奏规划是否合理."""
        return self._check_no_consecutive_battles() and self._check_type_diversity()

    def _check_no_consecutive_battles(self) -> bool:
        """检查是否超过连续战斗章节上限."""
        max_consecutive = 2
        consecutive = 0
        for plan in self.chapter_plans:
            if plan.chapter_type == ChapterType.BATTLE:
                consecutive += 1
                if consecutive > max_consecutive:
                    return False
            else:
                consecutive = 0
        return True

    def _check_type_diversity(self) -> bool:
        """检查章节类型是否足够多样."""
        if len(self.chapter_plans) < 5:
            return True  # 章节数不足时不强制
        # 至少需要3种不同类型的章节
        return len(self.type_distribution) >= 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "volume_number": self.volume_number,
            "chapter_plans": [p.to_dict() for p in self.chapter_plans],
            "tension_curve": self.tension_curve,
            "type_distribution": self.type_distribution,
            "is_valid": self.is_valid,
        }


class ChapterRhythmPlanner:
    """章节节奏规划器.

    核心规则：
    1. 连续战斗章节不超过 2 章
    2. 每 5 章至少 1 章日常或情感类
    3. 紧张度曲线遵循波浪形
    4. 每卷至少包含 1 章探索类（世界观扩展）
    """

    # 爽感类型映射
    PAYOFF_MAP = {
        ChapterType.BATTLE: "face_slap/revenge",
        ChapterType.TRAINING: "upgrade",
        ChapterType.EXPLORATION: "reveal",
        ChapterType.PLOT_TWIST: "reveal/reversal",
        ChapterType.EMOTIONAL: "reunion",
        ChapterType.DAILY: "none",
        ChapterType.SETUP: "suspense",
    }

    # 情绪弧线映射
    EMOTIONAL_ARC_MAP = {
        ChapterType.BATTLE: "buildup→release",
        ChapterType.TRAINING: "suppress→buildup",
        ChapterType.EXPLORATION: "curiosity→reveal",
        ChapterType.PLOT_TWIST: "calm→climax",
        ChapterType.EMOTIONAL: "tension→warmth",
        ChapterType.DAILY: "warmth→humor",
        ChapterType.SETUP: "calm→tension",
    }

    # 战斗章节后的建议类型（打破固定模式）
    BATTLE_FOLLOWUPS = [
        ChapterType.EMOTIONAL,
        ChapterType.DAILY,
        ChapterType.EXPLORATION,
        ChapterType.SETUP,
    ]

    def __init__(
        self,
        max_consecutive_battles: int = 2,
        min_daily_per_5: int = 1,
    ):
        """初始化节奏规划器.

        Args:
            max_consecutive_battles: 连续战斗章节上限
            min_daily_per_5: 每5章至少的日常章节数
        """
        self.max_consecutive_battles = max_consecutive_battles
        self.min_daily_per_5 = min_daily_per_5

    def plan_chapter(
        self,
        chapter_number: int,
        previous_types: Optional[List[ChapterType]] = None,
        suggested_type: Optional[ChapterType] = None,
    ) -> ChapterRhythmPlan:
        """为单章规划节奏.

        Args:
            chapter_number: 章节号
            previous_types: 前序章节的类型列表
            suggested_type: 建议的类型（可选，来自大纲）

        Returns:
            ChapterRhythmPlan
        """
        prev = previous_types or []

        # 确定本章类型
        if suggested_type:
            chapter_type = suggested_type
        else:
            chapter_type = self._determine_type(prev)

        # 紧张度
        tension = TensionLevel.for_type(chapter_type)

        # 爽感类型
        payoff = self.PAYOFF_MAP.get(chapter_type, "none")

        # 情绪弧线
        emotional_arc = self.EMOTIONAL_ARC_MAP.get(chapter_type, "calm→buildup")

        # 生成说明
        notes = self._generate_notes(chapter_type, prev)

        return ChapterRhythmPlan(
            chapter_number=chapter_number,
            chapter_type=chapter_type,
            tension_level=tension,
            recommended_payoff_type=payoff,
            recommended_emotional_arc=emotional_arc,
            notes=notes,
        )

    def plan_volume(
        self,
        volume_number: int,
        chapter_range: tuple,
        volume_summary: str = "",
    ) -> VolumeRhythmPlan:
        """为整卷规划节奏.

        Args:
            volume_number: 卷号
            chapter_range: (起始章, 结束章)
            volume_summary: 卷概要

        Returns:
            VolumeRhythmPlan
        """
        start, end = chapter_range
        plan = VolumeRhythmPlan(volume_number=volume_number)

        prev_types: List[ChapterType] = []
        for ch_num in range(start, end + 1):
            chapter_plan = self.plan_chapter(ch_num, prev_types)
            plan.chapter_plans.append(chapter_plan)
            plan.tension_curve.append(chapter_plan.tension_level.value)
            type_name = chapter_plan.chapter_type.value
            plan.type_distribution[type_name] = (
                plan.type_distribution.get(type_name, 0) + 1
            )
            prev_types.append(chapter_plan.chapter_type)

        # 验证并修正
        if not plan.is_valid:
            self._fix_volume_plan(plan)

        logger.info(
            f"[RhythmPlanner] 第{volume_number}卷节奏规划完成: "
            f"{len(plan.chapter_plans)}章, "
            f"类型分布: {plan.type_distribution}, "
            f"验证: {'通过' if plan.is_valid else '需修正'}"
        )

        return plan

    def _determine_type(self, previous_types: List[ChapterType]) -> ChapterType:
        """基于前序章节类型确定本章类型."""
        if not previous_types:
            return ChapterType.BATTLE  # 第一章默认战斗/冲突

        # 规则1：连续战斗章节不超过上限
        consecutive_battles = 0
        for t in reversed(previous_types):
            if t == ChapterType.BATTLE:
                consecutive_battles += 1
            else:
                break

        if consecutive_battles >= self.max_consecutive_battles:
            # 必须切换到非战斗类型
            return self.BATTLE_FOLLOWUPS[consecutive_battles % len(self.BATTLE_FOLLOWUPS)]

        # 规则2：每5章至少1章日常/情感
        recent_5 = previous_types[-5:] if len(previous_types) >= 5 else previous_types
        daily_count = sum(
            1 for t in recent_5 if t in (ChapterType.DAILY, ChapterType.EMOTIONAL)
        )
        if daily_count < self.min_daily_per_5 and len(recent_5) >= 5:
            return ChapterType.DAILY if len(previous_types) % 2 == 0 else ChapterType.EMOTIONAL

        # 规则3：波浪形紧张度 - 如果连续3章高紧张，插入低紧张
        recent_3 = previous_types[-3:] if len(previous_types) >= 3 else previous_types
        high_tension_types = {ChapterType.BATTLE, ChapterType.PLOT_TWIST}
        if all(t in high_tension_types for t in recent_3):
            return ChapterType.SETUP

        # 默认：交替使用
        type_cycle = [
            ChapterType.BATTLE,
            ChapterType.TRAINING,
            ChapterType.EXPLORATION,
            ChapterType.EMOTIONAL,
            ChapterType.SETUP,
            ChapterType.BATTLE,
            ChapterType.PLOT_TWIST,
            ChapterType.DAILY,
        ]
        idx = len(previous_types) % len(type_cycle)
        return type_cycle[idx]

    def _generate_notes(
        self, chapter_type: ChapterType, previous_types: List[ChapterType]
    ) -> str:
        """生成规划说明."""
        notes_map = {
            ChapterType.BATTLE: "战斗章节注意：打脸场景需写旁观者反应，放大爽感",
            ChapterType.DAILY: "日常章节：增加角色互动、幽默元素、世界观自然展示",
            ChapterType.TRAINING: "修炼章节：升级需仪式感，描写变化过程和自身感受",
            ChapterType.EXPLORATION: "探索章节：通过角色发现自然展现世界观设定",
            ChapterType.PLOT_TWIST: "转折章节：信息揭露需有铺垫，制造意外但合理的感觉",
            ChapterType.EMOTIONAL: "情感章节：重要情感时刻用内心+身体反应+环境呼应三重表达",
            ChapterType.SETUP: "铺垫章节：埋设伏笔，为后续高潮做铺垫，章末留强悬念",
        }
        return notes_map.get(chapter_type, "")

    def _fix_volume_plan(self, plan: VolumeRhythmPlan) -> None:
        """修正不合理的卷节奏规划."""
        # 修正连续战斗
        consecutive = 0
        for i, cp in enumerate(plan.chapter_plans):
            if cp.chapter_type == ChapterType.BATTLE:
                consecutive += 1
                if consecutive > self.max_consecutive_battles:
                    # 将后续战斗章改为情感章
                    plan.chapter_plans[i].chapter_type = ChapterType.EMOTIONAL
                    plan.chapter_plans[i].tension_level = TensionLevel.for_type(
                        ChapterType.EMOTIONAL
                    )
                    plan.chapter_plans[i].notes = "（节奏修正：连续战斗过多，改为情感章节）"
            else:
                consecutive = 0

        # 重新计算分布
        plan.type_distribution = {}
        plan.tension_curve = []
        for cp in plan.chapter_plans:
            type_name = cp.chapter_type.value
            plan.type_distribution[type_name] = plan.type_distribution.get(type_name, 0) + 1
            plan.tension_curve.append(cp.tension_level.value)

    def build_planner_prompt(self, chapter_plan: ChapterRhythmPlan) -> str:
        """构建注入 ChapterPlanner 提示词的节奏约束文本."""
        lines = [
            "## 本章节奏规划（你必须遵循）",
            chapter_plan.to_writer_prompt(),
            "",
            "**注意事项**：",
        ]

        if chapter_plan.chapter_type == ChapterType.BATTLE:
            lines.extend([
                "- 本章为战斗类型，必须设计有层次的冲突：压制→蓄力→释放",
                "- 必须有旁观者反应描写，放大爽感",
                "- 战斗解决方式不要只用'秒杀'，考虑智谋/环境利用/能力克制等",
            ])
        elif chapter_plan.chapter_type == ChapterType.DAILY:
            lines.extend([
                "- 本章为日常类型，重点刻画角色互动和情感交流",
                "- 至少包含1处幽默元素（自嘲/吐槽/反差笑点/俏皮对话）",
                "- 可通过日常对话自然展现世界观设定",
            ])
        elif chapter_plan.chapter_type == ChapterType.EXPLORATION:
            lines.extend([
                "- 本章为探索类型，通过角色探索发现来推进剧情",
                "- 世界观设定需通过角色行动和对话展现，禁止百科式说明",
                "- 章末必须有新发现或悬念",
            ])

        return "\n".join(lines)
