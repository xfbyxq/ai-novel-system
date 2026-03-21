"""fix: complete database tables

Revision ID: 186700edca0b
Revises: 82c931d1231a
Create Date: 2026-02-24 09:26:16.500062

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "186700edca0b"
down_revision: Union[str, Sequence[str], None] = "82c931d1231a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    """检查表是否存在"""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}')"
        )
    )
    return result.scalar()


def upgrade() -> None:
    """Upgrade schema."""
    # 只创建不存在的表

    if not table_exists("novels"):
        op.create_table(
            "novels",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("author", sa.String(length=100), nullable=True),
            sa.Column("genre", sa.String(length=50), nullable=False),
            sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column(
                "status",
                sa.Enum(
                    "planning",
                    "writing",
                    "completed",
                    "published",
                    name="novelstatus",
                    create_type=False,
                ),
                nullable=True,
            ),
            sa.Column("word_count", sa.Integer(), nullable=True),
            sa.Column("chapter_count", sa.Integer(), nullable=True),
            sa.Column("cover_url", sa.String(length=500), nullable=True),
            sa.Column("synopsis", sa.Text(), nullable=True),
            sa.Column("target_platform", sa.String(length=50), nullable=True),
            sa.Column(
                "estimated_revenue", sa.Numeric(precision=10, scale=2), nullable=True
            ),
            sa.Column(
                "actual_revenue", sa.Numeric(precision=10, scale=2), nullable=True
            ),
            sa.Column("token_cost", sa.Numeric(precision=10, scale=4), nullable=True),
            sa.Column(
                "metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if not table_exists("chapters"):
        op.create_table(
            "chapters",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("novel_id", sa.UUID(), nullable=False),
            sa.Column("chapter_number", sa.Integer(), nullable=False),
            sa.Column("volume_number", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=200), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("word_count", sa.Integer(), nullable=True),
            sa.Column(
                "status",
                sa.Enum(
                    "draft",
                    "reviewing",
                    "published",
                    name="chapterstatus",
                    create_type=False,
                ),
                nullable=True,
            ),
            sa.Column(
                "outline", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "characters_appeared", postgresql.ARRAY(sa.UUID()), nullable=True
            ),
            sa.Column(
                "plot_points", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "foreshadowing", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column("quality_score", sa.Float(), nullable=True),
            sa.Column(
                "continuity_issues",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            comment="Novel chapters",
        )

    if not table_exists("characters"):
        op.create_table(
            "characters",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("novel_id", sa.UUID(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column(
                "role_type",
                sa.Enum(
                    "protagonist",
                    "supporting",
                    "antagonist",
                    "minor",
                    name="roletype",
                    create_type=False,
                ),
                nullable=True,
            ),
            sa.Column(
                "gender",
                sa.Enum("male", "female", "other", name="gender", create_type=False),
                nullable=True,
            ),
            sa.Column("age", sa.Integer(), nullable=True),
            sa.Column("appearance", sa.Text(), nullable=True),
            sa.Column("personality", sa.Text(), nullable=True),
            sa.Column("background", sa.Text(), nullable=True),
            sa.Column("goals", sa.Text(), nullable=True),
            sa.Column(
                "abilities", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "relationships", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "growth_arc", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "status",
                sa.Enum(
                    "alive",
                    "dead",
                    "unknown",
                    name="characterstatus",
                    create_type=False,
                ),
                nullable=True,
            ),
            sa.Column("first_appearance_chapter", sa.Integer(), nullable=True),
            sa.Column("avatar_url", sa.String(length=500), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not table_exists("generation_tasks"):
        op.create_table(
            "generation_tasks",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("novel_id", sa.UUID(), nullable=False),
            sa.Column(
                "task_type",
                sa.Enum(
                    "planning",
                    "writing",
                    "editing",
                    "batch_writing",
                    name="tasktype",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column(
                "status",
                sa.Enum(
                    "pending",
                    "running",
                    "completed",
                    "failed",
                    "cancelled",
                    name="taskstatus",
                    create_type=False,
                ),
                nullable=True,
            ),
            sa.Column("phase", sa.String(length=50), nullable=True),
            sa.Column(
                "input_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "output_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "agent_logs", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column("token_usage", sa.Integer(), nullable=True),
            sa.Column("cost", sa.Numeric(precision=10, scale=4), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not table_exists("plot_outlines"):
        op.create_table(
            "plot_outlines",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("novel_id", sa.UUID(), nullable=False),
            sa.Column("structure_type", sa.String(length=50), nullable=True),
            sa.Column(
                "volumes", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "main_plot", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "sub_plots", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "key_turning_points",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
            sa.Column("climax_chapter", sa.Integer(), nullable=True),
            sa.Column("raw_content", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("novel_id"),
        )

    if not table_exists("world_settings"):
        op.create_table(
            "world_settings",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("novel_id", sa.UUID(), nullable=False),
            sa.Column("world_name", sa.String(length=200), nullable=True),
            sa.Column("world_type", sa.String(length=50), nullable=True),
            sa.Column(
                "power_system", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "geography", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "factions", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column(
                "timeline", postgresql.JSONB(astext_type=sa.Text()), nullable=True
            ),
            sa.Column(
                "special_elements",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
            sa.Column("raw_content", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("novel_id"),
        )

    if not table_exists("token_usages"):
        op.create_table(
            "token_usages",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("novel_id", sa.UUID(), nullable=False),
            sa.Column("task_id", sa.UUID(), nullable=False),
            sa.Column("agent_name", sa.String(length=100), nullable=False),
            sa.Column("prompt_tokens", sa.Integer(), nullable=True),
            sa.Column("completion_tokens", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
            sa.Column("cost", sa.Numeric(precision=10, scale=6), nullable=True),
            sa.Column(
                "timestamp",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["task_id"], ["generation_tasks.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    """Downgrade schema."""
    # 只删除这个迁移创建的表（不删除其他迁移创建的）
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS token_usages CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS world_settings CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS plot_outlines CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS generation_tasks CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS characters CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS chapters CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS novels CASCADE"))
