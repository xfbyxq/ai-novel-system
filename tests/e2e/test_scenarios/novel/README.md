# AI小说系统 - E2E测试用例

## 测试用例列表

| 功能 | 测试文件 | 说明 |
|------|----------|------|
| 小说创建 | `test_小说创建.py` | 测试创建新小说的完整流程 |
| 小说查看 | `test_小说查看.py` | 测试查看小说详情的功能 |
| 世界观查看 | `test_世界观查看.py` | 测试查看和编辑世界观的功能 |
| 大纲查看 | `test_大纲查看.py` | 测试查看和编辑大纲的功能 |
| 小说章节查看 | `test_小说章节查看.py` | 测试查看和管理章节的功能 |
| 添加企划任务 | `test_添加企划任务.py` | 测试在小说详情页添加企划任务的功能 |
| 批量生成小说任务 | `test_批量生成小说任务.py` | 测试批量生成小说内容的功能 |

## 运行测试

### 运行单个测试
```bash
cd /Users/sanyi/code/python/novel_system
pytest tests/e2e/test_scenarios/novel/test_小说创建.py -v
```

### 运行所有小说相关测试
```bash
pytest tests/e2e/test_scenarios/novel/ -v
```

### 使用AI E2E运行器
```bash
# 自主测试模式
python scripts/ai_e2e_runner.py --mode autonomous --goal "测试小说创建功能" --start-url "/novels"

# 测试生成模式
python scripts/ai_e2e_runner.py --mode generate --feature "小说管理"
```

## 生成时间
2026-03-23T22:07:01.966029

## 作者
Qoder - AI测试工程师
