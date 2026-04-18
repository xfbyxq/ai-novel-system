"""自动化服务单元测试."""
import pytest
from backend.services.automation_service import AutomationService


@pytest.mark.skip(reason="需要完整的异步事件循环环境，作为集成测试运行")
async def test_run_automated_novel_creation(db_session):
    """测试运行自动化小说创建流程."""
    # 测试服务
    service = AutomationService(db_session)

    # 运行自动化小说创建
    result = await service.run_automated_novel_creation(
        config={
            "platform": "qidian",
            "market_analysis_days": 7,
            "writing_style": "modern",
        },
    )

    assert isinstance(result, dict)
    assert "status" in result
    assert "workflow_id" in result
    assert "novel_id" in result


@pytest.mark.skip(reason="需要完整的异步事件循环环境，作为集成测试运行")
async def test_initialize_agents(db_session):
    """测试初始化代理."""
    # 测试服务
    service = AutomationService(db_session)

    # 初始化代理
    await service.initialize_agents()

    # 检查代理是否初始化成功
    assert hasattr(service, "agents")
    assert isinstance(service.agents, dict)
    assert "content_planner" in service.agents
    assert "writer" in service.agents
    assert "editor" in service.agents
    assert "publisher" in service.agents


async def test_get_workflow_status(db_session):
    """测试获取工作流状态."""
    # 测试服务
    service = AutomationService(db_session)

    # 获取工作流状态
    workflow_id = "test_workflow_id"
    status = await service.get_workflow_status(workflow_id)

    assert isinstance(status, dict)
    assert status["workflow_id"] == workflow_id
    assert "status" in status
    assert "last_updated" in status


@pytest.mark.skip(reason="需要完整的异步事件循环环境，作为集成测试运行")
async def test_run_batch_automation(db_session):
    """测试运行批量自动化任务."""
    # 测试服务
    service = AutomationService(db_session)

    # 运行批量自动化
    batch_config = [
        {
            "platform": "qidian",
            "market_analysis_days": 7,
            "writing_style": "modern",
        },
        {
            "platform": "douyin",
            "market_analysis_days": 7,
            "writing_style": "modern",
        },
    ]

    result = await service.run_batch_automation(batch_config)

    assert isinstance(result, dict)
    assert "total_tasks" in result
    assert result["total_tasks"] == len(batch_config)
    assert "success_count" in result
    assert "failed_count" in result
    assert "results" in result
    assert len(result["results"]) == len(batch_config)
