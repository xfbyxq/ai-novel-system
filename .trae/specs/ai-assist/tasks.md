# Tasks

## Task 1: 修改后端 AI 解析服务
- [ ] Task 1.1: 修改 backend/services/ai_chat_service.py
  - 添加 parse_novel_intent() 方法：解析用户输入，提取小说相关字段
  - 添加 parse_crawler_intent() 方法：解析用户输入，提取爬虫任务相关字段
  - 保留对话功能，但增加结构化解析能力
- [ ] Task 1.2: 修改 backend/schemas/ai_chat.py
  - 添加 NovelParseRequest, NovelParseResponse Schema
  - 添加 CrawlerParseRequest, CrawlerParseResponse Schema

## Task 2: 修改后端 API 端点
- [ ] Task 2.1: 修改 backend/api/v1/ai_chat.py
  - 添加 POST /ai-chat/parse-novel 端点
  - 添加 POST /ai-chat/parse-crawler 端点
  - 保留现有对话端点

## Task 3: 改造前端 AI 面板组件
- [ ] Task 3.1: 修改 frontend/src/components/AIChatDrawer.tsx
  - 改为嵌入到 Modal 内部的 Panel 模式
  - 添加 onParse 回调 prop
  - 添加"应用到表单"按钮显示逻辑

## Task 4: 改造小说创建页面
- [ ] Task 4.1: 修改 frontend/src/pages/NovelList.tsx
  - 移除独立的"AI 辅助"按钮
  - 在 Modal 内部添加 AI 对话面板
  - 实现表单字段与 AI 解析结果同步

## Task 5: 改造爬虫任务创建页面
- [ ] Task 5.1: 修改 frontend/src/pages/CrawlerTasks.tsx
  - 移除独立的"AI 辅助"按钮
  - 在 Modal 内部添加 AI 对话面板
  - 实现表单字段与 AI 解析结果同步

# Task Dependencies
- Task 1.1 和 Task 1.2 完成后才能开始 Task 2.1
- Task 2.1 完成后才能开始 Task 3.1
- Task 3.1 完成后才能开始 Task 4.1 和 Task 5.1
