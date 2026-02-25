# Docker 部署说明

## 📋 架构说明

完整的 Docker Compose 配置包含以下服务：

| 服务 | 容器名称 | 端口映射 | 说明 |
|------|---------|---------|------|
| **PostgreSQL** | novel_postgres | 5434:5432 | 主数据库 |
| **Redis** | novel_redis | 6379:6379 | 缓存和消息队列 |
| **Backend** | novel_backend | 8000:8000 | FastAPI 后端服务 |
| **Frontend** | novel_frontend | 3000:3000 | Vite + React 前端 |

## 🚀 快速启动

### 1. 启动所有服务

```bash
./docker-start.sh
```

或手动执行：

```bash
docker-compose up -d --build
```

### 2. 查看服务状态

```bash
docker-compose ps
```

### 3. 查看服务日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 4. 停止所有服务

```bash
./docker-stop.sh
```

或手动执行：

```bash
docker-compose down
```

## 🔧 服务配置说明

### Backend 服务

- **镜像构建**：基于 `python:3.12-slim`
- **热重载**：支持代码修改自动重启
- **挂载目录**：
  - `./backend` → `/app/backend`
  - `./core` → `/app/core`
  - `./agents` → `/app/agents`
  - `./llm` → `/app/llm`
  - `./workers` → `/app/workers`

### Frontend 服务

- **镜像构建**：基于 `node:20-alpine`
- **热重载**：支持 HMR（热模块替换）
- **挂载目录**：
  - `./frontend/src` → `/app/src`
  - `./frontend/public` → `/app/public`

### 数据库连接

容器内服务使用以下连接配置：

```bash
# Backend 容器内的数据库连接
DATABASE_URL=postgresql+asyncpg://novel_user:novel_pass@postgres:5432/novel_system

# Redis 连接
REDIS_URL=redis://redis:6379/0
```

**注意**：容器间通信使用服务名（如 `postgres`、`redis`），端口使用容器内部端口（5432、6379）。

## 📊 健康检查

所有服务都配置了健康检查：

- **PostgreSQL**：使用 `pg_isready` 检查
- **Redis**：使用 `redis-cli ping` 检查
- **Backend**：依赖数据库和 Redis 健康后启动
- **Frontend**：依赖后端服务启动

## 🛠️ 常用命令

### 重新构建服务

```bash
docker-compose up -d --build backend
docker-compose up -d --build frontend
```

### 进入容器 Shell

```bash
# 进入后端容器
docker exec -it novel_backend bash

# 进入前端容器
docker exec -it novel_frontend sh

# 进入数据库容器
docker exec -it novel_postgres psql -U novel_user -d novel_system
```

### 数据库迁移

```bash
# 在后端容器内执行
docker exec -it novel_backend alembic upgrade head
```

### 清理未使用的资源

```bash
docker system prune -f
docker volume prune -f
```

## 🔍 故障排查

### 查看特定服务日志

```bash
docker-compose logs backend
docker-compose logs frontend
docker-compose logs postgres
docker-compose logs redis
```

### 重启服务

```bash
docker-compose restart backend
docker-compose restart frontend
```

### 完全重建

```bash
docker-compose down -v  # 删除容器和数据卷
docker-compose up -d --build
```

## 📝 环境变量

主要环境变量在 `.env` 文件中配置：

- `DASHSCOPE_API_KEY`：通义千问 API 密钥
- `DASHSCOPE_MODEL`：LLM 模型名称
- 其他数据库和 Redis 配置在 `docker-compose.yml` 中设置

## 🌐 访问地址

服务启动后，可通过以下地址访问：

- **前端应用**：http://localhost:3000
- **后端 API**：http://localhost:8000
- **API 文档**：http://localhost:8000/docs
- **健康检查**：http://localhost:8000/health
