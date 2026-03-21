"""
配置模块单元测试

测试 backend.config 模块的配置验证逻辑
"""

import os
import pytest
from pydantic import ValidationError


class TestSettings:
    """Settings 配置测试类."""

    def test_settings_default_values(self):
        """测试配置的默认值."""
        from backend.config import Settings

        # 清除环境变量以避免干扰
        env_backup = os.environ.copy()
        try:
            # 清除敏感环境变量
            for key in ['DB_PASSWORD', 'DASHSCOPE_API_KEY', 'DOCKER_ENV']:
                os.environ.pop(key, None)

            # 设置必要的测试环境变量
            os.environ['DB_PASSWORD'] = 'test_password'

            settings = Settings()

            # 验证默认值
            assert settings.DB_USER == "novel_user"
            assert settings.DB_NAME == "novel_system"
            assert settings.APP_ENV == "development"
            assert settings.APP_DEBUG is True
            assert settings.APP_HOST == "0.0.0.0"
            assert settings.APP_PORT == 8000

        finally:
            # 恢复环境变量
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_db_password_required(self):
        """测试数据库密码为必填项."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            # 清除 DB_PASSWORD
            os.environ.pop('DB_PASSWORD', None)

            # 应该抛出 ValidationError
            with pytest.raises(ValidationError) as exc_info:
                Settings()

            assert 'DB_PASSWORD' in str(exc_info.value)

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_database_url_generation(self):
        """测试数据库 URL 动态生成."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ['DB_PASSWORD'] = 'test_pass'
            os.environ['DOCKER_ENV'] = 'false'

            settings = Settings()

            # 本地环境
            assert settings.DB_HOST == 'localhost'
            assert settings.DB_PORT == 5434
            assert 'localhost:5434' in settings.DATABASE_URL
            assert 'novel_user:test_pass' in settings.DATABASE_URL

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_docker_environment(self):
        """测试 Docker 环境配置."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ['DB_PASSWORD'] = 'test_pass'
            os.environ['DOCKER_ENV'] = 'true'

            settings = Settings()

            # Docker 环境
            assert settings.DB_HOST == 'postgres'
            assert settings.DB_PORT == 5432
            assert 'postgres:5432' in settings.DATABASE_URL

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_redis_url(self):
        """测试 Redis URL 配置."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ['DB_PASSWORD'] = 'test_pass'
            os.environ['DOCKER_ENV'] = 'false'

            settings = Settings()

            assert settings.REDIS_URL == "redis://localhost:6379/0"
            assert settings.CELERY_BROKER_URL == "redis://localhost:6379/1"
            assert settings.CELERY_RESULT_BACKEND == "redis://localhost:6379/2"

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_docker_redis_url(self):
        """测试 Docker 环境 Redis URL."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ['DB_PASSWORD'] = 'test_pass'
            os.environ['DOCKER_ENV'] = 'true'

            settings = Settings()

            assert settings.REDIS_URL == "redis://redis:6379/0"
            assert settings.CELERY_BROKER_URL == "redis://redis:6379/1"
            assert settings.CELERY_RESULT_BACKEND == "redis://redis:6379/2"

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_review_thresholds(self):
        """测试审查阈值配置."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ['DB_PASSWORD'] = 'test_pass'

            settings = Settings()

            # 验证默认阈值
            assert settings.WORLD_QUALITY_THRESHOLD == 8.0
            assert settings.CHARACTER_QUALITY_THRESHOLD == 8.0
            assert settings.PLOT_QUALITY_THRESHOLD == 8.0
            assert settings.CHAPTER_QUALITY_THRESHOLD == 8.0

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_review_iterations(self):
        """测试审查迭代次数配置."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ['DB_PASSWORD'] = 'test_pass'

            settings = Settings()

            # 验证默认迭代次数
            assert settings.MAX_WORLD_REVIEW_ITERATIONS == 5
            assert settings.MAX_CHARACTER_REVIEW_ITERATIONS == 5
            assert settings.MAX_PLOT_REVIEW_ITERATIONS == 5
            assert settings.MAX_CHAPTER_REVIEW_ITERATIONS == 5

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_feature_flags(self):
        """测试功能开关配置."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ['DB_PASSWORD'] = 'test_pass'

            settings = Settings()

            # 验证默认功能开关
            assert settings.ENABLE_WORLD_REVIEW is True
            assert settings.ENABLE_CHARACTER_REVIEW is True
            assert settings.ENABLE_PLOT_REVIEW is True
            assert settings.ENABLE_CHAPTER_REVIEW is True
            assert settings.ENABLE_VOTING is True
            assert settings.ENABLE_QUERY is True
            assert settings.ENABLE_OUTLINE_REFINEMENT is True

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_crawler_config(self):
        """测试爬虫配置."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ['DB_PASSWORD'] = 'test_pass'

            settings = Settings()

            # 验证爬虫配置
            assert settings.CRAWLER_REQUEST_DELAY == 1.5
            assert settings.CRAWLER_MAX_RETRIES == 3
            assert settings.CRAWLER_TIMEOUT == 30
            assert 'Mozilla' in settings.CRAWLER_USER_AGENT

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_character_detection_validation(self):
        """测试角色检测配置验证."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ['DB_PASSWORD'] = 'test_pass'

            # 测试有效值
            os.environ['CHARACTER_DETECTION_CONFIDENCE_THRESHOLD'] = '0.6'
            settings = Settings()
            assert settings.CHARACTER_DETECTION_CONFIDENCE_THRESHOLD == 0.6

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_outline_update_config(self):
        """测试大纲更新配置."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ['DB_PASSWORD'] = 'test_pass'

            settings = Settings()

            assert settings.ENABLE_DYNAMIC_OUTLINE_UPDATE is True
            assert settings.OUTLINE_UPDATE_INTERVAL == 3
            assert settings.OUTLINE_DEVIATION_THRESHOLD == 6.0

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_reflection_config(self):
        """测试反思机制配置."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ['DB_PASSWORD'] = 'test_pass'

            settings = Settings()

            assert settings.ENABLE_REFLECTION is True
            assert settings.ENABLE_REFLECTION_SHORT_TERM is True
            assert settings.ENABLE_REFLECTION_LONG_TERM is True
            assert settings.REFLECTION_ANALYSIS_INTERVAL == 3

        finally:
            os.environ.clear()
            os.environ.update(env_backup)


class TestGetSettings:
    """get_settings 函数测试."""

    def test_get_settings_singleton(self):
        """测试 get_settings 返回单例."""
        from backend.config import get_settings

        settings1 = get_settings()
        settings2 = get_settings()

        # 由于使用了 lru_cache，应该返回相同的实例
        assert settings1 is settings2
