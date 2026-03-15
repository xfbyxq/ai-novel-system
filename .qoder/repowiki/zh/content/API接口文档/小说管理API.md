# 小说管理API

<cite>
**本文档引用的文件**
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py)
- [backend/schemas/novel.py](file://backend/schemas/novel.py)
- [core/models/novel.py](file://core/models/novel.py)
- [backend/dependencies.py](file://backend/dependencies.py)
- [core/database.py](file://core/database.py)
- [backend/api/v1/__init__.py](file://backend/api/v1/__init__.py)
- [backend/main.py](file://backend/main.py)
- [frontend/src/api/novels.ts](file://frontend/src/api/novels.ts)
- [frontend/src/api/types.ts](file://frontend/src/api/types.ts)
- [backend/config.py](file://backend/config.py)
</cite>

## 目录
1. [简介](#简介)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构概览](#架构概览)
5. [详细组件分析](#详细组件分析)
6. [依赖分析](#依赖分析)
7. [性能考虑](#性能考虑)
8. [故障排除指南](#故障排除指南)
9. [结论](#结论)
10. [附录](#附录)

## 简介
本文件为小说管理API的详细技术文档，覆盖小说的完整CRUD操作，包括：
- GET /api/v1/novels：分页获取小说列表，支持状态筛选
- POST /api/v1/novels：创建新小说
- GET /api/v1/novels/{novel_id}：获取小说详情（包含世界观、角色数、章节数等关联信息）
- PATCH /api/v1/novels/{novel_id}：更新小说信息
- DELETE /api/v1/novels/{novel_id}：删除小说（级联删除相关数据）

文档详细说明每个端点的请求参数、响应格式、状态码处理、分页参数、状态枚举值、错误处理机制，并提供完整的请求/响应示例与常见使用场景。

## 项目结构
后端采用FastAPI + SQLAlchemy异步ORM架构，API版本化组织在v1模块下，数据库通过依赖注入提供会话管理。前端通过Axios客户端调用后端接口。

```mermaid
graph TB
subgraph "后端"
A[FastAPI 应用<br/>backend/main.py]
B[API 路由聚合<br/>backend/api/v1/__init__.py]
C[小说API<br/>backend/api/v1/novels.py]
D[依赖注入<br/>backend/dependencies.py]
E[数据库引擎<br/>core/database.py]
F[模型定义<br/>core/models/novel.py]
G[Pydantic Schema<br/>backend/schemas/novel.py]
end
subgraph "前端"
H[Axios 客户端<br/>frontend/src/api/client.ts]
I[小说API封装<br/>frontend/src/api/novels.ts]
J[类型定义<br/>frontend/src/api/types.ts]
end
H --> I
I --> A
A --> B
B --> C
C --> D
D --> E
E --> F
C --> G
F --> G
```

**图表来源**
- [backend/main.py](file://backend/main.py#L15-L32)
- [backend/api/v1/__init__.py](file://backend/api/v1/__init__.py#L11-L24)
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L22-L22)
- [backend/dependencies.py](file://backend/dependencies.py#L12-L19)
- [core/database.py](file://core/database.py#L11-L35)
- [core/models/novel.py](file://core/models/novel.py#L37-L66)
- [backend/schemas/novel.py](file://backend/schemas/novel.py#L8-L57)
- [frontend/src/api/client.ts](file://frontend/src/api/client.ts#L4-L8)
- [frontend/src/api/novels.ts](file://frontend/src/api/novels.ts#L1-L44)
- [frontend/src/api/types.ts](file://frontend/src/api/types.ts#L5-L44)

**章节来源**
- [backend/main.py](file://backend/main.py#L15-L32)
- [backend/api/v1/__init__.py](file://backend/api/v1/__init__.py#L11-L24)
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L22-L22)
- [backend/dependencies.py](file://backend/dependencies.py#L12-L19)
- [core/database.py](file://core/database.py#L11-L35)
- [core/models/novel.py](file://core/models/novel.py#L37-L66)
- [backend/schemas/novel.py](file://backend/schemas/novel.py#L8-L57)
- [frontend/src/api/client.ts](file://frontend/src/api/client.ts#L4-L8)
- [frontend/src/api/novels.ts](file://frontend/src/api/novels.ts#L1-L44)
- [frontend/src/api/types.ts](file://frontend/src/api/types.ts#L5-L44)

## 核心组件
- API路由器：定义了小说模块的路由前缀与标签，集中管理CRUD端点。
- Pydantic模型：定义请求与响应的数据结构，确保前后端数据一致性。
- ORM模型：定义数据库表结构及枚举类型，包含小说状态与篇幅类型。
- 依赖注入：提供异步数据库会话，自动处理事务与异常回滚。
- 前端封装：统一的HTTP客户端与类型定义，便于调用与类型安全。

**章节来源**
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L22-L22)
- [backend/schemas/novel.py](file://backend/schemas/novel.py#L8-L57)
- [core/models/novel.py](file://core/models/novel.py#L24-L35)
- [backend/dependencies.py](file://backend/dependencies.py#L12-L19)
- [core/database.py](file://core/database.py#L25-L35)
- [frontend/src/api/novels.ts](file://frontend/src/api/novels.ts#L1-L44)
- [frontend/src/api/types.ts](file://frontend/src/api/types.ts#L5-L44)

## 架构概览
小说API遵循REST风格，使用FastAPI的依赖注入与SQLAlchemy异步查询实现高效的数据访问。前端通过Axios进行HTTP请求，后端通过CORS中间件允许指定来源访问。

```mermaid
sequenceDiagram
participant FE as "前端应用"
participant AX as "Axios 客户端"
participant API as "FastAPI 应用"
participant R as "小说路由"
participant DEP as "依赖注入"
participant DB as "数据库引擎"
FE->>AX : 发送HTTP请求
AX->>API : 转发到 /api/v1/novels/*
API->>R : 路由到对应端点
R->>DEP : 获取数据库会话
DEP->>DB : 创建/获取异步会话
DB-->>R : 返回查询结果
R-->>FE : 返回JSON响应
```

**图表来源**
- [backend/main.py](file://backend/main.py#L22-L32)
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L25-L150)
- [backend/dependencies.py](file://backend/dependencies.py#L12-L19)
- [core/database.py](file://core/database.py#L25-L35)

**章节来源**
- [backend/main.py](file://backend/main.py#L22-L32)
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L25-L150)
- [backend/dependencies.py](file://backend/dependencies.py#L12-L19)
- [core/database.py](file://core/database.py#L25-L35)

## 详细组件分析

### 端点：GET /api/v1/novels
- 功能：分页获取小说列表，支持按状态筛选。
- 查询参数：
  - page：页码，最小为1
  - page_size：每页数量，最小为1，最大为100
  - status：可选，小说状态筛选（planning/writing/completed/published）
- 响应：NovelListResponse，包含items（小说列表）、total（总数）、page、page_size。
- 状态码：
  - 200 OK：成功返回数据
- 错误处理：
  - 参数校验失败时由FastAPI自动返回422 Unprocessable Entity
  - 无数据时返回空数组，total为0

请求示例
- GET /api/v1/novels?page=1&page_size=10&status=writing
- GET /api/v1/novels?page=2&page_size=20

响应示例
- 200 OK
  {
    "items": [
      {
        "id": "d2b8f1a4-1a2b-4c3d-8e5f-6a7b8c9d0e1f",
        "title": "示例小说",
        "author": "AI创作",
        "genre": "科幻",
        "tags": ["未来", "太空"],
        "status": "writing",
        "length_type": "medium",
        "word_count": 15000,
        "chapter_count": 12,
        "cover_url": null,
        "synopsis": "这是一个示例小说。",
        "target_platform": "番茄小说",
        "estimated_revenue": 0,
        "actual_revenue": 0,
        "token_cost": 0,
        "created_at": "2024-01-01T12:00:00Z",
        "updated_at": "2024-01-02T14:30:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 10
  }

常见场景
- 列表分页浏览：设置page与page_size
- 状态筛选：添加status参数过滤
- 性能优化：合理设置page_size，避免过大导致响应缓慢

**章节来源**
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L25-L63)
- [backend/schemas/novel.py](file://backend/schemas/novel.py#L53-L57)
- [frontend/src/api/novels.ts](file://frontend/src/api/novels.ts#L4-L13)
- [frontend/src/api/types.ts](file://frontend/src/api/types.ts#L26-L33)

### 端点：POST /api/v1/novels
- 功能：创建新小说。
- 请求体：NovelCreate
  - title：必填，小说标题
  - genre：必填，小说类型
  - tags：可选，标签列表
  - synopsis：可选，简介
  - target_platform：可选，默认"番茄小说"
  - length_type：可选，默认"medium"（short/medium/long）
- 响应：NovelResponse
- 状态码：
  - 201 Created：创建成功
  - 422 Unprocessable Entity：请求参数校验失败
- 错误处理：
  - 参数校验失败返回422
  - 数据库约束冲突由底层ORM抛出异常

请求示例
- POST /api/v1/novels
  {
    "title": "新小说",
    "genre": "悬疑",
    "tags": ["推理", "都市"],
    "synopsis": "这是一部悬疑小说。",
    "target_platform": "番茄小说",
    "length_type": "medium"
  }

响应示例
- 201 Created
  {
    "id": "a1b2c3d4-e5f6-7890-a1b2-c3d4e5f67890",
    "title": "新小说",
    "author": "AI创作",
    "genre": "悬疑",
    "tags": ["推理", "都市"],
    "status": "planning",
    "length_type": "medium",
    "word_count": 0,
    "chapter_count": 0,
    "cover_url": null,
    "synopsis": "这是一部悬疑小说。",
    "target_platform": "番茄小说",
    "estimated_revenue": 0,
    "actual_revenue": 0,
    "token_cost": 0,
    "created_at": "2024-01-03T09:00:00Z",
    "updated_at": "2024-01-03T09:00:00Z"
  }

常见场景
- 快速创建：仅提供必要字段title与genre
- 初始化状态：默认状态为planning，适合后续流程推进

**章节来源**
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L66-L78)
- [backend/schemas/novel.py](file://backend/schemas/novel.py#L8-L28)
- [frontend/src/api/novels.ts](file://frontend/src/api/novels.ts#L20-L23)
- [frontend/src/api/types.ts](file://frontend/src/api/types.ts#L26-L44)

### 端点：GET /api/v1/novels/{novel_id}
- 功能：获取小说详情，包含世界观、角色、章节数等关联信息。
- 路径参数：
  - novel_id：UUID，小说唯一标识
- 响应：NovelResponse（包含关联信息的预加载）
- 状态码：
  - 200 OK：成功
  - 404 Not Found：小说不存在
- 错误处理：
  - 未找到小说时返回404

请求示例
- GET /api/v1/novels/d2b8f1a4-1a2b-4c3d-8e5f-6a7b8c9d0e1f

响应示例
- 200 OK
  {
    "id": "d2b8f1a4-1a2b-4c3d-8e5f-6a7b8c9d0e1f",
    "title": "示例小说",
    "author": "AI创作",
    "genre": "科幻",
    "tags": ["未来", "太空"],
    "status": "writing",
    "length_type": "medium",
    "word_count": 15000,
    "chapter_count": 12,
    "cover_url": null,
    "synopsis": "这是一个示例小说。",
    "target_platform": "番茄小说",
    "estimated_revenue": 0,
    "actual_revenue": 0,
    "token_cost": 0,
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-02T14:30:00Z"
  }

常见场景
- 详情页展示：获取小说基础信息与统计指标
- 关联信息：前端可直接使用返回的关联数据减少二次请求

**章节来源**
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L81-L104)
- [core/models/novel.py](file://core/models/novel.py#L59-L66)
- [frontend/src/api/novels.ts](file://frontend/src/api/novels.ts#L15-L18)
- [frontend/src/api/types.ts](file://frontend/src/api/types.ts#L6-L24)

### 端点：PATCH /api/v1/novels/{novel_id}
- 功能：更新小说信息（部分字段）。
- 路径参数：
  - novel_id：UUID，小说唯一标识
- 请求体：NovelUpdate（可选字段）
  - title、genre、tags、synopsis、status、cover_url、target_platform、length_type
- 响应：NovelResponse
- 状态码：
  - 200 OK：更新成功
  - 404 Not Found：小说不存在
  - 422 Unprocessable Entity：请求参数校验失败
- 错误处理：
  - 未找到小说返回404
  - 参数校验失败返回422

请求示例
- PATCH /api/v1/novels/d2b8f1a4-1a2b-4c3d-8e5f-6a7b8c9d0e1f
  {
    "status": "completed",
    "word_count": 50000
  }

响应示例
- 200 OK
  {
    "id": "d2b8f1a4-1a2b-4c3d-8e5f-6a7b8c9d0e1f",
    "title": "示例小说",
    "author": "AI创作",
    "genre": "科幻",
    "tags": ["未来", "太空"],
    "status": "completed",
    "length_type": "medium",
    "word_count": 50000,
    "chapter_count": 12,
    "cover_url": null,
    "synopsis": "这是一个示例小说。",
    "target_platform": "番茄小说",
    "estimated_revenue": 0,
    "actual_revenue": 0,
    "token_cost": 0,
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-03T10:00:00Z"
  }

常见场景
- 状态变更：如从writing切换到completed
- 统计更新：如更新word_count、chapter_count等

**章节来源**
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L107-L130)
- [backend/schemas/novel.py](file://backend/schemas/novel.py#L18-L28)
- [frontend/src/api/novels.ts](file://frontend/src/api/novels.ts#L25-L28)
- [frontend/src/api/types.ts](file://frontend/src/api/types.ts#L35-L44)

### 端点：DELETE /api/v1/novels/{novel_id}
- 功能：删除小说（级联删除相关数据）。
- 路径参数：
  - novel_id：UUID，小说唯一标识
- 响应：无内容（204 No Content）
- 状态码：
  - 204 No Content：删除成功
  - 404 Not Found：小说不存在
- 错误处理：
  - 未找到小说返回404

请求示例
- DELETE /api/v1/novels/d2b8f1a4-1a2b-4c3d-8e5f-6a7b8c9d0e1f

响应示例
- 204 No Content

常见场景
- 清理无效数据：删除不再需要的小说及其关联内容
- 级联删除：确保相关的世界观、角色、章节、生成与发布任务一并清理

**章节来源**
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L133-L150)
- [core/models/novel.py](file://core/models/novel.py#L60-L66)
- [frontend/src/api/novels.ts](file://frontend/src/api/novels.ts#L30-L32)

### 数据模型与枚举
小说状态与篇幅类型的定义如下：

```mermaid
classDiagram
class NovelStatus {
+planning
+writing
+completed
+published
}
class NovelLengthType {
+short
+medium
+long
}
class Novel {
+id : UUID
+title : string
+author : string
+genre : string
+tags : list[string]
+status : NovelStatus
+length_type : NovelLengthType
+word_count : int
+chapter_count : int
+cover_url : string
+synopsis : string
+target_platform : string
+estimated_revenue : number
+actual_revenue : number
+token_cost : number
+created_at : datetime
+updated_at : datetime
+world_setting
+characters
+plot_outline
+chapters
+generation_tasks
+publish_tasks
}
```

**图表来源**
- [core/models/novel.py](file://core/models/novel.py#L24-L66)

**章节来源**
- [core/models/novel.py](file://core/models/novel.py#L24-L66)

### 端到端调用序列
以下序列图展示了前端调用小说API的典型流程（以创建为例）：

```mermaid
sequenceDiagram
participant FE as "前端应用"
participant AX as "Axios 客户端"
participant API as "FastAPI 应用"
participant R as "小说路由"
participant DEP as "依赖注入"
participant DB as "数据库引擎"
FE->>AX : 调用 createNovel(payload)
AX->>API : POST /api/v1/novels
API->>R : 进入 create_novel 处理器
R->>DEP : 依赖注入获取数据库会话
DEP->>DB : 创建小说记录
DB-->>R : 返回持久化后的对象
R-->>FE : 返回 NovelResponse (201)
```

**图表来源**
- [frontend/src/api/novels.ts](file://frontend/src/api/novels.ts#L20-L23)
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L66-L78)
- [backend/dependencies.py](file://backend/dependencies.py#L12-L19)
- [core/database.py](file://core/database.py#L25-L35)

**章节来源**
- [frontend/src/api/novels.ts](file://frontend/src/api/novels.ts#L20-L23)
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L66-L78)
- [backend/dependencies.py](file://backend/dependencies.py#L12-L19)
- [core/database.py](file://core/database.py#L25-L35)

## 依赖分析
- 路由聚合：API v1将各模块路由统一挂载，小说路由位于其中。
- 依赖注入：通过get_db提供异步会话，自动处理提交与回滚。
- 数据库引擎：基于异步PostgreSQL驱动，支持高并发读写。
- 前端类型：与后端Pydantic模型保持一致，确保类型安全。

```mermaid
graph LR
A[backend/api/v1/__init__.py] --> B[backend/api/v1/novels.py]
B --> C[backend/dependencies.py]
C --> D[core/database.py]
B --> E[backend/schemas/novel.py]
E --> F[core/models/novel.py]
G[frontend/src/api/novels.ts] --> A
H[frontend/src/api/types.ts] --> E
```

**图表来源**
- [backend/api/v1/__init__.py](file://backend/api/v1/__init__.py#L11-L24)
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L13-L20)
- [backend/dependencies.py](file://backend/dependencies.py#L12-L19)
- [core/database.py](file://core/database.py#L11-L35)
- [backend/schemas/novel.py](file://backend/schemas/novel.py#L8-L57)
- [core/models/novel.py](file://core/models/novel.py#L37-L66)
- [frontend/src/api/novels.ts](file://frontend/src/api/novels.ts#L1-L44)
- [frontend/src/api/types.ts](file://frontend/src/api/types.ts#L5-L44)

**章节来源**
- [backend/api/v1/__init__.py](file://backend/api/v1/__init__.py#L11-L24)
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L13-L20)
- [backend/dependencies.py](file://backend/dependencies.py#L12-L19)
- [core/database.py](file://core/database.py#L11-L35)
- [backend/schemas/novel.py](file://backend/schemas/novel.py#L8-L57)
- [core/models/novel.py](file://core/models/novel.py#L37-L66)
- [frontend/src/api/novels.ts](file://frontend/src/api/novels.ts#L1-L44)
- [frontend/src/api/types.ts](file://frontend/src/api/types.ts#L5-L44)

## 性能考虑
- 分页参数限制：page_size最大为100，避免单次返回过多数据。
- 异步数据库：使用异步引擎与会话，提升并发处理能力。
- 关联预加载：详情接口对关联实体进行selectinload，减少N+1查询风险。
- CORS限制：仅允许特定前端地址访问，降低跨域攻击面。
- 超时设置：前端Axios设置较长超时，适应长时间任务。

[本节为通用性能建议，不直接分析具体文件]

## 故障排除指南
- 404 Not Found：当novel_id不存在时返回。检查ID是否正确以及数据是否已删除。
- 422 Unprocessable Entity：请求参数校验失败。检查请求体字段类型与必填项。
- 数据库异常：依赖注入层自动回滚并抛出异常。检查数据库连接与权限。
- CORS问题：确认前端地址在CORS白名单内且请求头正确。

**章节来源**
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L101-L102)
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L120-L121)
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L145-L146)
- [backend/dependencies.py](file://backend/dependencies.py#L25-L35)
- [backend/main.py](file://backend/main.py#L22-L29)

## 结论
小说管理API提供了完整的CRUD能力，结合Pydantic模型与SQLAlchemy ORM实现了强类型与高性能的数据访问。通过合理的分页策略、异步数据库与CORS配置，满足了生产环境下的可用性与安全性需求。前端类型定义与Axios封装进一步提升了开发效率与调用体验。

[本节为总结性内容，不直接分析具体文件]

## 附录

### 状态枚举值
- 小说状态：planning（规划中）、writing（写作中）、completed（已完成）、published（已发布）
- 篇幅类型：short（短文）、medium（中篇小说）、long（长篇小说）

**章节来源**
- [core/models/novel.py](file://core/models/novel.py#L24-L35)

### 分页参数说明
- page：页码，从1开始
- page_size：每页数量，最小1，最大100

**章节来源**
- [backend/api/v1/novels.py](file://backend/api/v1/novels.py#L27-L29)

### 数据库配置
- 使用异步PostgreSQL驱动，连接池大小与溢出配置见数据库引擎初始化。
- 动态构建DATABASE_URL，支持从环境变量读取配置。

**章节来源**
- [core/database.py](file://core/database.py#L11-L22)
- [backend/config.py](file://backend/config.py#L18-L27)