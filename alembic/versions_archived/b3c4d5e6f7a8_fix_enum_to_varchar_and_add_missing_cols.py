"""fix: convert enum columns to varchar and add missing columns.

将所有 PostgreSQL 原生枚举类型列转换为 varchar，以匹配 ORM 模型定义。
同时添加 ORM 模型中定义但数据库缺失的列。

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-20 14:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """将枚举类型列转换为 varchar，添加缺失列，修复类型不匹配."""

    # ========== 1. novels 表 ==========
    # novels.status: novelstatus enum -> varchar(50)
    op.alter_column(
        "novels",
        "status",
        type_=sa.String(50),
        existing_type=postgresql.ENUM(
            "planning", "writing", "completed", "published", name="novelstatus"
        ),
        existing_nullable=True,
        postgresql_using="status::text",
    )

    # novels.length_type: novellengthtype enum -> varchar(50)
    op.alter_column(
        "novels",
        "length_type",
        type_=sa.String(50),
        existing_type=postgresql.ENUM(
            "short", "medium", "long", name="novellengthtype"
        ),
        existing_nullable=False,
        existing_server_default=sa.text("'medium'::novellengthtype"),
        server_default="medium",
        postgresql_using="length_type::text",
    )

    # novels.tags: varchar[] (ARRAY) -> JSONB
    op.alter_column(
        "novels",
        "tags",
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_type=postgresql.ARRAY(sa.String()),
        existing_nullable=True,
        postgresql_using="to_jsonb(tags)",
    )

    # novels.chapter_config: 添加缺失列
    op.add_column(
        "novels",
        sa.Column(
            "chapter_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default='{"total_chapters": 6, "min_chapters": 3, "max_chapters": 12, "flexible": true}',
        ),
    )

    # ========== 2. generation_tasks 表 ==========
    # generation_tasks.task_type: tasktype enum -> varchar(50)
    op.alter_column(
        "generation_tasks",
        "task_type",
        type_=sa.String(50),
        existing_type=postgresql.ENUM(
            "planning", "writing", "editing", "batch_writing", name="tasktype"
        ),
        existing_nullable=False,
        postgresql_using="task_type::text",
    )

    # generation_tasks.status: taskstatus enum -> varchar(50)
    op.alter_column(
        "generation_tasks",
        "status",
        type_=sa.String(50),
        existing_type=postgresql.ENUM(
            "pending", "running", "completed", "failed", "cancelled", name="taskstatus"
        ),
        existing_nullable=True,
        postgresql_using="status::text",
    )

    # ========== 3. characters 表 ==========
    # characters.role_type: roletype enum -> varchar(50)
    op.alter_column(
        "characters",
        "role_type",
        type_=sa.String(50),
        existing_type=postgresql.ENUM(
            "protagonist", "supporting", "antagonist", "minor", name="roletype"
        ),
        existing_nullable=True,
        postgresql_using="role_type::text",
    )

    # characters.gender: gender enum -> varchar(20)
    op.alter_column(
        "characters",
        "gender",
        type_=sa.String(20),
        existing_type=postgresql.ENUM("male", "female", "other", name="gender"),
        existing_nullable=True,
        postgresql_using="gender::text",
    )

    # characters.status: characterstatus enum -> varchar(50)
    op.alter_column(
        "characters",
        "status",
        type_=sa.String(50),
        existing_type=postgresql.ENUM(
            "alive", "dead", "unknown", name="characterstatus"
        ),
        existing_nullable=True,
        postgresql_using="status::text",
    )

    # ========== 4. chapters 表 ==========
    # chapters.status: chapterstatus enum -> varchar(50)
    op.alter_column(
        "chapters",
        "status",
        type_=sa.String(50),
        existing_type=postgresql.ENUM(
            "draft", "reviewing", "published", name="chapterstatus"
        ),
        existing_nullable=True,
        postgresql_using="status::text",
    )

    # ========== 5. 清理不再使用的枚举类型 ==========
    op.execute(sa.text("DROP TYPE IF EXISTS novelstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS novellengthtype"))
    op.execute(sa.text("DROP TYPE IF EXISTS tasktype"))
    op.execute(sa.text("DROP TYPE IF EXISTS taskstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS roletype"))
    op.execute(sa.text("DROP TYPE IF EXISTS gender"))
    op.execute(sa.text("DROP TYPE IF EXISTS characterstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS chapterstatus"))


def downgrade() -> None:
    """恢复枚举类型，移除新增列."""
    # 重建枚举类型
    novelstatus = postgresql.ENUM(
        "planning",
        "writing",
        "completed",
        "published",
        name="novelstatus",
        create_type=False,
    )
    novelstatus.create(op.get_bind(), checkfirst=True)

    novellengthtype = postgresql.ENUM(
        "short", "medium", "long", name="novellengthtype", create_type=False
    )
    novellengthtype.create(op.get_bind(), checkfirst=True)

    tasktype = postgresql.ENUM(
        "planning",
        "writing",
        "editing",
        "batch_writing",
        name="tasktype",
        create_type=False,
    )
    tasktype.create(op.get_bind(), checkfirst=True)

    taskstatus = postgresql.ENUM(
        "pending",
        "running",
        "completed",
        "failed",
        "cancelled",
        name="taskstatus",
        create_type=False,
    )
    taskstatus.create(op.get_bind(), checkfirst=True)

    roletype = postgresql.ENUM(
        "protagonist",
        "supporting",
        "antagonist",
        "minor",
        name="roletype",
        create_type=False,
    )
    roletype.create(op.get_bind(), checkfirst=True)

    gender_enum = postgresql.ENUM(
        "male", "female", "other", name="gender", create_type=False
    )
    gender_enum.create(op.get_bind(), checkfirst=True)

    characterstatus = postgresql.ENUM(
        "alive", "dead", "unknown", name="characterstatus", create_type=False
    )
    characterstatus.create(op.get_bind(), checkfirst=True)

    chapterstatus = postgresql.ENUM(
        "draft", "reviewing", "published", name="chapterstatus", create_type=False
    )
    chapterstatus.create(op.get_bind(), checkfirst=True)

    # 恢复列类型
    op.alter_column(
        "chapters",
        "status",
        type_=chapterstatus,
        postgresql_using="status::chapterstatus",
    )
    op.alter_column(
        "characters",
        "status",
        type_=characterstatus,
        postgresql_using="status::characterstatus",
    )
    op.alter_column(
        "characters", "gender", type_=gender_enum, postgresql_using="gender::gender"
    )
    op.alter_column(
        "characters",
        "role_type",
        type_=roletype,
        postgresql_using="role_type::roletype",
    )
    op.alter_column(
        "generation_tasks",
        "status",
        type_=taskstatus,
        postgresql_using="status::taskstatus",
    )
    op.alter_column(
        "generation_tasks",
        "task_type",
        type_=tasktype,
        postgresql_using="task_type::tasktype",
    )
    op.alter_column(
        "novels",
        "tags",
        type_=postgresql.ARRAY(sa.String()),
        postgresql_using="ARRAY(SELECT jsonb_array_elements_text(tags))",
    )
    op.alter_column(
        "novels",
        "length_type",
        type_=novellengthtype,
        postgresql_using="length_type::novellengthtype",
    )
    op.alter_column(
        "novels", "status", type_=novelstatus, postgresql_using="status::novelstatus"
    )

    # 移除新增列
    op.drop_column("novels", "chapter_config")
