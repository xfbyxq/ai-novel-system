"""
NovelTeamContext - 小说生成团队共享上下文

借鉴AgentMesh的TeamContext设计，实现Agent之间的信息共享和状态追踪。
"""
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.logging_config import logger


class AgentOutput:
    """Agent输出记录"""

    def __init__(self, agent_name: str, output: Dict[str, Any], subtask: str = ""):
        self.agent_name = agent_name
        self.output = output
        self.subtask = subtask
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "output": self.output,
            "subtask": self.subtask,
            "timestamp": self.timestamp
        }


class CharacterState:
    """角色状态追踪"""

    def __init__(self, name: str):
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
        """更新角色状态"""
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
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterState":
        """从字典创建角色状态"""
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
    """时间线事件"""

    def __init__(self, chapter_number: int, story_day: int, event: str,
                 characters: List[str] = None, location: str = ""):
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
            "created_at": self.created_at
        }


class NovelTeamContext:
    """
    小说生成团队共享上下文
    
    借鉴AgentMesh的TeamContext设计，实现：
    1. Agent输出历史追踪
    2. 角色状态管理
    3. 时间线追踪
    4. 伏笔系统集成
    5. 团队规则管理
    """

    def __init__(self, novel_id: str, novel_title: str = ""):
        self.novel_id = novel_id
        self.novel_title = novel_title

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

        logger.info(f"NovelTeamContext initialized for novel: {novel_id}")

    def set_novel_data(self, novel_data: Dict[str, Any]):
        """设置小说基础数据"""
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
                    current_location=starting_location
                )

        logger.info(f"Novel data set: {len(self.characters)} characters initialized")

    def add_agent_output(self, agent_name: str, output: Dict[str, Any], subtask: str = ""):
        """记录Agent输出"""
        agent_output = AgentOutput(agent_name, output, subtask)
        self.agent_outputs.append(agent_output)
        self.current_steps += 1
        logger.debug(f"Agent output added: {agent_name}, steps: {self.current_steps}")

    def get_previous_outputs(self, last_n: int = None) -> str:
        """获取前置Agent的输出（供后续Agent参考）"""
        outputs = self.agent_outputs if last_n is None else self.agent_outputs[-last_n:]

        if not outputs:
            return "（暂无前置Agent输出）"

        result = []
        for o in outputs:
            output_str = json.dumps(o.output, ensure_ascii=False, indent=2) if isinstance(o.output, dict) else str(o.output)
            # 限制输出长度
            if len(output_str) > 1000:
                output_str = output_str[:1000] + "...(已截断)"
            result.append(f"**{o.agent_name}** ({o.subtask}):\n{output_str}")

        return "\n\n---\n\n".join(result)

    def update_character_state(self, char_name: str, **kwargs):
        """更新角色状态"""
        if char_name not in self.character_states:
            self.character_states[char_name] = CharacterState(char_name)

        self.character_states[char_name].update(**kwargs)
        logger.debug(f"Character state updated: {char_name}")

    def get_character_state(self, char_name: str) -> Optional[CharacterState]:
        """获取角色状态"""
        return self.character_states.get(char_name)

    def get_all_character_states(self) -> Dict[str, Dict[str, Any]]:
        """获取所有角色状态"""
        return {name: state.to_dict() for name, state in self.character_states.items()}

    def format_character_states(self, characters: List[str] = None) -> str:
        """格式化角色状态为字符串"""
        if characters:
            states = {name: self.character_states[name]
                     for name in characters if name in self.character_states}
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
                events = ", ".join([e.get("event", "") for e in state.pending_events[:3]])
                info.append(f"  - 待办: {events}")
            result.append("\n".join(info))

        return "\n\n".join(result)

    def add_timeline_event(self, chapter_number: int, event: str,
                          characters: List[str] = None, location: str = ""):
        """添加时间线事件"""
        timeline_event = TimelineEvent(
            chapter_number=chapter_number,
            story_day=self.current_story_day,
            event=event,
            characters=characters,
            location=location
        )
        self.timeline.append(timeline_event)
        logger.debug(f"Timeline event added: chapter {chapter_number}, day {self.current_story_day}")

    def advance_story_day(self, days: int = 1):
        """推进故事日期"""
        self.current_story_day += days
        logger.debug(f"Story day advanced to: {self.current_story_day}")

    def get_recent_timeline(self, last_n: int = 10) -> str:
        """获取最近的时间线事件"""
        events = self.timeline[-last_n:] if last_n else self.timeline

        if not events:
            return "（故事刚刚开始）"

        result = []
        for e in events:
            chars = ", ".join(e.characters) if e.characters else "未知"
            result.append(f"第{e.chapter_number}章 (第{e.story_day}天): {e.event} [角色: {chars}]")

        return "\n".join(result)

    def set_current_chapter(self, chapter_number: int, volume_number: int = None):
        """设置当前章节"""
        self.current_chapter_number = chapter_number
        if volume_number is not None:
            self.current_volume_number = volume_number

    def get_current_volume_info(self) -> Dict[str, Any]:
        """获取当前卷信息"""
        volumes = self.plot_outline.get("volumes", [])
        if not volumes or self.current_volume_number > len(volumes):
            return {}
        return volumes[self.current_volume_number - 1]

    def build_enhanced_context(self, chapter_number: int) -> str:
        """
        构建增强的章节上下文
        
        整合：当前卷信息、角色状态、时间线、伏笔等
        """
        self.set_current_chapter(chapter_number)

        # 当前卷信息
        current_volume = self.get_current_volume_info()
        volume_info = f"""## 当前卷信息
卷号：第 {self.current_volume_number} 卷 - {current_volume.get('title', '')}
卷概要：{current_volume.get('summary', '')}
关键事件：{', '.join(current_volume.get('key_events', [])[:5])}"""

        # 角色状态
        character_info = f"""## 主要角色当前状态
{self.format_character_states()}"""

        # 时间线
        timeline_info = f"""## 时间线进度
当前是故事的第 {self.current_story_day} 天
最近事件：
{self.get_recent_timeline(5)}"""

        # 伏笔信息
        foreshadowing_info = ""
        if self.foreshadowing_tracker:
            pending = self.foreshadowing_tracker.get_pending_foreshadowings()
            if pending:
                foreshadowing_list = "\n".join([
                    f"- 第{f['planted_chapter']}章: {f['content']}"
                    for f in pending[:5]
                ])
                foreshadowing_info = f"""## 待回收的伏笔
{foreshadowing_list}"""

        # 组合上下文
        context_parts = [volume_info, character_info, timeline_info]
        if foreshadowing_info:
            context_parts.append(foreshadowing_info)

        return "\n\n".join(context_parts)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
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
            "max_steps": self.max_steps
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NovelTeamContext":
        """从字典反序列化"""
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
                output_data.get("subtask", "")
            )
            output.timestamp = output_data.get("timestamp", "")
            ctx.agent_outputs.append(output)

        return ctx
