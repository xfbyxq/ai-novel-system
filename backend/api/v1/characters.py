"""
Character CRUD API endpoints.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.schemas.character import (
    CharacterCreate,
    CharacterUpdate,
    CharacterResponse,
    CharacterRelationshipResponse,
)
from core.models.character import Character
from core.models.novel import Novel

router = APIRouter(prefix="/novels/{novel_id}/characters", tags=["characters"])


@router.get("", response_model=list[CharacterResponse])
async def list_characters(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取指定小说的所有角色.
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()
    
    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")
    
    # Get characters
    query = select(Character).where(Character.novel_id == novel_id).order_by(Character.created_at)
    result = await db.execute(query)
    characters = result.scalars().all()
    
    return characters


@router.post("", response_model=CharacterResponse, status_code=201)
async def create_character(
    novel_id: UUID,
    character_in: CharacterCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    为指定小说创建新角色.
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()
    
    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")
    
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
    获取角色关系图数据(节点和边).
    
    返回格式:
    - nodes: 角色列表 [{id, name, role_type, ...}]
    - edges: 关系列表 [{source, target, relationship_type}]
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()
    
    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")
    
    # Get all characters
    query = select(Character).where(Character.novel_id == novel_id)
    result = await db.execute(query)
    characters = result.scalars().all()
    
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
                    edges.append({
                        "source": str(char.id),
                        "target": target_id,
                        "label": relationship_type,
                    })
    
    return CharacterRelationshipResponse(nodes=nodes, edges=edges)


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(
    novel_id: UUID,
    character_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取角色详情.
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
