"""
Character CRUD API endpoints.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.schemas.character import (
    CharacterCreate,
    CharacterRelationshipResponse,
    CharacterResponse,
    CharacterUpdate,
)
from core.models.character import Character
from core.models.novel import Novel
from core.models.character_name_version import CharacterNameVersionService

router = APIRouter(prefix="/novels/{novel_id}/characters", tags=["characters"])


@router.get("", response_model=list[CharacterResponse])
async def list_characters(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取指定小说的所有角色.

    返回角色列表，按创建时间正序排列（先创建的角色在前）。
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    # Get characters
    query = (
        select(Character)
        .where(Character.novel_id == novel_id)
        .order_by(Character.created_at)
    )
    result = await db.execute(query)
    characters = result.scalars().all()

    # 按名称去重（保留最早创建的记录），防止数据库中存在历史重复数据
    seen_names: set[str] = set()
    unique_characters = []
    for c in characters:
        name_lower = c.name.strip().lower()
        if name_lower not in seen_names:
            seen_names.add(name_lower)
            unique_characters.append(c)

    return unique_characters


@router.post("", response_model=CharacterResponse, status_code=201)
async def create_character(
    novel_id: UUID,
    character_in: CharacterCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    为指定小说创建新角色.

    创建角色后可在 relationships 字段中指定与其他角色的关系。
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    # 检查同名角色是否已存在（不区分大小写）
    existing_check = await db.execute(
        select(Character).where(
            Character.novel_id == novel_id,
            func.lower(Character.name) == character_in.name.strip().lower(),
        )
    )
    if existing_check.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"角色「{character_in.name}」在该小说中已存在",
        )

    # Create character
    character = Character(**character_in.model_dump(), novel_id=novel_id)
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character


@router.get("/relationships", response_model=CharacterRelationshipResponse)
async def get_character_relationships(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取角色关系图数据（图论格式）.

    返回用于前端可视化的关系图数据结构：
    - **nodes**: 角色节点列表，每个节点包含 id、name、role_type 等信息
    - **edges**: 关系边列表，表示从 source 角色到 target 角色的有向关系

    关系数据来源于各角色的 relationships 字段。
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    # Get all characters
    query = (
        select(Character)
        .where(Character.novel_id == novel_id)
        .order_by(Character.created_at)
    )
    result = await db.execute(query)
    all_characters = result.scalars().all()

    # 按名称去重（保留最早创建的记录），防止重复角色产生孤立节点
    seen_names: set[str] = set()
    characters = []
    for c in all_characters:
        name_lower = c.name.strip().lower()
        if name_lower not in seen_names:
            seen_names.add(name_lower)
            characters.append(c)

    # Create name to ID mapping
    name_to_id = {char.name: str(char.id) for char in characters}

    # Build nodes
    nodes = [
        {
            "id": str(char.id),
            "name": char.name,
            "role_type": char.role_type,
            "gender": char.gender,
            "avatar_url": char.avatar_url,
        }
        for char in characters
    ]

    # Build edges from relationships
    edges = []
    for char in characters:
        if char.relationships:
            for target_name, relationship_type in char.relationships.items():
                # Convert target name to UUID (strip whitespace)
                target_id = name_to_id.get(target_name.strip())
                if target_id:  # Only add edge if target character exists
                    edges.append(
                        {
                            "source": str(char.id),
                            "target": target_id,
                            "label": relationship_type,
                        }
                    )

    return CharacterRelationshipResponse(nodes=nodes, edges=edges)


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(
    novel_id: UUID,
    character_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取角色详情.

    返回指定角色的完整信息。
    """
    query = select(Character).where(
        Character.id == character_id,
        Character.novel_id == novel_id,
    )
    result = await db.execute(query)
    character = result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail=f"角色 {character_id} 未找到")

    return character


@router.patch("/{character_id}", response_model=CharacterResponse)
async def update_character(
    novel_id: UUID,
    character_id: UUID,
    character_in: CharacterUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    更新角色信息.

    仅更新请求体中提供的字段，未提供的字段保持不变。
    """
    query = select(Character).where(
        Character.id == character_id,
        Character.novel_id == novel_id,
    )
    result = await db.execute(query)
    character = result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail=f"角色 {character_id} 未找到")

    # Update only provided fields
    update_data = character_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(character, field, value)

    await db.commit()
    await db.refresh(character)
    return character


@router.delete("/{character_id}", status_code=204)
async def delete_character(
    novel_id: UUID,
    character_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    删除角色.

    删除后，其他角色的 relationships 中对此角色的引用不会自动更新。
    """
    query = select(Character).where(
        Character.id == character_id,
        Character.novel_id == novel_id,
    )
    result = await db.execute(query)
    character = result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail=f"角色 {character_id} 未找到")

    await db.delete(character)
    await db.commit()


