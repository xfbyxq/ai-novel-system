"""大纲系统集成测试。

测试大纲系统的完整流程，包括：
1. 大纲生成流程
2. 章节拆分流程
3. 大纲验证流程
4. 端到端流程

使用 pytest 框架，mock LLM 调用避免真实 API 调用。
"""
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from backend.services.outline_service import OutlineService


# ---------------------------------------------------------------------------
# Mock 数据
# ---------------------------------------------------------------------------

MOCK_WORLD_SETTING = {
    "world_name": "青玄大陆",
    "world_type": "仙侠",
    "power_system": {
        "name": "修真体系",
        "levels": ["炼气", "筑基", "金丹", "元婴", "化神"],
        "description": "通过吸收天地灵气提升修为"
    },
    "factions": [
        {
            "name": "天剑宗",
            "type": "正道宗门",
            "power_level": "S 级",
            "description": "以剑道闻名的顶级宗门"
        },
        {
            "name": "魔教",
            "type": "魔道势力",
            "power_level": "A 级",
            "description": "与正道对立的魔道组织"
        }
    ],
    "geography": {
        "regions": [
            {"name": "东域", "features": ["山脉", "宗门"]},
            {"name": "西域", "features": ["沙漠", "古城"]}
        ]
    }
}

MOCK_OUTLINE_RESPONSE = {
    "structure_type": "三幕式",
    "main_plot": {
        "setup": "主角林玄天是青玄大陆东域一个小家族的庶子，因天赋低下备受欺凌。",
        "conflict": "在一次意外中获得上古传承，开始崛起，引起各方势力关注。",
        "climax": "与魔教圣子的终极对决，揭开身世之谜。",
        "resolution": "击败强敌，成为一代强者，守护家族和爱人。"
    },
    "sub_plots": [
        {
            "name": "感情线",
            "characters": ["林玄天", "苏清雪"],
            "arc": "从相遇到相知，共同经历生死考验"
        },
        {
            "name": "成长线",
            "characters": ["林玄天"],
            "arc": "从废柴庶子到一代强者的蜕变"
        }
    ],
    "volumes": [
        {
            "number": 1,
            "title": "潜龙在渊",
            "chapters": [1, 30],
            "summary": "主角获得传承，开始崛起之路",
            "core_conflict": "家族内部的权力斗争",
            "tension_cycles": [
                {
                    "chapters": [1, 10],
                    "suppress_events": ["被族人嘲笑", "被退婚", "被打压"],
                    "release_event": "获得上古传承"
                },
                {
                    "chapters": [15, 25],
                    "suppress_events": ["被天才打压", "被误解"],
                    "release_event": "家族大比一鸣惊人"
                }
            ],
            "key_events": [
                {"chapter": 3, "event": "获得神秘玉佩", "impact": "开启传承之路"},
                {"chapter": 15, "event": "家族大比夺冠", "impact": "震惊全族"},
                {"chapter": 28, "event": "突破筑基", "impact": "实力飞跃"}
            ]
        },
        {
            "number": 2,
            "title": "风云再起",
            "chapters": [31, 60],
            "summary": "主角走出家族，进入宗门修炼",
            "core_conflict": "宗门内的派系斗争",
            "tension_cycles": [
                {
                    "chapters": [31, 45],
                    "suppress_events": ["被师兄打压", "任务失败"],
                    "release_event": "秘境中获得机缘"
                }
            ],
            "key_events": [
                {"chapter": 35, "event": "进入天剑宗", "impact": "开始宗门修炼"},
                {"chapter": 50, "event": "秘境夺宝", "impact": "获得顶级功法"},
                {"chapter": 58, "event": "结成金丹", "impact": "成为核心弟子"}
            ]
        }
    ],
    "key_turning_points": [
        {"chapter": 3, "event": "获得传承", "impact": "命运转折点"},
        {"chapter": 15, "event": "家族大比", "impact": "崭露头角"},
        {"chapter": 35, "event": "进入宗门", "impact": "新的舞台"},
        {"chapter": 50, "event": "秘境机缘", "impact": "实力暴涨"},
        {"chapter": 60, "event": "身世揭秘", "impact": "真相大白"}
    ],
    "climax_chapter": 58
}

