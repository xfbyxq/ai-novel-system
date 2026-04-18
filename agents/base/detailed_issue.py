"""详细问题数据结构.

用于支持生成用户期望的详细评估报告，包含：
- 问题位置定位（段落/场景/角色/整体）
- 具体表现描述
- 优先级分类（影响阅读体验/提升表现力/细节打磨）
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PriorityCategory(Enum):
    """问题优先级分类.

    用于指导 Writer 修订的优先级：
    - READING_EXPERIENCE: 影响阅读体验，必须修改
    - CRAFT_QUALITY: 提升表现力，建议增强
    - POLISH: 细节打磨，可考虑优化
    """

    READING_EXPERIENCE = "reading_experience"  # 影响阅读体验
    CRAFT_QUALITY = "craft_quality"  # 提升表现力
    POLISH = "polish"  # 细节打磨

    def get_revision_directive(self) -> str:
        """获取修订指令语气."""
        directives = {
            PriorityCategory.READING_EXPERIENCE: "必须修改",
            PriorityCategory.CRAFT_QUALITY: "建议增强",
            PriorityCategory.POLISH: "可考虑优化",
        }
        return directives[self]

    def get_chinese_name(self) -> str:
        """获取中文显示名称."""
        names = {
            PriorityCategory.READING_EXPERIENCE: "影响阅读体验",
            PriorityCategory.CRAFT_QUALITY: "提升表现力",
            PriorityCategory.POLISH: "细节打磨",
        }
        return names[self]


class IssueLocationType(Enum):
    """问题位置类型."""

    PARAGRAPH = "paragraph"  # 段落级别
    SCENE = "scene"  # 场景级别
    CHARACTER = "character"  # 角色相关
    GLOBAL = "global"  # 整体问题

    def get_chinese_name(self) -> str:
        """获取中文显示名称."""
        names = {
            IssueLocationType.PARAGRAPH: "段落",
            IssueLocationType.SCENE: "场景",
            IssueLocationType.CHARACTER: "角色",
            IssueLocationType.GLOBAL: "整体",
        }
        return names[self]


@dataclass
class IssueLocation:
    """问题位置定位.

    用于精确定位问题所在位置，帮助 Writer 快速找到需要修改的内容。

    Attributes:
        type: 位置类型（paragraph/scene/character/global）
        identifier: 具体位置标识（如"第3段"、"开篇场景"、"主角王明"）
        excerpt: 问题片段摘录（可选，50字以内）
    """

    type: str  # "paragraph"/"scene"/"character"/"global"
    identifier: str  # 具体位置标识
    excerpt: Optional[str] = None  # 问题片段摘录（可选）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式."""
        return {
            "type": self.type,
            "identifier": self.identifier,
            "excerpt": self.excerpt,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IssueLocation":
        """从字典创建."""
        return cls(
            type=data.get("type", "global"),
            identifier=data.get("identifier", ""),
            excerpt=data.get("excerpt"),
        )

    def format_display(self) -> str:
        """格式化显示文本."""
        type_display = {
            "paragraph": "段落",
            "scene": "场景",
            "character": "角色",
            "global": "整体",
        }
        type_name = type_display.get(self.type, self.type)
        return f"[{type_name}]{self.identifier}"


@dataclass
class DetailedIssue:
    """详细问题描述.

    包含问题的完整信息，用于生成详细评估报告和指导修订。

    Attributes:
        location: 问题位置
        description: 问题描述（精炼概括）
        manifestation: 具体表现（原文中的具体表现列表）
        severity: 严重程度（high/medium/low）
        priority_category: 优先级分类
        suggestion: 修订建议
        related_dimensions: 关联维度（如 coherence/plausibility/engagement）
    """

    location: IssueLocation
    description: str  # 问题描述（精炼概括）
    manifestation: List[str] = field(default_factory=list)  # 具体表现
    severity: str = "medium"  # "high"/"medium"/"low"
    priority_category: str = "polish"  # 优先级分类
    suggestion: str = ""  # 修订建议
    related_dimensions: List[str] = field(default_factory=list)  # 关联维度

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式."""
        return {
            "location": self.location.to_dict(),
            "description": self.description,
            "manifestation": self.manifestation,
            "severity": self.severity,
            "priority_category": self.priority_category,
            "suggestion": self.suggestion,
            "related_dimensions": self.related_dimensions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DetailedIssue":
        """从字典创建."""
        location_data = data.get("location", {})
        location = IssueLocation.from_dict(location_data)

        # 向后兼容：旧值 "excitement" 映射为 "craft_quality"
        raw_priority = data.get("priority_category", "polish")
        if raw_priority == "excitement":
            raw_priority = "craft_quality"

        return cls(
            location=location,
            description=data.get("description", ""),
            manifestation=data.get("manifestation", []),
            severity=data.get("severity", "medium"),
            priority_category=raw_priority,
            suggestion=data.get("suggestion", ""),
            related_dimensions=data.get("related_dimensions", []),
        )

    def format_for_revision(self) -> str:
        """格式化修订指导文本."""
        lines = []

        # 位置和问题描述
        lines.append(f"位置{self.location.format_display()}: {self.description}")

        # 具体表现
        if self.manifestation:
            lines.append(f"  表现: {', '.join(self.manifestation)}")

        # 摘录（如果有）
        if self.location.excerpt:
            lines.append(f'  原文: "{self.location.excerpt}"')

        # 修订建议
        if self.suggestion:
            lines.append(f"  建议: {self.suggestion}")

        return "\n".join(lines)

    def get_priority_enum(self) -> PriorityCategory:
        """获取优先级枚举对象."""
        try:
            return PriorityCategory(self.priority_category)
        except ValueError:
            return PriorityCategory.POLISH


def group_issues_by_priority(issues: List[DetailedIssue]) -> Dict[str, List[DetailedIssue]]:
    """按优先级分组问题.

    Args:
        issues: 详细问题列表

    Returns:
        分组后的问题字典，键为优先级分类
    """
    grouped = {
        "reading_experience": [],
        "craft_quality": [],
        "polish": [],
    }

    for issue in issues:
        category = issue.priority_category
        if category in grouped:
            grouped[category].append(issue)
        else:
            grouped["polish"].append(issue)

    return grouped


def format_issues_table(issues: List[DetailedIssue]) -> str:
    """格式化问题表格输出.

    生成类似用户报告中的表格格式：
    | 位置 | 问题描述 | 具体表现 |

    Args:
        issues: 详细问题列表

    Returns:
        格式化的表格文本
    """
    if not issues:
        return "无问题发现"

    lines = []
    lines.append("| 位置 | 问题描述 | 具体表现 |")
    lines.append("|------|----------|----------|")

    for issue in issues:
        location_str = issue.location.format_display()
        description = issue.description
        manifestation = ", ".join(issue.manifestation) if issue.manifestation else "-"

        # 截断过长内容
        if len(description) > 30:
            description = description[:30] + "..."
        if len(manifestation) > 50:
            manifestation = manifestation[:50] + "..."

        lines.append(f"| {location_str} | {description} | {manifestation} |")

    return "\n".join(lines)
