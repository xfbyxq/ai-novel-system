"""add novel_id and title to chat session.

Revision ID: 5c24a4e1ec52
Revises: 575f1ce44645
Create Date: 2026-02-25

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5c24a4e1ec52"
down_revision: Union[str, None] = "575f1ce44645"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加 novel_id 字段 - 用于按小说隔离会话
    op.add_column(
        "ai_chat_sessions",
        sa.Column("novel_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_ai_chat_sessions_novel_id"),
        "ai_chat_sessions",
        ["novel_id"],
        unique=False,
    )

    # 添加 title 字段 - 用于识别会话内容
    op.add_column("ai_chat_sessions", sa.Column("title", sa.String(200), nullable=True))

    # 从现有的 context 字段中提取 novel_id 更新到新字段
    # 使用原始 SQL 因为需要处理 JSON 字段
    op.execute("""
        UPDATE ai_chat_sessions
        SET novel_id = (context->>'novel_id')::uuid
        WHERE context->>'novel_id' IS NOT NULL
        AND context->>'novel_id' != ''
        AND context->>'novel_id' ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    """)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_chat_sessions_novel_id"), table_name="ai_chat_sessions")
    op.drop_column("ai_chat_sessions", "novel_id")
    op.drop_column("ai_chat_sessions", "title")
