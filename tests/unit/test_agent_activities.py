"""Agent 活动记录功能单元测试.

测试 AgentActivity 模型和 AgentActivityRecorder 服务的功能.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


class TestAgentActivityModel:
    """AgentActivity 模型测试."""

    def test_from_activity_with_all_fields(self):
        """测试从完整数据创建 AgentActivity."""
        from core.models.agent_activity import AgentActivity

        novel_id = uuid4()
        task_id = uuid4()

        activity_data = {
            "novel_id": novel_id,
            "task_id": task_id,
            "agent_name": "测试 Agent",
            "agent_role": "测试角色",
            "activity_type": "planning_topic_analysis",
            "phase": "planning",
            "step_number": 1,
            "iteration_number": None,
            "input_data": {"genre": "科幻"},
            "output_data": {"result": "测试成功"},
            "raw_output": "原始输出内容",
            "metadata": {"review_score": 8.5, "suggestions": ["建议 1", "建议 2"]},
            "prompt_tokens": 100,
            "completion_tokens": 200,
            "total_tokens": 300,
            "cost": 0.0012,
            "status": "success",
            "error_message": None,
            "retry_count": 0,
        }

        activity = AgentActivity.from_activity(activity_data)

        assert activity.agent_name == "测试 Agent"
        assert activity.activity_type == "planning_topic_analysis"
        assert activity.total_tokens == 300
        assert activity.status == "success"

    def test_from_activity_with_minimal_fields(self):
        """测试从最小数据创建 AgentActivity."""
        from core.models.agent_activity import AgentActivity

        novel_id = uuid4()
        task_id = uuid4()

        activity_data = {
            "novel_id": novel_id,
            "task_id": task_id,
            "agent_name": "测试 Agent",
            "activity_type": "test",
        }

        activity = AgentActivity.from_activity(activity_data)

        assert activity.agent_name == "测试 Agent"
        assert activity.activity_type == "test"
        assert activity.input_data == {}
        assert activity.output_data == {}

    def test_to_dict(self):
        """测试转换为字典."""
        from core.models.agent_activity import AgentActivity

        novel_id = uuid4()
        task_id = uuid4()

        activity_data = {
            "novel_id": novel_id,
            "task_id": task_id,
            "agent_name": "测试 Agent",
            "activity_type": "test",
            "input_data": {"key": "value"},
            "output_data": {"result": "ok"},
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cost": 0.001,
        }

        activity = AgentActivity.from_activity(activity_data)
        result = activity.to_dict()

        assert "agent_name" in result
        assert "input_data" in result
        assert result["total_tokens"] == 150


class TestAgentActivityRecorder:
    """AgentActivityRecorder 服务测试."""

    @pytest.fixture
    def mock_db_session(self):
        """创建 Mock 数据库会话."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.add = MagicMock()
        return mock_session

    @pytest.fixture
    def recorder(self, mock_db_session):
        """创建 AgentActivityRecorder 实例."""
        from backend.services.agent_activity_recorder import AgentActivityRecorder

        return AgentActivityRecorder(mock_db_session)

    @pytest.mark.asyncio
    async def test_record_activity_basic(self, recorder, mock_db_session):
        """测试基本活动记录."""
        novel_id = uuid4()
        task_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result

        activity = await recorder.record_activity(
            novel_id=novel_id,
            task_id=task_id,
            agent_name="测试 Agent",
            activity_type="test_activity",
        )

        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_planning_activity(self, recorder, mock_db_session):
        """测试记录企划活动."""
        novel_id = uuid4()
        task_id = uuid4()

        activity = await recorder.record_planning_activity(
            novel_id=novel_id,
            task_id=task_id,
            agent_name="主题分析师",
            agent_role="市场趋势分析",
            activity_subtype="topic_analysis",
            input_data={"genre": "玄幻"},
            output_data={"recommendation": "东方玄幻"},
            total_tokens=500,
            cost=0.002,
        )

        mock_db_session.add.assert_called_once()
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.agent_name == "主题分析师"
        assert call_args.activity_type == "planning_topic_analysis"
        assert call_args.phase == "planning"

    @pytest.mark.asyncio
    async def test_record_review_activity(self, recorder, mock_db_session):
        """测试记录审查活动."""
        novel_id = uuid4()
        task_id = uuid4()

        activity = await recorder.record_review_activity(
            novel_id=novel_id,
            task_id=task_id,
            agent_name="大纲审查员",
            agent_role="情节架构审查",
            review_type="plot_review",
            iteration=1,
            score=7.5,
            input_data={"outline": "测试大纲"},
            output_data={"feedback": "需要改进"},
            suggestions=["增加冲突", "加快节奏"],
        )

        mock_db_session.add.assert_called_once()
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.agent_name == "大纲审查员"
        assert call_args.activity_type == "review_plot_review"
        assert call_args.iteration_number == 1

    @pytest.mark.asyncio
    async def test_record_voting_activity(self, recorder, mock_db_session):
        """测试记录投票活动."""
        novel_id = uuid4()
        task_id = uuid4()

        activity = await recorder.record_voting_activity(
            novel_id=novel_id,
            task_id=task_id,
            agent_name="投票决策者",
            agent_role="最终决策",
            topic="剧情走向",
            chosen_option="方案 A",
            reasoning="方案 A 更符合设定",
            confidence=0.85,
        )

        mock_db_session.add.assert_called_once()
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.agent_name == "投票决策者"
        assert call_args.activity_type == "voting_vote_cast"

    @pytest.mark.asyncio
    async def test_record_writing_activity(self, recorder, mock_db_session):
        """测试记录写作活动."""
        novel_id = uuid4()
        task_id = uuid4()

        activity = await recorder.record_writing_activity(
            novel_id=novel_id,
            task_id=task_id,
            agent_name="章节作家",
            agent_role="内容创作",
            activity_subtype="draft_writing",
            chapter_number=5,
            input_data={"outline": "章节大纲"},
            output_data={"content": "章节内容"},
        )

        mock_db_session.add.assert_called_once()
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.agent_name == "章节作家"
        assert call_args.activity_type == "writing_draft_writing"
        assert call_args.phase == "writing"

    @pytest.mark.asyncio
    async def test_get_activities_by_task(self, recorder, mock_db_session):
        """测试按任务查询活动."""
        from core.models.agent_activity import AgentActivity

        task_id = uuid4()
        novel_id = uuid4()

        mock_activity1 = AgentActivity.from_activity(
            {
                "novel_id": novel_id,
                "task_id": task_id,
                "agent_name": "Agent-1",
                "activity_type": "test",
            }
        )
        mock_activity2 = AgentActivity.from_activity(
            {
                "novel_id": novel_id,
                "task_id": task_id,
                "agent_name": "Agent-2",
                "activity_type": "test",
            }
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_activity1, mock_activity2]
        mock_db_session.execute.return_value = mock_result

        activities = await recorder.get_activities_by_task(task_id)

        assert len(activities) == 2
        assert activities[0].agent_name == "Agent-1"
        assert activities[1].agent_name == "Agent-2"

    @pytest.mark.asyncio
    async def test_get_activities_by_novel(self, recorder, mock_db_session):
        """测试按小说查询活动."""
        from core.models.agent_activity import AgentActivity

        novel_id = uuid4()
        task_id = uuid4()

        mock_activity = AgentActivity.from_activity(
            {
                "novel_id": novel_id,
                "task_id": task_id,
                "agent_name": "测试 Agent",
                "activity_type": "test",
            }
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_activity]
        mock_db_session.execute.return_value = mock_result

        activities = await recorder.get_activities_by_novel(novel_id)

        assert len(activities) == 1

    @pytest.mark.asyncio
    async def test_get_activities_by_agent(self, recorder, mock_db_session):
        """测试按 Agent 查询活动."""
        from core.models.agent_activity import AgentActivity

        novel_id = uuid4()
        task_id = uuid4()

        mock_activity = AgentActivity.from_activity(
            {
                "novel_id": novel_id,
                "task_id": task_id,
                "agent_name": "测试 Agent",
                "activity_type": "test",
            }
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_activity]
        mock_db_session.execute.return_value = mock_result

        activities = await recorder.get_activities_by_agent("测试 Agent")

        assert len(activities) == 1
        assert activities[0].agent_name == "测试 Agent"

    @pytest.mark.asyncio
    async def test_get_activity_summary(self, recorder, mock_db_session):
        """测试获取活动摘要."""
        from core.models.agent_activity import AgentActivity

        novel_id = uuid4()
        task_id = uuid4()

        mock_activities = [
            AgentActivity.from_activity(
                {
                    "novel_id": novel_id,
                    "task_id": task_id,
                    "agent_name": f"Agent-{i % 2}",
                    "activity_type": "test",
                    "total_tokens": 100 * (i + 1),
                    "cost": 0.001 * (i + 1),
                }
            )
            for i in range(5)
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_activities
        mock_db_session.execute.return_value = mock_result

        summary = await recorder.get_activity_summary(task_id)

        assert summary["total_activities"] == 5
        assert summary["total_tokens"] == 1500
        assert "Agent-0" in summary["agent_statistics"]
        assert "Agent-1" in summary["agent_statistics"]

    @pytest.mark.asyncio
    async def test_get_activity_summary_empty(self, recorder, mock_db_session):
        """测试空任务摘要."""
        task_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        summary = await recorder.get_activity_summary(task_id)

        assert summary["total_activities"] == 0

    @pytest.mark.asyncio
    async def test_get_agent_activity_recorder(self, mock_db_session):
        """测试获取记录器实例."""
        from backend.services.agent_activity_recorder import get_agent_activity_recorder

        recorder = get_agent_activity_recorder(mock_db_session)

        assert recorder.db is mock_db_session


class TestAgentActivityRecorderEdgeCases:
    """AgentActivityRecorder 边界情况测试."""

    @pytest.fixture
    def mock_db_session(self):
        """创建 Mock 数据库会话."""
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.add = MagicMock()
        return mock_session

    @pytest.fixture
    def recorder(self, mock_db_session):
        """创建 AgentActivityRecorder 实例."""
        from backend.services.agent_activity_recorder import AgentActivityRecorder

        return AgentActivityRecorder(mock_db_session)

    @pytest.mark.asyncio
    async def test_record_activity_with_all_metadata(self, recorder, mock_db_session):
        """测试带完整元数据的活动记录."""
        novel_id = uuid4()
        task_id = uuid4()

        await recorder.record_activity(
            novel_id=novel_id,
            task_id=task_id,
            agent_name="测试 Agent",
            activity_type="test",
            metadata={
                "review_score": 8.5,
                "iteration": 2,
                "custom_field": "自定义值",
            },
        )

        mock_db_session.add.assert_called_once()
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.activity_metadata["review_score"] == 8.5
        assert call_args.activity_metadata["custom_field"] == "自定义值"

    @pytest.mark.asyncio
    async def test_record_activity_with_error(self, recorder, mock_db_session):
        """测试记录失败活动."""
        novel_id = uuid4()
        task_id = uuid4()

        await recorder.record_activity(
            novel_id=novel_id,
            task_id=task_id,
            agent_name="测试 Agent",
            activity_type="test",
            status="failed",
            error_message="测试错误信息",
            retry_count=3,
        )

        mock_db_session.add.assert_called_once()
        call_args = mock_db_session.add.call_args[0][0]
        assert call_args.status == "failed"
        assert call_args.error_message == "测试错误信息"
        assert call_args.retry_count == 3

    @pytest.mark.asyncio
    async def test_get_activities_with_limit(self, recorder, mock_db_session):
        """测试带限制的查询."""
        from core.models.agent_activity import AgentActivity

        task_id = uuid4()
        novel_id = uuid4()

        mock_activities = [
            AgentActivity.from_activity(
                {
                    "novel_id": novel_id,
                    "task_id": task_id,
                    "agent_name": f"Agent-{i}",
                    "activity_type": "test",
                }
            )
            for i in range(10)
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_activities[:5]
        mock_db_session.execute.return_value = mock_result

        activities = await recorder.get_activities_by_task(task_id, limit=5)

        assert len(activities) == 5

    @pytest.mark.asyncio
    async def test_get_activities_by_agent_with_novel_filter(self, recorder, mock_db_session):
        """测试按 Agent 和小说过滤查询."""
        novel_id = uuid4()
        task_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        await recorder.get_activities_by_agent("测试 Agent", novel_id=novel_id)

        assert mock_db_session.execute.called
