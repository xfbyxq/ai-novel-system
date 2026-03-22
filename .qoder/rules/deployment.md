---
trigger: deployment
---

# 部署规范

## 环境说明

### 环境类型
| 环境 | 用途 | docker-compose文件 |
|------|------|-------------------|
| 开发环境 | 本地开发调试 | docker-compose.dev.yml |
| 测试环境 | 功能测试验证 | docker-compose.yml |
| 生产环境 | 正式对外服务 | docker-compose.prod.yml |

## Docker部署

### 服务架构
```
novel_system/
├── backend/           # 后端服务
├── frontend/          # 前端服务
├── postgres/         # PostgreSQL数据库
├── redis/            # Redis缓存
├── celery-worker/    # Celery工作进程
└── nginx/            # Nginx反向代理
```

### 快速启动

#### 开发环境
```bash
# 启动开发环境
./start_dev.sh

# 或手动启动
docker-compose -f docker-compose.dev.yml up -d
```

#### 生产环境
```bash
# 构建并启动
./deploy_docker.sh

# 或手动构建
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

#### 停止服务
```bash
# 停止所有服务
./docker-stop.sh

# 或手动停止
docker-compose -f docker-compose.yml down
```

## 环境变量配置

### 后端环境变量
| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| DATABASE_URL | PostgreSQL连接串 | postgresql+asyncpg://user:pass@localhost:5432/db |
| REDIS_URL | Redis连接串 | redis://localhost:6379/0 |
| DASHSCOPE_API_KEY | 通义千问API密钥 | sk-xxx |
| SECRET_KEY | JWT密钥 | your-secret-key |
| CORS_ORIGINS | 允许的跨域来源 | http://localhost:5173 |

### 前端环境变量
| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| VITE_API_BASE_URL | API基础URL | http://localhost:8000 |
| VITE_WS_URL | WebSocket URL | ws://localhost:8000 |

## 部署检查清单

### 部署前检查
- [ ] 数据库迁移已执行
- [ ] 环境变量已正确配置
- [ ] 防火墙端口已开放 (80, 443)
- [ ] 磁盘空间充足
- [ ] 内存资源充足

### 部署后检查
- [ ] 所有容器正常运行
- [ ] 后端API可访问
- [ ] 前端页面可访问
- [ ] 数据库连接正常
- [ ] Redis连接正常
- [ ] 日志无错误输出

## 监控与运维

### 日志查看
```bash
# 查看后端日志
docker-compose logs -f backend

# 查看前端日志
docker-compose logs -f frontend

# 查看所有日志
docker-compose logs -f
```

### 容器状态
```bash
# 查看所有容器状态
docker-compose ps

# 查看资源使用
docker stats
```

### 数据库迁移
```bash
# 创建新迁移
alembic revision --autogenerate -m "description"

# 执行迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

## CI/CD部署流程

项目使用GitHub Actions进行自动化部署:

1. **代码质量检查** - flake8, black, pydocstyle
2. **单元测试** - pytest + coverage
3. **Docker构建** - 构建镜像并验证
4. **安全扫描** - CodeQL + dependency scanning
5. **生产部署** - 仅main分支触发

### 触发部署
- 推送到main分支
- 推送到develop分支（测试环境）
- 手动触发workflow_dispatch