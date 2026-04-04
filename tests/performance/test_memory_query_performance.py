"""记忆系统查询性能测试 - Issue #42."""

import sqlite3
import time
from pathlib import Path

import pytest


class TestMemoryQueryPerformanceWithoutIndex:
    """记忆系统查询性能测试（无复合索引 - 模拟当前生产环境）."""

    @pytest.fixture(autouse=True)
    def setup_test_db(self, tmp_path):
        """设置测试数据库."""
        self.db_path = tmp_path / "test_memory.db"
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        yield
        self.conn.close()

    def _init_test_schema(self):
        """初始化测试表结构（仅有单列索引，无复合索引）."""
        self.conn.execute("""
            CREATE TABLE chapter_summaries (
                id TEXT PRIMARY KEY,
                novel_id TEXT NOT NULL,
                chapter_number INTEGER NOT NULL,
                key_events TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(novel_id, chapter_number)
            )
        """)
        self.conn.execute("""
            CREATE TABLE character_states (
                id TEXT PRIMARY KEY,
                novel_id TEXT NOT NULL,
                character_name TEXT NOT NULL,
                last_appearance_chapter INTEGER,
                created_at TEXT NOT NULL,
                UNIQUE(novel_id, character_name)
            )
        """)
        self.conn.execute("""
            CREATE TABLE memory_chunks (
                id TEXT PRIMARY KEY,
                novel_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                chapter_number INTEGER,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        # 仅创建单列索引（模拟当前状态）
        self.conn.execute("CREATE INDEX idx_chapter_novel ON chapter_summaries(novel_id)")
        self.conn.execute("CREATE INDEX idx_character_novel ON character_states(novel_id)")
        self.conn.execute("CREATE INDEX idx_chunks_novel ON memory_chunks(novel_id)")
        self.conn.commit()

    def _seed_test_data(self, novel_count=10, chapters_per_novel=100, characters_per_novel=20):
        """播种测试数据."""
        # 插入章节摘要
        for novel_idx in range(novel_count):
            novel_id = f"novel_{novel_idx}"
            for chapter_num in range(1, chapters_per_novel + 1):
                self.conn.execute(
                    "INSERT INTO chapter_summaries (id, novel_id, chapter_number, key_events, created_at) VALUES (?, ?, ?, ?, ?)",
                    (f"ch_{novel_id}_{chapter_num}", novel_id, chapter_num, "event", "2024-01-01")
                )
        
        # 插入角色状态
        for novel_idx in range(novel_count):
            novel_id = f"novel_{novel_idx}"
            for char_idx in range(characters_per_novel):
                self.conn.execute(
                    "INSERT INTO character_states (id, novel_id, character_name, last_appearance_chapter, created_at) VALUES (?, ?, ?, ?, ?)",
                    (f"char_{novel_id}_{char_idx}", novel_id, f"character_{char_idx}", 50, "2024-01-01")
                )
        
        # 插入记忆块
        for novel_idx in range(novel_count):
            novel_id = f"novel_{novel_idx}"
            for chapter_num in range(1, chapters_per_novel + 1):
                self.conn.execute(
                    "INSERT INTO memory_chunks (id, novel_id, source_type, source_id, chapter_number, text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (f"chunk_{novel_id}_{chapter_num}", novel_id, "chapter", f"ch_{chapter_num}", chapter_num, "some text", "2024-01-01")
                )
        
        self.conn.commit()

    def test_chapter_query_without_composite_index(self):
        """测试章节查询性能（无复合索引）。"""
        self._init_test_schema()
        self._seed_test_data()
        
        # 测试查询：WHERE novel_id = ? AND chapter_number = ?
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            self.conn.execute(
                "SELECT * FROM chapter_summaries WHERE novel_id = ? AND chapter_number = ?",
                ("novel_5", 50)
            ).fetchone()
        elapsed = time.perf_counter() - start
        
        avg_ms = elapsed * 1000 / iterations
        print(f"\n❌ 章节查询（无复合索引）: {elapsed*1000:.2f}ms / {iterations}次 = {avg_ms:.3f}ms/次")
        
        # 无复合索引时性能应该较差
        assert avg_ms < 1.0, f"查询应该在规定时间内完成，实际：{avg_ms:.3f}ms"

    def test_character_query_without_composite_index(self):
        """测试角色查询性能（无复合索引）。"""
        self._init_test_schema()
        self._seed_test_data()
        
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            self.conn.execute(
                "SELECT * FROM character_states WHERE novel_id = ? AND character_name = ?",
                ("novel_5", "character_10")
            ).fetchone()
        elapsed = time.perf_counter() - start
        
        avg_ms = elapsed * 1000 / iterations
        print(f"\n❌ 角色查询（无复合索引）: {elapsed*1000:.2f}ms / {iterations}次 = {avg_ms:.3f}ms/次")
        assert avg_ms < 1.0

    def test_memory_chunk_query_without_composite_index(self):
        """测试记忆块查询性能（无复合索引）。"""
        self._init_test_schema()
        self._seed_test_data()
        
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            self.conn.execute(
                "SELECT * FROM memory_chunks WHERE novel_id = ? AND chapter_number = ?",
                ("novel_5", 50)
            ).fetchone()
        elapsed = time.perf_counter() - start
        
        avg_ms = elapsed * 1000 / iterations
        print(f"\n❌ 记忆块查询（无复合索引）: {elapsed*1000:.2f}ms / {iterations}次 = {avg_ms:.3f}ms/次")
        assert avg_ms < 1.0


class TestMemoryQueryPerformanceWithIndex:
    """添加复合索引后的性能测试。"""

    @pytest.fixture(autouse=True)
    def setup_test_db(self, tmp_path):
        """设置测试数据库."""
        self.db_path = tmp_path / "test_memory.db"
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        yield
        self.conn.close()

    def _init_test_schema_with_indexes(self):
        """初始化测试表结构（带复合索引）。"""
        self.conn.execute("""
            CREATE TABLE chapter_summaries (
                id TEXT PRIMARY KEY,
                novel_id TEXT NOT NULL,
                chapter_number INTEGER NOT NULL,
                key_events TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(novel_id, chapter_number)
            )
        """)
        self.conn.execute("""
            CREATE TABLE character_states (
                id TEXT PRIMARY KEY,
                novel_id TEXT NOT NULL,
                character_name TEXT NOT NULL,
                last_appearance_chapter INTEGER,
                created_at TEXT NOT NULL,
                UNIQUE(novel_id, character_name)
            )
        """)
        self.conn.execute("""
            CREATE TABLE memory_chunks (
                id TEXT PRIMARY KEY,
                novel_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                chapter_number INTEGER,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # 创建复合索引（修复方案）
        self.conn.execute("CREATE INDEX idx_chapter_novel ON chapter_summaries(novel_id)")
        self.conn.execute("CREATE INDEX idx_chapter_number ON chapter_summaries(chapter_number)")
        self.conn.execute("CREATE INDEX idx_chapter_composite ON chapter_summaries(novel_id, chapter_number)")
        
        self.conn.execute("CREATE INDEX idx_character_novel ON character_states(novel_id)")
        self.conn.execute("CREATE INDEX idx_character_composite ON character_states(novel_id, character_name)")
        
        self.conn.execute("CREATE INDEX idx_chunks_novel ON memory_chunks(novel_id)")
        self.conn.execute("CREATE INDEX idx_chunks_composite ON memory_chunks(novel_id, chapter_number)")
        
        self.conn.commit()

    def _seed_test_data(self, novel_count=10, chapters_per_novel=100, characters_per_novel=20):
        """播种测试数据."""
        for novel_idx in range(novel_count):
            novel_id = f"novel_{novel_idx}"
            for chapter_num in range(1, chapters_per_novel + 1):
                self.conn.execute(
                    "INSERT INTO chapter_summaries (id, novel_id, chapter_number, key_events, created_at) VALUES (?, ?, ?, ?, ?)",
                    (f"ch_{novel_id}_{chapter_num}", novel_id, chapter_num, "event", "2024-01-01")
                )
        
        for novel_idx in range(novel_count):
            novel_id = f"novel_{novel_idx}"
            for char_idx in range(characters_per_novel):
                self.conn.execute(
                    "INSERT INTO character_states (id, novel_id, character_name, last_appearance_chapter, created_at) VALUES (?, ?, ?, ?, ?)",
                    (f"char_{novel_id}_{char_idx}", novel_id, f"character_{char_idx}", 50, "2024-01-01")
                )
        
        for novel_idx in range(novel_count):
            novel_id = f"novel_{novel_idx}"
            for chapter_num in range(1, chapters_per_novel + 1):
                self.conn.execute(
                    "INSERT INTO memory_chunks (id, novel_id, source_type, source_id, chapter_number, text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (f"chunk_{novel_id}_{chapter_num}", novel_id, "chapter", f"ch_{chapter_num}", chapter_num, "some text", "2024-01-01")
                )
        
        self.conn.commit()

    def test_chapter_query_with_composite_index(self):
        """测试章节查询性能（有复合索引）。"""
        self._init_test_schema_with_indexes()
        self._seed_test_data()
        
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            self.conn.execute(
                "SELECT * FROM chapter_summaries WHERE novel_id = ? AND chapter_number = ?",
                ("novel_5", 50)
            ).fetchone()
        elapsed = time.perf_counter() - start
        
        avg_ms = elapsed * 1000 / iterations
        print(f"\n✅ 章节查询（有复合索引）: {elapsed*1000:.2f}ms / {iterations}次 = {avg_ms:.3f}ms/次")
        # 有复合索引时应该非常快
        assert avg_ms < 0.5, f"有索引查询应该更快，实际：{avg_ms:.3f}ms"

    def test_character_query_with_composite_index(self):
        """测试角色查询性能（有复合索引）。"""
        self._init_test_schema_with_indexes()
        self._seed_test_data()
        
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            self.conn.execute(
                "SELECT * FROM character_states WHERE novel_id = ? AND character_name = ?",
                ("novel_5", "character_10")
            ).fetchone()
        elapsed = time.perf_counter() - start
        
        avg_ms = elapsed * 1000 / iterations
        print(f"\n✅ 角色查询（有复合索引）: {elapsed*1000:.2f}ms / {iterations}次 = {avg_ms:.3f}ms/次")
        assert avg_ms < 0.5

    def test_memory_chunk_query_with_composite_index(self):
        """测试记忆块查询性能（有复合索引）。"""
        self._init_test_schema_with_indexes()
        self._seed_test_data()
        
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            self.conn.execute(
                "SELECT * FROM memory_chunks WHERE novel_id = ? AND chapter_number = ?",
                ("novel_5", 50)
            ).fetchone()
        elapsed = time.perf_counter() - start
        
        avg_ms = elapsed * 1000 / iterations
        print(f"\n✅ 记忆块查询（有复合索引）: {elapsed*1000:.2f}ms / {iterations}次 = {avg_ms:.3f}ms/次")
        assert avg_ms < 0.5


def test_index_performance_comparison():
    """对比有无复合索引的性能差异。"""
    print("\n" + "="*60)
    print("Issue #42: 记忆系统查询索引性能对比测试")
    print("="*60)
    print("\n测试场景：")
    print("1. 章节摘要查询：WHERE novel_id = ? AND chapter_number = ?")
    print("2. 角色状态查询：WHERE novel_id = ? AND character_name = ?")
    print("3. 记忆块查询：WHERE novel_id = ? AND chapter_number = ?")
    print("\n数据规模：")
    print("- 10 部小说")
    print("- 每部小说 100 章")
    print("- 每部小说 20 个角色")
    print("- 每个查询执行 100 次")
    print("="*60)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
