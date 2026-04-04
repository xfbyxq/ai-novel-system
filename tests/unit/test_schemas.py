"""Pydantic Schema 单元测试.

测试所有 backend/schemas 中的 Pydantic 模型.
"""

import pytest
from datetime import datetime
from uuid import uuid4


class TestNovelSchemas:
    """小说 Schema 测试类."""

    def test_novel_create_valid(self):
        """测试创建有效的小说."""
        from backend.schemas.novel import NovelCreate

        novel = NovelCreate(
            title="测试小说",
            genre="仙侠",
            tags=["升级", "战斗"],
            synopsis="这是一个测试简介",
        )

        assert novel.title == "测试小说"
        assert novel.genre == "仙侠"
        assert novel.tags == ["升级", "战斗"]

    def test_novel_create_minimal(self):
        """测试创建最小数据的小说."""
        from backend.schemas.novel import NovelCreate

        novel = NovelCreate(title="最小小说", genre="都市")

        assert novel.title == "最小小说"
        assert novel.genre == "都市"
        assert novel.tags is None

    def test_novel_create_title_validation(self):
        """测试标题验证."""
        from backend.schemas.novel import NovelCreate

        with pytest.raises(ValueError, match="标题不能为空"):
            NovelCreate(title="   ", genre="都市")

    def test_novel_create_title_special_chars(self):
        """测试标题特殊字符验证."""
        from backend.schemas.novel import NovelCreate

        with pytest.raises(ValueError, match="标题包含非法字符"):
            NovelCreate(title="测试<script>", genre="都市")

    def test_novel_create_genre_validation(self):
        """测试类型验证."""
        from backend.schemas.novel import NovelCreate

        with pytest.raises(ValueError, match="小说类型不能为空"):
            NovelCreate(title="测试", genre="   ")

    def test_novel_create_tags_validation(self):
        """测试标签验证."""
        from backend.schemas.novel import NovelCreate

        with pytest.raises(ValueError, match="标签列表包含重复项"):
            NovelCreate(title="测试", genre="都市", tags=["升级", "升级"])

    def test_novel_create_tags_empty_filter(self):
        """测试空标签过滤."""
        from backend.schemas.novel import NovelCreate

        novel = NovelCreate(title="测试", genre="都市", tags=["升级", "  ", ""])
        assert novel.tags == ["升级"]

    def test_novel_create_tags_too_long(self):
        """测试标签长度验证."""
        from backend.schemas.novel import NovelCreate

        with pytest.raises(ValueError, match="长度超过 50 字符"):
            NovelCreate(title="测试", genre="都市", tags=["a" * 51])

    def test_novel_create_length_type(self):
        """测试篇幅类型验证."""
        from backend.schemas.novel import NovelCreate

        novel = NovelCreate(title="测试", genre="都市", length_type="short")
        assert novel.length_type == "short"

    def test_novel_create_invalid_length_type(self):
        """测试无效篇幅类型."""
        from backend.schemas.novel import NovelCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            NovelCreate(title="测试", genre="都市", length_type="invalid")

    def test_novel_update_valid(self):
        """测试更新小说."""
        from backend.schemas.novel import NovelUpdate

        update = NovelUpdate(title="更新标题", status="completed")
        assert update.title == "更新标题"
        assert update.status == "completed"

    def test_novel_update_partial(self):
        """测试部分更新."""
        from backend.schemas.novel import NovelUpdate

        update = NovelUpdate(title="更新标题")
        assert update.title == "更新标题"
        assert update.genre is None

    def test_novel_update_cover_url_validation(self):
        """测试封面 URL 验证."""
        from backend.schemas.novel import NovelUpdate

        with pytest.raises(ValueError, match="封面 URL 必须以"):
            NovelUpdate(cover_url="invalid-url")

    def test_novel_update_valid_cover_url(self):
        """测试有效封面 URL."""
        from backend.schemas.novel import NovelUpdate

        update = NovelUpdate(cover_url="https://example.com/cover.jpg")
        assert update.cover_url == "https://example.com/cover.jpg"

    def test_novel_update_invalid_status(self):
        """测试无效状态."""
        from backend.schemas.novel import NovelUpdate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            NovelUpdate(status="invalid_status")

    def test_novel_response_from_model(self):
        """测试从模型创建响应."""
        from backend.schemas.novel import NovelResponse

        response = NovelResponse(
            id=uuid4(),
            title="测试小说",
            author="测试作者",
            genre="仙侠",
            status="writing",
            length_type="long",
            word_count=10000,
            chapter_count=5,
            target_platform="番茄小说",
            estimated_revenue=1000.0,
            actual_revenue=500.0,
            token_cost=50.0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert response.title == "测试小说"
        assert response.word_count == 10000

    def test_novel_list_response(self):
        """测试小说列表响应."""
        from backend.schemas.novel import NovelListResponse, NovelResponse

        response = NovelListResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
        )

        assert response.total == 0
        assert response.page == 1


