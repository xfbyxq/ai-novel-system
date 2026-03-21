"""平台账号模型."""

import enum
import uuid

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class AccountStatus(str, enum.Enum):
    """账号状态."""

    active = "active"  # 正常
    inactive = "inactive"  # 未激活
    expired = "expired"  # 已过期
    error = "error"  # 异常


class PlatformAccount(Base):
    """平台账号（加密存储凭证）."""

    __tablename__ = "platform_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_name = Column(String(50), nullable=False)  # qidian
    account_name = Column(String(100), nullable=False)  # 备注名
    username = Column(String(100), nullable=False)
    encrypted_credentials = Column(
        Text, nullable=True
    )  # Fernet 加密的 JSON（含密码、cookies、tokens）
    status = Column(String(50), default="inactive")
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    publish_tasks = relationship(
        "PublishTask", back_populates="platform_account", cascade="all, delete-orphan"
    )
