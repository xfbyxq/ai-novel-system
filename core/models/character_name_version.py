import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship

from core.database import Base


class CharacterNameVersion(Base):
    """角色名字版本记录"""
    __tablename__ = "character_name_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id = Column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    old_name = Column(String(100), nullable=False)
    new_name = Column(String(100), nullable=False)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    changed_by = Column(String(100), nullable=False, default="system")
    reason = Column(Text, nullable=True)
    is_active = Column(default=True)

    character = relationship("Character", back_populates="name_versions")


class CharacterNameVersionService:
    """角色名字版本管理服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_version_record(
        self,
        character_id: uuid.UUID,
        old_name: str,
        new_name: str,
        changed_by: str = "system",
        reason: Optional[str] = None,
    ) -> CharacterNameVersion:
        """创建名字版本记录"""
        version = CharacterNameVersion(
            character_id=character_id,
            old_name=old_name,
            new_name=new_name,
            changed_by=changed_by,
            reason=reason,
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(version)
        return version

    async def get_version_history(
        self,
        character_id: uuid.UUID,
        limit: int = 50,
    ) -> list[CharacterNameVersion]:
        """获取角色名字版本历史"""
        result = await self.db.execute(
            select(CharacterNameVersion)
            .where(CharacterNameVersion.character_id == character_id)
            .order_by(CharacterNameVersion.changed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_version_at_time(
        self,
        character_id: uuid.UUID,
        target_time: datetime,
    ) -> Optional[CharacterNameVersion]:
        """获取指定时间点的名字版本"""
        result = await self.db.execute(
            select(CharacterNameVersion)
            .where(CharacterNameVersion.character_id == character_id)
            .where(CharacterNameVersion.changed_at <= target_time)
            .order_by(CharacterNameVersion.changed_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def compare_versions(
        self,
        version_id_1: uuid.UUID,
        version_id_2: uuid.UUID,
    ) -> dict:
        """对比两个版本的差异"""
        version_1 = await self.db.get(CharacterNameVersion, version_id_1)
        version_2 = await self.db.get(CharacterNameVersion, version_id_2)

        if not version_1 or not version_2:
            return {"error": "版本不存在"}

        return {
            "version_1": {
                "id": str(version_1.id),
                "old_name": version_1.old_name,
                "new_name": version_1.new_name,
                "changed_at": version_1.changed_at.isoformat(),
                "changed_by": version_1.changed_by,
                "reason": version_1.reason,
            },
            "version_2": {
                "id": str(version_2.id),
                "old_name": version_2.old_name,
                "new_name": version_2.new_name,
                "changed_at": version_2.changed_at.isoformat(),
                "changed_by": version_2.changed_by,
                "reason": version_2.reason,
            },
            "differences": {
                "name_changed": version_1.new_name != version_2.new_name,
                "reason_changed": version_1.reason != version_2.reason,
            },
        }

    async def revert_to_version(
        self,
        character_id: uuid.UUID,
        target_version_id: uuid.UUID,
        reverted_by: str = "system",
    ) -> Optional[CharacterNameVersion]:
        """回溯到指定版本"""
        target_version = await self.db.get(CharacterNameVersion, target_version_id)
        if not target_version:
            return None

        current_version = await self.db.execute(
            select(CharacterNameVersion)
            .where(CharacterNameVersion.character_id == character_id)
            .where(CharacterNameVersion.is_active == True)
            .order_by(CharacterNameVersion.changed_at.desc())
            .limit(1)
        )
        current = current_version.scalar_one_or_none()

        if current and current.new_name == target_version.new_name:
            return None

        new_version = CharacterNameVersion(
            character_id=character_id,
            old_name=current.new_name if current else "Unknown",
            new_name=target_version.new_name,
            changed_by=reverted_by,
            reason=f"版本回溯到 {target_version_id}",
        )
        self.db.add(new_version)
        await self.db.commit()
        await self.db.refresh(new_version)
        return new_version

    async def get_current_name(
        self,
        character_id: uuid.UUID,
    ) -> Optional[str]:
        """获取角色当前名字"""
        result = await self.db.execute(
            select(CharacterNameVersion)
            .where(CharacterNameVersion.character_id == character_id)
            .where(CharacterNameVersion.is_active == True)
            .order_by(CharacterNameVersion.changed_at.desc())
            .limit(1)
        )
        version = result.scalar_one_or_none()
        return version.new_name if version else None

    async def validate_name_change(
        self,
        character_id: uuid.UUID,
        new_name: str,
    ) -> dict:
        """验证名字变更是否合理"""
        history = await self.get_version_history(character_id, limit=10)

        if not history:
            return {"valid": True, "warnings": []}

        warnings = []
        last_version = history[0]

        if last_version.new_name == new_name:
            warnings.append(f"名字与新版本相同：{new_name}")

        similar_names = [v for v in history if v.new_name.lower() == new_name.lower()]
        if similar_names:
            warnings.append(f"发现相似名字的历史版本")

        return {
            "valid": len(warnings) == 0,
            "warnings": warnings,
            "previous_names": [v.new_name for v in history[:5]],
        }
