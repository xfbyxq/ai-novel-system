"""Merge multiple heads.

Revision ID: d784dd8cedf8
Revises: 117e653b6d9a, 650321fc7ff3
Create Date: 2026-03-19 16:58:08.267369

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d784dd8cedf8"
down_revision: Union[str, Sequence[str], None] = ("117e653b6d9a", "650321fc7ff3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
