# Issue #40: 大纲完善预览成本高 - 修复方案

## 问题描述

当前大纲完善预览 (`/outline/enhance-preview`) 存在以下性能问题：

1. **完整的 AI 处理流程**：调用 `refine_outline_comprehensive` 执行多轮改进
2. **双重质量评估**：对原始和增强后大纲都进行完整评估
3. **无缓存机制**：每次预览都重新计算
4. **高 Token 消耗**：完整流程消耗大量 LLM Token

## 修复方案

### 方案 1: 添加快速预览模式

实现一个轻量级的预览模式，只进行关键改进的预览：

```python
@router.post("/outline/enhance-preview/fast")
async def enhance_outline_preview_fast(...):
    """快速预览模式 - 仅预览关键改进"""
    # 1. 只进行单轮改进（而非多轮）
    # 2. 使用简化的评估指标
    # 3. 缓存最近的结果
```

### 方案 2: 增量预览

只预览用户选择的改进项：

```python
@router.post("/outline/enhance-preview/incremental")
async def enhance_outline_preview_incremental(...):
    """增量预览 - 仅预览选定的改进项"""
    # 用户指定要预览的改进类型
    # 只处理选定的改进
```

### 方案 3: 缓存优化

```python
from functools import lru_cache
import hashlib

def compute_outline_hash(outline: dict) -> str:
    """计算大纲哈希用于缓存"""
    return hashlib.md5(json.dumps(outline, sort_keys=True).encode()).hexdigest()

@lru_cache(maxsize=100)
def cached_preview(outline_hash: str, options_hash: str):
    """缓存预览结果"""
    pass
```

## 推荐实现

结合以上三种方案：

1. **默认使用快速预览模式**
2. **提供完整预览选项**（用户明确请求时）
3. **实现结果缓存**（5 分钟有效期）
4. **添加预览超时限制**（30 秒）

## 预期效果

- 预览时间：30 秒 → 5 秒
- Token 消耗：减少 70%
- 用户体验：显著提升响应速度

## 实施步骤

1. 添加 `fast_preview` 参数到 `EnhancementOptions`
2. 实现快速预览逻辑
3. 添加 Redis/内存缓存
4. 更新前端 UI 提供预览模式选择
