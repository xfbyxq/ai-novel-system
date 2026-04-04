---
trigger: always_on
alwaysApply: true
---

# 个人编码规范与交互规则

## 基础交互规则
1. **语言要求**：请始终使用中文回答
2. **代码注释**：为复杂逻辑和关键节点添加详细中文注释（PEP 257风格，中文docstring）
3. **内容深度**：提供详细解释和示例，不仅给结论
4. **格式要求**：代码超过20行时考虑聚合，保持可读性

## Python编码风格
- **格式化工具**：Ruff（行长度100字符，目标py312）
- **Lint规则**：E（PEP 8）、F（Pyflakes）、I（isort）、W（警告）
- **类型提示**：参数和返回值必须标注类型（MyPy检查）
- **命名规范**：遵循PEP 8（snake_case函数/变量，PascalCase类名）
- **异步处理**：优先使用async/await，异常必须指定类型（禁止裸except）
- **日志规范**：统一使用 `from core.logging_config import logger`
- **异常规范**：统一使用 `from core.exceptions import *`
- **数据传输**：禁止直接返回ORM对象，必须经Pydantic schema转换
- **代码简洁**：避免冗余代码，追求简洁优雅的实现
- **性能考虑**：关注代码性能，避免明显的性能问题

## TypeScript/React前端规范
- **框架版本**：React 19 + TypeScript 5.9 + Vite 7
- **状态管理**：Zustand
- **UI组件库**：Ant Design 6
- **路由**：React Router 7
- **代码检查**：ESLint + TypeScript ESLint推荐规则
- **ECMAScript版本**：ES2020