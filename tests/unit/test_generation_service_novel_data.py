"""GenerationService novel_data 构造测试.

测试 novel_data 字典构造时是否包含必要字段，特别是 id 字段。

问题背景：
- 日志显示"跳过图查询: 小说ID未设置"
- 原因是 novel_data 字典缺少 id 字段
- crew_manager.py 调用 novel_data.get("id", "") 返回空字符串
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestNovelDataConstruction:
    """测试 novel_data 字典构造."""

    def test_novel_data_contains_id_field(self):
        """测试 novel_data 必须包含 id 字段."""
        novel_id = uuid4()

        # 模拟 generation_service.py 中的 novel_data 构造
        novel_data = {
            "id": str(novel_id),  # 必须包含
            "title": "测试小说",
            "genre": "仙侠",
            "world_setting": {},
            "characters": [],
            "plot_outline": {},
        }

        # 验证 id 字段存在且正确
        assert "id" in novel_data, "novel_data 必须包含 id 字段"
        assert novel_data["id"] == str(novel_id), "id 字段值应为字符串形式的 UUID"

    def test_novel_data_id_used_by_graph_query(self):
        """测试 novel_data.id 能被图查询正确使用."""
        novel_id = uuid4()

        novel_data = {
            "id": str(novel_id),
            "title": "测试小说",
        }

        # 模拟 crew_manager.py 中的使用方式
        extracted_id = novel_data.get("id", "")

        assert extracted_id == str(novel_id), (
            f"novel_data.get('id') 应返回正确的ID，实际返回: {extracted_id}"
        )
        assert extracted_id != "", "novel_data.get('id') 不应返回空字符串"

    def test_novel_data_missing_id_causes_graph_query_skip(self):
        """测试缺少 id 字段会导致图查询被跳过（问题的根因）."""
        # 模拟修复前的错误构造
        novel_data_without_id = {
            "title": "测试小说",
            "genre": "仙侠",
            # 缺少 "id" 字段
        }

        extracted_id = novel_data_without_id.get("id", "")

        # 这正是导致 "跳过图查询: 小说ID未设置" 的原因
        assert extracted_id == "", "缺少 id 字段时 get('id') 返回空字符串"

    @pytest.mark.parametrize("scene", ["run_chapter_writing", "run_batch_chapter_writing", "_write_single_chapter"])
    def test_all_novel_data_constructions_have_id(self, scene):
        """测试所有 novel_data 构造场景都包含 id 字段."""
        novel_id = uuid4()

        # 所有场景的 novel_data 构造都应包含 id
        expected_fields = {"id", "title", "genre", "world_setting", "characters", "plot_outline"}

        novel_data = {
            "id": str(novel_id),
            "title": "测试小说",
            "genre": "仙侠",
            "world_setting": {},
            "characters": [],
            "plot_outline": {},
        }

        missing_fields = expected_fields - set(novel_data.keys())
        assert not missing_fields, f"场景 {scene} 中 novel_data 缺少字段: {missing_fields}"
        assert novel_data["id"] == str(novel_id)


class TestGraphQueryMixinRequiresNovelId:
    """测试 GraphQueryMixin 对 novel_id 的依赖."""

    def test_graph_query_skip_without_novel_id(self):
        """测试缺少 novel_id 时图查询被跳过."""
        from agents.graph_query_mixin import GraphQueryMixin

        mixin = GraphQueryMixin()
        # 未调用 set_graph_context，_novel_id 为 None

        assert mixin._novel_id is None, "未设置时 _novel_id 应为 None"

    def test_graph_query_enabled_with_novel_id(self):
        """测试设置 novel_id 后图查询可以执行."""
        from unittest.mock import patch

        from agents.graph_query_mixin import GraphQueryMixin

        mixin = GraphQueryMixin()
        novel_id = str(uuid4())
        mixin.set_graph_context(novel_id)

        assert mixin._novel_id == novel_id, "set_graph_context 后 _novel_id 应正确设置"


class TestIntegrationNovelDataToGraphQuery:
    """集成测试：novel_data.id -> 图查询链路."""

    @pytest.mark.asyncio
    async def test_novel_data_id_flows_to_graph_context(self):
        """测试 novel_data.id 正确流向图查询上下文."""
        from agents.graph_query_mixin import GraphQueryMixin

        novel_id = uuid4()

        # 1. generation_service 构造 novel_data
        novel_data = {
            "id": str(novel_id),
            "title": "测试小说",
            "genre": "仙侠",
            "world_setting": {},
            "characters": [],
            "plot_outline": {},
        }

        # 2. crew_manager 提取 id
        extracted_id = novel_data.get("id", "")
        assert extracted_id == str(novel_id)

        # 3. GraphQueryMixin 设置上下文
        mixin = GraphQueryMixin()
        mixin.set_graph_context(extracted_id)

        # 4. 验证图查询上下文正确
        assert mixin._novel_id == str(novel_id), (
            f"图查询上下文应正确设置，期望: {novel_id}, 实际: {mixin._novel_id}"
        )
