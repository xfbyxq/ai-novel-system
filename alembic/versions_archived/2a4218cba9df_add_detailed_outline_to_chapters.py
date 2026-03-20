"""Add detailed_outline column to chapters

Revision ID: 2a4218cba9df
Revises: 5c24a4e1ec52
Create Date: 2026-03-07 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2a4218cba9df'
down_revision: Union[str, None] = '5c24a4e1ec52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add detailed_outline JSONB column to chapters table."""
    op.add_column(
        'chapters',
        sa.Column('detailed_outline', postgresql.JSONB(), nullable=True, server_default='{}')
    )


def downgrade() -> None:
    """Remove detailed_outline column from chapters table."""
    op.drop_column('chapters', 'detailed_outline')
