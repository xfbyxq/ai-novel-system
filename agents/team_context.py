"""
NovelTeamContext - 小说生成团队共享上下文.

借鉴AgentMesh的TeamContext设计，实现Agent之间的信息共享和状态追踪。

线程安全说明：
- 所有写操作都通过 asyncio.Lock 保护
- 读操作不加锁，返回数据的快照
- 在高并发场景下保证数据一致性
"""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.logging_config import logger


class AgentOutput:
    """Agent输出记录."""

    def __init__(self, agent_name: str, output: Dict[str, Any], subtask: str = ""):
        """初始化方法."""
        self.agent_name = agent_name
        self.output = output
        self.subtask = subtask
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "output": self.output,
            "subtask": self.subtask,
            "timestamp": self.timestamp,
        }


class CharacterState:
    """角色状态追踪."""

    def __init__(self, name: str):
        """初始化方法."""
        self.name = name
        self.last_appearance_chapter: int = 0
        self.current_location: str = ""
        self.cultivation_level: str = ""
        self.emotional_state: str = ""
        self.relationships: Dict[str, str] = {}
        self.status: str = "active"  # active/injured/missing/dead
        self.pending_events: List[Dict[str, Any]] = []
        self.updated_at: str = datetime.now().isoformat()

    def update(self, **kwargs):
        """更新角色状态."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "last_appearance_chapter": self.last_appearance_chapter,
            "current_location": self.current_location,
            "cultivation_level": self.cultivation_level,
            "emotional_state": self.emotional_state,
            "relationships": self.relationships,
            "status": self.status,
            "pending_events": self.pending_events,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterState":
        """从字典创建角色状态."""
        state = cls(data.get("name", ""))
        state.last_appearance_chapter = data.get("last_appearance_chapter", 0)
        state.current_location = data.get("current_location", "")
        state.cultivation_level = data.get("cultivation_level", "")
        state.emotional_state = data.get("emotional_state", "")
        state.relationships = data.get("relationships", {})
        state.status = data.get("status", "active")
        state.pending_events = data.get("pending_events", [])
        state.updated_at = data.get("updated_at", datetime.now().isoformat())
        return state


class TimelineEvent:
    """时间线事件."""

    def __init__(
        self,
        chapter_number: int,
        story_day: int,
        event: str,
        characters: List[str] = None,
        location: str = "",
    ):
        """初始化方法."""
        self.id = str(uuid.uuid4())[:8]
        self.chapter_number = chapter_number
        self.story_day = story_day
        self.event = event
        self.characters = characters or []
        self.location = location
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "chapter_number": self.chapter_number,
            "story_day": self.story_day,
            "event": self.event,
            "characters": self.characters,
            "location": self.location,
            "created_at": self.created_at,
        }


class AgentReview:
    """Agent审查反馈记录."""

    def __init__(
        self,
        reviewer: str,
        target_agent: str,
        task_desc: str,
        score: float,
        passed: bool,
        suggestions: List[Dict[str, str]] = None,
        chapter_number: int = 0,
    ):
        """初始化方法."""
        self.reviewer = reviewer
        self.target_agent = target_agent
        self.task_desc = task_desc
        self.score = score
        self.passed = passed
        self.suggestions = suggestions or []
        self.chapter_number = chapter_number
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reviewer": self.reviewer,
            "target_agent": self.target_agent,
            "task_desc": self.task_desc,
            "score": self.score,
            "passed": self.passed,
            "suggestions": self.suggestions,
            "chapter_number": self.chapter_number,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentReview":
        review = cls(
            reviewer=data.get("reviewer", ""),
            target_agent=data.get("target_agent", ""),
            task_desc=data.get("task_desc", ""),
            score=data.get("score", 0.0),
            passed=data.get("passed", False),
            suggestions=data.get("suggestions", []),
            chapter_number=data.get("chapter_number", 0),
        )
        review.timestamp = data.get("timestamp", datetime.now().isoformat())
        return review


class NovelTeamContext:
    """
    小说生成团队共享上下文.

    借鉴AgentMesh的TeamContext设计，实现：
    1. Agent输出历史追踪
    2. 角色状态管理
    3. 时间线追踪
    4. 伏笔系统集成
    5. 团队规则管理

    线程安全保证：
    - 使用 asyncio.Lock 保护所有写操作
    - 读操作返回数据快照，避免并发修改问题
    """

    def __init__(self, novel_id: str, novel_title: str = ""):
        """初始化方法."""
        self.novel_id = novel_id
        self.novel_title = novel_title

        # 异步锁，保护所有写操作
        self._lock = asyncio.Lock()

        # 小说元数据
        self.novel_metadata: Dict[str, Any] = {}

        # 世界观设定（所有Agent共享）
        self.world_setting: Dict[str, Any] = {}

        # 角色信息
        self.characters: List[Dict[str, Any]] = []

        # 情节大纲
        self.plot_outline: Dict[str, Any] = {}

        # Agent输出历史
        self.agent_outputs: List[AgentOutput] = []

        # 角色状态追踪
        self.character_states: Dict[str, CharacterState] = {}

        # 时间线追踪
        self.timeline: List[TimelineEvent] = []
        self.current_story_day: int = 1

        # 当前章节信息
        self.current_chapter_number: int = 0
        self.current_volume_number: int = 1

        # 团队规则（指导Agent决策）
        self.rule: str = ""

        # 步数计数
        self.current_steps: int = 0
        self.max_steps: int = 100

        # 伏笔追踪器引用（由外部注入）
        self.foreshadowing_tracker = None

        # Agent审查反馈记录
        self.agent_reviews: List[AgentReview] = []

        # 迭代日志：记录 Writer-Editor 等循环的每轮信息
        self.iteration_logs: List[Dict[str, Any]] = []

        # 投票记录
        self.voting_records: List[Dict[str, Any]] = []

        logger.info(f"NovelTeamContext initialized for novel: {novel_id}")

    @asynccontextmanager
    async def _write_lock(self):
        """获取写锁的上下文管理器."""
        async with self._lock:
            yield

    def _acquire_lock_sync(self) -> bool:
        """
        同步方式尝试获取锁（用于非异步上下文）

        注意：这是一个尽力而为的保护，在纯同步代码中使用。
        如果锁已被持有，将立即返回 False 而不是等待。
        """
        try:
            # 检查是否在事件循环中
            asyncio.get_running_loop()
            # 如果在事件循环中，应该使用异步方法
            logger.warning(
                "_acquire_lock_sync called from async context, use async methods instead"
            )
            return False
        except RuntimeError:
            # 不在事件循环中，可以安全地进行同步操作
            return True

    def set_novel_data(self, novel_data: Dict[str, Any]):
        """设置小说基础数据."""
        self.novel_metadata = novel_data.get("metadata", {})
        self.world_setting = novel_data.get("world_setting", {})
        self.characters = novel_data.get("characters", [])
        self.plot_outline = novel_data.get("plot_outline", {})
        self.novel_title = novel_data.get("title", self.novel_title)

        # 初始化角色状态
        for char in self.characters:
            char_name = char.get("name", "")
            if char_name and char_name not in self.character_states:
                self.character_states[char_name] = CharacterState(char_name)
                # 从角色设定初始化状态（兼容不同的数据格式）
                abilities = char.get("abilities", {})
                background = char.get("background", {})

                # abilities 可能是字典或字符串
                cultivation_level = ""
                if isinstance(abilities, dict):
                    cultivation_level = abilities.get("level", "")

                # background 可能是字典或字符串
                starting_location = ""
                if isinstance(background, dict):
                    starting_location = background.get("starting_location", "")

                self.character_states[char_name].update(
                    cultivation_level=cultivation_level,
                    current_location=starting_location,
                )

        logger.info(f"Novel data set: {len(self.characters)} characters initialized")

    def add_agent_output(
        self, agent_name: str, output: Dict[str, Any], subtask: str = ""
    ):
        """记录Agent输出（同步版本，向后兼容）.

        注意：在异步上下文中应优先使用 add_agent_output_async
        """
        agent_output = AgentOutput(agent_name, output, subtask)
        self.agent_outputs.append(agent_output)
        self.current_steps += 1
        logger.debug(f"Agent output added: {agent_name}, steps: {self.current_steps}")

    async def add_agent_output_async(
        self, agent_name: str, output: Dict[str, Any], subtask: str = ""
    ):
        """记录Agent输出（异步版本，线程安全）."""
        async with self._write_lock():
            agent_output = AgentOutput(agent_name, output, subtask)
            self.agent_outputs.append(agent_output)
            self.current_steps += 1
            logger.debug(
                f"Agent output added (async): {agent_name}, steps: {self.current_steps}"
            )

    def get_previous_outputs(self, last_n: int = None) -> str:
        """获取前置Agent的输出（供后续Agent参考）."""
        outputs = self.agent_outputs if last_n is None else self.agent_outputs[-last_n:]

        if not outputs:
            return "（暂无前置Agent输出）"

        result = []
        for o in outputs:
            output_str = (
                json.dumps(o.output, ensure_ascii=False, indent=2)
                if isinstance(o.output, dict)
                else str(o.output)
            )
            # 限制输出长度
            if len(output_str) > 1000:
                output_str = output_str[:1000] + "...(已截断)"
            result.append(f"**{o.agent_name}** ({o.subtask}):\n{output_str}")

        return "\n\n---\n\n".join(result)

    def update_character_state(self, char_name: str, **kwargs):
        """更新角色状态（同步版本）."""
        if char_name not in self.character_states:
            self.character_states[char_name] = CharacterState(char_name)

        self.character_states[char_name].update(**kwargs)
        logger.debug(f"Character state updated: {char_name}")

    async def update_character_state_async(self, char_name: str, **kwargs):
        """更新角色状态（异步版本，线程安全）."""
        async with self._write_lock():
            if char_name not in self.character_states:
                self.character_states[char_name] = CharacterState(char_name)

            self.character_states[char_name].update(**kwargs)
            logger.debug(f"Character state updated (async): {char_name}")

    def get_character_state(self, char_name: str) -> Optional[CharacterState]:
        """获取角色状态."""
        return self.character_states.get(char_name)

    def get_all_character_states(self) -> Dict[str, Dict[str, Any]]:
        """获取所有角色状态."""
        return {name: state.to_dict() for name, state in self.character_states.items()}

    def format_character_states(self, characters: List[str] = None) -> str:
        """格式化角色状态为字符串."""
        if characters:
            states = {
                name: self.character_states[name]
                for name in characters
                if name in self.character_states
            }
        else:
            states = self.character_states

        if not states:
            return "（暂无角色状态记录）"

        result = []
        for name, state in states.items():
            info = [f"**{name}**"]
            if state.current_location:
                info.append(f"  - 位置: {state.current_location}")
            if state.cultivation_level:
                info.append(f"  - 修为: {state.cultivation_level}")
            if state.emotional_state:
                info.append(f"  - 情绪: {state.emotional_state}")
            if state.status != "active":
                info.append(f"  - 状态: {state.status}")
            if state.pending_events:
                events = ", ".join(
                    [e.get("event", "") for e in state.pending_events[:3]]
                )
                info.append(f"  - 待办: {events}")
            result.append("\n".join(info))

        return "\n\n".join(result)

    def add_timeline_event(
        self,
        chapter_number: int,
        event: str,
        characters: List[str] = None,
        location: str = "",
    ):
        """添加时间线事件（同步版本）."""
        timeline_event = TimelineEvent(
            chapter_number=chapter_number,
            story_day=self.current_story_day,
            event=event,
            characters=characters,
            location=location,
        )
        self.timeline.append(timeline_event)
        logger.info(
            f"[Timeline] 事件添加: 第{chapter_number}章, 故事第{self.current_story_day}天"
        )

    async def add_timeline_event_async(
        self,
        chapter_number: int,
        event: str,
        characters: List[str] = None,
        location: str = "",
    ):
        """添加时间线事件（异步版本，线程安全）."""
        async with self._write_lock():
            timeline_event = TimelineEvent(
                chapter_number=chapter_number,
                story_day=self.current_story_day,
                event=event,
                characters=characters,
                location=location,
            )
            self.timeline.append(timeline_event)
            logger.info(
                f"[Timeline] 事件添加(async): 第{chapter_number}章, 故事第{self.current_story_day}天"
            )

    def advance_story_day(self, days: int = 1):
        """推进故事日期（同步版本）."""
        self.current_story_day += days
        logger.debug(f"Story day advanced to: {self.current_story_day}")

    async def advance_story_day_async(self, days: int = 1):
        """推进故事日期（异步版本，线程安全）."""
        async with self._write_lock():
            self.current_story_day += days
            logger.debug(f"Story day advanced (async) to: {self.current_story_day}")

    def get_recent_timeline(self, last_n: int = 10) -> str:
        """获取最近的时间线事件."""
        events = self.timeline[-last_n:] if last_n else self.timeline

        if not events:
            return "（故事刚刚开始）"

        result = []
        for e in events:
            chars = ", ".join(e.characters) if e.characters else "未知"
            result.append(
                f"第{e.chapter_number}章 (第{e.story_day}天): {e.event} [角色: {chars}]"
            )

        return "\n".join(result)

    def set_current_chapter(self, chapter_number: int, volume_number: int = None):
        """设置当前章节."""
        self.current_chapter_number = chapter_number
        if volume_number is not None:
            self.current_volume_number = volume_number

    def get_current_volume_info(self) -> Dict[str, Any]:
        """获取当前卷信息."""
        volumes = self.plot_outline.get("volumes", [])
        if not volumes or self.current_volume_number > len(volumes):
            return {}
        return volumes[self.current_volume_number - 1]

    def add_review(self, review: "AgentReview"):
        """记录一次 Agent 审查反馈（同步版本）."""
        self.agent_reviews.append(review)
        logger.debug(
            f"Review added: {review.reviewer} -> {review.target_agent}, "
            f"score={review.score}, passed={review.passed}"
        )

    async def add_review_async(self, review: "AgentReview"):
        """记录一次 Agent 审查反馈（异步版本，线程安全）."""
        async with self._write_lock():
            self.agent_reviews.append(review)
            logger.debug(
                f"Review added (async): {review.reviewer} -> {review.target_agent}, "
                f"score={review.score}, passed={review.passed}"
            )

    def get_reviews_for_chapter(self, chapter_number: int) -> List["AgentReview"]:
        """获取某章的所有审查反馈."""
        return [r for r in self.agent_reviews if r.chapter_number == chapter_number]

    def add_iteration_log(self, log_entry: Dict[str, Any]):
        """记录一次迭代信息（同步版本）."""
        log_entry.setdefault("timestamp", datetime.now().isoformat())
        self.iteration_logs.append(log_entry)

    async def add_iteration_log_async(self, log_entry: Dict[str, Any]):
        """记录一次迭代信息（异步版本，线程安全）."""
        async with self._write_lock():
            log_entry.setdefault("timestamp", datetime.now().isoformat())
            self.iteration_logs.append(log_entry)

    def add_voting_record(self, record: Dict[str, Any]):
        """记录一次投票结果（同步版本）."""
        record.setdefault("timestamp", datetime.now().isoformat())
        self.voting_records.append(record)

    async def add_voting_record_async(self, record: Dict[str, Any]):
        """记录一次投票结果（异步版本，线程安全）."""
        async with self._write_lock():
            record.setdefault("timestamp", datetime.now().isoformat())
            self.voting_records.append(record)

    def build_enhanced_context(self, chapter_number: int) -> str:
        """
        构建增强的章节上下文.

        整合：当前卷信息、角色状态、时间线、伏笔等
        """
        self.set_current_chapter(chapter_number)

        # 当前卷信息
        current_volume = self.get_current_volume_info()
        volume_info = f"""## 当前卷信息.
