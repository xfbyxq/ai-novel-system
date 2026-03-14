# Docker 部署和数据库迁移指南

本文档说明如何重新部署前端和后端服务，以及如何执行数据库迁移脚本。

## 📦 部署脚本说明

项目提供了三个部署脚本，适用于不同场景：

### 1. `deploy_complete.sh` - 一键完整部署（推荐）

**功能**：
- 自动构建 Docker 镜像
- 自动启动所有服务
- 自动执行数据库迁移
- 支持多种部署模式

**用法**：

```bash
# 标准部署（保留数据）
./deploy_complete.sh

# 全新部署（清理所有容器和镜像）
./deploy_complete.sh --clean

# 仅执行数据库迁移
./deploy_complete.sh --migrate

# 仅重启服务
./deploy_complete.sh --restart

# 查看帮助
./deploy_complete.sh --help
```

**适用场景**：
- 首次部署
- 代码更新后重新部署
- 数据库结构变更后

---

### 2. `run_migration.sh` - 独立数据库迁移脚本

**功能**：
- 直接在运行的数据库容器中执行迁移
- 支持 Alembic 自动迁移和手动 SQL 迁移
- 智能检测字段是否已存在

**用法**：

```bash
# 确保数据库容器正在运行
docker-compose up -d postgres

# 执行迁移
./run_migration.sh
```

**适用场景**：
- 数据库容器已在运行
- 只需要更新数据库结构
- Alembic 迁移失败时的备选方案

---

### 3. `redeploy_with_migration.sh` - 完整重新部署脚本

**功能**：
- 停止并清理旧容器
- 重新构建镜像
- 执行数据库迁移
- 启动所有服务

**用法**：

```bash
./redeploy_with_migration.sh
```

**适用场景**：
- 需要彻底重新部署
- 镜像损坏需要重建
- 重大版本更新

---

## 🗄️ 数据库迁移详情

### 迁移内容

本次迁移为 `chapters` 表添加三个新字段，用于支持大纲系统：

| 字段名 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `outline_task` | JSONB | 本章的大纲任务配置 | `{}` |
| `outline_validation` | JSONB | 大纲验证结果 | `{}` |
| `outline_version` | VARCHAR(50) | 使用的大纲版本号 | NULL |

### 字段用途

#### 1. outline_task (JSONB)
存储本章创作前的大纲任务配置：

```json
{
  "mandatory_events": ["必须完成的事件 1", "必须完成的事件 2"],
  "optional_events": ["建议事件"],
  "foreshadowing_to_plant": ["需要埋设的伏笔"],
  "foreshadowing_to_payoff": ["需要回收的伏笔"],
  "emotional_tone": "情感基调",
  "tension_position": "张力位置",
  "character_development": {"角色名": "发展轨迹"}
}
```

#### 2. outline_validation (JSONB)
存储章节生成后的大纲验证结果：

```json
{
  "passed": true,
  "completion_rate": 0.85,
  "completed_events": ["已完成的事件"],
  "missing_events": ["缺失的事件"],
  "suggestions": ["改进建议"]
}
```

#### 3. outline_version (VARCHAR)
记录使用的大纲版本号，用于版本追踪和回滚。

---

## 🚀 快速开始

### 首次部署

```bash
# 1. 确保 Docker 和 Docker Compose 已安装
docker --version
docker-compose --version

# 2. 赋予脚本执行权限
chmod +x deploy_complete.sh
chmod +x run_migration.sh
chmod +x redeploy_with_migration.sh

# 3. 执行一键部署
./deploy_complete.sh

# 4. 访问应用
# 前端：http://localhost:3000
# 后端：http://localhost:8000
# API 文档：http://localhost:8000/docs
```

### 更新代码后重新部署

```bash
# 拉取最新代码后
git pull

# 执行完整部署（自动迁移数据库）
./deploy_complete.sh
```

### 仅更新数据库结构

```bash
# 如果只需要执行数据库迁移
./run_migration.sh
```

---

## 🔍 故障排查

### 1. 数据库迁移失败

