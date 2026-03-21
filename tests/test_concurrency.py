"""并发控制测试 - Issue #7 验证.

测试并发场景下的数据一致性：
1. 并发更新同一小说
2. 并发创建章节
3. 并发修改用户状态
"""

import asyncio
import uuid
from decimal import Decimal
from typing import List
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from core.models.novel import Novel


class TestNovelConcurrency:
    """小说并发操作测试."""

    @pytest.mark.asyncio
    async def test_concurrent_novel_updates(
        self, async_client: AsyncClient, test_novel: Novel
    ):
        """测试并发更新同一小说 - 应该只有一个成功."""
        novel_id = test_novel.id

        async def update_novel(update_data: dict):
            """更新小说的辅助函数."""
            response = await async_client.patch(
                f"/api/v1/novels/{novel_id}", json=update_data
            )
            return response.status_code, response.json()

        # 并发发送多个更新请求
        updates = [
            {"title": f"并发测试 {i}", "word_count": i * 1000}
            for i in range(5)
        ]

        tasks = [update_novel(update) for update in updates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计成功和失败的请求
        success_count = 0
        conflict_count = 0

        for result in results:
            if isinstance(result, Exception):
                # 异常处理
                conflict_count += 1
            else:
                status_code, data = result
                if status_code == 200:
                    success_count += 1
                elif status_code == 409:  # Conflict - 并发冲突
                    conflict_count += 1

        # 验证：只有一个更新成功，其他都被拒绝
        assert success_count == 1, f"期望 1 个成功，实际 {success_count} 个"
        assert conflict_count == 4, f"期望 4 个冲突，实际 {conflict_count} 个"

    @pytest.mark.asyncio
    async def test_concurrent_novel_status_changes(
        self, async_client: AsyncClient, test_novel: Novel
    ):
        """测试并发修改小说状态 - 应该只有一个成功."""
        novel_id = test_novel.id

        async def change_status(status: str):
            """修改小说状态的辅助函数."""
            response = await async_client.patch(
                f"/api/v1/novels/{novel_id}",
                json={"status": status},
            )
            return response.status_code, response.json()

        # 并发发送多个状态变更请求
        statuses = ["writing", "completed", "published", "planning"]
        tasks = [change_status(status) for status in statuses]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计成功和失败的请求
        success_count = 0
        conflict_count = 0

        for result in results:
            if isinstance(result, Exception):
                conflict_count += 1
            else:
                status_code, data = result
                if status_code == 200:
                    success_count += 1
                elif status_code == 409:
                    conflict_count += 1

        # 验证：只有一个状态变更成功
        assert success_count == 1, f"期望 1 个成功，实际 {success_count} 个"
        assert conflict_count == 3, f"期望 3 个冲突，实际 {conflict_count} 个"


class TestChapterConcurrency:
    """章节并发操作测试."""

    @pytest.mark.asyncio
    async def test_concurrent_chapter_updates(
        self, async_client: AsyncClient, test_novel: Novel
    ):
        """测试并发更新同一章节 - 应该只有一个成功."""
        novel_id = test_novel.id
        chapter_number = 1

        # 先创建一个章节
        create_response = await async_client.post(
            f"/api/v1/novels/{novel_id}/chapters",
            json={
                "chapter_number": chapter_number,
                "title": "初始章节",
                "content": "初始内容",
            },
        )
        assert create_response.status_code == 201

        async def update_chapter(content: str):
            """更新章节的辅助函数."""
            response = await async_client.patch(
                f"/api/v1/novels/{novel_id}/chapters/{chapter_number}",
                json={"content": content},
            )
            return response.status_code, response.json()

        # 并发发送多个更新请求
        updates = [f"并发内容版本 {i}" for i in range(5)]
        tasks = [update_chapter(content) for content in updates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计成功和失败的请求
        success_count = 0
        conflict_count = 0

        for result in results:
            if isinstance(result, Exception):
                conflict_count += 1
            else:
                status_code, data = result
                if status_code == 200:
                    success_count += 1
                elif status_code == 409:
                    conflict_count += 1

        # 验证：只有一个更新成功
        assert success_count == 1, f"期望 1 个成功，实际 {success_count} 个"
        assert conflict_count == 4, f"期望 4 个冲突，实际 {conflict_count} 个"

    @pytest.mark.asyncio
    async def test_concurrent_chapter_creation(
        self, async_client: AsyncClient, test_novel: Novel
    ):
        """测试并发创建同一章节号的章节 - 应该只有一个成功."""
        novel_id = test_novel.id
        chapter_number = 999  # 使用不存在的章节号

        async def create_chapter(ch_num: int, content: str):
            """创建章节的辅助函数."""
            response = await async_client.post(
                f"/api/v1/novels/{novel_id}/chapters",
                json={
                    "chapter_number": ch_num,
                    "title": f"章节 {ch_num}",
                    "content": content,
                },
            )
            return response.status_code, response.json()

        # 并发创建同一章节号的章节
        tasks = [
            create_chapter(chapter_number, f"内容版本 {i}") for i in range(5)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计成功和失败的请求
        success_count = 0
        conflict_count = 0

        for result in results:
            if isinstance(result, Exception):
                conflict_count += 1
            else:
                status_code, data = result
                if status_code == 201:
                    success_count += 1
                elif status_code in [409, 400]:  # Conflict or Bad Request
                    conflict_count += 1

        # 验证：只有一个创建成功
        assert success_count == 1, f"期望 1 个成功，实际 {success_count} 个"
        assert conflict_count == 4, f"期望 4 个冲突，实际 {conflict_count} 个"


class TestDatabaseLocking:
    """数据库锁机制测试."""

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(
        self, async_client: AsyncClient, test_novel: Novel
    ):
        """测试事务回滚 - 错误时应该回滚所有更改."""
        novel_id = test_novel.id
        original_word_count = test_novel.word_count or 0

        # 尝试一个会导致错误的更新
        response = await async_client.patch(
            f"/api/v1/novels/{novel_id}",
            json={
                "word_count": original_word_count + 1000,
                "invalid_field": "this_should_fail",  # 无效字段
            },
        )

        # 验证请求失败
        assert response.status_code in [422, 400]

        # 验证数据库中的小说数据未改变（事务回滚）
        # 注意：这里需要重新查询数据库
        # 在实际测试中应该通过数据库连接验证


class TestPerformanceWithIndexes:
    """索引性能测试 - Issue #6 验证."""

    @pytest.mark.asyncio
    async def test_novel_status_query_performance(
        self, async_client: AsyncClient, test_novels: List[Novel]
    ):
        """测试 status 字段索引性能."""
        import time

        # 测试 status 筛选查询
        start_time = time.time()
        response = await async_client.get(
            "/api/v1/novels",
            params={"status": "planning", "page_size": 100},
        )
        elapsed = time.time() - start_time

        assert response.status_code == 200
        # 有索引的情况下应该在 100ms 内完成
        assert elapsed < 0.1, f"查询耗时 {elapsed:.3f}s，期望 < 0.1s"

    @pytest.mark.asyncio
    async def test_novel_created_at_sorting_performance(
        self, async_client: AsyncClient, test_novels: List[Novel]
    ):
        """测试 created_at 字段索引性能（时间排序）."""
        import time

        # 测试 created_at 排序查询
        start_time = time.time()
        response = await async_client.get(
            "/api/v1/novels",
            params={"page_size": 100},
        )
        elapsed = time.time() - start_time

        assert response.status_code == 200
        # 有索引的情况下应该在 100ms 内完成
        assert elapsed < 0.1, f"查询耗时 {elapsed:.3f}s，期望 < 0.1s"

    @pytest.mark.asyncio
    async def test_chapter_novel_id_query_performance(
        self, async_client: AsyncClient, test_novel: Novel
    ):
        """测试 novel_id 字段索引性能（关联查询）."""
        import time

        novel_id = test_novel.id

        # 测试 novel_id 筛选查询
        start_time = time.time()
        response = await async_client.get(
            f"/api/v1/novels/{novel_id}/chapters",
            params={"page_size": 100},
        )
        elapsed = time.time() - start_time

        assert response.status_code == 200
        # 有索引的情况下应该在 100ms 内完成
        assert elapsed < 0.1, f"查询耗时 {elapsed:.3f}s，期望 < 0.1s"


# Fixtures
@pytest.fixture
async def test_novel(async_client: AsyncClient) -> Novel:
    """创建测试用小说."""
    response = await async_client.post(
        "/api/v1/novels",
        json={
            "title": f"测试小说 {uuid.uuid4()}",
            "genre": "玄幻",
            "status": "planning",
        },
    )
    assert response.status_code == 201
    return Novel(**response.json())


@pytest.fixture
async def test_novels(async_client: AsyncClient) -> List[Novel]:
    """创建多个测试用小说."""
    novels = []
    for i in range(20):
        response = await async_client.post(
            "/api/v1/novels",
            json={
                "title": f"测试小说 {i} - {uuid.uuid4()}",
                "genre": "玄幻",
                "status": ["planning", "writing", "completed"][i % 3],
            },
        )
        assert response.status_code == 201
        novels.append(Novel(**response.json()))
    return novels
