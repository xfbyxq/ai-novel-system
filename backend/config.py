import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_MODEL: str = "qwen-plus"
    DASHSCOPE_BASE_URL: str = ""  # Coding Plan Pro 的 base URL

    # Database
    DB_USER: str = "novel_user"
    DB_PASSWORD: str = "novel_pass"
    DB_NAME: str = "novel_system"

    @property
    def DB_HOST(self) -> str:
        """自动检测是否在Docker环境中"""
        if os.environ.get('DOCKER_ENV') == 'true':
            return 'postgres'  # Docker服务名
        return 'localhost'     # 本地开发

    @property
    def DB_PORT(self) -> int:
        """自动检测是否在Docker环境中"""
        if os.environ.get('DOCKER_ENV') == 'true':
            return 5432        # Docker内部端口
        return 5434            # 本地开发映射端口

    @property
    def DATABASE_URL(self) -> str:
        """动态构建数据库连接URL"""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """动态构建同步数据库连接URL"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Redis
    @property
    def REDIS_URL(self) -> str:
        """自动检测Redis URL"""
        if os.environ.get('DOCKER_ENV') == 'true':
            return "redis://redis:6379/0"
        return "redis://localhost:6379/0"

    @property
    def CELERY_BROKER_URL(self) -> str:
        """自动检测Celery Broker URL"""
        if os.environ.get('DOCKER_ENV') == 'true':
            return "redis://redis:6379/1"
        return "redis://localhost:6379/1"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        """自动检测Celery Result Backend URL"""
        if os.environ.get('DOCKER_ENV') == 'true':
            return "redis://redis:6379/2"
        return "redis://localhost:6379/2"

    # Application
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # Encryption (用于加密平台账号凭证)
    ENCRYPTION_KEY: str = ""

    # Crawler Settings (爬虫配置)
    CRAWLER_REQUEST_DELAY: float = 1.5  # 请求间隔(秒)
    CRAWLER_MAX_RETRIES: int = 3
    CRAWLER_TIMEOUT: int = 30
    CRAWLER_USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

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
    WORLD_QUALITY_THRESHOLD: float = 8.0      # 世界观质量阈值
    CHARACTER_QUALITY_THRESHOLD: float = 8.0  # 角色质量阈值
    PLOT_QUALITY_THRESHOLD: float = 8.0       # 大纲质量阈值
    CHAPTER_QUALITY_THRESHOLD: float = 8.0    # 章节质量阈值

    # --- 最大迭代次数 ---
    # 即使未达阈值，超过最大次数也会停止，防止无限循环
    # 每次迭代会消耗 API 调用，企划阶段建议 3-5 次，写作阶段建议 3-5 次
    MAX_WORLD_REVIEW_ITERATIONS: int = 5      # 世界观审查最大迭代（从3增加到5）
    MAX_CHARACTER_REVIEW_ITERATIONS: int = 5  # 角色审查最大迭代（从3增加到5）
    MAX_PLOT_REVIEW_ITERATIONS: int = 5       # 大纲审查最大迭代（从3增加到5）
    MAX_CHAPTER_REVIEW_ITERATIONS: int = 5    # 章节审查最大迭代（从3增加到5）
    MAX_FIX_ITERATIONS: int = 3               # 连续性修复最大迭代（从2增加到3）

    # --- 角色自动检测 ---
    # 每章生成后自动检测内容中的新角色并注册到角色库
    ENABLE_CHARACTER_AUTO_DETECTION: bool = True
    CHARACTER_DETECTION_CONFIDENCE_THRESHOLD: float = 0.6  # 置信度阈值，低于此值的角色不注册
    CHARACTER_DETECTION_MAX_CONTENT_LENGTH: int = 6000      # 传入 LLM 的内容最大字符数

    # --- 大纲动态更新 ---
    # 每 N 章自动评估大纲偏差并更新未来章节的大纲
    ENABLE_DYNAMIC_OUTLINE_UPDATE: bool = True
    OUTLINE_UPDATE_INTERVAL: int = 3            # 每 N 章触发一次偏差评估
    OUTLINE_DEVIATION_THRESHOLD: float = 6.0    # 偏差综合分超过此阈值才执行更新 (0-10)

    # --- 反思机制 (Reflection) ---
    # 从审查循环历史中提取经验教训，注入到后续写作/审查 prompt 中
    # 短期反思：纯 Python 统计，零 LLM 开销
    # 长期反思：每 N 章调用 1 次 LLM 做跨章节模式分析
    ENABLE_REFLECTION: bool = True               # 反思机制总开关
    ENABLE_REFLECTION_SHORT_TERM: bool = True    # 短期反思开关（每次审查循环后的统计分析）
    ENABLE_REFLECTION_LONG_TERM: bool = True     # 长期反思开关（跨章节模式分析，需调用 LLM）
    REFLECTION_ANALYSIS_INTERVAL: int = 3        # 长期反思触发间隔（每 N 章分析一次）
    REFLECTION_MIN_CHAPTERS: int = 3             # 启动长期反思所需的最少章节数
    REFLECTION_LESSON_BUDGET: int = 600          # 注入 prompt 时的字符预算上限

    def __init__(self, **values):
        super().__init__(**values)
        # 验证配置值的合理性
        if self.CHARACTER_DETECTION_CONFIDENCE_THRESHOLD < 0 or self.CHARACTER_DETECTION_CONFIDENCE_THRESHOLD > 1:
            raise ValueError("CHARACTER_DETECTION_CONFIDENCE_THRESHOLD must be between 0 and 1")
        if self.OUTLINE_DEVIATION_THRESHOLD < 0 or self.OUTLINE_DEVIATION_THRESHOLD > 10:
            raise ValueError("OUTLINE_DEVIATION_THRESHOLD must be between 0 and 10")
        if self.OUTLINE_UPDATE_INTERVAL < 1:
            raise ValueError("OUTLINE_UPDATE_INTERVAL must be at least 1")
        if self.CHARACTER_DETECTION_MAX_CONTENT_LENGTH < 100:
            raise ValueError("CHARACTER_DETECTION_MAX_CONTENT_LENGTH must be at least 100")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