class TestCommonSchemas:
    """通用 Schema 测试类."""

    def test_message_response(self):
        """测试消息响应."""
        from backend.schemas.common import MessageResponse

        response = MessageResponse(message="操作成功")
        assert response.message == "操作成功"

    def test_task_cancel_response(self):
        """测试任务取消响应."""
        from backend.schemas.common import TaskCancelResponse

        response = TaskCancelResponse(
            message="任务已取消",
            task_id="task-123",
        )
        assert response.task_id == "task-123"

    def test_verify_account_response(self):
        """测试账号验证响应."""
        from backend.schemas.common import VerifyAccountResponse

        response = VerifyAccountResponse(success=True, message="验证成功")
        assert response.success is True

    def test_delete_response(self):
        """测试删除响应."""
        from backend.schemas.common import DeleteResponse

        response = DeleteResponse(
            message="删除成功",
            account_id="acc-123",
        )
        assert response.account_id == "acc-123"

    def test_delete_response_without_id(self):
        """测试无 ID 的删除响应."""
        from backend.schemas.common import DeleteResponse

        response = DeleteResponse(message="删除成功")
        assert response.account_id is None


class TestCharacterSchemas:
    """角色 Schema 测试类."""

    def test_character_create_valid(self):
        """测试创建有效角色."""
        from backend.schemas.character import CharacterCreate

        character = CharacterCreate(
            name="林玄天",
            role_type="主角",
            gender="男",
            background="测试背景",
        )

        assert character.name == "林玄天"
        assert character.role_type == "主角"

    def test_character_create_minimal(self):
        """测试最小数据角色."""
        from backend.schemas.character import CharacterCreate

        character = CharacterCreate(name="测试角色")
        assert character.name == "测试角色"

    def test_character_gender_validation(self):
        """测试性别验证."""
        from backend.schemas.character import CharacterCreate

        with pytest.raises(ValueError, match="性别必须是"):
            CharacterCreate(name="测试", gender="双性")

    def test_character_name_validation(self):
        """测试角色名称验证."""
        from backend.schemas.character import CharacterCreate

        with pytest.raises(ValueError, match="角色名称不能为空"):
            CharacterCreate(name="   ")


