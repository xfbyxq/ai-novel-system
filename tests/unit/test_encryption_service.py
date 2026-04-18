"""加密服务单元测试.

测试 EncryptionService 的加密解密功能.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestEncryptionService:
    """EncryptionService 测试类."""

    def test_encrypt_decrypt_roundtrip(self):
        """测试加密解密往返."""
        from backend.services.encryption_service import EncryptionService

        service = EncryptionService()

        original = "这是测试数据"
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)

        assert decrypted == original
        assert encrypted != original

    def test_encrypt_produces_different_output(self):
        """测试加密产生不同输出."""
        from backend.services.encryption_service import EncryptionService

        service = EncryptionService()

        data = "测试数据"
        encrypted1 = service.encrypt(data)
        encrypted2 = service.encrypt(data)

        assert encrypted1 != encrypted2

    def test_encrypt_empty_string(self):
        """测试加密空字符串."""
        from backend.services.encryption_service import EncryptionService

        service = EncryptionService()

        original = ""
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)

        assert decrypted == original

    def test_encrypt_unicode(self):
        """测试加密 Unicode 字符."""
        from backend.services.encryption_service import EncryptionService

        service = EncryptionService()

        original = "中文测试 🎉 emoji"
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)

        assert decrypted == original

    def test_encrypt_long_text(self):
        """测试加密长文本."""
        from backend.services.encryption_service import EncryptionService

        service = EncryptionService()

        original = "A" * 10000
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)

        assert decrypted == original

    def test_encrypt_dict(self):
        """测试加密字典."""
        from backend.services.encryption_service import EncryptionService

        service = EncryptionService()

        original = {"key": "value", "number": 123, "nested": {"a": 1}}
        encrypted = service.encrypt_dict(original)
        decrypted = service.decrypt_dict(encrypted)

        assert decrypted == original

    def test_encrypt_dict_with_unicode(self):
        """测试加密带中文的字典."""
        from backend.services.encryption_service import EncryptionService

        service = EncryptionService()

        original = {"用户名": "张三", "密码": "secret123"}
        encrypted = service.encrypt_dict(original)
        decrypted = service.decrypt_dict(encrypted)

        assert decrypted == original
        assert decrypted["用户名"] == "张三"

    def test_encrypt_dict_empty(self):
        """测试加密空字典."""
        from backend.services.encryption_service import EncryptionService

        service = EncryptionService()

        original = {}
        encrypted = service.encrypt_dict(original)
        decrypted = service.decrypt_dict(encrypted)

        assert decrypted == original

    def test_decrypt_invalid_data_raises(self):
        """测试解密无效数据抛出异常."""
        from backend.services.encryption_service import EncryptionService

        service = EncryptionService()

        with pytest.raises(Exception):
            service.decrypt("invalid_encrypted_data")

    def test_decrypt_wrong_key_raises(self):
        """测试用错误密钥解密抛出异常."""
        from backend.services.encryption_service import EncryptionService
        from cryptography.fernet import Fernet

        service1 = EncryptionService()
        key = Fernet.generate_key().decode()
        with patch("backend.services.encryption_service.settings") as mock_settings:
            mock_settings.ENCRYPTION_KEY = key
            service2 = EncryptionService()

        encrypted = service1.encrypt("测试数据")

        with pytest.raises(Exception):
            service2.decrypt(encrypted)

    def test_get_encryption_service_singleton(self):
        """测试获取加密服务单例."""
        from backend.services.encryption_service import get_encryption_service

        service1 = get_encryption_service()
        service2 = get_encryption_service()

        assert service1 is service2

    def test_encrypt_special_characters(self):
        """测试加密特殊字符."""
        from backend.services.encryption_service import EncryptionService

        service = EncryptionService()

        original = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)

        assert decrypted == original

    def test_encrypt_json_like_string(self):
        """测试加密 JSON 格式字符串."""
        from backend.services.encryption_service import EncryptionService

        service = EncryptionService()

        original = '{"key": "value", "array": [1, 2, 3]}'
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)

        assert decrypted == original


class TestEncryptionServiceEdgeCases:
    """EncryptionService 边界情况测试."""

    def test_encrypt_with_generated_key(self):
        """测试使用自动生成的密钥."""
        from backend.services.encryption_service import EncryptionService

        with patch("backend.services.encryption_service.settings") as mock_settings:
            mock_settings.ENCRYPTION_KEY = None

            service = EncryptionService()
            data = "测试数据"
            encrypted = service.encrypt(data)
            decrypted = service.decrypt(encrypted)

            assert decrypted == data

    def test_multiple_dicts_same_values(self):
        """测试加密多个相同值的字典产生不同密文."""
        from backend.services.encryption_service import EncryptionService

        service = EncryptionService()

        original = {"key": "value"}
        encrypted1 = service.encrypt_dict(original)
        encrypted2 = service.encrypt_dict(original)

        assert encrypted1 != encrypted2

        assert service.decrypt_dict(encrypted1) == original
        assert service.decrypt_dict(encrypted2) == original
