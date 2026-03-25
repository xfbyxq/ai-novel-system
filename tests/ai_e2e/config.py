"""
AI增强型E2E测试框架配置

管理框架运行时所需的各种配置参数
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")


@dataclass
class PlaywrightConfig:
    """Playwright运行配置"""
    headless: bool = True
    slow_mo: int = 500
    viewport_width: int = 1920
    viewport_height: int = 1080
    locale: str = "zh-CN"
    timezone: str = "Asia/Shanghai"
    timeout: int = 30000
    navigation_timeout: int = 30000


@dataclass
class HealeniumConfig:
    """Healenium自愈配置"""
    enabled: bool = True
    endpoint: str = "http://localhost:8088"
    self_healing_enabled: bool = True
    score_threshold: float = 0.7
    healing_timeout: int = 15000


@dataclass
class AIConfig:
    """AI大模型配置"""
    provider: str = "dashscope"  # dashscope, openai
    api_key: str = ""
    model: str = "qwen3.5-plus"
    temperature: float = 0.7
    max_tokens: int = 4000
    base_url: Optional[str] = None

    def __post_init__(self):
        """加载环境变量"""
        if not self.api_key:
            self.api_key = os.getenv("DASHSCOPE_API_KEY", "")
        if not self.base_url:
            self.base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")


@dataclass
class TestConfig:
    """测试框架主配置"""
    base_url: str = "http://localhost:3000"
    playwright: PlaywrightConfig = field(default_factory=PlaywrightConfig)
    healenium: HealeniumConfig = field(default_factory=HealeniumConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    report_dir: Path = Path("./ai_test_reports")
    selector_db_path: Path = Path("./.ai_test_selectors.db")

    @classmethod
    def from_env(cls) -> "TestConfig":
        """从环境变量加载配置"""
        return cls(
            base_url=os.getenv("TEST_BASE_URL", "http://localhost:3000"),
            playwright=PlaywrightConfig(
                headless=os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true",
                slow_mo=int(os.getenv("PLAYWRIGHT_SLOW_MO", "500")),
            ),
            healenium=HealeniumConfig(
                enabled=os.getenv("HEALENIUM_ENABLED", "true").lower() == "true",
                endpoint=os.getenv("HEALENIUM_ENDPOINT", "http://localhost:8088"),
            ),
            ai=AIConfig(
                api_key=os.getenv("DASHSCOPE_API_KEY", ""),
                model=os.getenv("DASHSCOPE_MODEL", "qwen3.5-plus"),
            ),
            report_dir=Path(os.getenv("TEST_REPORT_DIR", "./ai_test_reports")),
            selector_db_path=Path(os.getenv("SELECTOR_DB_PATH", "./.ai_test_selectors.db")),
        )


# 默认配置实例
default_config = TestConfig.from_env()