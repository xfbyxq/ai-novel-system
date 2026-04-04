# AI多Agent小说生成系统 - 产品需求规格说明书 (PRD)

**版本**: v1.1.0  
**日期**: 2026-04-04  
**状态**: 有效

---

## 1. 执行摘要

### 1.1 产品概述

Novel System 是一个基于 CrewAI 设计模式和通义千问(Qwen) LLM 的 AI 多Agent小说生成系统，提供从企划、写作、审查到发布的完整流程。

### 1.2 核心价值

- **智能化创作**: 多Agent协作，自动生成高质量小说内容
- **一致性保障**: 角色、情节、世界观全程一致性跟踪
- **效率提升**: 自动化审查循环，减少人工返工
- **全流程管理**: 从大纲到发布的端到端支持

---

## 2. 系统架构

### 2.1 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│  前端层 (Frontend)                                          │
│  React 19 + TypeScript 5.9 + Vite 7 + Ant Design 6          │
│  Zustand 状态管理 + React Router 7                          │
│  端口: 3000                                                  │
├─────────────────────────────────────────────────────────────┤
│  后端层 (Backend)                                            │
│  FastAPI + SQLAlchemy Async + Pydantic                      │
│  端口: 8000                                                  │
├─────────────────────────────────────────────────────────────┤
│  Agent层 (Agents)                                           │
│  CrewAI 设计模式 + QwenClient 直接调用                       │
├─────────────────────────────────────────────────────────────┤
│  数据层 (Data)                                               │
│  PostgreSQL (主数据库) + SQLite (记忆存储) + Neo4j (图数据库) │
├─────────────────────────────────────────────────────────────┤
│  LLM层 (LLM)                                                │
│  通义千问 API (DashScope SDK) + Token 计费跟踪               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心技术栈

| 层级 | 技术选型 |
|------|---------|
| 前端框架 | React 19, TypeScript 5.9, Vite 7 |
| UI组件库 | Ant Design 6 |
| 后端框架 | FastAPI 0.115+ |
| 数据库 | PostgreSQL 15+, SQLite (FTS5) |
| 图数据库 | Neo4j 5.15 |
| Python版本 | Python 3.12 |
| LLM | 通义千问 (DashScope) |

---

## 3. 功能模块

### 3.1 小说管理模块

#### 3.1.1 小说基础管理

| 功能 | 描述 | 状态 |
|------|------|------|
| 创建小说 | 创建新小说项目，设置基本信息 | ✅ 已实现 |
| 小说列表 | 分页展示所有小说，支持搜索过滤 | ✅ 已实现 |
| 小说详情 | 展示小说完整信息，包含多Tab页面 | ✅ 已实现 |
| 小说删除 | 软删除小说，保留历史数据 | ✅ 已实现 |

#### 3.1.2 小说数据模型

```
Novel
├── id: UUID (主键)
├── title: str (标题)
├── genre: str (类型)
├── synopsis: str (简介)
├── status: NovelStatus (草稿/进行中/已完成)
├── current_outline_version: int (当前大纲版本)
├── created_at: datetime
└── updated_at: datetime
```

### 3.2 大纲管理模块

#### 3.2.1 大纲编辑

| 功能 | 描述 | 状态 |
|------|------|------|
| PlotOutline 编辑 | 大纲主线条管理 | ✅ 已实现 |
| 卷结构定义 | 支持多卷结构 | ✅ 已实现 |
| 大纲版本控制 | 记录历史版本 | ✅ 已实现 |
| AI大纲完善 | LLM辅助优化大纲 | ✅ 已实现 |

#### 3.2.2 大纲审查循环

继承 `BaseReviewLoopHandler` 的 `PlotReviewLoop`，提供：
- 自动评估大纲质量 (1-10 分)
- 迭代优化直到达到阈值 (默认8.0分)
- 最大迭代次数保护 (默认5次)

### 3.3 角色管理模块

#### 3.3.1 角色CRUD

| 功能 | 描述 | 状态 |
|------|------|------|
| 创建角色 | 添加角色基本信息 | ✅ 已实现 |
| 角色列表 | 按小说筛选展示角色 | ✅ 已实现 |
| 角色详情 | 完整角色信息 | ✅ 已实现 |
| 角色关系图 | Neo4j 可视化关系 | ✅ 已实现 |
| 角色一致性检测 | 自动检测冲突 | ✅ 已实现 |

#### 3.3.2 角色数据模型

