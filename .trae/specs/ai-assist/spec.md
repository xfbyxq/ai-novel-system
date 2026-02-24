# AI 辅助创建功能规格

## Why
用户当前在创建小说或爬虫任务时，需要手动填写大量信息（如标题、类型、标签、简介、世界观设定、角色设定、爬取配置等）。通过引入 AI 辅助，用户可以通过自然语言描述需求，AI 理解用户意图并自动填充或更新表单内容，大幅提升效率。

## What Changes
- 重新设计 AI 辅助功能，将创建表单与 AI 对话合并
- 用户通过自然语言描述需求，AI 解析并提取结构化信息
- AI 解析结果实时更新到表单字段
- 后端新增意图解析和表单填充 API
- 前端改造创建 Modal，集成 AI 对话面板

## Impact
- Affected specs: 替代原有的纯对话 AI 辅助设计
- Affected code:
  - backend/api/v1/ai_chat.py (修改)
  - backend/services/ai_chat_service.py (修改)
  - frontend/src/components/AIChatDrawer.tsx (修改)
  - frontend/src/pages/NovelList.tsx (修改)
  - frontend/src/pages/CrawlerTasks.tsx (修改)

## ADDED Requirements
### Requirement: AI 辅助表单填充
系统 SHALL 提供 AI 辅助表单填充能力，用户通过自然语言描述需求，AI 自动解析并填充表单字段。

#### Scenario: 小说创建 - 用户描述需求
- **WHEN** 用户在小说创建表单中点击"AI 辅助"并输入 "我想写一个玄幻小说，主角叫张凡，父母被魔教所杀，立志复仇"
- **THEN** AI 解析用户输入，提取：
  - genre = "玄幻"
  - title = "张凡的修仙之路" 或类似（AI 根据描述生成标题建议）
  - synopsis = 用户描述的摘要
- **AND** 表单字段自动更新为解析结果

#### Scenario: 小说创建 - 用户询问建议
- **WHEN** 用户输入 "有什么有趣的玄幻小说设定推荐"
- **THEN** AI 返回多个创意建议
- **AND** 用户选择后，表单字段更新为选定的建议内容

#### Scenario: 爬虫任务创建 - 用户描述需求
- **WHEN** 用户在爬虫任务表单中点击"AI 辅助"并输入 "帮我爬取起点月票榜前 50 本书"
- **THEN** AI 解析用户输入，提取：
  - crawl_type = "ranking"
  - config.ranking_type = "yuepiao"
  - config.max_pages = 5
- **AND** 表单字段自动更新为解析结果

#### Scenario: 表单实时更新
- **WHEN** AI 返回解析结果后
- **AND** 用户可以继续编辑或再次请求 AI 辅助
- **THEN** 表单保留用户手动修改的内容

### Requirement: AI 意图解析 API
系统 SHALL 提供意图解析 API，将用户自然语言输入转换为结构化表单数据。

#### Scenario: 解析小说创建意图
- **WHEN** 前端调用 POST /api/v1/ai-chat/parse-novel
- **AND** 请求体包含用户输入的自然语言描述
- **THEN** 返回解析后的结构化数据，包括：genre, title, tags, synopsis 等字段

#### Scenario: 解析爬虫任务意图
- **WHEN** 前端调用 POST /api/v1/ai-chat/parse-crawler
- **AND** 请求体包含用户输入的自然语言描述
- **THEN** 返回解析后的结构化数据，包括：crawl_type, config 等字段

### Requirement: 混合对话 + 表单填充模式
系统 SHALL 在同一界面中提供对话和表单填充两种能力的融合。

#### Scenario: 对话中提取信息
- **WHEN** 用户与 AI 对话过程中
- **AND** AI 识别到可以提取的结构化信息
- **THEN** 显示"应用到表单"按钮，点击后填充对应字段

#### Scenario: 建议模式
- **WHEN** 用户请求创意建议（如 "推荐几个热血小说类型"）
- **AND** AI 返回多个选项
- **THEN** 每个选项附带"选用"按钮，点击后应用到表单

## MODIFIED Requirements
### Requirement: 小说创建页面
- 移除独立的"AI 辅助"按钮
- 在创建 Modal 内部集成 AI 对话面板
- AI 对话与表单填充实时同步

### Requirement: 爬虫任务创建页面
- 移除独立的"AI 辅助"按钮
- 在创建 Modal 内部集成 AI 对话面板
- AI 对话与表单填充实时同步

## REMOVED Requirements
### Requirement: 独立的 AI 对话抽屉
**Reason**: 改为在创建 Modal 内部直接集成 AI 对话，减少操作步骤
**Migration**: 现有对话抽屉组件将改造为创建 Modal 内的 AI 面板
