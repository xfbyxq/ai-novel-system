"""修订数据验证服务 - 验证用户反馈中的实体是否存在."""

import re
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Chapter, Character, PlotOutline, WorldSetting


@dataclass
class EntityValidationResult:
    """单个实体验证结果."""

    entity_type: str  # character, chapter, location, world_element
    entity_name: str  # 实体名称
    exists: bool  # 是否存在
    matched_item: Optional[dict] = None  # 匹配到的数据库记录
    suggestions: list[str] = field(default_factory=list)  # 相似名称建议


@dataclass
class ValidationReport:
    """完整验证报告."""

    novel_id: str
    is_valid: bool  # 整体是否有效
    entity_count: int  # 检测到的实体数量
    valid_count: int  # 有效实体数量
    invalid_count: int  # 无效实体数量
    character_results: list[EntityValidationResult] = field(default_factory=list)
    chapter_results: list[EntityValidationResult] = field(default_factory=list)
    location_results: list[EntityValidationResult] = field(default_factory=list)
    world_element_results: list[EntityValidationResult] = field(default_factory=list)
    extracted_entities: dict = field(default_factory=dict)  # 提取的原始实体
    warning_message: Optional[str] = None  # 警告信息
    summary: str = ""  # 人类可读的总结


class RevisionDataValidator:
    """修订数据验证器 - 验证用户反馈中的实体是否存在.

    在处理小说修订请求前，先验证用户提到的角色、地点、章节等是否真实存在于数据库中，
    以避免基于不存在的数据生成错误的修订建议。
    """

    def __init__(self, db: AsyncSession):
        """初始化验证器.

        Args:
            db: 数据库会话
        """
        self.db = db

    async def validate_feedback(
        self, user_feedback: str, novel_id: str
    ) -> ValidationReport:
        """验证用户反馈中的实体是否存在.

        核心流程：
        1. 从用户反馈中提取各类实体（角色、章节、地点等）
        2. 查询数据库验证这些实体是否存在
        3. 生成详细的验证报告

        Args:
            user_feedback: 用户反馈文本
            novel_id: 小说ID

        Returns:
            ValidationReport: 验证报告
        """
        # Step 1: 加载小说上下文用于验证（需要先加载才能提取角色）
        context = await self._load_context(novel_id)

        # Step 2: 提取实体（传入context以检测角色名）
        extracted = self._extract_entities(user_feedback, context)

        # Step 3: 验证各类实体
        report = ValidationReport(
            novel_id=novel_id,
            is_valid=True,
            entity_count=0,
            valid_count=0,
            invalid_count=0,
            extracted_entities=extracted,
        )

        # 验证角色
        if extracted.get("characters"):
            char_results = await self._validate_characters(
                extracted["characters"], context
            )
            report.character_results = char_results

        # 验证章节
        if extracted.get("chapters"):
            chapter_results = await self._validate_chapters(
                extracted["chapters"], context
            )
            report.chapter_results = chapter_results

        # 验证地点/世界元素
        if extracted.get("locations") or extracted.get("world_elements"):
            loc_results = await self._validate_locations(
                extracted.get("locations", []), context
            )
            report.location_results = loc_results
            world_results = await self._validate_world_elements(
                extracted.get("world_elements", []), context
            )
            report.world_element_results = world_results

        # 计算统计数据
        all_results = (
            report.character_results
            + report.chapter_results
            + report.location_results
            + report.world_element_results
        )
        report.entity_count = len(all_results)
        report.valid_count = sum(1 for r in all_results if r.exists)
        report.invalid_count = report.entity_count - report.valid_count
        report.is_valid = report.invalid_count == 0

        # 生成警告信息
        report.warning_message = self._generate_warning(report, context)
        report.summary = self._generate_summary(report, context)

        return report

    def _extract_entities(self, feedback: str, context: dict) -> dict:
        """从用户反馈中提取实体.

        使用规则匹配提取常见的实体类型。

        Args:
            feedback: 用户反馈文本
            context: 小说上下文（包含角色名列表）

        Returns:
            dict: 提取的实体字典
        """
        extracted = {
            "characters": [],
            "chapters": [],
            "locations": [],
            "world_elements": [],
        }

        # 首先，从context中获取已知角色名，检测反馈中是否提到
        character_names = context.get("character_names", [])
        for name in character_names:
            if name in feedback:
                extracted["characters"].append(name)

        # 提取章节号（匹配 "第X章"、"第X话"、"章节X" 等模式）
        chapter_patterns = [
            r"第\s*([零一二三四五六七八九十百千\d]+)\s*[章节话]",
            r"章节\s*([零一二三四五六七八九十百千\d]+)",
            r"(\d+)\s*[章节话]",
        ]
        for pattern in chapter_patterns:
            matches = re.findall(pattern, feedback)
            for match in matches:
                # 转换中文数字
                chapter_num = self._chinese_to_number(match)
                if chapter_num and chapter_num not in extracted["chapters"]:
                    extracted["chapters"].append(chapter_num)

        # 提取常见的世界元素关键词
        world_keywords = [
            "世界观", "设定", "修炼体系", "功法", "境界", "能力", "武器",
            "门派", "宗门", "势力", "国家", "种族", "血脉", "天赋",
        ]
        for keyword in world_keywords:
            if keyword in feedback:
                # 提取关键词附近的文本作为世界元素
                idx = feedback.find(keyword)
                start = max(0, idx - 10)
                end = min(len(feedback), idx + len(keyword) + 10)
                element = feedback[start:end].strip()
                if element and element not in extracted["world_elements"]:
                    extracted["world_elements"].append(element)

        # 提取地点关键词
        location_keywords = [
            "地点", "位置", "城市", "国家", "地区", "场景",
            "在哪里", "什么地点", "什么地方",
        ]
        for keyword in location_keywords:
            if keyword in feedback:
                idx = feedback.find(keyword)
                start = max(0, idx - 5)
                end = min(len(feedback), idx + len(keyword) + 5)
                location = feedback[start:end].strip()
                if location and location not in extracted["locations"]:
                    extracted["locations"].append(location)

        return extracted

    def _chinese_to_number(self, text: str) -> Optional[int]:
        """将中文数字转换为整数.

        Args:
            text: 中文数字字符串

        Returns:
            int: 转换后的整数，转换失败返回None
        """
        chinese_map = {
            "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
            "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
            "百": 100, "千": 1000, "万": 10000,
        }

        try:
            # 如果已经是数字字符串，直接转换
            return int(text)
        except ValueError:
            pass

        # 处理纯中文数字
        result = 0
        temp = 0
        for char in text:
            if char in chinese_map:
                value = chinese_map[char]
                if value >= 10:
                    if temp == 0:
                        temp = 1
                    result += temp * value
                    temp = 0
                else:
                    temp += value
        result += temp
        return result if result > 0 else None

    async def _load_context(self, novel_id: str) -> dict:
        """加载小说上下文用于验证.

        Args:
            novel_id: 小说ID

        Returns:
            dict: 上下文字典
        """
        novel_uuid = UUID(novel_id)

        # 并行加载所有相关数据
        stmt_chars = select(Character).where(Character.novel_id == novel_uuid)
        result_chars = await self.db.execute(stmt_chars)
        characters = result_chars.scalars().all()

        stmt_chapters = (
            select(Chapter)
            .where(Chapter.novel_id == novel_uuid)
            .order_by(Chapter.chapter_number)
        )
        result_chapters = await self.db.execute(stmt_chapters)
        chapters = result_chapters.scalars().all()

        stmt_ws = select(WorldSetting).where(WorldSetting.novel_id == novel_uuid)
        result_ws = await self.db.execute(stmt_ws)
        world_setting = result_ws.scalar_one_or_none()

        stmt_outline = select(PlotOutline).where(PlotOutline.novel_id == novel_uuid)
        result_outline = await self.db.execute(stmt_outline)
        plot_outline = result_outline.scalar_one_or_none()

        return {
            "characters": {c.name: c for c in characters},
            "character_names": [c.name for c in characters],
            "chapters": {c.chapter_number: c for c in chapters},
            "chapter_numbers": [c.chapter_number for c in chapters],
            "world_setting": world_setting,
            "plot_outline": plot_outline,
        }

    async def _validate_characters(
        self, names: list[str], context: dict
    ) -> list[EntityValidationResult]:
        """验证角色是否存在.

        Args:
            names: 角色名列表
            context: 小说上下文

        Returns:
            list[EntityValidationResult]: 验证结果列表
        """
        results = []
        characters_db = context["characters"]
        character_names = [n.lower() for n in context["character_names"]]

        for name in names:
            name_lower = name.lower()
            # 精确匹配
            if name in characters_db:
                results.append(
                    EntityValidationResult(
                        entity_type="character",
                        entity_name=name,
                        exists=True,
                        matched_item={
                            "id": str(characters_db[name].id),
                            "name": characters_db[name].name,
                            "role_type": characters_db[name].role_type,
                            "personality": characters_db[name].personality,
                        },
                    )
                )
            # 模糊匹配（忽略大小写）
            elif name_lower in character_names:
                # 找到原始名称
                for orig_name in characters_db:
                    if orig_name.lower() == name_lower:
                        results.append(
                            EntityValidationResult(
                                entity_type="character",
                                entity_name=name,
                                exists=True,
                                matched_item={
                                    "id": str(characters_db[orig_name].id),
                                    "name": characters_db[orig_name].name,
                                    "role_type": characters_db[orig_name].role_type,
                                },
                            )
                        )
                        break
            else:
                # 找不到，提供相似建议
                suggestions = self._find_similar_names(name, context["character_names"])
                results.append(
                    EntityValidationResult(
                        entity_type="character",
                        entity_name=name,
                        exists=False,
                        suggestions=suggestions,
                    )
                )

        return results

    async def _validate_chapters(
        self, chapter_nums: list[int], context: dict
    ) -> list[EntityValidationResult]:
        """验证章节是否存在.

        Args:
            chapter_nums: 章节号列表
            context: 小说上下文

        Returns:
            list[EntityValidationResult]: 验证结果列表
        """
        results = []
        chapters_db = context["chapters"]

        for num in chapter_nums:
            if num in chapters_db:
                chapter = chapters_db[num]
                results.append(
                    EntityValidationResult(
                        entity_type="chapter",
                        entity_name=f"第{num}章",
                        exists=True,
                        matched_item={
                            "id": str(chapter.id),
                            "chapter_number": chapter.chapter_number,
                            "title": chapter.title,
                            "word_count": chapter.word_count,
                        },
                    )
                )
            else:
                # 找到可用的章节建议
                available = sorted(context["chapter_numbers"])
                suggestions = [f"第{c}章" for c in available[:5]] if available else []
                results.append(
                    EntityValidationResult(
                        entity_type="chapter",
                        entity_name=f"第{num}章",
                        exists=False,
                        suggestions=suggestions,
                    )
                )

        return results

    async def _validate_locations(
        self, locations: list[str], context: dict
    ) -> list[EntityValidationResult]:
        """验证地点是否存在.

        目前通过检查世界设定中的地理信息来验证。

        Args:
            locations: 地点列表
            context: 小说上下文

        Returns:
            list[EntityValidationResult]: 验证结果列表
        """
        results = []
        world_setting = context.get("world_setting")

        if not world_setting:
            for loc in locations:
                results.append(
                    EntityValidationResult(
                        entity_type="location",
                        entity_name=loc,
                        exists=False,
                        suggestions=["该小说尚未设定世界观，请先创建世界观"],
                    )
                )
            return results

        # 从世界设定中提取地点
        geography = world_setting.geography or {}
        known_locations = []

        # 提取各种地理信息
        if isinstance(geography, dict):
            for key, value in geography.items():
                if isinstance(value, list):
                    known_locations.extend([str(v) for v in value])
                elif isinstance(value, str):
                    known_locations.append(value)

        for loc in locations:
            loc_str = str(loc)
            # 简单检查是否在已知地点中
            exists = any(
                loc_str.lower() in str(known_loc).lower()
                for known_loc in known_locations
            )
            results.append(
                EntityValidationResult(
                    entity_type="location",
                    entity_name=loc_str,
                    exists=exists,
                    suggestions=(
                        known_locations[:3] if not exists and known_locations else []
                    ),
                )
            )

        return results

    async def _validate_world_elements(
        self, elements: list[str], context: dict
    ) -> list[EntityValidationResult]:
        """验证世界元素是否存在.

        Args:
            elements: 世界元素列表
            context: 小说上下文

        Returns:
            list[EntityValidationResult]: 验证结果列表
        """
        results = []
        world_setting = context.get("world_setting")

        if not world_setting:
            for elem in elements:
                results.append(
                    EntityValidationResult(
                        entity_type="world_element",
                        entity_name=elem,
                        exists=False,
                        suggestions=["该小说尚未设定世界观，请先创建世界观"],
                    )
                )
            return results

        # 从世界设定中提取已知元素
        known_elements = []
        for field_name in ["power_system", "factions", "rules"]:
            field_data = getattr(world_setting, field_name, None) or {}
            if isinstance(field_data, dict):
                known_elements.extend(field_data.keys())
            elif isinstance(field_data, list):
                known_elements.extend([str(e) for e in field_data])

        for elem in elements:
            exists = any(
                str(elem).lower() in str(known).lower() for known in known_elements
            )
            results.append(
                EntityValidationResult(
                    entity_type="world_element",
                    entity_name=elem,
                    exists=exists,
                )
            )

        return results

    def _find_similar_names(
        self, target: str, names: list[str], threshold: float = 0.6
    ) -> list[str]:
        """查找相似的角色名称.

        使用简单的编辑距离和包含关系匹配。

        Args:
            target: 目标名称
            names: 候选名称列表
            threshold: 相似度阈值

        Returns:
            list[str]: 相似名称列表
        """
        target_lower = target.lower()
        suggestions = []

        for name in names:
            name_lower = name.lower()

            # 完全包含
            if target_lower in name_lower or name_lower in target_lower:
                suggestions.append(name)
                continue

            # 首字母匹配
            if target_lower[:2] == name_lower[:2]:
                suggestions.append(name)

        return suggestions[:3]  # 最多返回3个建议

    def _generate_warning(
        self, report: ValidationReport, context: dict
    ) -> Optional[str]:
        """生成验证警告信息.

        Args:
            report: 验证报告
            context: 上下文

        Returns:
            Optional[str]: 警告信息
        """
        if report.invalid_count == 0:
            return None

        warnings = []

        # 角色不存在警告
        invalid_chars = [
            r for r in report.character_results if not r.exists
        ]
        if invalid_chars:
            names = [r.entity_name for r in invalid_chars]
            suggestions = []
            for r in invalid_chars:
                if r.suggestions:
                    suggestions.extend(r.suggestions[:1])
            msg = f"角色 {', '.join(names)} 在小说中不存在"
            if suggestions:
                msg += f"，您是否指的是：{', '.join(suggestions[:3])}"
            warnings.append(msg)

        # 章节不存在警告
        invalid_chapters = [
            r for r in report.chapter_results if not r.exists
        ]
        if invalid_chapters:
            nums = [r.entity_name for r in invalid_chapters]
            max_chapter = max(context["chapter_numbers"]) if context["chapter_numbers"] else 0
            warnings.append(
                f"章节 {', '.join(nums)} 不存在，小说目前共 {max_chapter} 章"
            )

        return " | ".join(warnings)

    def _generate_summary(self, report: ValidationReport, context: dict) -> str:
        """生成人类可读的验证总结.

        Args:
            report: 验证报告
            context: 上下文

        Returns:
            str: 验证总结
        """
        if report.entity_count == 0:
            return "未检测到具体角色或章节引用，将基于通用理解进行分析"

        parts = []

        # 角色统计
        if report.character_results:
            valid_chars = [r for r in report.character_results if r.exists]
            invalid_chars = [r for r in report.character_results if not r.exists]
            if valid_chars:
                names = [r.matched_item["name"] for r in valid_chars]
                parts.append(f"已验证角色：{', '.join(names)}")
            if invalid_chars:
                names = [r.entity_name for r in invalid_chars]
                parts.append(f"未知角色：{', '.join(names)}")

        # 章节统计
        if report.chapter_results:
            valid_chapters = [r for r in report.chapter_results if r.exists]
            invalid_chapters = [r for r in report.chapter_results if not r.exists]
            if valid_chapters:
                nums = [str(r.matched_item["chapter_number"]) for r in valid_chapters]
                parts.append(f"已验证章节：第{', 第'.join(nums)}章")
            if invalid_chapters:
                nums = [r.entity_name for r in invalid_chapters]
                parts.append(f"未知章节：{', '.join(nums)}")

        return "；".join(parts) if parts else "所有实体验证通过"
