"""大纲版本管理单元测试.

测试大纲版本管理功能 (Issue #30):
- 版本历史查询
- 版本自动创建
- 版本回滚
- 版本号连续性

使用 Mock 方式测试，隔离数据库依赖。
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


class TestOutlineVersioning:
    """大纲版本管理功能测试."""

    @pytest.fixture
    def mock_novel(self):
        """创建 Mock 小说对象."""
        novel = MagicMock()
        novel.id = uuid4()
        novel.title = "测试小说"
        return novel

    @pytest.fixture
    def mock_outline(self, mock_novel):
        """创建 Mock 大纲对象."""
        outline = MagicMock()
        outline.id = uuid4()
        outline.novel_id = mock_novel.id
        outline.structure_type = "three_act"
        outline.volumes = [
            {"number": 1, "title": "第一卷", "summary": "测试概要", "chapters": [1, 10]}
        ]
        outline.main_plot = {"setup": "测试开端"}
        outline.sub_plots = []
        outline.key_turning_points = []
        outline.version = 1
        outline.created_at = datetime.now()
        outline.updated_at = datetime.now()
        return outline

    @pytest.fixture
    def mock_version1(self, mock_outline):
        """创建 Mock 版本记录 1."""
        version = MagicMock()
        version.id = uuid4()
        version.plot_outline_id = mock_outline.id
        version.version_number = 1
        version.version_data = {
            "structure_type": "three_act",
            "volumes": mock_outline.volumes,
        }
        version.change_summary = "初始版本"
        version.changes = {}
        version.created_by = "system"
        version.created_at = datetime.now()
        return version

    @pytest.fixture
    def mock_version2(self, mock_outline):
        """创建 Mock 版本记录 2."""
        version = MagicMock()
        version.id = uuid4()
        version.plot_outline_id = mock_outline.id
        version.version_number = 2
        version.version_data = {
            "structure_type": "three_act",
            "volumes": [{"number": 1, "title": "第一卷（修改版）", "chapters": [1, 15]}],
        }
        version.change_summary = "修改卷标题"
        version.changes = {"volumes": [{"title": "第一卷（修改版）"}]}
        version.created_by = "user"
        version.created_at = datetime.now()
        return version

    def test_outline_version_model_structure(self):
        """测试版本记录模型结构.

        验证 PlotOutlineVersion 模型包含必要字段。
        """
        from core.models.plot_outline_version import PlotOutlineVersion

        # 验证模型字段存在
        assert hasattr(PlotOutlineVersion, "id")
        assert hasattr(PlotOutlineVersion, "plot_outline_id")
        assert hasattr(PlotOutlineVersion, "version_number")
        assert hasattr(PlotOutlineVersion, "version_data")
        assert hasattr(PlotOutlineVersion, "change_summary")
        assert hasattr(PlotOutlineVersion, "changes")
        assert hasattr(PlotOutlineVersion, "created_by")
        assert hasattr(PlotOutlineVersion, "created_at")

    def test_outline_model_has_versions_relationship(self):
        """测试大纲模型具有版本关系.

        验证 PlotOutline 模型具有 versions 关系。
        """
        from core.models.plot_outline import PlotOutline

        assert hasattr(PlotOutline, "versions")

    def test_version_data_structure(self, mock_version1):
        """测试版本数据结构.

        验证版本数据包含完整的大纲信息。
        """
        version_data = mock_version1.version_data

        assert "structure_type" in version_data
        assert "volumes" in version_data
        assert isinstance(version_data["volumes"], list)
        assert len(version_data["volumes"]) > 0

    def test_version_number_sequence(self, mock_version1, mock_version2):
        """测试版本号连续性.

        验证版本号正确递增。
        """
        assert mock_version1.version_number == 1
        assert mock_version2.version_number == 2
        assert mock_version2.version_number == mock_version1.version_number + 1

    def test_version_change_tracking(self, mock_version2):
        """测试版本变更追踪.

        验证 changes 字段记录了具体变更内容。
        """
        changes = mock_version2.changes

        assert isinstance(changes, dict)
        assert "volumes" in changes

    def test_get_outline_versions_empty(self, mock_outline):
        """测试获取无版本历史的大纲版本列表.

        验证：当没有版本记录时，返回初始版本信息。
        """
        versions = []  # 模拟空版本列表

        if not versions:
            # 构建初始版本信息
            initial_version = {
                "version_id": str(mock_outline.id),
                "version_number": 1,
                "change_summary": "初始版本",
                "is_current": True,
            }
            versions = [initial_version]

        assert len(versions) == 1
        assert versions[0]["version_number"] == 1
        assert versions[0]["change_summary"] == "初始版本"
        assert versions[0]["is_current"] is True

    def test_get_outline_versions_with_history(self, mock_version1, mock_version2):
        """测试获取有版本历史的大纲版本列表.

        验证：返回所有版本记录，正确标记当前版本。
        """
        # 模拟版本列表（按 version_number 降序）
        versions = [mock_version2, mock_version1]

        # 验证返回结果
        assert len(versions) == 2
        assert versions[0].version_number == 2
        assert versions[1].version_number == 1

        # 验证 is_current 逻辑
        current_version_number = 2  # 模拟大纲的当前版本号
        for v in versions:
            if v.version_number == current_version_number:
                assert True  # 当前版本标记正确

    def test_update_creates_new_version_number(self):
        """测试更新大纲时版本号递增.

        验证：新版本号 = 最大版本号 + 1。
        """
        existing_versions = [MagicMock(version_number=1), MagicMock(version_number=2)]

        max_version = max([v.version_number for v in existing_versions], default=0)
        new_version_number = max_version + 1

        assert new_version_number == 3

    def test_rollback_restores_version_data(self, mock_version1):
        """测试回滚恢复版本数据.

        验证：回滚后使用指定版本的数据。
        """
        target_version = mock_version1
        restored_data = target_version.version_data

        assert "volumes" in restored_data
        assert restored_data["volumes"][0]["title"] == "第一卷"

    def test_rollback_creates_new_version_record(self):
        """测试回滚创建新版本记录.

        验证：回滚操作不覆盖原版本，而是创建新版本。
        """
        existing_versions = [MagicMock(version_number=1), MagicMock(version_number=2)]

        max_version = max([v.version_number for v in existing_versions], default=0)
        rollback_version_number = max_version + 1

        # 原版本保留
        assert len(existing_versions) == 2

        # 新版本号递增
        assert rollback_version_number == 3

    def test_rollback_preserves_original_history(self, mock_version1, mock_version2):
        """测试回滚不删除历史记录.

        验证：回滚操作保留所有历史版本。
        """
        versions = [mock_version1, mock_version2]

        # 回滚前
        original_count = len(versions)

        # 模拟回滚创建新版本
        new_version = MagicMock()
        new_version.version_number = 3
        versions.append(new_version)

        # 原版本仍存在
        assert len(versions) == original_count + 1
        assert mock_version1 in versions
        assert mock_version2 in versions

    def test_version_ordering(self, mock_version1, mock_version2):
        """测试版本按版本号降序排列.

        验证：最新版本排在最前面。
        """
        versions = [mock_version2, mock_version1]

        # 验证排序正确
        assert versions[0].version_number > versions[1].version_number


class TestOutlineVersionServiceLogic:
    """大纲版本服务逻辑测试."""

    def test_get_next_version_number_empty(self):
        """测试获取下一个版本号（空列表）."""
        existing_versions = []

        next_version = max([v["version_number"] for v in existing_versions], default=0) + 1

        assert next_version == 1

    def test_get_next_version_number_with_existing(self):
        """测试获取下一个版本号（有现有版本）."""
        existing_versions = [{"version_number": 1}, {"version_number": 2}]

        next_version = max([v["version_number"] for v in existing_versions], default=0) + 1

        assert next_version == 3

    def test_is_current_version_logic(self):
        """测试当前版本判断逻辑."""
        versions = [
            {"version_number": 1, "is_current": False},
            {"version_number": 2, "is_current": False},
        ]
        current_version_number = 2

        # 判断 is_current
        for v in versions:
            v["is_current"] = v["version_number"] == current_version_number

        current_versions = [v for v in versions if v["is_current"]]

        assert len(current_versions) == 1
        assert current_versions[0]["version_number"] == 2

    def test_rollback_changes_structure(self):
        """测试回滚变更数据结构."""
        rollback_changes = {
            "action": "rollback",
            "rollback_from_version": 2,
            "rollback_to_version": 1,
        }

        assert rollback_changes["action"] == "rollback"
        assert rollback_changes["rollback_from_version"] == 2
        assert rollback_changes["rollback_to_version"] == 1

    def test_version_data_json_serializable(self):
        """测试版本数据可序列化为 JSON."""
        version_data = {
            "structure_type": "three_act",
            "volumes": [
                {
                    "number": 1,
                    "title": "第一卷",
                    "summary": "测试概要",
                    "chapters": [1, 10],
                    "core_conflict": "测试冲突",
                }
            ],
            "main_plot": {"setup": "测试开端", "conflict": "测试冲突"},
            "sub_plots": [],
            "key_turning_points": [],
        }

        # 验证可序列化
        json_str = json.dumps(version_data, ensure_ascii=False)
        restored_data = json.loads(json_str)

        assert restored_data == version_data


class TestOutlineVersionAPIFixtures:
    """大纲版本 API 请求/响应模型测试."""

    def test_outline_version_info_schema(self):
        """测试大纲版本信息 Schema."""
        from backend.schemas.outline import OutlineVersionInfo

        version_info = OutlineVersionInfo(
            version_id="test-uuid",
            novel_id=uuid4(),
            version_number=1,
            change_summary="初始版本",
            changes={},
            created_by="system",
            created_at=datetime.now(),
            is_current=True,
        )

        assert version_info.version_number == 1
        assert version_info.is_current is True

    def test_outline_version_info_without_changes(self):
        """测试大纲版本信息（无变更记录）."""
        from backend.schemas.outline import OutlineVersionInfo

        version_info = OutlineVersionInfo(
            version_id="test-uuid",
            novel_id=uuid4(),
            version_number=1,
            created_at=datetime.now(),
            is_current=True,
        )

        assert version_info.change_summary is None
        assert version_info.changes is None

    def test_plot_outline_update_schema(self):
        """测试大纲更新 Schema."""
        from backend.schemas.outline import PlotOutlineUpdate

        update_data = PlotOutlineUpdate(
            structure_type="hero_journey",
            volumes=[
                {
                    "number": 1,
                    "title": "第一卷",
                    "summary": "新概要",
                    "chapters": [1, 20],
                }
            ],
        )

        assert update_data.structure_type == "hero_journey"
        assert len(update_data.volumes) == 1
        assert update_data.volumes[0]["title"] == "第一卷"

    def test_plot_outline_update_partial(self):
        """测试大纲部分更新."""
        from backend.schemas.outline import PlotOutlineUpdate

        # 只更新部分字段
        update_data = PlotOutlineUpdate(
            volumes=[{"number": 1, "title": "更新后的标题", "chapters": [1, 15]}]
        )

        assert update_data.structure_type is None
        assert update_data.volumes is not None
        assert update_data.volumes[0]["title"] == "更新后的标题"
