# 数据库管理最佳实践文档

## 1. Alembic 简介

Alembic 是一个轻量级的数据库迁移工具，专门为 SQLAlchemy ORM 设计。它提供了以下核心功能：

- **版本控制**: 跟踪数据库模式变更的历史
- **自动生成迁移**: 根据模型变更自动生成迁移脚本
- **可逆操作**: 支持升级和回滚操作
- **事务管理**: 确保迁移操作的原子性

## 2. 环境配置

### 2.1 配置文件

**`alembic.ini`**: 主配置文件，包含以下关键配置：

```ini
# 脚本位置
script_location = %(here)s/alembic

# 系统路径
prepend_sys_path = .

# 数据库连接URL（会被env.py覆盖）
sqlalchemy.url = driver://user:pass@localhost/dbname
```

**`alembic/env.py`**: 环境配置文件，重要配置：

```python
# 导入所有模型
from core.models import (
    Novel, WorldSetting, Character, PlotOutline,
    Chapter, ReaderPreference, GenerationTask, TokenUsage,
    CrawlerTask, CrawlResult, PlatformAccount, PublishTask, ChapterPublish
)

# 覆盖数据库URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)

# 设置元数据
target_metadata = Base.metadata
```

### 2.2 依赖管理

确保项目依赖中包含：

```toml
# pyproject.toml
dependencies = [
    "sqlalchemy",
    "alembic",
    "psycopg2-binary",  # 或 asyncpg
]
```

## 3. 常用命令

### 3.1 基本操作

| 命令 | 描述 | 示例 |
|------|------|------|
| `alembic init` | 初始化Alembic环境 | `alembic init alembic` |
| `alembic revision` | 创建新的迁移文件 | `alembic revision -m "add new table"` |
| `alembic revision --autogenerate` | 自动生成迁移文件 | `alembic revision --autogenerate -m "update models"` |
| `alembic upgrade` | 执行迁移 | `alembic upgrade head` |
| `alembic downgrade` | 回滚迁移 | `alembic downgrade -1` |
| `alembic current` | 查看当前迁移版本 | `alembic current` |
| `alembic history` | 查看迁移历史 | `alembic history` |

### 3.2 迁移策略

1. **初始化迁移**: 
   ```bash
   alembic revision --autogenerate -m "initial tables"
   alembic upgrade head
   ```

2. **模型变更迁移**: 
   ```bash
   # 修改模型后
   alembic revision --autogenerate -m "update user table"
   alembic upgrade head
   ```

3. **回滚操作**: 
   ```bash
   # 回滚到上一个版本
   alembic downgrade -1
   
   # 回滚到特定版本
   alembic downgrade 5badc20e064a
   ```

## 4. 最佳实践

### 4.1 模型管理

1. **统一导入**: 在 `env.py` 中导入所有模型，确保迁移能检测到所有变更
2. **外键依赖**: 注意表创建顺序，确保外键引用的表先创建
3. **枚举类型**: 使用 SQLAlchemy 的 `Enum` 类型时，确保正确处理枚举值变更
4. **索引优化**: 为常用查询字段添加索引，提升性能

### 4.2 迁移文件管理

1. **有意义的提交信息**: 迁移文件的消息应该清晰描述变更内容
2. **版本控制**: 将迁移文件纳入版本控制系统
3. **手动审核**: 自动生成的迁移文件应手动审核，确保正确性
4. **测试环境验证**: 在生产环境执行迁移前，先在测试环境验证

### 4.3 生产环境部署

1. **备份先行**: 执行迁移前，确保数据库已备份
2. **维护窗口**: 在低峰期执行迁移操作
3. **监控执行**: 密切关注迁移执行过程，及时发现问题
4. **回滚计划**: 准备回滚方案，以防迁移失败

## 5. 常见问题与解决方案

### 5.1 表不存在错误

**问题**: `relation "table_name" does not exist`

**原因**: 
- 迁移文件中表创建顺序错误
- 模型未正确导入到 `env.py`
- 迁移未执行或执行失败

**解决方案**: 
1. 检查 `env.py` 中是否导入了所有模型
2. 运行 `alembic upgrade head` 执行所有迁移
3. 如问题持续，考虑重建数据库并重新执行迁移

### 5.2 外键约束错误

**问题**: `foreign key constraint "..." cannot be implemented`

**原因**: 
- 引用的表不存在
- 引用的列类型不匹配

