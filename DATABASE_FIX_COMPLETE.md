# ✅ 数据库问题彻底解决

## 问题描述

后端运行时报错，主要错误有两个：

### 错误 1: 枚举类型不存在
```
ERROR: type "taskstatus" does not exist
```

### 错误 2: 字段缺失
```
ERROR: column novels.cover_url does not exist
```

## 根本原因

`create_tables.sh` 脚本创建的表结构不完整：
1. 缺少 `taskstatus` 枚举类型定义
2. `novels` 表缺少多个字段（cover_url, synopsis 等）
3. `generation_tasks.status` 字段应该使用枚举类型而不是 VARCHAR

## 解决方案

### 1. 创建修复脚本 `fix_database_types.sh`

**功能**:
- ✅ 创建 `taskstatus` 枚举类型
- ✅ 添加 `novels.cover_url` 字段
- ✅ 添加 `novels.synopsis` 字段
- ✅ 添加 `novels.target_platform` 字段
- ✅ 添加 `novels.estimated_revenue` 字段
- ✅ 添加 `novels.actual_revenue` 字段
- ✅ 添加 `novels.chapter_config` 字段
- ✅ 添加 `novels.metadata` 字段

**执行结果**:
```
✓ 数据库修复成功！
```

### 2. 更新 `create_tables.sh`

修正了 `generation_tasks` 表的 `status` 字段类型：
```sql
-- 修改前
status VARCHAR(50) DEFAULT 'pending'

-- 修改后
status taskstatus DEFAULT 'pending'
```

## 修复后的数据库结构

### novels 表
```sql
novels (
    id UUID PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    author VARCHAR(100),
    genre VARCHAR(100),
    status VARCHAR(50) DEFAULT 'draft',
    word_count INTEGER DEFAULT 0,
    chapter_count INTEGER DEFAULT 0,
    tags JSONB DEFAULT '[]',
    platform VARCHAR(100),
    platform_id VARCHAR(200),
    length_type VARCHAR(50) DEFAULT 'medium',
    token_cost DECIMAL(10,4) DEFAULT 0,
    cover_url VARCHAR(500),              -- ✅ 新增
    synopsis TEXT,                        -- ✅ 新增
    target_platform VARCHAR(100),         -- ✅ 新增
    estimated_revenue DECIMAL(10,2),      -- ✅ 新增
    actual_revenue DECIMAL(10,2),         -- ✅ 新增
    chapter_config JSONB DEFAULT '{}',    -- ✅ 新增
    metadata JSONB DEFAULT '{}',          -- ✅ 新增
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
)
```

### generation_tasks 表
```sql
generation_tasks (
    id UUID PRIMARY KEY,
    novel_id UUID NOT NULL REFERENCES novels(id),
    chapter_id UUID REFERENCES chapters(id),
    task_type VARCHAR(50),
    status taskstatus DEFAULT 'pending',  -- ✅ 使用枚举类型
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
)
```

### taskstatus 枚举类型
```sql
CREATE TYPE taskstatus AS ENUM (
    'pending',
    'running',
    'success',
    'failed',
    'cancelled'
);
```

## 验证结果

### 服务状态
```
✅ 后端服务正常 (http://localhost:8000)
✅ 前端服务正常 (http://localhost:3000)
✅ API 文档可访问 (http://localhost:8000/docs)
```

### 数据库日志
```
✅ 无 ERROR 日志
✅ 查询正常执行
```

## 创建的修复脚本

### 1. `fix_database_types.sh` - 数据库修复脚本

**使用方法**:
```bash
./fix_database_types.sh
```

**适用场景**:
- 数据库表结构不完整
- 缺少枚举类型
- 缺少字段

### 2. `create_tables.sh` - 已更新

现在包含正确的枚举类型定义和完整的字段列表。

## 完整数据库初始化流程

如果是全新部署，按以下顺序执行：

```bash
# 1. 启动 PostgreSQL
docker-compose -f docker-compose.dev.yml up -d postgres

# 2. 创建枚举类型和所有表
./fix_database_types.sh

# 或者使用完整脚本
./create_tables.sh
```

## 预防措施

### 问题：为什么表结构会不完整？

**原因**:
- SQLAlchemy 模型定义与实际数据库表可能不同步
- 手动创建的表结构可能遗漏某些字段
- 枚举类型需要在表之前创建

### 改进方案

1. **使用 Alembic 进行迁移管理**
   - 自动跟踪模型变化
   - 生成迁移脚本
   - 版本控制

2. **在模型中定义枚举类型**
   ```python
   from sqlalchemy import Enum
   
   class GenerationTask(Base):
       status = Column(Enum('pending', 'running', 'success', 'failed', 'cancelled', name='taskstatus'))
   ```

3. **定期同步数据库结构**
   ```bash
   # 导出当前结构
   pg_dump -U novel_user -d novel_system --schema-only > schema.sql
   
   # 对比模型和实际结构
   ```

## 测试验证

### 测试 API

```bash
# 测试小说列表 API
curl http://localhost:8000/api/v1/novels

# 测试生成任务列表 API
curl http://localhost:8000/api/v1/generation/tasks

# 应该不再出现数据库错误
```

### 测试前端

访问 http://localhost:3000，检查：
- ✅ 小说列表页面正常显示
- ✅ 创建小说功能正常
- ✅ 无数据库相关错误

## 总结

### 已解决的问题
1. ✅ 创建 `taskstatus` 枚举类型
2. ✅ 添加 `novels.cover_url` 字段
3. ✅ 添加 `novels` 表缺失的其他字段
4. ✅ 修正 `generation_tasks.status` 字段类型

### 创建的脚本
- `fix_database_types.sh` - 数据库修复脚本
- `create_tables.sh` - 已更新为正确的表结构

### 服务状态
- ✅ 后端服务正常运行
- ✅ 前端服务正常运行
- ✅ 数据库无错误日志

**所有问题已彻底解决！** 🎉
