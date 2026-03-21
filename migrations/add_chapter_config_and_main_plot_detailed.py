"""
数据库迁移脚本：添加章节配置和主线剧情详细字段

此脚本为以下表添加新字段：
1. novels 表：添加 chapter_config 字段（JSONB）
2. plot_outlines 表：添加 main_plot_detailed 字段（JSONB）

使用方法：
    python -m migrations.add_chapter_config_and_main_plot_detailed
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import engine, get_db
from sqlalchemy.ext.asyncio import create_async_engine


async def migrate():
    """执行数据库迁移"""
    print("开始数据库迁移...")

    async with engine.begin() as conn:
        # 1. 为 novels 表添加 chapter_config 字段
        print("1. 为 novels 表添加 chapter_config 字段...")
        try:
            await conn.execute(text("""
                ALTER TABLE novels 
                ADD COLUMN IF NOT EXISTS chapter_config JSONB DEFAULT '{"total_chapters": 6, "min_chapters": 3, "max_chapters": 12, "flexible": true}'
            """))
            print("   ✅ novels.chapter_config 添加成功")
        except Exception as e:
            print(f"   ⚠️  novels.chapter_config 可能已存在：{e}")

        # 2. 为 plot_outlines 表添加 main_plot_detailed 字段
        print("2. 为 plot_outlines 表添加 main_plot_detailed 字段...")
        try:
            await conn.execute(text("""
                ALTER TABLE plot_outlines 
                ADD COLUMN IF NOT EXISTS main_plot_detailed JSONB DEFAULT '{}'
            """))
            print("   ✅ plot_outlines.main_plot_detailed 添加成功")
        except Exception as e:
            print(f"   ⚠️  plot_outlines.main_plot_detailed 可能已存在：{e}")

    print("\n✅ 数据库迁移完成！")
    print("\n新增字段说明：")
    print("- novels.chapter_config: 存储章节配置，支持灵活的章节数设置")
    print("- plot_outlines.main_plot_detailed: 存储详细的主线剧情描述")


async def rollback():
    """回滚迁移（仅用于测试）"""
    print("开始回滚数据库迁移...")

    async with engine.begin() as conn:
        # 1. 删除 novels 表的 chapter_config 字段
        print("1. 删除 novels.chapter_config 字段...")
        try:
            await conn.execute(text("""
                ALTER TABLE novels 
                DROP COLUMN IF EXISTS chapter_config
            """))
            print("   ✅ novels.chapter_config 已删除")
        except Exception as e:
            print(f"   ⚠️  删除失败：{e}")

        # 2. 删除 plot_outlines 表的 main_plot_detailed 字段
        print("2. 删除 plot_outlines.main_plot_detailed 字段...")
        try:
            await conn.execute(text("""
                ALTER TABLE plot_outlines 
                DROP COLUMN IF EXISTS main_plot_detailed
            """))
            print("   ✅ plot_outlines.main_plot_detailed 已删除")
        except Exception as e:
            print(f"   ⚠️  删除失败：{e}")

    print("\n⚠️  数据库迁移已回滚！")


async def check_migration_status():
    """检查迁移状态"""
    print("检查数据库迁移状态...")

    async with engine.begin() as conn:
        # 检查 novels.chapter_config
        result = await conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'novels' AND column_name = 'chapter_config'
        """))
        row = result.fetchone()
        if row:
            print(f"✅ novels.chapter_config 存在 (类型：{row[1]})")
        else:
            print("❌ novels.chapter_config 不存在")

        # 检查 plot_outlines.main_plot_detailed
        result = await conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'plot_outlines' AND column_name = 'main_plot_detailed'
        """))
        row = result.fetchone()
        if row:
            print(f"✅ plot_outlines.main_plot_detailed 存在 (类型：{row[1]})")
        else:
            print("❌ plot_outlines.main_plot_detailed 不存在")


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="数据库迁移脚本")
    parser.add_argument(
        "--action",
        choices=["migrate", "rollback", "check"],
        default="migrate",
        help="执行的操作：migrate(迁移), rollback(回滚), check(检查状态)",
    )

    args = parser.parse_args()

    if args.action == "migrate":
        await migrate()
    elif args.action == "rollback":
        confirmation = input("⚠️  确定要回滚迁移吗？此操作不可逆！(yes/no): ")
        if confirmation.lower() == "yes":
            await rollback()
        else:
            print("回滚已取消")
    elif args.action == "check":
        await check_migration_status()


if __name__ == "__main__":
    asyncio.run(main())
