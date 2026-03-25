"""
迁移脚本：添加记忆系统查询复合索引 - Issue #42

问题描述:
  当前记忆系统查询缺少复合索引，导致以下高频查询性能不佳：
  1. chapter_summaries: WHERE novel_id = ? AND chapter_number = ?
  2. character_states: WHERE novel_id = ? AND character_name = ?
  3. memory_chunks: WHERE novel_id = ? AND chapter_number = ?
  4. reflection_entries: WHERE novel_id = ? AND chapter_number = ?
  5. foreshadowing: WHERE novel_id = ? AND status = ? ORDER BY planted_chapter

解决方案:
  添加复合索引以优化查询性能，预计提升 30-50% 的查询速度
"""

import sqlite3
from pathlib import Path


def migrate(db_path: str = "./novel_memory/novel_memory.db"):
    """添加记忆系统查询复合索引."""
    db_path = Path(db_path)
    
    if not db_path.exists():
        print(f"⚠️  数据库不存在：{db_path}")
        print("   将在首次使用时自动创建")
        return True
    
    print(f"📌 连接到数据库：{db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    try:
        # 启用 WAL 模式提升并发性能
        conn.execute("PRAGMA journal_mode=WAL")
        
        # 检查并创建复合索引
        indexes_to_create = [
            # 章节摘要表
            (
                "idx_chapter_composite",
                "chapter_summaries",
                "CREATE INDEX IF NOT EXISTS idx_chapter_composite ON chapter_summaries(novel_id, chapter_number)"
            ),
            
            # 角色状态表
            (
                "idx_character_composite",
                "character_states",
                "CREATE INDEX IF NOT EXISTS idx_character_composite ON character_states(novel_id, character_name)"
            ),
            
            # 记忆块表
            (
                "idx_memory_chunks_composite",
                "memory_chunks",
                "CREATE INDEX IF NOT EXISTS idx_memory_chunks_composite ON memory_chunks(novel_id, chapter_number)"
            ),
            
            # 反思记录表
            (
                "idx_reflection_chapter",
                "reflection_entries",
                "CREATE INDEX IF NOT EXISTS idx_reflection_chapter ON reflection_entries(novel_id, chapter_number)"
            ),
            
            # 伏笔表（三列复合索引）
            (
                "idx_foreshadowing_composite",
                "foreshadowing",
                "CREATE INDEX IF NOT EXISTS idx_foreshadowing_composite ON foreshadowing(novel_id, status, planted_chapter)"
            ),
            
            # 章节模式表
            (
                "idx_patterns_composite",
                "chapter_patterns",
                "CREATE INDEX IF NOT EXISTS idx_patterns_composite ON chapter_patterns(novel_id, status, pattern_type)"
            ),
            
            # 经验规则表
            (
                "idx_lessons_composite",
                "writing_lessons",
                "CREATE INDEX IF NOT EXISTS idx_lessons_composite ON writing_lessons(novel_id, lesson_type, status, priority)"
            ),
        ]
        
        created_count = 0
        skipped_count = 0
        
        for index_name, table_name, create_sql in indexes_to_create:
            # 检查索引是否已存在
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                (index_name,)
            )
            existing = cursor.fetchone()
            
            if existing:
                print(f"⏭️  索引已存在：{index_name}")
                skipped_count += 1
            else:
                print(f"➕ 创建索引：{index_name} ON {table_name}")
                conn.execute(create_sql)
                created_count += 1
        
        conn.commit()
        
        print(f"\n✅ 迁移完成！")
        print(f"   新建索引：{created_count} 个")
        print(f"   跳过索引：{skipped_count} 个")
        
        # 显示索引统计信息
        print("\n📊 索引统计:")
        stats = conn.execute("""
            SELECT name, tbl_name, sql
            FROM sqlite_master
            WHERE type='index' AND sql IS NOT NULL
            ORDER BY tbl_name, name
        """).fetchall()
        
        current_table = None
        for row in stats:
            if row['tbl_name'] != current_table:
                current_table = row['tbl_name']
                print(f"\n  {current_table}:")
            print(f"    - {row['name']}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ 迁移失败：{e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()


def rollback(db_path: str = "./novel_memory/novel_memory.db"):
    """回滚迁移（删除新增的索引）."""
    db_path = Path(db_path)
    
    if not db_path.exists():
        print(f"⚠️  数据库不存在：{db_path}")
        return True
    
    print(f"🔙 回滚迁移：{db_path}")
    conn = sqlite3.connect(str(db_path))
    
    try:
        indexes_to_drop = [
            "idx_chapter_composite",
            "idx_character_composite",
            "idx_memory_chunks_composite",
            "idx_reflection_chapter",
            "idx_foreshadowing_composite",
            "idx_patterns_composite",
            "idx_lessons_composite",
        ]
        
        dropped_count = 0
        
        for index_name in indexes_to_drop:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                (index_name,)
            )
            existing = cursor.fetchone()
            
            if existing:
                print(f"🗑️  删除索引：{index_name}")
                conn.execute(f"DROP INDEX IF EXISTS {index_name}")
                dropped_count += 1
            else:
                print(f"⏭️  索引不存在：{index_name}")
        
        conn.commit()
        
        print(f"\n✅ 回滚完成！删除了 {dropped_count} 个索引")
        return True
        
    except sqlite3.Error as e:
        print(f"❌ 回滚失败：{e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        success = rollback()
    else:
        success = migrate()
    
    sys.exit(0 if success else 1)
