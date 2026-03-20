"""
API 认证中间件

提供基于 API Key 的请求认证，保护 API 端点免受未授权访问。
"""

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.config import settings


class APIKeyAuth:
    """API Key 认证类"""
    
    def __init__(self):
        self.security = HTTPBearer(auto_error=False)
    
    async def __call__(self, request: Request) -> str:
        """
        验证 API Key
        
        Args:
            request: FastAPI 请求对象
            
        Returns:
            验证通过的 API Key
            
        Raises:
            HTTPException: 认证失败时抛出
        """
        # 开发环境可跳过认证（方便调试）
        if settings.APP_ENV == "development" and not settings.DASHSCOPE_API_KEY:
            return "dev-mode"
        
        credentials = await self.security(request)
        
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="缺少认证凭据",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 验证 API Key
        if credentials.credentials != settings.DASHSCOPE_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的 API Key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return credentials.credentials


# 全局认证实例
api_key_auth = APIKeyAuth()


async def verify_api_key(request: Request, credentials: HTTPAuthorizationCredentials = None) -> str:
    """
    验证 API Key 的依赖注入函数
    
    用法：
    @app.get("/protected")
    async def protected_endpoint(api_key: str = Depends(verify_api_key)):
        pass
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 开发环境可跳过认证
    if settings.APP_ENV == "development" and not settings.DASHSCOPE_API_KEY:
        return "dev-mode"
    
    if credentials.credentials != settings.DASHSCOPE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return credentials.credentials
