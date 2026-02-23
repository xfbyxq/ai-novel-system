"""集成测试：Crawler API 端点"""
import asyncio
from unittest.mock import patch

import pytest

from core.models.crawler_task import CrawlerTask, CrawlType, CrawlTaskStatus


@pytest.mark.integration
class TestCrawlerAPI:
    """测试 Crawler API 端点"""

    async def test_create_task_returns_201(self, test_client, db_session):
        """POST /api/v1/crawler/tasks 创建任务返回 201"""
        # Mock asyncio.create_task 避免后台任务执行
        with patch("backend.api.v1.crawler.asyncio.create_task"):
            response = await test_client.post(
                "/api/v1/crawler/tasks",
                json={
                    "task_name": "测试创建任务",
                    "platform": "qidian",
                    "crawl_type": "ranking",
                    "config": {"ranking_type": "yuepiao", "max_pages": 1},
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["task_name"] == "测试创建任务"
        assert data["status"] == "pending"
        assert "id" in data

    async def test_create_task_invalid_type_returns_400(self, test_client, db_session):
        """无效的 crawl_type 返回 400"""
        with patch("backend.api.v1.crawler.asyncio.create_task"):
            response = await test_client.post(
                "/api/v1/crawler/tasks",
                json={
                    "task_name": "无效类型任务",
                    "platform": "qidian",
                    "crawl_type": "invalid_type",
                },
            )

        assert response.status_code == 400
        assert "无效的爬取类型" in response.json()["detail"]

    async def test_list_tasks(self, test_client, db_session):
        """GET /api/v1/crawler/tasks 获取任务列表"""
        # 先创建几个任务
        for i in range(3):
            task = CrawlerTask(
                task_name=f"列表测试任务{i}",
                platform="qidian",
                crawl_type=CrawlType.ranking,
                status=CrawlTaskStatus.pending,
            )
            db_session.add(task)
        await db_session.commit()

        response = await test_client.get("/api/v1/crawler/tasks")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 3

    async def test_get_task_detail(self, test_client, db_session):
        """GET /api/v1/crawler/tasks/{id} 获取任务详情"""
        task = CrawlerTask(
            task_name="详情测试任务",
            platform="qidian",
            crawl_type=CrawlType.ranking,
            status=CrawlTaskStatus.pending,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        response = await test_client.get(f"/api/v1/crawler/tasks/{task.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["task_name"] == "详情测试任务"
        assert data["id"] == str(task.id)

    async def test_get_task_not_found_returns_404(self, test_client, db_session):
        """不存在的任务返回 404"""
        from uuid import uuid4

        fake_id = uuid4()
        response = await test_client.get(f"/api/v1/crawler/tasks/{fake_id}")

        assert response.status_code == 404
        assert "未找到" in response.json()["detail"]

    async def test_cancel_task(self, test_client, db_session):
        """POST /api/v1/crawler/tasks/{id}/cancel 取消任务"""
        task = CrawlerTask(
            task_name="取消测试任务",
            platform="qidian",
            crawl_type=CrawlType.ranking,
            status=CrawlTaskStatus.running,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        response = await test_client.post(f"/api/v1/crawler/tasks/{task.id}/cancel")

        assert response.status_code == 200
        assert "已取消" in response.json()["message"]

        # 验证数据库状态
        await db_session.refresh(task)
        assert task.status == CrawlTaskStatus.cancelled

    async def test_cancel_completed_task_returns_400(self, test_client, db_session):
        """不能取消已完成的任务"""
        task = CrawlerTask(
            task_name="已完成任务",
            platform="qidian",
            crawl_type=CrawlType.ranking,
            status=CrawlTaskStatus.completed,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        response = await test_client.post(f"/api/v1/crawler/tasks/{task.id}/cancel")

        assert response.status_code == 400
        assert "终态" in response.json()["detail"]

    async def test_get_task_results_empty(self, test_client, db_session):
        """获取任务结果（空）"""
        task = CrawlerTask(
            task_name="结果测试任务",
            platform="qidian",
            crawl_type=CrawlType.ranking,
            status=CrawlTaskStatus.completed,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        response = await test_client.get(f"/api/v1/crawler/tasks/{task.id}/results")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
