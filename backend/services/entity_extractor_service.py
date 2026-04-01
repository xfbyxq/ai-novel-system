"""实体抽取服务.

使用LLM从章节内容中抽取实体信息，包括角色、地点、事件、伏笔等，
用于同步到图数据库。
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.config import settings
from core.logging_config import logger
from llm.qwen_client import QwenClient, qwen_client


@dataclass
class ExtractedCharacter:
    """抽取的角色实体."""

    name: str
    role_type: str = "minor"  # protagonist/supporting/antagonist/minor
    gender: Optional[str] = None
    is_new: bool = True  # 是否是新角色
    actions: List[str] = field(default_factory=list)  # 角色在章节中的主要行为
    status_change: Optional[str] = None  # 状态变化（如死亡）


@dataclass
class ExtractedLocation:
    """抽取的地点实体."""

    name: str
    location_type: str = "scene"  # scene/region/building
    description: Optional[str] = None


@dataclass
class ExtractedEvent:
    """抽取的事件实体."""

    name: str
    chapter_number: int  # 章节号（必需参数）
    event_type: str = "plot"  # plot/battle/romance/conflict/revelation
    participants: List[str] = field(default_factory=list)
    description: Optional[str] = None
    significance: int = 5  # 1-10重要程度


@dataclass
class ExtractedForeshadowing:
    """抽取的伏笔实体."""

    content: str
    planted_chapter: int  # 埋设章节（必需参数）
    ftype: str = "plot"  # plot/character/item/mystery/hint
    importance: int = 5
    related_characters: List[str] = field(default_factory=list)
    expected_resolve_chapter: Optional[int] = None
    is_resolved: bool = False  # 是否为回收伏笔


@dataclass
class ExtractedRelationship:
    """抽取的角色关系."""

    from_character: str
    to_character: str
    relation_type: str  # lover/enemy/friend/parent等
    strength: int = 5  # 1-10关系强度
    is_new: bool = True  # 是否是新建立的关系
    change_type: Optional[str] = None  # strengthen/weaken/establish/break


@dataclass
class ExtractionResult:
    """实体抽取结果."""

    chapter_number: int
    characters: List[ExtractedCharacter] = field(default_factory=list)
    locations: List[ExtractedLocation] = field(default_factory=list)
    events: List[ExtractedEvent] = field(default_factory=list)
    foreshadowings: List[ExtractedForeshadowing] = field(default_factory=list)
    relationships: List[ExtractedRelationship] = field(default_factory=list)
    summary: Optional[str] = None
    extraction_time: float = 0.0  # 抽取耗时（秒）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式."""
        return {
            "chapter_number": self.chapter_number,
            "characters": [
                {
                    "name": c.name,
                    "role_type": c.role_type,
                    "gender": c.gender,
                    "is_new": c.is_new,
                    "actions": c.actions,
                    "status_change": c.status_change,
                }
                for c in self.characters
            ],
            "locations": [
                {
                    "name": loc.name,
                    "location_type": loc.location_type,
                    "description": loc.description,
                }
                for loc in self.locations
            ],
            "events": [
                {
                    "name": e.name,
                    "event_type": e.event_type,
                    "chapter_number": e.chapter_number,
                    "participants": e.participants,
                    "description": e.description,
                    "significance": e.significance,
                }
                for e in self.events
            ],
            "foreshadowings": [
                {
                    "content": f.content,
                    "ftype": f.ftype,
                    "planted_chapter": f.planted_chapter,
                    "importance": f.importance,
                    "related_characters": f.related_characters,
                    "expected_resolve_chapter": f.expected_resolve_chapter,
                    "is_resolved": f.is_resolved,
                }
                for f in self.foreshadowings
            ],
            "relationships": [
                {
                    "from_character": r.from_character,
                    "to_character": r.to_character,
                    "relation_type": r.relation_type,
                    "strength": r.strength,
                    "is_new": r.is_new,
                    "change_type": r.change_type,
                }
                for r in self.relationships
            ],
            "summary": self.summary,
            "extraction_time": self.extraction_time,
        }


