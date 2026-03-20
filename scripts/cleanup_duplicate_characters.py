"""清理数据库中的重复角色数据

功能：
1. 查找所有 (novel_id, lower(name)) 重复的角色记录
2. 每组保留 created_at 最早的记录作为"主记录"
3. 将被删除记录的 relationships 数据合并到主记录
4. 更新 chapters.characters_appeared 中的引用
5. 删除重复记录
6. 输出清理报告

使用方式：
    python scripts/cleanup_duplicate_characters.py           # 预览模式（不修改数据）
    python scripts/cleanup_duplicate_characters.py --apply   # 执行清理
"""

import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path
from uuid import UUID

# 将项目根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.config import settings
from core.database import Base
from core.models.character import Character
from core.models.chapter import Chapter


async def find_duplicates(db: AsyncSession) -> dict[str, list[Character]]:
    """查找所有重复角色，按 (novel_id, lower(name)) 分组。

    Returns:
        字典：key 为 "novel_id::name_lower"，value 为按 created_at 排序的角色列表
    """
    # 查询所有角色，按 novel_id 和 created_at 排序
    stmt = select(Character).order_by(Character.novel_id, Character.created_at)
    result = await db.execute(stmt)
    all_characters = result.scalars().all()

    # 按 (novel_id, lower(name)) 分组
    groups: dict[str, list[Character]] = defaultdict(list)
    for char in all_characters:
        key = f"{char.novel_id}::{char.name.strip().lower()}"
        groups[key].append(char)

    # 只保留有重复的组
    return {k: v for k, v in groups.items() if len(v) > 1}


async def merge_relationships(
    primary: Character, duplicates: list[Character]
) -> bool:
    """将重复角色的 relationships 合并到主记录。

    Returns:
        是否有合并发生
    """
    merged = dict(primary.relationships or {})
    changed = False
    for dup in duplicates:
        if dup.relationships:
            for target_name, rel_type in dup.relationships.items():
                if target_name not in merged:
                    merged[target_name] = rel_type
                    changed = True
    if changed:
        primary.relationships = merged
    return changed


async def update_chapter_references(
    db: AsyncSession,
    novel_id: UUID,
    primary_id: UUID,
    duplicate_ids: list[UUID],
) -> int:
    """更新 chapters.characters_appeared 中对重复角色 ID 的引用。

    Returns:
        更新的章节数量
    """
    stmt = select(Chapter).where(Chapter.novel_id == novel_id)
    result = await db.execute(stmt)
    chapters = result.scalars().all()

    updated_count = 0
    dup_id_strs = {str(did) for did in duplicate_ids}

    for chapter in chapters:
        appeared = chapter.characters_appeared
        if not appeared:
            continue

        # characters_appeared 可能是 UUID 列表或字符串列表
        original_ids = [str(cid) for cid in appeared]
        new_ids = []
        changed = False
        primary_added = False

        for cid_str in original_ids:
            if cid_str in dup_id_strs:
                # 替换为主记录 ID（只添加一次）
                if not primary_added:
                    new_ids.append(primary_id)
                    primary_added = True
                changed = True
            elif str(cid_str) == str(primary_id):
                if not primary_added:
                    new_ids.append(primary_id)
                    primary_added = True
                else:
                    changed = True  # 去除重复的主记录引用
            else:
                new_ids.append(type(appeared[0])(cid_str) if appeared else cid_str)

        if changed:
            chapter.characters_appeared = new_ids
            updated_count += 1

    return updated_count


async def cleanup(apply: bool = False) -> None:
    """执行数据清理。"""
    engine = create_async_engine(
        settings.DATABASE_URL.split("?")[0],
        echo=False,
        connect_args={"ssl": False},
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        # 先检查 characters 表是否存在
        try:
            check_result = await db.execute(text(
                "SELECT EXISTS ("
                "  SELECT FROM information_schema.tables "
                "  WHERE table_schema = 'public' AND table_name = 'characters'"
                ")"
            ))
            table_exists = check_result.scalar()
        except Exception:
            table_exists = False

        if not table_exists:
            print("错误：数据库中 characters 表不存在。")
            print("请先执行数据库迁移：alembic upgrade head")
            await engine.dispose()
            return

        duplicates = await find_duplicates(db)

        if not duplicates:
            print("未发现重复角色数据，数据库状态良好。")
            await engine.dispose()
            return

        # 输出报告
        total_duplicates = sum(len(v) - 1 for v in duplicates.values())
        print(f"\n{'='*60}")
        print(f"角色去重清理报告")
        print(f"{'='*60}")
        print(f"发现 {len(duplicates)} 组重复角色，共 {total_duplicates} 条待删除记录\n")

        for key, chars in duplicates.items():
            novel_id_str, name_lower = key.split("::", 1)
            primary = chars[0]  # created_at 最早的
            dups = chars[1:]
            print(f"  角色名: {primary.name}")
            print(f"  小说ID: {novel_id_str}")
            print(f"  保留记录: id={primary.id}, created_at={primary.created_at}")
            for d in dups:
                print(f"  删除记录: id={d.id}, created_at={d.created_at}")
            print()

        if not apply:
            print(f"{'='*60}")
            print("以上为预览模式，未修改任何数据。")
            print("使用 --apply 参数执行实际清理。")
            print(f"{'='*60}")
            await engine.dispose()
            return

        # 执行清理
        print("开始执行清理...")
        deleted_count = 0
        merged_count = 0
        chapters_updated = 0

        for key, chars in duplicates.items():
            primary = chars[0]
            dups = chars[1:]
            dup_ids = [d.id for d in dups]

            # 合并 relationships
            if await merge_relationships(primary, dups):
                merged_count += 1
                print(f"  已合并角色「{primary.name}」的关系数据")

            # 更新章节引用
            updated = await update_chapter_references(
                db, primary.novel_id, primary.id, dup_ids
            )
            chapters_updated += updated

            # 删除重复记录
            for dup in dups:
                await db.delete(dup)
                deleted_count += 1

        await db.commit()

        print(f"\n{'='*60}")
        print(f"清理完成：")
        print(f"  删除重复角色记录: {deleted_count} 条")
        print(f"  合并关系数据: {merged_count} 组")
        print(f"  更新章节引用: {chapters_updated} 章")
        print(f"{'='*60}")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="清理数据库中的重复角色数据")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="执行实际清理（默认为预览模式）",
    )
    args = parser.parse_args()
    asyncio.run(cleanup(apply=args.apply))


if __name__ == "__main__":
    main()
