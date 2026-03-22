"""
迁移脚本：添加大纲与章节外键关联

Issue: #32 [P1] 大纲与章节关联弱 - 未建立外键关联和同步机制
迁移内容：
1. 在 chapters 表添加 plot_outline_id 外键字段
2. 在 chapters 表添加 outline_version_id 外键字段
3. 为现有数据建立关联（如果可能）
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import settings


async def migrate():
    """执行数据库迁移."""
    # 创建异步引擎
    engine = create_async_engine(settings.database_url, echo=True)
    
    async with engine.connect() as conn:
        print("Starting migration: Add outline-chapter foreign keys...")
        
        # 1. 添加 plot_outline_id 字段
        print("Adding plot_outline_id column to chapters table...")
        await conn.execute(text("""
            ALTER TABLE chapters 
            ADD COLUMN IF NOT EXISTS plot_outline_id UUID
        """))
        await conn.commit()
        print("✓ plot_outline_id column added")
        
        # 2. 添加 outline_version_id 字段
        print("Adding outline_version_id column to chapters table...")
        await conn.execute(text("""
            ALTER TABLE chapters 
            ADD COLUMN IF NOT EXISTS outline_version_id UUID
        """))
        await conn.commit()
        print("✓ outline_version_id column added")
        
        # 3. 添加外键约束
        print("Adding foreign key constraint for plot_outline_id...")
        try:
            await conn.execute(text("""
                ALTER TABLE chapters 
                ADD CONSTRAINT fk_chapters_plot_outline 
                FOREIGN KEY (plot_outline_id) 
                REFERENCES plot_outlines(id) 
                ON DELETE SET NULL
            """))
            await conn.commit()
            print("✓ Foreign key constraint for plot_outline_id added")
        except Exception as e:
            print(f"⚠ Foreign key for plot_outline_id may already exist: {e}")
            await conn.rollback()
        
        print("Adding foreign key constraint for outline_version_id...")
        try:
            await conn.execute(text("""
                ALTER TABLE chapters 
                ADD CONSTRAINT fk_chapters_outline_version 
                FOREIGN KEY (outline_version_id) 
                REFERENCES plot_outline_versions(id) 
                ON DELETE SET NULL
            """))
            await conn.commit()
            print("✓ Foreign key constraint for outline_version_id added")
        except Exception as e:
            print(f"⚠ Foreign key for outline_version_id may already exist: {e}")
            await conn.rollback()
        
        # 4. 为现有数据建立关联（可选）
        print("Linking existing chapters to their outlines...")
        await conn.execute(text("""
            UPDATE chapters
            SET plot_outline_id = (
                SELECT id FROM plot_outlines 
                WHERE plot_outlines.novel_id = chapters.novel_id
                LIMIT 1
            )
            WHERE plot_outline_id IS NULL
        """))
        await conn.commit()
        print("✓ Existing chapters linked to outlines")
        
        # 5. 创建索引（提升查询性能）
        print("Creating indexes...")
        try:
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chapters_plot_outline_id 
                ON chapters(plot_outline_id)
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_chapters_outline_version_id 
                ON chapters(outline_version_id)
            """))
            await conn.commit()
            print("✓ Indexes created")
        except Exception as e:
            print(f"⚠ Index creation issue: {e}")
            await conn.rollback()
        
        print("\n✅ Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(migrate())
