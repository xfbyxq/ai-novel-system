# 📚 AI 小说系统 - opencli 适配器

**API 地址**: http://127.0.0.1:3000  
**版本**: 1.0.0  
**作者**: 易大哥

## 🚀 快速开始

### 安装适配器

```bash
# 注册适配器到 opencli
opencli adapter register /Users/sanyi/.openclaw/workspace/novel_system/opencli-adapter
```

### 验证安装

```bash
# 查看可用的小说系统命令
opencli novel --help
```

---

## 📖 可用命令

### 1. 列出所有小说

```bash
opencli novel list
```

**输出示例**：
```
ID                                    标题          类型    章节数   状态
─────────────────────────────────────────────────────────────────────────
f0983ec7-e48b-4cb7-a8f4-21939fad63f9  周天星图     玄幻     1       连载中
```

---

### 2. 获取小说详情

```bash
opencli novel get <novel_id>
```

**示例**：
```bash
opencli novel get f0983ec7-e48b-4cb7-a8f4-21939fad63f9
```

---

### 3. 创建新小说

```bash
opencli novel create --title "我的小说" --genre "玄幻" --description "这是一个精彩的故事"
```

**参数**：
- `--title` (必需): 小说标题
- `--genre` (可选): 小说类型，默认"玄幻"
- `--description` (可选): 小说简介

---

### 4. 获取章节列表

```bash
opencli novel chapters <novel_id>
```

**示例**：
```bash
opencli novel chapters f0983ec7-e48b-4cb7-a8f4-21939fad63f9
```

---

### 5. AI 生成章节

```bash
opencli novel generate <novel_id> <chapter_number> --outline "章节大纲"
```

**示例**：
```bash
opencli novel generate f0983ec7-e48b-4cb7-a8f4-21939fad63f9 2 --outline "主角觉醒新的能力"
```

**参数**：
- `novel_id` (必需): 小说 ID
- `chapter_number` (必需): 章节编号
- `--outline` (可选): 章节大纲

**超时**: 120 秒（AI 生成可能需要较长时间）

---

### 6. 获取角色列表

```bash
opencli novel characters <novel_id>
```

**示例**：
```bash
opencli novel characters f0983ec7-e48b-4cb7-a8f4-21939fad63f9
```

---

### 7. 获取小说状态统计

```bash
opencli novel status <novel_id>
```

**示例**：
```bash
opencli novel status f0983ec7-e48b-4cb7-a8f4-21939fad63f9
```

---

## 🔧 配置

### 修改 API 地址

如果小说系统 API 不在 `http://localhost:8000`，编辑 `manifest.json`：

```json
{
  "commands": [
    {
      "endpoint": "http://YOUR_HOST:YOUR_PORT/api/v1/novels"
    }
  ]
}
```

### 添加认证

如果 API 需要认证，在 `manifest.json` 中添加：

```json
{
  "auth": {
    "type": "bearer",
    "token": "YOUR_API_TOKEN"
  }
}
```

---

## 💡 使用技巧

### 1. 结合 jq 使用

```bash
# 获取小说列表并格式化
opencli novel list -f json | jq '.[].title'

# 获取特定小说的章节数
opencli novel get <novel_id> -f json | jq '.chapter_count'
```

### 2. 批量操作

```bash
# 批量生成章节
for i in {1..5}; do
  opencli novel generate <novel_id> $i
done
```

### 3. 自动化脚本

```bash
#!/bin/bash
# 创建新小说并生成第一章

NOVEL_ID=$(opencli novel create --title "新书" | jq -r '.id')
opencli novel generate $NOVEL_ID 1 --outline "故事开始"
```

---

## 🐛 故障排查

### 命令不工作？

```bash
# 检查 API 是否可访问
curl http://localhost:8000/api/v1/novels

# 检查适配器是否注册
opencli adapter list

# 查看详细错误
opencli novel list --verbose
```

### 超时问题？

AI 生成章节可能需要较长时间，可以：
- 增加 `timeout` 值（在 `manifest.json` 中）
- 使用 `--timeout` 参数

---

## 📝 扩展适配器

你可以添加更多命令到 `manifest.json`：

```json
{
  "commands": [
    {
      "name": "your-command",
      "description": "命令描述",
      "type": "api",
      "method": "GET|POST|PUT|DELETE",
      "endpoint": "http://localhost:8000/api/v1/...",
      "params": [...],
      "output": "table|json|text"
    }
  ]
}
```

---

## 📚 更多信息

- [opencli 文档](https://github.com/jackwener/opencli)
- [小说系统 API 文档](http://localhost:8000/docs)

---

**作者**: 易大哥  
**版本**: 1.0.0  
**最后更新**: 2026-03-21
