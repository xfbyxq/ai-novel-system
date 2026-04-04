"""Hindsight事后回顾服务单元测试.

测试 hindsight_service.py 中的服务.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


class TestHindsightService:
    """HindsightService 测试."""

    @pytest.fixture
    def mock_db_session(self):
        """模拟数据库会话."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_db_session):
        """创建服务实例."""
        from backend.services.hindsight_service import HindsightService

        return HindsightService(db=mock_db_session, llm=None)

    @pytest.mark.asyncio
    async def test_execute_review_creates_experience(self, service, mock_db_session):
        """测试执行回顾创建经验记录."""
        # Mock _detect_pattern 返回 None
        service._detect_pattern = AsyncMock(return_value=None)

        result = await service.execute_review(
            novel_id=str(uuid4()),
            task_type="writing",
            initial_goal="测试目标",
            initial_plan={"test": "plan"},
            actual_result="测试结果",
            outcome_score=8.0,
        )

        assert result is not None
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_execute_review_with_feedback(self, service, mock_db_session):
        """测试带用户反馈的回顾."""
        # Mock _detect_pattern 返回 None
        service._detect_pattern = AsyncMock(return_value=None)

        result = await service.execute_review(
            novel_id=str(uuid4()),
            task_type="revision",
            initial_goal="修正角色性格",
            actual_result="完成修正",
            outcome_score=7.5,
            original_feedback="角色性格不一致",
            revision_plan_id=str(uuid4()),
        )

        assert result.original_feedback == "角色性格不一致"
        assert result.revision_plan_id is not None

    @pytest.mark.asyncio
    async def test_simple_analyze_high_score(self, service):
        """测试高分简化分析."""
        result = service._simple_analyze(8.5)

        assert "lessons" in result
        assert result["lessons"] == ["本次任务完成良好"]
        assert len(result["deviations"]) == 0

    @pytest.mark.asyncio
    async def test_simple_analyze_medium_score(self, service):
        """测试中等分简化分析."""
        result = service._simple_analyze(6.5)

        assert "lessons" in result
        assert len(result["deviations"]) > 0

    @pytest.mark.asyncio
    async def test_simple_analyze_low_score(self, service):
        """测试低分简化分析."""
        result = service._simple_analyze(4.0)

        assert "lessons" in result
        assert len(result["deviations"]) > 0


class TestStrategyTrendCalculation:
    """策略趋势计算测试."""

    def test_calculate_improving_trend(self):
        """测试上升趋势计算."""
        from backend.services.hindsight_service import HindsightService

        # _calculate_trend 是实例方法
        service = HindsightService(db=MagicMock())
        recent_results = [0.6, 0.7, 0.8, 0.9]

        trend = service._calculate_trend(recent_results)
        assert trend == "improving"

    def test_calculate_declining_trend(self):
        """测试下降趋势计算."""
        from backend.services.hindsight_service import HindsightService

        service = HindsightService(db=MagicMock())
        recent_results = [0.9, 0.8, 0.7, 0.6]

        trend = service._calculate_trend(recent_results)
        assert trend == "declining"

    def test_calculate_stable_trend(self):
        """测试稳定趋势计算."""
        from backend.services.hindsight_service import HindsightService

        service = HindsightService(db=MagicMock())
        recent_results = [0.75, 0.78, 0.76, 0.77]

        trend = service._calculate_trend(recent_results)
        assert trend == "stable"

    def test_calculate_trend_with_single_result(self):
        """测试单个结果的稳定趋势."""
        from backend.services.hindsight_service import HindsightService

        service = HindsightService(db=MagicMock())
        recent_results = [0.8]

        trend = service._calculate_trend(recent_results)
        assert trend == "stable"


class TestStrategyTypeInference:
    """策略类型推断测试."""

    def test_infer_dialogue_strategy(self):
        """测试推断对话策略."""
        from backend.services.hindsight_service import HindsightService

        service = HindsightService(db=MagicMock())

        result = service._infer_strategy_type("增加对话描写")
        assert result == "description"

        result = service._infer_strategy_type("语言风格调整")
        assert result == "description"

    def test_infer_pacing_strategy(self):
        """测试推断节奏策略."""
        from backend.services.hindsight_service import HindsightService

        service = HindsightService(db=MagicMock())

        result = service._infer_strategy_type("加快节奏")
        assert result == "pacing"

        result = service._infer_strategy_type("场景转换优化")
        assert result == "pacing"

    def test_infer_revision_strategy(self):
        """测试推断修订策略."""
        from backend.services.hindsight_service import HindsightService

        service = HindsightService(db=MagicMock())

        result = service._infer_strategy_type("修订角色设定")
        assert result == "revision"

        result = service._infer_strategy_type("修改情节")
        assert result == "revision"