**症状**：迁移脚本报错，字段未创建

**解决方案**：

```bash
# 方案 1: 手动执行 SQL
docker exec -i novel_postgres psql -U novel_user -d novel_system << 'EOSQL'
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS outline_task JSONB DEFAULT '{}';
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS outline_validation JSONB DEFAULT '{}';
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS outline_version VARCHAR(50);
EOSQL

# 方案 2: 使用 Alembic
docker exec novel_backend alembic upgrade head
```

### 2. 容器无法启动

**症状**：容器启动后立即退出

**解决方案**：

```bash
# 查看日志
docker-compose logs backend
docker-compose logs frontend

# 重启特定服务
docker-compose restart backend
docker-compose restart frontend

# 完全重新部署
./deploy_complete.sh --clean
```

### 3. 数据库连接失败

**症状**：后端无法连接数据库

**解决方案**：

```bash
# 检查数据库容器状态
docker-compose ps postgres

# 查看数据库日志
docker-compose logs postgres

# 测试数据库连接
docker exec novel_postgres pg_isready -U novel_user -d novel_system

# 重启数据库服务
docker-compose restart postgres
```

---

## 📊 验证部署

### 检查服务状态

```bash
# 查看所有容器状态
docker-compose ps

# 应该看到 4 个运行的容器：
# novel_postgres   Up
# novel_redis      Up
# novel_backend    Up
# novel_frontend   Up
```

### 验证数据库迁移

```bash
# 连接到数据库
docker exec -it novel_postgres psql -U novel_user -d novel_system

# 查看 chapters 表结构
\d chapters

# 应该看到新增的三个字段：
# outline_task         | jsonb
# outline_validation   | jsonb
# outline_version      | character varying(50)
```

### 测试 API

```bash
# 测试后端健康检查
curl http://localhost:8000/health

# 测试大纲生成 API
curl -X POST http://localhost:8000/api/v1/novels/{novel_id}/outline/generate \
  -H "Content-Type: application/json"
```

### 测试前端

打开浏览器访问：http://localhost:3000

检查是否能看到：
- 小说列表页面
- 新增的"大纲梳理"标签页
- 新增的"章节拆分"标签页

---

## 🔧 高级配置

### 修改数据库配置

编辑 `docker-compose.yml`：

```yaml
services:
  postgres:
    environment:
      POSTGRES_USER: your_user      # 修改用户名
      POSTGRES_PASSWORD: your_pass  # 修改密码
      POSTGRES_DB: your_db          # 修改数据库名
    ports:
      - "5434:5432"  # 修改外部访问端口
```

### 修改服务端口

编辑 `docker-compose.yml`：

```yaml
services:
  backend:
    ports:
      - "8001:8000"  # 修改后端端口
  frontend:
    ports:
      - "3001:3000"  # 修改前端端口
```

### 数据持久化

数据库数据存储在 Docker volume 中：

```bash
# 查看 volume
docker volume ls | grep postgres

# 备份数据
docker run --rm \
  -v novel_system_postgres_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/postgres_backup.tar.gz /data

# 恢复数据
docker run --rm \
  -v novel_system_postgres_data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/postgres_backup.tar.gz -C /
```

---

## 📝 回滚方案

如果需要回滚数据库变更：

```bash
# 使用 Alembic 回滚
docker exec novel_backend alembic downgrade -1

# 或手动回滚 SQL
docker exec -i novel_postgres psql -U novel_user -d novel_system << 'EOSQL'
ALTER TABLE chapters DROP COLUMN IF EXISTS outline_task;
ALTER TABLE chapters DROP COLUMN IF EXISTS outline_validation;
ALTER TABLE chapters DROP COLUMN IF EXISTS outline_version;
EOSQL
```

---

## 📞 支持

如有问题，请检查：

1. Docker 日志：`docker-compose logs`
2. 数据库日志：`docker-compose logs postgres`
3. 后端日志：`docker-compose logs backend`
4. 前端日志：`docker-compose logs frontend`

或查看项目文档获取更多信息。