@router.get("/{character_id}/name-versions", response_model=list)
async def get_character_name_versions(
    novel_id: UUID,
    character_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取角色名字版本历史.

    返回角色名字的变更历史记录，包括每次变更的时间、操作人和原因。
    """
    query = select(Character).where(
        Character.id == character_id,
        Character.novel_id == novel_id,
    )
    result = await db.execute(query)
    character = result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail=f"角色 {character_id} 未找到")

    version_service = CharacterNameVersionService(db)
    versions = await version_service.get_version_history(character_id)

    return [
        {
            "id": str(version.id),
            "old_name": version.old_name,
            "new_name": version.new_name,
            "changed_at": version.changed_at.isoformat(),
            "changed_by": version.changed_by,
            "reason": version.reason,
        }
        for version in versions
    ]


@router.post("/{character_id}/name-versions", response_model=dict, status_code=201)
async def create_character_name_version(
    novel_id: UUID,
    character_id: UUID,
    version_data: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    创建角色名字版本记录.

    记录角色名字的变更，包括旧名字、新名字、变更人和原因。
    """
    query = select(Character).where(
        Character.id == character_id,
        Character.novel_id == novel_id,
    )
    result = await db.execute(query)
    character = result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail=f"角色 {character_id} 未找到")

    old_name = version_data.get("old_name", character.name)
    new_name = version_data.get("new_name")
    changed_by = version_data.get("changed_by", "system")
    reason = version_data.get("reason")

    if not new_name:
        raise HTTPException(status_code=400, detail="new_name 是必填字段")

    version_service = CharacterNameVersionService(db)
    version = await version_service.create_version_record(
        character_id=character_id,
        old_name=old_name,
        new_name=new_name,
        changed_by=changed_by,
        reason=reason,
    )

    return {
        "id": str(version.id),
        "old_name": version.old_name,
        "new_name": version.new_name,
        "changed_at": version.changed_at.isoformat(),
        "changed_by": version.changed_by,
        "reason": version.reason,
    }


@router.get("/{character_id}/name-versions/compare")
async def compare_character_name_versions(
    novel_id: UUID,
    character_id: UUID,
    version_id_1: UUID,
    version_id_2: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    对比两个名字版本的差异.

    返回两个版本之间的差异信息。
    """
    query = select(Character).where(
        Character.id == character_id,
        Character.novel_id == novel_id,
    )
    result = await db.execute(query)
    character = result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail=f"角色 {character_id} 未找到")

    version_service = CharacterNameVersionService(db)
    comparison = await version_service.compare_versions(version_id_1, version_id_2)

    return comparison


@router.post("/{character_id}/name-versions/revert")
async def revert_character_name_version(
    novel_id: UUID,
    character_id: UUID,
    version_data: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    回溯到指定的名字版本.

    将角色名字恢复到历史版本，并创建新的版本记录。
    """
    query = select(Character).where(
        Character.id == character_id,
        Character.novel_id == novel_id,
    )
    result = await db.execute(query)
    character = result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail=f"角色 {character_id} 未找到")

    target_version_id = version_data.get("target_version_id")
    reverted_by = version_data.get("reverted_by", "system")

    if not target_version_id:
        raise HTTPException(status_code=400, detail="target_version_id 是必填字段")

    version_service = CharacterNameVersionService(db)
    reverted_version = await version_service.revert_to_version(
        character_id=character_id,
        target_version_id=UUID(target_version_id),
        reverted_by=reverted_by,
    )

    if not reverted_version:
        raise HTTPException(
            status_code=404, detail=f"目标版本 {target_version_id} 未找到"
        )

    return {
        "id": str(reverted_version.id),
        "old_name": reverted_version.old_name,
        "new_name": reverted_version.new_name,
        "changed_at": reverted_version.changed_at.isoformat(),
        "changed_by": reverted_version.changed_by,
        "reason": reverted_version.reason,
        "message": f"成功回溯到版本 {target_version_id}",
    }


@router.get("/{character_id}/name-versions/validate")
async def validate_character_name_change(
    novel_id: UUID,
    character_id: UUID,
    new_name: str,
    db: AsyncSession = Depends(get_db),
):
    """
    验证角色名字变更是否合理.

    检查新名字是否与历史版本冲突，并提供警告信息。
    """
    query = select(Character).where(
        Character.id == character_id,
        Character.novel_id == novel_id,
    )
    result = await db.execute(query)
    character = result.scalar_one_or_none()

    if not character:
        raise HTTPException(status_code=404, detail=f"角色 {character_id} 未找到")

    version_service = CharacterNameVersionService(db)
    validation = await version_service.validate_name_change(character_id, new_name)

    return validation