MOCK_CHAPTER_CONFIG = {
    "novel_id": "test-novel-id",
    "volumes": [
        {
            "number": 1,
            "title": "潜龙在渊",
            "chapters": [1, 30]
        }
    ],
    "chapter_configs": [
        {
            "chapter_number": 1,
            "volume_number": 1,
            "main_goal": "引入主角，展示困境",
            "mandatory_events": ["主角出场", "被族人嘲笑", "发现神秘玉佩"],
            "tension_phase": "suppress",
            "foreshadowing": ["玉佩的神秘来历", "主角的身世线索"]
        },
        {
            "chapter_number": 2,
            "volume_number": 1,
            "main_goal": "冲突升级",
            "mandatory_events": ["被退婚", "立誓崛起"],
            "tension_phase": "suppress",
            "foreshadowing": ["未婚妻的真实身份"]
        },
        {
            "chapter_number": 3,
            "volume_number": 1,
            "main_goal": "获得传承",
            "mandatory_events": ["激活玉佩", "获得传承", "实力提升"],
            "tension_phase": "release",
            "foreshadowing": ["传承者的身份"]
        }
    ],
    "total_chapters": 3
}


# ---------------------------------------------------------------------------
# Mock Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db_session():
    """创建 mock 数据库 session."""
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.add = MagicMock()
    return mock_session


@pytest.fixture
def mock_novel():
    """创建 mock 小说对象."""
    novel = MagicMock()
    novel.id = uuid4()
    novel.title = "测试小说"
    novel.author = "AI 测试"
    novel.genre = "仙侠"
    novel.tags = ["修真", "升级", "热血"]
    novel.synopsis = "这是一本测试小说"
    novel.length_type = MagicMock()
    novel.length_type.value = "medium"
    return novel


# ---------------------------------------------------------------------------
# 1. 大纲生成流程测试
# ---------------------------------------------------------------------------

class TestOutlineGeneration:
    """大纲生成流程测试."""

    @pytest.mark.asyncio
    async def test_generate_complete_outline(
        self,
        mock_db_session,
        mock_novel,
    ):
        """测试生成完整大纲."""
        # Arrange
        service = OutlineService(mock_db_session)

        # Mock 数据库查询返回小说
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_novel
        mock_db_session.execute.return_value = mock_result

        # Mock LLM 调用
        mock_response = {
            "content": json.dumps(MOCK_OUTLINE_RESPONSE, ensure_ascii=False),
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 2000,
                "total_tokens": 3000
            }
        }

        with patch.object(
            service.client,
            "chat",
            new=AsyncMock(return_value=mock_response)
        ) as mock_chat:
            # Act
            result = await service.generate_complete_outline(
                novel_id=mock_novel.id,
                world_setting_data=MOCK_WORLD_SETTING
            )

            # Assert
            assert mock_chat.called
            assert result["structure_type"] == "三幕式"
            assert "main_plot" in result
            assert "volumes" in result
            assert len(result["volumes"]) == 2

    @pytest.mark.asyncio
    async def test_generate_outline_with_world_setting(
        self,
        mock_db_session,
        mock_novel,
    ):
        """测试基于世界观生成大纲."""
        # Arrange
        service = OutlineService(mock_db_session)

        # Mock 数据库查询返回小说
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_novel
        mock_db_session.execute.return_value = mock_result

        # Mock LLM 调用
        mock_response = {
            "content": json.dumps(MOCK_OUTLINE_RESPONSE, ensure_ascii=False),
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 2000,
                "total_tokens": 3000
            }
        }

        with patch.object(
            service.client,
            "chat",
            new=AsyncMock(return_value=mock_response)
        ):
            # Act
            result = await service.generate_complete_outline(
                novel_id=mock_novel.id,
                world_setting_data={
                    "world_name": "测试世界",
                    "world_type": "仙侠",
                    "power_system": {"name": "修真"},
                    "factions": [],
                }
            )

            # Assert
            assert result["structure_type"] == "三幕式"
            assert len(result["volumes"]) == 2

    @pytest.mark.asyncio
    async def test_outline_contains_required_elements(
        self,
        mock_db_session,
        mock_novel,
    ):
        """测试大纲包含必要元素（核心冲突、结局等）."""
        # Arrange
        service = OutlineService(mock_db_session)

        # Mock 数据库查询返回小说
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_novel
        mock_db_session.execute.return_value = mock_result

        # Mock LLM 调用
        mock_response = {
            "content": json.dumps(MOCK_OUTLINE_RESPONSE, ensure_ascii=False),
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 2000,
                "total_tokens": 3000
            }
        }

        with patch.object(
            service.client,
            "chat",
            new=AsyncMock(return_value=mock_response)
        ):
            # Act
            result = await service.generate_complete_outline(
                novel_id=mock_novel.id,
                world_setting_data=MOCK_WORLD_SETTING
            )

            # Assert - 验证必要元素
            # 1. 主线剧情（包含核心冲突和结局）
            assert "main_plot" in result
            main_plot = result["main_plot"]
            assert "setup" in main_plot  # 开端
            assert "conflict" in main_plot  # 冲突
            assert "climax" in main_plot  # 高潮
            assert "resolution" in main_plot  # 结局

            # 2. 支线剧情
            assert "sub_plots" in result
            assert len(result["sub_plots"]) >= 2  # 至少 2 条支线

            # 3. 卷级大纲
            assert "volumes" in result
            for volume in result["volumes"]:
                assert "number" in volume
                assert "title" in volume
                assert "chapters" in volume
                assert "summary" in volume
                assert "core_conflict" in volume  # 核心冲突
                assert "tension_cycles" in volume  # 张力循环
                assert "key_events" in volume  # 关键事件

            # 4. 关键转折点
            assert "key_turning_points" in result
            assert len(result["key_turning_points"]) >= 5

            # 5. 高潮章节
            assert "climax_chapter" in result
            assert isinstance(result["climax_chapter"], int)


