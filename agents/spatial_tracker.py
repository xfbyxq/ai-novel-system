"""空间位置追踪器 - 建立地理位置图谱，追踪角色位置变化，检测空间不一致.

核心功能：
1. 注册和管理地理位置（支持层级关系和连接关系）
2. 记录角色在各章节的空间位置变化
3. 检测空间一致性问题（瞬移、旅行时间矛盾等）
4. 为写作提供空间上下文提示

解决的根本问题：
- 角色瞬移（位置变化无描述）
- 旅行时间不合理
- 场景描述矛盾
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from agents.base.json_extractor import JsonExtractor
from core.logging_config import logger
from llm.qwen_client import qwen_client


@dataclass
class Location:
    """地理位置.

    Attributes:
        location_id: 位置唯一标识（自动生成的8位UUID）
        name: 位置名称
        description: 位置描述
        parent_location: 上级位置ID（如"苍穹城·中央广场"的上级是"苍穹城"）
        connected_locations: 相邻位置ID列表
        travel_times: 到其他位置的旅行时间描述 {位置ID: 旅行时间}
        first_mentioned_chapter: 首次提及的章节号
        tags: 位置标签（如"城市"、"森林"、"室内"等）
        created_at: 创建时间
    """

    location_id: str = field(default_factory=lambda: uuid4().hex[:8])
    name: str = ""
    description: str = ""
    parent_location: Optional[str] = None
    connected_locations: List[str] = field(default_factory=list)
    travel_times: Dict[str, str] = field(default_factory=dict)
    first_mentioned_chapter: int = 1
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "location_id": self.location_id,
            "name": self.name,
            "description": self.description,
            "parent_location": self.parent_location,
            "connected_locations": self.connected_locations,
            "travel_times": self.travel_times,
            "first_mentioned_chapter": self.first_mentioned_chapter,
            "tags": self.tags,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Location":
        """从字典创建."""
        return cls(
            location_id=data.get("location_id", uuid4().hex[:8]),
            name=data.get("name", ""),
            description=data.get("description", ""),
            parent_location=data.get("parent_location"),
            connected_locations=data.get("connected_locations", []),
            travel_times=data.get("travel_times", {}),
            first_mentioned_chapter=data.get("first_mentioned_chapter", 1),
            tags=data.get("tags", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


@dataclass
class CharacterPosition:
    """角色空间位置记录.

    Attributes:
        character_name: 角色名称
        location_id: 位置ID
        location_name: 位置名称（冗余存储，便于显示）
        chapter_number: 章节号
        arrival_method: 到达方式（步行|传送|骑马|飞行等）
        scene_description: 场景描述片段
        timestamp: 记录时间
    """

    character_name: str = ""
    location_id: str = ""
    location_name: str = ""
    chapter_number: int = 0
    arrival_method: str = ""
    scene_description: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "character_name": self.character_name,
            "location_id": self.location_id,
            "location_name": self.location_name,
            "chapter_number": self.chapter_number,
            "arrival_method": self.arrival_method,
            "scene_description": self.scene_description,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterPosition":
        """从字典创建."""
        return cls(
            character_name=data.get("character_name", ""),
            location_id=data.get("location_id", ""),
            location_name=data.get("location_name", ""),
            chapter_number=data.get("chapter_number", 0),
            arrival_method=data.get("arrival_method", ""),
            scene_description=data.get("scene_description", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )


@dataclass
class SpatialIssue:
    """空间一致性问题.

    Attributes:
        issue_type: 问题类型（teleportation|travel_time|location_conflict|scene_jump）
        character: 角色名称
        from_location: 起始位置
        to_location: 目标位置
        from_chapter: 起始章节
        to_chapter: 目标章节
        description: 问题描述
        severity: 严重程度（critical|high|medium|low）
        suggested_fix: 建议修复方案
    """

    issue_type: str = ""
    character: str = ""
    from_location: str = ""
    to_location: str = ""
    from_chapter: int = 0
    to_chapter: int = 0
    description: str = ""
    severity: str = "medium"
    suggested_fix: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "issue_type": self.issue_type,
            "character": self.character,
            "from_location": self.from_location,
            "to_location": self.to_location,
            "from_chapter": self.from_chapter,
            "to_chapter": self.to_chapter,
            "description": self.description,
            "severity": self.severity,
            "suggested_fix": self.suggested_fix,
        }


class SpatialTracker:
    """空间位置追踪器.

    建立地理位置图谱，追踪角色位置变化，检测空间不一致。
    支持位置的层级关系、连接关系和旅行时间记录。

    Attributes:
        locations: 位置字典 {location_id: Location}
        _name_index: 名称索引 {name: location_id}
        character_positions: 角色位置记录 {character_name: [CharacterPosition]}
    """

    # 已知的快速旅行方式（不需要旅行时间描述）
    FAST_TRAVEL_METHODS = {"传送", "传送阵", "空间魔法", "瞬移", "神行", "遁术"}

    def __init__(self, novel_data: Optional[Dict[str, Any]] = None) -> None:
        """初始化空间追踪器.

        Args:
            novel_data: 小说数据，用于提取初始位置信息
        """
        self.locations: Dict[str, Location] = {}
        self._name_index: Dict[str, str] = {}
        self.character_positions: Dict[str, List[CharacterPosition]] = {}

        # 从 novel_data 提取初始位置信息
        if novel_data:
            self._initialize_from_novel_data(novel_data)

    def _initialize_from_novel_data(self, novel_data: Dict[str, Any]) -> None:
        """从小说数据初始化位置信息.

        Args:
            novel_data: 小说数据字典
        """
        # 从世界观设定中提取位置
        world_setting = novel_data.get("world_setting", {})
        if isinstance(world_setting, dict):
            locations_data = world_setting.get("locations", [])
            if isinstance(locations_data, list):
                for loc_data in locations_data:
                    if isinstance(loc_data, dict):
                        name = loc_data.get("name", "")
                        if name:
                            self.register_location(
                                name=name,
                                description=loc_data.get("description", ""),
                                chapter=1,
                                tags=loc_data.get("tags", []),
                            )

        # 从角色设定中提取初始位置
        characters = novel_data.get("characters", [])
        if isinstance(characters, list):
            for char_data in characters:
                if isinstance(char_data, dict):
                    char_name = char_data.get("name", "")
                    initial_location = char_data.get("initial_location", "")
                    if char_name and initial_location:
                        self.record_character_position(
                            character=char_name,
                            location_name=initial_location,
                            chapter=0,  # 第0章表示初始状态
                            method="初始位置",
                        )

    def register_location(
        self,
        name: str,
        description: str,
        chapter: int,
        parent: Optional[str] = None,
        connections: Optional[List[str]] = None,
        travel_times: Optional[Dict[str, str]] = None,
    ) -> str:
        """注册新位置.

        如果同名位置已存在则返回已有ID，否则创建新位置。

        Args:
            name: 位置名称
            description: 位置描述
            chapter: 首次提及的章节号
            parent: 上级位置名称或ID
            connections: 相邻位置名称或ID列表
            travel_times: 旅行时间描述 {位置名称或ID: 旅行时间}

        Returns:
            位置ID
        """
        # 检查是否已存在同名位置（支持模糊匹配）
        existing = self.get_location_by_name(name)
        if existing:
            logger.debug(f"位置 '{name}' 已存在，返回已有ID: {existing.location_id}")
            return existing.location_id

        # 创建新位置
        location = Location(
            name=name,
            description=description,
            first_mentioned_chapter=chapter,
        )

        # 处理上级位置
        if parent:
            parent_loc = self.get_location_by_name(parent)
            if parent_loc:
                location.parent_location = parent_loc.location_id
            else:
                # 上级位置不存在，先注册
                parent_id = self.register_location(
                    name=parent,
                    description=f"{parent}（上级位置）",
                    chapter=chapter,
                )
                location.parent_location = parent_id

        # 处理相邻位置
        if connections:
            for conn in connections:
                conn_loc = self.get_location_by_name(conn)
                if conn_loc:
                    if conn_loc.location_id not in location.connected_locations:
                        location.connected_locations.append(conn_loc.location_id)
                else:
                    # 相邻位置不存在，先注册
                    conn_id = self.register_location(
                        name=conn,
                        description=f"{conn}（相邻位置）",
                        chapter=chapter,
                    )
                    if conn_id not in location.connected_locations:
                        location.connected_locations.append(conn_id)

        # 处理旅行时间
        if travel_times:
            for dest_name, time_desc in travel_times.items():
                dest_loc = self.get_location_by_name(dest_name)
                if dest_loc:
                    location.travel_times[dest_loc.location_id] = time_desc
                else:
                    # 目标位置不存在，先注册
                    dest_id = self.register_location(
                        name=dest_name,
                        description=f"{dest_name}（关联位置）",
                        chapter=chapter,
                    )
                    location.travel_times[dest_id] = time_desc

        # 添加到字典和索引
        self.locations[location.location_id] = location
        self._name_index[name.lower()] = location.location_id

        logger.info(f"注册新位置: {name} (ID: {location.location_id})")
        return location.location_id

    def record_character_position(
        self,
        character: str,
        location_name: str,
        chapter: int,
        method: str = "",
        scene_description: str = "",
    ) -> None:
        """记录角色的空间位置.

        如果位置尚未注册，自动注册。

        Args:
            character: 角色名称
            location_name: 位置名称
            chapter: 章节号
            method: 到达方式
            scene_description: 场景描述片段
        """
        # 查找或注册位置
        location = self.get_location_by_name(location_name)
        if not location:
            location_id = self.register_location(
                name=location_name,
                description="",
                chapter=chapter,
            )
            location = self.locations.get(location_id)

        if not location:
            logger.error(f"无法注册位置: {location_name}")
            return

        # 创建位置记录
        position = CharacterPosition(
            character_name=character,
            location_id=location.location_id,
            location_name=location.name,
            chapter_number=chapter,
            arrival_method=method,
            scene_description=scene_description,
        )

        # 添加到角色位置列表
        if character not in self.character_positions:
            self.character_positions[character] = []
        self.character_positions[character].append(position)

        logger.debug(
            f"记录角色位置: {character} 在第{chapter}章位于 {location_name}，"
            f"到达方式: {method or '未指定'}"
        )

    def get_character_last_position(
        self, character: str
    ) -> Optional[CharacterPosition]:
        """获取角色最后已知的位置.

        Args:
            character: 角色名称

        Returns:
            最后的位置记录，如果不存在则返回 None
        """
        positions = self.character_positions.get(character, [])
        if not positions:
            return None
        return max(positions, key=lambda p: p.chapter_number)

    def get_location_by_name(self, name: str) -> Optional[Location]:
        """按名称查找位置.

        支持模糊匹配：
        1. 精确匹配（不区分大小写）
        2. 包含匹配（如"苍穹城"匹配"苍穹城·中央广场"）
        3. 被包含匹配（如"苍穹城·中央广场"匹配"苍穹城"）

        Args:
            name: 位置名称

        Returns:
            位置对象，如果不存在则返回 None
        """
        if not name:
            return None

        name_lower = name.lower()

        # 精确匹配
        if name_lower in self._name_index:
            return self.locations.get(self._name_index[name_lower])

        # 模糊匹配
        for loc_name, loc_id in self._name_index.items():
            # 包含匹配
            if name_lower in loc_name or loc_name in name_lower:
                return self.locations.get(loc_id)

        # 分隔符匹配（处理"苍穹城·中央广场"格式）
        if "·" in name:
            parts = name.split("·")
            for part in parts:
                part_lower = part.lower()
                if part_lower in self._name_index:
                    return self.locations.get(self._name_index[part_lower])

        return None

    def get_characters_at_location(self, location_name: str, chapter: int) -> List[str]:
        """获取某章节中某位置的所有角色.

        Args:
            location_name: 位置名称
            chapter: 章节号

        Returns:
            角色名称列表
        """
        location = self.get_location_by_name(location_name)
        if not location:
            return []

        characters = []
        for char_name, positions in self.character_positions.items():
            # 查找该章节中该角色的位置
            for pos in positions:
                if pos.chapter_number == chapter and pos.location_id == location.location_id:
                    characters.append(char_name)
                    break

        return characters

    async def extract_locations_from_text(
        self,
        chapter_content: str,
        chapter_number: int,
    ) -> List[Location]:
        """使用 LLM 从章节文本中提取位置和角色位置信息.

        提取的信息：
        1. 新出现的地点名称和描述
        2. 各角色在本章的位置变化
        3. 地点之间的关系（距离、方位等）

        提取后自动更新内部状态。

        Args:
            chapter_content: 章节内容
            chapter_number: 章节号

        Returns:
            提取到的新位置列表
        """
        prompt = f"""请从以下章节内容中提取空间位置信息。

