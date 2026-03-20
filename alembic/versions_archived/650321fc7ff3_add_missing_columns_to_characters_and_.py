"""add_missing_columns_to_characters_and_remove_old_columns

Revision ID: 650321fc7ff3
Revises: c6cfc7b3ef20
Create Date: 2026-03-14 22:39:22.459815

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '650321fc7ff3'
down_revision: Union[str, Sequence[str], None] = 'c6cfc7b3ef20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.
    
    注意：此迁移原本用于添加 role_type, growth_arc, first_appearance_chapter, avatar_url 列，
    并删除 role, character_arc 列。但这些更改已在初始迁移 5badc20e064a 中完成，
    因此此迁移为空操作（no-op）。
    """
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
