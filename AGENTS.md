# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-29
**Commit:** 5f78111
**Branch:** develop

## OVERVIEW

AI多Agent小说系统，基于CrewAI和Qwen，提供企划、写作、审查、发布能力。

## STRUCTURE

```
./
├── agents/           # Agent系统核心 (41 files)
├── backend/          # FastAPI REST API (22 services)
├── core/             # 共享基础设施 (16 models)
├── llm/              # Qwen客户端封装
├── workers/          # Celery异步任务
├── frontend/         # TypeScript/React前端
├── tests/           # 测试套件 (unit/e2e/ai_e2e)
├── scripts/         # 工具脚本 (23 files)
├── alembic/         # 数据库迁移
└── docs/            # 文档
```

## PROJECT METRICS

- **Python文件**: 253 (42个 >500行)
- **TypeScript文件**: ~90
- **最大目录深度**: 5层
- **测试标记**: unit, integration, e2e, smoke, slow, creation

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Agent定义 | `agents/` | CrewAI扩展，包含审查循环、连续性管理 |
| REST API | `backend/api/v1/` | 12个路由模块 |
| 数据库模型 | `core/models/` | 16个SQLAlchemy模型 |
| 业务服务 | `backend/services/` | 21个服务类 |
| LLM调用 | `llm/qwen_client.py` | 通义千问SDK封装 |
| 测试运行 | `tests/` | unit/integration/e2e/ai_e2e |
| 启动后端 | `uvicorn backend.main:app` | 端口8000 |
| 运行测试 | `pytest tests/ -v` | 带标记: -m smoke |

## CODE MAP

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| Settings | class | backend/config.py | 全局配置单例 |
| QwenClient | class | llm/qwen_client.py | LLM调用封装 |
| CrewManager | class | agents/crew_manager.py | Agent编排器 |
| GenerationService | class | backend/services/ | 生成任务编排 |
| Novel | model | core/models/novel.py | 小说ORM模型 |

## CONVENTIONS

- **行长度**: 100字符 (ruff target-version: py312)
- **类型提示**: 必须使用，针对参数和返回值
- **导入排序**: ruff I规则自动处理
- **Docstring**: PEP 257，中文编写
- **日志**: `from core.logging_config import logger`
- **异常**: `from core.exceptions import *`

## ANTI-PATTERNS (THIS PROJECT)

- **禁止硬编码密码**: `DB_PASSWORD` 必须通过环境变量设置
- **禁止裸except**: 必须指定异常类型 (已发现多处违规: ai_chat_service.py, novel_creation_flow_manager.py)
- **禁止特殊字符**: 标题等用户输入禁止 `<>{}|\\^`
- **不要模仿示例**: `agents/` 中的 Few-shot 示例仅供启发
- **禁止直接返回ORM对象**: 必须通过Pydantic schema转换

## COMMANDS

```bash
# 开发环境启动
./start_dev.sh                    # Docker Compose完整环境

# 后端独立
uvicorn backend.main:app --reload --port 8000

# 测试
pytest tests/ -v                  # 所有测试
pytest tests/unit/ -v            # 单元测试
pytest tests/e2e/ -v             # E2E测试
pytest -m smoke -v               # 冒烟测试
pytest -m "not slow" -v          # 排除慢测试

# 代码检查
ruff check .                     # ruff lint
ruff format .                    # ruff format

# 数据库迁移
alembic upgrade head             # 升级
alembic revision --autogenerate  # 生成迁移
```

## NOTES

- 前端: TypeScript + Vite + React (端口3000)
- 数据库: PostgreSQL + SQLAlchemy async
- 缓存: Redis (task broker + cache)
- LLM: 通义千问 (DASHSCOPE_API_KEY)
- 审查循环: Designer-Editor模式，质量阈值8.0
- 连续性: 三层存储同步 (SQL + Redis + SQLite)
