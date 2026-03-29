# AGENTS 模块

**核心模块**: 多Agent协作系统，驱动小说创作流程

## OVERVIEW

基于CrewAI的多Agent系统，包含企划、写作、审查Agent，Designer-Reviewer模式。

## WHERE TO LOOK

| 组件 | 文件 | 用途 |
|------|------|------|
| Agent编排 | `crew_manager.py` | 主入口，管理所有Agent |
| 审查循环 | `review_loop.py` | Writer-Editor质量迭代 |
| 连续性管理 | `continuity_*.py` | 上下文传递和伏笔追踪 |
| 上下文压缩 | `context_compressor.py` | 防止LLM上下文溢出 |
| 角色一致性 | `character_consistency_tracker.py` | 跨章节角色一致性 |
| 大纲细化 | `outline_refiner.py` | 章节计划展开 |

## KEY CLASSES

| Class | File | Role |
|-------|------|------|
| CrewManager | crew_manager.py | Agent编排主控制器 |
| NovelPlanner | specific_agents.py | 企划阶段Agent |
| NovelWriter | specific_agents.py | 写作阶段Agent |
| ReviewLoopHandler | review_loop.py | 质量审查循环 |
| ContinuityValidator | continuity_validation.py | 连续性验证 |

## PATTERNS

### Agent任务定义
```python
# agents/tasks/ 下定义任务
TASK_NAME = """
任务描述...
期望输出格式...
"""
```

### 连续性注入
```python
# 在生成内容时自动注入前文上下文
from agents.continuity_propagator import ContinuityPropagator
propagator = ContinuityPropagator()
context = propagator.get_chapter_context(novel_id, chapter_number)
```

### 审查循环调用
```python
from agents.review_loop import ReviewLoopHandler
handler = ReviewLoopHandler(qwen_client, cost_tracker)
result = await handler.review_chapter(chapter_id, threshold=8.0)
```

## CONVENTIONS

- **Few-shot示例**: 仅供启发，禁止直接模仿
- **连续性检查**: 每章生成后必须调用 `ContinuityValidator`
- **上下文预算**: 单次LLM调用不超过6000字符
- **Agent通信**: 通过 `AgentCommunicator` 而非直接调用

## ANTI-PATTERNS

- **不要模仿示例内容**: `context_propagator.py` 第38行明确说明
- **不局限于示例**: `continuity_inference.py` 第55行警告
- **禁止跳过连续性检查**: 必须验证角色名、伏笔、关键情节

## EXTERNAL DEPS

- `crewai`: Agent框架基础
- `dashscope`: LLM调用
- `llm/qwen_client.py`: QwenClient封装