# ---------------------------------------------------------------------------
# 2. 章节拆分流程测试
# ---------------------------------------------------------------------------

class TestChapterDecomposition:
    """章节拆分流程测试."""

    @pytest.mark.asyncio
    async def test_decompose_outline_to_chapters(
        self,
        mock_db_session,
        mock_novel,
    ):
        """测试将大纲分解为章节."""
        # Arrange
        service = OutlineService(mock_db_session)

        # Mock 数据库查询返回小说和大纲
        mock_result = MagicMock()
        mock_outline = MagicMock()
        mock_outline.volumes = MOCK_OUTLINE_RESPONSE["volumes"]
        mock_result.scalar_one_or_none.return_value = mock_outline
        mock_db_session.execute.return_value = mock_result

        # Act
        result = await service.decompose_outline(
            novel_id=mock_novel.id,
            outline_data={"volumes": MOCK_OUTLINE_RESPONSE["volumes"]},
            config={
                "auto_split": True,
                "chapters_per_volume": 30,
                "flexible": True
            }
        )

        # Assert
        assert "chapter_configs" in result
        assert "volumes" in result
        assert result["total_chapters"] > 0

        # 验证章节配置包含必要信息
        chapter_configs = result["chapter_configs"]
        assert len(chapter_configs) > 0

        first_chapter = chapter_configs[0]
        assert "chapter_number" in first_chapter
        assert "volume_number" in first_chapter
        assert "mandatory_events" in first_chapter
        assert "emotional_tone" in first_chapter
        assert "tension_cycle_position" in first_chapter

    @pytest.mark.asyncio
    async def test_chapter_task_assignment(
        self,
        mock_db_session,
        mock_novel,
    ):
        """测试章节任务分配."""
        # Arrange
        service = OutlineService(mock_db_session)

        # Mock 数据库查询返回小说和大纲
        mock_result = MagicMock()
        mock_outline = MagicMock()
        mock_outline.volumes = MOCK_OUTLINE_RESPONSE["volumes"]
        mock_result.scalar_one_or_none.return_value = mock_outline
        mock_db_session.execute.return_value = mock_result

        # Act - 获取特定章节的大纲任务
        chapter_number = 1
        task = await service.get_chapter_outline_task(
            novel_id=mock_novel.id,
            chapter_number=chapter_number
        )

        # Assert
        assert "chapter_number" in task
        assert task["chapter_number"] == chapter_number
        assert "volume_number" in task
        assert "mandatory_events" in task
        assert "emotional_tone" in task  # 情感基调
        assert "tension_cycle_position" in task  # 张力阶段

    @pytest.mark.asyncio
    async def test_tension_cycle_generation(
        self,
        mock_db_session,
        mock_novel,
    ):
        """测试张力循环生成."""
        # Arrange
        service = OutlineService(mock_db_session)

        # Mock 数据库查询返回小说和大纲
        mock_result = MagicMock()
        mock_outline = MagicMock()
        mock_outline.volumes = MOCK_OUTLINE_RESPONSE["volumes"]
        mock_result.scalar_one_or_none.return_value = mock_outline
        mock_db_session.execute.return_value = mock_result

        # Act - 分解大纲
        result = await service.decompose_outline(
            novel_id=mock_novel.id,
            outline_data={"volumes": MOCK_OUTLINE_RESPONSE["volumes"]},
            config={"auto_split": True}
        )

        # Assert - 验证张力循环信息被分配到章节
        chapter_configs = result["chapter_configs"]

        # 检查是否有章节包含张力循环位置信息
        tension_positions = [
            ch.get("tension_cycle_position")
            for ch in chapter_configs
            if "tension_cycle_position" in ch
        ]

        assert len(tension_positions) > 0

        # 验证张力循环位置类型
        valid_positions = ["suppress", "release", None]
        for position in tension_positions:
            assert position in valid_positions or position is None


