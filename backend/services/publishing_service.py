"""发布服务 - 负责管理发布任务和平台账号"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.adapters.base_adapter import BookInfo, ChapterInfo
from backend.adapters.qidian_adapter import get_adapter
from backend.services.encryption_service import EncryptionService
from core.models.chapter import Chapter
from core.models.chapter_publish import ChapterPublish, PublishStatus
from core.models.novel import Novel
from core.models.platform_account import PlatformAccount, AccountStatus
from core.models.publish_task import PublishTask, PublishType, PublishTaskStatus

logger = logging.getLogger(__name__)


class PublishingService:
    """发布服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.encryption = EncryptionService()
    
    # ============================================================
    # 平台账号管理
    # ============================================================
    
    async def create_account(
        self,
        platform: str,
        account_name: str,
        username: str,
        password: str,
        extra_credentials: Optional[dict] = None,
    ) -> PlatformAccount:
        """创建平台账号"""
        # 加密凭证
        credentials = {
            "username": username,
            "password": password,
        }
        if extra_credentials:
            credentials.update(extra_credentials)
        
        encrypted = self.encryption.encrypt_dict(credentials)
        
        account = PlatformAccount(
            platform=platform,
            account_name=account_name,
            username=username,
            encrypted_credentials=encrypted,
            status=AccountStatus.active,
        )
        self.db.add(account)
        await self.db.commit()
        await self.db.refresh(account)
        
        logger.info(f"创建平台账号: {account_name} ({platform})")
        return account
    
    async def update_account(
        self,
        account_id: UUID,
        account_name: Optional[str] = None,
        password: Optional[str] = None,
        extra_credentials: Optional[dict] = None,
        status: Optional[str] = None,
    ) -> Optional[PlatformAccount]:
        """更新平台账号"""
        result = await self.db.execute(
            select(PlatformAccount).where(PlatformAccount.id == account_id)
        )
        account = result.scalar_one_or_none()
        if not account:
            return None
        
        if account_name:
            account.account_name = account_name
        
        if password or extra_credentials:
            # 解密现有凭证
            current_credentials = self.encryption.decrypt_dict(account.encrypted_credentials)
            
            if password:
                current_credentials["password"] = password
            if extra_credentials:
                current_credentials.update(extra_credentials)
            
            # 重新加密
            account.encrypted_credentials = self.encryption.encrypt_dict(current_credentials)
        
        if status:
            account.status = AccountStatus(status)
        
        await self.db.commit()
        await self.db.refresh(account)
        return account
    
    async def get_account_credentials(self, account_id: UUID) -> Optional[dict]:
        """获取解密后的账号凭证"""
        result = await self.db.execute(
            select(PlatformAccount).where(PlatformAccount.id == account_id)
        )
        account = result.scalar_one_or_none()
        if not account:
            return None
        
        return self.encryption.decrypt_dict(account.encrypted_credentials)
    
    async def verify_account(self, account_id: UUID) -> bool:
        """验证账号是否可用"""
        credentials = await self.get_account_credentials(account_id)
        if not credentials:
            return False
        
        result = await self.db.execute(
            select(PlatformAccount).where(PlatformAccount.id == account_id)
        )
        account = result.scalar_one_or_none()
        if not account:
            return False
        
        try:
            adapter = get_adapter(account.platform, credentials)
            success = await adapter.login()
            await adapter.logout()
            
            if success:
                account.status = AccountStatus.active
                account.last_login_at = datetime.now()
            else:
                account.status = AccountStatus.invalid
            
            await self.db.commit()
            return success
            
        except Exception as e:
            logger.error(f"验证账号失败: {e}")
            account.status = AccountStatus.invalid
            await self.db.commit()
            return False
    
    # ============================================================
    # 发布任务管理
    # ============================================================
    
    async def run_publish_task(self, task_id: UUID) -> None:
        """执行发布任务（后台运行）"""
        # 获取任务
        result = await self.db.execute(
            select(PublishTask).where(PublishTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            logger.error(f"发布任务 {task_id} 未找到")
            return
        
        # 更新状态为运行中
        task.status = PublishTaskStatus.running
        task.started_at = datetime.now()
        task.progress = {"status": "started"}
        await self.db.commit()
        
        try:
            # 获取账号凭证
            credentials = await self.get_account_credentials(task.account_id)
            if not credentials:
                raise ValueError("账号凭证获取失败")
            
            # 获取账号信息
            account_result = await self.db.execute(
                select(PlatformAccount).where(PlatformAccount.id == task.account_id)
            )
            account = account_result.scalar_one_or_none()
            if not account:
                raise ValueError("账号不存在")
            
            # 创建适配器并登录
            adapter = get_adapter(account.platform, credentials)
            if not await adapter.login():
                raise ValueError("平台登录失败")
            
            try:
                # 根据发布类型分发
                if task.publish_type == PublishType.create_book:
                    await self._create_book(task, adapter)
                elif task.publish_type == PublishType.publish_chapter:
                    await self._publish_single_chapter(task, adapter)
                elif task.publish_type == PublishType.batch_publish:
                    await self._batch_publish(task, adapter)
                else:
                    raise ValueError(f"不支持的发布类型: {task.publish_type}")
                
                # 更新状态为完成
                task.status = PublishTaskStatus.completed
                task.completed_at = datetime.now()
                
            finally:
                await adapter.logout()
            
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"发布任务 {task_id} 失败: {e}")
            task.status = PublishTaskStatus.failed
            task.error_message = str(e)
            task.completed_at = datetime.now()
            await self.db.commit()
    
    async def _create_book(self, task: PublishTask, adapter) -> None:
        """创建新书"""
        # 获取小说信息
        result = await self.db.execute(
            select(Novel).where(Novel.id == task.novel_id)
        )
        novel = result.scalar_one_or_none()
        if not novel:
            raise ValueError("小说不存在")
        
        task.progress = {"status": "creating_book", "title": novel.title}
        await self.db.commit()
        
        # 创建书籍
        book_info = BookInfo(
            title=novel.title,
            author=novel.author,
            synopsis=novel.synopsis or "",
            genre=novel.genre,
            tags=novel.tags or [],
            cover_url=novel.cover_url,
        )
        
        result = await adapter.create_book(book_info)
        
        if result.success:
            task.platform_book_id = result.platform_id
            task.result_summary = {
                "book_created": True,
                "platform_id": result.platform_id,
                "extra": result.extra_data,
            }
        else:
            raise ValueError(f"创建书籍失败: {result.error_message}")
    
    async def _publish_single_chapter(self, task: PublishTask, adapter) -> None:
        """发布单章"""
        config = task.config or {}
        chapter_number = config.get("chapter_number", 1)
        volume_number = config.get("volume_number", 1)
        
        if not task.platform_book_id:
            raise ValueError("未设置平台书籍ID，请先创建书籍")
        
        # 获取章节
        result = await self.db.execute(
            select(Chapter).where(
                Chapter.novel_id == task.novel_id,
                Chapter.chapter_number == chapter_number,
                Chapter.volume_number == volume_number,
            )
        )
        chapter = result.scalar_one_or_none()
        if not chapter:
            raise ValueError(f"章节 {volume_number}-{chapter_number} 不存在")
        
        task.progress = {
            "status": "publishing_chapter",
            "chapter_number": chapter_number,
        }
        await self.db.commit()
        
        # 发布章节
        chapter_info = ChapterInfo(
            chapter_number=chapter.chapter_number,
            title=chapter.title or f"第{chapter.chapter_number}章",
            content=chapter.content or "",
            volume_number=chapter.volume_number,
        )
        
        pub_result = await adapter.publish_chapter(task.platform_book_id, chapter_info)
        
        # 记录发布结果
        chapter_publish = ChapterPublish(
            publish_task_id=task.id,
            chapter_id=chapter.id,
            chapter_number=chapter.chapter_number,
            status=PublishStatus.published if pub_result.success else PublishStatus.failed,
            platform_chapter_id=pub_result.platform_id,
            error_message=pub_result.error_message,
            published_at=datetime.now() if pub_result.success else None,
        )
        self.db.add(chapter_publish)
        
        if pub_result.success:
            task.result_summary = {
                "chapters_published": 1,
                "platform_chapter_id": pub_result.platform_id,
            }
        else:
            raise ValueError(f"发布章节失败: {pub_result.error_message}")
    
    async def _batch_publish(self, task: PublishTask, adapter) -> None:
        """批量发布章节"""
        config = task.config or {}
        from_chapter = config.get("from_chapter", 1)
        to_chapter = config.get("to_chapter", from_chapter)
        volume_number = config.get("volume_number", 1)
        
        if not task.platform_book_id:
            raise ValueError("未设置平台书籍ID，请先创建书籍")
        
        # 获取章节列表
        result = await self.db.execute(
            select(Chapter).where(
                Chapter.novel_id == task.novel_id,
                Chapter.volume_number == volume_number,
                Chapter.chapter_number >= from_chapter,
                Chapter.chapter_number <= to_chapter,
            ).order_by(Chapter.chapter_number)
        )
        chapters = result.scalars().all()
        
        if not chapters:
            raise ValueError(f"未找到章节 {from_chapter}-{to_chapter}")
        
        total = len(chapters)
        success_count = 0
        fail_count = 0
        
        for i, chapter in enumerate(chapters):
            task.progress = {
                "status": "publishing",
                "current": i + 1,
                "total": total,
                "chapter_number": chapter.chapter_number,
            }
            await self.db.commit()
            
            # 发布章节
            chapter_info = ChapterInfo(
                chapter_number=chapter.chapter_number,
                title=chapter.title or f"第{chapter.chapter_number}章",
                content=chapter.content or "",
                volume_number=chapter.volume_number,
            )
            
            pub_result = await adapter.publish_chapter(task.platform_book_id, chapter_info)
            
            # 记录发布结果
            chapter_publish = ChapterPublish(
                publish_task_id=task.id,
                chapter_id=chapter.id,
                chapter_number=chapter.chapter_number,
                status=PublishStatus.published if pub_result.success else PublishStatus.failed,
                platform_chapter_id=pub_result.platform_id,
                error_message=pub_result.error_message,
                published_at=datetime.now() if pub_result.success else None,
            )
            self.db.add(chapter_publish)
            
            if pub_result.success:
                success_count += 1
            else:
                fail_count += 1
                logger.warning(f"章节 {chapter.chapter_number} 发布失败: {pub_result.error_message}")
            
            # 发布间隔
            await asyncio.sleep(2)
        
        task.result_summary = {
            "total": total,
            "success_count": success_count,
            "fail_count": fail_count,
        }
    
    async def get_publish_preview(
        self,
        novel_id: UUID,
        from_chapter: int = 1,
        to_chapter: Optional[int] = None,
    ) -> dict:
        """获取发布预览"""
        # 获取小说
        novel_result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id)
        )
        novel = novel_result.scalar_one_or_none()
        if not novel:
            return {"error": "小说不存在"}
        
        # 获取章节
        query = select(Chapter).where(
            Chapter.novel_id == novel_id,
            Chapter.chapter_number >= from_chapter,
        )
        if to_chapter:
            query = query.where(Chapter.chapter_number <= to_chapter)
        query = query.order_by(Chapter.chapter_number)
        
        result = await self.db.execute(query)
        chapters = result.scalars().all()
        
        # 获取已发布记录
        published_chapters = {}
        pub_result = await self.db.execute(
            select(ChapterPublish).where(
                ChapterPublish.chapter_id.in_([c.id for c in chapters]),
                ChapterPublish.status == PublishStatus.published,
            )
        )
        for pub in pub_result.scalars().all():
            published_chapters[pub.chapter_id] = pub
        
        # 构建预览
        chapter_previews = []
        unpublished_count = 0
        for chapter in chapters:
            is_published = chapter.id in published_chapters
            if not is_published:
                unpublished_count += 1
            
            pub_record = published_chapters.get(chapter.id)
            chapter_previews.append({
                "chapter_number": chapter.chapter_number,
                "title": chapter.title or f"第{chapter.chapter_number}章",
                "word_count": chapter.word_count,
                "status": chapter.status.value if hasattr(chapter.status, 'value') else str(chapter.status),
                "is_published": is_published,
                "published_at": pub_record.published_at.isoformat() if pub_record else None,
            })
        
        return {
            "novel_id": str(novel_id),
            "novel_title": novel.title,
            "total_chapters": len(chapters),
            "unpublished_count": unpublished_count,
            "chapters": chapter_previews,
        }
