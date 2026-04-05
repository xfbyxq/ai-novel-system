"""数据库模型单元测试.

测试 core/models/ 中的所有数据模型.
"""

import pytest
from datetime import datetime
from uuid import uuid4


class TestNovelEnums:
    """Novel 相关枚举测试."""

    def test_novel_status_enum_values(self):
        """测试 NovelStatus 枚举值."""
        from core.models.novel import NovelStatus

        assert NovelStatus.planning.value == "planning"
        assert NovelStatus.writing.value == "writing"
        assert NovelStatus.completed.value == "completed"
        assert NovelStatus.published.value == "published"

    def test_novel_length_type_enum_values(self):
        """测试 NovelLengthType 枚举值."""
        from core.models.novel import NovelLengthType

        assert NovelLengthType.short.value == "short"
        assert NovelLengthType.medium.value == "medium"
        assert NovelLengthType.long.value == "long"


class TestChapterEnums:
    """Chapter 相关枚举测试."""

    def test_chapter_status_enum_values(self):
        """测试 ChapterStatus 枚举值."""
        from core.models.chapter import ChapterStatus

        assert ChapterStatus.draft.value == "draft"
        assert ChapterStatus.reviewing.value == "reviewing"
        assert ChapterStatus.published.value == "published"


class TestCharacterEnums:
    """Character 相关枚举测试."""

    def test_role_type_enum_values(self):
        """测试 RoleType 枚举值."""
        from core.models.character import RoleType

        assert RoleType.protagonist.value == "protagonist"
        assert RoleType.supporting.value == "supporting"
        assert RoleType.antagonist.value == "antagonist"
        assert RoleType.minor.value == "minor"

    def test_gender_enum_values(self):
        """测试 Gender 枚举值."""
        from core.models.character import Gender

        assert Gender.male.value == "male"
        assert Gender.female.value == "female"
        assert Gender.other.value == "other"

    def test_character_status_enum_values(self):
        """测试 CharacterStatus 枚举值."""
        from core.models.character import CharacterStatus

        assert CharacterStatus.alive.value == "alive"
        assert CharacterStatus.dead.value == "dead"
        assert CharacterStatus.unknown.value == "unknown"


class TestGenerationTaskEnums:
    """GenerationTask 相关枚举测试."""

    def test_task_type_enum_values(self):
        """测试 TaskType 枚举值."""
        from core.models.generation_task import TaskType

        assert TaskType.planning.value == "planning"
        assert TaskType.writing.value == "writing"
        assert TaskType.batch_writing.value == "batch_writing"
        assert TaskType.outline_refinement.value == "outline_refinement"

    def test_task_status_enum_values(self):
        """测试 TaskStatus 枚举值."""
        from core.models.generation_task import TaskStatus

        assert TaskStatus.pending.value == "pending"
        assert TaskStatus.running.value == "running"
        assert TaskStatus.completed.value == "completed"
        assert TaskStatus.failed.value == "failed"
        assert TaskStatus.cancelled.value == "cancelled"


class TestPublishTaskEnums:
    """PublishTask 相关枚举测试."""

    def test_publish_type_enum_values(self):
        """测试 PublishType 枚举值."""
        from core.models.publish_task import PublishType

        assert PublishType.create_book.value == "create_book"
        assert PublishType.publish_chapter.value == "publish_chapter"
        assert PublishType.batch_publish.value == "batch_publish"

    def test_publish_status_enum_values(self):
        """测试 PublishTaskStatus 枚举值."""
        from core.models.publish_task import PublishTaskStatus

        assert PublishTaskStatus.pending.value == "pending"
        assert PublishTaskStatus.running.value == "running"
        assert PublishTaskStatus.completed.value == "completed"
        assert PublishTaskStatus.failed.value == "failed"
        assert PublishTaskStatus.cancelled.value == "cancelled"


class TestModelCreation:
    """模型创建测试（验证模型结构）."""

    def test_novel_model_has_required_columns(self):
        """测试 Novel 模型具有必需的列."""
        from core.models.novel import Novel

        columns = [c.name for c in Novel.__table__.columns]
        required_columns = [
            "id",
            "title",
            "author",
            "genre",
            "tags",
            "status",
            "length_type",
            "word_count",
            "chapter_count",
            "created_at",
        ]
        for col in required_columns:
            assert col in columns, f"Missing column: {col}"

    def test_chapter_model_has_required_columns(self):
        """测试 Chapter 模型具有必需的列."""
        from core.models.chapter import Chapter

        columns = [c.name for c in Chapter.__table__.columns]
        required_columns = [
            "id",
            "novel_id",
            "chapter_number",
            "volume_number",
            "title",
            "content",
            "word_count",
            "status",
        ]
        for col in required_columns:
            assert col in columns, f"Missing column: {col}"

    def test_character_model_has_required_columns(self):
        """测试 Character 模型具有必需的列."""
        from core.models.character import Character

        columns = [c.name for c in Character.__table__.columns]
        required_columns = [
            "id",
            "novel_id",
            "name",
            "role_type",
            "gender",
            "age",
            "status",
            "created_at",
        ]
        for col in required_columns:
            assert col in columns, f"Missing column: {col}"

    def test_generation_task_model_has_required_columns(self):
        """测试 GenerationTask 模型具有必需的列."""
        from core.models.generation_task import GenerationTask

        columns = [c.name for c in GenerationTask.__table__.columns]
        required_columns = [
            "id",
            "novel_id",
            "task_type",
            "status",
            "input_data",
            "output_data",
            "created_at",
        ]
        for col in required_columns:
            assert col in columns, f"Missing column: {col}"

    def test_publish_task_model_has_required_columns(self):
        """测试 PublishTask 模型具有必需的列."""
        from core.models.publish_task import PublishTask

        columns = [c.name for c in PublishTask.__table__.columns]
        required_columns = [
            "id",
            "novel_id",
            "platform_account_id",
            "publish_type",
            "status",
            "created_at",
        ]
        for col in required_columns:
            assert col in columns, f"Missing column: {col}"

    def test_world_setting_model_has_required_columns(self):
        """测试 WorldSetting 模型具有必需的列."""
        from core.models.world_setting import WorldSetting

        columns = [c.name for c in WorldSetting.__table__.columns]
        required_columns = ["id", "novel_id", "world_name", "world_type", "created_at"]
        for col in required_columns:
            assert col in columns, f"Missing column: {col}"

    def test_plot_outline_model_has_required_columns(self):
        """测试 PlotOutline 模型具有必需的列."""
        from core.models.plot_outline import PlotOutline

        columns = [c.name for c in PlotOutline.__table__.columns]
        required_columns = [
            "id",
            "novel_id",
            "structure_type",
            "volumes",
            "main_plot",
            "created_at",
        ]
        for col in required_columns:
            assert col in columns, f"Missing column: {col}"


