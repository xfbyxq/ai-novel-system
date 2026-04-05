# LLM 模块

**LLM集成层**: Qwen客户端封装、成本追踪、提示词管理

## OVERVIEW

通义千问（Qwen）API封装，提供统一的LLM调用接口、成本追踪、提示词管理。

## WHERE TO LOOK

| 文件 | 用途 |
|------|------|
| `qwen_client.py` | QwenClient主类，API调用封装 |
| `cost_tracker.py` | Token使用量和成本追踪 |
| `prompt_manager.py` | 提示词模板管理 |

## QWEN CLIENT

```python
from llm.qwen_client import QwenClient

client = QwenClient(
    api_key=settings.DASHSCOPE_API_KEY,
    model=settings.DASHSCOPE_MODEL,
)
response = await client.chat(messages=[...])
```

## CONVENTIONS

- **调用方式**: 始终使用 `async/await`
- **成本追踪**: 使用 `CostTracker.track()` 记录token消耗
- **错误处理**: 捕获 `LLMError` 异常
- **重试机制**: 使用 `tenacity` 自动重试

## EXTERNAL DEPS

- `dashscope`: 通义千问SDK
- `openai`: OpenAI兼容接口
