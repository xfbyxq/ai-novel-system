#!/usr/bin/env python
"""
初始化数据库表的脚本
"""

from sqlalchemy import create_engine, inspect
from core.database import Base
from backend.config import settings

def init_db():
    # 创建同步引擎
    sync_url = settings.DATABASE_URL_SYNC
    print(f"Connecting to database: {sync_url}")
    
    sync_engine = create_engine(sync_url)
    
    # 检查现有表
    inspector = inspect(sync_engine)
    existing_tables = inspector.get_table_names()
    print('Existing tables:', existing_tables)
    
    # 导入所有模型以注册到 Base
    from core.models.novel import Novel
    from core.models.world_setting import WorldSetting
    from core.models.character import Character
    from core.models.character_name_version import CharacterNameVersion
    from core.models.plot_outline import PlotOutline
    from core.models.chapter import Chapter
    from core.models.generation_task import GenerationTask
    from core.models.token_usage import TokenUsage
    from core.models.platform_account import PlatformAccount
    from core.models.publish_task import PublishTask
    from core.models.chapter_publish import ChapterPublish
    from core.models.ai_chat_session import AIChatSession
    
    # 创建缺失的表
    print('Creating tables...')
    Base.metadata.create_all(sync_engine)
    print('Tables created successfully.')
    
    # 再次检查
    updated_tables = inspector.get_table_names()
    print('Updated tables:', updated_tables)
    
    # 检查特定表是否已创建
    required_tables = ['novels', 'generation_tasks']
    missing_tables = [table for table in required_tables if table not in updated_tables]
    
    if missing_tables:
        print(f'Warning: Missing tables: {missing_tables}')
    else:
        print('All required tables are present.')

if __name__ == "__main__":
    init_db()