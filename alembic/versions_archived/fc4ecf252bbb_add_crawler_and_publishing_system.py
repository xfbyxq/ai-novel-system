"""add_crawler_and_publishing_system.

Revision ID: fc4ecf252bbb
Revises: 40555b81bb5d
Create Date: 2026-02-23 15:58:33.328332

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "fc4ecf252bbb"
down_revision: Union[str, Sequence[str], None] = "40555b81bb5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 创建 crawler_tasks 表
    op.create_table(
        "crawler_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("task_name", sa.String(length=100), nullable=False),
        sa.Column(
            "platform", sa.String(length=50), nullable=False, server_default="qidian"
        ),
        sa.Column(
            "crawl_type",
            sa.Enum(
                "ranking",
                "trending_tags",
                "book_metadata",
                "genre_list",
                name="crawltype",
                create_type=True,
            ),
            nullable=False,
        ),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "completed",
                "failed",
                "cancelled",
                name="crawltaskstatus",
                create_type=True,
            ),
            nullable=True,
        ),
        sa.Column("progress", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "result_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index(
        "ix_crawler_tasks_platform_status", "crawler_tasks", ["platform", "status"]
    )
    op.create_index("ix_crawler_tasks_created_at", "crawler_tasks", ["created_at"])

    # 创建 crawl_results 表
    op.create_table(
        "crawl_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("crawler_task_id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("data_type", sa.String(length=50), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "processed_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["crawler_task_id"], ["crawler_tasks.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crawl_results_task_id", "crawl_results", ["crawler_task_id"])

    # 创建 platform_accounts 表
    op.create_table(
        "platform_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("platform_name", sa.String(length=50), nullable=False),
        sa.Column("account_name", sa.String(length=100), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "inactive", "expired", "error", name="accountstatus"),
            nullable=True,
        ),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
    op.create_index(
        "ix_platform_accounts_platform", "platform_accounts", ["platform_name"]
    )

    # 创建 publish_tasks 表
    op.create_table(
        "publish_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("novel_id", sa.UUID(), nullable=False),
        sa.Column("platform_account_id", sa.UUID(), nullable=False),
        sa.Column(
            "publish_type",
            sa.Enum(
                "create_book", "publish_chapter", "batch_publish", name="publishtype"
            ),
            nullable=False,
        ),
        sa.Column("target_chapters", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "completed",
                "failed",
                "cancelled",
                name="publishtaskstatus",
            ),
            nullable=True,
        ),
        sa.Column("progress", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "result_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["platform_account_id"], ["platform_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_publish_tasks_novel_id", "publish_tasks", ["novel_id"])
    op.create_index("ix_publish_tasks_status", "publish_tasks", ["status"])

    # 创建 chapter_publishes 表
    op.create_table(
        "chapter_publishes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("publish_task_id", sa.UUID(), nullable=False),
        sa.Column("chapter_id", sa.UUID(), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("platform_chapter_id", sa.String(length=100), nullable=True),
        sa.Column("platform_url", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "publishing", "published", "failed", name="publishstatus"
            ),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["publish_task_id"], ["publish_tasks.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chapter_publishes_task_id", "chapter_publishes", ["publish_task_id"]
    )

    # 扩展 reader_preferences 表
    op.add_column(
        "reader_preferences", sa.Column("crawler_task_id", sa.UUID(), nullable=True)
    )
    op.add_column(
        "reader_preferences", sa.Column("book_id", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "reader_preferences",
        sa.Column("book_title", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "reader_preferences",
        sa.Column("author_name", sa.String(length=100), nullable=True),
    )
    op.add_column("reader_preferences", sa.Column("rating", sa.Float(), nullable=True))
    op.add_column(
        "reader_preferences", sa.Column("word_count", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_reader_preferences_crawler_task",
        "reader_preferences",
        "crawler_tasks",
        ["crawler_task_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 移除 reader_preferences 的扩展字段
    op.drop_constraint(
        "fk_reader_preferences_crawler_task", "reader_preferences", type_="foreignkey"
    )
    op.drop_column("reader_preferences", "word_count")
    op.drop_column("reader_preferences", "rating")
    op.drop_column("reader_preferences", "author_name")
    op.drop_column("reader_preferences", "book_title")
    op.drop_column("reader_preferences", "book_id")
    op.drop_column("reader_preferences", "crawler_task_id")

    # 删除表（按依赖顺序反向删除）
    op.drop_index("ix_chapter_publishes_task_id", table_name="chapter_publishes")
    op.drop_table("chapter_publishes")

    op.drop_index("ix_publish_tasks_status", table_name="publish_tasks")
    op.drop_index("ix_publish_tasks_novel_id", table_name="publish_tasks")
    op.drop_table("publish_tasks")

    op.drop_index("ix_platform_accounts_platform", table_name="platform_accounts")
    op.drop_table("platform_accounts")

    op.drop_index("ix_crawl_results_task_id", table_name="crawl_results")
    op.drop_table("crawl_results")

    op.drop_index("ix_crawler_tasks_created_at", table_name="crawler_tasks")
    op.drop_index("ix_crawler_tasks_platform_status", table_name="crawler_tasks")
    op.drop_table("crawler_tasks")

    # 删除枚举类型
    sa.Enum(name="publishstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="publishtaskstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="publishtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="accountstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="crawltaskstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="crawltype").drop(op.get_bind(), checkfirst=True)
