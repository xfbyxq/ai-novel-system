# AGENTS.md

This file provides guidance to Qoder (qoder.com) when working with code in this repository.

---

## 概述

AI多Agent小说生成系统，基于CrewAI设计模式和通义千问(Qwen)LLM，提供企划、写作、审查、发布完整流程。

## 常用命令

```bash
# 开发环境启动（推荐）
./start_dev.sh                    # Docker Compose一键启动

# 后端独立运行（本地开发）
uvicorn backend.main:app --reload --port 8000

# 前端独立运行（进入frontend目录）
npm run dev                        # Vite开发服务器，端口3000

# 测试
pytest tests/ -v                   # 所有测试
pytest tests/unit/ -v              # 仅单元测试
pytest tests/e2e/ -v               # 仅E2E测试
pytest tests/unit/test_character.py -v  # 运行单个测试文件
pytest -m smoke -v                 # 冒烟测试（快速验证）
pytest -m "not slow" -v            # 排除慢测试
pytest -k "continuity" -v          # 按名称匹配测试

# 代码检查与格式化
ruff check .                       # lint检查
ruff check . --fix                 # 自动修复lint问题
ruff format .                      # 代码格式化

# 数据库迁移
alembic upgrade head               # 升级到最新版本
alembic downgrade -1               # 回退一个版本
alembic revision --autogenerate -m "描述"  # 自动生成迁移

# Docker服务管理
docker-compose -f docker-compose.dev.yml up -d
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml logs -f backend
```

## 核心架构

### 三层架构

```
┌─────────────────────────────────────────────────────────┐
│  frontend/     React + TypeScript + Vite + Ant Design   │
│  端口3000                                               │
├─────────────────────────────────────────────────────────┤
│  backend/      FastAPI + SQLAlchemy async               │
│  端口8000, API路由在 backend/api/v1/                    │
├─────────────────────────────────────────────────────────┤
│  agents/       Agent系统核心                            │
│  CrewAI设计模式 + QwenClient直接调用                    │
├─────────────────────────────────────────────────────────┤
│  core/         共享基础设施                             │
│  database.py, models/, exceptions.py, logging_config.py │
├─────────────────────────────────────────────────────────┤
│  llm/          LLM调用封装                              │
│  qwen_client.py (DashScope SDK), cost_tracker.py        │
└─────────────────────────────────────────────────────────┘
```

### Agent系统架构

**核心编排器**:
- `crew_manager.py` → NovelCrewManager: 协调企划和写作阶段所有Agent
- `agent_dispatcher.py` → AgentDispatcher: 在不同Agent实现间调度

**审查循环系统 (Designer-Reviewer模式)**:

位于 `agents/base/review_loop_base.py`，使用模板方法模式封装迭代逻辑：

```
流程: Reviewer评估 → 构造质量报告 → 检查退出条件 → Builder修订 → 循环
```

继承此基类的审查循环：
- `review_loop.py` → 章节审查 (Writer-Editor)
- `world_review_loop.py` → 世界观审查
- `character_review_loop.py` → 角色设计审查
- `plot_review_loop.py` → 大纲审查

**审查循环配置** (`backend/config.py`):
| 配置项 | 默认值 | 说明 |
|-------|-------|------|
| `ENABLE_*_REVIEW` | True | 各阶段审查开关 |
| `*_QUALITY_THRESHOLD` | 8.0 | 质量阈值(1-10) |
| `MAX_*_REVIEW_ITERATIONS` | 5 | 最大迭代次数 |

**Agent间协作组件**:
- `team_context.py` → NovelTeamContext: Agent间信息共享
- `voting_manager.py` → 企划阶段投票共识
- `agent_query_service.py` → Writer写作过程中查询设定
- `context_compressor.py` → 上下文压缩
- `similarity_detector.py` → 内容相似度检测

### 数据流

```
API请求 → GenerationService → AgentDispatcher → NovelCrewManager
         ↓                        ↓
    UnifiedContextManager    各Agent执行(LLM调用)
         ↓                        ↓
    PostgreSQL持久化        CostTracker记录成本
```

GenerationService (`backend/services/generation_service.py`) 是API层和Agent层的桥梁，负责：
- 从数据库加载小说上下文
- 调用AgentDispatcher执行生成
- 持久化生成结果
- 记录Token使用量

## 关键模块定位

| 需求 | 位置 |
|-----|------|
| 添加新API端点 | `backend/api/v1/*.py` |
| 添加新数据模型 | `core/models/*.py`, 同步更新 `backend/schemas/*.py` |
| 修改Agent行为 | `agents/*.py` |
| 添加新审查循环 | 继承 `agents/base/review_loop_base.py` 的 `BaseReviewLoopHandler` |
| 调整LLM调用 | `llm/qwen_client.py` |
| 修改审查配置 | `backend/config.py` 的 `ENABLE_*` 和 `*_THRESHOLD` 系列 |
| 前端页面 | `frontend/src/pages/*.tsx` |
| 前端API调用 | `frontend/src/api/*.ts` |

## 代码规范

- **行长度**: 100字符 (ruff配置)
- **类型提示**: 参数和返回值必须标注
- **Docstring**: PEP 257标准，使用中文
- **日志**: `from core.logging_config import logger`
- **异常**: `from core.exceptions import *`

### 反模式（禁止）

- 禁止硬编码密码：`DB_PASSWORD`必须通过环境变量
- 禁止裸except：必须指定异常类型
- 禁止用户输入含 `<>{}|\\^` 特殊字符
- 禁止直接返回ORM对象：必须经Pydantic schema转换
- 禁止模仿`agents/`中的Few-shot示例作为真实输出

## 环境配置

**必需环境变量**:
- `DASHSCOPE_API_KEY`: 通义千问API密钥
- `DB_PASSWORD` 或 `DATABASE_URL`: 数据库密码

**Docker环境检测**:
- `DOCKER_ENV=dev` → 使用开发容器服务名
- `DOCKER_ENV=true` → 使用生产容器服务名
- 无设置 → 使用localhost和映射端口

## 测试标记

可用pytest标记: `unit`, `integration`, `e2e`, `smoke`, `slow`, `creation`

## 前端开发

```bash
cd frontend
npm install            # 安装依赖
npm run dev            # 开发服务器
npm run build          # 生产构建
npm run lint           # ESLint检查
```

前端状态管理使用Zustand，路由使用React Router 7。