# ---------------------------------------------------------------------------
# 3. 大纲验证流程测试
# ---------------------------------------------------------------------------

class TestOutlineValidation:
    """大纲验证流程测试."""

    @pytest.mark.asyncio
    async def test_validate_chapter_outline_success(
        self,
        mock_db_session,
        mock_novel,
    ):
        """测试验证通过的章节."""
        # Arrange
        service = OutlineService(mock_db_session)

        # Mock 数据库查询返回小说和大纲
        mock_result = MagicMock()
        mock_outline = MagicMock()
        mock_outline.volumes = MOCK_OUTLINE_RESPONSE["volumes"]
        mock_result.scalar_one_or_none.return_value = mock_outline
        mock_db_session.execute.return_value = mock_result

        # 准备一个包含所有强制性事件的章节计划
        chapter_plan = {
            "title": "第一章：废柴庶子",
            "content_plan": "主角林玄天出场，被族人嘲笑，发现神秘玉佩",
            "key_events": ["主角出场", "被族人嘲笑", "发现神秘玉佩"],
            "word_count": 3000
        }

        # Act
        result = await service.validate_chapter_outline(
            novel_id=mock_novel.id,
            chapter_number=1,
            chapter_plan=chapter_plan
        )

        # Assert
        assert "chapter_number" in result
        assert result["chapter_number"] == 1
        assert "passed" in result
        assert "completion" in result

        completion = result["completion"]
        assert "completed_events" in completion
        assert "missing_events" in completion
        assert "completion_rate" in completion

    @pytest.mark.asyncio
    async def test_validate_chapter_outline_failure(
        self,
        mock_db_session,
        mock_novel,
    ):
        """测试验证失败的章节."""
        # Arrange
        service = OutlineService(mock_db_session)

        # Mock 数据库查询返回小说和大纲
        mock_result = MagicMock()
        mock_outline = MagicMock()
        mock_outline.volumes = MOCK_OUTLINE_RESPONSE["volumes"]
        mock_result.scalar_one_or_none.return_value = mock_outline
        mock_db_session.execute.return_value = mock_result

        # 准备一个缺少强制性事件的章节计划
        chapter_plan = {
            "title": "第一章：不完整的剧情",
            "content_plan": "主角林玄天出场，但没有被嘲笑，也没有发现玉佩",
            "key_events": ["主角出场"],  # 缺少关键事件
            "word_count": 2000
        }

        # Act
        result = await service.validate_chapter_outline(
            novel_id=mock_novel.id,
            chapter_number=1,
            chapter_plan=chapter_plan
        )

        # Assert
        assert "chapter_number" in result
        assert result["chapter_number"] == 1
        assert "passed" in result
        assert "completion" in result

        completion = result["completion"]
        assert "missing_events" in completion

        # 验证失败（完成率低）
        assert len(completion["missing_events"]) > 0

    @pytest.mark.asyncio
    async def test_validation_suggestions(
        self,
        mock_db_session,
        mock_novel,
    ):
        """测试验证建议生成."""
        # Arrange
        service = OutlineService(mock_db_session)

        # Mock 数据库查询返回小说和大纲
        mock_result = MagicMock()
        mock_outline = MagicMock()
        mock_outline.volumes = MOCK_OUTLINE_RESPONSE["volumes"]
        mock_result.scalar_one_or_none.return_value = mock_outline
        mock_db_session.execute.return_value = mock_result

        # 准备一个有部分缺失的章节计划
        chapter_plan = {
            "title": "第一章：有缺陷的剧情",
            "content_plan": "主角林玄天出场，被族人嘲笑",
            "key_events": ["主角出场", "被族人嘲笑"],  # 缺少"发现神秘玉佩"
            "word_count": 2500
        }

        # Act
        result = await service.validate_chapter_outline(
            novel_id=mock_novel.id,
            chapter_number=1,
            chapter_plan=chapter_plan
        )

        # Assert
        assert "suggestions" in result

        # 验证生成了改进建议
        suggestions = result["suggestions"]
        assert isinstance(suggestions, list)


