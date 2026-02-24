"""抖音平台适配器

支持在抖音相关平台发布内容。
"""
import asyncio
import logging
import random
from typing import Optional

import httpx

from backend.adapters.base_adapter import (
    BasePlatformAdapter,
    BookInfo,
    ChapterInfo,
    PublishResult,
)

logger = logging.getLogger(__name__)


class DouyinAdapter(BasePlatformAdapter):
    """抖音适配器
    
    此适配器提供与抖音平台交互的接口。
    注意：抖音的API可能会经常变化，需要根据实际情况调整。
    """
    
    platform_name = "douyin"
    
    # 模拟的 API 端点（实际需要根据抖音开放平台文档调整）
    BASE_URL = "https://api.douyin.com"
    LOGIN_URL = f"{BASE_URL}/passport/login/"
    CREATE_CONTENT_URL = f"{BASE_URL}/content/create/"
    PUBLISH_ARTICLE_URL = f"{BASE_URL}/article/publish/"
    
    def __init__(self, credentials: dict):
        super().__init__(credentials)
        self.client: Optional[httpx.AsyncClient] = None
        self.user_id: Optional[str] = None
        self.access_token: Optional[str] = None
        
    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
            )
        return self.client
    
    async def login(self) -> bool:
        """登录抖音
        
        注意：抖音的登录流程可能会经常变化，需要根据实际情况调整。
        """
        try:
            logger.info(f"正在登录抖音账号: {self.credentials.get('username')}")
            
            # 模拟登录延迟
            await asyncio.sleep(1)
            
            # 模拟登录成功
            self.is_logged_in = True
            self.user_id = f"user_{random.randint(1000000, 9999999)}"
            self.access_token = f"douyin_token_{random.randint(1000000, 9999999)}"
            self.session_data = {
                "user_id": self.user_id,
                "access_token": self.access_token,
            }
            
            logger.info(f"抖音登录成功，用户ID: {self.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"抖音登录失败: {e}")
            self.is_logged_in = False
            return False
    
    async def logout(self) -> None:
        """登出抖音"""
        if self.client:
            await self.client.aclose()
            self.client = None
        self.is_logged_in = False
        self.session_data = None
        self.user_id = None
        self.access_token = None
        logger.info("已登出抖音")
    
    async def create_content(self, book_info: BookInfo) -> PublishResult:
        """在抖音创建内容
        
        注意：抖音主要是短视频平台，这里模拟创建抖音内容。
        """
        if not self.is_logged_in:
            return PublishResult(
                success=False,
                error_message="未登录，请先登录"
            )
        
        try:
            logger.info(f"正在抖音创建内容: {book_info.title}")
            
            # 模拟创建延迟
            await asyncio.sleep(2)
            
            # 模拟创建成功
            platform_content_id = f"dy_{random.randint(1000000, 9999999)}"
            
            logger.info(f"抖音内容创建成功: {platform_content_id}")
            return PublishResult(
                success=True,
                platform_id=platform_content_id,
                extra_data={
                    "title": book_info.title,
                    "status": "published",
                }
            )
            
        except Exception as e:
            logger.error(f"抖音内容创建失败: {e}")
            return PublishResult(
                success=False,
                error_message=str(e)
            )
    
    async def create_book(self, book_info: BookInfo) -> PublishResult:
        """在抖音创建内容（重写基类方法）"""
        return await self.create_content(book_info)
    
    async def publish_chapter(
        self,
        platform_book_id: str,
        chapter_info: ChapterInfo,
    ) -> PublishResult:
        """在抖音发布章节
        
        注意：抖音主要是短视频平台，这里模拟发布短视频内容。
        """
        if not self.is_logged_in:
            return PublishResult(
                success=False,
                error_message="未登录，请先登录"
            )
        
        try:
            logger.info(
                f"正在抖音发布内容: 内容ID={platform_book_id}, "
                f"章节={chapter_info.chapter_number}"
            )
            
            # 模拟发布延迟
            await asyncio.sleep(1)
            
            # 验证内容长度
            if len(chapter_info.content) < 50:
                return PublishResult(
                    success=False,
                    error_message="内容过短，抖音要求至少50字"
                )
            
            # 模拟发布成功
            platform_chapter_id = f"dy_ch_{random.randint(10000000, 99999999)}"
            
            logger.info(f"抖音内容发布成功: {platform_chapter_id}")
            return PublishResult(
                success=True,
                platform_id=platform_chapter_id,
                extra_data={
                    "chapter_number": chapter_info.chapter_number,
                    "word_count": len(chapter_info.content),
                    "status": "published",
                }
            )
            
        except Exception as e:
            logger.error(f"抖音内容发布失败: {e}")
            return PublishResult(
                success=False,
                error_message=str(e)
            )
    
    async def get_book_info(self, platform_book_id: str) -> Optional[dict]:
        """获取抖音内容信息"""
        if not self.is_logged_in:
            return None
        
        try:
            # 模拟获取延迟
            await asyncio.sleep(0.5)
            
            # 模拟返回内容信息
            return {
                "content_id": platform_book_id,
                "status": "published",
                "view_count": random.randint(100, 10000),
                "like_count": random.randint(10, 1000),
                "comment_count": random.randint(0, 100),
            }
            
        except Exception as e:
            logger.error(f"获取抖音内容信息失败: {e}")
            return None
    
    async def get_published_chapters(self, platform_book_id: str) -> list[dict]:
        """获取抖音已发布的内容列表"""
        if not self.is_logged_in:
            return []
        
        try:
            # 模拟获取延迟
            await asyncio.sleep(0.5)
            
            # 模拟返回章节列表
            chapters = []
            for i in range(1, random.randint(3, 10)):
                chapters.append({
                    "chapter_id": f"dy_ch_{i}",
                    "chapter_number": i,
                    "title": f"第{i}部分",
                    "word_count": random.randint(200, 1000),
                    "published_at": "2024-01-01 12:00:00",
                    "view_count": random.randint(100, 5000),
                })
            
            return chapters
            
        except Exception as e:
            logger.error(f"获取抖音内容列表失败: {e}")
            return []
    
    async def update_chapter(
        self,
        platform_book_id: str,
        platform_chapter_id: str,
        chapter_info: ChapterInfo,
    ) -> PublishResult:
        """更新抖音内容"""
        if not self.is_logged_in:
            return PublishResult(
                success=False,
                error_message="未登录，请先登录"
            )
        
        try:
            logger.info(f"正在更新抖音内容: {platform_chapter_id}")
            await asyncio.sleep(1)
            
            # 模拟更新成功
            return PublishResult(
                success=True,
                platform_id=platform_chapter_id,
                extra_data={"updated": True}
            )
            
        except Exception as e:
            return PublishResult(
                success=False,
                error_message=str(e)
            )
