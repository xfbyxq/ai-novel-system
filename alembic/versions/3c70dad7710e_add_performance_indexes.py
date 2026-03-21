"""add_performance_indexes

Revision ID: 3c70dad7710e
Revises: 90162718523f
Create Date: 2026-03-21 16:54:27.276026

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c70dad7710e'
down_revision: Union[str, Sequence[str], None] = '90162718523f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add performance indexes for slow queries."""
    # ### Issue #6: 数据库索引缺失修复 ###
    
    # 1. novels 表索引
    with op.batch_alter_table("novels", schema=None) as batch_op:
        # user_id 索引 (外键查询) - 如果存在 user_id 列
        # 注意：novels 表目前没有 user_id 列，如果有需要添加
        # status 索引 (状态筛选)
        batch_op.create_index(
            batch_op.f("ix_novels_status"), ["status"], unique=False
        )
        # created_at 索引 (时间排序)
        batch_op.create_index(
            batch_op.f("ix_novels_created_at"), ["created_at"], unique=False
        )
    
    # 2. chapters 表索引
    with op.batch_alter_table("chapters", schema=None) as batch_op:
        # novel_id 索引 (关联查询)
        batch_op.create_index(
            batch_op.f("ix_chapters_novel_id"), ["novel_id"], unique=False
        )
        # status 索引 (状态筛选)
        batch_op.create_index(
            batch_op.f("ix_chapters_status"), ["status"], unique=False
        )
        # created_at 索引 (时间排序)
        batch_op.create_index(
            batch_op.f("ix_chapters_created_at"), ["created_at"], unique=False
        )
    
    # 3. generation_tasks 表索引
    with op.batch_alter_table("generation_tasks", schema=None) as batch_op:
        # novel_id 索引 (关联查询)
        batch_op.create_index(
            batch_op.f("ix_generation_tasks_novel_id"), ["novel_id"], unique=False
        )
        # status 索引 (状态筛选)
        batch_op.create_index(
            batch_op.f("ix_generation_tasks_status"), ["status"], unique=False
        )
        # created_at 索引 (时间排序)
        batch_op.create_index(
            batch_op.f("ix_generation_tasks_created_at"), ["created_at"], unique=False
        )
    
    # 4. publish_tasks 表索引
    with op.batch_alter_table("publish_tasks", schema=None) as batch_op:
        # novel_id 索引 (关联查询)
        batch_op.create_index(
            batch_op.f("ix_publish_tasks_novel_id"), ["novel_id"], unique=False
        )
        # status 索引 (状态筛选)
        batch_op.create_index(
            batch_op.f("ix_publish_tasks_status"), ["status"], unique=False
        )
        # created_at 索引 (时间排序)
        batch_op.create_index(
            batch_op.f("ix_publish_tasks_created_at"), ["created_at"], unique=False
        )
    
    # 5. agent_activities 表索引 (已有部分索引，补充完整)
    with op.batch_alter_table("agent_activities", schema=None) as batch_op:
        # status 索引 (状态筛选)
        batch_op.create_index(
            batch_op.f("ix_agent_activities_status"), ["status"], unique=False
        )
        # created_at 索引已有，无需重复添加


def downgrade() -> None:
    """Downgrade schema - remove performance indexes."""
    # ### Issue #6: 数据库索引缺失修复 - 回滚 ###
    
    # 1. novels 表索引
    with op.batch_alter_table("novels", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_novels_status"))
        batch_op.drop_index(batch_op.f("ix_novels_created_at"))
    
    # 2. chapters 表索引
    with op.batch_alter_table("chapters", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_chapters_novel_id"))
        batch_op.drop_index(batch_op.f("ix_chapters_status"))
        batch_op.drop_index(batch_op.f("ix_chapters_created_at"))
    
    # 3. generation_tasks 表索引
    with op.batch_alter_table("generation_tasks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_generation_tasks_novel_id"))
        batch_op.drop_index(batch_op.f("ix_generation_tasks_status"))
        batch_op.drop_index(batch_op.f("ix_generation_tasks_created_at"))
    
    # 4. publish_tasks 表索引
    with op.batch_alter_table("publish_tasks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_publish_tasks_novel_id"))
        batch_op.drop_index(batch_op.f("ix_publish_tasks_status"))
        batch_op.drop_index(batch_op.f("ix_publish_tasks_created_at"))
    
    # 5. agent_activities 表索引
    with op.batch_alter_table("agent_activities", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_agent_activities_status"))
