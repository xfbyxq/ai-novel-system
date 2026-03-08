"""审查循环基础模块

提供审查循环的共享基础设施：
- JsonExtractor: JSON 提取工具
- BaseQualityReport: 质量报告基类及子类
- BaseReviewResult: 审查结果基类及子类
- BaseReviewLoopHandler: 审查循环处理器基类
- ReviewLoopConfig: 审查循环配置
- QualityLevel: 质量级别枚举
- IssueRecord / IssueTracker: 跨轮次问题追踪
- ReviewProgressSummary: 审查进度摘要
"""

from agents.base.json_extractor import JsonExtractor, extract_json
from agents.base.quality_report import (
    BaseQualityReport,
    ChapterQualityReport,
    CharacterQualityReport,
    PlotQualityReport,
    WorldQualityReport,
)
from agents.base.review_result import (
    BaseReviewResult,
    CharacterReviewResult,
    PlotReviewResult,
    ReviewLoopResult,
    WorldReviewResult,
)
from agents.base.review_loop_base import (
    BaseReviewLoopHandler,
    ReviewLoopConfig,
    QualityLevel,
    IssueRecord,
    IssueTracker,
    ReviewProgressSummary,
)

__all__ = [
    # JSON 工具
    "JsonExtractor",
    "extract_json",
    # 质量报告
    "BaseQualityReport",
    "WorldQualityReport",
    "CharacterQualityReport",
    "PlotQualityReport",
    "ChapterQualityReport",
    # 审查结果
    "BaseReviewResult",
    "ReviewLoopResult",
    "WorldReviewResult",
    "CharacterReviewResult",
    "PlotReviewResult",
    # 循环处理器
    "BaseReviewLoopHandler",
    "ReviewLoopConfig",
    # 增强组件
    "QualityLevel",
    "IssueRecord",
    "IssueTracker",
    "ReviewProgressSummary",
]
