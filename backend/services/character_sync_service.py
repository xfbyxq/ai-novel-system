"""
角色数据同步服务

确保角色数据在多模块间的一致性，提供：
1. 角色数据同步机制
2. 同步失败处理策略
3. 数据一致性验证
4. 自动修复功能
"""

from typing import Any, Dict, List, Optional, Set
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.logging_config import logger
from core.models.character import Character
from core.models.chapter import Chapter


class CharacterDataSyncService:
    """角色数据同步服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.max_retry_attempts = 2
        self.sync_history = []
    
    async def sync_character_data(
        self,
        novel_id: UUID,
        character_id: UUID,
        source_type: str = "database",
    ) -> Dict[str, Any]:
        """
        同步角色数据
        
        Args:
            novel_id: 小说 ID
            character_id: 角色 ID
            source_type: 数据源类型 ("database" | "chapters")
        
        Returns:
            同步结果
        """
        logger.info(f"🔄 开始同步角色数据：{character_id}")
        
        try:
            # 获取角色设定
            character = await self._get_character(character_id, novel_id)
            if not character:
                return {
                    "status": "failed",
                    "error": f"角色不存在：{character_id}",
                }
            
            # 获取所有章节中该角色的实际使用数据
            chapter_usage = await self._get_character_usage_from_chapters(
                novel_id, character.name
            )
            
            # 分析差异
            differences = await self._analyze_differences(
                character, chapter_usage, source_type
            )
            
            if not differences:
                logger.info(f"✅ 角色数据已同步：{character.name}")
                return {
                    "status": "success",
                    "message": "数据已同步",
                    "differences": [],
                }
            
            # 应用修复
            sync_result = await self._apply_sync_fixes(
                character, differences, source_type
            )
            
            # 记录同步历史
            self._record_sync_history(
                character_id=character_id,
                character_name=character.name,
                differences=differences,
                result=sync_result,
            )
            
            return sync_result
            
        except Exception as e:
            logger.error(f"❌ 角色数据同步失败：{e}")
            return {
                "status": "failed",
                "error": str(e),
            }
    
    async def sync_all_characters(
        self,
        novel_id: UUID
    ) -> Dict[str, Any]:
        """
        同步小说中所有角色数据
        
        Args:
            novel_id: 小说 ID
        
        Returns:
            同步结果摘要
        """
        logger.info(f"🔄 开始同步小说所有角色数据：{novel_id}")
        
        try:
            # 获取所有角色
            result = await self.db.execute(
                select(Character)
                .where(Character.novel_id == novel_id)
                .options(selectinload(Character.novel))
            )
            characters = result.scalars().all()
            
            if not characters:
                logger.warning(f"未找到角色数据：{novel_id}")
                return {
                    "status": "success",
                    "total": 0,
                    "synced": 0,
                    "failed": 0,
                }
            
            # 逐个同步
            sync_results = []
            for character in characters:
                result = await self.sync_character_data(
                    novel_id=novel_id,
                    character_id=character.id,
                )
                sync_results.append(result)
            
            # 统计结果
            total = len(characters)
            synced = sum(1 for r in sync_results if r["status"] == "success")
            failed = total - synced
            
            logger.info(
                f"✅ 角色数据同步完成：总计 {total}, 成功 {synced}, 失败 {failed}"
            )
            
            return {
                "status": "completed",
                "total": total,
                "synced": synced,
                "failed": failed,
                "results": sync_results,
            }
            
        except Exception as e:
            logger.error(f"❌ 批量角色同步失败：{e}")
            return {
                "status": "failed",
                "error": str(e),
            }
    
    async def validate_character_consistency(
        self,
        novel_id: UUID,
        character_name: str
    ) -> Dict[str, Any]:
        """
        验证角色数据一致性
        
        Args:
            novel_id: 小说 ID
            character_name: 角色名字
        
        Returns:
            验证结果
        """
        logger.info(f"🔍 验证角色数据一致性：{character_name}")
        
        try:
            # 获取角色设定
            character_result = await self.db.execute(
                select(Character)
                .where(
                    Character.novel_id == novel_id,
                    Character.name == character_name
                )
            )
            character = character_result.scalar_one_or_none()
            
            if not character:
                return {
                    "status": "failed",
                    "error": f"角色不存在：{character_name}",
                }
            
            # 从章节中提取角色使用情况
            chapter_usage = await self._get_character_usage_from_chapters(
                novel_id, character_name
            )
            
            # 验证一致性
            issues = []
            
            # 检查名字变体
            name_variants = chapter_usage.get("name_variants", [])
            if name_variants and character_name not in name_variants:
                issues.append({
                    "type": "name_inconsistency",
                    "description": f"章节中使用了不同的名字变体：{name_variants}",
                    "severity": "high",
                })
            
            # 检查属性一致性
            chapter_attributes = chapter_usage.get("attributes", {})
            for attr, value in chapter_attributes.items():
                db_value = getattr(character, attr, None)
                if db_value and db_value != value:
                    issues.append({
                        "type": "attribute_mismatch",
                        "attribute": attr,
                        "database_value": db_value,
                        "chapter_value": value,
                        "severity": "medium",
                    })
            
            if not issues:
                logger.info(f"✅ 角色数据一致：{character_name}")
                return {
                    "status": "consistent",
                    "issues": [],
                }
            else:
                logger.warning(
                    f"⚠️ 发现 {len(issues)} 个一致性问题：{character_name}"
                )
                return {
                    "status": "inconsistent",
                    "issues": issues,
                }
            
        except Exception as e:
            logger.error(f"❌ 角色一致性验证失败：{e}")
            return {
                "status": "failed",
                "error": str(e),
            }
    
    async def _get_character(
        self,
        character_id: UUID,
        novel_id: UUID
    ) -> Optional[Character]:
        """获取角色对象"""
        result = await self.db.execute(
            select(Character)
            .where(
                Character.id == character_id,
                Character.novel_id == novel_id
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_character_usage_from_chapters(
        self,
        novel_id: UUID,
        character_name: str
    ) -> Dict[str, Any]:
        """从章节中提取角色使用数据"""
        # 获取所有章节
        result = await self.db.execute(
            select(Chapter)
            .where(Chapter.novel_id == novel_id)
            .order_by(Chapter.chapter_number)
        )
        chapters = result.scalars().all()
        
        # 分析角色使用情况
        name_variants = set()
        attributes = {}
        appearances = []
        
        for chapter in chapters:
            content = chapter.content or ""
            
            # 查找角色名字出现
            if character_name in content:
                appearances.append({
                    "chapter_number": chapter.chapter_number,
                    "word_count": content.count(character_name),
                })
            
            # 查找可能的名字变体（简单实现）
            # TODO: 使用更智能的 NLP 方法
            if "苏叶" in character_name and "苏晚" in content:
                name_variants.add("苏晚")
            if "苏晚" in character_name and "苏叶" in content:
                name_variants.add("苏叶")
        
        return {
            "name_variants": list(name_variants),
            "attributes": attributes,
            "appearances": appearances,
            "total_appearances": len(appearances),
        }
    
    async def _analyze_differences(
        self,
        character: Character,
        chapter_usage: Dict[str, Any],
        source_type: str
    ) -> List[Dict[str, Any]]:
        """分析数据库与章节使用之间的差异"""
        differences = []
        
        # 检查名字变体
        name_variants = chapter_usage.get("name_variants", [])
        if name_variants and character.name not in name_variants:
            # 章节中使用的名字与数据库不同
            most_common = name_variants[0]  # 简化：使用第一个
            differences.append({
                "type": "name_mismatch",
                "database_value": character.name,
                "chapter_value": most_common,
                "severity": "high",
                "suggestion": f"更新数据库名字为 '{most_common}'",
            })
        
        return differences
    
    async def _apply_sync_fixes(
        self,
        character: Character,
        differences: List[Dict[str, Any]],
        source_type: str
    ) -> Dict[str, Any]:
        """应用同步修复"""
        if not differences:
            return {"status": "success", "message": "无需修复"}
        
        try:
            # 根据差异类型应用修复
            for diff in differences:
                if diff["type"] == "name_mismatch" and diff["severity"] == "high":
                    # 高优先级的名字不匹配，以章节为准
                    new_name = diff["chapter_value"]
                    logger.info(
                        f"🔄 更新角色名字：{character.name} → {new_name}"
                    )
                    
                    await self.db.execute(
                        update(Character)
                        .where(Character.id == character.id)
                        .values(name=new_name)
                    )
            
            await self.db.commit()
            
            return {
                "status": "success",
                "message": f"已修复 {len(differences)} 个差异",
                "fixed_differences": differences,
            }
            
        except Exception as e:
            logger.error(f"❌ 应用同步修复失败：{e}")
            await self.db.rollback()
            return {
                "status": "failed",
                "error": str(e),
            }
    
    def _record_sync_history(
        self,
        character_id: UUID,
        character_name: str,
        differences: List[Dict[str, Any]],
        result: Dict[str, Any]
    ):
        """记录同步历史"""
        self.sync_history.append({
            "timestamp": datetime.now(timezone.utc),
            "character_id": character_id,
            "character_name": character_name,
            "differences": differences,
            "result": result,
        })
    
    def get_sync_history(self) -> List[Dict[str, Any]]:
        """获取同步历史"""
        return self.sync_history


def get_character_sync_service(db: AsyncSession) -> CharacterDataSyncService:
    """获取角色同步服务实例"""
    return CharacterDataSyncService(db)
