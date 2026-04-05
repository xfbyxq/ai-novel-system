"""修订计划与记忆模型单元测试.

测试 revision_plan.py 和 hindsight_memory.py 中的数据模型.
"""

from uuid import uuid4


class TestRevisionPlanEnums:
    """RevisionPlan 相关枚举测试."""

    def test_revision_plan_status_enum_values(self):
        """测试 RevisionPlanStatus 枚举值."""
        from core.models.revision_plan import RevisionPlanStatus

        assert RevisionPlanStatus.pending.value == "pending"
        assert RevisionPlanStatus.confirmed.value == "confirmed"
        assert RevisionPlanStatus.executed.value == "executed"
        assert RevisionPlanStatus.rejected.value == "rejected"

    def test_revision_target_type_enum_values(self):
        """测试 RevisionTargetType 枚举值."""
        from core.models.revision_plan import RevisionTargetType

        assert RevisionTargetType.character.value == "character"
        assert RevisionTargetType.chapter.value == "chapter"
        assert RevisionTargetType.world_setting.value == "world_setting"
        assert RevisionTargetType.outline.value == "outline"
        assert RevisionTargetType.plot.value == "plot"


class TestRevisionPlanModel:
    """RevisionPlan 模型测试."""

    def test_revision_plan_model_columns(self):
        """测试 RevisionPlan 模型列."""
        from core.models.revision_plan import RevisionPlan

        columns = [c.name for c in RevisionPlan.__table__.columns]
        required_columns = [
            "id",
            "novel_id",
            "feedback_text",
            "understood_intent",
            "confidence",
            "targets",
            "proposed_changes",
            "impact_assessment",
            "status",
            "user_modifications",
            "confirmed_at",
            "executed_at",
            "created_at",
            "updated_at",
        ]
        for col in required_columns:
            assert col in columns, f"Missing column: {col}"

    def test_revision_plan_model_creation(self):
        """测试 RevisionPlan 模型创建."""
        from core.models.revision_plan import RevisionPlan, RevisionPlanStatus, RevisionTargetType

        novel_id = uuid4()
        plan = RevisionPlan(
            id=uuid4(),
            novel_id=novel_id,
            feedback_text="第5章张三的性格不一致",
            understood_intent="修正角色性格一致性",
            confidence=0.85,
            targets=[
                {
                    "type": RevisionTargetType.character.value,
                    "target_id": str(uuid4()),
                    "target_name": "张三",
                    "field": "personality",
                    "current_value": "冲动",
                    "issue_description": "第5章性格表现与第3章设定不一致",
                }
            ],
            proposed_changes=[
                {
                    "target_type": RevisionTargetType.character.value,
                    "target_id": str(uuid4()),
                    "field": "personality",
                    "old_value": "冲动",
                    "new_value": "稳重内敛",
                    "reasoning": "保持角色设定一致性",
                }
            ],
            impact_assessment={
                "affected_chapters": [3, 5],
                "affected_characters": [str(uuid4())],
            },
            status=RevisionPlanStatus.pending.value,
        )

        assert plan.novel_id == novel_id
        assert plan.feedback_text == "第5章张三的性格不一致"
        assert plan.confidence == 0.85
        assert plan.status == "pending"
        assert len(plan.targets) == 1
        assert len(plan.proposed_changes) == 1

    def test_revision_plan_to_dict(self):
        """测试 RevisionPlan 转换为字典."""
        from core.models.revision_plan import RevisionPlan

        plan = RevisionPlan(
            id=uuid4(),
            novel_id=uuid4(),
            feedback_text="测试反馈",
        )

        result = plan.to_dict()
        assert "id" in result
        assert "novel_id" in result
        assert "feedback_text" in result
        assert result["feedback_text"] == "测试反馈"


class TestHindsightExperienceModel:
    """HindsightExperience 模型测试."""

    def test_hindsight_experience_model_columns(self):
        """测试 HindsightExperience 模型列."""
        from core.models.hindsight_memory import HindsightExperience

        columns = [c.name for c in HindsightExperience.__table__.columns]
        required_columns = [
            "id",
            "novel_id",
            "revision_plan_id",
            "task_type",
            "chapter_number",
            "agent_name",
            "user_satisfaction",
            "initial_goal",
            "initial_plan",
            "actual_result",
            "outcome_score",
            "deviations",
            "deviation_reasons",
            "lessons_learned",
            "successful_strategies",
            "failed_strategies",
            "recurring_pattern",
            "pattern_confidence",
            "improvement_suggestions",
            "is_archived",
            "created_at",
            "updated_at",
        ]
        for col in required_columns:
            assert col in columns, f"Missing column: {col}"

    def test_hindsight_experience_model_creation(self):
        """测试 HindsightExperience 模型创建."""
        from core.models.hindsight_memory import HindsightExperience, TaskType

        novel_id = uuid4()
        plan_id = uuid4()
        experience = HindsightExperience(
            id=uuid4(),
            novel_id=novel_id,
            revision_plan_id=plan_id,
            task_type=TaskType.writing.value,
            chapter_number=5,
            agent_name="writer",
            user_satisfaction=8.0,
            initial_goal="保持角色性格一致性",
            initial_plan={"strategy": "参考第3章设定"},
            actual_result="角色性格已统一",
            outcome_score=8.5,
            deviations=["轻微调整对话风格"],
            deviation_reasons=["根据用户反馈优化"],
            lessons_learned=["写作时需要参考前文角色设定"],
            successful_strategies=["跨章节引用法"],
            failed_strategies=["仅依赖当前章节内容"],
            recurring_pattern="character_inconsistency",
            pattern_confidence=0.75,
        )

        assert experience.novel_id == novel_id
        assert experience.task_type == "writing"
        assert experience.chapter_number == 5
        assert experience.outcome_score == 8.5

    def test_hindsight_experience_to_dict(self):
        """测试 HindsightExperience 转换为字典."""
        from core.models.hindsight_memory import HindsightExperience

        experience = HindsightExperience(
            id=uuid4(),
            novel_id=uuid4(),
            task_type="writing",
        )

        result = experience.to_dict()
        assert "id" in result
        assert "task_type" in result


