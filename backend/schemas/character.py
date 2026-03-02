"""角色相关的 Pydantic schemas"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CharacterCreate(BaseModel):
    """创建角色的请求模型"""
    name: str = Field(..., description="角色名称", examples=["李逍遥"])
    role_type: Optional[str] = Field(
        default=None,
        description="角色类型：主角、配角、反派、龙套等",
        examples=["主角", "配角", "反派"]
    )
    gender: Optional[str] = Field(default=None, description="性别：男、女、未知")
    age: Optional[int] = Field(default=None, description="年龄")
    appearance: Optional[str] = Field(
        default=None, description="外貌描述"
    )
    personality: Optional[str] = Field(
        default=None, description="性格描述"
    )
    background: Optional[str] = Field(
        default=None, description="背景故事"
    )
    goals: Optional[str] = Field(default=None, description="目标动机，如追求、愿望、驱动力等")
    abilities: Optional[dict] = Field(
        default=None,
        description="能力属性，格式: {能力名: 等级或描述}，如 {'剑术': 'S级', '内力': '深厚'}",
        examples=[{"剑术": "S级", "内力": "深厚", "速度": "极快"}]
    )
    relationships: Optional[dict] = Field(
        default=None,
        description="人物关系，格式: {角色名: 关系类型}",
        examples=[{"李云龙": "师傅", "王小红": "妻子", "黑龙王": "宿敌"}]
    )


class CharacterUpdate(BaseModel):
    """更新角色的请求模型（仅更新提供的字段）"""
    name: Optional[str] = Field(default=None, description="角色名称")
    role_type: Optional[str] = Field(default=None, description="角色类型：主角、配角、反派等")
    gender: Optional[str] = Field(default=None, description="性别")
    age: Optional[int] = Field(default=None, description="年龄")
    appearance: Optional[str] = Field(default=None, description="外貌描述")
    personality: Optional[str] = Field(default=None, description="性格描述")
    background: Optional[str] = Field(default=None, description="背景故事")
    goals: Optional[str] = Field(default=None, description="目标动机")
    abilities: Optional[dict] = Field(
        default=None,
        description="能力属性，格式: {能力名: 等级或描述}"
    )
    relationships: Optional[dict] = Field(
        default=None,
        description="人物关系，格式: {关系人名字: 关系类型}"
    )


class CharacterResponse(BaseModel):
    """角色响应模型"""
    id: UUID = Field(..., description="角色唯一标识符")
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
    growth_arc: Optional[dict] = Field(default=None, description="成长轨迹/角色弧线")
    avatar_url: Optional[str] = Field(default=None, description="角色头像URL")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "novel_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "李逍遥",
                "role_type": "主角",
                "gender": "男",
                "age": 25,
                "appearance": "白衣翩翩，剑眉星目，身材修长",
                "personality": "正义感强，但有些鲁莽冲动",
                "background": "出身平凡农家，机缘巧合踏入修仙界",
                "goals": "成为天下第一剑客，守护苍生",
                "abilities": {"剑术": "S级", "内力": "深厚"},
                "relationships": {"李云龙": "师傅", "王小红": "妻子"},
                "growth_arc": {"起点": "普通少年", "转折": "获得神剑", "高潮": "成就剑圣"},
                "avatar_url": "https://example.com/avatar.jpg",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-03-01T12:00:00Z"
            }
        }
    )


class CharacterNode(BaseModel):
    """角色关系图节点（用于图形化展示）"""
    id: UUID = Field(..., description="角色ID")
    name: str = Field(..., description="角色名称")
    role_type: Optional[str] = Field(default=None, description="角色类型")


class CharacterEdge(BaseModel):
    """角色关系图边（表示两个角色之间的关系）"""
    source: UUID = Field(..., description="源角色ID（关系的主体）")
    target: UUID = Field(..., description="目标角色ID（关系的对象）")
    label: str = Field(..., description="关系标签，如：师傅、徒弟、父子、敌人等")


class CharacterRelationshipResponse(BaseModel):
    """角色关系图响应模型（图论格式，用于前端可视化）"""
    nodes: list[CharacterNode] = Field(..., description="角色节点列表")
    edges: list[CharacterEdge] = Field(..., description="关系边列表（有向边，从source指向target）")
