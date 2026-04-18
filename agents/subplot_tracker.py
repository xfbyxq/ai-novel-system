"""SubplotTracker - 支线情节追踪器.

追踪各支线的使用频率，超过N章未出现的支线主动提醒插入。
集成到 ContinuityIntegrationModule 中。

解决根本问题：
- 6章全是主线推进，无支线缓冲
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from core.logging_config import logger


@dataclass
class SubplotInfo:
    """支线情节信息."""

    name: str  # 支线名称
    description: str  # 支线描述
    status: str = "pending"  # pending/active/resolved/abandoned
    trigger_chapter: int = 0  # 计划触发章节
    last_appearance_chapter: int = 0  # 最近出现章节
    appearance_count: int = 0  # 出现次数
    importance: int = 5  # 重要性 1-10
    involved_characters: List[str] = field(default_factory=list)  # 涉及角色
    resolution_deadline: int = 0  # 回收截止章节
    notes: str = ""

    @property
    def chapters_since_appearance(self) -> int:
        """距离上次出现的章节数."""
        if self.last_appearance_chapter == 0:
            return 999  # 从未出现
        return 0  # 由外部传入当前章节号计算

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "trigger_chapter": self.trigger_chapter,
            "last_appearance_chapter": self.last_appearance_chapter,
            "appearance_count": self.appearance_count,
            "importance": self.importance,
            "involved_characters": self.involved_characters,
            "resolution_deadline": self.resolution_deadline,
            "notes": self.notes,
        }


@dataclass
class SubplotReminder:
    """支线插入提醒."""

    subplot_name: str
    reason: str
    urgency: str  # high/medium/low
    suggested_scene: str  # 建议的插入方式
    involved_characters: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subplot_name": self.subplot_name,
            "reason": self.reason,
            "urgency": self.urgency,
            "suggested_scene": self.suggested_scene,
            "involved_characters": self.involved_characters,
        }

    def to_prompt(self) -> str:
        return (
            f"## 支线插入提醒 — {self.subplot_name}\n"
            f"- 原因：{self.reason}\n"
            f"- 紧急度：{self.urgency}\n"
            f"- 建议方式：{self.suggested_scene}\n"
            f"- 涉及角色：{', '.join(self.involved_characters)}"
        )


class SubplotTracker:
    """支线情节追踪器.

    功能：
    1. 注册支线情节
    2. 追踪支线使用频率
    3. 生成插入提醒
    4. 提供支线规划建议
    """

    def __init__(self, max_chapters_without_appearance: int = 4):
        """初始化支线追踪器.

        Args:
            max_chapters_without_appearance: 支线超过此章数未出现则提醒
        """
        self.max_chapters_without = max_chapters_without_appearance
        self.subplots: Dict[str, SubplotInfo] = {}
        self._chapter_appearances: Dict[int, List[str]] = {}  # {chapter: [subplot_names]}

    def register_subplot(self, subplot: SubplotInfo) -> None:
        """注册支线情节."""
        self.subplots[subplot.name] = subplot
        logger.info(
            f"[SubplotTracker] 注册支线: {subplot.name}, "
            f"触发章节={subplot.trigger_chapter}, "
            f"重要性={subplot.importance}"
        )

    def record_appearance(
        self, chapter_number: int, subplot_names: List[str]
    ) -> None:
        """记录支线在某章的出现."""
        self._chapter_appearances[chapter_number] = subplot_names
        for name in subplot_names:
            if name in self.subplots:
                subplot = self.subplots[name]
                subplot.last_appearance_chapter = chapter_number
                subplot.appearance_count += 1
                if subplot.status == "pending":
                    subplot.status = "active"

    def check_and_remind(
        self, current_chapter: int
    ) -> List[SubplotReminder]:
        """检查并生成支线插入提醒.

        Args:
            current_chapter: 当前章节号

        Returns:
            需要插入的支线提醒列表
        """
        reminders = []

        for name, subplot in self.subplots.items():
            if subplot.status in ("resolved", "abandoned"):
                continue

            # 计算距离上次出现的章数
            chapters_since = current_chapter - subplot.last_appearance_chapter
            if subplot.last_appearance_chapter == 0:
                chapters_since = current_chapter - subplot.trigger_chapter + 1

            # 检查是否需要提醒
            needs_reminder = False
            urgency = "low"
            reason = ""

            if subplot.last_appearance_chapter == 0:
                # 从未出现
                if current_chapter >= subplot.trigger_chapter:
                    needs_reminder = True
                    urgency = "high" if subplot.importance >= 7 else "medium"
                    reason = (
                        f"计划在第{subplot.trigger_chapter}章触发，"
                        f"目前已到第{current_chapter}章"
                    )
            elif chapters_since > self.max_chapters_without:
                # 超过最大间隔
                needs_reminder = True
                urgency = (
                    "high"
                    if chapters_since > self.max_chapters_without * 2
                    else "medium"
                )
                reason = (
                    f"已连续{chapters_since}章未出现"
                    f"（上次在第{subplot.last_appearance_chapter}章）"
                )

            if subplot.resolution_deadline > 0:
                remaining = subplot.resolution_deadline - current_chapter
                if remaining <= 3 and subplot.status != "resolved":
                    needs_reminder = True
                    urgency = "high"
                    reason = f"回收截止章节临近（剩余{remaining}章）"

            if needs_reminder:
                reminder = SubplotReminder(
                    subplot_name=name,
                    reason=reason,
                    urgency=urgency,
                    suggested_scene=self._suggest_insertion(subplot),
                    involved_characters=subplot.involved_characters,
                )
                reminders.append(reminder)

        # 按紧急度排序
        urgency_order = {"high": 0, "medium": 1, "low": 2}
        reminders.sort(key=lambda r: urgency_order.get(r.urgency, 3))

        if reminders:
            logger.info(
                f"[SubplotTracker] 第{current_chapter}章生成 {len(reminders)} 个支线提醒"
            )

        return reminders

    def _suggest_insertion(self, subplot: SubplotInfo) -> str:
        """根据支线类型建议插入方式."""
        suggestions = {
            "身世": "可通过角色发现旧物、偶然对话、梦境等方式引入",
            "感情": "安排日常互动场景，通过细微动作和对话推进感情",
            "复仇": "通过情报传递、意外遭遇、线索发现等方式推进",
            "成长": "修炼场景中穿插内心独白，展现成长感悟",
            "阴谋": "通过配角对话、暗中观察、信息碎片等方式暗示",
        }

        for keyword, suggestion in suggestions.items():
            if keyword in subplot.name or keyword in subplot.description:
                return suggestion

        char_name = (
            subplot.involved_characters[0]
            if subplot.involved_characters
            else "相关角色"
        )
        return f"在{char_name}出场的场景中自然引入"

    def get_subplot_summary(self, current_chapter: int) -> str:
        """获取支线状态摘要（用于注入提示词）."""
        lines = ["## 当前支线状态"]

        active_subplots = [
            s for s in self.subplots.values() if s.status in ("active", "pending")
        ]
        if not active_subplots:
            lines.append("暂无活跃支线")
            return "\n".join(lines)

        for subplot in sorted(
            active_subplots, key=lambda s: s.importance, reverse=True
        ):
            chapters_since = (
                current_chapter - subplot.last_appearance_chapter
                if subplot.last_appearance_chapter > 0
                else current_chapter - subplot.trigger_chapter + 1
            )
            if subplot.last_appearance_chapter == 0:
                status_text = "未触发"
            else:
                status_text = f"已{chapters_since}章未出现"
            lines.append(
                f"- {subplot.name}（重要性{subplot.importance}）: "
                f"状态={subplot.status}, {status_text}, "
                f"已出场{subplot.appearance_count}次"
            )

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subplots": {name: s.to_dict() for name, s in self.subplots.items()},
            "chapter_appearances": {
                str(k): v for k, v in self._chapter_appearances.items()
            },
        }
