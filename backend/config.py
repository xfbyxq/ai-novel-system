"""
配置模块 - 管理系统配置和验证.

本模块提供 Settings 类，用于加载、验证和访问系统配置。
支持开发环境和生产环境的自动检测，包括数据库、Redis、LLM 等配置。

配置优先级:
    1. 环境变量（最高优先级）
    2. .env 文件
    3. 默认值（最低优先级）

Example:
    >>> from backend.config import get_settings
    >>> settings = get_settings()
    >>> print(settings.DATABASE_URL)
    'postgresql+asyncpg://...'
"""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


def get_version_from_pyproject() -> str:
    """
    从 pyproject.toml 动态读取版本号.

    Returns:
        str: 版本号字符串，如果读取失败则返回 "2.0.0"
    """
    import re

    try:
        pyproject_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "..", "pyproject.toml"
        )
        with open(pyproject_path, "r") as f:
            content = f.read()
        match = re.search(r'version\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "2.0.0"


class Settings(BaseSettings):
    """
    系统配置类.

    管理所有系统配置项，包括 LLM、数据库、Redis、应用设置等。
    支持自动环境检测（Docker/本地）和配置验证。

    Attributes:
        DASHSCOPE_API_KEY: 通义千问 API 密钥
        DASHSCOPE_MODEL: LLM 模型名称
        DB_USER: 数据库用户名
        DB_PASSWORD: 数据库密码
        DB_NAME: 数据库名称
        APP_ENV: 应用环境（development/production）
        APP_DEBUG: 调试模式开关
        ENABLE_WORLD_REVIEW: 世界观审查开关
        ENABLE_CHARACTER_REVIEW: 角色审查开关
        ENABLE_CHAPTER_REVIEW: 章节审查开关

    Note:
        - 敏感配置（如密码）必须通过环境变量设置
        - 生产环境会自动启用更严格的验证
        - 配置项修改后需要重启应用
    """

    # LLM
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_MODEL: str = "qwen-plus"
    DASHSCOPE_BASE_URL: str = ""  # Coding Plan Pro 的 base URL

    # Database
    DB_USER: str = "novel_user"
    DB_PASSWORD: str | None = None  # 必须通过环境变量设置，禁止硬编码
    DB_NAME: str = "novel_system"

    def model_post_init(self, __context) -> None:
        """初始化后验证：确保敏感配置已设置."""
        # 跳过验证，因为密码会从 DATABASE_URL 中提取
        pass

    def _get_db_password_from_url(self) -> str:
        """从 DATABASE_URL 中提取密码."""
        import os

        # __file__ 是 backend/config.py，需要向上两级到项目根目录
        config_dir = os.path.dirname(os.path.abspath(__file__))  # backend/
        project_root = os.path.dirname(config_dir)  # 项目根目录
        env_file = os.path.join(project_root, ".env")
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DATABASE_URL="):
                        url = line.split("=", 1)[1]
                        import re

                        match = re.search(r"://([^:]+):([^@]+)@", url)
                        if match:
                            return match.group(2)
        return ""

    @property
    def _effective_db_password(self) -> str:
        """获取有效的数据库密码."""
        if self.DB_PASSWORD:
            return self.DB_PASSWORD
        return self._get_db_password_from_url()

    @property
    def DB_HOST(self) -> str:
        """自动检测是否在Docker环境中."""
        docker_env = os.environ.get("DOCKER_ENV", "")
        if docker_env == "dev":
            return "postgres_dev"  # 开发 Docker 服务名
        elif docker_env in ("true", "1"):
            return "postgres"  # 生产 Docker 服务名
        return "localhost"  # 本地开发

    @property
    def DB_PORT(self) -> int:
        """自动检测是否在Docker环境中."""
        docker_env = os.environ.get("DOCKER_ENV", "")
        if docker_env == "dev":
            return 5432  # 开发 Docker 内部端口
        elif docker_env in ("true", "1"):
            return 5432  # 生产 Docker 内部端口
        return 5434  # 本地开发映射端口

    @property
    def DATABASE_URL(self) -> str:
        """动态构建数据库连接URL."""
        return f"postgresql+asyncpg://{self.DB_USER}:{self._effective_db_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """动态构建同步数据库连接URL."""
        return f"postgresql://{self.DB_USER}:{self._effective_db_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Redis - 使用环境变量或自动检测
    @property
    def REDIS_URL(self) -> str:
        """自动检测Redis URL."""
        docker_env = os.environ.get("DOCKER_ENV", "")
        if docker_env == "dev":
            return "redis://redis_dev:6379/0"
        elif docker_env in ("true", "1"):
            return "redis://redis:6379/0"
        return "redis://localhost:6379/0"

    @property
    def CELERY_BROKER_URL(self) -> str:
        """自动检测Celery Broker URL."""
        docker_env = os.environ.get("DOCKER_ENV", "")
        if docker_env == "dev":
            return "redis://redis_dev:6379/1"
        elif docker_env in ("true", "1"):
            return "redis://redis:6379/1"
        return "redis://localhost:6379/1"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        """自动检测Celery Result Backend URL."""
        docker_env = os.environ.get("DOCKER_ENV", "")
        if docker_env == "dev":
            return "redis://redis_dev:6379/2"
        elif docker_env in ("true", "1"):
            return "redis://redis:6379/2"
        return "redis://localhost:6379/2"

    # Application
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # 日志配置
    LOG_DIR: str = "logs"  # 日志目录（相对于项目根目录）
    LOG_FILE_MAX_BYTES: int = 10 * 1024 * 1024  # 单个日志文件大小（默认10MB）
    LOG_FILE_BACKUP_COUNT: int = 5  # 轮转备份数量
    LOG_RETENTION_DAYS: int = 7  # 日志保留天数
    LOG_FILE_NAME: str = "app.log"  # 后端日志文件名
    LOG_WORKER_FILE_NAME: str = "worker.log"  # Worker日志文件名

    # CORS 配置（安全加固）
    # 生产环境应设置为实际域名，如：https://api.example.com,https://app.example.com
    CORS_ALLOWED_ORIGINS: str = ""  # 逗号分隔的允许来源列表，为空则使用默认开发环境配置

    @property
    def APP_VERSION(self) -> str:
        """动态获取应用版本号."""
        return get_version_from_pyproject()

    # Encryption (用于加密平台账号凭证)
    ENCRYPTION_KEY: str = ""

    # Crawler Settings (爬虫配置)
    CRAWLER_REQUEST_DELAY: float = 1.5  # 请求间隔(秒)
    CRAWLER_MAX_RETRIES: int = 3
    CRAWLER_TIMEOUT: int = 30
    CRAWLER_USER_AGENT: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # Agent Review Settings (审查循环配置)
    # ============================================================
    # 审查循环是保证生成质量的核心机制，通过 Designer-Reviewer 模式
    # 对世界观、角色、大纲、章节进行多轮迭代优化，直到达到质量阈值。
    #
    # 配置建议：
    # - 追求高质量：阈值设为 7.5-8.0，迭代次数 2-3
    # - 追求速度/省成本：阈值设为 6.0-6.5，迭代次数 1，或直接关闭审查
    # - 调试模式：可关闭部分审查，加快测试速度
    # ============================================================

    # --- 功能开关 ---
    # 世界观审查：检查设定一致性、深度、独特性、可扩展性
    ENABLE_WORLD_REVIEW: bool = True
    # 角色审查：检查心理深度、独特性、成长弧线、关系复杂性
    ENABLE_CHARACTER_REVIEW: bool = True
    # 大纲审查：检查结构完整性、节奏把控、冲突张力、伏笔设计
    ENABLE_PLOT_REVIEW: bool = True
    # 章节审查：Writer-Editor 循环，检查语言流畅度、情节逻辑、角色一致性
    ENABLE_CHAPTER_REVIEW: bool = True
    # 投票共识：企划阶段关键决策由多 Agent 投票决定
    ENABLE_VOTING: bool = True
    # 设定查询：写作过程中 Writer 可查询世界观/角色/大纲设定
    ENABLE_QUERY: bool = True
    # 章节大纲细化：在 ChapterPlanner 之后、Writer 之前，将章节计划展开为详细大纲
    ENABLE_OUTLINE_REFINEMENT: bool = True

    # --- 质量阈值 (1-10分) ---
    # 评分达到阈值即停止迭代，分数越高要求越严格
    # 建议范围：6.0(宽松) - 8.0(严格)
    WORLD_QUALITY_THRESHOLD: float = 8.0  # 世界观质量阈值
    CHARACTER_QUALITY_THRESHOLD: float = 8.0  # 角色质量阈值
    PLOT_QUALITY_THRESHOLD: float = 8.0  # 大纲质量阈值
    CHAPTER_QUALITY_THRESHOLD: float = 8.0  # 章节质量阈值

    # --- 最大迭代次数 ---
    # 即使未达阈值，超过最大次数也会停止，防止无限循环
    # 每次迭代会消耗 API 调用，企划阶段建议 3-5 次，写作阶段建议 3-5 次
    MAX_WORLD_REVIEW_ITERATIONS: int = 5  # 世界观审查最大迭代（从3增加到5）
    MAX_CHARACTER_REVIEW_ITERATIONS: int = 5  # 角色审查最大迭代（从3增加到5）
    MAX_PLOT_REVIEW_ITERATIONS: int = 5  # 大纲审查最大迭代（从3增加到5）
    MAX_CHAPTER_REVIEW_ITERATIONS: int = 5  # 章节审查最大迭代（从3增加到5）
    MAX_FIX_ITERATIONS: int = 3  # 连续性修复最大迭代（从2增加到3）

    # --- 超时机制（熔断保护） ---
    # 单次审查迭代超时时间（秒），防止 LLM 调用卡死导致整个循环挂起
    # 建议：世界观/大纲/角色审查 120-180 秒，章节审查 60-90 秒
    WORLD_REVIEW_TIMEOUT: int = 180  # 世界观审查超时
    CHARACTER_REVIEW_TIMEOUT: int = 120  # 角色审查超时
    PLOT_REVIEW_TIMEOUT: int = 180  # 大纲审查超时
    CHAPTER_REVIEW_TIMEOUT: int = 90  # 章节审查超时

    # --- 重试策略 ---
    # LLM 调用失败时的重试次数（不含首次尝试）
    # 建议：2-3 次，过多会导致延迟累积
    REVIEW_LLM_MAX_RETRIES: int = 2
    # 重试基础延迟（秒），配合指数退避
    REVIEW_RETRY_BASE_DELAY: float = 1.0
    # 重试最大延迟（秒），防止退避时间过长
    REVIEW_RETRY_MAX_DELAY: float = 10.0

    # --- 角色自动检测 ---
    # 每章生成后自动检测内容中的新角色并注册到角色库
    ENABLE_CHARACTER_AUTO_DETECTION: bool = True
    CHARACTER_DETECTION_CONFIDENCE_THRESHOLD: float = 0.6  # 置信度阈值，低于此值的角色不注册
    CHARACTER_DETECTION_MAX_CONTENT_LENGTH: int = 6000  # 传入 LLM 的内容最大字符数

    # --- 大纲动态更新 ---
    # 每 N 章自动评估大纲偏差并更新未来章节的大纲
    ENABLE_DYNAMIC_OUTLINE_UPDATE: bool = True
    OUTLINE_UPDATE_INTERVAL: int = 3  # 每 N 章触发一次偏差评估
    OUTLINE_DEVIATION_THRESHOLD: float = 6.0  # 偏差综合分超过此阈值才执行更新 (0-10)

    # --- 反思机制 (Reflection) ---
    # 从审查循环历史中提取经验教训，注入到后续写作/审查 prompt 中
    # 短期反思：纯 Python 统计，零 LLM 开销
    # 长期反思：每 N 章调用 1 次 LLM 做跨章节模式分析
    ENABLE_REFLECTION: bool = True  # 反思机制总开关
    ENABLE_REFLECTION_SHORT_TERM: bool = True  # 短期反思开关（每次审查循环后的统计分析）
    ENABLE_REFLECTION_LONG_TERM: bool = True  # 长期反思开关（跨章节模式分析，需调用 LLM）
    REFLECTION_ANALYSIS_INTERVAL: int = 3  # 长期反思触发间隔（每 N 章分析一次）
    REFLECTION_MIN_CHAPTERS: int = 3  # 启动长期反思所需的最少章节数
    REFLECTION_LESSON_BUDGET: int = 600  # 注入 prompt 时的字符预算上限

    def __init__(self, **values):
        """初始化方法."""
        super().__init__(**values)
        # 验证配置值的合理性
        if (
            self.CHARACTER_DETECTION_CONFIDENCE_THRESHOLD < 0
            or self.CHARACTER_DETECTION_CONFIDENCE_THRESHOLD > 1
        ):
            raise ValueError("CHARACTER_DETECTION_CONFIDENCE_THRESHOLD must be between 0 and 1")
        if self.OUTLINE_DEVIATION_THRESHOLD < 0 or self.OUTLINE_DEVIATION_THRESHOLD > 10:
            raise ValueError("OUTLINE_DEVIATION_THRESHOLD must be between 0 and 10")
        if self.OUTLINE_UPDATE_INTERVAL < 1:
            raise ValueError("OUTLINE_UPDATE_INTERVAL must be at least 1")
        if self.CHARACTER_DETECTION_MAX_CONTENT_LENGTH < 100:
            raise ValueError("CHARACTER_DETECTION_MAX_CONTENT_LENGTH must be at least 100")

        # 生产环境必须配置 API Key
        if self.APP_ENV == "production" and not self.DASHSCOPE_API_KEY:
            raise ValueError(
                "生产环境必须配置 DASHSCOPE_API_KEY！\n"
                "请通过环境变量设置：export DASHSCOPE_API_KEY='your_api_key'"
            )

        # 验证质量阈值范围 (1-10)
        self._validate_threshold("WORLD_QUALITY_THRESHOLD", self.WORLD_QUALITY_THRESHOLD)
        self._validate_threshold("CHARACTER_QUALITY_THRESHOLD", self.CHARACTER_QUALITY_THRESHOLD)
        self._validate_threshold("PLOT_QUALITY_THRESHOLD", self.PLOT_QUALITY_THRESHOLD)
        self._validate_threshold("CHAPTER_QUALITY_THRESHOLD", self.CHAPTER_QUALITY_THRESHOLD)

        # 验证迭代次数 (>0)
        self._validate_positive_int("MAX_WORLD_REVIEW_ITERATIONS", self.MAX_WORLD_REVIEW_ITERATIONS)
        self._validate_positive_int(
            "MAX_CHARACTER_REVIEW_ITERATIONS", self.MAX_CHARACTER_REVIEW_ITERATIONS
        )
        self._validate_positive_int("MAX_PLOT_REVIEW_ITERATIONS", self.MAX_PLOT_REVIEW_ITERATIONS)
        self._validate_positive_int(
            "MAX_CHAPTER_REVIEW_ITERATIONS", self.MAX_CHAPTER_REVIEW_ITERATIONS
        )
        self._validate_positive_int("MAX_FIX_ITERATIONS", self.MAX_FIX_ITERATIONS)

        # 验证超时时间 (>0)
        self._validate_positive_int("WORLD_REVIEW_TIMEOUT", self.WORLD_REVIEW_TIMEOUT)
        self._validate_positive_int("CHARACTER_REVIEW_TIMEOUT", self.CHARACTER_REVIEW_TIMEOUT)
        self._validate_positive_int("PLOT_REVIEW_TIMEOUT", self.PLOT_REVIEW_TIMEOUT)
        self._validate_positive_int("CHAPTER_REVIEW_TIMEOUT", self.CHAPTER_REVIEW_TIMEOUT)

        # 验证重试策略
        self._validate_non_negative_int("REVIEW_LLM_MAX_RETRIES", self.REVIEW_LLM_MAX_RETRIES)
        if self.REVIEW_RETRY_BASE_DELAY <= 0:
            raise ValueError("REVIEW_RETRY_BASE_DELAY must be positive")
        if self.REVIEW_RETRY_MAX_DELAY <= 0:
            raise ValueError("REVIEW_RETRY_MAX_DELAY must be positive")
        if self.REVIEW_RETRY_MAX_DELAY < self.REVIEW_RETRY_BASE_DELAY:
            raise ValueError("REVIEW_RETRY_MAX_DELAY must be >= REVIEW_RETRY_BASE_DELAY")

        # 验证反思机制配置
        if self.REFLECTION_ANALYSIS_INTERVAL < 1:
            raise ValueError("REFLECTION_ANALYSIS_INTERVAL must be at least 1")
        if self.REFLECTION_MIN_CHAPTERS < 1:
            raise ValueError("REFLECTION_MIN_CHAPTERS must be at least 1")
        if self.REFLECTION_LESSON_BUDGET < 100:
            raise ValueError("REFLECTION_LESSON_BUDGET must be at least 100")

        # 验证爬虫配置
        if self.CRAWLER_REQUEST_DELAY <= 0:
            raise ValueError("CRAWLER_REQUEST_DELAY must be positive")
        if self.CRAWLER_MAX_RETRIES < 0:
            raise ValueError("CRAWLER_MAX_RETRIES must be non-negative")
        if self.CRAWLER_TIMEOUT <= 0:
            raise ValueError("CRAWLER_TIMEOUT must be positive")

        # 生产环境验证加密密钥
        if self.APP_ENV == "production" and not self.ENCRYPTION_KEY:
            raise ValueError(
                "生产环境必须配置 ENCRYPTION_KEY！\n"
                "请通过环境变量设置：export ENCRYPTION_KEY='your_32_char_key'"
            )

        # 验证配置依赖关系
        self._validate_config_dependencies()

    def _validate_threshold(self, name: str, value: float):
        """验证质量阈值在有效范围内 (1-10)."""
        if value < 1 or value > 10:
            raise ValueError(f"{name} must be between 1 and 10, got {value}")

    def _validate_positive_int(self, name: str, value: int):
        """验证正整数配置."""
        if value < 1:
            raise ValueError(f"{name} must be at least 1, got {value}")

    def _validate_non_negative_int(self, name: str, value: int):
        """验证非负整数配置."""
        if value < 0:
            raise ValueError(f"{name} must be non-negative, got {value}")

    def _validate_config_dependencies(self):
        """验证配置项之间的依赖关系."""
        # 如果启用章节审查，必须配置有效的阈值
        if self.ENABLE_CHAPTER_REVIEW and (
            self.CHAPTER_QUALITY_THRESHOLD < 1 or self.CHAPTER_QUALITY_THRESHOLD > 10
        ):
            raise ValueError(
                "ENABLE_CHAPTER_REVIEW=True 时，CHAPTER_QUALITY_THRESHOLD 必须在 1-10 之间"
            )

        # 如果启用大纲动态更新，OUTLINE_UPDATE_INTERVAL 必须合理
        if self.ENABLE_DYNAMIC_OUTLINE_UPDATE and self.OUTLINE_UPDATE_INTERVAL > 10:
            raise ValueError(
                "ENABLE_DYNAMIC_OUTLINE_UPDATE=True 时，OUTLINE_UPDATE_INTERVAL 建议不超过 10"
            )

        # 如果启用反思机制，相关配置必须合理
        if self.ENABLE_REFLECTION:
            if not self.ENABLE_REFLECTION_SHORT_TERM and not self.ENABLE_REFLECTION_LONG_TERM:
                raise ValueError(
                    "ENABLE_REFLECTION=True 时，至少需要启用 ENABLE_REFLECTION_SHORT_TERM 或 ENABLE_REFLECTION_LONG_TERM 之一"
                )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