章节内容：
{chapter_content[:8000]}

请提取以下信息并以JSON格式返回：

1. **地点信息**：新出现或有详细描述的地点
   - name: 地点名称
   - description: 地点描述（如果有）
   - parent: 上级位置（如"苍穹城"是"苍穹城·中央广场"的上级）
   - connections: 相邻或可达的位置列表
   - travel_times: 到其他位置的旅行时间描述

2. **角色位置变化**：角色在本章的位置移动
   - character: 角色名称
   - location: 所在位置
   - arrival_method: 到达方式（步行、传送、骑马、飞行等，如果描述了）
   - scene_description: 相关场景描述片段

请以以下JSON格式返回：
```json
{{
  "locations": [
    {{
      "name": "地点名称",
      "description": "描述",
      "parent": "上级位置",
      "connections": ["相邻位置1", "相邻位置2"],
      "travel_times": {{"目标位置": "旅行时间描述"}}
    }}
  ],
  "character_positions": [
    {{
      "character": "角色名",
      "location": "位置名称",
      "arrival_method": "到达方式",
      "scene_description": "场景描述片段"
    }}
  ]
}}
```

注意：
- 只提取文本中明确提及的信息
- 不要推测或添加文本中未提及的内容
- 如果某项信息未提及，请省略该字段
"""

        try:
            response = await qwen_client.chat(
                prompt=prompt,
                system="你是一个专业的小说内容分析助手，擅长提取空间位置信息。",
                temperature=0.3,
            )

            content = response.get("content", "")
            data = JsonExtractor.extract_json(content, default={})

            if not data:
                logger.warning(f"第{chapter_number}章位置提取失败：无法解析JSON")
                return []

            new_locations = []

            # 处理提取到的位置
            locations_data = data.get("locations", [])
            for loc_data in locations_data:
                if not isinstance(loc_data, dict):
                    continue
                name = loc_data.get("name", "")
                if not name:
                    continue

                # 检查是否为新位置
                existing = self.get_location_by_name(name)
                if not existing:
                    loc_id = self.register_location(
                        name=name,
                        description=loc_data.get("description", ""),
                        chapter=chapter_number,
                        parent=loc_data.get("parent"),
                        connections=loc_data.get("connections", []),
                        travel_times=loc_data.get("travel_times"),
                    )
                    new_locations.append(self.locations[loc_id])
                else:
                    # 更新已有位置的信息
                    if loc_data.get("description"):
                        existing.description = loc_data["description"]
                    # 更新旅行时间
                    if loc_data.get("travel_times"):
                        for dest, time_desc in loc_data["travel_times"].items():
                            dest_loc = self.get_location_by_name(dest)
                            if dest_loc:
                                existing.travel_times[dest_loc.location_id] = time_desc

            # 处理角色位置
            positions_data = data.get("character_positions", [])
            for pos_data in positions_data:
                if not isinstance(pos_data, dict):
                    continue
                char_name = pos_data.get("character", "")
                location_name = pos_data.get("location", "")
                if char_name and location_name:
                    self.record_character_position(
                        character=char_name,
                        location_name=location_name,
                        chapter=chapter_number,
                        method=pos_data.get("arrival_method", ""),
                        scene_description=pos_data.get("scene_description", ""),
                    )

            logger.info(
                f"第{chapter_number}章提取完成：{len(new_locations)}个新位置，"
                f"{len(positions_data)}条角色位置记录"
            )
            return new_locations

        except Exception as e:
            logger.error(f"第{chapter_number}章位置提取异常: {e}")
            return []

    def validate_spatial_continuity(
        self,
        chapter_content: str,
        chapter_number: int,
    ) -> List[SpatialIssue]:
        """检查空间连贯性.

        检测问题：
        1. teleportation: 角色在没有旅行描述的情况下出现在不同位置
        2. travel_time: 角色的旅行时间与已知距离不符
        3. location_conflict: 同一场景中的位置描述互相矛盾
        4. scene_jump: 场景转换过于突兀，缺乏过渡

        本方法基于已记录的数据进行规则检查（不调LLM），快速执行。

        Args:
            chapter_content: 章节内容
            chapter_number: 章节号

        Returns:
            检测到的问题列表
        """
        issues: List[SpatialIssue] = []

        # 检查每个角色的位置连续性
        for char_name, positions in self.character_positions.items():
            if len(positions) < 2:
                continue

            # 按章节排序
            sorted_positions = sorted(positions, key=lambda p: p.chapter_number)

            for i in range(1, len(sorted_positions)):
                prev_pos = sorted_positions[i - 1]
                curr_pos = sorted_positions[i]

                # 只检查相邻章节
                if curr_pos.chapter_number - prev_pos.chapter_number > 1:
                    continue

                # 位置相同，无问题
                if prev_pos.location_id == curr_pos.location_id:
                    continue

                # 检查是否为瞬移问题
                if self._check_teleportation(prev_pos, curr_pos):
                    issues.append(
                        SpatialIssue(
                            issue_type="teleportation",
                            character=char_name,
                            from_location=prev_pos.location_name,
                            to_location=curr_pos.location_name,
                            from_chapter=prev_pos.chapter_number,
                            to_chapter=curr_pos.chapter_number,
                            description=(
                                f"角色{char_name}从{prev_pos.location_name}（第{prev_pos.chapter_number}章）"
                                f"移动到{curr_pos.location_name}（第{curr_pos.chapter_number}章），"
                                f"但没有描述到达方式"
                            ),
                            severity="medium",
                            suggested_fix=(
                                f"建议在第{curr_pos.chapter_number}章开头添加"
                                f"从{prev_pos.location_name}到{curr_pos.location_name}的旅行描述"
                            ),
                        )
                    )

                # 检查旅行时间是否合理
                travel_issue = self._check_travel_time(prev_pos, curr_pos)
                if travel_issue:
                    issues.append(travel_issue)

        # 检查场景跳跃
        scene_issues = self._check_scene_jumps(chapter_content, chapter_number)
        issues.extend(scene_issues)

        return issues

    def _check_teleportation(
        self, prev_pos: CharacterPosition, curr_pos: CharacterPosition
    ) -> bool:
        """检查是否为瞬移问题.

        角色在相邻章节出现在不同位置，且没有相应的 arrival_method。

        Args:
            prev_pos: 前一位置
            curr_pos: 当前位置

        Returns:
            是否为瞬移问题
        """
        # 如果有到达方式描述，检查是否为快速旅行方式
        if curr_pos.arrival_method:
            method = curr_pos.arrival_method.lower()
            for fast_method in self.FAST_TRAVEL_METHODS:
                if fast_method in method:
                    return False
            return False

        # 检查两个位置是否相邻或有旅行时间记录
        prev_loc = self.locations.get(prev_pos.location_id)
        curr_loc = self.locations.get(curr_pos.location_id)

        if prev_loc and curr_loc:
            # 检查是否为相邻位置
            if curr_pos.location_id in prev_loc.connected_locations:
                return False
            # 检查是否有旅行时间记录
            if curr_pos.location_id in prev_loc.travel_times:
                return False

        # 没有任何旅行描述，认为是瞬移问题
        return True

    def _check_travel_time(
        self, prev_pos: CharacterPosition, curr_pos: CharacterPosition
    ) -> Optional[SpatialIssue]:
        """检查旅行时间是否合理.

        Args:
            prev_pos: 前一位置
            curr_pos: 当前位置

        Returns:
            如果有问题返回 SpatialIssue，否则返回 None
        """
        prev_loc = self.locations.get(prev_pos.location_id)
        curr_loc = self.locations.get(curr_pos.location_id)

        if not prev_loc or not curr_loc:
            return None

        # 检查是否有旅行时间记录
        travel_time = prev_loc.travel_times.get(curr_pos.location_id)
        if not travel_time:
            return None

        # 如果有快速旅行方式，跳过检查
        if curr_pos.arrival_method:
            method = curr_pos.arrival_method.lower()
            for fast_method in self.FAST_TRAVEL_METHODS:
                if fast_method in method:
                    return None

        # 简单检查：如果旅行时间描述包含"天"但章节间隔为0或1
        # 可能在时间线上有问题
        if "天" in travel_time or "周" in travel_time or "月" in travel_time:
            chapter_gap = curr_pos.chapter_number - prev_pos.chapter_number
            if chapter_gap <= 1:
                return SpatialIssue(
                    issue_type="travel_time",
                    character=prev_pos.character_name,
                    from_location=prev_pos.location_name,
                    to_location=curr_pos.location_name,
                    from_chapter=prev_pos.chapter_number,
                    to_chapter=curr_pos.chapter_number,
                    description=(
                        f"角色{prev_pos.character_name}从{prev_pos.location_name}到"
                        f"{curr_pos.location_name}的旅行时间为{travel_time}，"
                        f"但章节间隔仅为{chapter_gap}章"
                    ),
                    severity="low",
                    suggested_fix="检查时间线是否合理，或添加快速旅行的描述",
                )

        return None

    def _check_scene_jumps(
        self, chapter_content: str, chapter_number: int
    ) -> List[SpatialIssue]:
        """检查场景跳跃问题.

        检测章节内容中是否有突兀的场景转换。

        Args:
            chapter_content: 章节内容
            chapter_number: 章节号

        Returns:
            检测到的问题列表
        """
        issues: List[SpatialIssue] = []

        # 简单规则：检测段落间是否有足够的过渡
        # 查找场景转换标记
        scene_markers = [
            r"与此同时",
            r"另一边",
            r"此时此刻",
            r"场景转换",
            r"镜头回到",
            r"转眼间",
        ]

        # 检测没有过渡的场景转换
        paragraphs = [p.strip() for p in chapter_content.split("\n\n") if p.strip()]
        for i in range(1, len(paragraphs)):
            curr_para = paragraphs[i]

            # 检查是否有过渡词
            has_transition = any(
                re.search(marker, curr_para) for marker in scene_markers
            )

            # 如果没有过渡词，检查是否有明显的人物/场景切换
            if not has_transition:
                # 简单检查：是否提到不同的角色
                # 这里只是简单检测，实际需要更复杂的逻辑
                # 暂不实现，避免误报
                _ = i  # 占位，后续扩展

        return issues

    def build_spatial_context(self, chapter_number: int) -> str:
        """生成空间上下文提示词.

        为写作提供当前角色位置和地点关系的上下文。

        Args:
            chapter_number: 目标章节号

        Returns:
            格式化的空间上下文提示词
        """
        lines = ["【空间位置上下文】"]

        # 当前角色位置
        lines.append("\n[当前角色位置]")
        has_positions = False
        for char_name, positions in self.character_positions.items():
            # 获取目标章节之前的最后位置
            valid_positions = [p for p in positions if p.chapter_number < chapter_number]
            if valid_positions:
                last_pos = max(valid_positions, key=lambda p: p.chapter_number)
                lines.append(
                    f"- {char_name}：{last_pos.location_name}"
                    f"（第{last_pos.chapter_number}章到达）"
                )
                has_positions = True

        if not has_positions:
            lines.append("- 暂无角色位置记录")

        # 已知地点关系
        lines.append("\n[已知地点关系]")
        has_relations = False
        for loc in self.locations.values():
            if loc.travel_times:
                for dest_id, time_desc in loc.travel_times.items():
                    dest_loc = self.locations.get(dest_id)
                    if dest_loc:
                        lines.append(f"- {loc.name} → {dest_loc.name}：{time_desc}")
                        has_relations = True

        if not has_relations:
            lines.append("- 暂无地点关系记录")

        return "\n".join(lines)

    def get_location_graph(self) -> Dict[str, Any]:
        """返回位置关系图的字典表示.

        返回节点和边的数据结构，可用于可视化。

        Returns:
            包含 nodes 和 edges 的字典
        """
        nodes = []
        edges = []

        for loc_id, loc in self.locations.items():
            nodes.append({
                "id": loc_id,
                "name": loc.name,
                "description": loc.description,
                "tags": loc.tags,
            })

            # 父子关系边
            if loc.parent_location:
                edges.append({
                    "source": loc.parent_location,
                    "target": loc_id,
                    "type": "parent",
                })

            # 相邻关系边
            for conn_id in loc.connected_locations:
                # 避免重复
                edge_exists = any(
                    e["source"] == loc_id and e["target"] == conn_id
                    or e["source"] == conn_id and e["target"] == loc_id
                    for e in edges
                )
                if not edge_exists:
                    edges.append({
                        "source": loc_id,
                        "target": conn_id,
                        "type": "connected",
                    })

            # 旅行时间边
            for dest_id, time_desc in loc.travel_times.items():
                edges.append({
                    "source": loc_id,
                    "target": dest_id,
                    "type": "travel",
                    "travel_time": time_desc,
                })

        return {"nodes": nodes, "edges": edges}

    def to_dict(self) -> Dict[str, Any]:
        """序列化追踪器状态.

        Returns:
            包含所有状态的字典
        """
        return {
            "locations": {
                loc_id: loc.to_dict() for loc_id, loc in self.locations.items()
            },
            "character_positions": {
                char_name: [pos.to_dict() for pos in positions]
                for char_name, positions in self.character_positions.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpatialTracker":
        """从字典恢复追踪器状态.

        Args:
            data: 序列化的状态字典

        Returns:
            恢复的追踪器实例
        """
        tracker = cls()

        # 恢复位置
        locations_data = data.get("locations", {})
        for loc_id, loc_data in locations_data.items():
            loc = Location.from_dict(loc_data)
            tracker.locations[loc.location_id] = loc
            tracker._name_index[loc.name.lower()] = loc.location_id

        # 恢复角色位置
        positions_data = data.get("character_positions", {})
        for char_name, pos_list in positions_data.items():
            tracker.character_positions[char_name] = [
                CharacterPosition.from_dict(pos_data) for pos_data in pos_list
            ]

        return tracker
