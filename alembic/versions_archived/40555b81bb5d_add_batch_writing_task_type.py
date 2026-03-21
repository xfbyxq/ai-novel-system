"""add_batch_writing_task_type.

Revision ID: 40555b81bb5d
Revises: 5badc20e064a
Create Date: 2026-02-23 07:15:40.473518

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "40555b81bb5d"
down_revision: Union[str, Sequence[str], None] = "5badc20e064a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 添加 'batch_writing' 到 TaskType 枚举
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'batch_writing'")


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL 不支持直接删除枚举值，需要重建类型
    # 此处留空，实际上不建议回滚此迁移