```
Character
├── id: UUID
├── novel_id: UUID (外键)
├── name: str
├── gender: Gender (男/女/其他)
├── role_type: RoleType (主角/配角/反派/路人)
├── personality: str
├── background: str
├── appearance: str
├── speech_style: str
├── character_arc: str
├── relationships: List[Relationship]
└── created_at: datetime
```

#### 3.3.3 角色审查循环

`CharacterReviewLoop` 提供：
- 角色设计质量评估
- 角色间一致性检查
- 角色弧线完整性验证

### 3.4 世界观管理模块

#### 3.4.1 世界设定

| 功能 | 描述 | 状态 |
|------|------|------|
| 创建世界观 | 添加世界设定 | ✅ 已实现 |
| 世界设定编辑 | 修改世界观内容 | ✅ 已实现 |
| 世界观审查 | 评估设定完整性 | ✅ 已实现 |
| 空间位置跟踪 | 追踪场景位置变化 | ✅ 已实现 |

#### 3.4.2 世界审查循环

`WorldReviewLoop` 提供：
- 世界观一致性检查
- 地理/时间线冲突检测
- 规则体系完整性验证

### 3.5 章节生成模块

#### 3.5.1 章节管理

| 功能 | 描述 | 状态 |
|------|------|------|
| 章节列表 | 按卷/部展示章节 | ✅ 已实现 |
| 章节生成 | AI自动生成章节内容 | ✅ 已实现 |
| 章节编辑 | 手动修改生成内容 | ✅ 已实现 |
| 章节状态 | 草稿/待审/已发布 | ✅ 已实现 |

#### 3.5.2 生成配置

```python
ChapterGenerationConfig
├── quality_threshold: float = 8.0  # 质量阈值
├── max_review_iterations: int = 5  # 最大审查迭代
├── enable_world_review: bool = True  # 世界观审查
├── enable_character_review: bool = True  # 角色审查
├── enable_plot_review: bool = True  # 情节审查
├── enable_outline_refinement: bool = True  # 大纲细化
├── context_compressor_max_tokens: int = 8000  # 上下文压缩
└── enable_voting: bool = True  # Agent投票
```

#### 3.5.3 章节审查循环

`ReviewLoop` (Writer-Editor模式)：
```
生成 → 审查评估 → 质量报告 → 达标? → Y: 完成
                        ↓ N
                    修订改进 → 重新生成
```

### 3.6 发布管理模块

#### 3.6.1 发布任务

| 功能 | 描述 | 状态 |
|------|------|------|
| 创建发布任务 | 设置目标平台和章节 | ✅ 已实现 |
| 发布历史 | 查看历史发布记录 | ✅ 已实现 |
| 发布状态跟踪 | 实时状态更新 | ✅ 已实现 |
| 多平台支持 | 番茄小说等平台集成 | ✅ 已实现 |

#### 3.6.2 平台账号管理

```
PlatformAccount
├── id: UUID
├── platform_name: str
├── account_name: str
├── api_key: str (加密存储)
├── api_secret: str (加密存储)
├── status: AccountStatus
└── created_at: datetime
```

### 3.7 AI聊天模块

#### 3.7.1 对话功能

| 功能 | 描述 | 状态 |
|------|------|------|
| 创建对话会话 | 开启新对话 | ✅ 已实现 |
| 发送消息 | 与AI交互 | ✅ 已实现 |
| 对话历史 | 持久化存储 | ✅ 已实现 |
| 上下文管理 | 自动压缩长对话 | ✅ 已实现 |

#### 3.7.2 记忆系统

| 功能 | 描述 | 状态 |
|------|------|------|
| 短期记忆 | SQLite + FTS5 全文搜索 | ✅ 已实现 |
| 长期记忆 | PostgreSQL 持久化 | ✅ 已实现 |
| 记忆检索 | 向量相似度搜索 | ✅ 已实现 |

### 3.8 自动化模块

#### 3.8.1 GitHub集成

| 功能 | 描述 | 状态 |
|------|------|------|
| Issue创建 | 从审查结果自动创建Issue | ✅ 已实现 |
| PR描述生成 | 自动生成PR描述 | ✅ 已实现 |
| 自动化工作流 | GitHub Actions CI/CD | ✅ 已实现 |

#### 3.8.2 自动化服务

`AutomationService` 提供：
- 定时任务执行
- 质量检查自动化
- 发布流程自动化

### 3.9 监控模块

#### 3.9.1 系统监控

| 功能 | 描述 | 状态 |
|------|------|------|
| LLM调用统计 | Token使用量跟踪 | ✅ 已实现 |
| 成本分析 | 按项目/功能统计成本 | ✅ 已实现 |
| Agent活动记录 | 记录所有Agent操作 | ✅ 已实现 |
| 性能指标 | 响应时间/吞吐量监控 | ✅ 已实现 |

