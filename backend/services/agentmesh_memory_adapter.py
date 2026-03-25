"""
小说持久化记忆系统.
借鉴 AgentMesh 的设计思想：SQLite + FTS5 全文搜索 + 分层记忆
解决当前内存缓存 30 分钟过期导致的内容不连贯问题
"""

import hashlib
import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NovelMemoryStorage:
    """
    小说记忆持久化存储层.
    借鉴 AgentMesh storage.py 的设计：SQLite + FTS5
    """

    def __init__(self, db_path: str = "./novel_memory/novel_memory.db"):
        """初始化方法."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_lock = threading.Lock()
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """获取线程本地连接（线程安全）."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path), check_same_thread=False, timeout=30.0
            )
            self._local.conn.row_factory = sqlite3.Row
            # 启用 WAL 模式提升并发性能
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_tables(self):
        """初始化数据库表结构."""
        with self._init_lock:
            conn = self._get_connection()

            # 章节摘要表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chapter_summaries (
                    id TEXT PRIMARY KEY,
                    novel_id TEXT NOT NULL,
                    chapter_number INTEGER NOT NULL,
                    key_events TEXT,
                    character_changes TEXT,
                    plot_progress TEXT,
                    foreshadowing TEXT,
                    ending_state TEXT,
                    full_content_hash TEXT,
                    word_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(novel_id, chapter_number)
                )
            """)

            # 角色状态表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS character_states (
                    id TEXT PRIMARY KEY,
                    novel_id TEXT NOT NULL,
                    character_name TEXT NOT NULL,
                    last_appearance_chapter INTEGER,
                    current_location TEXT,
                    cultivation_level TEXT,
                    emotional_state TEXT,
                    relationships TEXT,
                    status TEXT,
                    pending_events TEXT,
                    state_hash TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(novel_id, character_name)
                )
            """)

            # 小说元数据表（长期记忆）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS novel_metadata (
                    id TEXT PRIMARY KEY,
                    novel_id TEXT UNIQUE NOT NULL,
                    title TEXT,
                    genre TEXT,
                    synopsis TEXT,
                    world_setting TEXT,
                    characters TEXT,
                    plot_outline TEXT,
                    metadata_hash TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 伏笔追踪表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS foreshadowing (
                    id TEXT PRIMARY KEY,
                    novel_id TEXT NOT NULL,
                    planted_chapter INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    foreshadowing_type TEXT DEFAULT 'PLOT',
                    importance INTEGER DEFAULT 5,
                    expected_resolve_chapter INTEGER,
                    resolved_chapter INTEGER,
                    related_characters TEXT,
                    notes TEXT,
                    status TEXT DEFAULT 'PENDING',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 记忆块表（用于语义搜索）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_chunks (
                    id TEXT PRIMARY KEY,
                    novel_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    chapter_number INTEGER,
                    text TEXT NOT NULL,
                    text_hash TEXT NOT NULL,
                    token_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)

            # FTS5 全文索引（用于关键词搜索）
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
                    USING fts5(
                        text,
                        novel_id UNINDEXED,
                        source_type UNINDEXED,
                        chapter_number UNINDEXED,
                        content='memory_chunks',
                        content_rowid='rowid'
                    )
                """)
            except sqlite3.OperationalError:
                # FTS5 已存在或不支持，忽略
                pass

            # ── 反思机制表 ──────────────────────────────────────

            # 反思记录表（短期反思输出，每次审查循环一条）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reflection_entries (
                    id TEXT PRIMARY KEY,
                    novel_id TEXT NOT NULL,
                    loop_type TEXT NOT NULL,
                    chapter_number INTEGER NOT NULL,
                    chapter_type TEXT DEFAULT 'normal',
                    total_iterations INTEGER DEFAULT 0,
                    initial_score REAL DEFAULT 0,
                    final_score REAL DEFAULT 0,
                    converged INTEGER DEFAULT 0,
                    score_progression TEXT,
                    dimension_scores_first TEXT,
                    dimension_scores_final TEXT,
                    issue_categories TEXT,
                    recurring_issues TEXT,
                    resolved_issues TEXT,
                    unresolved_issues TEXT,
                    effective_strategies TEXT,
                    stagnation_detected INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)

            # 跨章节模式表（长期反思输出）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chapter_patterns (
                    id TEXT PRIMARY KEY,
                    novel_id TEXT NOT NULL,
                    pattern_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    confidence REAL DEFAULT 0.7,
                    evidence_chapters TEXT,
                    affected_dimension TEXT,
                    occurrence_count INTEGER DEFAULT 1,
                    last_seen_chapter INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 写作经验规则表（长期反思输出，注入到 prompt）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS writing_lessons (
                    id TEXT PRIMARY KEY,
                    novel_id TEXT NOT NULL,
                    lesson_type TEXT NOT NULL,
                    rule_text TEXT NOT NULL,
                    reasoning TEXT,
                    source_pattern_id TEXT,
                    applicable_chapter_types TEXT,
                    priority INTEGER DEFAULT 1,
                    times_applied INTEGER DEFAULT 0,
                    effectiveness_score REAL DEFAULT 0.5,
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 创建索引 - 单列索引
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chapter_novel ON chapter_summaries(novel_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chapter_number ON chapter_summaries(chapter_number)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_character_novel ON character_states(novel_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_foreshadowing_novel ON foreshadowing(novel_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_foreshadowing_status ON foreshadowing(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_novel ON memory_chunks(novel_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_source ON memory_chunks(source_type, source_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reflection_novel ON reflection_entries(novel_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reflection_loop ON reflection_entries(novel_id, loop_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_patterns_novel ON chapter_patterns(novel_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_patterns_status ON chapter_patterns(novel_id, status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_lessons_novel ON writing_lessons(novel_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_lessons_type ON writing_lessons(novel_id, lesson_type, status)"
            )
            
            # 创建复合索引 - 优化高频查询性能 (Issue #42)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chapter_composite ON chapter_summaries(novel_id, chapter_number)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_character_composite ON character_states(novel_id, character_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_chunks_composite ON memory_chunks(novel_id, chapter_number)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reflection_chapter ON reflection_entries(novel_id, chapter_number)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_foreshadowing_composite ON foreshadowing(novel_id, status, planted_chapter)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_patterns_composite ON chapter_patterns(novel_id, status, pattern_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_lessons_composite ON writing_lessons(novel_id, lesson_type, status, priority)"
            )

            conn.commit()
            logger.info(f"Initialized novel memory storage at {self.db_path}")

    def _compute_hash(self, data: Any) -> str:
        """计算数据哈希（SHA256）."""
        if data is None:
            return ""
        try:
            content = json.dumps(data, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(content.encode()).hexdigest()[:16]
        except (TypeError, ValueError):
            return ""

    # ==================== 章节摘要操作 ====================

    def save_chapter_summary(
        self,
        novel_id: str,
        chapter_number: int,
        summary: Dict[str, Any],
        full_content_hash: str = "",
    ) -> str:
        """保存章节摘要."""
        conn = self._get_connection()
        now = datetime.now().isoformat()

        # 检查是否已存在
        existing = conn.execute(
            "SELECT id FROM chapter_summaries WHERE novel_id = ? AND chapter_number = ?",
            (novel_id, chapter_number),
        ).fetchone()

        if existing:
            # 更新
            conn.execute(
                """
                UPDATE chapter_summaries SET
                    key_events = ?,
                    character_changes = ?,
                    plot_progress = ?,
                    foreshadowing = ?,
                    ending_state = ?,
                    full_content_hash = ?,
                    word_count = ?,
                    updated_at = ?
                WHERE novel_id = ? AND chapter_number = ?
            """,
                (
                    json.dumps(summary.get("key_events", []), ensure_ascii=False),
                    summary.get("character_changes", ""),
                    summary.get("plot_progress", ""),
                    json.dumps(summary.get("foreshadowing", []), ensure_ascii=False),
                    summary.get("ending_state", ""),
                    full_content_hash,
                    summary.get("word_count", 0),
                    now,
                    novel_id,
                    chapter_number,
                ),
            )
            record_id = existing["id"]
            logger.debug(
                f"Updated chapter {chapter_number} summary for novel {novel_id}"
            )
        else:
            # 插入
            record_id = str(uuid.uuid4())[:12]
            conn.execute(
                """
                INSERT INTO chapter_summaries
                (id, novel_id, chapter_number, key_events, character_changes,
                 plot_progress, foreshadowing, ending_state, full_content_hash,
                 word_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record_id,
                    novel_id,
                    chapter_number,
                    json.dumps(summary.get("key_events", []), ensure_ascii=False),
                    summary.get("character_changes", ""),
                    summary.get("plot_progress", ""),
                    json.dumps(summary.get("foreshadowing", []), ensure_ascii=False),
                    summary.get("ending_state", ""),
                    full_content_hash,
                    summary.get("word_count", 0),
                    now,
                    now,
                ),
            )
            logger.debug(
                f"Saved new chapter {chapter_number} summary for novel {novel_id}"
            )

        conn.commit()

        # 同步更新 FTS 索引
        self._update_memory_chunk(
            novel_id=novel_id,
            source_type="chapter_summary",
            source_id=record_id,
            chapter_number=chapter_number,
            text=self._format_summary_for_search(summary, chapter_number),
        )

        return record_id

    def get_chapter_summary(
        self, novel_id: str, chapter_number: int
    ) -> Optional[Dict[str, Any]]:
        """获取单个章节摘要."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM chapter_summaries WHERE novel_id = ? AND chapter_number = ?",
            (novel_id, chapter_number),
        ).fetchone()

        if row:
            return self._row_to_summary_dict(row)
        return None

    def get_chapter_summaries(
        self,
        novel_id: str,
        start_chapter: int = 1,
        end_chapter: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取章节摘要列表."""
        conn = self._get_connection()

        if end_chapter:
            query = """
                SELECT * FROM chapter_summaries
                WHERE novel_id = ? AND chapter_number >= ? AND chapter_number <= ?
                ORDER BY chapter_number DESC
                LIMIT ?
            """
            rows = conn.execute(
                query, (novel_id, start_chapter, end_chapter, limit)
            ).fetchall()
        else:
            query = """
                SELECT * FROM chapter_summaries
                WHERE novel_id = ? AND chapter_number >= ?
                ORDER BY chapter_number DESC
                LIMIT ?
            """
            rows = conn.execute(query, (novel_id, start_chapter, limit)).fetchall()

        return [self._row_to_summary_dict(row) for row in rows]

    def get_recent_chapter_summaries(
        self, novel_id: str, current_chapter: int, count: int = 5
    ) -> List[Dict[str, Any]]:
        """获取最近 N 章摘要（用于上下文构建）."""
        conn = self._get_connection()
        query = """
            SELECT * FROM chapter_summaries
            WHERE novel_id = ? AND chapter_number < ?
            ORDER BY chapter_number DESC
            LIMIT ?
        """
        rows = conn.execute(query, (novel_id, current_chapter, count)).fetchall()
        # 返回按章节号升序排列
        return sorted(
            [self._row_to_summary_dict(row) for row in rows],
            key=lambda x: x["chapter_number"],
        )

    def _row_to_summary_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """将数据库行转换为摘要字典."""
        return {
            "id": row["id"],
            "novel_id": row["novel_id"],
            "chapter_number": row["chapter_number"],
            "key_events": json.loads(row["key_events"]) if row["key_events"] else [],
            "character_changes": row["character_changes"] or "",
            "plot_progress": row["plot_progress"] or "",
            "foreshadowing": (
                json.loads(row["foreshadowing"]) if row["foreshadowing"] else []
            ),
            "ending_state": row["ending_state"] or "",
            "word_count": row["word_count"] or 0,
            "full_content_hash": row["full_content_hash"] or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _format_summary_for_search(
        self, summary: Dict[str, Any], chapter_number: int
    ) -> str:
        """格式化摘要用于全文搜索."""
        parts = [f"第{chapter_number}章"]

        if summary.get("key_events"):
            events = summary["key_events"]
            if isinstance(events, list):
                parts.append("主要事件：" + "；".join(events))
            else:
                parts.append(f"主要事件：{events}")

        if summary.get("character_changes"):
            parts.append(f"角色变化：{summary['character_changes']}")

        if summary.get("plot_progress"):
            parts.append(f"情节：{summary['plot_progress']}")

        if summary.get("foreshadowing"):
            foreshadowing = summary["foreshadowing"]
            if isinstance(foreshadowing, list):
                parts.append("伏笔：" + "；".join(foreshadowing))
            else:
                parts.append(f"伏笔：{foreshadowing}")

        return "\n".join(parts)

    # ==================== 角色状态操作 ====================

    def save_character_state(
        self, novel_id: str, character_name: str, state: Dict[str, Any]
    ) -> str:
        """保存角色状态."""
        conn = self._get_connection()
        now = datetime.now().isoformat()
        state_hash = self._compute_hash(state)

        # 检查是否已存在
        existing = conn.execute(
            "SELECT id, state_hash FROM character_states WHERE novel_id = ? AND character_name = ?",
            (novel_id, character_name),
        ).fetchone()

        if existing:
            # 检查是否有变化
            if existing["state_hash"] == state_hash:
                logger.debug(
                    f"Character {character_name} state unchanged, skipping update"
                )
                return existing["id"]

            # 更新
            conn.execute(
                """
                UPDATE character_states SET
                    last_appearance_chapter = ?,
                    current_location = ?,
                    cultivation_level = ?,
                    emotional_state = ?,
                    relationships = ?,
                    status = ?,
                    pending_events = ?,
                    state_hash = ?,
                    updated_at = ?
                WHERE novel_id = ? AND character_name = ?
            """,
                (
                    state.get("last_appearance_chapter"),
                    state.get("current_location", ""),
                    state.get("cultivation_level", ""),
                    state.get("emotional_state", ""),
                    json.dumps(state.get("relationships", {}), ensure_ascii=False),
                    state.get("status", "active"),
                    json.dumps(state.get("pending_events", []), ensure_ascii=False),
                    state_hash,
                    now,
                    novel_id,
                    character_name,
                ),
            )
            record_id = existing["id"]
            logger.debug(
                f"Updated character {character_name} state for novel {novel_id}"
            )
        else:
            # 插入
            record_id = str(uuid.uuid4())[:12]
            conn.execute(
                """
                INSERT INTO character_states
                (id, novel_id, character_name, last_appearance_chapter, current_location,
                 cultivation_level, emotional_state, relationships, status, pending_events,
                 state_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record_id,
                    novel_id,
                    character_name,
                    state.get("last_appearance_chapter"),
                    state.get("current_location", ""),
                    state.get("cultivation_level", ""),
                    state.get("emotional_state", ""),
                    json.dumps(state.get("relationships", {}), ensure_ascii=False),
                    state.get("status", "active"),
                    json.dumps(state.get("pending_events", []), ensure_ascii=False),
                    state_hash,
                    now,
                    now,
                ),
            )
            logger.debug(
                f"Saved new character {character_name} state for novel {novel_id}"
            )

        conn.commit()
        return record_id

    def get_character_state(
        self, novel_id: str, character_name: str
    ) -> Optional[Dict[str, Any]]:
        """获取单个角色状态."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM character_states WHERE novel_id = ? AND character_name = ?",
            (novel_id, character_name),
        ).fetchone()

        if row:
            return self._row_to_character_dict(row)
        return None

    def get_all_character_states(self, novel_id: str) -> Dict[str, Dict[str, Any]]:
        """获取所有角色状态."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT * FROM character_states WHERE novel_id = ?", (novel_id,)
        ).fetchall()

        return {row["character_name"]: self._row_to_character_dict(row) for row in rows}

    def _row_to_character_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """将数据库行转换为角色状态字典."""
        return {
            "id": row["id"],
            "novel_id": row["novel_id"],
            "character_name": row["character_name"],
            "last_appearance_chapter": row["last_appearance_chapter"],
            "current_location": row["current_location"] or "",
            "cultivation_level": row["cultivation_level"] or "",
            "emotional_state": row["emotional_state"] or "",
            "relationships": (
                json.loads(row["relationships"]) if row["relationships"] else {}
            ),
            "status": row["status"] or "active",
            "pending_events": (
                json.loads(row["pending_events"]) if row["pending_events"] else []
            ),
            "updated_at": row["updated_at"],
        }

    # ==================== 小说元数据操作（长期记忆） ====================

    def save_novel_metadata(self, novel_id: str, metadata: Dict[str, Any]) -> str:
        """保存小说元数据（长期记忆）."""
        conn = self._get_connection()
        now = datetime.now().isoformat()
        metadata_hash = self._compute_hash(metadata)

        # 检查是否已存在
        existing = conn.execute(
            "SELECT id, metadata_hash FROM novel_metadata WHERE novel_id = ?",
            (novel_id,),
        ).fetchone()

        if existing:
            if existing["metadata_hash"] == metadata_hash:
                logger.debug(f"Novel {novel_id} metadata unchanged, skipping update")
                return existing["id"]

            conn.execute(
                """
                UPDATE novel_metadata SET
                    title = ?,
                    genre = ?,
                    synopsis = ?,
                    world_setting = ?,
                    characters = ?,
                    plot_outline = ?,
                    metadata_hash = ?,
                    updated_at = ?
                WHERE novel_id = ?
            """,
                (
                    metadata.get("title", ""),
                    metadata.get("genre", ""),
                    metadata.get("synopsis", ""),
                    json.dumps(metadata.get("world_setting", {}), ensure_ascii=False),
                    json.dumps(metadata.get("characters", []), ensure_ascii=False),
                    json.dumps(metadata.get("plot_outline", {}), ensure_ascii=False),
                    metadata_hash,
                    now,
                    novel_id,
                ),
            )
            record_id = existing["id"]
            logger.info(f"Updated novel {novel_id} metadata")
        else:
            record_id = str(uuid.uuid4())[:12]
            conn.execute(
                """
                INSERT INTO novel_metadata
                (id, novel_id, title, genre, synopsis, world_setting, characters,
                 plot_outline, metadata_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record_id,
                    novel_id,
                    metadata.get("title", ""),
                    metadata.get("genre", ""),
                    metadata.get("synopsis", ""),
                    json.dumps(metadata.get("world_setting", {}), ensure_ascii=False),
                    json.dumps(metadata.get("characters", []), ensure_ascii=False),
                    json.dumps(metadata.get("plot_outline", {}), ensure_ascii=False),
                    metadata_hash,
                    now,
                    now,
                ),
            )
            logger.info(f"Saved new novel {novel_id} metadata")

        conn.commit()
        return record_id

    def get_novel_metadata(self, novel_id: str) -> Optional[Dict[str, Any]]:
        """获取小说元数据."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM novel_metadata WHERE novel_id = ?", (novel_id,)
        ).fetchone()

        if row:
            return {
                "id": row["id"],
                "novel_id": row["novel_id"],
                "title": row["title"] or "",
                "genre": row["genre"] or "",
                "synopsis": row["synopsis"] or "",
                "world_setting": (
                    json.loads(row["world_setting"]) if row["world_setting"] else {}
                ),
                "characters": (
                    json.loads(row["characters"]) if row["characters"] else []
                ),
                "plot_outline": (
                    json.loads(row["plot_outline"]) if row["plot_outline"] else {}
                ),
                "updated_at": row["updated_at"],
            }
        return None

    # ==================== 记忆块与搜索操作 ====================

    def _update_memory_chunk(
        self,
        novel_id: str,
        source_type: str,
        source_id: str,
        chapter_number: Optional[int],
        text: str,
    ):
        """更新记忆块（用于全文搜索）."""
        conn = self._get_connection()
        now = datetime.now().isoformat()
        text_hash = self._compute_hash(text)

        # 删除旧记录
        conn.execute(
            "DELETE FROM memory_chunks WHERE source_type = ? AND source_id = ?",
            (source_type, source_id),
        )

        # 插入新记录
        chunk_id = str(uuid.uuid4())[:12]
        conn.execute(
            """
            INSERT INTO memory_chunks
            (id, novel_id, source_type, source_id, chapter_number, text, text_hash,
             token_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                chunk_id,
                novel_id,
                source_type,
                source_id,
                chapter_number,
                text,
                text_hash,
                len(text) // 4,  # 粗略估算 token 数
                now,
            ),
        )

        # 更新 FTS 索引（使用 content= 外部内容模式）
        try:
            # 获取新插入记录的 rowid
            cursor = conn.execute(
                "SELECT rowid FROM memory_chunks WHERE id = ?", (chunk_id,)
            )
            row = cursor.fetchone()
            if row:
                new_rowid = row[0]
                # 直接插入新 FTS 记录
                conn.execute(
                    """
                    INSERT INTO memory_fts(rowid, text, novel_id, source_type, chapter_number)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (new_rowid, text, novel_id, source_type, chapter_number),
                )
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logger.warning(f"FTS update failed (will use LIKE fallback): {e}")

        conn.commit()

    def search_memories(
        self,
        novel_id: str,
        query: str,
        source_types: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        搜索相关记忆.
        使用 FTS5 全文搜索
        """
        conn = self._get_connection()

        try:
            # 构建 FTS5 查询
            # 将查询分词并用 OR 连接
            terms = query.replace("，", " ").replace("。", " ").split()
            fts_query = " OR ".join(f'"{term}"' for term in terms if term.strip())

            if source_types:
                placeholders = ",".join("?" * len(source_types))
                query_sql = f"""
                    SELECT m.*, bm25(memory_fts) as rank
                    FROM memory_fts f
                    JOIN memory_chunks m ON f.rowid = m.rowid
                    WHERE memory_fts MATCH ?
                      AND m.novel_id = ?
                      AND m.source_type IN ({placeholders})
                    ORDER BY rank
                    LIMIT ?
                """
                params = [fts_query, novel_id] + source_types + [limit]
            else:
                query_sql = """
                    SELECT m.*, bm25(memory_fts) as rank
                    FROM memory_fts f
                    JOIN memory_chunks m ON f.rowid = m.rowid
                    WHERE memory_fts MATCH ? AND m.novel_id = ?
                    ORDER BY rank
                    LIMIT ?
                """
                params = [fts_query, novel_id, limit]

            rows = conn.execute(query_sql, params).fetchall()

            return [
                {
                    "id": row["id"],
                    "source_type": row["source_type"],
                    "source_id": row["source_id"],
                    "chapter_number": row["chapter_number"],
                    "text": row["text"],
                    "rank": row["rank"],
                }
                for row in rows
            ]
        except sqlite3.OperationalError as e:
            logger.warning(f"FTS search failed, falling back to LIKE: {e}")
            # 回退到 LIKE 搜索
            return self._search_memories_like(novel_id, query, source_types, limit)

    def _search_memories_like(
        self,
        novel_id: str,
        query: str,
        source_types: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """LIKE 搜索回退."""
        conn = self._get_connection()

        # 分词搜索
        terms = query.replace("，", " ").replace("。", " ").split()
        conditions = []
        params = [novel_id]

        for term in terms:
            if term.strip():
                conditions.append("text LIKE ?")
                params.append(f"%{term.strip()}%")

        if not conditions:
            return []

        where_clause = " OR ".join(conditions)

        if source_types:
            placeholders = ",".join("?" * len(source_types))
            query_sql = f"""
                SELECT * FROM memory_chunks
                WHERE novel_id = ? AND ({where_clause})
                  AND source_type IN ({placeholders})
                ORDER BY chapter_number DESC
                LIMIT ?
            """
            params.extend(source_types)
        else:
            query_sql = f"""
                SELECT * FROM memory_chunks
                WHERE novel_id = ? AND ({where_clause})
                ORDER BY chapter_number DESC
                LIMIT ?
            """

        params.append(limit)
        rows = conn.execute(query_sql, params).fetchall()

        return [
            {
                "id": row["id"],
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "chapter_number": row["chapter_number"],
                "text": row["text"],
                "rank": 0,
            }
            for row in rows
        ]

    # ==================== 伏笔查询 ====================

    def get_foreshadowing(
        self, novel_id: str, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """查询伏笔列表.

        Args:
            novel_id: 小说ID
            status: 可选状态过滤（'PENDING', 'RESOLVED', 'planted' 等）

        Returns:
            伏笔字典列表
        """
        conn = self._get_connection()

        # 兼容 ai_chat_service 传入的 'planted' 映射到 'PENDING'
        status_map = {
            "planted": "PENDING",
            "resolved": "RESOLVED",
            "abandoned": "ABANDONED",
        }
        db_status = status_map.get(status, status) if status else None

        if db_status:
            rows = conn.execute(
                "SELECT * FROM foreshadowing WHERE novel_id = ? AND status = ? ORDER BY planted_chapter DESC",
                (novel_id, db_status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM foreshadowing WHERE novel_id = ? ORDER BY planted_chapter DESC",
                (novel_id,),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "novel_id": row["novel_id"],
                "planted_chapter": row["planted_chapter"],
                "description": row["content"],
                "content": row["content"],
                "foreshadowing_type": row["foreshadowing_type"],
                "importance": row["importance"],
                "expected_resolve_chapter": row["expected_resolve_chapter"],
                "resolved_chapter": row["resolved_chapter"],
                "related_characters": row["related_characters"],
                "notes": row["notes"],
                "status": row["status"],
            }
            for row in rows
        ]

    # ==================== 时间线查询 ====================

    def get_timeline_events(
        self, novel_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """从章节摘要中提取关键事件作为时间线.

        由于没有独立的 timeline 表，直接从 chapter_summaries
        中提取每章的 key_events 作为时间线事件。

        Args:
            novel_id: 小说ID
            limit: 返回最近 N 章的事件

        Returns:
            时间线事件列表
        """
        conn = self._get_connection()

        rows = conn.execute(
            """SELECT chapter_number, key_events, plot_progress
               FROM chapter_summaries
               WHERE novel_id = ?
               ORDER BY chapter_number DESC
               LIMIT ?""",
            (novel_id, limit),
        ).fetchall()

        events = []
        for row in rows:
            chapter_number = row["chapter_number"]
            # 优先使用 key_events
            key_events_raw = row["key_events"]
            if key_events_raw:
                try:
                    key_events = json.loads(key_events_raw)
                    if isinstance(key_events, list):
                        for evt in key_events[:2]:  # 每章最多取 2 个事件
                            desc = evt if isinstance(evt, str) else str(evt)
                            events.append(
                                {
                                    "chapter_number": chapter_number,
                                    "description": desc,
                                }
                            )
                        continue
                except (json.JSONDecodeError, TypeError):
                    pass

            # 回退到 plot_progress
            plot_progress = row["plot_progress"]
            if plot_progress:
                events.append(
                    {
                        "chapter_number": chapter_number,
                        "description": plot_progress[:80],
                    }
                )

        # 按章节正序返回
        events.sort(key=lambda x: x["chapter_number"])
        return events

    # ==================== 工具方法 ====================

    def get_statistics(self, novel_id: str) -> Dict[str, Any]:
        """获取小说记忆统计."""
        conn = self._get_connection()

        chapter_count = conn.execute(
            "SELECT COUNT(*) FROM chapter_summaries WHERE novel_id = ?", (novel_id,)
        ).fetchone()[0]

        character_count = conn.execute(
            "SELECT COUNT(*) FROM character_states WHERE novel_id = ?", (novel_id,)
        ).fetchone()[0]

        foreshadowing_stats = conn.execute(
            """
            SELECT status, COUNT(*) as count
            FROM foreshadowing WHERE novel_id = ?
            GROUP BY status
        """,
            (novel_id,),
        ).fetchall()

        chunk_count = conn.execute(
            "SELECT COUNT(*) FROM memory_chunks WHERE novel_id = ?", (novel_id,)
        ).fetchone()[0]

        return {
            "novel_id": novel_id,
            "chapter_count": chapter_count,
            "character_count": character_count,
            "foreshadowing": {
                row["status"]: row["count"] for row in foreshadowing_stats
            },
            "memory_chunk_count": chunk_count,
        }

    # ==================== 反思记录操作 ====================

    def save_reflection_entry(self, novel_id: str, entry: Dict[str, Any]) -> str:
        """保存一条短期反思记录."""
        conn = self._get_connection()
        record_id = str(uuid.uuid4())[:12]
        now = entry.get("created_at", datetime.now().isoformat())

        conn.execute(
            """
            INSERT INTO reflection_entries
            (id, novel_id, loop_type, chapter_number, chapter_type,
             total_iterations, initial_score, final_score, converged,
             score_progression, dimension_scores_first, dimension_scores_final,
             issue_categories, recurring_issues, resolved_issues,
             unresolved_issues, effective_strategies, stagnation_detected, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                record_id,
                novel_id,
                entry.get("loop_type", "chapter"),
                entry.get("chapter_number", 0),
                entry.get("chapter_type", "normal"),
                entry.get("total_iterations", 0),
                entry.get("initial_score", 0),
                entry.get("final_score", 0),
                1 if entry.get("converged", False) else 0,
                json.dumps(entry.get("score_progression", []), ensure_ascii=False),
                json.dumps(entry.get("dimension_scores_first", {}), ensure_ascii=False),
                json.dumps(entry.get("dimension_scores_final", {}), ensure_ascii=False),
                json.dumps(entry.get("issue_categories", []), ensure_ascii=False),
                json.dumps(entry.get("recurring_issues", []), ensure_ascii=False),
                json.dumps(entry.get("resolved_issues", []), ensure_ascii=False),
                json.dumps(entry.get("unresolved_issues", []), ensure_ascii=False),
                json.dumps(entry.get("effective_strategies", []), ensure_ascii=False),
                1 if entry.get("stagnation_detected", False) else 0,
                now,
            ),
        )
        conn.commit()
        logger.debug(
            f"Saved reflection entry for novel {novel_id}, chapter {entry.get('chapter_number')}"
        )
        return record_id

    def get_reflection_entries(
        self,
        novel_id: str,
        loop_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取反思记录列表."""
        conn = self._get_connection()

        if loop_type:
            rows = conn.execute(
                """SELECT * FROM reflection_entries.
                   WHERE novel_id = ? AND loop_type = ?
                   ORDER BY chapter_number ASC LIMIT ?""",
                (novel_id, loop_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM reflection_entries.
                   WHERE novel_id = ?
                   ORDER BY chapter_number ASC LIMIT ?""",
                (novel_id, limit),
            ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            # 反序列化 JSON 字段
            for field_name in (
                "score_progression",
                "dimension_scores_first",
                "dimension_scores_final",
                "issue_categories",
                "recurring_issues",
                "resolved_issues",
                "unresolved_issues",
                "effective_strategies",
            ):
                val = d.get(field_name)
                if isinstance(val, str):
                    try:
                        d[field_name] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
            d["converged"] = bool(d.get("converged", 0))
            d["stagnation_detected"] = bool(d.get("stagnation_detected", 0))
            results.append(d)
        return results

    # ==================== 模式 (Pattern) 操作 ====================

    def save_pattern(self, novel_id: str, pattern: Dict[str, Any]) -> str:
        """保存一条跨章节模式."""
        conn = self._get_connection()
        record_id = str(uuid.uuid4())[:12]
        now = pattern.get("created_at", datetime.now().isoformat())

        conn.execute(
            """
            INSERT INTO chapter_patterns
            (id, novel_id, pattern_type, description, confidence,
             evidence_chapters, affected_dimension, occurrence_count,
             last_seen_chapter, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                record_id,
                novel_id,
                pattern.get("pattern_type", "weakness"),
                pattern.get("description", ""),
                pattern.get("confidence", 0.7),
                pattern.get("evidence_chapters", "[]"),
                pattern.get("affected_dimension", ""),
                pattern.get("occurrence_count", 1),
                pattern.get("last_seen_chapter", 0),
                pattern.get("status", "active"),
                now,
                pattern.get("updated_at", now),
            ),
        )
        conn.commit()
        logger.debug(
            f"Saved pattern for novel {novel_id}: {pattern.get('description', '')[:30]}"
        )
        return record_id

    def get_active_patterns(
        self, novel_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取活跃的模式列表."""
        conn = self._get_connection()
        rows = conn.execute(
            """SELECT * FROM chapter_patterns.
               WHERE novel_id = ? AND status = 'active'
               ORDER BY confidence DESC, occurrence_count DESC
               LIMIT ?""",
            (novel_id, limit),
        ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            val = d.get("evidence_chapters")
            if isinstance(val, str):
                try:
                    d["evidence_chapters"] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(d)
        return results

    # ==================== 经验规则 (Lesson) 操作 ====================

    def save_lesson(self, novel_id: str, lesson: Dict[str, Any]) -> str:
        """保存一条写作经验规则."""
        conn = self._get_connection()
        record_id = str(uuid.uuid4())[:12]
        now = lesson.get("created_at", datetime.now().isoformat())

        conn.execute(
            """
            INSERT INTO writing_lessons
            (id, novel_id, lesson_type, rule_text, reasoning, source_pattern_id,
             applicable_chapter_types, priority, times_applied,
             effectiveness_score, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                record_id,
                novel_id,
                lesson.get("lesson_type", "writer"),
                lesson.get("rule_text", ""),
                lesson.get("reasoning", ""),
                lesson.get("source_pattern_id"),
                lesson.get("applicable_chapter_types", '["normal"]'),
                lesson.get("priority", 1),
                lesson.get("times_applied", 0),
                lesson.get("effectiveness_score", 0.5),
                lesson.get("status", "active"),
                now,
                lesson.get("updated_at", now),
            ),
        )
        conn.commit()
        logger.debug(
            f"Saved lesson for novel {novel_id}: {lesson.get('rule_text', '')[:30]}"
        )
        return record_id

    def get_applicable_lessons(
        self,
        novel_id: str,
        lesson_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """获取适用的经验规则列表."""
        conn = self._get_connection()

        if lesson_type:
            rows = conn.execute(
                """SELECT * FROM writing_lessons.
                   WHERE novel_id = ? AND lesson_type = ? AND status = 'active'
                   ORDER BY priority DESC, effectiveness_score DESC
                   LIMIT ?""",
                (novel_id, lesson_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM writing_lessons.
                   WHERE novel_id = ? AND status = 'active'
                   ORDER BY priority DESC, effectiveness_score DESC
                   LIMIT ?""",
                (novel_id, limit),
            ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            val = d.get("applicable_chapter_types")
            if isinstance(val, str):
                try:
                    d["applicable_chapter_types"] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(d)
        return results

    def update_lesson_effectiveness(
        self,
        novel_id: str,
        lesson_id: str,
        times_applied: Optional[int] = None,
        effectiveness_score: Optional[float] = None,
        status: Optional[str] = None,
    ) -> None:
        """更新经验规则的效果追踪数据."""
        conn = self._get_connection()
        now = datetime.now().isoformat()

        updates = []
        params = []

        if times_applied is not None:
            updates.append("times_applied = ?")
            params.append(times_applied)
        if effectiveness_score is not None:
            updates.append("effectiveness_score = ?")
            params.append(effectiveness_score)
        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if not updates:
            return

        updates.append("updated_at = ?")
        params.append(now)
        params.extend([novel_id, lesson_id])

        conn.execute(
            f"UPDATE writing_lessons SET {', '.join(updates)} WHERE novel_id = ? AND id = ?",
            params,
        )
        conn.commit()

    def close(self):
        """关闭数据库连接."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


class NovelMemoryAdapter:
    """
    小说记忆适配器.
    提供高层 API，集成持久化存储与现有系统
    借鉴 AgentMesh MemoryManager 的设计
    """

    def __init__(self, workspace_root: str = "./novel_memory"):
        """初始化方法."""
        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)

        db_path = self.workspace_root / "novel_memory.db"
        self.storage = NovelMemoryStorage(str(db_path))

        logger.info(f"NovelMemoryAdapter initialized at {workspace_root}")

    # ==================== 章节记忆操作 ====================

    async def save_chapter_memory(
        self, novel_id: str, chapter_number: int, content: str, summary: Dict[str, Any]
    ) -> str:
        """
        保存章节记忆.
        包括章节摘要和全文索引
        """
        # 计算全文哈希
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        # 添加字数统计
        summary["word_count"] = len(content)

        # 保存摘要
        record_id = self.storage.save_chapter_summary(
            novel_id=novel_id,
            chapter_number=chapter_number,
            summary=summary,
            full_content_hash=content_hash,
        )

        logger.info(f"Saved chapter {chapter_number} memory for novel {novel_id}")
        return record_id

    async def get_chapter_context(
        self, novel_id: str, chapter_number: int, context_chapters: int = 5
    ) -> str:
        """
        获取章节生成所需的上下文.
        包括最近 N 章摘要、角色状态、待回收伏笔
        """
        parts = []

        # 1. 获取最近章节摘要
        recent_summaries = self.storage.get_recent_chapter_summaries(
            novel_id, chapter_number, context_chapters
        )

        if recent_summaries:
            parts.append("## 前文摘要")
            for summary in recent_summaries:
                chapter_text = f"\n### 第{summary['chapter_number']}章"
                if summary["key_events"]:
                    chapter_text += f"\n- 主要事件：{'；'.join(summary['key_events'])}"
                if summary["character_changes"]:
                    chapter_text += f"\n- 角色变化：{summary['character_changes']}"
                if summary["plot_progress"]:
                    chapter_text += f"\n- 情节：{summary['plot_progress'][:300]}"
                parts.append(chapter_text)

        # 2. 获取角色状态
        character_states = self.storage.get_all_character_states(novel_id)
        if character_states:
            parts.append("\n## 角色当前状态")
            for name, state in character_states.items():
                state_text = f"\n### {name}"
                if state.get("current_location"):
                    state_text += f"\n- 位置：{state['current_location']}"
                if state.get("cultivation_level"):
                    state_text += f"\n- 境界：{state['cultivation_level']}"
                if state.get("emotional_state"):
                    state_text += f"\n- 情绪：{state['emotional_state']}"
                if state.get("status") and state["status"] != "active":
                    state_text += f"\n- 状态：{state['status']}"
                if state.get("pending_events"):
                    state_text += (
                        f"\n- 待处理事件：{'；'.join(state['pending_events'])}"
                    )
                parts.append(state_text)

        return "\n".join(parts) if parts else ""

    # ==================== 小说元数据操作（长期记忆） ====================

    async def initialize_novel_memory(self, novel_id: str, novel_data: Dict[str, Any]):
        """
        初始化小说长期记忆.
        在企划完成后调用，保存世界观、角色、大纲等核心设定
        """
        metadata = {
            "title": novel_data.get("title", ""),
            "genre": novel_data.get("genre", ""),
            "synopsis": novel_data.get("synopsis", ""),
            "world_setting": novel_data.get("world_setting", {}),
            "characters": novel_data.get("characters", []),
            "plot_outline": novel_data.get("plot_outline", {}),
        }

        self.storage.save_novel_metadata(novel_id, metadata)

        # 初始化角色状态
        for char in novel_data.get("characters", []):
            # 兼容字符串和字典两种格式
            if isinstance(char, str):
                char_name = char
                char_data = {}
            elif isinstance(char, dict):
                char_name = char.get("name", "")
                char_data = char
            else:
                continue

            if char_name:
                self.storage.save_character_state(
                    novel_id=novel_id,
                    character_name=char_name,
                    state={
                        "last_appearance_chapter": 0,
                        "current_location": char_data.get("initial_location", ""),
                        "cultivation_level": char_data.get("cultivation_level", ""),
                        "emotional_state": "平静",
                        "relationships": char_data.get("relationships", {}),
                        "status": "active",
                        "pending_events": [],
                    },
                )

        logger.info(f"Initialized novel {novel_id} long-term memory")

    async def load_novel_bootstrap(self, novel_id: str) -> str:
        """
        加载小说的长期记忆（Bootstrap）
        用于系统提示词中提供背景知识
        """
        metadata = self.storage.get_novel_metadata(novel_id)
        if not metadata:
            return ""

        parts = []

        # 标题和类型
        if metadata.get("title"):
            parts.append(f"# {metadata['title']}")
        if metadata.get("genre"):
            parts.append(f"类型：{metadata['genre']}")

        # 世界观
        world_setting = metadata.get("world_setting", {})
        if world_setting:
            parts.append("\n## 世界观")
            if isinstance(world_setting, dict):
                if world_setting.get("name"):
                    parts.append(f"世界名称：{world_setting['name']}")
                if world_setting.get("description"):
                    parts.append(f"描述：{world_setting['description']}")
                if world_setting.get("cultivation_system"):
                    parts.append(f"修炼体系：{world_setting['cultivation_system']}")
            else:
                parts.append(str(world_setting))

        # 主要角色
        characters = metadata.get("characters", [])
        if characters:
            parts.append("\n## 主要角色")
            for char in characters[:10]:  # 限制数量
                if isinstance(char, dict):
                    char_text = f"- {char.get('name', '未知')}"
                    if char.get("role"):
                        char_text += f"（{char['role']}）"
                    if char.get("description"):
                        char_text += f"：{char['description'][:100]}"
                    parts.append(char_text)
                else:
                    parts.append(f"- {char}")

        return "\n".join(parts)

    # ==================== 搜索操作 ====================

    async def search_relevant_context(
        self, novel_id: str, query: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        搜索相关上下文.
        使用 FTS5 全文搜索
        """
        return self.storage.search_memories(
            novel_id=novel_id, query=query, limit=max_results
        )

    # ==================== 角色状态操作 ====================

    async def update_character_state(
        self,
        novel_id: str,
        character_name: str,
        chapter_number: int,
        updates: Dict[str, Any],
    ):
        """更新角色状态."""
        # 获取当前状态
        current = self.storage.get_character_state(novel_id, character_name) or {}

        # 合并更新
        new_state = {
            "last_appearance_chapter": chapter_number,
            "current_location": updates.get(
                "current_location", current.get("current_location", "")
            ),
            "cultivation_level": updates.get(
                "cultivation_level", current.get("cultivation_level", "")
            ),
            "emotional_state": updates.get(
                "emotional_state", current.get("emotional_state", "")
            ),
            "relationships": {
                **current.get("relationships", {}),
                **updates.get("relationships", {}),
            },
            "status": updates.get("status", current.get("status", "active")),
            "pending_events": updates.get(
                "pending_events", current.get("pending_events", [])
            ),
        }

        self.storage.save_character_state(novel_id, character_name, new_state)

    # ==================== 统计和管理 ====================

    def get_statistics(self, novel_id: str) -> Dict[str, Any]:
        """获取小说记忆统计."""
        return self.storage.get_statistics(novel_id)

    def close(self):
        """关闭适配器."""
        self.storage.close()


# 全局适配器实例
_novel_memory_adapter: Optional[NovelMemoryAdapter] = None


def get_novel_memory_adapter() -> NovelMemoryAdapter:
    """获取小说记忆适配器实例（单例）."""
    global _novel_memory_adapter
    if _novel_memory_adapter is None:
        _novel_memory_adapter = NovelMemoryAdapter()
    return _novel_memory_adapter
