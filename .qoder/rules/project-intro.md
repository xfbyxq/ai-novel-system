---
trigger: always_on
alwaysApply: true
---

# 项目介绍

## 系统概述
- **项目名称**: AI Novel System (AI小说生成系统)
- **项目版本**: 2.0.0
- **项目描述**: 基于AI的小说生成系统，采用CrewAI和Qwen大模型驱动

## 技术架构
- **前端框架**: React 19 + TypeScript + Vite 7
- **后端框架**: FastAPI + Python 3.12
- **数据库**: PostgreSQL + SQLAlchemy (async) + Alembic
- **缓存**: Redis
- **任务队列**: Celery
- **AI引擎**: CrewAI + DashScope (通义千问)
- **前端UI**: Ant Design 6 + React Router 7 + Zustand

## 项目目录结构
```
novel_system/
├── backend/           # FastAPI后端应用
│   ├── api/           # API路由
│   ├── services/      # 业务服务层
│   ├── schemas/       # Pydantic模型
│   ├── models/        # SQLAlchemy模型
│   ├── dependencies/  # 依赖注入
│   ├── middleware/    # 中间件
│   └── utils/         # 工具函数
├── frontend/          # React前端应用
│   ├── src/           # 源代码
│   ├── public/        # 静态资源
│   └── dist/          # 构建产物
├── agents/            # AI智能体模块
├── core/              # 核心业务逻辑
├── workers/           # Celery工作进程
├── tests/             # 测试代码
├── scripts/           # 脚本工具
└── migrations/        # 数据库迁移
```

## 环境配置
- **开发环境**: docker-compose.dev.yml
- **生产环境**: docker-compose.prod.yml
- **Python版本**: 3.12
- **Node版本**: 18+

## 部署方式
- Docker容器化部署
- 包含完整CI/CD流水线
- 支持多环境部署（开发、测试、生产）