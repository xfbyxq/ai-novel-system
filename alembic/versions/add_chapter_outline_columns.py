"""add plot_outline_id and outline_version_id to chapters

Revision ID: add_chapter_outline_columns
Revises: 3c70dad7710e
Create Date: 2026-03-22 09:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_chapter_outline_columns"
down_revision: Union[str, None] = "3c70dad7710e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chapters",
        sa.Column(
            "plot_outline_id",
            sa.UUID(),
            nullable=True,
        ),
    )
    op.add_column(
        "chapters",
        sa.Column(
            "outline_version_id",
            sa.UUID(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("chapters", "outline_version_id")
    op.drop_column("chapters", "plot_outline_id")
