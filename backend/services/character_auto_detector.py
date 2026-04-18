"""角色自动检测器 - 从章节内容中自动识别并注册新角色.

每章生成后，使用 LLM 从章节内容中提取新出现的角色，
对比现有角色库进行去重，然后自动注册到数据库。
"""

import json
import re
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from core.logging_config import logger
from core.models.chapter import Chapter
from core.models.character import Character
from llm.cost_tracker import CostTracker
from llm.prompt_manager import PromptManager
from llm.qwen_client import QwenClient


class CharacterAutoDetector:
    """角色自动检测器.

    核心功能：
    1. 使用 LLM 从章节内容中提取角色信息
    2. 对比现有角色库进行多层去重
    3. 自动注册新角色到数据库
    """

    def __init__(
        self,
        db: AsyncSession,
        client: QwenClient,
        cost_tracker: CostTracker,
    ):
        """初始化方法."""
        self.db = db
        self.client = client
        self.cost_tracker = cost_tracker
        self.pm = PromptManager

    async def detect_and_register_new_characters(
        self,
        novel_id: UUID,
        chapter_number: int,
        chapter_content: str,
        existing_characters: List[Character],
    ) -> List[Character]:
        """检测并注册新角色（对外入口方法）.

        整体用 try/except 包裹，绝不抛异常，确保不阻塞章节生成流程.

        Args:
            novel_id: 小说 ID
            chapter_number: 章节号
            chapter_content: 章节内容
            existing_characters: 现有角色列表（保留参数兼容性，内部会重新查询数据库）

        Returns:
            新创建的 Character 列表（可能为空）
        """
        try:
            if not chapter_content or not chapter_content.strip():
                return []

            # 关键修复：直接从数据库查询最新角色列表，
            # 避免因 expire_on_commit=False 导致 ORM 关系缓存过期而产生重复角色
            db_stmt = select(Character).where(Character.novel_id == novel_id)
            db_result = await self.db.execute(db_stmt)
            db_characters = list(db_result.scalars().all())

            existing_names = [c.name for c in db_characters]

            # 1. LLM 提取章节中的角色
            extracted = await self._extract_characters_from_content(
                chapter_content=chapter_content,
                chapter_number=chapter_number,
                existing_character_names=existing_names,
            )

            if not extracted:
                logger.info(f"[CharacterAutoDetector] 第{chapter_number}章未检测到新角色")
                return []

            # 2. 多层去重过滤（使用数据库最新数据）
            new_chars = self._filter_new_characters(extracted, db_characters)

            if not new_chars:
                logger.info(
                    f"[CharacterAutoDetector] 第{chapter_number}章提取到角色均已存在，无需注册"
                )
                return []

            # 3. 注册新角色到数据库
            registered = await self._register_characters(
                novel_id=novel_id,
                chapter_number=chapter_number,
                new_chars=new_chars,
            )

            logger.info(
                f"[CharacterAutoDetector] 第{chapter_number}章成功注册 "
                f"{len(registered)} 个新角色: {[c.name for c in registered]}"
            )
            return registered

        except Exception as e:
            logger.warning(f"[CharacterAutoDetector] 角色自动检测异常（不影响章节生成）: {e}")
            return []

    async def _extract_characters_from_content(
        self,
        chapter_content: str,
        chapter_number: int,
        existing_character_names: List[str],
    ) -> List[Dict[str, Any]]:
        """调用 LLM 从章节内容中提取角色信息.

        Args:
            chapter_content: 章节内容
            chapter_number: 章节号
            existing_character_names: 已有角色名列表

        Returns:
            LLM 解析后的角色字典列表
        """
        # 截断内容避免 token 过长
        max_len = settings.CHARACTER_DETECTION_MAX_CONTENT_LENGTH
        content_truncated = chapter_content[:max_len]

        names_str = (
            "、".join(existing_character_names) if existing_character_names else "（暂无已知角色）"
        )

        task_prompt = self.pm.format(
            self.pm.CHARACTER_DETECTION_TASK,
            existing_character_names=names_str,
            chapter_number=chapter_number,
            chapter_content=content_truncated,
        )

        try:
            response = await self.client.chat(
                prompt=task_prompt,
                system=self.pm.CHARACTER_DETECTION_SYSTEM,
                temperature=0.2,
                max_tokens=1024,
            )

            usage = response.get("usage", {})
            self.cost_tracker.record(
                agent_name="新角色检测器",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                cost_category="base",
            )

            result = self._extract_json_array(response.get("content", ""))
            return result

        except Exception as e:
            logger.warning(f"[CharacterAutoDetector] LLM 提取角色失败: {e}")
            return []

    def _filter_new_characters(
        self,
        extracted: List[Dict[str, Any]],
        existing: List[Character],
    ) -> List[Dict[str, Any]]:
        """四层去重过滤，确保只返回真正的新角色.

        去重策略：
        1. 精确名字匹配（标准化后）
        2. 子串包含（如 "小明" vs "李小明"）
        3. name_variants 交叉检查
        4. 置信度阈值过滤

        Args:
            extracted: LLM 提取的角色列表
            existing: 现有角色列表

        Returns:
            仅包含真正新角色的列表
        """
        existing_names_normalized = {self._normalize_name(c.name) for c in existing}
        existing_names_raw = [c.name for c in existing]

        result = []

        for char in extracted:
            name = char.get("name", "").strip()
            if not name:
                continue

            name_normalized = self._normalize_name(name)
            confidence = char.get("confidence", 0.5)

            # 层 4: 置信度过滤
            threshold = settings.CHARACTER_DETECTION_CONFIDENCE_THRESHOLD
            if confidence < threshold:
                logger.debug(
                    f"[CharacterAutoDetector] 角色「{name}」置信度 {confidence} "
                    f"低于阈值 {threshold}，跳过"
                )
                continue

            # 层 1: 精确名字匹配
            if name_normalized in existing_names_normalized:
                continue

            # 层 2: 子串包含
            is_substring = False
            for existing_name in existing_names_raw:
                existing_norm = self._normalize_name(existing_name)
                # 新角色名是已有角色名的子串，或反之
                if (
                    len(name_normalized) >= 2
                    and len(existing_norm) >= 2
                    and (name_normalized in existing_norm or existing_norm in name_normalized)
                ):
                    is_substring = True
                    logger.debug(
                        f"[CharacterAutoDetector] 角色「{name}」与已有角色"
                        f"「{existing_name}」存在子串关系，跳过"
                    )
                    break
            if is_substring:
                continue

            # 层 3: name_variants 交叉检查
            variants = char.get("name_variants", [])
            variant_match = False
            for variant in variants:
                variant_norm = self._normalize_name(variant)
                if variant_norm in existing_names_normalized:
                    variant_match = True
                    logger.debug(
                        f"[CharacterAutoDetector] 角色「{name}」的别名"
                        f"「{variant}」匹配已有角色，跳过"
                    )
                    break
                # 别名也做子串检查
                for existing_name in existing_names_raw:
                    existing_norm = self._normalize_name(existing_name)
                    if (
                        len(variant_norm) >= 2
                        and len(existing_norm) >= 2
                        and (variant_norm in existing_norm or existing_norm in variant_norm)
                    ):
                        variant_match = True
                        break
                if variant_match:
                    break
            if variant_match:
                continue

            # 通过全部去重层，确认为新角色
            result.append(char)
            # 将新角色名也加入已有集合，避免本次批量提取中重复
            existing_names_normalized.add(name_normalized)
            existing_names_raw.append(name)

        return result

    async def _register_characters(
        self,
        novel_id: UUID,
        chapter_number: int,
        new_chars: List[Dict[str, Any]],
    ) -> List[Character]:
        """将新角色批量注册到数据库.

        Args:
            novel_id: 小说 ID
            chapter_number: 首次出现的章节号
            new_chars: 新角色信息列表

        Returns:
            创建的 Character 对象列表
        """
        created = []

        for char_data in new_chars:
            try:
                name = char_data.get("name", "").strip()
                if not name:
                    continue

                # 插入前再次检查数据库，防止竞态条件导致重复创建
                existing_stmt = select(Character).where(
                    Character.novel_id == novel_id,
                    func.lower(Character.name) == name.lower(),
                )
                existing_result = await self.db.execute(existing_stmt)
                if existing_result.scalar_one_or_none():
                    logger.info(f"[CharacterAutoDetector] 角色「{name}」在数据库中已存在，跳过注册")
                    continue

                # 确定 role_type（允许 minor/supporting/antagonist，不允许自动标记为 protagonist）
                role_type = char_data.get("role_type", "minor")
                if role_type not in ("minor", "supporting", "antagonist"):
                    role_type = "minor"

                # 确定 gender
                gender = char_data.get("gender", "unknown")
                if gender not in ("male", "female", "other"):
                    gender = None

                character = Character(
                    novel_id=novel_id,
                    name=name,
                    role_type=role_type,
                    gender=gender,
                    background=char_data.get("brief_description", ""),
                    first_appearance_chapter=chapter_number,
                    status="alive",
                )
                self.db.add(character)
                created.append(character)

            except Exception as e:
                logger.warning(
                    f"[CharacterAutoDetector] 注册角色「{char_data.get('name', '?')}」失败: {e}"
                )
                continue

        # 回填章节的 characters_appeared 字段
        if created:
            try:
                await self.db.flush()  # flush 以获取角色 ID
                stmt = select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                )
                result = await self.db.execute(stmt)
                chapter_obj = result.scalar_one_or_none()
                if chapter_obj:
                    existing_ids = chapter_obj.characters_appeared or []
                    new_ids = [c.id for c in created]
                    chapter_obj.characters_appeared = existing_ids + new_ids
            except Exception as e:
                logger.warning(f"[CharacterAutoDetector] 回填 characters_appeared 失败: {e}")

        return created

    @staticmethod
    def _normalize_name(name: str) -> str:
        """标准化角色名字，用于去重比较.

        去除空格、标点、常见称呼后缀等.

        Args:
            name: 原始名字

        Returns:
            标准化后的名字
        """
        name = name.strip()
        # 去除常见称呼后缀
        suffixes = [
            "先生",
            "小姐",
            "女士",
            "大人",
            "前辈",
            "师兄",
            "师姐",
            "师弟",
            "师妹",
            "师父",
            "师傅",
            "大师",
            "长老",
            "掌门",
            "宗主",
            "公子",
            "姑娘",
            "道友",
            "阁下",
        ]
        for suffix in suffixes:
            if name.endswith(suffix) and len(name) > len(suffix):
                name = name[: -len(suffix)]
                break
        # 去除空格和标点
        name = re.sub(r"[\s·・\-]", "", name)
        return name

    @staticmethod
    def _extract_json_array(text: str) -> List[Dict[str, Any]]:
        """从 LLM 响应中提取 JSON 数组.

        多层策略，兼容各种 LLM 输出格式.

        Args:
            text: LLM 响应的原始文本

        Returns:
            解析后的字典列表，全部失败则返回空列表
        """
        text = text.strip()

        # 策略 1: 直接解析
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        # 策略 2: 提取 markdown 代码块
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                result = json.loads(match.group(1).strip())
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        # 策略 3: 提取方括号内的 JSON 数组
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            json_str = text[start : end + 1]
            try:
                result = json.loads(json_str)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                # 策略 4: 尝试修复不完整的 JSON
                open_brackets = json_str.count("[")
                close_brackets = json_str.count("]")
                open_braces = json_str.count("{")
                close_braces = json_str.count("}")
                missing = "}" * (open_braces - close_braces) + "]" * (
                    open_brackets - close_brackets
                )
                if missing:
                    try:
                        result = json.loads(json_str + missing)
                        if isinstance(result, list):
                            return result
                    except json.JSONDecodeError:
                        pass

        logger.warning(
            f"[CharacterAutoDetector] JSON 数组解析失败，返回空列表。" f"文本片段：{text[:100]}..."
        )
        return []
