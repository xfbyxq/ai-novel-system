"""add unique constraint on characters (novel_id, name).

Revision ID: a1b2c3d4e5f6
Revises: fb6eed83562e
Create Date: 2026-03-20 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "fb6eed83562e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """清理重复角色数据，并添加 (novel_id, lower(name)) 唯一索引防止未来重复."""
    # 先清理现有重复数据：每组同名角色保留 created_at 最早的记录
    op.execute(sa.text("""
        DELETE FROM characters
        WHERE id NOT IN (
            SELECT DISTINCT ON (novel_id, lower(name)) id
            FROM characters
            ORDER BY novel_id, lower(name), created_at ASC
        )
    """))
    # 添加唯一索引（不区分大小写）
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX ix_characters_novel_id_name_unique "
            "ON characters (novel_id, lower(name))"
        )
    )


def downgrade() -> None:
    """移除角色唯一索引."""
    op.drop_index("ix_characters_novel_id_name_unique", table_name="characters")
