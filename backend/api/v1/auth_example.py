"""
API 认证使用示例.

展示如何在 API 端点中添加认证保护。
"""

from fastapi import APIRouter, Depends
from backend.dependencies import get_db, verify_api_key
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


# ========== 无需认证的端点 ========== #


@router.get("/public")
async def public_endpoint():
    """
    公开端点 - 无需认证.

    适用于：健康检查、公开文档、登录注册等
    """
    return {"message": "这是公开端点，无需认证"}


# ========== 需要认证的端点 ========== #


@router.get("/protected")
async def protected_endpoint(
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    受保护端点 - 需要 API Key 认证.

    使用方法：
    1. 在请求头中添加：Authorization: Bearer <your_api_key>
    2. 或使用 Swagger UI 的 Authorize 按钮配置 API Key

    适用于：
    - 小说管理（创建、更新、删除）
    - 章节生成
    - 发布操作
    - 敏感数据访问
    """
    return {
        "message": "认证成功！",
        "api_key_prefix": api_key[:8] + "..." if api_key != "dev-mode" else "dev-mode",
    }


# ========== 批量操作端点（需要认证） ========== #


@router.post("/bulk-operation")
async def bulk_operation(
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    批量操作端点 - 需要认证.

    示例：批量生成章节、批量发布等
    """
    return {"status": "authenticated", "operation": "bulk"}


# ========== 使用建议 ========== #
"""
1. 公开端点（无需认证）：
   - GET /health - 健康检查
   - GET / - API 信息
   - POST /api/v1/auth/login - 登录

2. 受保护端点（需要认证）：
   - 所有 POST/PUT/DELETE 操作
   - 敏感数据查询（用户信息、收入数据等）
   - 生成和发布操作

3. 测试认证：
   curl -H "Authorization: Bearer your_api_key" http://localhost:8000/api/v1/protected

4. Swagger UI 测试：
   - 访问 http://localhost:8000/docs
   - 点击右上角 "Authorize" 按钮
   - 输入：Bearer <your_api_key>
   - 点击 "Authorize" 确认
"""