---

## 4. Agent系统

### 4.1 核心编排器

| 组件 | 类名 | 职责 |
|------|------|------|
| Crew管理器 | `NovelCrewManager` | 协调企划和写作阶段所有Agent |
| Agent调度器 | `AgentDispatcher` | 在不同Agent实现间调度 |
| 团队上下文 | `NovelTeamContext` | Agent间信息共享 |

### 4.2 审查循环系统

基于 `BaseReviewLoopHandler` 的模板方法模式：

```
Reviewer评估 → 构造质量报告 → 检查退出条件 → Builder修订 → 循环
```

| 审查循环 | 文件 | 用途 |
|---------|------|------|
| ReviewLoop | review_loop.py | 章节审查 (Writer-Editor) |
| WorldReviewLoop | world_review_loop.py | 世界观审查 |
| CharacterReviewLoop | character_review_loop.py | 角色设计审查 |
| PlotReviewLoop | plot_review_loop.py | 大纲审查 |

### 4.3 协作组件

| 组件 | 文件 | 功能 |
|------|------|------|
| VotingManager | voting_manager.py | 企划阶段投票共识 |
| AgentQueryService | agent_query_service.py | Writer查询设定 |
| ContextCompressor | context_compressor.py | 上下文压缩 |
| SimilarityDetector | similarity_detector.py | 内容相似度检测 |

### 4.4 一致性保障组件

| 组件 | 文件 | 功能 |
|------|------|------|
| CharacterConsistencyTracker | character_consistency_tracker.py | 角色一致性跟踪 |
| ContinuityValidator | continuity_validation.py | 连续性验证 |
| TimelineTracker | timeline_tracker.py | 时间线跟踪 |
| SpatialTracker | spatial_tracker.py | 空间位置跟踪 |
| ForeshadowingTracker | foreshadowing_tracker.py | 伏笔跟踪 |
| WorldEvolutionTracker | world_evolution_tracker.py | 世界演化跟踪 |

---

## 5. API接口

### 5.1 路由结构

| 路由前缀 | 模块 | 功能 |
|---------|------|------|
| `/api/v1/novels` | novels.py | 小说管理 |
| `/api/v1/characters` | characters.py | 角色管理 |
| `/api/v1/chapters` | chapters.py | 章节管理 |
| `/api/v1/outlines` | outlines.py | 大纲管理 |
| `/api/v1/generation` | generation.py | 生成任务 |
| `/api/v1/publishing` | publishing.py | 发布管理 |
| `/api/v1/ai-chat` | ai_chat.py | AI对话 |
| `/api/v1/graph` | graph.py | 图数据库 |
| `/api/v1/monitoring` | monitoring.py | 系统监控 |
| `/api/v1/revenue` | revenue.py | 收入分析 |
| `/api/v1/automation` | automation.py | 自动化 |

### 5.2 数据验证

所有API使用Pydantic Schema进行请求/响应验证：
- `backend/schemas/` 目录下的schema文件
- 禁止直接返回ORM对象

---

## 6. 数据流

### 6.1 核心流程

```
API请求 → GenerationService → AgentDispatcher → NovelCrewManager
         ↓                        ↓
    UnifiedContextManager    各Agent执行(LLM调用)
         ↓                        ↓
    PostgreSQL持久化        CostTracker记录成本
```

### 6.2 上下文管理

`UnifiedContextManager` 负责：
- 从数据库加载小说上下文
- 构建Agent所需提示词
- 管理上下文生命周期

---

## 7. 前端页面

### 7.1 页面结构

| 页面 | 路径 | 功能 |
|------|------|------|
| 仪表盘 | `/` | 总览数据统计 |
| 小说列表 | `/novels` | 小说管理 |
| 小说详情 | `/novels/:id` | 小说详情多Tab |
| 发布任务 | `/publish` | 发布任务管理 |
| 平台账号 | `/platforms` | 平台账号配置 |
| 系统监控 | `/monitoring` | 系统状态监控 |
| 章节阅读 | `/read/:id` | 章节内容阅读 |

### 7.2 小说详情Tab

| Tab | 组件 | 功能 |
|-----|------|------|
| 概览 | OverviewTab.tsx | 小说基本信息 |
| 大纲 | PlotOutlineTab.tsx | 大纲编辑 |
| 大纲完善 | OutlineRefinementTab.tsx | AI辅助完善 |
| 章节 | ChaptersTab.tsx | 章节列表 |
| 角色 | CharactersTab.tsx | 角色管理 |
| 关系图 | RelationshipGraph.tsx | Neo4j可视化 |
| 世界观 | WorldSettingTab.tsx | 世界设定 |
| 生成历史 | GenerationHistoryTab.tsx | AI生成记录 |