class TestOutlineSchemas:
    """大纲 Schema 测试类."""

    def test_world_setting_response(self):
        """测试世界观响应."""
        from backend.schemas.outline import WorldSettingResponse

        response = WorldSettingResponse(
            id=uuid4(),
            novel_id=uuid4(),
            world_name="测试世界",
            world_type="仙侠",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert response.world_name == "测试世界"

    def test_volume_info(self):
        """测试卷信息."""
        from backend.schemas.outline import VolumeInfo

        volume = VolumeInfo(
            number=1,
            title="第一卷",
            summary="测试概要",
            chapters=[1, 10],
        )

        assert volume.number == 1
        assert volume.title == "第一卷"

    def test_plot_outline_response(self):
        """测试剧情大纲响应."""
        from backend.schemas.outline import PlotOutlineResponse

        response = PlotOutlineResponse(
            id=uuid4(),
            novel_id=uuid4(),
            structure_type="三幕式",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert response.structure_type == "三幕式"

    def test_chapter_create(self):
        """测试创建章节."""
        from backend.schemas.outline import ChapterCreate

        chapter = ChapterCreate(
            chapter_number=1,
            volume_number=1,
            title="第一章",
        )

        assert chapter.chapter_number == 1
        assert chapter.title == "第一章"

    def test_chapter_update(self):
        """测试更新章节."""
        from backend.schemas.outline import ChapterUpdate

        update = ChapterUpdate(title="新标题", content="新内容")
        assert update.title == "新标题"
        assert update.content == "新内容"


class TestGenerationSchemas:
    """生成任务 Schema 测试类."""

    def test_generation_task_create_valid(self):
        """测试创建有效生成任务."""
        from backend.schemas.generation import GenerationTaskCreate

        task = GenerationTaskCreate(
            task_type="chapter",
            novel_id=uuid4(),
        )

        assert task.task_type == "chapter"

    def test_generation_task_create_writing(self):
        """测试创建写作任务."""
        from backend.schemas.generation import GenerationTaskCreate

        task = GenerationTaskCreate(
            task_type="writing",
            novel_id=uuid4(),
            input_data={"chapter_number": 1},
        )

        assert task.input_data["chapter_number"] == 1

    def test_generation_task_response(self):
        """测试生成任务响应."""
        from backend.schemas.generation import GenerationTaskResponse

        response = GenerationTaskResponse(
            id=uuid4(),
            novel_id=uuid4(),
            task_type="chapter",
            status="pending",
            created_at=datetime.now(),
        )

        assert response.task_type == "chapter"
        assert response.status == "pending"


class TestPublishingSchemas:
    """发布 Schema 测试类."""

    def test_platform_account_create(self):
        """测试创建平台账号."""
        from backend.schemas.publishing import PlatformAccountCreate

        account = PlatformAccountCreate(
            platform="qidian",
            account_name="测试账号",
            username="test_user",
            password="test_pass",
        )

        assert account.platform == "qidian"
        assert account.account_name == "测试账号"

    def test_publish_task_create(self):
        """测试创建发布任务."""
        from backend.schemas.publishing import PublishTaskCreate

        task = PublishTaskCreate(
            novel_id=uuid4(),
            account_id=uuid4(),
            publish_type="create_book",
        )

        assert task.publish_type == "create_book"

    def test_publish_task_response(self):
        """测试发布任务响应."""
        from backend.schemas.publishing import PublishTaskResponse

        response = PublishTaskResponse(
            id=uuid4(),
            novel_id=uuid4(),
            account_id=uuid4(),
            publish_type="create_book",
            status="pending",
            created_at=datetime.now(),
        )

        assert response.status == "pending"

    def test_chapter_publish_response(self):
        """测试章节发布响应."""
        from backend.schemas.publishing import ChapterPublishResponse

        response = ChapterPublishResponse(
            id=uuid4(),
            publish_task_id=uuid4(),
            chapter_id=uuid4(),
            chapter_number=1,
            status="published",
            created_at=datetime.now(),
        )

        assert response.chapter_number == 1


class TestAIChatSchemas:
    """AI 聊天 Schema 测试类."""

    def test_chat_session_create(self):
        """测试创建聊天会话."""
        from backend.schemas.ai_chat import AIChatSessionCreate

        session = AIChatSessionCreate(
            scene="novel_creation",
        )

        assert session.scene == "novel_creation"

    def test_chat_message_create(self):
        """测试发送消息."""
        from backend.schemas.ai_chat import AIChatMessageCreate

        message = AIChatMessageCreate(message="测试消息")
        assert message.message == "测试消息"

    def test_novel_parse_request(self):
        """测试小说解析请求."""
        from backend.schemas.ai_chat import NovelParseRequest

        request = NovelParseRequest(user_input="创建一个仙侠小说")
        assert "仙侠" in request.user_input

    def test_revision_suggestion(self):
        """测试修订建议."""
        from backend.schemas.ai_chat import RevisionSuggestion

        suggestion = RevisionSuggestion(
            type="character",
            target_name="主角",
            description="建议修改性格",
        )

        assert suggestion.type == "character"


class TestNovelCreationFlowSchemas:
    """小说创建流程 Schema 测试类."""

    def test_world_setting_details(self):
        """测试世界观设定详情."""
        from backend.schemas.novel_creation_flow import WorldSettingDetails

        details = WorldSettingDetails(
            era_background="古代",
            power_system="修真",
        )

        assert details.era_background == "古代"

    def test_novel_synopsis(self):
        """测试小说简介."""
        from backend.schemas.novel_creation_flow import NovelSynopsis

        synopsis = NovelSynopsis(
            main_plot="测试主线",
            core_conflict="测试冲突",
            target_audience="年轻读者",
        )

        assert synopsis.main_plot == "测试主线"

    def test_novel_creation_context(self):
        """测试创建上下文."""
        from backend.schemas.novel_creation_flow import NovelCreationContext

        context = NovelCreationContext(
            genre="仙侠",
            novel_title="测试小说",
        )

        assert context.genre == "仙侠"
        assert context.scene.value == "create"

    def test_novel_creation_flow_state(self):
        """测试创建流程状态."""
        from backend.schemas.novel_creation_flow import NovelCreationFlowState, NovelCreationContext

        state = NovelCreationFlowState(
            session_id="test-session",
            context=NovelCreationContext(genre="仙侠"),
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        assert state.session_id == "test-session"
