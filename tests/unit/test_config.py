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

        env_backup = os.environ.copy()
        try:
            for key in ["DB_PASSWORD", "DASHSCOPE_API_KEY", "DOCKER_ENV", "APP_DEBUG"]:
                os.environ.pop(key, None)

            os.environ["DB_PASSWORD"] = "test_password"

            settings = Settings()

            assert settings.DB_USER == "novel_user"
            assert settings.DB_NAME == "novel_system"
            assert settings.APP_HOST == "0.0.0.0"
            assert settings.APP_PORT == 8000

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_db_password_from_env(self):
        """测试从环境变量读取数据库密码."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ.pop("DB_PASSWORD", None)
            os.environ["DB_PASSWORD"] = "test_password"

            settings = Settings()
            assert settings.DB_PASSWORD == "test_password"

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_database_url_generation(self):
        """测试数据库 URL 动态生成."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"
            os.environ["DOCKER_ENV"] = "false"

            settings = Settings()

            # 本地环境
            assert settings.DB_HOST == "localhost"
            assert settings.DB_PORT == 5434
            assert "localhost:5434" in settings.DATABASE_URL
            assert "novel_user:test_pass" in settings.DATABASE_URL

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_docker_environment(self):
        """测试 Docker 环境配置."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"
            os.environ["DOCKER_ENV"] = "true"

            settings = Settings()

            # Docker 环境
            assert settings.DB_HOST == "postgres"
            assert settings.DB_PORT == 5432
            assert "postgres:5432" in settings.DATABASE_URL

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_redis_url(self):
        """测试 Redis URL 配置."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"
            os.environ["DOCKER_ENV"] = "false"

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
            os.environ["DB_PASSWORD"] = "test_pass"
            os.environ["DOCKER_ENV"] = "true"

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
            os.environ["DB_PASSWORD"] = "test_pass"

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
            os.environ["DB_PASSWORD"] = "test_pass"

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
            os.environ["DB_PASSWORD"] = "test_pass"

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
            os.environ["DB_PASSWORD"] = "test_pass"

            settings = Settings()

            # 验证爬虫配置
            assert settings.CRAWLER_REQUEST_DELAY == 1.5
            assert settings.CRAWLER_MAX_RETRIES == 3
            assert settings.CRAWLER_TIMEOUT == 30
            assert "Mozilla" in settings.CRAWLER_USER_AGENT

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_settings_character_detection_validation(self):
        """测试角色检测配置验证."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"

            # 测试有效值
            os.environ["CHARACTER_DETECTION_CONFIDENCE_THRESHOLD"] = "0.6"
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
            os.environ["DB_PASSWORD"] = "test_pass"

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
            os.environ["DB_PASSWORD"] = "test_pass"

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


class TestConfigValidation:
    """配置验证逻辑测试."""

    def test_quality_threshold_validation(self):
        """测试质量阈值范围验证 (1-10)."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"

            # 测试阈值 < 1
            os.environ["WORLD_QUALITY_THRESHOLD"] = "0.5"
            with pytest.raises(
                ValueError, match="WORLD_QUALITY_THRESHOLD must be between 1 and 10"
            ):
                Settings()

            # 测试阈值 > 10
            os.environ["WORLD_QUALITY_THRESHOLD"] = "11"
            with pytest.raises(
                ValueError, match="WORLD_QUALITY_THRESHOLD must be between 1 and 10"
            ):
                Settings()

            # 测试有效值
            os.environ["WORLD_QUALITY_THRESHOLD"] = "7.5"
            settings = Settings()
            assert settings.WORLD_QUALITY_THRESHOLD == 7.5

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_iteration_count_validation(self):
        """测试迭代次数验证 (>0)."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"

            # 测试迭代次数 < 1
            os.environ["MAX_WORLD_REVIEW_ITERATIONS"] = "0"
            with pytest.raises(ValueError, match="MAX_WORLD_REVIEW_ITERATIONS must be at least 1"):
                Settings()

            # 测试有效值
            os.environ["MAX_WORLD_REVIEW_ITERATIONS"] = "3"
            settings = Settings()
            assert settings.MAX_WORLD_REVIEW_ITERATIONS == 3

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_timeout_validation(self):
        """测试超时时间验证 (>0)."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"

            # 测试超时时间 <= 0
            os.environ["WORLD_REVIEW_TIMEOUT"] = "0"
            with pytest.raises(ValueError, match="WORLD_REVIEW_TIMEOUT must be at least 1"):
                Settings()

            # 测试有效值
            os.environ["WORLD_REVIEW_TIMEOUT"] = "120"
            settings = Settings()
            assert settings.WORLD_REVIEW_TIMEOUT == 120

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_retry_strategy_validation(self):
        """测试重试策略验证."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"

            # 测试 REVIEW_RETRY_BASE_DELAY <= 0
            os.environ["REVIEW_RETRY_BASE_DELAY"] = "0"
            with pytest.raises(ValueError, match="REVIEW_RETRY_BASE_DELAY must be positive"):
                Settings()

            # 测试 REVIEW_RETRY_MAX_DELAY <= 0
            os.environ["REVIEW_RETRY_BASE_DELAY"] = "1.0"
            os.environ["REVIEW_RETRY_MAX_DELAY"] = "0"
            with pytest.raises(ValueError, match="REVIEW_RETRY_MAX_DELAY must be positive"):
                Settings()

            # 测试 REVIEW_RETRY_MAX_DELAY < REVIEW_RETRY_BASE_DELAY
            os.environ["REVIEW_RETRY_BASE_DELAY"] = "5.0"
            os.environ["REVIEW_RETRY_MAX_DELAY"] = "2.0"
            with pytest.raises(
                ValueError, match="REVIEW_RETRY_MAX_DELAY must be >= REVIEW_RETRY_BASE_DELAY"
            ):
                Settings()

            # 测试有效值
            os.environ["REVIEW_RETRY_BASE_DELAY"] = "1.0"
            os.environ["REVIEW_RETRY_MAX_DELAY"] = "10.0"
            settings = Settings()
            assert settings.REVIEW_RETRY_BASE_DELAY == 1.0
            assert settings.REVIEW_RETRY_MAX_DELAY == 10.0

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_reflection_config_validation(self):
        """测试反思机制配置验证."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"

            # 测试 REFLECTION_ANALYSIS_INTERVAL < 1
            os.environ["REFLECTION_ANALYSIS_INTERVAL"] = "0"
            with pytest.raises(ValueError, match="REFLECTION_ANALYSIS_INTERVAL must be at least 1"):
                Settings()

            # 测试 REFLECTION_MIN_CHAPTERS < 1
            os.environ["REFLECTION_ANALYSIS_INTERVAL"] = "3"
            os.environ["REFLECTION_MIN_CHAPTERS"] = "0"
            with pytest.raises(ValueError, match="REFLECTION_MIN_CHAPTERS must be at least 1"):
                Settings()

            # 测试 REFLECTION_LESSON_BUDGET < 100
            os.environ["REFLECTION_MIN_CHAPTERS"] = "3"
            os.environ["REFLECTION_LESSON_BUDGET"] = "50"
            with pytest.raises(ValueError, match="REFLECTION_LESSON_BUDGET must be at least 100"):
                Settings()

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_crawler_config_validation(self):
        """测试爬虫配置验证."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"

            # 测试 CRAWLER_REQUEST_DELAY <= 0
            os.environ["CRAWLER_REQUEST_DELAY"] = "0"
            with pytest.raises(ValueError, match="CRAWLER_REQUEST_DELAY must be positive"):
                Settings()

            # 测试 CRAWLER_MAX_RETRIES < 0
            os.environ["CRAWLER_REQUEST_DELAY"] = "1.5"
            os.environ["CRAWLER_MAX_RETRIES"] = "-1"
            with pytest.raises(ValueError, match="CRAWLER_MAX_RETRIES must be non-negative"):
                Settings()

            # 测试 CRAWLER_TIMEOUT <= 0
            os.environ["CRAWLER_MAX_RETRIES"] = "3"
            os.environ["CRAWLER_TIMEOUT"] = "0"
            with pytest.raises(ValueError, match="CRAWLER_TIMEOUT must be positive"):
                Settings()

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_production_encryption_key_required(self):
        """测试生产环境必须配置加密密钥."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"
            os.environ["APP_ENV"] = "production"
            os.environ["DASHSCOPE_API_KEY"] = "test_key"

            # 未配置 ENCRYPTION_KEY
            os.environ.pop("ENCRYPTION_KEY", None)
            with pytest.raises(ValueError, match="生产环境必须配置 ENCRYPTION_KEY"):
                Settings()

            # 配置 ENCRYPTION_KEY
            os.environ["ENCRYPTION_KEY"] = "test_encryption_key_32chars"
            settings = Settings()
            assert settings.ENCRYPTION_KEY == "test_encryption_key_32chars"

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_config_dependency_chapter_review(self):
        """测试章节审查依赖关系验证."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"

            # ENABLE_CHAPTER_REVIEW=True 但阈值无效
            # 注意：阈值验证会先于依赖关系验证执行，所以错误消息是阈值相关的
            os.environ["ENABLE_CHAPTER_REVIEW"] = "true"
            os.environ["CHAPTER_QUALITY_THRESHOLD"] = "0"
            with pytest.raises(
                ValueError, match="CHAPTER_QUALITY_THRESHOLD must be between 1 and 10"
            ):
                Settings()

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_config_dependency_outline_update(self):
        """测试大纲更新依赖关系验证."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"

            # ENABLE_DYNAMIC_OUTLINE_UPDATE=True 但 INTERVAL 过大
            os.environ["ENABLE_DYNAMIC_OUTLINE_UPDATE"] = "true"
            os.environ["OUTLINE_UPDATE_INTERVAL"] = "15"
            with pytest.raises(
                ValueError,
                match="ENABLE_DYNAMIC_OUTLINE_UPDATE=True 时，OUTLINE_UPDATE_INTERVAL 建议不超过 10",
            ):
                Settings()

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_config_dependency_reflection(self):
        """测试反思机制依赖关系验证."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"

            # ENABLE_REFLECTION=True 但两个子开关都为 False
            os.environ["ENABLE_REFLECTION"] = "true"
            os.environ["ENABLE_REFLECTION_SHORT_TERM"] = "false"
            os.environ["ENABLE_REFLECTION_LONG_TERM"] = "false"
            with pytest.raises(ValueError, match="ENABLE_REFLECTION=True 时，至少需要启用"):
                Settings()

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_all_quality_thresholds_validation(self):
        """测试所有质量阈值验证."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"

            # 测试所有阈值
            for threshold_name in [
                "WORLD_QUALITY_THRESHOLD",
                "CHARACTER_QUALITY_THRESHOLD",
                "PLOT_QUALITY_THRESHOLD",
                "CHAPTER_QUALITY_THRESHOLD",
            ]:
                os.environ[threshold_name] = "0"
                with pytest.raises(ValueError, match=f"{threshold_name} must be between 1 and 10"):
                    Settings()
                os.environ[threshold_name] = "11"
                with pytest.raises(ValueError, match=f"{threshold_name} must be between 1 and 10"):
                    Settings()
                # 清理
                os.environ.pop(threshold_name, None)

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_all_iteration_counts_validation(self):
        """测试所有迭代次数验证."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"

            # 测试所有迭代次数
            for iter_name in [
                "MAX_WORLD_REVIEW_ITERATIONS",
                "MAX_CHARACTER_REVIEW_ITERATIONS",
                "MAX_PLOT_REVIEW_ITERATIONS",
                "MAX_CHAPTER_REVIEW_ITERATIONS",
                "MAX_FIX_ITERATIONS",
            ]:
                os.environ[iter_name] = "0"
                with pytest.raises(ValueError, match=f"{iter_name} must be at least 1"):
                    Settings()
                # 清理
                os.environ.pop(iter_name, None)

        finally:
            os.environ.clear()
            os.environ.update(env_backup)

    def test_all_timeouts_validation(self):
        """测试所有超时时间验证."""
        from backend.config import Settings

        env_backup = os.environ.copy()
        try:
            os.environ["DB_PASSWORD"] = "test_pass"

            # 测试所有超时时间
            for timeout_name in [
                "WORLD_REVIEW_TIMEOUT",
                "CHARACTER_REVIEW_TIMEOUT",
                "PLOT_REVIEW_TIMEOUT",
                "CHAPTER_REVIEW_TIMEOUT",
            ]:
                os.environ[timeout_name] = "0"
                with pytest.raises(ValueError, match=f"{timeout_name} must be at least 1"):
                    Settings()
                # 清理
                os.environ.pop(timeout_name, None)

        finally:
            os.environ.clear()
            os.environ.update(env_backup)
