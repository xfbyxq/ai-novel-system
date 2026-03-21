"""add_outline_dynamic_update_fields

Revision ID: fb6eed83562e
Revises: d784dd8cedf8
Create Date: 2026-03-19 19:17:15.740733

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "fb6eed83562e"
down_revision: Union[str, Sequence[str], None] = "d784dd8cedf8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """plot_outlines 表新增大纲动态更新相关字段"""
    op.add_column(
        "plot_outlines",
        sa.Column(
            "update_history",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=True,
            comment="大纲动态更新历史记录",
        ),
    )
    op.add_column(
        "plot_outlines",
        sa.Column(
            "version",
            sa.Integer(),
            server_default="1",
            nullable=True,
            comment="大纲版本号，每次动态更新 +1",
        ),
    )


def downgrade() -> None:
    """移除大纲动态更新字段"""
    op.drop_column("plot_outlines", "version")
    op.drop_column("plot_outlines", "update_history")
