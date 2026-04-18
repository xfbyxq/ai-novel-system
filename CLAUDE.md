# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 概述

AI 多 Agent 小说生成系统 (v2.5.0)，基于 CrewAI 设计模式和通义千问 (Qwen) LLM，提供企划、写作、审查、发布完整流程。当前分支为 `develop`，目标合入分支为 `master`。

---

## 常用命令

### 开发环境

```bash
# Docker Compose 一键启动（推荐）
./start_dev.sh

# 后端独立运行（本地开发）
uvicorn backend.main:app --reload --port 8000

# 前端独立运行
cd frontend && npm run dev

# 停止 Docker 服务
./docker-stop.sh
```

### 测试

```bash
pytest tests/ -v                         # 所有测试
pytest tests/unit/ -v                     # 单元测试
pytest tests/e2e/ -v                      # E2E 测试
pytest tests/unit/test_character.py -v    # 单个测试文件
pytest -m smoke -v                        # 冒烟测试（快速验证）
pytest -m "not slow" -v                   # 排除慢测试
pytest -k "continuity" -v                 # 按名称匹配测试
```

可用 pytest 标记: `unit`, `integration`, `network`, `smoke`, `slow`, `creation`, `graph`, `ai_e2e`, `ai_smoke`, `ai_regression`, `ui`, `edge_case`, `real_crawl`, `regression`

### 代码检查

```bash
ruff check .           # lint 检查
ruff check . --fix     # 自动修复 lint 问题
ruff format .          # 代码格式化
```

### 数据库迁移

```bash
alembic upgrade head                        # 升级到最新版本
alembic downgrade -1                        # 回退一个版本
alembic revision --autogenerate -m "描述"   # 自动生成迁移
```

Docker 环境中: `docker exec novel_backend alembic upgrade head`

### Docker 服务管理

```bash
docker-compose -f docker-compose.dev.yml up -d
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml logs -f backend
```

---

## 核心架构

### 三层架构

```
┌─────────────────────────────────────────────────────────┐
│  frontend/     React + TypeScript + Vite + Ant Design   │
│                端口 3000, Zustand 状态管理               │
├─────────────────────────────────────────────────────────┤
│  backend/      FastAPI + SQLAlchemy async               │
│                端口 8000, API 路由在 backend/api/v1/    │
├─────────────────────────────────────────────────────────┤
│  agents/       Agent 系统核心 (CrewAI 设计模式)          │
│  core/         共享基础设施 (database, models, utils)    │
│  llm/          LLM 调用封装 (DashScope SDK)              │
├─────────────────────────────────────────────────────────┤
│  workers/      Celery Worker (异步任务处理)              │
│  PostgreSQL    持久化存储 + Neo4j 图数据库               │
│  Redis         缓存 + Celery broker                     │
└─────────────────────────────────────────────────────────┘
```

### 数据流

```
API 请求 → GenerationService → AgentDispatcher → NovelCrewManager
         ↓                        ↓
    UnifiedContextManager    各 Agent 执行 (LLM 调用)
         ↓                        ↓
    PostgreSQL 持久化        CostTracker 记录成本
         ↓
    Neo4j 图数据库同步 (角色关系、剧情关联)
```

### 关键服务 (backend/services/)

| 服务 | 用途 |
|------|------|
| `generation_service.py` | API 层和 Agent 层的桥梁，协调生成流程 |
| `safe_chapter_generator.py` | 安全的章节生成（含预算控制） |
| `context_manager.py` | 上下文管理器，加载小说上下文 |
| `ai_chat_service.py` | AI 对话服务 |
| `publishing_service.py` | 多平台发布服务 |
| `novel_revision_service.py` | 自然语言修订服务 |
| `graph_query_service.py` | Neo4j 图数据库查询 |
| `hindsight_service.py` | 后见之明记忆系统 |

### Agent 系统 (agents/)

**核心编排器**:
- `crew_manager.py` → NovelCrewManager: 协调企划和写作阶段所有 Agent
- `agent_dispatcher.py` → AgentDispatcher: 在不同 Agent 实现间调度

**审查循环系统 (Designer-Reviewer 模式)**:

位于 `agents/base/review_loop_base.py`，使用模板方法模式封装迭代逻辑:

```
流程: Reviewer 评估 → 构造质量报告 → 检查退出条件 → Builder 修订 → 循环
```

