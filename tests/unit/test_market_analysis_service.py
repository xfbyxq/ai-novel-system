"""市场分析服务单元测试"""
import pytest
from datetime import date
from backend.services.market_analysis_service import MarketAnalysisService
from core.models.crawl_result import CrawlResult
from core.models.reader_preference import ReaderPreference


async def test_get_market_data(db_session):
    """测试获取市场数据"""
    # 先创建一个CrawlerTask
    from core.models.crawler_task import CrawlerTask, CrawlTaskStatus
    test_task = CrawlerTask(
        task_name="测试任务",
        platform="qidian",
        crawl_type="ranking",
        status=CrawlTaskStatus.completed,
    )
    db_session.add(test_task)
    await db_session.flush()
    
    # 创建测试数据
    test_crawl_result = CrawlResult(
        crawler_task_id=test_task.id,
        platform="qidian",
        data_type="ranking",
        raw_data={"book_title": "测试小说", "author_name": "测试作者"},
        processed_data={"book_title": "测试小说", "author_name": "测试作者"},
        url="https://www.qidian.com/rank/yuepiao/",
    )
    db_session.add(test_crawl_result)
    await db_session.commit()
    
    # 测试服务
    service = MarketAnalysisService(db_session)
    result = await service.get_market_data(
        platform="qidian",
        data_type="ranking",
        days=7,
        limit=10,
    )
    
    assert isinstance(result, list)
    assert len(result) > 0
    assert result[0]["book_title"] == "测试小说"


async def test_get_reader_preferences(db_session):
    """测试获取读者偏好数据"""
    # 创建测试数据
    # 使用当前日期
    from datetime import datetime
    current_date = date.today()
    
    test_preference = ReaderPreference(
        source="qidian",
        genre="都市",
        tags=["现代", "情感"],
        ranking_data={"rank": 1, "score": 9.5},
        trend_score=8.5,
        data_date=current_date,
        crawler_task_id=None,
        book_id="123456",
        book_title="测试小说",
        author_name="测试作者",
        rating=4.5,
        word_count=100000,
    )
    db_session.add(test_preference)
    await db_session.commit()
    
    # 测试服务
    service = MarketAnalysisService(db_session)
    result = await service.get_reader_preferences(
        platform="qidian",
        genre="都市",
        days=30,
    )
    
    assert isinstance(result, dict)
    assert result["total_records"] == 1
    assert result["platform_distribution"]["qidian"] == 1
    assert result["genre_distribution"]["都市"] == 1
    assert result["trending_tags"]["现代"] == 1
    assert result["average_trend_score"] == 8.5


async def test_get_trending_topics(db_session):
    """测试获取热门话题"""
    # 先创建一个CrawlerTask
    from core.models.crawler_task import CrawlerTask, CrawlTaskStatus
    test_task = CrawlerTask(
        task_name="测试任务",
        platform="douyin",
        crawl_type="douyin_hot",
        status=CrawlTaskStatus.completed,
    )
    db_session.add(test_task)
    await db_session.flush()
    
    # 创建测试数据
    test_crawl_result = CrawlResult(
        crawler_task_id=test_task.id,
        platform="douyin",
        data_type="hot",
        raw_data={"title": "抖音热门话题", "heat": "100万"},
        processed_data={"title": "抖音热门话题", "heat": "100万"},
        url="https://www.douyin.com/hot",
    )
    db_session.add(test_crawl_result)
    await db_session.commit()
    
    # 测试服务
    service = MarketAnalysisService(db_session)
    result = await service.get_trending_topics(
        platform="douyin",
        limit=10,
        days=7,
    )
    
    assert isinstance(result, list)
    assert len(result) > 0
    assert result[0]["title"] == "抖音热门话题"
    assert result[0]["platform"] == "douyin"


async def test_get_recommended_genres(db_session):
    """测试获取推荐分类"""
    # 创建测试数据
    # 使用当前日期
    from datetime import datetime
    current_date = date.today()
    
    test_preference = ReaderPreference(
        source="qidian",
        genre="都市",
        tags=["现代", "情感"],
        ranking_data={"rank": 1, "score": 9.5},
        trend_score=8.5,
        data_date=current_date,
        crawler_task_id=None,
        book_id="123456",
        book_title="测试小说",
        author_name="测试作者",
        rating=4.5,
        word_count=100000,
    )
    db_session.add(test_preference)
    await db_session.commit()
    
    # 测试服务
    service = MarketAnalysisService(db_session)
    result = await service.get_recommended_genres(
        platform="qidian",
        days=30,
        limit=10,
    )
    
    assert isinstance(result, list)
    assert len(result) > 0
    assert result[0]["genre"] == "都市"


async def test_get_trending_tags(db_session):
    """测试获取热门标签"""
    # 创建测试数据
    # 使用当前日期
    from datetime import datetime
    current_date = date.today()
    
    test_preference = ReaderPreference(
        source="qidian",
        genre="都市",
        tags=["现代", "情感"],
        ranking_data={"rank": 1, "score": 9.5},
        trend_score=8.5,
        data_date=current_date,
        crawler_task_id=None,
        book_id="123456",
        book_title="测试小说",
        author_name="测试作者",
        rating=4.5,
        word_count=100000,
    )
    db_session.add(test_preference)
    await db_session.commit()
    
    # 测试服务
    service = MarketAnalysisService(db_session)
    result = await service.get_trending_tags(
        platform="qidian",
        days=14,
        limit=30,
    )
    
    assert isinstance(result, list)
    assert len(result) > 0
    assert result[0]["tag"] == "现代"


async def test_generate_market_report(db_session):
    """测试生成市场报告"""
    # 创建测试数据
    # 使用当前日期
    from datetime import datetime
    current_date = date.today()
    
    test_preference = ReaderPreference(
        source="qidian",
        genre="都市",
        tags=["现代", "情感"],
        ranking_data={"rank": 1, "score": 9.5},
        trend_score=8.5,
        data_date=current_date,
        crawler_task_id=None,
        book_id="123456",
        book_title="测试小说",
        author_name="测试作者",
        rating=4.5,
        word_count=100000,
    )
    db_session.add(test_preference)
    await db_session.commit()
    
    # 测试服务
    service = MarketAnalysisService(db_session)
    result = await service.generate_market_report(
        days=7,
        include_platforms=["qidian"],
    )
    
    assert isinstance(result, dict)
    assert "platforms" in result
    assert "qidian" in result["platforms"]
    assert "overall_insights" in result
