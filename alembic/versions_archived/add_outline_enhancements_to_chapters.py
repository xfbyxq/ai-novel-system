"""Add outline enhancements to chapters

Revision ID: add_outline_enhancements
Revises: 2a4218cba9df
Create Date: 2026-03-13 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_outline_enhancements"
down_revision: Union[str, None] = "2a4218cba9df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add outline_task, outline_validation, and outline_version columns to chapters table."""
    op.add_column(
        "chapters",
        sa.Column(
            "outline_task", postgresql.JSONB(), nullable=True, server_default="{}"
        ),
    )
    op.add_column(
        "chapters",
        sa.Column(
            "outline_validation", postgresql.JSONB(), nullable=True, server_default="{}"
        ),
    )
    op.add_column(
        "chapters", sa.Column("outline_version", sa.String(length=50), nullable=True)
    )


def downgrade() -> None:
    """Remove outline_task, outline_validation, and outline_version columns from chapters table."""
    op.drop_column("chapters", "outline_version")
    op.drop_column("chapters", "outline_validation")
    op.drop_column("chapters", "outline_task")
