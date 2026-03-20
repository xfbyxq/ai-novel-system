"""fix: add all missing columns, tables, and convert remaining enums to varchar

彻底修复所有 ORM 模型与数据库的不匹配：
1. 添加缺失列：plot_outlines.main_plot_detailed
2. 转换残留枚举列：platform_accounts/publish_tasks/chapter_publishes
3. 创建缺失表：agent_activities, character_name_versions

Revision ID: c5d6e7f8a9b0
Revises: b3c4d5e6f7a8
Create Date: 2026-03-20 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """修复所有 ORM 模型与数据库的差异。"""

    # ========== 1. 添加缺失列 ==========
    # plot_outlines.main_plot_detailed (JSONB) - PlotOutline 模型第 76 行
    op.add_column('plot_outlines', sa.Column(
        'main_plot_detailed',
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=True
    ))

    # ========== 2. 转换残留的枚举列为 varchar ==========
    # platform_accounts.status: accountstatus -> varchar(50)
    op.alter_column(
        'platform_accounts', 'status',
        type_=sa.String(50),
        existing_type=postgresql.ENUM(
            'active', 'inactive', 'expired', 'error',
            name='accountstatus'
        ),
        existing_nullable=True,
        postgresql_using='status::text'
    )

    # publish_tasks.publish_type: publishtype -> varchar(50)
    op.alter_column(
        'publish_tasks', 'publish_type',
        type_=sa.String(50),
        existing_type=postgresql.ENUM(
            'create_book', 'publish_chapter', 'batch_publish',
            name='publishtype'
        ),
        existing_nullable=False,
        postgresql_using='publish_type::text'
    )

    # publish_tasks.status: publishtaskstatus -> varchar(50)
    op.alter_column(
        'publish_tasks', 'status',
        type_=sa.String(50),
        existing_type=postgresql.ENUM(
            'pending', 'running', 'completed', 'failed', 'cancelled',
            name='publishtaskstatus'
        ),
        existing_nullable=True,
        postgresql_using='status::text'
    )

    # chapter_publishes.status: publishstatus -> varchar(50)
    op.alter_column(
        'chapter_publishes', 'status',
        type_=sa.String(50),
        existing_type=postgresql.ENUM(
            'pending', 'publishing', 'published', 'failed',
            name='publishstatus'
        ),
        existing_nullable=True,
        postgresql_using='status::text'
    )

    # 清理残留枚举类型
    op.execute(sa.text("DROP TYPE IF EXISTS accountstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS publishtype"))
    op.execute(sa.text("DROP TYPE IF EXISTS publishtaskstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS publishstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS crawltaskstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS crawltype"))

    # ========== 3. 创建缺失表 ==========
    # agent_activities 表 - AgentActivity 模型
    op.create_table(
        'agent_activities',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('novel_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_name', sa.String(100), nullable=False),
        sa.Column('agent_role', sa.String(200), nullable=True),
        sa.Column('activity_type', sa.String(50), nullable=False),
        sa.Column('phase', sa.String(50), nullable=True),
        sa.Column('step_number', sa.Integer(), nullable=True),
        sa.Column('iteration_number', sa.Integer(), nullable=True),
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('raw_output', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('cost', sa.Numeric(10, 6), nullable=True, server_default='0'),
        sa.Column('status', sa.String(20), nullable=True, server_default='success'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['generation_tasks.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_agent_activities_novel_task', 'agent_activities', ['novel_id', 'task_id'])
    op.create_index('idx_agent_activities_type', 'agent_activities', ['activity_type'])
    op.create_index('idx_agent_activities_created', 'agent_activities', ['created_at'])
    op.create_index('ix_agent_activities_agent_name', 'agent_activities', ['agent_name'])
    op.create_index('ix_agent_activities_novel_id', 'agent_activities', ['novel_id'])
    op.create_index('ix_agent_activities_task_id', 'agent_activities', ['task_id'])
    op.create_index('ix_agent_activities_activity_type', 'agent_activities', ['activity_type'])

    # character_name_versions 表 - CharacterNameVersion 模型
    op.create_table(
        'character_name_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('character_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('old_name', sa.String(100), nullable=False),
        sa.Column('new_name', sa.String(100), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('changed_by', sa.String(100), nullable=False, server_default='system'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    )


def downgrade() -> None:
    """回滚所有更改。"""
    # 删除新增表
    op.drop_table('character_name_versions')
    op.drop_index('ix_agent_activities_activity_type', table_name='agent_activities')
    op.drop_index('ix_agent_activities_task_id', table_name='agent_activities')
    op.drop_index('ix_agent_activities_novel_id', table_name='agent_activities')
    op.drop_index('ix_agent_activities_agent_name', table_name='agent_activities')
    op.drop_index('idx_agent_activities_created', table_name='agent_activities')
    op.drop_index('idx_agent_activities_type', table_name='agent_activities')
    op.drop_index('idx_agent_activities_novel_task', table_name='agent_activities')
    op.drop_table('agent_activities')

    # 恢复枚举类型（简化处理，实际 downgrade 很少使用）
    accountstatus = postgresql.ENUM('active', 'inactive', 'expired', 'error', name='accountstatus', create_type=False)
    accountstatus.create(op.get_bind(), checkfirst=True)
    op.alter_column('platform_accounts', 'status', type_=accountstatus, postgresql_using='status::accountstatus')

    publishtype = postgresql.ENUM('create_book', 'publish_chapter', 'batch_publish', name='publishtype', create_type=False)
    publishtype.create(op.get_bind(), checkfirst=True)
    op.alter_column('publish_tasks', 'publish_type', type_=publishtype, postgresql_using='publish_type::publishtype')

    publishtaskstatus = postgresql.ENUM('pending', 'running', 'completed', 'failed', 'cancelled', name='publishtaskstatus', create_type=False)
    publishtaskstatus.create(op.get_bind(), checkfirst=True)
    op.alter_column('publish_tasks', 'status', type_=publishtaskstatus, postgresql_using='status::publishtaskstatus')

    publishstatus = postgresql.ENUM('pending', 'publishing', 'published', 'failed', name='publishstatus', create_type=False)
    publishstatus.create(op.get_bind(), checkfirst=True)
    op.alter_column('chapter_publishes', 'status', type_=publishstatus, postgresql_using='status::publishstatus')

    # 移除缺失列
    op.drop_column('plot_outlines', 'main_plot_detailed')
