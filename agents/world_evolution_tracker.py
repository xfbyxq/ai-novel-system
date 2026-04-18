"""
WorldEvolutionTracker - 世界观演变追踪器.

用于追踪小说世界观设定的跨章节演变，区分故意变更和错误不一致。

核心功能：
1. 注册和管理世界观设定元素
2. 记录设定的变更历史
3. 使用 LLM 验证章节内容与世界观的一致性
4. 自动从文本中提取世界观设定
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from core.logging_config import logger


class SettingCategory(str, Enum):
    """世界观设定分类."""

    POWER_SYSTEM = "power_system"  # 力量体系
    GEOGRAPHY = "geography"  # 地理设定
    FACTION = "faction"  # 派系体系
    CULTURE = "culture"  # 文化背景
    HISTORY = "history"  # 历史背景
    PHYSICS = "physics"  # 物理规则
    OTHER = "other"


@dataclass
class WorldSettingChange:
    """世界观设定变更记录.

    Attributes:
        chapter_number: 变更发生的章节号
        before_state: 变更前的状态
        after_state: 变更后的状态
        change_reason: 变更原因
        is_intentional: 是否为故意变更
        confidence: 置信度 0-1
        detected_at: 检测时间
    """

    chapter_number: int
    before_state: str
    after_state: str
    change_reason: str
    is_intentional: bool = True
    confidence: float = 0.8
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        """验证数据有效性."""
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "chapter_number": self.chapter_number,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "change_reason": self.change_reason,
            "is_intentional": self.is_intentional,
            "confidence": self.confidence,
            "detected_at": self.detected_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldSettingChange":
        """从字典创建."""
        return cls(
            chapter_number=data.get("chapter_number", 0),
            before_state=data.get("before_state", ""),
            after_state=data.get("after_state", ""),
            change_reason=data.get("change_reason", ""),
            is_intentional=data.get("is_intentional", True),
            confidence=data.get("confidence", 0.8),
            detected_at=data.get("detected_at", datetime.now().isoformat()),
        )


@dataclass
class WorldSettingElement:
    """世界观设定元素.

    Attributes:
        element_id: 元素唯一ID
        category: 设定分类
        name: 设定名称
        description: 设定描述
        established_chapter: 首次建立的章节
        current_state: 当前状态
        change_history: 变更历史记录
        tags: 搜索标签
        created_at: 创建时间
    """

    element_id: str = field(default_factory=lambda: uuid4().hex[:8])
    category: SettingCategory = SettingCategory.OTHER
    name: str = ""
    description: str = ""
    established_chapter: int = 1
    current_state: str = ""
    change_history: List[WorldSettingChange] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "element_id": self.element_id,
            "category": self.category.value,
            "name": self.name,
            "description": self.description,
            "established_chapter": self.established_chapter,
            "current_state": self.current_state,
            "change_history": [c.to_dict() for c in self.change_history],
            "tags": self.tags,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldSettingElement":
        """从字典创建."""
        return cls(
            element_id=data.get("element_id", uuid4().hex[:8]),
            category=SettingCategory(data.get("category", "other")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            established_chapter=data.get("established_chapter", 1),
            current_state=data.get("current_state", ""),
            change_history=[
                WorldSettingChange.from_dict(c) for c in data.get("change_history", [])
            ],
            tags=data.get("tags", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


@dataclass
class WorldConsistencyIssue:
    """世界观一致性问题.

    Attributes:
        element_name: 相关设定名称
        element_category: 设定分类
        conflicting_chapter: 冲突发生的章节
        conflict_description: 冲突描述
        expected_state: 根据已有设定应该是什么
        actual_state: 实际出现的是什么
        severity: 严重程度 critical|high|medium|low
        suggested_fix: 建议修复方案
    """

    element_name: str
    element_category: str
    conflicting_chapter: int
    conflict_description: str
    expected_state: str = ""
    actual_state: str = ""
    severity: str = "medium"
    suggested_fix: str = ""

    def __post_init__(self):
        """验证严重程度有效性."""
        valid_severities = ["critical", "high", "medium", "low"]
        if self.severity not in valid_severities:
            raise ValueError(
                f"Invalid severity: {self.severity}. Must be one of {valid_severities}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "element_name": self.element_name,
            "element_category": self.element_category,
            "conflicting_chapter": self.conflicting_chapter,
            "conflict_description": self.conflict_description,
            "expected_state": self.expected_state,
            "actual_state": self.actual_state,
            "severity": self.severity,
            "suggested_fix": self.suggested_fix,
        }


class WorldEvolutionTracker:
    """世界观演变追踪器.

    追踪世界设定的跨章节演变，区分故意变更和错误不一致。

    功能：
    1. 注册和管理世界观设定
    2. 记录设定的变更历史
    3. 验证章节内容与世界观的一致性
    4. 自动提取和更新世界观设定
    """

    def __init__(
        self,
        novel_data: Optional[Dict[str, Any]] = None,
        qwen_client: Optional[Any] = None,
    ) -> None:
        """初始化追踪器.

        Args:
            novel_data: 小说数据，可从中提取初始世界观设定
            qwen_client: LLM 客户端实例，用于验证和提取
        """
        self.settings: Dict[str, WorldSettingElement] = {}  # element_id -> element
        self._name_index: Dict[str, str] = {}  # name -> element_id
        self._qwen_client = qwen_client

        # 从 novel_data 中提取初始设定
        if novel_data:
            self._extract_initial_settings(novel_data)

        logger.info(f"WorldEvolutionTracker initialized with {len(self.settings)} settings")

    def _extract_initial_settings(self, novel_data: Dict[str, Any]) -> None:
        """从小说数据中提取初始世界观设定.

        Args:
            novel_data: 小说数据字典
        """
        # 尝试从世界观字段提取
        world_setting = novel_data.get("world_setting", {})
        if isinstance(world_setting, dict):
            # 提取力量体系
            power_system = world_setting.get("power_system", {})
            if power_system:
                self._register_from_dict(
                    power_system, SettingCategory.POWER_SYSTEM, "力量体系"
                )

            # 提取地理设定
            geography = world_setting.get("geography", {})
            if geography:
                self._register_from_dict(geography, SettingCategory.GEOGRAPHY, "地理设定")

            # 提取派系体系
            factions = world_setting.get("factions", [])
            for faction in factions:
                if isinstance(faction, dict):
                    self.register_setting(
                        name=faction.get("name", "未命名派系"),
                        category=SettingCategory.FACTION,
                        description=faction.get("description", ""),
                        chapter=1,
                        tags=["faction"],
                    )

            # 提取文化背景
            culture = world_setting.get("culture", {})
            if culture:
                self._register_from_dict(culture, SettingCategory.CULTURE, "文化背景")

            # 提取历史背景
            history = world_setting.get("history", "")
            if history:
                self.register_setting(
                    name="历史背景",
                    category=SettingCategory.HISTORY,
                    description=history if isinstance(history, str) else str(history),
                    chapter=1,
                    tags=["history"],
                )

    def _register_from_dict(
        self, data: Dict[str, Any], category: SettingCategory, default_name: str
    ) -> None:
        """从字典注册设定.

        Args:
            data: 设定数据字典
            category: 设定分类
            default_name: 默认名称
        """
        if isinstance(data, dict):
            name = data.get("name", default_name)
            description = data.get("description", str(data))
            self.register_setting(
                name=name,
                category=category,
                description=description,
                chapter=1,
                tags=[category.value],
            )

    def register_setting(
        self,
        name: str,
        category: SettingCategory,
        description: str,
        chapter: int,
        tags: Optional[List[str]] = None,
    ) -> str:
        """注册新的世界观设定元素.

        Args:
            name: 设定名称
            category: 设定分类
            description: 设定描述
            chapter: 首次出现的章节
            tags: 搜索标签

        Returns:
            element_id: 设定元素ID
        """
        # 检查是否已存在同名设定
        existing = self.get_setting_by_name(name)
        if existing:
            logger.warning(f"Setting with name '{name}' already exists, skipping registration")
            return existing.element_id

        element = WorldSettingElement(
            category=category,
            name=name,
            description=description,
            established_chapter=chapter,
            current_state=description,
            tags=tags or [],
        )

        self.settings[element.element_id] = element
        self._name_index[name] = element.element_id

        logger.info(
            f"Registered setting: {name} (ID: {element.element_id}, "
            f"Category: {category.value})"
        )
        return element.element_id

    def record_change(
        self,
        element_id: str,
        chapter: int,
        new_state: str,
        reason: str,
        intentional: bool = True,
        confidence: float = 0.8,
    ) -> None:
        """记录设定的变更.

        Args:
            element_id: 设定元素ID
            chapter: 变更发生的章节
            new_state: 新状态
            reason: 变更原因
            intentional: 是否为故意变更
            confidence: 置信度
        """
        if element_id not in self.settings:
            logger.warning(f"Setting not found: {element_id}")
            return

        element = self.settings[element_id]
        old_state = element.current_state

        change = WorldSettingChange(
            chapter_number=chapter,
            before_state=old_state,
            after_state=new_state,
            change_reason=reason,
            is_intentional=intentional,
            confidence=confidence,
        )

        element.change_history.append(change)
        element.current_state = new_state

        logger.info(
            f"Recorded change for '{element.name}': chapter {chapter}, "
            f"intentional={intentional}"
        )

    def get_setting_by_name(self, name: str) -> Optional[WorldSettingElement]:
        """按名称查找设定.

        Args:
            name: 设定名称

        Returns:
            设定元素，未找到返回 None
        """
        element_id = self._name_index.get(name)
        if element_id:
            return self.settings.get(element_id)
        return None

    def get_settings_by_category(self, category: SettingCategory) -> List[WorldSettingElement]:
        """按分类获取设定.

        Args:
            category: 设定分类

        Returns:
            该分类下的所有设定元素
        """
        return [s for s in self.settings.values() if s.category == category]

    async def validate_chapter_against_settings(
        self,
        chapter_content: str,
        chapter_number: int,
    ) -> List[WorldConsistencyIssue]:
        """使用 LLM 验证章节内容是否与已知世界观设定冲突.

        Args:
            chapter_content: 章节内容
            chapter_number: 章节号

        Returns:
            发现的一致性问题列表
        """
        # 如果没有注册任何设定，返回空列表
        if not self.settings:
            logger.info("No settings registered, skipping validation")
            return []

        # 如果没有 LLM 客户端，返回空列表
        if not self._qwen_client:
            logger.warning("No QwenClient provided, cannot validate chapter")
            return []

        # 构建设定摘要
        settings_summary = self._build_validation_summary()

        # 构建验证提示词
        prompt = self._build_validation_prompt(chapter_content, settings_summary, chapter_number)

        try:
            # 调用 LLM 进行验证
            response = await self._qwen_client.chat(
                prompt=prompt,
                system="你是一个专业的小说世界观一致性检查助手。请仔细检查章节内容与世界观设定的一致性。",
                temperature=0.3,
            )

            content = response.get("content", "")

            # 使用 JsonExtractor 提取 JSON
            from agents.base.json_extractor import JsonExtractor

            issues_data = JsonExtractor.extract_array(content, default=[])

            # 转换为 WorldConsistencyIssue 对象
            issues = []
            for issue_data in issues_data:
                if isinstance(issue_data, dict):
                    issue = WorldConsistencyIssue(
                        element_name=issue_data.get("element_name", "未知设定"),
                        element_category=issue_data.get("element_category", "other"),
                        conflicting_chapter=chapter_number,
                        conflict_description=issue_data.get("conflict_description", ""),
                        expected_state=issue_data.get("expected_state", ""),
                        actual_state=issue_data.get("actual_state", ""),
                        severity=issue_data.get("severity", "medium"),
                        suggested_fix=issue_data.get("suggested_fix", ""),
                    )
                    issues.append(issue)

            logger.info(
                f"Validation found {len(issues)} consistency issues "
                f"for chapter {chapter_number}"
            )
            return issues

        except Exception as e:
            logger.error(f"Error validating chapter {chapter_number}: {e}")
            return []

    def _build_validation_summary(self) -> str:
        """构建用于验证的设定摘要.

        Returns:
            设定摘要文本
        """
        parts = []
        for category in SettingCategory:
            category_settings = self.get_settings_by_category(category)
            if category_settings:
                category_name = self._get_category_display_name(category)
                parts.append(f"\n[{category_name}]")
                for setting in category_settings:
                    parts.append(f"- {setting.name}: {setting.current_state}")
        return "\n".join(parts)

    def _get_category_display_name(self, category: SettingCategory) -> str:
        """获取分类显示名称.

        Args:
            category: 设定分类

        Returns:
            显示名称
        """
        display_names = {
            SettingCategory.POWER_SYSTEM: "力量体系",
            SettingCategory.GEOGRAPHY: "地理设定",
            SettingCategory.FACTION: "派系体系",
            SettingCategory.CULTURE: "文化背景",
            SettingCategory.HISTORY: "历史背景",
            SettingCategory.PHYSICS: "物理规则",
            SettingCategory.OTHER: "其他设定",
        }
        return display_names.get(category, category.value)

    def _build_validation_prompt(
        self, chapter_content: str, settings_summary: str, chapter_number: int
    ) -> str:
        """构建验证提示词.

        Args:
            chapter_content: 章节内容
            settings_summary: 设定摘要
            chapter_number: 章节号

        Returns:
            验证提示词
        """
        return f"""请检查以下第{chapter_number}章的内容是否与已知的世界观设定存在冲突。

