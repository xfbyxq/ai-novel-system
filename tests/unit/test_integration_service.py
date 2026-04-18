"""集成服务单元测试."""
import pytest
from backend.services.integration_service import IntegrationService


@pytest.mark.skip(reason="需要完整的异步事件循环环境，作为集成测试运行")
async def test_run_end_to_end_workflow(db_session):
    """测试运行端到端的自动化小说创作和发布工作流."""
    # 测试服务
    service = IntegrationService(db_session)

    # 运行端到端工作流
    result = await service.run_end_to_end_workflow(
        config={
            "platform": "qidian",
            "market_analysis_days": 7,
            "writing_style": "modern",
            "auto_publish": False,
        },
    )

    assert isinstance(result, dict)
    assert "status" in result
    assert "workflow_id" in result
    assert "novel_info" in result
    assert "novel_creation_result" in result
    assert "market_analysis_report" in result


async def test_get_workflow_history(db_session):
    """测试获取工作流历史记录."""
    # 测试服务
    service = IntegrationService(db_session)

    # 获取工作流历史
    history = await service.get_workflow_history(
        limit=10,
        offset=0,
    )

    assert isinstance(history, dict)
    assert "total" in history
    assert "items" in history
    assert isinstance(history["items"], list)


async def test_get_workflow_detail(db_session):
    """测试获取工作流详情."""
    # 测试服务
    service = IntegrationService(db_session)

    # 获取工作流详情
    workflow_id = "test_workflow_id"
    detail = await service.get_workflow_detail(workflow_id)

    assert isinstance(detail, dict)
    assert detail["workflow_id"] == workflow_id
    assert "status" in detail
    assert "details" in detail
