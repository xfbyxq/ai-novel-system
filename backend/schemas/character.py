"""角色相关的 Pydantic schemas（带输入验证）."""

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CharacterCreate(BaseModel):
    """创建角色的请求模型（带输入验证）."""

    name: str = Field(
        ...,
        description="角色名称",
        examples=["李逍遥"],
        min_length=1,
        max_length=50,
    )
    role_type: Optional[str] = Field(
        default=None,
        description="角色类型：主角、配角、反派、龙套等",
        examples=["主角", "配角", "反派"],
        max_length=50,
    )
    gender: Optional[str] = Field(
        default=None,
        description="性别：男、女、未知",
        max_length=20,
    )
    age: Optional[int] = Field(
        default=None,
        description="年龄",
        ge=0,
        le=150,
    )
    appearance: Optional[str] = Field(
        default=None,
        description="外貌描述",
        max_length=2000,
    )
    personality: Optional[str] = Field(
        default=None,
        description="性格描述",
        max_length=2000,
    )
    background: Optional[str] = Field(
        default=None,
        description="背景故事",
        max_length=5000,
    )
    goals: Optional[str] = Field(
        default=None,
        description="目标动机，如追求、愿望、驱动力等",
        max_length=2000,
    )
    abilities: Optional[dict] = Field(
        default=None,
        description="能力属性，格式：{能力名：等级或描述}，如 {'剑术': 'S 级', '内力': '深厚'}",
        examples=[{"剑术": "S 级", "内力": "深厚", "速度": "极快"}],
    )
    relationships: Optional[dict] = Field(
        default=None,
        description="人物关系，格式：{角色名：关系类型}",
        examples=[{"李云龙": "师傅", "王小红": "妻子", "黑龙王": "宿敌"}],
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证角色名称."""
        if not v.strip():
            raise ValueError("角色名称不能为空或只包含空白字符")
        if re.search(r'[<>{}|\\^`]', v):
            raise ValueError("角色名称包含非法字符")
        return v.strip()

    @field_validator("role_type")
    @classmethod
    def validate_role_type(cls, v: Optional[str]) -> Optional[str]:
        """验证角色类型."""
        if v is not None and not v.strip():
            raise ValueError("角色类型不能为空字符串")
        return v.strip() if v else v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        """验证性别."""
        if v is not None:
            v = v.strip()
            if v and v not in ["男", "女", "未知"]:
                raise ValueError("性别必须是：男、女、未知")
            return v if v else None
        return v


class CharacterUpdate(BaseModel):
    """更新角色的请求模型（仅更新提供的字段，带输入验证）."""

    name: Optional[str] = Field(
        default=None,
        description="角色名称",
        min_length=1,
        max_length=50,
    )
    role_type: Optional[str] = Field(
        default=None,
        description="角色类型：主角、配角、反派等",
        max_length=50,
    )
    gender: Optional[str] = Field(
        default=None,
        description="性别",
        max_length=20,
    )
    age: Optional[int] = Field(
        default=None,
        description="年龄",
        ge=0,
        le=150,
    )
    appearance: Optional[str] = Field(
        default=None,
        description="外貌描述",
        max_length=2000,
    )
    personality: Optional[str] = Field(
        default=None,
        description="性格描述",
        max_length=2000,
    )
    background: Optional[str] = Field(
        default=None,
        description="背景故事",
        max_length=5000,
    )
    goals: Optional[str] = Field(
        default=None,
        description="目标动机",
        max_length=2000,
    )
    abilities: Optional[dict] = Field(
        default=None,
        description="能力属性，格式：{能力名：等级或描述}",
    )
    relationships: Optional[dict] = Field(
        default=None,
        description="人物关系，格式：{关系人名字：关系类型}",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """验证角色名称."""
        if v is not None:
            if not v.strip():
                raise ValueError("角色名称不能为空或只包含空白字符")
            if re.search(r'[<>{}|\\^`]', v):
                raise ValueError("角色名称包含非法字符")
            return v.strip()
        return v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        """验证性别."""
        if v is not None:
            v = v.strip()
            if v and v not in ["男", "女", "未知"]:
                raise ValueError("性别必须是：男、女、未知")
            return v if v else None
        return v


class CharacterResponse(BaseModel):
    """角色响应模型."""

    id: UUID = Field(..., description="角色唯一标识符")
    novel_id: UUID = Field(..., description="所属小说 ID")
    name: str = Field(..., description="角色名称")
    role_type: Optional[str] = Field(default=None, description="角色类型")
    gender: Optional[str] = Field(default=None, description="性别")
    age: Optional[int] = Field(default=None, description="年龄", ge=0, le=150)
    appearance: Optional[str] = Field(default=None, description="外貌描述")
    personality: Optional[str] = Field(default=None, description="性格描述")
    background: Optional[str] = Field(default=None, description="背景故事")
    goals: Optional[str] = Field(default=None, description="目标动机")
    abilities: Optional[dict] = Field(default=None, description="能力属性")
    relationships: Optional[dict] = Field(default=None, description="人物关系")
    growth_arc: Optional[dict] = Field(default=None, description="成长轨迹/角色弧线")
    avatar_url: Optional[str] = Field(
        default=None,
        description="角色头像 URL",
        max_length=500,
    )
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "novel_id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "李逍遥",
                "role_type": "主角",
                "gender": "男",
                "age": 18,
                "appearance": "身穿青色长衫，手持长剑",
                "personality": "豪爽、正直、重情重义",
                "background": "余杭镇客栈小伙计，后拜入蜀山剑派",
                "goals": "成为天下第一剑客",
                "abilities": {"剑术": "S 级", "内力": "深厚"},
                "relationships": {"赵灵儿": "妻子", "林月如": "红颜知己"},
                "growth_arc": {"起点": "客栈小伙计", "终点": "蜀山剑仙"},
                "avatar_url": "https://example.com/avatar.jpg",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-03-01T12:00:00Z",
            }
        },
    )


class CharacterListResponse(BaseModel):
    """角色列表响应模型（分页）."""

    items: list[CharacterResponse] = Field(..., description="角色列表")
    total: int = Field(..., description="符合条件的角色总数", ge=0)
    page: Optional[int] = Field(default=None, description="当前页码", ge=1)
    page_size: Optional[int] = Field(default=None, description="每页数量", ge=1, le=100)

class CharacterNode(BaseModel):
    """角色关系图节点（用于图形化展示）."""

    id: UUID = Field(..., description="角色 ID")
    name: str = Field(..., description="角色名称")
    role_type: Optional[str] = Field(default=None, description="角色类型")


class CharacterEdge(BaseModel):
    """角色关系图边（表示两个角色之间的关系）."""

    source: UUID = Field(..., description="源角色 ID（关系的主体）")
    target: UUID = Field(..., description="目标角色 ID（关系的对象）")
    label: str = Field(..., description="关系标签，如：师傅、徒弟、父子、敌人等")


class CharacterRelationshipResponse(BaseModel):
    """角色关系图响应模型（图论格式，用于前端可视化）."""

    nodes: list[CharacterNode] = Field(..., description="角色节点列表")
    edges: list[CharacterEdge] = Field(
        ..., description="关系边列表（有向边，从 source 指向 target）"
    )
