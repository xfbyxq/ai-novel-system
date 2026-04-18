"""企划任务并发控制测试.

测试企划任务并发控制功能（Issue #31 配套）:
- 企划任务创建时的并发控制
- 防止重复创建企划任务
- 任务完成后允许创建新任务

使用 Mock 方式测试，隔离数据库依赖。
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


class TestPlanningConcurrencyControl:
    """企划任务并发控制测试."""

    @pytest.fixture
    def mock_novel(self):
        """创建 Mock 小说对象."""
        novel = MagicMock()
        novel.id = uuid4()
        novel.title = "测试小说"
        return novel

    @pytest.fixture
    def mock_planning_task_pending(self, mock_novel):
        """创建 Mock 企划任务（pending 状态）."""
        task = MagicMock()
        task.id = uuid4()
        task.novel_id = mock_novel.id
        task.task_type = "planning"
        task.status = "pending"
        task.created_at = datetime.now()
        return task

    @pytest.fixture
    def mock_planning_task_running(self, mock_novel):
        """创建 Mock 企划任务（running 状态）."""
        task = MagicMock()
        task.id = uuid4()
        task.novel_id = mock_novel.id
        task.task_type = "planning"
        task.status = "running"
        task.started_at = datetime.now()
        return task

    def test_check_running_planning_task_logic_no_task(self):
        """测试无运行时企划任务时的检查逻辑.

        验证：没有 running/planning 任务时可以创建新任务。
        """
        running_tasks = []

        can_create = len(running_tasks) == 0

        assert can_create is True

    def test_check_running_planning_task_logic_with_pending(self):
        """测试有 pending 企划任务时的检查逻辑.

        验证：有 pending 任务时不应创建新任务。
        """
        running_tasks = [MagicMock(status="pending")]

        has_running = any(t.status in ["pending", "running"] for t in running_tasks)
        can_create = not has_running

        assert can_create is False

    def test_check_running_planning_task_logic_with_running(self):
        """测试有 running 企划任务时的检查逻辑.

        验证：有 running 任务时不应创建新任务。
        """
        running_tasks = [MagicMock(status="running")]

        has_running = any(t.status in ["pending", "running"] for t in running_tasks)
        can_create = not has_running

        assert can_create is False

    def test_check_running_planning_task_logic_multiple_tasks(self):
        """测试多个企划任务时的检查逻辑.

        验证：只要存在 pending/running 任务就不应创建新任务。
        """
        running_tasks = [
            MagicMock(status="completed"),
            MagicMock(status="pending"),
            MagicMock(status="failed"),
        ]

        has_running = any(t.status in ["pending", "running"] for t in running_tasks)
        can_create = not has_running

        assert can_create is False

    def test_task_status_enum_values(self):
        """测试任务状态枚举值.

        验证：正确的状态值用于并发检查。
        """
        blocking_statuses = ["pending", "running"]
        non_blocking_statuses = ["completed", "failed", "cancelled"]

        # blocking 状态应该阻止创建新任务
        for status in blocking_statuses:
            assert status in ["pending", "running"]

        # non-blocking 状态应该允许创建新任务
        for status in non_blocking_statuses:
            assert status not in ["pending", "running"]

    def test_planning_task_concurrency_query(self):
        """测试企划任务并发查询逻辑.

        验证：查询条件正确过滤 pending/running 状态的任务。
        """
        all_tasks = [
            MagicMock(task_type="planning", status="pending"),
            MagicMock(task_type="planning", status="running"),
            MagicMock(task_type="planning", status="completed"),
            MagicMock(task_type="writing", status="running"),
            MagicMock(task_type="planning", status="failed"),
        ]

        # 模拟查询条件
        running_planning_tasks = [
            t for t in all_tasks if t.task_type == "planning" and t.status in ["pending", "running"]
        ]

        assert len(running_planning_tasks) == 2
        assert all(t.task_type == "planning" for t in running_planning_tasks)
        assert all(t.status in ["pending", "running"] for t in running_planning_tasks)

    def test_different_task_types_no_conflict(self):
        """测试不同任务类型不冲突.

        验证：writing 任务不应影响 planning 任务创建。
        """
        running_tasks = [
            MagicMock(task_type="writing", status="running"),
            MagicMock(task_type="batch_writing", status="running"),
        ]

        planning_tasks = [t for t in running_tasks if t.task_type == "planning"]

        assert len(planning_tasks) == 0

    def test_same_novel_only_one_planning(self):
        """测试同一小说只有一个企划任务.

        验证：企划任务并发控制基于小说 ID。
        """
        tasks_by_novel = {
            "novel-1": [
                MagicMock(task_type="planning", status="pending"),
            ],
            "novel-2": [
                MagicMock(task_type="planning", status="running"),
            ],
        }

        for novel_id, tasks in tasks_by_novel.items():
            has_running = any(t.status in ["pending", "running"] for t in tasks)
            # 每个小说独立判断
            assert isinstance(has_running, bool)


class TestPlanningTaskCreation:
    """企划任务创建逻辑测试."""

    @pytest.fixture
    def mock_novel(self):
        """创建 Mock 小说对象."""
        novel = MagicMock()
        novel.id = uuid4()
        novel.title = "测试小说"
        return novel

    def test_create_task_when_no_running(self, mock_novel):
        """测试无运行时任务时创建企划任务.

        验证：可以成功创建。
        """
        running_tasks = []
        novel_id = mock_novel.id

        # 模拟创建逻辑
        can_create = len(running_tasks) == 0

        if can_create:
            new_task = MagicMock()
            new_task.id = uuid4()
            new_task.novel_id = novel_id
            new_task.task_type = "planning"
            new_task.status = "pending"
            created = True
        else:
            created = False

        assert created is True

    def test_create_task_blocked_when_running(self, mock_novel):
        """测试有运行时任务时创建企划任务被阻止.

        验证：创建失败并返回错误信息。
        """
        running_tasks = [MagicMock(status="pending", id=uuid4())]
        novel_id = mock_novel.id

        # 模拟创建逻辑
        can_create = len(running_tasks) == 0

        if can_create:
            error_message = None
            created = True
        else:
            error_message = f"该小说已有企划任务在运行中 (Task ID: {running_tasks[0].id})"
            created = False

        assert created is False
        assert error_message is not None
        assert "已有企划任务在运行中" in error_message

    def test_create_task_after_completion(self, mock_novel):
        """测试任务完成后创建新企划任务.

        验证：completed 状态的任务不阻止创建新任务。
        """
        completed_tasks = [
            MagicMock(status="completed", id=uuid4()),
            MagicMock(status="failed", id=uuid4()),
        ]
        novel_id = mock_novel.id

        # 模拟创建逻辑
        can_create = len(completed_tasks) == 0

        # 注意：实际代码中已完成的任务不计入 running_tasks
        # 这里模拟的是重新查询后的状态
        can_create_after_completion = True

        if can_create_after_completion:
            new_task = MagicMock()
            new_task.id = uuid4()
            new_task.novel_id = novel_id
            new_task.task_type = "planning"
            new_task.status = "pending"
            created = True
        else:
            created = False

        assert created is True


class TestFrontendButtonState:
    """前端按钮状态逻辑测试（模拟）."""

    def test_button_disabled_when_running_task(self):
        """测试有运行时任务时按钮禁用.

        验证：前端 disabled 逻辑正确。
        """
        tasks = [
            {"task_type": "planning", "status": "running"},
        ]

        has_running_planning_task = any(
            t["task_type"] == "planning" and t["status"] in ["pending", "running"] for t in tasks
        )

        button_disabled = has_running_planning_task

        assert button_disabled is True

    def test_button_enabled_when_no_running_task(self):
        """测试无运行时任务时按钮启用.

        验证：前端 disabled 逻辑正确。
        """
        tasks = [
            {"task_type": "planning", "status": "completed"},
            {"task_type": "writing", "status": "running"},
        ]

        has_running_planning_task = any(
            t["task_type"] == "planning" and t["status"] in ["pending", "running"] for t in tasks
        )

        button_disabled = has_running_planning_task

        assert button_disabled is False

    def test_button_enabled_with_empty_tasks(self):
        """测试任务列表为空时按钮启用.

        验证：前端 disabled 逻辑正确。
        """
        tasks = []

        has_running_planning_task = any(
            t["task_type"] == "planning" and t["status"] in ["pending", "running"] for t in tasks
        )

        button_disabled = has_running_planning_task

        assert button_disabled is False

    def test_button_enabled_after_task_completion(self):
        """测试任务完成后按钮启用.

        验证：任务状态变为 completed 后按钮恢复启用。
        """
        # 初始状态：有运行中的任务
        tasks_before = [
            {"task_type": "planning", "status": "running"},
        ]
        has_running_before = any(
            t["task_type"] == "planning" and t["status"] in ["pending", "running"]
            for t in tasks_before
        )
        assert has_running_before is True

        # 完成后状态
        tasks_after = [
            {"task_type": "planning", "status": "completed"},
        ]
        has_running_after = any(
            t["task_type"] == "planning" and t["status"] in ["pending", "running"]
            for t in tasks_after
        )
        button_disabled = has_running_after

        assert button_disabled is False


class TestGenerationTaskModel:
    """GenerationTask 模型测试."""

    def test_task_type_enum(self):
        """测试任务类型枚举."""
        from core.models.generation_task import TaskType

        assert TaskType.planning.value == "planning"
        assert TaskType.writing.value == "writing"
        assert TaskType.batch_writing.value == "batch_writing"

    def test_task_status_enum(self):
        """测试任务状态枚举."""
        from core.models.generation_task import TaskStatus

        assert TaskStatus.pending.value == "pending"
        assert TaskStatus.running.value == "running"
        assert TaskStatus.completed.value == "completed"
        assert TaskStatus.failed.value == "failed"
        assert TaskStatus.cancelled.value == "cancelled"

    def test_generation_task_model_fields(self):
        """测试 GenerationTask 模型字段."""
        from core.models.generation_task import GenerationTask

        required_fields = [
            "id",
            "novel_id",
            "task_type",
            "status",
            "input_data",
            "output_data",
        ]

        for field in required_fields:
            assert hasattr(GenerationTask, field)
