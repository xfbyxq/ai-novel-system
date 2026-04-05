"""
Tests for character name version control functionality.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.character_name_version import (
    CharacterNameVersionService,
)
from core.models.character import Character


class TestCharacterNameVersionService:
    """角色名字版本服务测试."""

    @pytest.fixture
    async def sample_character(self, db_session: AsyncSession) -> Character:
        """创建测试角色."""
        character = Character(
            novel_id=uuid4(),
            name="苏叶",
            role_type="protagonist",
            gender="female",
        )
        db_session.add(character)
        await db_session.commit()
        await db_session.refresh(character)
        return character

    @pytest.fixture
    def version_service(self, db_session: AsyncSession) -> CharacterNameVersionService:
        """创建版本服务实例."""
        return CharacterNameVersionService(db_session)

    async def test_create_version_record(
        self,
        db_session: AsyncSession,
        sample_character: Character,
        version_service: CharacterNameVersionService,
    ):
        """测试创建名字版本记录."""
        version = await version_service.create_version_record(
            character_id=sample_character.id,
            old_name="苏叶",
            new_name="苏晚",
            changed_by="user_admin",
            reason="统一角色命名",
        )

        assert version.old_name == "苏叶"
        assert version.new_name == "苏晚"
        assert version.changed_by == "user_admin"
        assert version.reason == "统一角色命名"
        assert version.id is not None

    async def test_get_version_history(
        self,
        db_session: AsyncSession,
        sample_character: Character,
        version_service: CharacterNameVersionService,
    ):
        """测试获取版本历史."""
        await version_service.create_version_record(
            character_id=sample_character.id,
            old_name="苏叶",
            new_name="苏晚",
            changed_by="system",
            reason="第一次修改",
        )
        await version_service.create_version_record(
            character_id=sample_character.id,
            old_name="苏晚",
            new_name="苏瑶",
            changed_by="user_admin",
            reason="第二次修改",
        )

        history = await version_service.get_version_history(sample_character.id)

        assert len(history) == 2
        assert history[0].new_name == "苏瑶"
        assert history[1].new_name == "苏晚"

    async def test_compare_versions(
        self,
        db_session: AsyncSession,
        sample_character: Character,
        version_service: CharacterNameVersionService,
    ):
        """测试版本对比."""
        version1 = await version_service.create_version_record(
            character_id=sample_character.id,
            old_name="苏叶",
            new_name="苏晚",
            changed_by="system",
            reason="初始修改",
        )
        version2 = await version_service.create_version_record(
            character_id=sample_character.id,
            old_name="苏晚",
            new_name="苏瑶",
            changed_by="user_admin",
            reason="再次修改",
        )

        comparison = await version_service.compare_versions(version1.id, version2.id)

        assert "version_1" in comparison
        assert "version_2" in comparison
        assert "differences" in comparison
        assert comparison["differences"]["name_changed"] is True

    async def test_revert_to_version(
        self,
        db_session: AsyncSession,
        sample_character: Character,
        version_service: CharacterNameVersionService,
    ):
        """测试版本回溯."""
        version1 = await version_service.create_version_record(
            character_id=sample_character.id,
            old_name="苏叶",
            new_name="苏晚",
            changed_by="system",
            reason="第一次修改",
        )
        version2 = await version_service.create_version_record(
            character_id=sample_character.id,
            old_name="苏晚",
            new_name="苏瑶",
            changed_by="user_admin",
            reason="第二次修改",
        )

        reverted = await version_service.revert_to_version(
            character_id=sample_character.id,
            target_version_id=version1.id,
            reverted_by="system",
        )

        assert reverted is not None
        assert reverted.new_name == "苏晚"
        assert "回溯" in reverted.reason

    async def test_validate_name_change_no_history(
        self,
        db_session: AsyncSession,
        sample_character: Character,
        version_service: CharacterNameVersionService,
    ):
        """测试验证名字变更（无历史记录）."""
        validation = await version_service.validate_name_change(
            sample_character.id,
            "苏瑶",
        )

        assert validation["valid"] is True
        assert len(validation["warnings"]) == 0

    async def test_validate_name_change_with_history(
        self,
        db_session: AsyncSession,
        sample_character: Character,
        version_service: CharacterNameVersionService,
    ):
        """测试验证名字变更（有历史记录）."""
        await version_service.create_version_record(
            character_id=sample_character.id,
            old_name="苏叶",
            new_name="苏晚",
            changed_by="system",
            reason="修改",
        )

        validation = await version_service.validate_name_change(
            sample_character.id,
            "苏晚",
        )

        assert validation["valid"] is False
        assert len(validation["warnings"]) > 0
        assert "苏晚" in validation["previous_names"]

    async def test_get_current_name(
        self,
        db_session: AsyncSession,
        sample_character: Character,
        version_service: CharacterNameVersionService,
    ):
        """测试获取当前名字."""
        await version_service.create_version_record(
            character_id=sample_character.id,
            old_name="苏叶",
            new_name="苏晚",
            changed_by="system",
        )

        current_name = await version_service.get_current_name(sample_character.id)

        assert current_name == "苏晚"

    async def test_get_version_at_time(
        self,
        db_session: AsyncSession,
        sample_character: Character,
        version_service: CharacterNameVersionService,
    ):
        """测试获取指定时间点的版本."""
        now = datetime.now()
        await version_service.create_version_record(
            character_id=sample_character.id,
            old_name="苏叶",
            new_name="苏晚",
            changed_by="system",
        )

        version = await version_service.get_version_at_time(
            sample_character.id,
            now + timedelta(days=1),
        )

        assert version is not None
        assert version.new_name == "苏晚"


class TestCharacterNameVersionAPI:
    """角色名字版本 API 测试."""

    async def test_get_name_versions(
        self,
        client,
        test_novel,
        sample_character,
    ):
        """测试获取角色名字版本历史 API."""
        response = await client.get(
            f"/api/v1/novels/{test_novel.id}/characters/{sample_character.id}/name-versions",
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_create_name_version(
        self,
        client,
        test_novel,
        sample_character,
    ):
        """测试创建名字版本 API."""
        version_data = {
            "old_name": "苏叶",
            "new_name": "苏晚",
            "changed_by": "user_admin",
            "reason": "统一命名",
        }
        response = await client.post(
            f"/api/v1/novels/{test_novel.id}/characters/{sample_character.id}/name-versions",
            json=version_data,
        )
        assert response.status_code == 201
        assert response.json()["new_name"] == "苏晚"

    async def test_compare_versions_api(
        self,
        client,
        test_novel,
        sample_character,
    ):
        """测试版本对比 API."""
        version_id_1 = uuid4()
        version_id_2 = uuid4()

        response = await client.get(
            f"/api/v1/novels/{test_novel.id}/characters/{sample_character.id}/name-versions/compare",
            params={"version_id_1": version_id_1, "version_id_2": version_id_2},
        )
        assert response.status_code in [200, 404]

    async def test_revert_version_api(
        self,
        client,
        test_novel,
        sample_character,
    ):
        """测试版本回溯 API."""
        version_data = {
            "target_version_id": str(uuid4()),
            "reverted_by": "system",
        }
        response = await client.post(
            f"/api/v1/novels/{test_novel.id}/characters/{sample_character.id}/name-versions/revert",
            json=version_data,
        )
        assert response.status_code in [200, 404]

    async def test_validate_name_change_api(
        self,
        client,
        test_novel,
        sample_character,
    ):
        """测试名字变更验证 API."""
        response = await client.get(
            f"/api/v1/novels/{test_novel.id}/characters/{sample_character.id}/name-versions/validate",
            params={"new_name": "苏瑶"},
        )
        assert response.status_code == 200
        assert "valid" in response.json()


@pytest.fixture
def sample_character(db_session: AsyncSession, test_novel) -> Character:
    """创建测试角色 fixture."""
    character = Character(
        novel_id=test_novel.id,
        name="苏叶",
        role_type="protagonist",
        gender="female",
    )
    db_session.add(character)
    db_session.commit()
    db_session.refresh(character)
    return character