【已知世界观设定】
{settings_summary}

【第{chapter_number}章内容】
{chapter_content[:3000]}...

请分析章节内容，找出任何与已知世界观设定不一致的地方。

请以JSON数组格式返回发现的所有冲突，每个冲突包含以下字段：
- element_name: 相关设定名称
- element_category: 设定分类（power_system|geography|faction|culture|history|physics|other）
- conflict_description: 冲突描述
- expected_state: 根据已有设定应该是什么
- actual_state: 实际出现的是什么
- severity: 严重程度（critical|high|medium|low）
- suggested_fix: 建议修复方案

如果没有发现冲突，请返回空数组 []。

示例输出格式：
```json
[
  {{
    "element_name": "冰焰术",
    "element_category": "power_system",
    "conflict_description": "前文设定冰焰术需要双系亲和力，但本章主角无火系亲和力却使用了冰焰术",
    "expected_state": "需要同时具备冰系和火系亲和力才能使用",
    "actual_state": "主角只有冰系亲和力却成功使用了冰焰术",
    "severity": "high",
    "suggested_fix": "修改本章，让主角使用纯冰系法术，或补充获得火系亲和力的情节"
  }}
]
```"""

    async def extract_settings_from_text(
        self,
        chapter_content: str,
        chapter_number: int,
    ) -> List[WorldSettingElement]:
        """使用 LLM 从章节文本中自动提取世界观设定信息.

        提取后自动与已有设定对比：
        - 如果是新设定，自动注册
        - 如果是已有设定的变更，记录变更

        Args:
            chapter_content: 章节内容
            chapter_number: 章节号

        Returns:
            所有提取到的设定元素
        """
        extracted_elements: List[WorldSettingElement] = []

        # 如果没有 LLM 客户端，返回空列表
        if not self._qwen_client:
            logger.warning("No QwenClient provided, cannot extract settings")
            return extracted_elements

        # 构建提取提示词
        prompt = self._build_extraction_prompt(chapter_content, chapter_number)

        try:
            # 调用 LLM 进行提取
            response = await self._qwen_client.chat(
                prompt=prompt,
                system="你是一个专业的小说世界观设定提取助手。请仔细分析章节内容，提取其中的世界观设定信息。",
                temperature=0.3,
            )

            content = response.get("content", "")

            # 使用 JsonExtractor 提取 JSON
            from agents.base.json_extractor import JsonExtractor

            settings_data = JsonExtractor.extract_array(content, default=[])

            # 处理提取到的设定
            for setting_data in settings_data:
                if isinstance(setting_data, dict):
                    element = self._process_extracted_setting(setting_data, chapter_number)
                    if element:
                        extracted_elements.append(element)

            logger.info(
                f"Extracted {len(extracted_elements)} settings from chapter {chapter_number}"
            )
            return extracted_elements

        except Exception as e:
            logger.error(f"Error extracting settings from chapter {chapter_number}: {e}")
            return extracted_elements

    def _build_extraction_prompt(self, chapter_content: str, chapter_number: int) -> str:
        """构建提取提示词.

        Args:
            chapter_content: 章节内容
            chapter_number: 章节号

        Returns:
            提取提示词
        """
        return f"""请分析第{chapter_number}章的内容，提取其中的世界观设定信息。