# ---------------------------------------------------------------------------
# 4. 端到端流程测试
# ---------------------------------------------------------------------------

class TestEndToEndWorkflow:
    """端到端流程测试."""

    @pytest.mark.asyncio
    async def test_complete_workflow(
        self,
        mock_db_session,
        mock_novel,
    ):
        """测试完整创作流程（世界观→大纲→章节拆分→章节生成）."""
        # Arrange
        service = OutlineService(mock_db_session)

        # Mock 大纲对象
        mock_outline = MagicMock()
        mock_outline.volumes = MOCK_OUTLINE_RESPONSE["volumes"]
        mock_outline.structure_type = "三幕式"

        # Mock 数据库查询结果
        mock_novel_result = MagicMock()
        mock_novel_result.scalar_one_or_none.return_value = mock_novel

        mock_outline_result = MagicMock()
        mock_outline_result.scalar_one_or_none.return_value = mock_outline

        # 配置 mock_db_session.execute 根据查询返回不同结果
        mock_db_session.execute.side_effect = [
            mock_novel_result,  # generate_complete_outline 查询 Novel
            mock_outline_result,  # decompose_outline 查询 PlotOutline
            mock_outline_result,  # get_chapter_outline_task 查询 PlotOutline
            mock_outline_result,  # validate_chapter_outline 查询 PlotOutline
        ]

        # Mock LLM 调用
        mock_response = {
            "content": json.dumps(MOCK_OUTLINE_RESPONSE, ensure_ascii=False),
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 2000,
                "total_tokens": 3000
            }
        }

        # Mock token usage recording
        with patch.object(service, '_record_token_usage', new=AsyncMock()):
            # Step 1: 生成大纲
            with patch.object(
                service.client,
                "chat",
                new=AsyncMock(return_value=mock_response)
            ):
                outline_result = await service.generate_complete_outline(
                    novel_id=mock_novel.id,
                    world_setting_data=MOCK_WORLD_SETTING
                )

            assert outline_result["structure_type"] == "三幕式"

        # Step 2: 分解大纲为章节
        decompose_result = await service.decompose_outline(
            novel_id=mock_novel.id,
            outline_data={"volumes": outline_result["volumes"]},
            config={"auto_split": True}
        )

        assert decompose_result["total_chapters"] > 0

        # Step 3: 获取章节任务
        chapter_task = await service.get_chapter_outline_task(
            novel_id=mock_novel.id,
            chapter_number=1
        )

        assert chapter_task["chapter_number"] == 1
        assert "mandatory_events" in chapter_task
        assert "emotional_tone" in chapter_task

        # Step 4: 验证章节大纲
        chapter_plan = {
            "title": "第一章",
            "content_plan": "完整的章节内容",
            "key_events": chapter_task.get("mandatory_events", []),
            "word_count": 3000
        }

        validation_result = await service.validate_chapter_outline(
            novel_id=mock_novel.id,
            chapter_number=1,
            chapter_plan=chapter_plan
        )

        assert "chapter_number" in validation_result
        assert "passed" in validation_result

    @pytest.mark.asyncio
    async def test_outline_versioning(
        self,
        mock_db_session,
        mock_novel,
    ):
        """测试大纲版本管理."""
        # Arrange
        service = OutlineService(mock_db_session)

        # Mock 数据库查询
        mock_result = MagicMock()
        mock_outline = MagicMock()
        mock_outline.volumes = MOCK_OUTLINE_RESPONSE["volumes"]
        mock_outline.structure_type = "三幕式"
        mock_outline.created_at = datetime.now()
        mock_outline.updated_at = datetime.now()
        mock_result.scalar_one_or_none.return_value = mock_outline
        mock_db_session.execute.return_value = mock_result

        # Act - 获取版本历史
        versions = await service.get_outline_versions(novel_id=mock_novel.id)

        # Assert
        assert isinstance(versions, list)
        assert len(versions) >= 1

        # 验证版本信息
        version = versions[0]
        assert "version" in version
        assert "created_at" in version
        assert "updated_at" in version
        assert "structure_type" in version
        assert "volumes_count" in version
        assert "total_chapters" in version

        assert version["structure_type"] == "三幕式"
        assert version["volumes_count"] == 2

    @pytest.mark.asyncio
    async def test_outline_update_affects_chapters(
        self,
        mock_db_session,
        mock_novel,
    ):
        """测试大纲更新影响章节标记."""
        # Arrange
        service = OutlineService(mock_db_session)

        # Mock 数据库查询
        mock_result = MagicMock()
        mock_outline = MagicMock()
        mock_outline.volumes = MOCK_OUTLINE_RESPONSE["volumes"]
        mock_result.scalar_one_or_none.return_value = mock_outline
        mock_db_session.execute.return_value = mock_result

        # 先分解大纲
        await service.decompose_outline(
            novel_id=mock_novel.id,
            outline_data={"volumes": MOCK_OUTLINE_RESPONSE["volumes"]},
            config={"auto_split": True}
        )

        # 获取原始章节任务
        original_task = await service.get_chapter_outline_task(
            novel_id=mock_novel.id,
            chapter_number=1
        )

        # 模拟更新大纲（修改卷信息）
        updated_volumes = MOCK_OUTLINE_RESPONSE["volumes"].copy()
        if updated_volumes and len(updated_volumes) > 0:
            # 修改第一卷的关键事件
            if "key_events" in updated_volumes[0]:
                updated_volumes[0]["key_events"].append(
                    {"chapter": 1, "event": "新增事件", "impact": "测试影响"}
                )

        # 重新分解大纲
        await service.decompose_outline(
            novel_id=mock_novel.id,
            outline_data={"volumes": updated_volumes},
            config={"auto_split": True}
        )

        # Act - 获取更新后的章节任务
        updated_task = await service.get_chapter_outline_task(
            novel_id=mock_novel.id,
            chapter_number=1
        )

        # Assert
        # 验证章节任务已更新
        assert updated_task is not None

        # 验证章节任务仍然包含必要信息
        assert "chapter_number" in updated_task
        assert "mandatory_events" in updated_task