# LLM实体抽取的系统提示词
ENTITY_EXTRACTION_SYSTEM_PROMPT = """你是一个专业的小说内容分析专家。
你的任务是从章节内容中识别和抽取以下类型的实体信息：

1. **角色实体**：识别章节中出现的角色，注意区分主要角色和次要角色
2. **地点实体**：识别章节中涉及的地点场景
3. **事件实体**：识别章节中发生的重要事件
4. **伏笔实体**：识别埋设的伏笔或回收的伏笔
5. **角色关系**：识别角色之间的关系及其变化

请严格按照JSON格式输出，不要添加任何额外文字。"""


ENTITY_EXTRACTION_PROMPT_TEMPLATE = """请分析以下章节内容
（第{chapter_number}章），抽取其中的实体信息。

## 已有角色列表（用于判断新角色）
{known_characters}

## 章节内容
{chapter_content}

## 输出要求
请以以下JSON格式输出：

```json
{{
    "summary": "章节简要摘要（1-2句话）",
    "characters": [
        {{
            "name": "角色名称",
            "role_type": "protagonist|supporting|antagonist|minor",
            "gender": "male|female|other",
            "is_new": true|false,
            "actions": ["主要行为1", "主要行为2"],
            "status_change": "alive|dead|unknown 或 null"
        }}
    ],
    "locations": [
        {{
            "name": "地点名称",
            "location_type": "scene|region|building",
            "description": "简短描述"
        }}
    ],
    "events": [
        {{
            "name": "事件名称",
            "event_type": "plot|battle|romance|conflict|revelation",
            "participants": ["参与角色"],
            "description": "事件描述",
            "significance": 1-10重要程度
        }}
    ],
    "foreshadowings": [
        {{
            "content": "伏笔内容",
            "ftype": "plot|character|item|mystery|hint",
            "importance": 1-10,
            "related_characters": ["相关角色"],
            "expected_resolve_chapter": 预计回收章节号或null,
            "is_resolved": true|false
        }}
    ],
    "relationships": [
        {{
            "from_character": "角色A",
            "to_character": "角色B",
            "relation_type": "lover|enemy|friend|parent|child|sibling|...",
            "strength": 1-10,
            "is_new": true|false,
            "change_type": "establish|strengthen|weaken|break 或 null"
        }}
    ]
}}
```

注意：
- 只抽取明确出现在章节中的实体，不要推测
- 角色名称应与已有角色列表匹配，如果不在列表中则为新角色
- 关系类型要准确，避免模糊描述
- 伏笔要区分是埋设还是回收
"""