继承此基类的审查循环:
- `review_loop.py` → 章节审查 (Writer-Editor)
- `world_review_loop.py` → 世界观审查
- `character_review_loop.py` → 角色设计审查
- `plot_review_loop.py` → 大纲审查

**审查配置** (`backend/config.py`):
| 配置项 | 默认值 | 说明 |
|-------|-------|------|
| `ENABLE_*_REVIEW` | True | 各阶段审查开关 |
| `*_QUALITY_THRESHOLD` | 8.0 | 质量阈值 (1-10) |
| `MAX_*_REVIEW_ITERATIONS` | 5 | 最大迭代次数 |

**Agent 间协作组件**:
- `team_context.py` → NovelTeamContext: Agent 间信息共享
- `voting_manager.py` → 企划阶段投票共识
- `agent_query_service.py` → Writer 写作过程中查询设定
- `context_compressor.py` → 上下文压缩
- `similarity_detector.py` → 内容相似度检测

**连续性保障系统**:
- `continuity_integration_module.py` → 章节连贯性集成
- `timeline_tracker.py` → 时间线追踪
- `spatial_tracker.py` → 空间位置追踪
- `character_consistency_tracker.py` → 角色一致性追踪
- `foreshadowing_tracker.py` → 伏笔追踪
- `consequence_tracker.py` → 剧情后果追踪

### 数据模型 (core/models/)

| 模型 | 用途 |
|------|------|
| `novel.py` | 小说项目 |
| `character.py` | 角色档案 |
| `chapter.py` | 章节内容 |
| `plot_outline.py` | 剧情大纲 |
| `world_setting.py` | 世界观设定 |
| `generation_task.py` | 生成任务 |
| `revision_plan.py` | 修订计划 |
| `token_usage.py` | Token 使用记录 |
| `ai_chat_session.py` | AI 对话会话 |

### LLM 调用 (llm/)

- `qwen_client.py` → DashScope SDK 封装，支持流式输出
- `cost_tracker.py` → Token 成本和费用追踪
- `prompt_manager.py` → 提示词模板管理（含章节语言规范）
- `token_calculator.py` → Token 计算工具

### Celery 异步任务 (workers/)

- `celery_app.py` → Celery 应用配置
- `generation_worker.py` → 生成任务 Worker

---

## 关键模块定位

| 需求 | 位置 |
|-----|------|
| 添加新 API 端点 | `backend/api/v1/` |
| 添加新数据模型 | `core/models/` + 同步更新 `backend/schemas/` |
| 修改 Agent 行为 | `agents/` |
| 添加新审查循环 | 继承 `agents/base/review_loop_base.py` 的 `BaseReviewLoopHandler` |
| 调整 LLM 调用 | `llm/qwen_client.py` |
| 修改审查配置 | `backend/config.py` 的 `ENABLE_*` 和 `*_THRESHOLD` 系列 |
| 前端页面 | `frontend/src/pages/` |
| 前端 API 调用 | `frontend/src/api/` |
| 修改提示词 | `llm/prompt_manager.py` |

---

## 代码规范

- **Python 版本**: 3.12+
- **行长度**: 100 字符 (ruff 配置)
- **类型提示**: 参数和返回值必须标注
- **Docstring**: PEP 257 标准，使用中文
- **日志**: `from core.logging_config import logger`
- **异常**: `from core.exceptions import *`
- **依赖管理**: Poetry (`pyproject.toml`)
- **数据库**: SQLAlchemy async + asyncpg

### 反模式（禁止）

- 禁止硬编码密码：`DB_PASSWORD` 必须通过环境变量
- 禁止裸 except：必须指定异常类型
- 禁止直接返回 ORM 对象：必须经 Pydantic schema 转换
- 禁止模仿 agents/ 中的 Few-shot 示例作为真实输出
- 禁止用户输入含 `<>{}|\\^` 特殊字符

---

## 环境配置

**必需环境变量** (参见 `.env.example`):
- `DASHSCOPE_API_KEY`: 通义千问 API 密钥
- `DB_PASSWORD` 或 `DATABASE_URL`: 数据库密码

**Docker 环境检测**:
- `DOCKER_ENV=dev` → 使用开发容器服务名
- `DOCKER_ENV=true` → 使用生产容器服务名
- 无设置 → 使用 localhost 和映射端口

**服务地址**:
| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |
| Neo4j | localhost:7687 |
