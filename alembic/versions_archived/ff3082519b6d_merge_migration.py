"""merge_migration

Revision ID: ff3082519b6d
Revises: 002, add_outline_enhancements
Create Date: 2026-03-14 22:22:57.571571

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "ff3082519b6d"
down_revision: Union[str, Sequence[str], None] = ("002", "add_outline_enhancements")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
