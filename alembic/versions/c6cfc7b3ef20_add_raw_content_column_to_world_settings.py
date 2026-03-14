"""add_raw_content_column_to_world_settings

Revision ID: c6cfc7b3ef20
Revises: ff3082519b6d
Create Date: 2026-03-14 22:33:29.757291

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6cfc7b3ef20'
down_revision: Union[str, Sequence[str], None] = 'ff3082519b6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
