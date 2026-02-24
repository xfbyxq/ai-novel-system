"""爬虫服务 - 负责爬取平台数据"""
import asyncio
import logging
import random
from datetime import datetime, date
from typing import Optional
from uuid import UUID

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import settings
from core.models.crawler_task import CrawlerTask, CrawlTaskStatus
from core.models.crawl_result import CrawlResult
from core.models.reader_preference import ReaderPreference

logger = logging.getLogger(__name__)

# User-Agent 列表，用于轮换
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class CrawlerService:
    """爬虫服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.request_delay = settings.CRAWLER_REQUEST_DELAY
        self.timeout = settings.CRAWLER_TIMEOUT

    async def run_crawler_task(self, task_id: UUID) -> None:
        """执行爬虫任务（后台运行）"""
        # 获取任务
        result = await self.db.execute(
            select(CrawlerTask).where(CrawlerTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            logger.error(f"爬虫任务 {task_id} 未找到")
            return

        # 更新状态为运行中
        task.status = CrawlTaskStatus.running
        task.started_at = datetime.now()
        task.progress = {"status": "started", "items_crawled": 0}
        await self.db.commit()

        try:
            # 根据爬取类型分发
            if task.crawl_type == "ranking":
                await self._crawl_qidian_ranking(task)
            elif task.crawl_type == "trending_tags":
                await self._crawl_qidian_tags(task)
            elif task.crawl_type == "book_metadata":
                await self._crawl_qidian_book(task)
            elif task.crawl_type == "genre_list":
                await self._crawl_qidian_genres(task)
            elif task.crawl_type == "douyin_hot":
                await self._crawl_douyin_hot(task)
            elif task.crawl_type == "douyin_search":
                await self._crawl_douyin_search(task)
            elif task.crawl_type == "douyin_creators":
                await self._crawl_douyin_creators(task)
            elif task.crawl_type == "fanqie_ranking":
                await self._crawl_fanqie_ranking(task)
            elif task.crawl_type == "zongheng_ranking":
                await self._crawl_zongheng_ranking(task)
            else:
                raise ValueError(f"不支持的爬取类型: {task.crawl_type}")

            # 更新状态为完成
            task.status = CrawlTaskStatus.completed
            task.completed_at = datetime.now()
            await self.db.commit()

        except Exception as e:
            logger.error(f"爬虫任务 {task_id} 失败: {e}")
            task.status = CrawlTaskStatus.failed
            task.error_message = str(e)
            task.completed_at = datetime.now()
            await self.db.commit()

    async def _crawl_qidian_ranking(self, task: CrawlerTask) -> None:
        """爬取起点排行榜"""
        config = task.config or {}
        ranking_type = config.get("ranking_type", "yuepiao")  # 默认月票榜
        max_pages = config.get("max_pages", 3)

        # 起点排行榜 URL 映射
        ranking_urls = {
            "yuepiao": "https://www.qidian.com/rank/yuepiao/",      # 月票榜
            "hotsales": "https://www.qidian.com/rank/hotsales/",    # 畅销榜
            "readIndex": "https://www.qidian.com/rank/readIndex/",  # 阅读指数榜
            "recom": "https://www.qidian.com/rank/recom/",          # 推荐榜
            "collect": "https://www.qidian.com/rank/collect/",      # 收藏榜
        }

        base_url = ranking_urls.get(ranking_type, ranking_urls["yuepiao"])
        items_crawled = 0
        success_count = 0
        error_count = 0

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for page in range(1, max_pages + 1):
                try:
                    # 更新进度
                    task.progress = {
                        "current_page": page,
                        "total_pages": max_pages,
                        "items_crawled": items_crawled,
                    }
                    await self.db.commit()

                    # 发送请求
                    url = f"{base_url}?page={page}"
                    html = await self._fetch_page(client, url)

                    if not html:
                        error_count += 1
                        continue

                    # 解析页面
                    books = self._parse_qidian_ranking_page(html)

                    # 保存结果
                    for book in books:
                        await self._save_crawl_result(
                            task_id=task.id,
                            platform="qidian",
                            data_type="ranking",
                            raw_data=book,
                            processed_data=book,
                            url=url,
                        )
                        
                        # 同时更新 ReaderPreference
                        await self._update_reader_preference(
                            task_id=task.id,
                            book_data=book,
                        )
                        
                        items_crawled += 1
                        success_count += 1

                    # 请求间隔
                    await asyncio.sleep(self.request_delay)

                except Exception as e:
                    logger.error(f"爬取第 {page} 页失败: {e}")
                    error_count += 1

        # 更新结果摘要
        task.result_summary = {
            "items_count": items_crawled,
            "success_count": success_count,
            "error_count": error_count,
        }

    async def _crawl_qidian_tags(self, task: CrawlerTask) -> None:
        """爬取起点热门标签"""
        config = task.config or {}
        items_crawled = 0
        success_count = 0
        error_count = 0

        # 起点分类/标签页面
        url = "https://www.qidian.com/all/"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                task.progress = {"status": "fetching_tags", "items_crawled": 0}
                await self.db.commit()

                html = await self._fetch_page(client, url)
                if html:
                    tags = self._parse_qidian_tags_page(html)

                    for tag in tags:
                        await self._save_crawl_result(
                            task_id=task.id,
                            platform="qidian",
                            data_type="tag",
                            raw_data=tag,
                            processed_data=tag,
                            url=url,
                        )
                        items_crawled += 1
                        success_count += 1

            except Exception as e:
                logger.error(f"爬取标签失败: {e}")
                error_count += 1

        task.result_summary = {
            "items_count": items_crawled,
            "success_count": success_count,
            "error_count": error_count,
        }

    async def _crawl_qidian_book(self, task: CrawlerTask) -> None:
        """爬取起点书籍详情"""
        config = task.config or {}
        book_ids = config.get("book_ids", [])
        items_crawled = 0
        success_count = 0
        error_count = 0

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for i, book_id in enumerate(book_ids):
                try:
                    task.progress = {
                        "current": i + 1,
                        "total": len(book_ids),
                        "items_crawled": items_crawled,
                    }
                    await self.db.commit()

                    url = f"https://book.qidian.com/info/{book_id}/"
                    html = await self._fetch_page(client, url)

                    if html:
                        book_info = self._parse_qidian_book_page(html, book_id)
                        await self._save_crawl_result(
                            task_id=task.id,
                            platform="qidian",
                            data_type="book",
                            raw_data=book_info,
                            processed_data=book_info,
                            url=url,
                        )
                        
                        await self._update_reader_preference(
                            task_id=task.id,
                            book_data=book_info,
                        )
                        
                        items_crawled += 1
                        success_count += 1

                    await asyncio.sleep(self.request_delay)

                except Exception as e:
                    logger.error(f"爬取书籍 {book_id} 失败: {e}")
                    error_count += 1

        task.result_summary = {
            "items_count": items_crawled,
            "success_count": success_count,
            "error_count": error_count,
        }

    async def _crawl_fanqie_ranking(self, task: CrawlerTask) -> None:
        """爬取番茄小说排行榜"""
        config = task.config or {}
        ranking_type = config.get("ranking_type", "hot")  # 默认热门榜
        max_pages = config.get("max_pages", 3)

        # 番茄小说排行榜 URL 映射
        ranking_urls = {
            "hot": "https://fanqienovel.com/rank/hot",      # 热门榜
            "new": "https://fanqienovel.com/rank/new",      # 新书榜
            "word": "https://fanqienovel.com/rank/word",    # 字数榜
        }

        base_url = ranking_urls.get(ranking_type, ranking_urls["hot"])
        items_crawled = 0
        success_count = 0
        error_count = 0

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for page in range(1, max_pages + 1):
                try:
                    # 更新进度
                    task.progress = {
                        "current_page": page,
                        "total_pages": max_pages,
                        "items_crawled": items_crawled,
                    }
                    await self.db.commit()

                    # 发送请求
                    url = f"{base_url}?page={page}"
                    html = await self._fetch_page(client, url)

                    if not html:
                        error_count += 1
                        continue

                    # 解析页面
                    books = self._parse_fanqie_ranking_page(html)

                    # 保存结果
                    for book in books:
                        await self._save_crawl_result(
                            task_id=task.id,
                            platform="fanqie",
                            data_type="ranking",
                            raw_data=book,
                            processed_data=book,
                            url=url,
                        )
                        
                        # 同时更新 ReaderPreference
                        await self._update_reader_preference(
                            task_id=task.id,
                            book_data=book,
                            source="fanqie",
                        )
                        
                        items_crawled += 1
                        success_count += 1

                    # 请求间隔
                    await asyncio.sleep(self.request_delay)

                except Exception as e:
                    logger.error(f"爬取番茄小说第 {page} 页失败: {e}")
                    error_count += 1

        # 更新结果摘要
        task.result_summary = {
            "items_count": items_crawled,
            "success_count": success_count,
            "error_count": error_count,
        }

    async def _crawl_zongheng_ranking(self, task: CrawlerTask) -> None:
        """爬取纵横中文网排行榜"""
        config = task.config or {}
        ranking_type = config.get("ranking_type", "hot")  # 默认热门榜
        max_pages = config.get("max_pages", 3)

        # 纵横中文网排行榜 URL 映射
        ranking_urls = {
            "hot": "https://www.zongheng.com/rank/details.html?rt=1",      # 热门榜
            "vip": "https://www.zongheng.com/rank/details.html?rt=2",       # VIP榜
            "new": "https://www.zongheng.com/rank/details.html?rt=6",       # 新书榜
        }

        base_url = ranking_urls.get(ranking_type, ranking_urls["hot"])
        items_crawled = 0
        success_count = 0
        error_count = 0

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for page in range(1, max_pages + 1):
                try:
                    # 更新进度
                    task.progress = {
                        "current_page": page,
                        "total_pages": max_pages,
                        "items_crawled": items_crawled,
                    }
                    await self.db.commit()

                    # 发送请求
                    url = f"{base_url}&p={page}"
                    html = await self._fetch_page(client, url)

                    if not html:
                        error_count += 1
                        continue

                    # 解析页面
                    books = self._parse_zongheng_ranking_page(html)

                    # 保存结果
                    for book in books:
                        await self._save_crawl_result(
                            task_id=task.id,
                            platform="zongheng",
                            data_type="ranking",
                            raw_data=book,
                            processed_data=book,
                            url=url,
                        )
                        
                        # 同时更新 ReaderPreference
                        await self._update_reader_preference(
                            task_id=task.id,
                            book_data=book,
                            source="zongheng",
                        )
                        
                        items_crawled += 1
                        success_count += 1

                    # 请求间隔
                    await asyncio.sleep(self.request_delay)

                except Exception as e:
                    logger.error(f"爬取纵横中文网第 {page} 页失败: {e}")
                    error_count += 1

        # 更新结果摘要
        task.result_summary = {
            "items_count": items_crawled,
            "success_count": success_count,
            "error_count": error_count,
        }

    async def _crawl_qidian_genres(self, task: CrawlerTask) -> None:
        """爬取起点分类列表"""
        items_crawled = 0
        success_count = 0
        error_count = 0

        url = "https://www.qidian.com/all/"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                task.progress = {"status": "fetching_genres", "items_crawled": 0}
                await self.db.commit()

                html = await self._fetch_page(client, url)
                if html:
                    genres = self._parse_qidian_genres_page(html)

                    for genre in genres:
                        await self._save_crawl_result(
                            task_id=task.id,
                            platform="qidian",
                            data_type="genre",
                            raw_data=genre,
                            processed_data=genre,
                            url=url,
                        )
                        items_crawled += 1
                        success_count += 1

            except Exception as e:
                logger.error(f"爬取分类失败: {e}")
                error_count += 1

        task.result_summary = {
            "items_count": items_crawled,
            "success_count": success_count,
            "error_count": error_count,
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """获取页面 HTML（带重试）"""
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

        response = await client.get(url, headers=headers, follow_redirects=True)
        response.raise_for_status()
        return response.text

    def _parse_qidian_ranking_page(self, html: str) -> list[dict]:
        """解析起点排行榜页面"""
        books = []
        soup = BeautifulSoup(html, "lxml")

        # 查找书籍列表（起点排行榜的结构）
        book_items = soup.select(".book-mid-info, .rank-list li, .book-item")

        for item in book_items:
            try:
                book = {}

                # 书名
                title_elem = item.select_one("h2 a, .book-name a, .name a")
                if title_elem:
                    book["book_title"] = title_elem.get_text(strip=True)
                    href = title_elem.get("href", "")
                    if href:
                        # 从 URL 提取书籍 ID
                        parts = href.rstrip("/").split("/")
                        if parts:
                            book["book_id"] = parts[-1]

                # 作者
                author_elem = item.select_one(".author a, .author-name")
                if author_elem:
                    book["author_name"] = author_elem.get_text(strip=True)

                # 类型
                genre_elem = item.select_one(".author span, .type")
                if genre_elem:
                    book["genre"] = genre_elem.get_text(strip=True)

                # 简介
                intro_elem = item.select_one(".intro, .desc")
                if intro_elem:
                    book["synopsis"] = intro_elem.get_text(strip=True)

                # 字数
                word_elem = item.select_one(".total span, .word-count")
                if word_elem:
                    word_text = word_elem.get_text(strip=True)
                    # 解析字数（如 "100万字"）
                    book["word_count"] = self._parse_word_count(word_text)

                # 标签
                tags = []
                tag_elems = item.select(".tag")
                for tag_elem in tag_elems:
                    tags.append(tag_elem.get_text(strip=True))
                if tags:
                    book["tags"] = tags

                if book.get("book_title"):
                    books.append(book)

            except Exception as e:
                logger.warning(f"解析书籍条目失败: {e}")

        return books

    def _parse_qidian_tags_page(self, html: str) -> list[dict]:
        """解析起点标签页面"""
        tags = []
        soup = BeautifulSoup(html, "lxml")

        # 查找标签元素
        tag_elems = soup.select(".tag-list a, .tag-wrap a, .work-filter a")

        for elem in tag_elems:
            try:
                tag_name = elem.get_text(strip=True)
                if tag_name:
                    tags.append({
                        "name": tag_name,
                        "href": elem.get("href", ""),
                    })
            except Exception as e:
                logger.warning(f"解析标签失败: {e}")

        return tags

    def _parse_qidian_book_page(self, html: str, book_id: str) -> dict:
        """解析起点书籍详情页"""
        soup = BeautifulSoup(html, "lxml")
        book = {"book_id": book_id}

        # 书名
        title_elem = soup.select_one("h1 em, .book-info h1")
        if title_elem:
            book["book_title"] = title_elem.get_text(strip=True)

        # 作者
        author_elem = soup.select_one(".writer, .author a")
        if author_elem:
            book["author_name"] = author_elem.get_text(strip=True)

        # 简介
        intro_elem = soup.select_one(".intro, .book-intro p")
        if intro_elem:
            book["synopsis"] = intro_elem.get_text(strip=True)

        # 类型/分类
        genre_elem = soup.select_one(".book-info .tag a, .book-label a")
        if genre_elem:
            book["genre"] = genre_elem.get_text(strip=True)

        # 标签
        tags = []
        tag_elems = soup.select(".book-info .tag a, .tag-wrap a")
        for elem in tag_elems:
            tags.append(elem.get_text(strip=True))
        if tags:
            book["tags"] = tags

        return book

    def _parse_qidian_genres_page(self, html: str) -> list[dict]:
        """解析起点分类页面"""
        genres = []
        soup = BeautifulSoup(html, "lxml")

        # 查找分类元素
        genre_elems = soup.select(".channel-nav a, .nav-item a, .select-list a")

        for elem in genre_elems:
            try:
                genre_name = elem.get_text(strip=True)
                if genre_name and genre_name not in ["全部", "全部作品"]:
                    genres.append({
                        "name": genre_name,
                        "href": elem.get("href", ""),
                    })
            except Exception as e:
                logger.warning(f"解析分类失败: {e}")

        return genres

    def _parse_word_count(self, text: str) -> int:
        """解析字数文本"""
        try:
            # 移除 "字" 字符
            text = text.replace("字", "").strip()
            
            # 处理 "万" 单位
            if "万" in text:
                num = float(text.replace("万", ""))
                return int(num * 10000)
            
            # 尝试直接解析
            return int(float(text))
        except:
            return 0

    async def _save_crawl_result(
        self,
        task_id: UUID,
        platform: str,
        data_type: str,
        raw_data: dict,
        processed_data: dict,
        url: str,
    ) -> CrawlResult:
        """保存爬取结果"""
        result = CrawlResult(
            crawler_task_id=task_id,
            platform=platform,
            data_type=data_type,
            raw_data=raw_data,
            processed_data=processed_data,
            url=url,
        )
        self.db.add(result)
        await self.db.flush()
        return result

    async def _update_reader_preference(
        self,
        task_id: UUID,
        book_data: dict,
        source: str = "qidian",
    ) -> None:
        """更新读者偏好数据"""
        # 根据来源构建不同的偏好数据
        if source == "douyin":
            # 抖音数据处理
            preference = ReaderPreference(
                source="douyin",
                genre=book_data.get("category", "抖音热门"),
                tags=book_data.get("tags", []),
                ranking_data=book_data,
                trend_score=self._calculate_trend_score(book_data.get("heat", "")),
                data_date=date.today(),
                crawler_task_id=task_id,
                book_id=book_data.get("link", "").split("/")[-1] if book_data.get("link") else None,
                book_title=book_data.get("title", ""),
                author_name=book_data.get("creator", ""),
                rating=None,
                word_count=None,
            )
        elif source == "fanqie":
            # 番茄小说数据处理
            preference = ReaderPreference(
                source="fanqie",
                genre=book_data.get("genre"),
                tags=book_data.get("tags", []),
                ranking_data=book_data,
                trend_score=0.0,
                data_date=date.today(),
                crawler_task_id=task_id,
                book_id=book_data.get("book_id"),
                book_title=book_data.get("book_title"),
                author_name=book_data.get("author_name"),
                rating=book_data.get("rating"),
                word_count=book_data.get("word_count"),
            )
        elif source == "zongheng":
            # 纵横中文网数据处理
            preference = ReaderPreference(
                source="zongheng",
                genre=book_data.get("genre"),
                tags=book_data.get("tags", []),
                ranking_data=book_data,
                trend_score=0.0,
                data_date=date.today(),
                crawler_task_id=task_id,
                book_id=book_data.get("book_id"),
                book_title=book_data.get("book_title"),
                author_name=book_data.get("author_name"),
                rating=book_data.get("rating"),
                word_count=book_data.get("word_count"),
            )
        else:
            # 起点数据处理
            preference = ReaderPreference(
                source="qidian",
                genre=book_data.get("genre"),
                tags=book_data.get("tags", []),
                ranking_data=book_data,
                trend_score=0.0,
                data_date=date.today(),
                crawler_task_id=task_id,
                book_id=book_data.get("book_id"),
                book_title=book_data.get("book_title"),
                author_name=book_data.get("author_name"),
                rating=book_data.get("rating"),
                word_count=book_data.get("word_count"),
            )
        
        self.db.add(preference)
        await self.db.flush()

    def _calculate_trend_score(self, heat_text: str) -> float:
        """根据热度文本计算趋势分数"""
        try:
            # 移除所有非数字字符
            import re
            numbers = re.findall(r'\d+', heat_text)
            if numbers:
                heat_value = int(numbers[0])
                # 简单的热度到分数的映射
                if heat_value >= 10000000:
                    return 10.0
                elif heat_value >= 1000000:
                    return 9.0
                elif heat_value >= 100000:
                    return 8.0
                elif heat_value >= 10000:
                    return 7.0
                elif heat_value >= 1000:
                    return 6.0
                else:
                    return 5.0
        except:
            pass
        return 0.0

    async def _crawl_douyin_hot(self, task: CrawlerTask) -> None:
        """爬取抖音热门内容"""
        config = task.config or {}
        max_items = config.get("max_items", 50)
        items_crawled = 0
        success_count = 0
        error_count = 0

        # 抖音热门内容 URL
        url = "https://www.douyin.com/hot"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                task.progress = {"status": "fetching_douyin_hot", "items_crawled": 0}
                await self.db.commit()

                html = await self._fetch_page(client, url)

                if not html:
                    error_count += 1
                else:
                    # 解析抖音热门页面
                    hot_items = self._parse_douyin_hot_page(html)

                    # 保存结果
                    for item in hot_items[:max_items]:
                        await self._save_crawl_result(
                            task_id=task.id,
                            platform="douyin",
                            data_type="hot",
                            raw_data=item,
                            processed_data=item,
                            url=url,
                        )
                        
                        # 同时更新 ReaderPreference
                        await self._update_reader_preference(
                            task_id=task.id,
                            book_data=item,
                            source="douyin",
                        )
                        
                        items_crawled += 1
                        success_count += 1

            except Exception as e:
                logger.error(f"爬取抖音热门失败: {e}")
                error_count += 1

        task.result_summary = {
            "items_count": items_crawled,
            "success_count": success_count,
            "error_count": error_count,
        }

    async def _crawl_douyin_search(self, task: CrawlerTask) -> None:
        """爬取抖音搜索趋势"""
        config = task.config or {}
        items_crawled = 0
        success_count = 0
        error_count = 0

        # 抖音搜索趋势 URL
        url = "https://www.douyin.com/search/trending"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                task.progress = {"status": "fetching_douyin_search", "items_crawled": 0}
                await self.db.commit()

                html = await self._fetch_page(client, url)

                if not html:
                    error_count += 1
                else:
                    # 解析抖音搜索趋势页面
                    search_trends = self._parse_douyin_search_page(html)

                    # 保存结果
                    for trend in search_trends:
                        await self._save_crawl_result(
                            task_id=task.id,
                            platform="douyin",
                            data_type="search_trend",
                            raw_data=trend,
                            processed_data=trend,
                            url=url,
                        )
                        
                        # 同时更新 ReaderPreference
                        await self._update_reader_preference(
                            task_id=task.id,
                            book_data=trend,
                            source="douyin",
                        )
                        
                        items_crawled += 1
                        success_count += 1

            except Exception as e:
                logger.error(f"爬取抖音搜索趋势失败: {e}")
                error_count += 1

        task.result_summary = {
            "items_count": items_crawled,
            "success_count": success_count,
            "error_count": error_count,
        }

    async def _crawl_douyin_creators(self, task: CrawlerTask) -> None:
        """爬取抖音创作者数据"""
        config = task.config or {}
        category = config.get("category", "all")
        items_crawled = 0
        success_count = 0
        error_count = 0

        # 抖音创作者页面 URL
        url = f"https://www.douyin.com/creators/{category}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                task.progress = {"status": "fetching_douyin_creators", "items_crawled": 0}
                await self.db.commit()

                html = await self._fetch_page(client, url)

                if not html:
                    error_count += 1
                else:
                    # 解析抖音创作者页面
                    creators = self._parse_douyin_creators_page(html)

                    # 保存结果
                    for creator in creators:
                        await self._save_crawl_result(
                            task_id=task.id,
                            platform="douyin",
                            data_type="creator",
                            raw_data=creator,
                            processed_data=creator,
                            url=url,
                        )
                        
                        # 同时更新 ReaderPreference
                        await self._update_reader_preference(
                            task_id=task.id,
                            book_data=creator,
                            source="douyin",
                        )
                        
                        items_crawled += 1
                        success_count += 1

            except Exception as e:
                logger.error(f"爬取抖音创作者失败: {e}")
                error_count += 1

        task.result_summary = {
            "items_count": items_crawled,
            "success_count": success_count,
            "error_count": error_count,
        }

    def _parse_douyin_hot_page(self, html: str) -> list[dict]:
        """解析抖音热门页面"""
        hot_items = []
        soup = BeautifulSoup(html, "lxml")

        # 查找热门内容元素
        # 注意：抖音的页面结构可能会经常变化，需要根据实际情况调整选择器
        hot_elems = soup.select(".hot-item, .trending-item, .video-card")

        for elem in hot_elems:
            try:
                item = {}

                # 标题
                title_elem = elem.select_one(".title, .hot-title, .video-title")
                if title_elem:
                    item["title"] = title_elem.get_text(strip=True)

                # 热度
                heat_elem = elem.select_one(".heat, .hot-value, .play-count")
                if heat_elem:
                    item["heat"] = heat_elem.get_text(strip=True)

                # 标签
                tags = []
                tag_elems = elem.select(".tag, .hot-tag")
                for tag_elem in tag_elems:
                    tags.append(tag_elem.get_text(strip=True))
                if tags:
                    item["tags"] = tags

                # 链接
                link_elem = elem.select_one("a[href]")
                if link_elem:
                    item["link"] = link_elem.get("href", "")

                if item.get("title"):
                    hot_items.append(item)

            except Exception as e:
                logger.warning(f"解析抖音热门条目失败: {e}")

        return hot_items

    def _parse_douyin_search_page(self, html: str) -> list[dict]:
        """解析抖音搜索趋势页面"""
        search_trends = []
        soup = BeautifulSoup(html, "lxml")

        # 查找搜索趋势元素
        trend_elems = soup.select(".trend-item, .search-trend-item")

        for elem in trend_elems:
            try:
                trend = {}

                # 关键词
                keyword_elem = elem.select_one(".keyword, .trend-keyword")
                if keyword_elem:
                    trend["keyword"] = keyword_elem.get_text(strip=True)

                # 热度
                heat_elem = elem.select_one(".heat, .trend-value")
                if heat_elem:
                    trend["heat"] = heat_elem.get_text(strip=True)

                # 趋势
                trend_elem = elem.select_one(".trend, .trend-direction")
                if trend_elem:
                    trend["trend"] = trend_elem.get_text(strip=True)

                if trend.get("keyword"):
                    search_trends.append(trend)

            except Exception as e:
                logger.warning(f"解析抖音搜索趋势失败: {e}")

        return search_trends

    def _parse_douyin_creators_page(self, html: str) -> list[dict]:
        """解析抖音创作者页面"""
        creators = []
        soup = BeautifulSoup(html, "lxml")

        # 查找创作者元素
        creator_elems = soup.select(".creator-item, .user-card")

        for elem in creator_elems:
            try:
                creator = {}

                # 名称
                name_elem = elem.select_one(".name, .creator-name, .user-name")
                if name_elem:
                    creator["name"] = name_elem.get_text(strip=True)

                # 粉丝数
                fans_elem = elem.select_one(".fans, .follower-count")
                if fans_elem:
                    creator["fans_count"] = fans_elem.get_text(strip=True)

                # 分类
                category_elem = elem.select_one(".category, .creator-category")
                if category_elem:
                    creator["category"] = category_elem.get_text(strip=True)

                # 链接
                link_elem = elem.select_one("a[href]")
                if link_elem:
                    creator["link"] = link_elem.get("href", "")

                if creator.get("name"):
                    creators.append(creator)

            except Exception as e:
                logger.warning(f"解析抖音创作者失败: {e}")

        return creators

    def _parse_fanqie_ranking_page(self, html: str) -> list[dict]:
        """解析番茄小说排行榜页面"""
        books = []
        soup = BeautifulSoup(html, "lxml")

        # 查找书籍列表
        book_items = soup.select(".book-item, .rank-item, .novel-item")

        for item in book_items:
            try:
                book = {}

                # 书名
                title_elem = item.select_one("h3 a, .book-title a, .title a")
                if title_elem:
                    book["book_title"] = title_elem.get_text(strip=True)
                    href = title_elem.get("href", "")
                    if href:
                        # 从 URL 提取书籍 ID
                        parts = href.rstrip("/").split("/")
                        if parts:
                            book["book_id"] = parts[-1]

                # 作者
                author_elem = item.select_one(".author, .writer, .author-name")
                if author_elem:
                    book["author_name"] = author_elem.get_text(strip=True)

                # 类型
                genre_elem = item.select_one(".category, .type, .genre")
                if genre_elem:
                    book["genre"] = genre_elem.get_text(strip=True)

                # 简介
                intro_elem = item.select_one(".intro, .desc, .synopsis")
                if intro_elem:
                    book["synopsis"] = intro_elem.get_text(strip=True)

                # 字数
                word_elem = item.select_one(".word-count, .words, .word")
                if word_elem:
                    word_text = word_elem.get_text(strip=True)
                    book["word_count"] = self._parse_word_count(word_text)

                # 标签
                tags = []
                tag_elems = item.select(".tag, .tags a")
                for tag_elem in tag_elems:
                    tags.append(tag_elem.get_text(strip=True))
                if tags:
                    book["tags"] = tags

                if book.get("book_title"):
                    books.append(book)

            except Exception as e:
                logger.warning(f"解析番茄小说条目失败: {e}")

        return books

    def _parse_zongheng_ranking_page(self, html: str) -> list[dict]:
        """解析纵横中文网排行榜页面"""
        books = []
        soup = BeautifulSoup(html, "lxml")

        # 查找书籍列表
        book_items = soup.select(".rankli_item, .book-item, .rank-item")

        for item in book_items:
            try:
                book = {}

                # 书名
                title_elem = item.select_one("h4 a, .bookname a, .title a")
                if title_elem:
                    book["book_title"] = title_elem.get_text(strip=True)
                    href = title_elem.get("href", "")
                    if href:
                        # 从 URL 提取书籍 ID
                        parts = href.rstrip("/").split("/")
                        if parts:
                            book["book_id"] = parts[-1].split(".")[0] if "." in parts[-1] else parts[-1]

                # 作者
                author_elem = item.select_one(".author, .writer, .author-name")
                if author_elem:
                    book["author_name"] = author_elem.get_text(strip=True)

                # 类型
                genre_elem = item.select_one(".category, .type, .genre")
                if genre_elem:
                    book["genre"] = genre_elem.get_text(strip=True)

                # 简介
                intro_elem = item.select_one(".intro, .desc, .synopsis")
                if intro_elem:
                    book["synopsis"] = intro_elem.get_text(strip=True)

                # 字数
                word_elem = item.select_one(".word-count, .words, .word")
                if word_elem:
                    word_text = word_elem.get_text(strip=True)
                    book["word_count"] = self._parse_word_count(word_text)

                # 标签
                tags = []
                tag_elems = item.select(".tag, .tags a")
                for tag_elem in tag_elems:
                    tags.append(tag_elem.get_text(strip=True))
                if tags:
                    book["tags"] = tags

                if book.get("book_title"):
                    books.append(book)

            except Exception as e:
                logger.warning(f"解析纵横中文网条目失败: {e}")

        return books
