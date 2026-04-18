# CORE 模块

**共享基础设施**: 数据库、异常、日志、通用工具

## OVERVIEW

共享基础设施，被所有模块依赖。含SQLAlchemy ORM、异常层次、日志配置。

## STRUCTURE

```
core/
├── __init__.py
├── database.py         # SQLAlchemy async engine
├── exceptions.py       # 异常类层次
├── logging_config.py   # 日志配置
├── models/            # ORM模型 (16个)
│   ├── novel.py
│   ├── character.py
│   ├── chapter.py
│   └── ...
└── utils/            # 通用工具
```

## WHERE TO LOOK

| 任务 | 文件 | 说明 |
|------|------|------|
| 新增模型 | `models/{name}.py` | 参考Novel模型 |
| 异常定义 | `exceptions.py` | 添加新异常类 |
| 日志使用 | `logging_config.py` | logger导入方式 |
| 数据库连接 | `database.py` | session获取方式 |

## DATABASE MODEL PATTERN

```python
from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

class Novel(Base):
    __tablename__ = "novels"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    chapters = relationship("Chapter", back_populates="novel")
```

## EXCEPTION PATTERN

```python
from core.exceptions import NovelException, NotFoundError, ValidationError

# 抛出异常
raise NotFoundError(resource_type="小说", resource_id=str(novel_id))
raise ValidationError(message="标题不能为空", field="title")
```

## EXCEPTION HIERARCHY

```
NovelException (基类)
├── NovelSystemError (系统级)
│   ├── DatabaseError
│   ├── CacheError
│   ├── LLMError
│   └── ConfigError
├── NovelBusinessError (业务级)
│   ├── NovelError
│   ├── ChapterError
│   ├── CharacterError
│   └── ...
└── ValidationError (验证级)
    ├── InvalidParameterError
    └── MissingRequiredFieldError
```

## LOGGING PATTERN

```python
from core.logging_config import logger

logger.info(f"企划阶段完成，总消耗 {cost_summary['total_tokens']} tokens")
logger.error(f"企划阶段失败: {e}")
logger.warning(f"新角色检测失败: {e}")
```

## CONVENTIONS

- **UUID主键**: `Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)`
- **JSONB默认值**: `default=dict` (非 `default={}`)
- **时间戳**: `DateTime(timezone=True), server_default=func.now()`
- **关系cascade**: `cascade="all, delete-orphan"`

## EXTERNAL DEPS

- `sqlalchemy`: ORM (async)
- `asyncpg`: PostgreSQL driver
- `redis`: 缓存 (cache_service)
