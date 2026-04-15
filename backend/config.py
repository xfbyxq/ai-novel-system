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

    # 模型上下文窗口配置
    MODEL_CONTEXT_WINDOW: int = int(os.getenv("MODEL_CONTEXT_WINDOW", "196608"))
    MODEL_MAX_OUTPUT_TOKENS: int = int(os.getenv("MODEL_MAX_OUTPUT_TOKENS", "16384"))
    MODEL_MIN_OUTPUT_TOKENS: int = int(os.getenv("MODEL_MIN_OUTPUT_TOKENS", "1024"))

    # 上下文压缩器配置
    CONTEXT_COMPRESSOR_MAX_TOKENS: int = int(
        os.getenv("CONTEXT_COMPRESSOR_MAX_TOKENS", "40000")
    )  # 压缩阈值，使用模型窗口约20%（从12000提高到40000）

    # 热记忆完整内容配置（优化连贯性）
    HOT_MEMORY_CHAPTERS: int = int(
        os.getenv("HOT_MEMORY_CHAPTERS", "5")
    )  # 热记忆使用完整内容的章节数（从3增加到5）
    WARM_MEMORY_CHAPTERS: int = int(
        os.getenv("WARM_MEMORY_CHAPTERS", "10")
    )  # 温记忆保留关键事件的章节数（从7增加到10）
    PREVIOUS_ENDING_LENGTH: int = int(
        os.getenv("PREVIOUS_ENDING_LENGTH", "500")
    )  # 上一章结尾保留长度（确保章节衔接）
    HOT_MEMORY_ENABLE_FULL_CONTENT: bool = (
        os.getenv("HOT_MEMORY_ENABLE_FULL_CONTENT", "true").lower() == "true"
    )  # 是否启用完整内容热记忆

    # 图库连续性检查配置
    ENABLE_GRAPH_CONTINUITY_CHECK: bool = (
        os.getenv("ENABLE_GRAPH_CONTINUITY_CHECK", "true").lower() == "true"
    )  # 是否在连续性审查时启用图库冲突检测
    GRAPH_CONTINUITY_CHECK_TIMEOUT: int = int(
        os.getenv("GRAPH_CONTINUITY_CHECK_TIMEOUT", "5")
    )  # 图库冲突检测超时时间（秒）

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
        return 5436  # 本地开发映射端口（开发环境容器映射到5436）

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
        return "redis://localhost:6382/0"  # 本地开发映射端口（开发环境容器映射到6382）

    @property
    def CELERY_BROKER_URL(self) -> str:
        """自动检测Celery Broker URL."""
        docker_env = os.environ.get("DOCKER_ENV", "")
        if docker_env == "dev":
            return "redis://redis_dev:6379/1"
        elif docker_env in ("true", "1"):
            return "redis://redis:6379/1"
        return "redis://localhost:6382/1"  # 本地开发映射端口

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        """自动检测Celery Result Backend URL."""
        docker_env = os.environ.get("DOCKER_ENV", "")
        if docker_env == "dev":
            return "redis://redis_dev:6379/2"
        elif docker_env in ("true", "1"):
            return "redis://redis:6379/2"
        return "redis://localhost:6382/2"  # 本地开发映射端口

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
    # 注意：跨章节连贯性检查已合并到编辑的 cross_chapter_coherence 维度
    ENABLE_CHAPTER_REVIEW: bool = True
    # 投票共识：企划阶段关键决策由多 Agent 投票决定
    ENABLE_VOTING: bool = True
    # 设定查询：写作过程中 Writer 可查询世界观/角色/大纲设定
    ENABLE_QUERY: bool = True
    # 章节大纲细化：在 ChapterPlanner 之后、Writer 之前，将章节计划展开为详细大纲
    # 注意：现已改为按需调用，根据章节复杂度动态决定是否需要细化
    ENABLE_OUTLINE_REFINEMENT: bool = True
    # 独立连续性审查：已废弃，连续性检查已合并到编辑的 cross_chapter_coherence 维度
    # 保留此配置作为降级开关，设为 False 时使用新流程
    ENABLE_STANDALONE_CONTINUITY_CHECK: bool = False
    # 预防式连贯性检查：章节策划后检查潜在连贯性问题，在生成前预警
    ENABLE_CONTINUITY_CHECK: bool = True
    # 连贯性质量阈值：预防式检查的通过阈值
    CONTINUITY_QUALITY_THRESHOLD: float = 7.0

    # --- 详细评估报告配置 ---
    # 启用详细问题报告：输出包含位置定位、具体表现、优先级分类的问题列表
    ENABLE_DETAILED_ISSUE_REPORT: bool = True
    # 启用优先级分类修订：按优先级（影响阅读体验/提升精彩度/细节打磨）分组输出修订建议
    ENABLE_PRIORITY_REVISION: bool = True
    # 启用聚合维度评分：输出连贯性、合理性、趣味性三个聚合维度的星级评分
    ENABLE_AGGREGATE_RATINGS: bool = True

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
    MAX_TOOL_CALL_ITERATIONS: int = 10  # AI Chat 工具调用最大迭代次数

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

    # ============================================================
    # Neo4j 图数据库配置
    # ============================================================
    # 图数据库用于存储小说中的实体关系网络，支持：
    # - 多跳关系查询（如"A的师傅的徒弟"）
    # - 角色影响力分析
    # - 社区发现
    # - 一致性冲突检测
    # ============================================================

    # --- 功能开关 ---
    # 图数据库总开关，关闭时系统正常运行但缺少图分析能力
    ENABLE_GRAPH_DATABASE: bool = False
    # 实体自动抽取开关，章节生成后自动识别角色、地点、事件等
    ENABLE_ENTITY_EXTRACTION: bool = True
    # 章节生成后自动同步到图数据库
    ENABLE_GRAPH_SYNC_ON_CHAPTER: bool = True

    # --- Neo4j 连接配置 ---
    NEO4J_URI: str = ""  # bolt://localhost:7687
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str | None = None  # 必须通过环境变量设置
    NEO4J_DATABASE: str = "neo4j"  # 数据库名称
    NEO4J_MAX_CONNECTION_POOL_SIZE: int = 50
    NEO4J_CONNECTION_TIMEOUT: int = 30  # 秒

    @property
    def NEO4J_EFFECTIVE_URI(self) -> str:
        """自动检测Neo4j URI，根据Docker环境动态调整."""
        docker_env = os.environ.get("DOCKER_ENV", "")
        if docker_env == "dev":
            return "bolt://neo4j_dev:7687"
        elif docker_env in ("true", "1"):
            return "bolt://neo4j:7687"
        # 本地开发：使用映射端口
        return self.NEO4J_URI if self.NEO4J_URI else "bolt://localhost:7688"

    # --- 实体抽取配置 ---
    # 使用LLM从章节内容中抽取实体
    ENTITY_EXTRACTION_MODEL: str = "qwen-plus"
    ENTITY_EXTRACTION_CONFIDENCE_THRESHOLD: float = 0.7  # 置信度阈值 0-1
    ENTITY_EXTRACTION_MAX_CONTENT_LENGTH: int = 4000  # 传入LLM的内容最大字符数

    # --- 图查询缓存配置 ---
    GRAPH_QUERY_CACHE_TTL: int = 300  # 缓存过期时间（秒）
    GRAPH_QUERY_CACHE_MAX_SIZE: int = 100  # 最大缓存条目数

    # --- Agent图查询增强配置 ---
    # 启用后，Writer Agent 的 prompt 中会注入图数据库查询结果
    # 包括：角色关系网络、待回收伏笔、一致性冲突警告
    ENABLE_GRAPH_CONTEXT_INJECTION: bool = True  # 注入图上下文到 Writer prompt
    ENABLE_GRAPH_QUERY_FOR_WRITER: bool = True  # Writer支持动态图查询

    # 图查询参数配置
    GRAPH_QUERY_DEPTH: int = 2  # 角色网络查询深度（1-3，推荐2）
    GRAPH_CONTEXT_MAX_CHARACTERS: int = 5  # 最大查询角色数（避免prompt过长）
    GRAPH_CONTEXT_MAX_FORESHADOWINGS: int = 5  # 最大伏笔提醒数
    GRAPH_ENABLE_INDIRECT_RELATIONS: bool = True  # 是否查询间接关系
    GRAPH_QUERY_RELATED_FORESHADOWINGS: bool = True  # 查询与出场角色相关的伏笔

    # ============================================================
    # AI E2E 测试配置（LLM + MCP chrome-devtools 自动化测试）
    # ============================================================
    # 基于 a11y 快照 UID 定位元素，通过 MCP chrome-devtools 驱动浏览器。
    # LLM 仅在自愈（SnapshotResolver 失败时）和语义断言时使用。
    # ============================================================

    # --- AI E2E 测试开关 ---
    AI_E2E_ENABLED: bool = False  # 总开关，CI 中默认关闭
    AI_E2E_SELF_HEAL_ENABLED: bool = True  # 自愈功能开关
    AI_E2E_LLM_EVAL_ENABLED: bool = True  # LLM 语义断言开关

    # --- AI E2E 超时与重试 ---
    AI_E2E_CASE_TIMEOUT: int = 120  # 单个用例超时（秒）
    AI_E2E_STEP_TIMEOUT_MS: int = 10000  # 单步超时（毫秒）
    AI_E2E_RETRY_COUNT: int = 2  # 元素操作失败重试次数

    # --- AI E2E LLM 参数 ---
    AI_E2E_LLM_TEMPERATURE: float = 0.1  # 自愈和断言的 LLM 温度
    AI_E2E_LLM_MAX_TOKENS: int = 256  # 单次 LLM 调用最大 token
    AI_E2E_CONFIDENCE_THRESHOLD: float = 0.7  # LLM 断言置信度阈值

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
        self._validate_positive_int("MAX_TOOL_CALL_ITERATIONS", self.MAX_TOOL_CALL_ITERATIONS)

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

        # 验证 Neo4j 图数据库配置
        if self.ENABLE_GRAPH_DATABASE:
            # 生产环境必须配置 Neo4j 密码
            if self.APP_ENV == "production" and not self.NEO4J_PASSWORD:
                raise ValueError(
                    "生产环境启用图数据库时必须配置 NEO4J_PASSWORD！\n"
                    "请通过环境变量设置：export NEO4J_PASSWORD='your_password'"
                )
            # 验证连接池和超时配置
            self._validate_positive_int(
                "NEO4J_MAX_CONNECTION_POOL_SIZE", self.NEO4J_MAX_CONNECTION_POOL_SIZE
            )
            self._validate_positive_int("NEO4J_CONNECTION_TIMEOUT", self.NEO4J_CONNECTION_TIMEOUT)

        # 验证实体抽取配置
        if self.ENABLE_ENTITY_EXTRACTION:
            if not 0 <= self.ENTITY_EXTRACTION_CONFIDENCE_THRESHOLD <= 1:
                raise ValueError("ENTITY_EXTRACTION_CONFIDENCE_THRESHOLD 必须在 0-1 之间")
            if self.ENTITY_EXTRACTION_MAX_CONTENT_LENGTH < 500:
                raise ValueError("ENTITY_EXTRACTION_MAX_CONTENT_LENGTH 必须至少为 500")

        # 验证图查询缓存配置
        if self.GRAPH_QUERY_CACHE_TTL < 0:
            raise ValueError("GRAPH_QUERY_CACHE_TTL 必须为非负整数")
        if self.GRAPH_QUERY_CACHE_MAX_SIZE < 1:
            raise ValueError("GRAPH_QUERY_CACHE_MAX_SIZE 必须至少为 1")

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