class EntityExtractorService:
    """实体抽取服务.

    使用LLM从章节内容中抽取实体信息。
    """

    def __init__(self, llm_client: Optional[QwenClient] = None):
        """初始化服务.

        Args:
            llm_client: LLM客户端实例，默认使用全局qwen_client
        """
        self.llm = llm_client or qwen_client

    async def extract_from_chapter(
        self,
        chapter_number: int,
        chapter_content: str,
        known_characters: Optional[List[str]] = None,
    ) -> ExtractionResult:
        """从章节内容中抽取实体.

        Args:
            chapter_number: 章节号
            chapter_content: 章节内容
            known_characters: 已有角色名称列表，用于判断新角色

        Returns:
            ExtractionResult: 抽取结果
        """
        import time

        start_time = time.time()

        # 准备角色列表文本
        chars_text = "无已知角色信息"
        if known_characters:
            chars_text = ", ".join(known_characters)

        # 构造提示词
        prompt = ENTITY_EXTRACTION_PROMPT_TEMPLATE.format(
            chapter_number=chapter_number,
            known_characters=chars_text,
            chapter_content=chapter_content[:8000],  # 限制长度避免超token
        )

        try:
            # 调用LLM
            response = await self.llm.chat(
                prompt=prompt,
                system=ENTITY_EXTRACTION_SYSTEM_PROMPT,
                temperature=0.3,  # 低温度以获得更稳定的抽取结果
                max_tokens=4096,  # 增大限制，确保完整JSON不被截断
            )

            content = response.get("content", "")

            # 解析JSON响应
            extraction_data = self._parse_json_response(content)

            # 构造结果对象
            result = self._build_extraction_result(chapter_number, extraction_data)
            result.extraction_time = time.time() - start_time

            logger.info(
                f"实体抽取完成: 第{chapter_number}章, "
                f"角色{len(result.characters)}, "
                f"事件{len(result.events)}, "
                f"耗时{result.extraction_time:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"实体抽取失败: {e}")
            # 返回空结果
            return ExtractionResult(
                chapter_number=chapter_number,
                summary=f"抽取失败: {str(e)}",
                extraction_time=time.time() - start_time,
            )

    async def extract_entities_batch(
        self,
        chapters: List[Dict[str, Any]],
        known_characters: Optional[List[str]] = None,
    ) -> List[ExtractionResult]:
        """批量抽取多章节的实体.

        Args:
            chapters: 章节列表，每项包含 chapter_number 和 content
            known_characters: 已有角色名称列表

        Returns:
            所有章节的抽取结果列表
        """
        results = []

        # 逐步抽取（避免并发请求过多）
        for chapter in chapters:
            result = await self.extract_from_chapter(
                chapter_number=chapter.get("chapter_number", 0),
                chapter_content=chapter.get("content", ""),
                known_characters=known_characters,
            )
            results.append(result)

            # 更新已知角色列表
            for char in result.characters:
                if char.is_new and char.name:
                    if known_characters is None:
                        known_characters = []
                    if char.name not in known_characters:
                        known_characters.append(char.name)

        return results

    async def extract_foreshadowing_check(
        self,
        chapter_content: str,
        pending_foreshadowings: List[Dict[str, Any]],
    ) -> List[str]:
        """检查章节是否回收了待处理的伏笔.

        Args:
            chapter_content: 章节内容
            pending_foreshadowings: 待回收的伏笔列表

        Returns:
            在本章回收的伏笔ID列表
        """
        if not pending_foreshadowings:
            return []

        # 构造伏笔列表文本
        foreshadowing_text = "\n".join(
            [
                f"- ID: {f.get('id')}, 内容: {f.get('content')}, 类型: {f.get('ftype')}"
                for f in pending_foreshadowings
            ]
        )

        prompt = f"""请分析以下章节内容，判断哪些待回收的伏笔在本章被回收了。

## 待回收的伏笔列表
{foreshadowing_text}

## 章节内容
{chapter_content[:6000]}

## 输出要求
请以JSON数组格式输出被回收的伏笔ID：
["伏笔ID1", "伏笔ID2"]

如果没有回收任何伏笔，输出空数组：[]

只输出JSON数组，不要其他文字。"""

        try:
            response = await self.llm.chat(
                prompt=prompt,
                system="你是一个伏笔分析专家，擅长识别小说中伏笔的回收情况。",
                temperature=0.2,
                max_tokens=500,
            )

            content = response.get("content", "")

            # 解析JSON数组
            resolved_ids = self._parse_json_array(content)
            return resolved_ids

        except Exception as e:
            logger.error(f"伏笔回收检查失败: {e}")
            return []

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """解析LLM返回的JSON响应.

        Args:
            content: LLM返回的文本内容

        Returns:
            解析后的字典
        """
        # 预处理：移除可能的前缀空白和标记
        content = content.strip()

        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试从代码块中提取（支持 ```json 和 ```）
        json_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
        matches = re.findall(json_block_pattern, content)
        if matches:
            for match in matches:
                try:
                    stripped = match.strip()
                    if stripped.startswith("{"):
                        return json.loads(stripped)
                except json.JSONDecodeError:
                    continue

        # 尝试提取第一个完整的JSON对象（非贪婪，找到最外层匹配）
        # 使用栈式匹配确保正确识别JSON边界
        json_start = content.find("{")
        if json_start != -1:
            brace_count = 0
            json_end = json_start
            for i, char in enumerate(content[json_start:], json_start):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i
                        break
            if json_end > json_start:
                try:
                    json_str = content[json_start:json_end + 1]
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

        logger.warning(f"无法解析JSON响应: {content[:300]}...")
        return {}

    def _parse_json_array(self, content: str) -> List[str]:
        """解析JSON数组响应."""
        try:
            result = json.loads(content)
            if isinstance(result, list):
                return [str(item) for item in result]
        except json.JSONDecodeError:
            pass

        # 尝试从代码块提取
        json_pattern = r"```(?:json)?\s*([\s\S]*?)```"
        matches = re.findall(json_pattern, content)
        if matches:
            try:
                result = json.loads(matches[0].strip())
                if isinstance(result, list):
                    return [str(item) for item in result]
            except json.JSONDecodeError:
                pass

        return []

    def _build_extraction_result(
        self, chapter_number: int, data: Dict[str, Any]
    ) -> ExtractionResult:
        """从解析的数据构造抽取结果对象."""
        result = ExtractionResult(chapter_number=chapter_number)

        # 解析摘要
        result.summary = data.get("summary")

        # 解析角色
        for char_data in data.get("characters", []):
            result.characters.append(
                ExtractedCharacter(
                    name=char_data.get("name", ""),
                    role_type=char_data.get("role_type", "minor"),
                    gender=char_data.get("gender"),
                    is_new=char_data.get("is_new", True),
                    actions=char_data.get("actions", []),
                    status_change=char_data.get("status_change"),
                )
            )

        # 解析地点
        for loc_data in data.get("locations", []):
            result.locations.append(
                ExtractedLocation(
                    name=loc_data.get("name", ""),
                    location_type=loc_data.get("location_type", "scene"),
                    description=loc_data.get("description"),
                )
            )

        # 解析事件
        for event_data in data.get("events", []):
            result.events.append(
                ExtractedEvent(
                    name=event_data.get("name", ""),
                    event_type=event_data.get("event_type", "plot"),
                    chapter_number=chapter_number,
                    participants=event_data.get("participants", []),
                    description=event_data.get("description"),
                    significance=event_data.get("significance", 5),
                )
            )

        # 解析伏笔
        for fore_data in data.get("foreshadowings", []):
            result.foreshadowings.append(
                ExtractedForeshadowing(
                    content=fore_data.get("content", ""),
                    ftype=fore_data.get("ftype", "plot"),
                    planted_chapter=chapter_number,
                    importance=fore_data.get("importance", 5),
                    related_characters=fore_data.get("related_characters", []),
                    expected_resolve_chapter=fore_data.get("expected_resolve_chapter"),
                    is_resolved=fore_data.get("is_resolved", False),
                )
            )

        # 解析关系
        for rel_data in data.get("relationships", []):
            result.relationships.append(
                ExtractedRelationship(
                    from_character=rel_data.get("from_character", ""),
                    to_character=rel_data.get("to_character", ""),
                    relation_type=rel_data.get("relation_type", "neutral"),
                    strength=rel_data.get("strength", 5),
                    is_new=rel_data.get("is_new", True),
                    change_type=rel_data.get("change_type"),
                )
            )

        return result


# 便捷函数
async def extract_chapter_entities(
    chapter_number: int,
    chapter_content: str,
    known_characters: Optional[List[str]] = None,
) -> ExtractionResult:
    """抽取章节实体的便捷函数."""
    if not settings.ENABLE_ENTITY_EXTRACTION:
        return ExtractionResult(
            chapter_number=chapter_number,
            summary="实体抽取功能未启用",
        )

    service = EntityExtractorService()
    return await service.extract_from_chapter(
        chapter_number, chapter_content, known_characters
    )
