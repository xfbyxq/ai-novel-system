"""Check if novel and world setting exist"""

import asyncio
from core.database import async_session_factory
from core.models.novel import Novel
from core.models.world_setting import WorldSetting

NOVEL_ID = '902c5971-775e-4e76-befb-ea1d7e4d0340'

async def check_novel():
    async with async_session_factory() as session:
        from sqlalchemy import select
        
        # Check if novel exists
        result = await session.execute(
            select(Novel).where(Novel.id == NOVEL_ID)
        )
        novel = result.scalar_one_or_none()
        print(f'Novel exists: {novel is not None}')
        if novel:
            print(f'Novel title: {novel.title}')
            print(f'Novel status: {novel.status}')
        
        # Check if world setting exists
        ws_result = await session.execute(
            select(WorldSetting).where(WorldSetting.novel_id == NOVEL_ID)
        )
        ws = ws_result.scalar_one_or_none()
        print(f'World setting exists: {ws is not None}')

if __name__ == "__main__":
    asyncio.run(check_novel())
