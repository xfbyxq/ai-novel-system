# ALEMBIC 模块

**数据库迁移**: SQLAlchemy ORM迁移管理

## OVERVIEW

使用Alembic管理PostgreSQL数据库Schema变更。

## COMMANDS

```bash
# 生成新迁移
alembic revision --autogenerate -m "描述"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1

# 查看状态
alembic current
alembic history
```

## CONVENTIONS

- **迁移命名**: `yyyyMMdd_HHMMSS_description.py`
- **撤销迁移**: 使用 `downgrade()` 方法
- **测试**: 迁移前先在本地测试
