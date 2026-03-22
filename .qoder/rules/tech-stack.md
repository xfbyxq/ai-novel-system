---
trigger: code_generation,code_modification
---

# 技术栈规范

## 后端技术栈
| 技术 | 版本 | 用途 |
|------|------|------|
| Python | >=3.12,<3.13 | 后端语言 |
| FastAPI | ^0.115.0 | Web框架 |
| Uvicorn | ^0.34.0 | ASGI服务器 |
| SQLAlchemy | ^2.0.0 | ORM框架 |
| PostgreSQL | - | 主数据库 |
| Redis | ^5.0.0 | 缓存/消息队列 |
| Celery | ^5.4.0 | 异步任务队列 |
| CrewAI | ^0.100.0 | AI Agent框架 |
| Dashscope | ^1.20.0 | 通义千问LLM集成 |
| Alembic | ^1.14.0 | 数据库迁移 |
| Pydantic | ^2.0.0 | 数据验证 |

## 前端技术栈
| 技术 | 版本 | 用途 |
|------|------|------|
| React | ^19.2.0 | UI框架 |
| TypeScript | ~5.9.3 | 类型系统 |
| Vite | ^7.3.1 | 构建工具 |
| Ant Design | ^6.3.0 | UI组件库 |
| React Router | ^7.13.0 | 路由管理 |
| Zustand | ^5.0.11 | 状态管理 |
| Axios | ^1.13.5 | HTTP客户端 |
| @xyflow/react | ^12.10.1 | 流程图组件 |

## 开发工具
| 技术 | 版本 | 用途 |
|------|------|------|
| Poetry | - | Python包管理 |
| Ruff | ^0.8.0 | Python代码检查 |
| ESLint | ^9.39.1 | JS代码检查 |
| pytest | ^8.0.0 | Python测试框架 |
| Playwright | ^1.58.0 | E2E测试 |

## 代码格式化规范

### Python (Ruff配置)
- **行长度**: 100字符
- **目标版本**: Python 3.12
- **检查规则**: E, F, I, W (pycodestyle, pyflakes, isort, warnings)

### JavaScript/TypeScript (ESLint)
- 遵循ESLint默认规则
- 使用react-hooks规则
- 使用react-refresh规则

### 文档字符串
- 遵循PEP 257规范
- 忽略规则: D204, D211, D212, D403