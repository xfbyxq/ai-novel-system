from typing import Dict, Any, Optional
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from core.models.novel import Novel
from core.models.world_setting import WorldSetting
from core.models.character import Character
from core.models.plot_outline import PlotOutline


class NovelRevisionService:
    """小说修订服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def update_world_setting(
        self, 
        novel_id: str, 
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新世界观设定"""
        try:
            novel_uuid = uuid.UUID(novel_id)
        except ValueError:
            return {"error": "无效的小说 ID"}
        
        stmt = select(WorldSetting).where(WorldSetting.novel_id == novel_uuid)
        result = await self.db.execute(stmt)
        ws = result.scalar_one_or_none()
        
        if not ws:
            # 创建新的世界观
            ws = WorldSetting(novel_id=novel_uuid)
            self.db.add(ws)
        
        # 更新字段
        for field, value in updates.items():
            if hasattr(ws, field):
                setattr(ws, field, value)
        
        await self.db.commit()
        await self.db.refresh(ws)
        
        return {"success": True, "message": "世界观已更新"}
    
    async def update_character(
        self,
        novel_id: str,
        character_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新角色信息"""
        try:
            novel_uuid = uuid.UUID(novel_id)
            char_uuid = uuid.UUID(character_id)
        except ValueError:
            return {"error": "无效的 ID"}
        
        stmt = select(Character).where(
            Character.id == char_uuid,
            Character.novel_id == novel_uuid
        )
        result = await self.db.execute(stmt)
        character = result.scalar_one_or_none()
        
        if not character:
            return {"error": "角色不存在"}
        
        # 更新字段
        for field, value in updates.items():
            if hasattr(character, field):
                setattr(character, field, value)
        
        await self.db.commit()
        
        return {"success": True, "message": f"角色{character.name}已更新"}
    
    async def update_plot_outline(
        self,
        novel_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新剧情大纲"""
        try:
            novel_uuid = uuid.UUID(novel_id)
        except ValueError:
            return {"error": "无效的小说 ID"}
        
        stmt = select(PlotOutline).where(PlotOutline.novel_id == novel_uuid)
        result = await self.db.execute(stmt)
        plot = result.scalar_one_or_none()
        
        if not plot:
            plot = PlotOutline(novel_id=novel_uuid)
            self.db.add(plot)
        
        for field, value in updates.items():
            if hasattr(plot, field):
                setattr(plot, field, value)
        
        await self.db.commit()
        
        return {"success": True, "message": "剧情大纲已更新"}
    
    async def update_novel_info(
        self,
        novel_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新小说基本信息"""
        try:
            novel_uuid = uuid.UUID(novel_id)
        except ValueError:
            return {"error": "无效的小说 ID"}
        
        stmt = select(Novel).where(Novel.id == novel_uuid)
        result = await self.db.execute(stmt)
        novel = result.scalar_one_or_none()
        
        if not novel:
            return {"error": "小说不存在"}
        
        # 过滤掉不能直接更新的字段
        allowed_fields = ['title', 'synopsis', 'tags', 'target_platform', 'length_type']
        for field, value in updates.items():
            if field in allowed_fields and hasattr(novel, field):
                setattr(novel, field, value)
        
        await self.db.commit()
        
        return {"success": True, "message": "小说信息已更新"}
