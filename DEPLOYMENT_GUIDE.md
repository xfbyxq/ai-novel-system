# Docker 部署指南

本文档说明如何使用 Docker 部署小说生成系统。

## 快速开始

```bash
# 首次部署
./deploy_docker.sh

# 访问应用
# 前端：http://localhost:3000
# 后端：http://localhost:8000
# API 文档：http://localhost:8000/docs
```

---

## 部署脚本说明

### 1. 开发环境

| 脚本 | 用途 |
|------|------|
| `./start_dev.sh` | Docker 开发模式（自动启动前后端 + 基础服务） |
| `./scripts/init_local_dev.sh` | 本地开发环境初始化（需要先启动 Docker 基础服务） |
| `./scripts/start_backend.sh` | 单独启动后端服务 |
| `./scripts/start_frontend.sh` | 单独启动前端服务 |
| `./scripts/start_dev_all.sh` | 统一启动前后端（推荐） |

### 2. 生产环境

| 脚本 | 用途 |
|------|------|
| `./deploy_docker.sh` | 构建并启动所有服务（使用缓存） |
| `./docker-start.sh` | 启动已构建的服务 |
| `./docker-stop.sh` | 停止所有服务 |
| `./rebuild_docker.sh` | 重新构建镜像（不使用缓存） |

---

## 常用操作

### 启动所有服务

```bash
# 开发模式（使用 docker-compose.dev.yml）
./start_dev.sh

# 生产模式
./deploy_docker.sh
```

### 停止服务

```bash
./docker-stop.sh
```

### 查看服务状态

```bash
docker-compose ps
# 或
docker ps
```

### 查看日志

```bash
# 所有服务日志
docker-compose logs -f

# 特定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres
docker-compose logs -f redis
```

### 更新代码后重新部署

```bash
# 拉取最新代码
git pull

# 重新部署
./deploy_docker.sh
```

---

## 数据库迁移

### 自动迁移（推荐）

服务启动时自动执行 Alembic 迁移：

```bash
# 启动后端时会自动运行 alembic upgrade head
./deploy_docker.sh
```

### 手动执行迁移

```bash
# 进入后端容器执行迁移
docker exec novel_backend alembic upgrade head

# 或使用 docker-compose
docker-compose exec backend alembic upgrade head
```

### 查看迁移状态

```bash
docker exec novel_backend alembic current
docker exec novel_backend alembic history
```

### 回滚迁移

```bash
# 回滚上一次迁移
docker exec novel_backend alembic downgrade -1

# 回滚到特定版本
docker exec novel_backend alembic downgrade <revision>
```

---

## 故障排查

### 1. 容器无法启动

```bash
# 查看日志
docker-compose logs <服务名>

# 重启特定服务
docker-compose restart <服务名>
```

### 2. 数据库连接失败

```bash
# 检查数据库容器状态
docker-compose ps postgres

# 测试数据库连接
docker exec novel_postgres pg_isready -U novel_user -d novel_system

# 查看数据库日志
docker-compose logs postgres
```

### 3. 迁移失败

```bash
# 手动执行迁移
docker exec novel_backend alembic upgrade head

# 查看迁移历史
docker exec novel_backend alembic history
```

---

## 环境配置

### 修改端口

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

### 修改数据库配置

编辑 `.env` 文件或 `docker-compose.yml`：

```yaml
services:
  postgres:
    environment:
      POSTGRES_USER: your_user
      POSTGRES_PASSWORD: your_password
      POSTGRES_DB: your_db
```

---

## 服务地址

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |
