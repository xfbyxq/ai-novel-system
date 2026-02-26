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

### 5. 清除浏览器缓存（重要）

如果遇到前端网络错误，请清除浏览器缓存：
- 按 `F12` 打开开发者工具
- 右键点击刷新按钮 → 选择 "清空缓存并硬性重新加载"
- 或在 Application 标签页中清除站点数据

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

**注意**：
- 容器间通信使用服务名（如 `postgres`、`redis`），端口使用容器内部端口（5432、6379）
- 数据库连接已配置 `connect_args={"ssl": False}` 以禁用 SSL 连接
- 前端代理配置使用 `API_PROXY_TARGET` 环境变量（非 `VITE_` 前缀）避免客户端代码冲突

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

### 常见问题及解决方案

#### 1. 前端无法访问后端 API

**问题现象**：浏览器控制台显示 `net::ERR_NAME_NOT_RESOLVED` 错误

**解决方案**：
```bash
# 1. 检查前端容器环境变量
docker-compose logs frontend | grep "API_PROXY_TARGET"

# 2. 重启前端服务
docker-compose restart frontend

# 3. 清除浏览器缓存（重要！）
# 在浏览器中：F12 → Application → Clear site data
```

#### 2. 数据库连接失败

**问题现象**：后端日志显示 `ConnectionRefusedError`

**解决方案**：
```bash
# 1. 检查数据库服务状态
docker-compose ps postgres

# 2. 验证数据库连接
docker exec novel_backend python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test():
    engine = create_async_engine(
        'postgresql+asyncpg://novel_user:novel_pass@postgres:5432/novel_system',
        connect_args={'ssl': False}
    )
    async with engine.begin() as conn:
        result = await conn.execute(text('SELECT 1'))
        print('✅ 数据库连接成功!')
    await engine.dispose()

asyncio.run(test())
"
```

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

### 后端环境变量

主要在 `.env` 文件中配置：

- `DASHSCOPE_API_KEY`：通义千问 API 密钥
- `DASHSCOPE_MODEL`：LLM 模型名称
- `DASHSCOPE_BASE_URL`：API 基础 URL

### Docker Compose 环境变量

在 `docker-compose.yml` 中设置：

```yaml
# 数据库配置
DB_HOST=postgres
DB_PORT=5432
DB_USER=novel_user
DB_PASSWORD=novel_pass
DB_NAME=novel_system

# Redis 配置
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# 前端代理配置（注意：不使用 VITE_ 前缀）
API_PROXY_TARGET=http://backend:8000
```

**重要说明**：
- 前端代理环境变量使用 `API_PROXY_TARGET` 而非 `VITE_API_PROXY_TARGET`
- 以 `VITE_` 开头的环境变量会被 Vite 暴露给客户端代码，可能导致冲突
- 数据库连接已禁用 SSL：`connect_args={"ssl": False}`

## 🌐 访问地址

服务启动后，可通过以下地址访问：

- **前端应用**：http://localhost:3000
- **后端 API**：http://localhost:8000
- **API 文档**：http://localhost:8000/docs
- **健康检查**：http://localhost:8000/health

### 调试页面

- **API 配置调试**：http://localhost:3000/debug.html
- **Axios 测试**：http://localhost:3000/test.html

这些页面可以帮助诊断前端网络连接问题。