卷号：第 {self.current_volume_number} 卷 - {current_volume.get('title', '')}
卷概要：{current_volume.get('summary', '')}
关键事件：{', '.join(current_volume.get('key_events', [])[:5])}"""

        # 角色状态
        character_info = f"""## 主要角色当前状态.
{self.format_character_states()}"""

        # 时间线
        timeline_info = f"""## 时间线进度.
当前是故事的第 {self.current_story_day} 天.
最近事件：
{self.get_recent_timeline(5)}"""

        # 伏笔信息
        foreshadowing_info = ""
        if self.foreshadowing_tracker:
            pending = self.foreshadowing_tracker.get_pending_foreshadowings()
            if pending:
                foreshadowing_list = "\n".join(
                    [
                        f"- 第{f['planted_chapter']}章: {f['content']}"
                        for f in pending[:5]
                    ]
                )
                foreshadowing_info = f"""## 待回收的伏笔.
{foreshadowing_list}"""

        # 组合上下文
        context_parts = [volume_info, character_info, timeline_info]
        if foreshadowing_info:
            context_parts.append(foreshadowing_info)

        return "\n\n".join(context_parts)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "novel_id": self.novel_id,
            "novel_title": self.novel_title,
            "novel_metadata": self.novel_metadata,
            "world_setting": self.world_setting,
            "characters": self.characters,
            "plot_outline": self.plot_outline,
            "agent_outputs": [o.to_dict() for o in self.agent_outputs],
            "character_states": self.get_all_character_states(),
            "timeline": [e.to_dict() for e in self.timeline],
            "current_story_day": self.current_story_day,
            "current_chapter_number": self.current_chapter_number,
            "current_volume_number": self.current_volume_number,
            "rule": self.rule,
            "current_steps": self.current_steps,
            "max_steps": self.max_steps,
            "agent_reviews": [r.to_dict() for r in self.agent_reviews],
            "iteration_logs": self.iteration_logs,
            "voting_records": self.voting_records,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NovelTeamContext":
        """从字典反序列化."""
        ctx = cls(data.get("novel_id", ""), data.get("novel_title", ""))
        ctx.novel_metadata = data.get("novel_metadata", {})
        ctx.world_setting = data.get("world_setting", {})
        ctx.characters = data.get("characters", [])
        ctx.plot_outline = data.get("plot_outline", {})
        ctx.current_story_day = data.get("current_story_day", 1)
        ctx.current_chapter_number = data.get("current_chapter_number", 0)
        ctx.current_volume_number = data.get("current_volume_number", 1)
        ctx.rule = data.get("rule", "")
        ctx.current_steps = data.get("current_steps", 0)
        ctx.max_steps = data.get("max_steps", 100)

        # 恢复角色状态
        for name, state_data in data.get("character_states", {}).items():
            ctx.character_states[name] = CharacterState.from_dict(state_data)

        # 恢复Agent输出
        for output_data in data.get("agent_outputs", []):
            output = AgentOutput(
                output_data.get("agent_name", ""),
                output_data.get("output", {}),
                output_data.get("subtask", ""),
            )
            output.timestamp = output_data.get("timestamp", "")
            ctx.agent_outputs.append(output)

        # 恢复审查反馈
        for review_data in data.get("agent_reviews", []):
            ctx.agent_reviews.append(AgentReview.from_dict(review_data))

        # 恢复迭代日志和投票记录
        ctx.iteration_logs = data.get("iteration_logs", [])
        ctx.voting_records = data.get("voting_records", [])

        return ctx
