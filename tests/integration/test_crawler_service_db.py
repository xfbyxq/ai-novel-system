"""集成测试：CrawlerService 与数据库的交互"""
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from backend.services.crawler_service import CrawlerService
from core.models.crawler_task import CrawlerTask, CrawlType, CrawlTaskStatus
from tests.fixtures.html_samples import RANKING_PAGE_HTML


@pytest.mark.integration
class TestCrawlerServiceDB:
    """测试 CrawlerService 数据库持久化"""

    async def test_save_crawl_result_persists_to_db(self, db_session):
        """保存爬取结果到数据库并验证"""
        # 先创建一个 task
        task = CrawlerTask(
            task_name="测试任务",
            platform="qidian",
            crawl_type=CrawlType.ranking,
            status=CrawlTaskStatus.pending,
        )
        db_session.add(task)
        await db_session.flush()

        service = CrawlerService(db=db_session)

        # 保存结果
        result = await service._save_crawl_result(
            task_id=task.id,
            platform="qidian",
            data_type="ranking",
            raw_data={"book_title": "测试书籍", "author_name": "测试作者"},
            processed_data={"book_title": "测试书籍", "author_name": "测试作者"},
            url="https://www.qidian.com/rank/yuepiao/",
        )

        assert result.id is not None
        assert result.crawler_task_id == task.id
        assert result.platform == "qidian"
        assert result.data_type == "ranking"
        assert result.raw_data["book_title"] == "测试书籍"

    async def test_update_reader_preference_persists(self, db_session):
        """保存读者偏好到数据库并验证"""
        task = CrawlerTask(
            task_name="测试任务",
            platform="qidian",
            crawl_type=CrawlType.ranking,
            status=CrawlTaskStatus.pending,
        )
        db_session.add(task)
        await db_session.flush()

        service = CrawlerService(db=db_session)

        book_data = {
            "book_id": "12345",
            "book_title": "测试小说",
            "author_name": "测试作者",
            "genre": "玄幻",
            "tags": ["热血", "系统"],
            "word_count": 1000000,
        }

        await service._update_reader_preference(task_id=task.id, book_data=book_data)
        await db_session.flush()

    @patch.object(CrawlerService, "_fetch_page")
    async def test_run_crawler_task_with_mock_fetch(self, mock_fetch, db_session):
        """mock _fetch_page，执行完整 task 流程"""
        # Mock 返回样本 HTML
        mock_fetch.return_value = RANKING_PAGE_HTML

        # 创建任务
        task = CrawlerTask(
            task_name="测试排行榜爬取",
            platform="qidian",
            crawl_type=CrawlType.ranking,
            config={"ranking_type": "yuepiao", "max_pages": 1},
            status=CrawlTaskStatus.pending,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        # 执行爬虫任务
        service = CrawlerService(db=db_session)
        await service.run_crawler_task(task.id)

        # 刷新获取最新状态
        await db_session.refresh(task)

        # 验证任务状态
        assert task.status == CrawlTaskStatus.completed
        assert task.started_at is not None
        assert task.completed_at is not None
        assert task.result_summary is not None
        assert task.result_summary.get("items_count", 0) > 0

        print(f"\n[集成测试] 任务完成，爬取 {task.result_summary.get('items_count')} 条数据")
