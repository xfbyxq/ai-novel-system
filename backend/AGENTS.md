# BACKEND 模块

**FastAPI REST API层**: 提供小说系统的所有HTTP接口

## OVERVIEW

FastAPI应用，含API路由、服务层、Schema验证。57个Python文件，12个路由。

## STRUCTURE

```
backend/
├── main.py              # FastAPI应用入口
├── config.py            # 配置管理 (Settings)
├── api/v1/              # API路由 (12个端点)
│   ├── novels.py        # 小说CRUD
│   ├── characters.py    # 角色管理
│   ├── chapters.py     # 章节管理
│   ├── outlines.py     # 大纲管理
│   ├── generation.py   # 生成任务
│   ├── ai_chat.py      # AI对话
│   └── publishing.py   # 发布系统
├── schemas/            # Pydantic模型
├── services/            # 业务逻辑 (21个)
├── middleware/         # 中间件
├── dependencies/       # 依赖注入
└── utils/              # 工具函数
```

## WHERE TO LOOK

| 任务 | 文件 | 说明 |
|------|------|------|
| 新增API | `api/v1/{resource}.py` | 参考现有路由模式 |
| 业务逻辑 | `services/` | 新服务放此目录 |
| 数据验证 | `schemas/` | Request/Response模型 |
| 依赖注入 | `dependencies/` | `get_db`, `get_current_user`等 |
| 配置变更 | `config.py` | Settings类添加新配置 |

## API ROUTE PATTERN

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/novels", tags=["novels"])

@router.get("", response_model=NovelListResponse)
async def list_novels(
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """获取小说列表（分页）."""
    ...
```

## SCHEMA PATTERN

```python
from pydantic import BaseModel, Field
from uuid import UUID

class NovelCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    genre: str
    
    model_config = ConfigDict(from_attributes=True)
```

## SERVICE PATTERN

```python
from core.exceptions import NotFoundError

class NovelService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_novel(self, novel_id: UUID) -> Novel:
        result = await self.db.get(Novel, novel_id)
        if not result:
            raise NotFoundError(resource_type="小说", resource_id=str(novel_id))
        return result
```

## CONVENTIONS

- **Response Model**: 必须使用Pydantic schema
- **依赖注入**: 使用 `Depends(get_db)`
- **异常处理**: 业务异常使用 `core.exceptions`
- **异步优先**: 所有I/O操作使用 `async/await`
- **日志**: `from core.logging_config import logger`

## TESTING

```bash
# 使用test_client fixture
@pytest.fixture
async def test_client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with httpx.AsyncClient(...) as client:
        yield client
```

## ANTI-PATTERNS

- **禁止裸except**: 必须指定异常类型
- **禁止直接返回ORM对象**: 必须通过schema转换
- **禁止硬编码密码**: config.py第80行禁止