class TestModelRelationships:
    """模型关系测试."""

    def test_novel_has_world_setting_relationship(self):
        """测试 Novel 有 world_setting 关系."""
        from core.models.novel import Novel

        relationship_names = [rel.key for rel in Novel.__mapper__.relationships]
        assert "world_setting" in relationship_names

    def test_novel_has_characters_relationship(self):
        """测试 Novel 有 characters 关系."""
        from core.models.novel import Novel

        relationship_names = [rel.key for rel in Novel.__mapper__.relationships]
        assert "characters" in relationship_names

    def test_novel_has_chapters_relationship(self):
        """测试 Novel 有 chapters 关系."""
        from core.models.novel import Novel

        relationship_names = [rel.key for rel in Novel.__mapper__.relationships]
        assert "chapters" in relationship_names

    def test_chapter_has_novel_relationship(self):
        """测试 Chapter 有 novel 关系."""
        from core.models.chapter import Chapter

        relationship_names = [rel.key for rel in Chapter.__mapper__.relationships]
        assert "novel" in relationship_names

    def test_character_has_novel_relationship(self):
        """测试 Character 有 novel 关系."""
        from core.models.character import Character

        relationship_names = [rel.key for rel in Character.__mapper__.relationships]
        assert "novel" in relationship_names


class TestTokenUsageModel:
    """TokenUsage 模型测试."""

    def test_token_usage_model_columns(self):
        """测试 TokenUsage 模型列."""
        from core.models.token_usage import TokenUsage

        columns = [c.name for c in TokenUsage.__table__.columns]
        required_columns = ["id", "novel_id", "agent_name", "prompt_tokens", "completion_tokens"]
        for col in required_columns:
            assert col in columns

    def test_token_usage_model_creation(self):
        """测试 TokenUsage 模型创建."""
        from core.models.token_usage import TokenUsage

        novel_id = uuid4()
        task_id = uuid4()
        usage = TokenUsage(
            novel_id=novel_id,
            task_id=task_id,
            agent_name="test_agent",
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
            cost=0.003,
        )

        assert usage.novel_id == novel_id
        assert usage.task_id == task_id
        assert usage.agent_name == "test_agent"
        assert usage.prompt_tokens == 1000
        assert usage.completion_tokens == 500


class TestCharacterNameVersionModel:
    """CharacterNameVersion 模型测试."""

    def test_character_name_version_model_columns(self):
        """测试 CharacterNameVersion 模型列."""
        from core.models.character_name_version import CharacterNameVersion

        columns = [c.name for c in CharacterNameVersion.__table__.columns]
        required_columns = ["id", "character_id", "old_name", "new_name", "is_active"]
        for col in required_columns:
            assert col in columns


class TestPlotOutlineVersionModel:
    """PlotOutlineVersion 模型测试."""

    def test_plot_outline_version_model_columns(self):
        """测试 PlotOutlineVersion 模型列."""
        from core.models.plot_outline_version import PlotOutlineVersion

        columns = [c.name for c in PlotOutlineVersion.__table__.columns]
        required_columns = ["id", "plot_outline_id", "version_number", "version_data"]
        for col in required_columns:
            assert col in columns


class TestChapterPublishModel:
    """ChapterPublish 模型测试."""

    def test_chapter_publish_model_columns(self):
        """测试 ChapterPublish 模型列."""
        from core.models.chapter_publish import ChapterPublish

        columns = [c.name for c in ChapterPublish.__table__.columns]
        required_columns = ["id", "publish_task_id", "chapter_id", "chapter_number", "status"]
        for col in required_columns:
            assert col in columns


class TestPlatformAccountModel:
    """PlatformAccount 模型测试."""

    def test_platform_account_model_columns(self):
        """测试 PlatformAccount 模型列."""
        from core.models.platform_account import PlatformAccount

        columns = [c.name for c in PlatformAccount.__table__.columns]
        required_columns = ["id", "platform_name", "account_name", "username", "status"]
        for col in required_columns:
            assert col in columns


class TestAIChatSessionModel:
    """AIChatSession 模型测试."""

    def test_ai_chat_session_model_columns(self):
        """测试 AIChatSession 模型列."""
        from core.models.ai_chat_session import AIChatSession

        columns = [c.name for c in AIChatSession.__table__.columns]
        required_columns = ["id", "session_id", "scene", "created_at"]
        for col in required_columns:
            assert col in columns
