---
trigger: code_generation,code_modification
---

# 后端代码规范

## Python编码规范

### 命名规范
- **函数/变量**: 蛇形命名法 (snake_case)
- **类名**: 驼峰命名法 (PascalCase)
- **常量**: 全大写蛇形命名 (UPPER_SNAKE_CASE)
- **私有成员**: 前缀下划线 (_private_method)

### 文件结构规范
每个后端模块应包含:
```python
"""
模块功能描述

作者: Novel System
版本: x.x.x
"""
from typing import Optional, List, Dict, Any
# 导入顺序: 标准库 > 第三方库 > 本地模块

class ClassName:
    """类功能描述"""

    def __init__(self, param: str) -> None:
        """初始化方法

        Args:
            param: 参数说明
        """
        self.param = param

    def method_name(self, arg: int) -> Dict[str, Any]:
        """方法功能描述

        Args:
            arg: 参数说明

        Returns:
            返回值说明

        Raises:
            ValueError: 异常条件说明
        """
        return {"result": arg}
```

### 异步编程规范
- **强制使用try-catch**: 所有异步操作必须捕获异常
- **使用async/await**: I/O密集型操作必须异步化
- **连接池管理**: 数据库/Redis连接必须使用连接池

```python
# 正确示例
async def fetch_data():
    try:
        async with async_session() as session:
            result = await session.execute(select(Model))
            return result.scalars().all()
    except Exception as e:
        logger.error(f"获取数据失败: {e}")
        raise

# 错误示例 - 缺少异常处理
async def fetch_data():
    async with async_session() as session:
        result = await session.execute(select(Model))
        return result.scalars().all()
```

### API设计规范
- 使用FastAPI依赖注入管理依赖
- 所有API必须有Pydantic模型进行请求/响应校验
- 错误响应使用统一的异常处理格式
- 必须添加OpenAPI文档注释

```python
@router.get("/items/{item_id}", response_model=ItemResponse)
async def get_item(item_id: int) -> ItemResponse:
    """获取单个项目详情

    Args:
        item_id: 项目ID

    Returns:
        项目详情

    Raises:
        HTTPException: 项目不存在时抛出404
    """
    item = await service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="项目不存在")
    return ItemResponse.model_validate(item)
```

### 数据库操作规范
- 使用SQLAlchemy 2.0风格的声明式API
- 必须使用异步会话管理器
- 查询必须使用参数化查询防止SQL注入
- 大数据量查询必须分页

### 日志规范
- 使用Python标准logging模块
- 日志级别: DEBUG < INFO < WARNING < ERROR < CRITICAL
- 关键操作必须记录日志
- 敏感信息禁止记录日志

```python
import logging

logger = logging.getLogger(__name__)

# 记录不同级别日志
logger.debug("调试信息: {0}".format(detail))
logger.info("操作成功: {0}".format(message))
logger.warning("警告信息: {0}".format(warning))
logger.error("错误信息: {0}".format(error))
logger.critical("严重错误: {0}".format(critical))
```

### 性能考虑
- 避免在循环中进行数据库/网络操作
- 使用批量操作替代循环单条操作
- 合理使用缓存减少数据库查询
- 大文件上传使用流式处理