from typing import Optional, Dict, Any, List
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.models.novel import Novel
from core.models.world_setting import WorldSetting
from core.models.character import Character
from core.models.plot_outline import PlotOutline
from core.models.chapter import Chapter


class NovelQueryService:
    """小说查询服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def search_novels(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索小说"""
        # 简单实现：搜索标题包含关键词的小说
        stmt = select(Novel).where(Novel.title.ilike(f"%{keyword}%")).limit(limit)
        result = await self.db.execute(stmt)
        novels = result.scalars().all()
        
        return [
            {
                "id": str(n.id),
                "title": n.title,
                "genre": n.genre,
                "status": n.status,
                "word_count": n.word_count,
                "chapter_count": n.chapter_count
            }
            for n in novels
        ]
    
    async def get_novel_by_id(self, novel_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取小说"""
        import uuid
        try:
            novel_uuid = uuid.UUID(novel_id)
        except ValueError:
            return None
        
        stmt = select(Novel).where(Novel.id == novel_uuid)
        result = await self.db.execute(stmt)
        novel = result.scalar_one_or_none()
        
        if not novel:
            return None
        
        return {
            "id": str(novel.id),
            "title": novel.title,
            "author": novel.author,
            "genre": novel.genre,
            "tags": novel.tags,
            "status": novel.status,
            "word_count": novel.word_count,
            "chapter_count": novel.chapter_count,
            "synopsis": novel.synopsis,
            "target_platform": novel.target_platform
        }
    
    async def get_world_setting(self, novel_id: str) -> Dict[str, Any]:
        """获取世界观设定"""
        import uuid
        try:
            novel_uuid = uuid.UUID(novel_id)
        except ValueError:
            return {"error": "无效的小说 ID"}
        
        stmt = select(WorldSetting).where(WorldSetting.novel_id == novel_uuid)
        result = await self.db.execute(stmt)
        ws = result.scalar_one_or_none()
        
        if not ws:
            return {"error": "暂无世界观设定"}
        
        return {
            "world_name": ws.world_name,
            "world_type": ws.world_type,
            "power_system": ws.power_system or {},
            "geography": ws.geography or {},
            "factions": ws.factions or {},
            "rules": ws.rules or {},
            "timeline": ws.timeline or {},
            "special_elements": ws.special_elements or {}
        }
    
    async def get_characters(self, novel_id: str, role_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取角色列表"""
        import uuid
        try:
            novel_uuid = uuid.UUID(novel_id)
        except ValueError:
            return []
        
        stmt = select(Character).where(Character.novel_id == novel_uuid)
        
        if role_type:
            stmt = stmt.where(Character.role_type == role_type)
        
        result = await self.db.execute(stmt)
        characters = result.scalars().all()
        
        return [
            {
                "id": str(c.id),
                "name": c.name,
                "role_type": c.role_type.value if hasattr(c.role_type, 'value') else str(c.role_type or "unknown"),
                "gender": c.gender.value if hasattr(c.gender, 'value') else str(c.gender or "unknown"),
                "age": c.age,
                "appearance": c.appearance,
                "personality": c.personality,
                "background": c.background,
                "goals": c.goals,
                "abilities": c.abilities or {}
            }
            for c in characters
        ]
    
    async def get_plot_outline(self, novel_id: str) -> Dict[str, Any]:
        """获取剧情大纲"""
        import uuid
        try:
            novel_uuid = uuid.UUID(novel_id)
        except ValueError:
            return {"error": "无效的小说 ID"}
        
        stmt = select(PlotOutline).where(PlotOutline.novel_id == novel_uuid)
        result = await self.db.execute(stmt)
        plot = result.scalar_one_or_none()
        
        if not plot:
            return {"error": "暂无剧情大纲"}
        
        return {
            "structure_type": plot.structure_type,
            "volumes": plot.volumes or [],
            "main_plot_detailed": plot.main_plot_detailed or {},
            "sub_plots": plot.sub_plots or {},
            "key_turning_points": plot.key_turning_points or []
        }
    
    async def get_chapter_list(self, novel_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取章节列表"""
        import uuid
        try:
            novel_uuid = uuid.UUID(novel_id)
        except ValueError:
            return []
        
        stmt = select(Chapter).where(Chapter.novel_id == novel_uuid).order_by(Chapter.chapter_number).limit(limit)
        result = await self.db.execute(stmt)
        chapters = result.scalars().all()
        
        return [
            {
                "chapter_number": c.chapter_number,
                "volume_number": c.volume_number,
                "title": c.title,
                "word_count": c.word_count,
                "status": c.status if c.status else "draft"
            }
            for c in chapters
        ]
    
    async def get_chapter_content(self, novel_id: str, chapter_number: int) -> Dict[str, Any]:
        """获取章节内容"""
        import uuid
        try:
            novel_uuid = uuid.UUID(novel_id)
        except ValueError:
            return {"error": "无效的小说 ID"}
        
        stmt = select(Chapter).where(
            Chapter.novel_id == novel_uuid,
            Chapter.chapter_number == chapter_number
        )
        result = await self.db.execute(stmt)
        chapter = result.scalar_one_or_none()
        
        if not chapter:
            return {"error": "章节不存在"}
        
        return {
            "chapter_number": chapter.chapter_number,
            "title": chapter.title,
            "content": chapter.content,
            "word_count": chapter.word_count,
            "outline": chapter.outline or {}
        }
