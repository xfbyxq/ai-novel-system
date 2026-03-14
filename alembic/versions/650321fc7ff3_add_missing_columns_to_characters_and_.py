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
    """Upgrade schema."""
    # 添加新列到characters表
    op.add_column('characters', sa.Column('role_type', sa.String(length=50), nullable=True))
    op.add_column('characters', sa.Column('growth_arc', sa.JSON(), nullable=True))
    op.add_column('characters', sa.Column('first_appearance_chapter', sa.Integer(), nullable=True))
    op.add_column('characters', sa.Column('avatar_url', sa.String(length=500), nullable=True))
    
    # 移除旧列
    op.drop_column('characters', 'role')
    op.drop_column('characters', 'character_arc')


def downgrade() -> None:
    """Downgrade schema."""
    # 恢复旧列
    op.add_column('characters', sa.Column('character_arc', sa.TEXT(), autoincrement=False, nullable=True))
    op.add_column('characters', sa.Column('role', sa.VARCHAR(length=50), autoincrement=False, nullable=True))
    
    # 移除新列
    op.drop_column('characters', 'avatar_url')
    op.drop_column('characters', 'first_appearance_chapter')
    op.drop_column('characters', 'growth_arc')
    op.drop_column('characters', 'role_type')
