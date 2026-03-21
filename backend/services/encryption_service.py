"""加密服务 - 用于加密/解密敏感凭证"""
import json
from typing import Any

from cryptography.fernet import Fernet

from backend.config import settings


class EncryptionService:
    """加密服务"""

    def __init__(self):
        """初始化加密服务"""
        key = settings.ENCRYPTION_KEY
        if not key:
            # 如果没有配置密钥，生成一个新的（仅用于开发）
            key = Fernet.generate_key().decode()
            print(f"警告: 未配置 ENCRYPTION_KEY，使用临时密钥。请在 .env 中设置: ENCRYPTION_KEY={key}")

        # 确保密钥是 bytes 类型
        if isinstance(key, str):
            key = key.encode()

        self._fernet = Fernet(key)

    def encrypt(self, data: str) -> str:
        """加密字符串数据

        Args:
            data: 要加密的字符串

        Returns:
            加密后的 base64 编码字符串
        """
        encrypted = self._fernet.encrypt(data.encode())
        return encrypted.decode()

    def decrypt(self, encrypted_data: str) -> str:
        """解密数据

        Args:
            encrypted_data: 加密后的 base64 编码字符串

        Returns:
            解密后的原始字符串
        """
        decrypted = self._fernet.decrypt(encrypted_data.encode())
        return decrypted.decode()

    def encrypt_dict(self, data: dict[str, Any]) -> str:
        """加密字典数据（转为 JSON 后加密）

        Args:
            data: 要加密的字典

        Returns:
            加密后的 base64 编码字符串
        """
        json_str = json.dumps(data, ensure_ascii=False)
        return self.encrypt(json_str)

    def decrypt_dict(self, encrypted_data: str) -> dict[str, Any]:
        """解密为字典数据

        Args:
            encrypted_data: 加密后的 base64 编码字符串

        Returns:
            解密后的字典
        """
        json_str = self.decrypt(encrypted_data)
        return json.loads(json_str)


# 全局单例
_encryption_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    """获取加密服务单例"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
