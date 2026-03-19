"""add agent_name column to token_usages table (minimal)

Revision ID: 117e653b6d9a
Revises: 8a5ce9fa2032
Create Date: 2026-03-15 14:10:02.056282

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '117e653b6d9a'
down_revision: Union[str, Sequence[str], None] = 'ff3082519b6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 检查列是否存在，避免重复添加
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'token_usages' AND column_name = 'agent_name'
    """))
    
    if not result.fetchone():
        # 添加 agent_name 列
        op.add_column('token_usages', sa.Column('agent_name', sa.String(length=100), nullable=False, server_default='Unknown'))
        # 移除默认值，因为模型中是 nullable=False
        op.alter_column('token_usages', 'agent_name', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    # 删除 agent_name 列
    op.drop_column('token_usages', 'agent_name')
