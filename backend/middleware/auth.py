"""
API 认证中间件.

提供基于 API Key 的请求认证，保护 API 端点免受未授权访问。
"""

from backend.dependencies import verify_api_key

# 全局认证实例
api_key_auth = verify_api_key


__all__ = ["api_key_auth", "verify_api_key"]
