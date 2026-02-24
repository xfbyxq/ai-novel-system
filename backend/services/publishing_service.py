"""发布服务 - 负责管理发布任务和平台账号"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
            # 模拟验证成功
            account.status = AccountStatus.active
            account.last_login_at = datetime.now()
            await self.db.commit()
            return True
            
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
            
            # 模拟发布过程
            await asyncio.sleep(2)  # 模拟处理时间
            
            # 根据发布类型设置结果
            if task.publish_type == PublishType.create_book:
                task.platform_book_id = "mock_book_id"
                task.result_summary = {
                    "book_created": True,
                    "platform_id": "mock_book_id",
                    "extra": {"message": "模拟创建书籍成功"},
                }
            elif task.publish_type == PublishType.publish_chapter:
                task.result_summary = {
                    "chapters_published": 1,
                    "platform_chapter_id": "mock_chapter_id",
                }
            elif task.publish_type == PublishType.batch_publish:
                task.result_summary = {
                    "total": 1,
                    "success_count": 1,
                    "fail_count": 0,
                }
            
            # 更新状态为完成
            task.status = PublishTaskStatus.completed
            task.completed_at = datetime.now()
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"发布任务 {task_id} 失败: {e}")
            task.status = PublishTaskStatus.failed
            task.error_message = str(e)
            task.completed_at = datetime.now()
            await self.db.commit()
    

    
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
