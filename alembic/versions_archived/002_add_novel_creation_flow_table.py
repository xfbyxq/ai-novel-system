"""add novel creation flow table.

Revision ID: 002
Revises: 186700edca0b
Create Date: 2026-03-12

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "2a4218cba9df"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "novel_creation_flows",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("novel_id", sa.String(100), nullable=True),
        sa.Column("scene", sa.String(50), default="create"),
        sa.Column("current_step", sa.String(50), default="initial"),
        sa.Column("genre", sa.String(100), nullable=True),
        sa.Column(
            "world_setting_data", postgresql.JSONB(astext_type=sa.Text()), default=dict
        ),
        sa.Column(
            "synopsis_data", postgresql.JSONB(astext_type=sa.Text()), default=dict
        ),
        sa.Column("novel_title", sa.String(200), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), default=list),
        sa.Column("target_platform", sa.String(100), default="番茄小说"),
        sa.Column("length_type", sa.String(50), default="medium"),
        sa.Column("selected_novel_id", sa.String(100), nullable=True),
        sa.Column("query_target", sa.String(100), nullable=True),
        sa.Column(
            "query_result", postgresql.JSONB(astext_type=sa.Text()), default=dict
        ),
        sa.Column("revision_target", sa.String(100), nullable=True),
        sa.Column(
            "revision_details", postgresql.JSONB(astext_type=sa.Text()), default=dict
        ),
        sa.Column("genre_confirmed", sa.Boolean, default=False),
        sa.Column("world_setting_confirmed", sa.Boolean, default=False),
        sa.Column("synopsis_confirmed", sa.Boolean, default=False),
        sa.Column("final_confirmed", sa.Boolean, default=False),
        sa.Column("revision_confirmed", sa.Boolean, default=False),
        sa.Column(
            "conversation_history",
            postgresql.JSONB(astext_type=sa.Text()),
            default=list,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["ai_chat_sessions.session_id"]),
        sa.UniqueConstraint("session_id"),
    )

    op.create_index(
        "ix_novel_creation_flows_session_id", "novel_creation_flows", ["session_id"]
    )
    op.create_index(
        "ix_novel_creation_flows_novel_id", "novel_creation_flows", ["novel_id"]
    )
    op.create_index(
        "ix_novel_creation_flows_selected_novel_id",
        "novel_creation_flows",
        ["selected_novel_id"],
    )


def downgrade():
    op.drop_index("ix_novel_creation_flows_selected_novel_id")
    op.drop_index("ix_novel_creation_flows_novel_id")
    op.drop_index("ix_novel_creation_flows_session_id")
    op.drop_table("novel_creation_flows")
