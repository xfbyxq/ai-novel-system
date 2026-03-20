# 小说生成系统 - 本地开发指南

## 📋 快速开始

### 环境准备

1. **Python 3.12+**
   ```bash
   python3 --version
   ```

2. **Node.js 20+**
   ```bash
   node --version
   npm --version
   ```

3. **Docker (可选,用于数据库和缓存)**
   ```bash
   docker --version
   docker-compose --version
   ```

## 🚀 本地开发环境部署

### 方式1: 使用自动初始化脚本 (推荐)

```bash
# 1. 克隆项目
cd novel_system

# 2. 运行初始化脚本
chmod +x scripts/init_local_dev.sh
./scripts/init_local_dev.sh

# 3. 配置环境变量
# 编辑 .env 文件,设置你的 DashScope API Key
nano .env  # 或使用你熟悉的编辑器
# 确保 DASHSCOPE_API_KEY 已正确设置

# 4. 启动后端服务
chmod +x scripts/start_backend.sh
./scripts/start_backend.sh

# 5. 启动前端服务 (在新终端)
chmod +x scripts/start_frontend.sh
./scripts/start_frontend.sh
```

### 方式2: 手动部署

#### 2.1 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

#### 2.2 安装Python依赖

```bash
# 使用Poetry (推荐)
poetry install

# 或使用pip
pip install -e .
```

#### 2.3 配置环境变量

```bash
# 复制模板
cp .env.example .env

# 编辑配置
nano .env
```

关键配置项:
```bash
# 必填项
DASHSCOPE_API_KEY=your-api-key-here  # 替换为你的实际API Key

# 数据库 (默认: localhost:5434)
DATABASE_URL=postgresql+asyncpg://novel_user:novel_pass@localhost:5434/novel_system

# Redis (默认: localhost:6379)
REDIS_URL=redis://localhost:6379/0
```

#### 2.4 启动数据库 (可选,使用Docker)

```bash
docker-compose up -d postgres redis

# 等待服务就绪
sleep 10

# 检查状态
docker-compose ps
```

#### 2.5 运行数据库迁移

```bash
alembic upgrade head
```

#### 2.6 启动服务

```bash
# 启动后端
uvicorn backend.main:app --reload

# 启动前端 (新终端)
cd frontend
npm run dev
```

## 🌐 服务地址

- **前端开发服务器**: http://localhost:3000
- **后端API服务器**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

## 🧪 测试

### 单元测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/unit/test_novels.py

# 带覆盖率报告
pytest --cov=backend --cov-report=html

# 运行特定标记的测试
pytest -m "integration"
```

### 手动测试

```bash
# 测试健康检查
curl http://localhost:8000/health

# 测试API
curl http://localhost:8000/api/v1/novels

# 测试创建小说
curl -X POST http://localhost:8000/api/v1/novels \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Novel", "genre": "fantasy"}'
```

## 🐳 Docker部署

### 开发环境

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart
```

### 生产环境

```bash
# 设置API Key
export DASHSCOPE_API_KEY=your-production-api-key

# 启动服务
DASHSCOPE_API_KEY=$DASHSCOPE_API_KEY docker-compose up -d

# 检查服务状态
docker-compose ps
```

## 📁 项目结构

```
novel_system/
├── backend/              # 后端服务
│   ├── api/             # API路由
│   ├── services/        # 业务逻辑
│   │   └── cache_service.py  # Redis缓存服务
│   ├── config.py        # 配置管理
│   └── main.py          # 应用入口
├── frontend/            # 前端应用
│   ├── src/
│   │   ├── api/        # API客户端
│   │   └── components/ # UI组件
├── agents/             # Agent系统
├── core/               # 核心模块
├── scripts/            # 运维脚本
│   ├── init_local_dev.sh     # 初始化脚本
│   ├── start_backend.sh      # 后端启动脚本
│   └── start_frontend.sh     # 前端启动脚本
├── tests/              # 测试
├── .env.example        # 环境变量模板
├── docker-compose.yml  # Docker编排
└── README.md           # 本文档
```

## 🔧 常见问题

### 1. 数据库连接失败

**问题**: `Connection refused (localhost:5434)`

**解决方案**:
```bash
# 检查PostgreSQL是否运行
docker-compose ps postgres

# 查看日志
docker-compose logs postgres

# 手动启动
docker-compose up -d postgres
```

### 2. Redis连接失败

**问题**: `Connection refused (localhost:6379)`

**解决方案**:
```bash
# 启动Redis
docker-compose up -d redis

# 或停止使用Redis
# 在 .env 中注释掉REDIS相关配置
```

### 3. API Key错误

**问题**: `Unauthorized` 或 `Invalid API Key`

**解决方案**:
```bash
# 检查.env配置
cat .env | grep DASHSCOPE

# 确保API Key正确
# 获取API Key: https://dashscope.console.aliyun.com/
```

### 4. 端口被占用

**问题**: `Address already in use (8000)` 或 `(3000)`

**解决方案**:
```bash
# 查找并杀死占用进程
lsof -i :8000
lsof -i :3000

# 或修改端口
# 在 .env 中修改 APP_PORT=8001
```

### 5. Python依赖冲突

**问题**: `Dependency resolution failed`

**解决方案**:
```bash
# 清理并重新安装
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install poetry
poetry install
```

## 📝 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| DASHSCOPE_API_KEY | 阿里云DashScope API Key | - | ✅ |
| DATABASE_URL | PostgreSQL连接字符串 | localhost:5434 | ✅ |
| REDIS_URL | Redis连接URL | localhost:6379 | ❌ |
| APP_ENV | 应用环境 | development | ❌ |
| APP_DEBUG | 调试模式 | true | ❌ |
| DOCKER_ENV | Docker环境标记 | false | ❌ |

### Agent审查配置

| 配置项 | 说明 | 推荐值 |
|--------|------|--------|
| ENABLE_WORLD_REVIEW | 启用世界观审查 | true |
| ENABLE_CHARACTER_REVIEW | 启用角色审查 | true |
| ENABLE_PLOT_REVIEW | 启用大纲审查 | true |
| ENABLE_CHAPTER_REVIEW | 启用章节审查 | true |
| WORLD_QUALITY_THRESHOLD | 世界观质量阈值 | 7.5-8.0 |
| MAX_WORLD_REVIEW_ITERATIONS | 最大迭代次数 | 3-5 |

## 🎯 开发建议

1. **使用虚拟环境**
   ```bash
   source venv/bin/activate  # 激活
   deactivate               # 退出
   ```

2. **代码风格**
   ```bash
   # Python格式化
   black backend/
   
   # 类型检查
   mypy backend/
   
   # Lint检查
   ruff check backend/
   ```

3. **热重载**
   - 后端使用 `--reload` 参数
   - 前端使用 Vite 的 HMR

4. **日志查看**
   ```bash
   # 后端日志 (终端)
   # 前端日志 (浏览器Console)
   ```

## 📚 相关文档

- [API文档](http://localhost:8000/docs) -FastAPI 自动生成
- [项目README](../README.md) -项目概述
- [部署指南](DEPLOYMENT_GUIDE.md) -Docker部署
- [变更日志](CHANGELOG.md) -版本更新

## 🔗 项目信息

- **版本**: v1.3.2
- **作者**: AI Assistant
- **技术栈**: FastAPI + React + PostgreSQL + Redis
- **Agent框架**: CrewAI + 自研

## 🆘 支持

如有问题,请检查:
1. 所有服务是否正常运行
2. API Key 是否正确配置
3. 数据库连接是否正常
4. 端口是否被占用
5. 日志中的错误信息

---

**祝您开发愉快!** 🚀
