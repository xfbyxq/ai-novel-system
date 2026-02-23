"""平台适配器基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class BookInfo:
    """书籍信息"""
    title: str
    author: str
    synopsis: str
    genre: str
    tags: list[str]
    cover_url: Optional[str] = None


@dataclass
class ChapterInfo:
    """章节信息"""
    chapter_number: int
    title: str
    content: str
    volume_number: int = 1


@dataclass
class PublishResult:
    """发布结果"""
    success: bool
    platform_id: Optional[str] = None
    error_message: Optional[str] = None
    extra_data: Optional[dict] = None


class BasePlatformAdapter(ABC):
    """平台适配器基类
    
    所有平台适配器都需要继承此类并实现相关方法。
    """
    
    platform_name: str = "base"
    
    def __init__(self, credentials: dict):
        """初始化适配器
        
        Args:
            credentials: 包含登录凭证的字典，至少包含 username 和 password
        """
        self.credentials = credentials
        self.is_logged_in = False
        self.session_data: Optional[dict] = None
    
    @abstractmethod
    async def login(self) -> bool:
        """登录平台
        
        Returns:
            登录是否成功
        """
        pass
    
    @abstractmethod
    async def logout(self) -> None:
        """登出平台"""
        pass
    
    @abstractmethod
    async def create_book(self, book_info: BookInfo) -> PublishResult:
        """在平台创建新书
        
        Args:
            book_info: 书籍信息
            
        Returns:
            发布结果，包含平台书籍ID
        """
        pass
    
    @abstractmethod
    async def publish_chapter(
        self,
        platform_book_id: str,
        chapter_info: ChapterInfo,
    ) -> PublishResult:
        """发布章节
        
        Args:
            platform_book_id: 平台书籍ID
            chapter_info: 章节信息
            
        Returns:
            发布结果，包含平台章节ID
        """
        pass
    
    @abstractmethod
    async def get_book_info(self, platform_book_id: str) -> Optional[dict]:
        """获取平台上的书籍信息
        
        Args:
            platform_book_id: 平台书籍ID
            
        Returns:
            书籍信息字典，不存在则返回 None
        """
        pass
    
    @abstractmethod
    async def get_published_chapters(self, platform_book_id: str) -> list[dict]:
        """获取已发布的章节列表
        
        Args:
            platform_book_id: 平台书籍ID
            
        Returns:
            章节信息列表
        """
        pass
    
    async def update_chapter(
        self,
        platform_book_id: str,
        platform_chapter_id: str,
        chapter_info: ChapterInfo,
    ) -> PublishResult:
        """更新已发布的章节（可选实现）
        
        Args:
            platform_book_id: 平台书籍ID
            platform_chapter_id: 平台章节ID
            chapter_info: 新的章节信息
            
        Returns:
            更新结果
        """
        return PublishResult(
            success=False,
            error_message="该平台不支持章节更新"
        )
    
    async def delete_chapter(
        self,
        platform_book_id: str,
        platform_chapter_id: str,
    ) -> PublishResult:
        """删除已发布的章节（可选实现）
        
        Args:
            platform_book_id: 平台书籍ID
            platform_chapter_id: 平台章节ID
            
        Returns:
            删除结果
        """
        return PublishResult(
            success=False,
            error_message="该平台不支持章节删除"
        )
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} platform={self.platform_name} logged_in={self.is_logged_in}>"