# ---------------------------------------------------------------------------
# 5. 边界情况和异常测试
# ---------------------------------------------------------------------------

class TestOutlineEdgeCases:
    """大纲系统边界情况测试."""

    @pytest.mark.asyncio
    async def test_generate_outline_for_nonexistent_novel(
        self,
        mock_db_session,
    ):
        """测试为不存在的小说生成大纲."""
        # Arrange
        service = OutlineService(mock_db_session)
        fake_novel_id = uuid4()

        # Mock 数据库查询返回 None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Act & Assert
        with pytest.raises(ValueError, match="小说.*不存在"):
            await service.generate_complete_outline(
                novel_id=fake_novel_id,
                world_setting_data=MOCK_WORLD_SETTING
            )

    @pytest.mark.asyncio
    async def test_decompose_outline_without_volumes(
        self,
        mock_db_session,
        mock_novel,
    ):
        """测试分解空大纲."""
        # Arrange
        service = OutlineService(mock_db_session)

        # Act
        result = await service.decompose_outline(
            novel_id=mock_novel.id,
            outline_data={"volumes": []},  # 空卷列表
            config={"auto_split": True}
        )

        # Assert
        assert result["chapters"] == []
        assert result["volumes"] == []

    @pytest.mark.asyncio
    async def test_validate_nonexistent_chapter(
        self,
        mock_db_session,
        mock_novel,
    ):
        """测试验证不存在的章节."""
        # Arrange
        service = OutlineService(mock_db_session)

        # Mock 数据库查询返回 None（章节不存在）
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Act
        result = await service.validate_chapter_outline(
            novel_id=mock_novel.id,
            chapter_number=999,  # 不存在的章节号
            chapter_plan={"title": "测试章节"}
        )

        # Assert
        assert result["passed"] is False
        assert "error" in result