class TestDimensionInference:
    """维度推断测试."""

    def test_infer_revision_dimension(self):
        """测试推断修订维度."""
        from backend.services.hindsight_service import HindsightService

        service = HindsightService(db=MagicMock())

        result = service._infer_dimension("revision")
        assert result == "一致性"

    def test_infer_writing_dimension(self):
        """测试推断写作维度."""
        from backend.services.hindsight_service import HindsightService

        service = HindsightService(db=MagicMock())

        result = service._infer_dimension("writing")
        assert result == "质量"

    def test_infer_planning_dimension(self):
        """测试推断企划维度."""
        from backend.services.hindsight_service import HindsightService

        service = HindsightService(db=MagicMock())

        result = service._infer_dimension("planning")
        assert result == "整体"


class TestAnalyzeOutcome:
    """结果分析测试."""

    @pytest.mark.asyncio
    async def test_analyze_outcome_without_llm(self):
        """测试无LLM时的简化分析."""
        from backend.services.hindsight_service import HindsightService

        service = HindsightService(db=MagicMock(), llm=None)

        result = await service._analyze_outcome(
            initial_goal="测试目标",
            initial_plan={"test": "plan"},
            actual_result="测试结果",
            outcome_score=8.0,
        )

        assert "lessons" in result
        assert "deviations" in result
        assert "successful_strategies" in result


class TestRecordStrategyResult:
    """记录策略结果测试."""

    @pytest.fixture
    def mock_db_session(self):
        """模拟数据库会话."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_record_strategy_result_creates_new(self, mock_db_session):
        """测试记录新策略结果."""
        from backend.services.hindsight_service import HindsightService

        # Mock 查询返回None（新建）
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = HindsightService(db=mock_db_session)

        result = await service.record_strategy_result(
            novel_id=str(uuid4()),
            strategy_name="test_strategy",
            strategy_type="description",
            target_dimension="一致性",
            effectiveness_score=0.8,
        )

        assert result is not None
        mock_db_session.add.assert_called()


class TestGetApplicableLessons:
    """获取适用经验测试."""

    @pytest.fixture
    def mock_db_session(self):
        """模拟数据库会话."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_get_applicable_lessons_formats_output(self, mock_db_session):
        """测试获取经验格式化输出."""
        from backend.services.hindsight_service import HindsightService

        # Mock 查询结果
        mock_exp = MagicMock()
        mock_exp.lessons_learned = ["保持角色一致性很重要"]
        mock_exp.recurring_pattern = "character_inconsistency"
        mock_exp.pattern_confidence = 0.8
        mock_exp.improvement_suggestions = ["建议每次写作前回顾角色设定"]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_exp]
        mock_db_session.execute.return_value = mock_result

        service = HindsightService(db=mock_db_session)

        lessons = await service.get_applicable_lessons(
            novel_id=str(uuid4()),
            task_type="writing",
        )

        assert isinstance(lessons, list)
        assert len(lessons) > 0


class TestUserPreferenceManagement:
    """用户偏好管理测试."""

    @pytest.fixture
    def mock_db_session(self):
        """模拟数据库会话."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_record_user_preference_creates_new(self, mock_db_session):
        """测试记录新用户偏好."""
        from backend.services.hindsight_service import HindsightService

        # Mock 无现有偏好
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = HindsightService(db=mock_db_session)

        result = await service.record_user_preference(
            user_id="test_user",
            preference_type="writing_style",
            preference_key="dialogue_ratio",
            preference_value={"min": 0.2, "max": 0.4},
            source="explicit",
            confidence=0.9,
        )

        assert result is not None
        mock_db_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_get_user_preferences_filters_by_confidence(self, mock_db_session):
        """测试按置信度过滤偏好."""
        from backend.services.hindsight_service import HindsightService

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        service = HindsightService(db=mock_db_session)

        preferences = await service.get_user_preferences(
            user_id="test_user",
            min_confidence=0.7,
        )

        assert isinstance(preferences, list)
