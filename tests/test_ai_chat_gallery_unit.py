"""测试 AI 助手图库功能的单元测试（不依赖数据库）."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from backend.services.ai_chat_service import AiChatService


class TestAiChatGalleryNoDB:
    """AI 助手图库功能测试（不依赖数据库）."""

    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话."""
        db = MagicMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def ai_chat_service_no_gallery(self, mock_db):
        """AI 助手服务 fixture（图库功能禁用）."""
        with patch('backend.services.ai_chat_service.Neo4jClient') as mock_neo4j:
            mock_neo4j.side_effect = Exception("Neo4j 未配置")
            
            with patch('backend.services.ai_chat_service.GraphQueryService'):
                with patch('backend.services.ai_chat_service.GraphSyncService'):
                    service = AiChatService(mock_db)
                    return service

    @pytest.mark.asyncio
    async def test_query_character_network_no_gallery(self, ai_chat_service_no_gallery):
        """测试图库未启用时查询角色关系网络."""
        novel_id = uuid4()
        result = await ai_chat_service_no_gallery.query_character_network(novel_id)
        
        assert isinstance(result, dict)
        assert "error" in result
        assert "图库功能未启用" in result["error"]

    @pytest.mark.asyncio
    async def test_query_world_setting_map_no_gallery(self, ai_chat_service_no_gallery):
        """测试图库未启用时查询世界观设定地图."""
        novel_id = uuid4()
        result = await ai_chat_service_no_gallery.query_world_setting_map(novel_id)
        
        assert isinstance(result, dict)
        assert "error" in result
        assert "图库功能未启用" in result["error"]

    @pytest.mark.asyncio
    async def test_query_plot_timeline_no_gallery(self, ai_chat_service_no_gallery):
        """测试图库未启用时查询情节时间线."""
        novel_id = uuid4()
        result = await ai_chat_service_no_gallery.query_plot_timeline(novel_id)
        
        assert isinstance(result, dict)
        assert "error" in result
        assert "图库功能未启用" in result["error"]

    @pytest.mark.asyncio
    async def test_query_gallery_no_gallery(self, ai_chat_service_no_gallery):
        """测试图库未启用时查询图库."""
        novel_id = uuid4()
        result = await ai_chat_service_no_gallery.query_gallery(novel_id, "character_network")
        
        assert isinstance(result, dict)
        assert "error" in result
        assert "图库功能未启用" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_chapter_to_gallery_no_gallery(self, ai_chat_service_no_gallery):
        """测试图库未启用时同步章节."""
        novel_id = uuid4()
        result = await ai_chat_service_no_gallery.sync_chapter_to_gallery(
            novel_id=novel_id,
            chapter_number=1,
            chapter_content="测试内容"
        )
        
        assert isinstance(result, dict)
        assert result["success"] is False
        assert "图库功能未启用" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_novel_full_to_gallery_no_gallery(self, ai_chat_service_no_gallery):
        """测试图库未启用时全量同步小说."""
        novel_id = uuid4()
        result = await ai_chat_service_no_gallery.sync_novel_full_to_gallery(novel_id)
        
        assert isinstance(result, dict)
        assert result["success"] is False
        assert "图库功能未启用" in result["error"]

    @pytest.mark.asyncio
    async def test_query_gallery_unknown_type(self, ai_chat_service_no_gallery):
        """测试查询未知类型."""
        novel_id = uuid4()
        result = await ai_chat_service_no_gallery.query_gallery(novel_id, "unknown_type")
        
        # 注意：未知类型会先检查图库是否启用
        assert isinstance(result, dict)
        assert "error" in result
        # 可能返回"图库功能未启用"或"未知的查询类型"
        assert any(err in result["error"] for err in ["图库功能未启用", "未知的查询类型"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
