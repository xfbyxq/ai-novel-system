"""add_revision_and_memory_tables

Revision ID: add_revision_and_memory_tables
Revises: add_chapter_outline_columns
Create Date: 2026-04-04 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_revision_and_memory_tables"
down_revision: Union[str, None] = "add_chapter_outline_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==================== Revision Plans ====================
    op.create_table(
        "revision_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("novel_id", sa.UUID(), nullable=False),
        sa.Column("feedback_text", sa.Text(), nullable=False),
        sa.Column("understood_intent", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("targets", sa.JSON(), nullable=True),
        sa.Column("proposed_changes", sa.JSON(), nullable=True),
        sa.Column("impact_assessment", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("user_modifications", sa.JSON(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_revision_plans_novel_id", "revision_plans", ["novel_id"])
    op.create_index("idx_revision_plans_status", "revision_plans", ["status"])
    op.create_index("idx_revision_plans_created_at", "revision_plans", ["created_at"])

    # ==================== Hindsight Experiences ====================
    op.create_table(
        "hindsight_experiences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("novel_id", sa.UUID(), nullable=False),
        sa.Column("revision_plan_id", sa.UUID(), nullable=True),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=True),
        sa.Column("agent_name", sa.String(length=100), nullable=True),
        sa.Column("original_feedback", sa.Text(), nullable=True),
        sa.Column("user_satisfaction", sa.Float(), nullable=True),
        sa.Column("initial_goal", sa.Text(), nullable=True),
        sa.Column("initial_plan", sa.JSON(), nullable=True),
        sa.Column("actual_result", sa.Text(), nullable=True),
        sa.Column("outcome_score", sa.Float(), nullable=True),
        sa.Column("deviations", sa.JSON(), nullable=True),
        sa.Column("deviation_reasons", sa.JSON(), nullable=True),
        sa.Column("lessons_learned", sa.JSON(), nullable=True),
        sa.Column("successful_strategies", sa.JSON(), nullable=True),
        sa.Column("failed_strategies", sa.JSON(), nullable=True),
        sa.Column("recurring_pattern", sa.String(length=200), nullable=True),
        sa.Column("pattern_confidence", sa.Float(), nullable=True),
        sa.Column("improvement_suggestions", sa.JSON(), nullable=True),
        sa.Column("is_archived", sa.Integer(), nullable=True, default=0),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_hindsight_novel_id", "hindsight_experiences", ["novel_id"])
    op.create_index("idx_hindsight_task_type", "hindsight_experiences", ["task_type"])
    op.create_index("idx_hindsight_chapter", "hindsight_experiences", ["chapter_number"])
    op.create_index("idx_hindsight_created_at", "hindsight_experiences", ["created_at"])

    # ==================== Strategy Effectiveness ====================
    op.create_table(
        "strategy_effectiveness",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("novel_id", sa.UUID(), nullable=False),
        sa.Column("strategy_name", sa.String(length=100), nullable=False),
        sa.Column("strategy_type", sa.String(length=50), nullable=True),
        sa.Column("target_dimension", sa.String(length=50), nullable=True),
        sa.Column("application_count", sa.Integer(), nullable=True, default=0),
        sa.Column("success_count", sa.Integer(), nullable=True, default=0),
        sa.Column("avg_effectiveness", sa.Float(), nullable=True, default=0.5),
        sa.Column("recent_results", sa.JSON(), nullable=True),
        sa.Column("trend", sa.String(length=20), nullable=True),
        sa.Column("last_applied_chapter", sa.Integer(), nullable=True),
        sa.Column("last_applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_strategy_novel_id", "strategy_effectiveness", ["novel_id"])
    op.create_index("idx_strategy_dimension", "strategy_effectiveness", ["target_dimension"])
    op.create_index("idx_strategy_name", "strategy_effectiveness", ["strategy_name"])

    # ==================== User Preferences ====================
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("novel_id", sa.UUID(), nullable=True),
        sa.Column("preference_type", sa.String(length=50), nullable=False),
        sa.Column("preference_key", sa.String(length=200), nullable=False),
        sa.Column("preference_value", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True, default=0.5),
        sa.Column("source", sa.String(length=20), nullable=True),
        sa.Column("times_activated", sa.Integer(), nullable=True, default=0),
        sa.Column("last_activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_user_pref_user_id", "user_preferences", ["user_id"])
    op.create_index("idx_user_pref_novel_id", "user_preferences", ["novel_id"])
    op.create_index("idx_user_pref_type", "user_preferences", ["preference_type"])


def downgrade() -> None:
    op.drop_table("user_preferences")
    op.drop_table("strategy_effectiveness")
    op.drop_table("hindsight_experiences")
    op.drop_table("revision_plans")