【第{chapter_number}章内容】
{chapter_content[:3000]}...

请提取以下类别的世界观设定：
1. power_system - 力量体系（修炼等级、法术体系、特殊能力等）
2. geography - 地理设定（地点、地形、国家等）
3. faction - 派系体系（宗门、家族、组织等）
4. culture - 文化背景（习俗、信仰、传统等）
5. history - 历史背景（历史事件、传说等）
6. physics - 物理规则（特殊物理法则、世界规则等）
7. other - 其他设定

请以JSON数组格式返回提取的设定，每个设定包含：
- name: 设定名称（必须）
- category: 分类（必须）
- description: 设定描述（必须）
- state: 当前状态/表现（可选）
- tags: 标签数组（可选）

示例输出格式：
```json
[
  {{
    "name": "苍穹城",
    "category": "geography",
    "description": "位于大陆中央的浮空城市，是修真界的中心",
    "state": "浮空高度约万米，由四大宗门共同管理",
    "tags": ["城市", "浮空", "中心"]
  }},
  {{
    "name": "冰焰术",
    "category": "power_system",
    "description": "可以同时操控冰与火的高阶法术",
    "state": "需要双系亲和力才能修炼",
    "tags": ["法术", "高阶", "双系"]
  }}
]
```"""

    def _process_extracted_setting(
        self, setting_data: Dict[str, Any], chapter_number: int
    ) -> Optional[WorldSettingElement]:
        """处理提取到的设定.

        Args:
            setting_data: 设定数据
            chapter_number: 章节号

        Returns:
            处理后的设定元素
        """
        name = setting_data.get("name", "").strip()
        if not name:
            return None

        category_str = setting_data.get("category", "other")
        try:
            category = SettingCategory(category_str)
        except ValueError:
            category = SettingCategory.OTHER

        description = setting_data.get("description", "").strip()
        state = setting_data.get("state", "").strip()
        tags = setting_data.get("tags", [])

        # 检查是否已存在同名设定
        existing = self.get_setting_by_name(name)
        if existing:
            # 检查是否有变更
            new_state = state or description
            if new_state and new_state != existing.current_state:
                # 记录变更
                self.record_change(
                    element_id=existing.element_id,
                    chapter=chapter_number,
                    new_state=new_state,
                    reason=f"第{chapter_number}章内容提取",
                    intentional=True,
                    confidence=0.7,
                )
            return existing
        else:
            # 注册新设定
            element_id = self.register_setting(
                name=name,
                category=category,
                description=description,
                chapter=chapter_number,
                tags=tags if isinstance(tags, list) else [],
            )
            return self.settings.get(element_id)

    def get_settings_summary(self) -> str:
        """生成当前世界观设定摘要.

        Returns:
            格式化的设定摘要字符串
        """
        if not self.settings:
            return "（暂无世界观设定）"

        parts = ["【世界观设定摘要】"]

        for category in SettingCategory:
            category_settings = self.get_settings_by_category(category)
            if category_settings:
                category_name = self._get_category_display_name(category)
                parts.append(f"\n[{category_name}]")
                for setting in category_settings:
                    change_count = len(setting.change_history)
                    change_info = f"（已变更{change_count}次）" if change_count > 0 else ""
                    parts.append(
                        f"- {setting.name}：{setting.current_state}"
                        f"（第{setting.established_chapter}章建立）{change_info}"
                    )

        return "\n".join(parts)

    def get_change_timeline(self, element_id: str) -> List[Dict[str, Any]]:
        """获取特定设定元素的变更时间线.

        Args:
            element_id: 设定元素ID

        Returns:
            变更时间线列表
        """
        element = self.settings.get(element_id)
        if not element:
            return []

        timeline = [
            {
                "chapter": element.established_chapter,
                "event": "建立",
                "state": element.description,
                "timestamp": element.created_at,
            }
        ]

        for change in element.change_history:
            timeline.append(
                {
                    "chapter": change.chapter_number,
                    "event": "变更",
                    "before": change.before_state,
                    "after": change.after_state,
                    "reason": change.change_reason,
                    "intentional": change.is_intentional,
                    "timestamp": change.detected_at,
                }
            )

        # 按章节号排序
        timeline.sort(key=lambda x: x["chapter"])
        return timeline

    def to_dict(self) -> Dict[str, Any]:
        """序列化整个追踪器状态.

        Returns:
            追踪器状态字典
        """
        return {
            "settings": {sid: s.to_dict() for sid, s in self.settings.items()},
            "name_index": self._name_index.copy(),
            "statistics": self.get_statistics(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldEvolutionTracker":
        """从字典恢复追踪器状态.

        Args:
            data: 追踪器状态字典

        Returns:
            恢复的追踪器实例
        """
        tracker = cls()

        # 恢复设定
        for sid, sdata in data.get("settings", {}).items():
            element = WorldSettingElement.from_dict(sdata)
            tracker.settings[sid] = element
            tracker._name_index[element.name] = sid

        # 恢复名称索引
        tracker._name_index.update(data.get("name_index", {}))

        return tracker

    def get_statistics(self) -> Dict[str, Any]:
        """获取追踪器统计信息.

        Returns:
            统计信息字典
        """
        total = len(self.settings)
        by_category = {}
        total_changes = 0
        intentional_changes = 0

        for category in SettingCategory:
            count = len(self.get_settings_by_category(category))
            if count > 0:
                by_category[category.value] = count

        for setting in self.settings.values():
            total_changes += len(setting.change_history)
            for change in setting.change_history:
                if change.is_intentional:
                    intentional_changes += 1

        return {
            "total_settings": total,
            "by_category": by_category,
            "total_changes": total_changes,
            "intentional_changes": intentional_changes,
            "unintentional_changes": total_changes - intentional_changes,
        }
