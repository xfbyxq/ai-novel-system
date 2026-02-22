"""角色相关的 Pydantic schemas"""
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CharacterCreate(BaseModel):
    """创建角色的请求模型"""
    name: str = Field(..., description="角色名称")
    role_type: Optional[str] = Field(default=None, description="角色类型(主角/配角/反派等)")
    gender: Optional[str] = Field(default=None, description="性别")
    age: Optional[int] = Field(default=None, description="年龄")
    appearance: Optional[str] = Field(default=None, description="外貌描述")
    personality: Optional[str] = Field(default=None, description="性格描述")
    background: Optional[str] = Field(default=None, description="背景故事")
    goals: Optional[str] = Field(default=None, description="目标动机")
    abilities: Optional[dict] = Field(default=None, description="能力属性")
    relationships: Optional[dict] = Field(default=None, description="人物关系")


class CharacterUpdate(BaseModel):
    """更新角色的请求模型"""
    name: Optional[str] = Field(default=None, description="角色名称")
    role_type: Optional[str] = Field(default=None, description="角色类型")
    gender: Optional[str] = Field(default=None, description="性别")
    age: Optional[int] = Field(default=None, description="年龄")
    appearance: Optional[str] = Field(default=None, description="外貌描述")
    personality: Optional[str] = Field(default=None, description="性格描述")
    background: Optional[str] = Field(default=None, description="背景故事")
    goals: Optional[str] = Field(default=None, description="目标动机")
    abilities: Optional[dict] = Field(default=None, description="能力属性")
    relationships: Optional[dict] = Field(default=None, description="人物关系")


class CharacterResponse(BaseModel):
    """角色响应模型"""
    id: UUID = Field(..., description="角色ID")
    novel_id: UUID = Field(..., description="所属小说ID")
    name: str = Field(..., description="角色名称")
    role_type: Optional[str] = Field(default=None, description="角色类型")
    gender: Optional[str] = Field(default=None, description="性别")
    age: Optional[int] = Field(default=None, description="年龄")
    appearance: Optional[str] = Field(default=None, description="外貌描述")
    personality: Optional[str] = Field(default=None, description="性格描述")
    background: Optional[str] = Field(default=None, description="背景故事")
    goals: Optional[str] = Field(default=None, description="目标动机")
    abilities: Optional[dict] = Field(default=None, description="能力属性")
    relationships: Optional[dict] = Field(default=None, description="人物关系")
    growth_arc: Optional[dict] = Field(default=None, description="成长轨迹")
    avatar_url: Optional[str] = Field(default=None, description="头像URL")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    model_config = ConfigDict(from_attributes=True)


class CharacterNode(BaseModel):
    """角色关系图节点"""
    id: UUID = Field(..., description="角色ID")
    name: str = Field(..., description="角色名称")
    role_type: Optional[str] = Field(default=None, description="角色类型")


class CharacterEdge(BaseModel):
    """角色关系图边"""
    source: UUID = Field(..., description="源角色ID")
    target: UUID = Field(..., description="目标角色ID")
    label: str = Field(..., description="关系标签")


class CharacterRelationshipResponse(BaseModel):
    """角色关系图响应模型"""
    nodes: list[CharacterNode] = Field(..., description="节点列表")
    edges: list[CharacterEdge] = Field(..., description="边列表")