class TestStrategyEffectivenessModel:
    """StrategyEffectiveness 模型测试."""

    def test_strategy_effectiveness_model_columns(self):
        """测试 StrategyEffectiveness 模型列."""
        from core.models.hindsight_memory import StrategyEffectiveness

        columns = [c.name for c in StrategyEffectiveness.__table__.columns]
        required_columns = [
            "id",
            "novel_id",
            "strategy_name",
            "strategy_type",
            "target_dimension",
            "application_count",
            "success_count",
            "avg_effectiveness",
            "recent_results",
            "trend",
            "last_applied_chapter",
            "last_applied_at",
            "created_at",
            "updated_at",
        ]
        for col in required_columns:
            assert col in columns, f"Missing column: {col}"

    def test_strategy_effectiveness_model_creation(self):
        """测试 StrategyEffectiveness 模型创建."""
        from core.models.hindsight_memory import StrategyEffectiveness, StrategyTrend

        novel_id = uuid4()
        strategy = StrategyEffectiveness(
            id=uuid4(),
            novel_id=novel_id,
            strategy_name="cross_chapter_reference",
            strategy_type="writing",
            target_dimension="character_consistency",
            application_count=5,
            success_count=4,
            avg_effectiveness=0.8,
            recent_results=[0.85, 0.75, 0.8, 0.78, 0.82],
            trend=StrategyTrend.stable.value,
            last_applied_chapter=5,
        )

        assert strategy.novel_id == novel_id
        assert strategy.strategy_name == "cross_chapter_reference"
        assert strategy.avg_effectiveness == 0.8
        assert strategy.trend == "stable"

    def test_strategy_effectiveness_to_dict(self):
        """测试 StrategyEffectiveness 转换为字典."""
        from core.models.hindsight_memory import StrategyEffectiveness

        strategy = StrategyEffectiveness(
            id=uuid4(),
            novel_id=uuid4(),
            strategy_name="test",
        )

        result = strategy.to_dict()
        assert "id" in result
        assert "strategy_name" in result


class TestUserPreferenceModel:
    """UserPreference 模型测试."""

    def test_user_preference_model_columns(self):
        """测试 UserPreference 模型列."""
        from core.models.hindsight_memory import UserPreference

        columns = [c.name for c in UserPreference.__table__.columns]
        required_columns = [
            "id",
            "user_id",
            "novel_id",
            "preference_type",
            "preference_key",
            "preference_value",
            "confidence",
            "source",
            "times_activated",
            "last_activated_at",
            "created_at",
            "updated_at",
        ]
        for col in required_columns:
            assert col in columns, f"Missing column: {col}"

    def test_user_preference_model_creation(self):
        """测试 UserPreference 模型创建."""
        from core.models.hindsight_memory import UserPreference

        user_id = "test_user_123"
        novel_id = uuid4()
        preference = UserPreference(
            id=uuid4(),
            user_id=user_id,
            novel_id=novel_id,
            preference_type="writing_style",
            preference_key="dialogue_ratio",
            preference_value={"min": 0.2, "max": 0.4},
            confidence=0.9,
            source="explicit",
            times_activated=3,
        )

        assert preference.user_id == user_id
        assert preference.novel_id == novel_id
        assert preference.preference_type == "writing_style"
        assert preference.confidence == 0.9
        assert preference.times_activated == 3

    def test_user_preference_to_dict(self):
        """测试 UserPreference 转换为字典."""
        from core.models.hindsight_memory import UserPreference

        preference = UserPreference(
            id=uuid4(),
            user_id="test",
            preference_type="test",
            preference_key="key",
        )

        result = preference.to_dict()
        assert "id" in result
        assert "user_id" in result


class TestHindsightEnums:
    """Hindsight 记忆相关枚举测试."""

    def test_task_type_enum_values(self):
        """测试 Hindsight TaskType 枚举值."""
        from core.models.hindsight_memory import TaskType

        assert TaskType.planning.value == "planning"
        assert TaskType.writing.value == "writing"
        assert TaskType.revision.value == "revision"

    def test_strategy_trend_enum_values(self):
        """测试 StrategyTrend 枚举值."""
        from core.models.hindsight_memory import StrategyTrend

        assert StrategyTrend.improving.value == "improving"
        assert StrategyTrend.declining.value == "declining"
        assert StrategyTrend.stable.value == "stable"
