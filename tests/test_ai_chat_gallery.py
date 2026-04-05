"""测试 AI 助手的图库功能."""

import asyncio
import pytest
from uuid import uuid4, UUID

from backend.services.ai_chat_service import AiChatService
from core.database import async_session_factory
from core.models.novel import Novel
from core.models.chapter import Chapter
from core.models.world_setting import WorldSetting
from core.models.character import Character
from core.models.plot_outline import PlotOutline


class TestAiChatGallery:
    """AI 助手图库功能测试."""

    @pytest.fixture
    async def db_session(self):
        """数据库会话 fixture."""
        async with async_session_factory() as db:
            yield db

    @pytest.fixture
    async def ai_chat_service(self, db_session):
        """AI 助手服务 fixture."""
        return AiChatService(db_session)

    @pytest.fixture
    async def test_novel(self, db_session):
        """创建测试小说 fixture."""
        novel_id = uuid4()
        
        # 创建测试小说
        novel = Novel(
            id=novel_id,
            title="测试小说",
            author="测试作者",
            genre="玄幻",
            status="writing",
        )
        
        # 创建测试世界观
        world_setting = WorldSetting(
            novel_id=novel_id,
            world_name="玄元大陆",
            world_type="仙侠",
            raw_content="测试世界观内容",
        )
        
        # 创建测试角色
        character = Character(
            novel_id=novel_id,
            name="萧尘",
            role_type="主角",
            personality="坚韧不拔",
            background="剑神转世",
        )
        
        # 创建测试大纲
        plot_outline = PlotOutline(
            novel_id=novel_id,
            structure_type="three_act",
            volumes=[],
            main_plot={"core_conflict": "测试核心冲突"},
            raw_content="测试大纲内容",
        )
        
        # 创建测试章节
        chapter1 = Chapter(
            novel_id=novel_id,
            chapter_number=1,
            title="第 1 章 父亲病逝",
            content="这是第一章的测试内容...",
            word_count=100,
        )
        
        chapter2 = Chapter(
            novel_id=novel_id,
            chapter_number=2,
            title="第 2 章 坟前誓",
            content="这是第二章的测试内容...",
            word_count=150,
        )
        
        db_session.add(novel)
        db_session.add(world_setting)
        db_session.add(character)
        db_session.add(plot_outline)
        db_session.add(chapter1)
        db_session.add(chapter2)
        
        await db_session.commit()
        
        yield novel
        
        # 清理
        await db_session.delete(novel)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_query_character_network(self, ai_chat_service, test_novel):
        """测试查询角色关系网络."""
        result = await ai_chat_service.query_character_network(test_novel.id)
        
        # 验证返回结果
        assert isinstance(result, dict)
        # 注意：如果 Neo4j 未连接，会返回错误信息
        if "error" in result:
            assert "查询失败" in result["error"]
        else:
            assert "nodes" in result or "characters" in result

    @pytest.mark.asyncio
    async def test_query_world_setting_map(self, ai_chat_service, test_novel):
        """测试查询世界观设定地图."""
        result = await ai_chat_service.query_world_setting_map(test_novel.id)
        
        # 验证返回结果
        assert isinstance(result, dict)
        if "error" in result:
            assert "查询失败" in result["error"]
        else:
            assert "locations" in result or "world_settings" in result

    @pytest.mark.asyncio
    async def test_query_plot_timeline(self, ai_chat_service, test_novel):
        """测试查询情节时间线."""
        result = await ai_chat_service.query_plot_timeline(test_novel.id)
        
        # 验证返回结果
        assert isinstance(result, dict)
        if "error" in result:
            assert "查询失败" in result["error"]
        else:
            assert "events" in result or "timeline" in result

    @pytest.mark.asyncio
    async def test_query_gallery(self, ai_chat_service, test_novel):
        """测试统一图库查询接口."""
        # 测试角色查询
        result = await ai_chat_service.query_gallery(
            test_novel.id, "character_network"
        )
        assert isinstance(result, dict)
        
        # 测试世界观查询
        result = await ai_chat_service.query_gallery(
            test_novel.id, "world_map"
        )
        assert isinstance(result, dict)
        
        # 测试情节查询
        result = await ai_chat_service.query_gallery(
            test_novel.id, "plot_timeline"
        )
        assert isinstance(result, dict)
        
        # 测试未知类型
        result = await ai_chat_service.query_gallery(
            test_novel.id, "unknown_type"
        )
        assert "error" in result
        assert "未知的查询类型" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_chapter_to_gallery(self, ai_chat_service, test_novel):
        """测试同步章节到图库."""
        result = await ai_chat_service.sync_chapter_to_gallery(
            novel_id=test_novel.id,
            chapter_number=1,
            chapter_content="测试章节内容"
        )
        
        # 验证返回结果
        assert isinstance(result, dict)
        # 注意：如果 Neo4j 未连接，会返回错误信息
        if "error" in result:
            assert "同步失败" in result["error"]
        else:
            assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_sync_novel_full_to_gallery(self, ai_chat_service, test_novel):
        """测试全量同步小说到图库."""
        result = await ai_chat_service.sync_novel_full_to_gallery(test_novel.id)
        
        # 验证返回结果
        assert isinstance(result, dict)
        # 注意：如果 Neo4j 未连接，会返回错误信息
        if "error" in result:
            assert "同步失败" in result["error"]
        else:
            assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_get_novel_info_with_chapters(self, ai_chat_service, test_novel):
        """测试获取小说信息（包含章节内容）."""
        result = await ai_chat_service.get_novel_info(
            novel_id=str(test_novel.id),
            chapter_start=1,
            chapter_end=2,
            force_db=True
        )
        
        # 验证返回结果
        assert isinstance(result, dict)
        assert "error" not in result, f"获取小说信息失败：{result.get('error')}"
        
        # 验证基本信息
        assert result.get("title") == "测试小说"
        assert result.get("author") == "测试作者"
        
        # 验证章节信息
        assert "chapters" in result
        assert len(result["chapters"]) == 2
        
        # 验证章节内容
        for chapter in result["chapters"]:
            assert "chapter_number" in chapter
            assert "title" in chapter
            assert "content" in chapter
            assert "word_count" in chapter
            
            # 验证章节内容不为空
            assert chapter["content"], f"章节 {chapter['chapter_number']} 内容为空"

    @pytest.mark.asyncio
    async def test_get_novel_chapters_summary(self, ai_chat_service, test_novel):
        """测试获取章节摘要."""
        result = await ai_chat_service.get_novel_chapters_summary(
            novel_id=str(test_novel.id),
            chapter_numbers=[1, 2]
        )
        
        # 验证返回结果
        assert isinstance(result, dict)
        
        # 如果 Neo4j 未连接或 LLM 未配置，会返回错误
        if "error" in result:
            # 允许的错误
            allowed_errors = ["LLM 未配置", "Neo4j 未连接", "查询失败"]
            assert any(err in result["error"] for err in allowed_errors), \
                f"未知错误：{result['error']}"
        else:
            # 验证摘要信息
            assert "summaries" in result
            assert result["total_chapters_requested"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