**解决方案**: 
1. 确保表创建顺序正确
2. 验证外键引用的表和列存在
3. 检查数据类型是否一致

### 5.3 枚举类型变更错误

**问题**: `type "enum_name" already exists`

**原因**: PostgreSQL 不支持直接修改枚举类型

**解决方案**: 
1. 使用 `ALTER TYPE ... ADD VALUE` 语句添加新值
2. 如需删除值，需要重建枚举类型
3. 或使用字符串类型替代枚举类型

### 5.4 迁移版本冲突

**问题**: `Can't locate revision identified by '...'`

**原因**: 
- 迁移文件丢失或被修改
- 本地和远程迁移版本不一致

**解决方案**: 
1. 检查 `alembic_version` 表中的当前版本
2. 确保所有迁移文件都在版本控制中
3. 如必要，使用 `alembic stamp` 命令手动设置版本

## 6. 自动化建议

### 6.1 CI/CD 集成

在 CI/CD 流程中集成数据库迁移检查：

```yaml
# .github/workflows/database.yml
jobs:
  migration-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install poetry
          poetry install
      - name: Check migration status
        run: |
          # 检查是否有未生成的迁移
          alembic revision --autogenerate -m "temp check"
          # 验证迁移文件语法
          python -m pytest tests/test_migrations.py
```

### 6.2 开发工作流

**推荐的开发工作流**:

1. **修改模型**: 在 `core/models/` 目录中修改或添加模型
2. **生成迁移**: 运行 `alembic revision --autogenerate -m "描述变更"`
3. **审核迁移**: 检查生成的迁移文件，确保正确性
4. **执行迁移**: 运行 `alembic upgrade head` 应用变更
5. **测试验证**: 运行测试确保功能正常
6. **提交代码**: 将模型变更和迁移文件一起提交

### 6.3 监控与维护

**定期维护任务**:

1. **健康检查**: 定期运行 `check_db.py` 验证数据库状态
2. **索引优化**: 分析查询性能，优化索引
3. **空间管理**: 监控数据库大小，及时清理无用数据
4. **备份验证**: 定期测试数据库备份的可恢复性

## 7. 命令参考

### 7.1 基本命令

```bash
# 查看当前状态
alembic current

# 查看历史
alembic history --verbose

# 生成新迁移
alembic revision -m "描述"

# 自动生成迁移
alembic revision --autogenerate -m "描述"

# 升级到最新版本
alembic upgrade head

# 升级到特定版本
alembic upgrade <revision_id>

# 回滚一个版本
alembic downgrade -1

# 回滚到特定版本
alembic downgrade <revision_id>

# 标记当前版本
alembic stamp <revision_id>
```

### 7.2 高级命令

```bash
# 清理未使用的迁移文件
alembic merge <revision1> <revision2>

# 检查迁移状态差异
alembic check

# 生成SQL脚本而非直接执行
alembic upgrade head --sql > migration.sql
```

## 8. 故障排除指南

### 8.1 迁移执行失败

**症状**: `alembic upgrade head` 执行失败

**排查步骤**:
1. 查看详细错误信息
2. 检查迁移文件中的SQL语句
3. 验证数据库连接和权限
4. 尝试分步执行迁移

### 8.2 模型与数据库不同步

**症状**: 模型定义与数据库实际结构不一致

**排查步骤**:
1. 运行 `alembic revision --autogenerate` 检测差异
2. 检查 `env.py` 中的模型导入
3. 验证所有迁移是否都已执行
4. 如必要，使用 `alembic stamp` 重新同步版本

### 8.3 性能问题

**症状**: 迁移执行缓慢

**解决方案**:
1. 对于大表变更，考虑分批次执行
2. 优化迁移文件中的SQL语句
3. 在非高峰期执行迁移
4. 考虑使用 `--sql` 模式生成脚本，手动优化后执行

## 9. 总结

有效的数据库管理是项目成功的关键组成部分。通过遵循本最佳实践文档，您可以：

1. **避免常见错误**: 减少数据库相关的问题和故障
2. **提高可靠性**: 确保数据库模式变更的安全执行
3. **简化维护**: 建立清晰的迁移管理流程
4. **保障性能**: 优化数据库结构和查询效率

记住，数据库迁移是一项需要谨慎处理的操作，尤其是在生产环境中。始终遵循最佳实践，确保每次变更都经过充分的测试和验证。