---

## 8. 配置管理

### 8.1 环境变量

| 变量 | 必需 | 描述 |
|------|------|------|
| `DASHSCOPE_API_KEY` | 是 | 通义千问API密钥 |
| `DB_PASSWORD` | 是 | 数据库密码 |
| `DATABASE_URL` | 否 | 数据库连接URL |
| `DOCKER_ENV` | 否 | Docker环境标识 |

### 8.2 审查配置

```python
# 章节审查
ENABLE_CHAPTER_REVIEW = True
CHAPTER_QUALITY_THRESHOLD = 8.0
MAX_CHAPTER_REVIEW_ITERATIONS = 5

# 世界观审查
ENABLE_WORLD_REVIEW = True
WORLD_QUALITY_THRESHOLD = 8.0
MAX_WORLD_REVIEW_ITERATIONS = 5

# 角色审查
ENABLE_CHARACTER_REVIEW = True
CHARACTER_QUALITY_THRESHOLD = 8.0
MAX_CHARACTER_REVIEW_ITERATIONS = 5

# 大纲审查
ENABLE_PLOT_REVIEW = True
PLOT_QUALITY_THRESHOLD = 8.0
MAX_PLOT_REVIEW_ITERATIONS = 5
```

---

## 9. 部署架构

### 9.1 Docker部署

```
docker-compose.prod.yml
├── frontend (Node 20)
├── backend (Python 3.12)
├── nginx (反向代理)
├── postgres (主数据库)
├── neo4j (图数据库)
└── celery-worker (异步任务)
```

### 9.2 开发环境

```bash
./start_dev.sh  # Docker Compose一键启动
uvicorn backend.main:app --reload --port 8000  # 后端独立运行
cd frontend && npm run dev  # 前端独立运行
```

---

## 10. 代码规范

### 10.1 Python规范

| 规范 | 要求 |
|------|------|
| 格式化 | Ruff (行长度100字符) |
| Lint规则 | E, F, I, W |
| 类型提示 | 必须标注 |
| Docstring | PEP 257，中文注释 |
| 日志 | `from core.logging_config import logger` |
| 异常 | `from core.exceptions import *` |

### 10.2 TypeScript规范

| 规范 | 要求 |
|------|------|
| 框架 | React 19 + TypeScript 5.9 |
| 状态管理 | Zustand |
| UI库 | Ant Design 6 |
| 路由 | React Router 7 |
| 代码检查 | ESLint |

### 10.3 禁止模式

- ❌ 硬编码密码
- ❌ 裸except (必须指定类型)
- ❌ 用户输入含 `<>{}|\\^` 特殊字符
- ❌ 直接返回ORM对象
- ❌ 模仿Few-shot示例作为真实输出

---

## 11. 测试策略

### 11.1 测试标记

| 标记 | 用途 |
|------|------|
| `unit` | 单元测试 |
| `integration` | 集成测试 |
| `e2e` | 端到端测试 |
| `smoke` | 冒烟测试 |
| `slow` | 慢测试 |
| `creation` | 创建功能测试 |

### 11.2 测试命令

```bash
pytest tests/ -v                   # 所有测试
pytest tests/unit/ -v              # 仅单元测试
pytest tests/e2e/ -v               # 仅E2E测试
pytest -m smoke -v                 # 冒烟测试
pytest -k "continuity" -v          # 按名称匹配
```

---

## 12. 未来规划

### 12.1 待实现功能

| 功能 | 优先级 | 状态 |
|------|--------|------|
| 多语言支持 | P1 | 规划中 |
| 协作写作模式 | P2 | 规划中 |
| 高级分析报告 | P2 | 规划中 |
| 插件系统 | P3 | 规划中 |

### 12.2 技术演进

- LLM模型升级支持
- 性能优化与缓存策略
- 安全性增强

---

## 13. 附录

### 13.1 相关文档

| 文档 | 路径 |
|------|------|
| AGENTS开发指南 | `/AGENTS.md` |
| 部署指南 | `/DEPLOYMENT_GUIDE.md` |
| API文档 | `/backend/api/v1/` |
| 数据库模型 | `/core/models/` |

### 13.2 变更历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.1.0 | 2026-04-04 | 当前版本 |
| v1.0.0 | 2025-XX | 初始版本 |
