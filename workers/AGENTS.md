# WORKERS 模块

**Celery异步任务**: 后台小说生成Worker

## OVERVIEW

Celery任务队列处理异步小说生成任务，支持并发和超时控制。

## WHERE TO LOOK

| 文件 | 用途 |
|------|------|
| `celery_app.py` | Celery应用配置 |
| `generation_worker.py` | 生成任务Worker |

## USAGE

```bash
# 启动Worker
celery -A workers.celery_app worker --loglevel=info -c 2

# 任务调用
from workers.generation_worker import generate_chapter_task
task = generate_chapter_task.delay(novel_id, chapter_number)
```

## CONVENTIONS

- **超时**: 默认10分钟超时
- **并发**: 2个并发worker
- **结果存储**: Redis backend
- **重试**: 失败自动重试3次
