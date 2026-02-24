# Checklist

## 后端实现检查清单
- [ ] ai_chat_service.py 已添加 parse_novel_intent() 方法
- [ ] ai_chat_service.py 已添加 parse_crawler_intent() 方法
- [ ] ai_chat.py 已添加 NovelParseRequest/Response Schema
- [ ] ai_chat.py 已添加 CrawlerParseRequest/Response Schema
- [ ] API 端点 POST /ai-chat/parse-novel 可正常工作
- [ ] API 端点 POST /ai-chat/parse-crawler 可正常工作
- [ ] 现有对话端点仍然可用

## 前端实现检查清单
- [ ] AIChatDrawer 组件支持 Panel 嵌入模式
- [ ] AIChatDrawer 组件支持 onParse 回调
- [ ] NovelList Modal 内部集成 AI 对话面板
- [ ] 表单字段可响应 AI 解析结果
- [ ] CrawlerTasks Modal 内部集成 AI 对话面板
- [ ] 表单字段可响应 AI 解析结果

## 功能验证检查清单
- [ ] 小说创建：输入"玄幻小说，主角复仇"可解析出 genre=玄幻
- [ ] 爬虫任务：输入"爬取月票榜"可解析出 crawl_type=ranking
- [ ] AI 解析结果正确填充到表单字段
- [ ] 对话功能仍然可用
- [ ] 页面无控制台错误
