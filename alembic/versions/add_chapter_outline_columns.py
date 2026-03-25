"""add plot_outline_id and outline_version_id to chapters

Revision ID: add_chapter_outline_columns
Revises:
Create Date: 2026-03-22 09:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_chapter_outline_columns"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chapters",
        sa.Column(
            "plot_outline_id",
            sa.UUID(),
            sa.ForeignKey("plot_outlines.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "chapters",
        sa.Column(
            "outline_version_id",
            sa.UUID(),
            sa.ForeignKey("plot_outline_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("chapters", "outline_version_id")
    op.drop_column("chapters", "plot_outline_id")
