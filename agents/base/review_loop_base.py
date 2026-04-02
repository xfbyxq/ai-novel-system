"""审查循环处理器基类.

使用模板方法模式封装 Designer-Reviewer 审查循环的核心迭代逻辑。
子类只需实现特定领域的方法即可获得完整的审查循环功能。

主要流程：
1. 初始化循环状态
2. for iteration in 1..max_iterations:
   a. Reviewer 评估当前内容
   b. 构造质量报告
   c. 记录迭代历史
   d. 检查退出条件（passed 或达到上限）
   e. Builder/Designer 修订内容
   f. 更新当前内容和问题列表
3. 组装并返回最终结果
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, Set, TypeVar

from agents.base.json_extractor import JsonExtractor
from agents.base.quality_report import BaseQualityReport
from agents.base.review_result import BaseReviewResult
from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient

# 泛型类型
TContent = TypeVar("TContent")  # 内容类型：str, Dict, List
TResult = TypeVar("TResult", bound=BaseReviewResult)  # 结果类型
TReport = TypeVar("TReport", bound=BaseQualityReport)  # 报告类型


@dataclass
class ReviewLoopConfig:
    """审查循环配置.

    封装循环控制相关的参数。
    """

    # 质量阈值（默认 7.0，章节审查可用 7.5）
    quality_threshold: float = 7.0

    # 最大迭代次数
    max_iterations: int = 2

    # Reviewer 调用温度
    reviewer_temperature: float = 0.5

    # Builder 调用温度
    builder_temperature: float = 0.7

    # Reviewer 最大 token 数（None 表示不限制，避免 JSON 截断）
    reviewer_max_tokens: Optional[int] = None

    # Builder 最大 token 数（None 表示不限制，避免输出截断）
    builder_max_tokens: Optional[int] = None

    # ── 增强功能配置 ──────────────────────────────────────────

    # 是否启用跨轮次问题跟踪
    enable_issue_tracking: bool = True

    # 是否启用审查进度摘要
    enable_progress_summary: bool = True

    # 历史上下文最大字符预算
    max_context_chars: int = 2000

    # 问题匹配相似度阈值（bigram Jaccard）
    issue_match_threshold: float = 0.5


class QualityLevel(Enum):
    """质量级别枚举.

    根据评分将内容分为5个质量级别，
    每个级别对应不同的修订策略指引。
    """

    CRITICAL = "critical"  # < 5.0 — 严重不合格
    LOW = "low"  # 5.0 - 6.0 — 质量偏低
    MEDIUM = "medium"  # 6.0 - 7.0 — 基本合格
    HIGH = "high"  # 7.0 - 8.0 — 质量良好
    EXCELLENT = "excellent"  # >= 8.0 — 质量优秀

    @classmethod
    def from_score(cls, score: float) -> "QualityLevel":
        """根据评分返回对应的质量级别."""
        if score < 5.0:
            return cls.CRITICAL
        elif score < 6.0:
            return cls.LOW
        elif score < 7.0:
            return cls.MEDIUM
        elif score < 8.0:
            return cls.HIGH
        else:
            return cls.EXCELLENT

    def get_revision_strategy(self) -> str:
        """获取对应的中文修订策略指引."""
        strategies = {
            QualityLevel.CRITICAL: (
                "【修订策略：结构性重写】\n"
                "当前内容存在根本性问题，请不要在现有基础上修补，而是重新构思并重写。\n"
                "重点确保基本结构完整、核心要素齐备、逻辑自洽。"
            ),
            QualityLevel.LOW: (
                "【修订策略：大幅修订】\n"
                "保留可用的框架和亮点，但对问题部分进行重写。\n"
                "请按严重程度从高到低依次解决问题，优先修复标记为 HIGH 的问题。"
            ),
            QualityLevel.MEDIUM: (
                "【修订策略：针对性修改】\n"
                "整体框架可接受，请聚焦以下具体问题进行精准修改。\n"
                "保持现有结构不变，逐项解决指出的问题。"
            ),
            QualityLevel.HIGH: (
                "【修订策略：精细打磨】\n"
                "整体质量不错，请进行细节层面的优化和润色。\n"
                "重点提升薄弱维度的表现，保持已有优势。"
            ),
            QualityLevel.EXCELLENT: (
                "【修订策略：微调润色】\n"
                "当前质量已经很好，仅需做极少量的微调。\n"
                "注意不要过度修改导致质量下降。"
            ),
        }
        return strategies.get(self, strategies[QualityLevel.MEDIUM])

    def get_feedback_prefix(self) -> str:
        """获取反馈文本的质量层级引导语."""
        prefixes = {
            QualityLevel.CRITICAL: (
                "【严重不合格 - 需要大幅重写】\n"
                "当前质量远低于标准，请重点关注以下核心问题，进行结构性重写而非局部修补："
            ),
            QualityLevel.LOW: (
                "【质量偏低 - 需要重点修订】\n" "存在较多问题需要系统性改进，请按优先级逐一解决："
            ),
            QualityLevel.MEDIUM: (
                "【基本合格 - 需要针对性提升】\n" "整体框架可接受，请聚焦以下具体问题进行精准修改："
            ),
            QualityLevel.HIGH: ("【质量良好 - 细节优化】\n" "整体质量不错，请进行以下微调和润色："),
            QualityLevel.EXCELLENT: (
                "【质量优秀 - 微调润色】\n" "当前质量已达到较高水准，仅需少量微调："
            ),
        }
        return prefixes.get(self, prefixes[QualityLevel.MEDIUM])


@dataclass
class IssueRecord:
    """单条问题记录，用于跨轮次追踪问题生命周期."""

    id: str  # 由 area + description 生成的标识
    area: str  # 问题领域
    description: str  # 问题描述
    severity: str  # high/medium/low
    suggestion: str  # 改进建议
    first_seen_round: int  # 首次发现的轮次
    last_seen_round: int  # 最后出现的轮次
    status: str = "open"  # open / resolved / recurring
    resolution_round: Optional[int] = None  # 解决的轮次
    # 新增字段：详细问题报告
    priority_category: str = "polish"  # reading_experience/excitement/polish
    location: Optional[Dict[str, str]] = None  # 问题位置信息
    manifestation: List[str] = field(default_factory=list)  # 具体表现
    related_dimensions: List[str] = field(default_factory=list)  # 关联维度


class IssueTracker:
    """跨轮次问题追踪器.

    使用字符 bigram Jaccard 相似度进行问题匹配（无外部依赖），
    追踪每个问题在多轮审查中的生命周期（open → resolved/recurring）。
    """

    def __init__(self, match_threshold: float = 0.5):
        """初始化方法."""
        self._match_threshold = match_threshold
        self._records: List[IssueRecord] = []
        self._current_round: int = 0
        self._resolved_this_round: List[IssueRecord] = []
        self._new_this_round: List[IssueRecord] = []

    # ── 核心方法 ──────────────────────────────────────────────

    def update_round(
        self,
        round_num: int,
        report: BaseQualityReport,
        review_data: Dict[str, Any],
    ) -> None:
        """更新一轮审查的问题状态.

        Args:
            round_num: 当前轮次
            report: 质量报告
            review_data: 完整的审查数据
        """
        self._current_round = round_num
        self._resolved_this_round = []
        self._new_this_round = []

        # 提取本轮发现的所有问题
        current_issues = self._extract_issues(report, review_data, round_num)

        # 标记哪些已有 open 问题在本轮仍然存在
        matched_record_ids: Set[str] = set()

        for issue_dict in current_issues:
            matched = self._find_matching_record(issue_dict)
            if matched:
                # 已有问题再次出现
                matched.last_seen_round = round_num
                if matched.status == "resolved":
                    # 之前解决了又出现，标记为 recurring
                    matched.status = "recurring"
                    matched.resolution_round = None
                elif matched.last_seen_round - matched.first_seen_round >= 1:
                    matched.status = "recurring"
                # 更新建议（可能有更新的建议）
                if issue_dict.get("suggestion"):
                    matched.suggestion = issue_dict["suggestion"]
                matched_record_ids.add(matched.id)
            else:
                # 新问题
                record = IssueRecord(
                    id=self._generate_id(
                        issue_dict.get("area", ""), issue_dict.get("description", "")
                    ),
                    area=issue_dict.get("area", ""),
                    description=issue_dict.get("description", ""),
                    severity=issue_dict.get("severity", "medium"),
                    suggestion=issue_dict.get("suggestion", ""),
                    first_seen_round=round_num,
                    last_seen_round=round_num,
                    status="open",
                    # 新增字段
                    priority_category=issue_dict.get("priority_category", "polish"),
                    location=issue_dict.get("location"),
                    manifestation=issue_dict.get("manifestation", []),
                    related_dimensions=issue_dict.get("related_dimensions", []),
                )
                self._records.append(record)
                self._new_this_round.append(record)
                matched_record_ids.add(record.id)

        # 未在本轮出现的 open/recurring 问题 → resolved
        for record in self._records:
            if record.id not in matched_record_ids and record.status in (
                "open",
                "recurring",
            ):
                record.status = "resolved"
                record.resolution_round = round_num
                self._resolved_this_round.append(record)

    # ── 查询方法 ──────────────────────────────────────────────

    def get_open_issues(self) -> List[IssueRecord]:
        return [r for r in self._records if r.status == "open"]

    def get_resolved_issues(self) -> List[IssueRecord]:
        return [r for r in self._records if r.status == "resolved"]

    def get_recurring_issues(self) -> List[IssueRecord]:
        return [r for r in self._records if r.status == "recurring"]

    def get_resolved_this_round(self) -> List[IssueRecord]:
        return self._resolved_this_round

    def get_new_this_round(self) -> List[IssueRecord]:
        return self._new_this_round

    def get_active_issues(self) -> List[IssueRecord]:
        """获取所有活跃问题（open + recurring）."""
        return [r for r in self._records if r.status in ("open", "recurring")]

    def get_summary(self) -> Dict[str, int]:
        return {
            "total": len(self._records),
            "open": len(self.get_open_issues()),
            "resolved": len(self.get_resolved_issues()),
            "recurring": len(self.get_recurring_issues()),
        }

    # ── 格式化输出 ────────────────────────────────────────────

    def format_for_reviewer(self, max_chars: int = 1000) -> str:
        """生成给 Reviewer 的历史问题摘要."""
        if not self._records:
            return ""

        resolved = self.get_resolved_issues()
        active = self.get_active_issues()
        self.get_recurring_issues()

        lines = ["【历史问题追踪】"]

        # 已解决的问题
        if resolved:
            lines.append(f"已解决({len(resolved)})：")
            for r in resolved[:5]:  # 最多展示5个
                area_tag = f"[{r.area}] " if r.area else ""
                lines.append(
                    f"  - {area_tag}{r.description} "
                    f"(第{r.first_seen_round}轮发现, 第{r.resolution_round}轮解决)"
                )
            if len(resolved) > 5:
                lines.append(f"  ...及其他 {len(resolved) - 5} 个已解决问题")

        # 仍未解决的问题
        if active:
            lines.append(f"仍未解决({len(active)})：")
            # 按 severity 排序：high > medium > low
            severity_order = {"high": 0, "medium": 1, "low": 2}
            sorted_active = sorted(active, key=lambda r: severity_order.get(r.severity, 1))
            for r in sorted_active:
                area_tag = f"[{r.area}] " if r.area else ""
                persist_info = (
                    f"已持续{r.last_seen_round - r.first_seen_round + 1}轮"
                    if r.status == "recurring"
                    else ""
                )
                recurring_mark = " !!!" if r.status == "recurring" else ""
                lines.append(
                    f"  - [{r.severity.upper()}] {area_tag}{r.description} "
                    f"(第{r.first_seen_round}轮首次发现{', ' + persist_info if persist_info else ''}){recurring_mark}"
                )

        if active:
            lines.append('\n请重点验证以上"仍未解决"的问题是否已改善。')

        result = "\n".join(lines)
        if len(result) > max_chars:
            result = self._compress_text(result, max_chars)
        return result

    def format_for_builder(self, max_chars: int = 800) -> str:
        """生成给 Builder 的待解决问题清单（按优先级排序）."""
        active = self.get_active_issues()
        if not active:
            return ""

        recurring = [r for r in active if r.status == "recurring"]
        open_issues = [r for r in active if r.status == "open"]

        lines = ["【待解决问题清单】（按优先级排序）"]
        idx = 1

        if recurring:
            lines.append("\n反复出现 - 必须优先解决：")
            for r in recurring:
                area_tag = f"[{r.area}] " if r.area else ""
                lines.append(f"  {idx}. {area_tag}{r.description}")
                if r.suggestion:
                    lines.append(f"     建议：{r.suggestion}")
                idx += 1

        if open_issues:
            lines.append("\n本轮待解决：")
            severity_order = {"high": 0, "medium": 1, "low": 2}
            sorted_open = sorted(open_issues, key=lambda r: severity_order.get(r.severity, 1))
            for r in sorted_open:
                area_tag = f"[{r.area}] " if r.area else ""
                lines.append(f"  {idx}. [{r.severity.upper()}] {area_tag}{r.description}")
                if r.suggestion:
                    lines.append(f"     建议：{r.suggestion}")
                idx += 1

        result = "\n".join(lines)
        if len(result) > max_chars:
            result = self._compress_text(result, max_chars)
        return result

    # ── 内部方法 ──────────────────────────────────────────────

    def _extract_issues(
        self,
        report: BaseQualityReport,
        review_data: Dict[str, Any],
        round_num: int,
    ) -> List[Dict[str, Any]]:
        """从报告和审查数据中提取所有问题（兼容所有子类格式）.

        支持新旧两种格式：
        - 新格式：detailed_issues（包含 location, manifestation, priority_category）
        - 旧格式：issues, revision_suggestions 等
        """
        issues: List[Dict[str, Any]] = []
        seen_descs: Set[str] = set()  # 去重

        def add_issue(
            area: str,
            desc: str,
            severity: str = "medium",
            suggestion: str = "",
            priority_category: str = "polish",
            location: Optional[Dict[str, str]] = None,
            manifestation: Optional[List[str]] = None,
            related_dimensions: Optional[List[str]] = None,
        ):
            if desc and desc not in seen_descs:
                seen_descs.add(desc)
                issues.append(
                    {
                        "area": area,
                        "description": desc,
                        "severity": severity,
                        "suggestion": suggestion,
                        "priority_category": priority_category,
                        "location": location,
                        "manifestation": manifestation or [],
                        "related_dimensions": related_dimensions or [],
                    }
                )

        # 0. 从 detailed_issues 提取（新格式，优先级最高）
        for issue in review_data.get("detailed_issues", []):
            location_data = issue.get("location", {})
            add_issue(
                area=location_data.get("type", "global"),
                desc=issue.get("description", ""),
                severity=issue.get("severity", "medium"),
                suggestion=issue.get("suggestion", ""),
                priority_category=issue.get("priority_category", "polish"),
                location=location_data if location_data else None,
                manifestation=issue.get("manifestation", []),
                related_dimensions=issue.get("related_dimensions", []),
            )

        # 1. 从 report.issues 提取（通用格式）
        for issue in report.issues:
            add_issue(
                area=issue.get("area", issue.get("character", "")),
                desc=issue.get("issue", issue.get("description", "")),
                severity=issue.get("severity", "medium"),
                suggestion=issue.get("suggestion", ""),
            )

        # 2. 从 critical_issues 提取（世界观/角色/大纲）
        for issue in review_data.get("critical_issues", []):
            add_issue(
                area=issue.get("area", issue.get("character", "")),
                desc=issue.get("issue", issue.get("description", "")),
                severity=issue.get("severity", "medium"),
                suggestion=issue.get("suggestion", ""),
            )

        # 3. 从 revision_suggestions 提取（章节审查）
        for s in review_data.get("revision_suggestions", []):
            add_issue(
                area="章节内容",
                desc=s.get("issue", ""),
                severity=s.get("severity", "medium"),
                suggestion=s.get("suggestion", ""),
            )

        # 4. 从 character_assessments 提取（角色审查）
        for ca in review_data.get("character_assessments", []):
            char_name = ca.get("name", "")
            for w in ca.get("weaknesses", []):
                add_issue(area=char_name, desc=w, severity="medium")

        # 5. 从 volume_assessments 提取（大纲审查）
        for va in review_data.get("volume_assessments", []):
            vol_num = va.get("volume_num", "?")
            for w in va.get("weaknesses", []):
                add_issue(area=f"第{vol_num}卷", desc=w, severity="medium")

        # 6. 从 missing_elements 提取
        for m in review_data.get("missing_elements", []):
            add_issue(area="缺失", desc=m, severity="medium")

        return issues

    def _find_matching_record(self, issue_dict: Dict[str, str]) -> Optional[IssueRecord]:
        """在已有记录中查找与当前问题匹配的记录."""
        area = issue_dict.get("area", "")
        desc = issue_dict.get("description", "")

        best_match: Optional[IssueRecord] = None
        best_sim = 0.0

        for record in self._records:
            if record.status == "resolved" and record.resolution_round == self._current_round:
                # 本轮刚标记为 resolved 的不参与匹配（避免循环）
                continue

            same_area = record.area == area and area != ""
            sim = self._bigram_similarity(record.description, desc)

            threshold = self._match_threshold if same_area else 0.7

            if sim >= threshold and sim > best_sim:
                best_sim = sim
                best_match = record

        return best_match

    @staticmethod
    def _bigram_similarity(text1: str, text2: str) -> float:
        """计算两个文本的字符 bigram Jaccard 相似度."""
        if not text1 or not text2:
            return 0.0
        if text1 == text2:
            return 1.0

        def get_bigrams(text: str) -> Set[str]:
            return {text[i : i + 2] for i in range(len(text) - 1)} if len(text) >= 2 else {text}

        bigrams1 = get_bigrams(text1)
        bigrams2 = get_bigrams(text2)

        intersection = len(bigrams1 & bigrams2)
        union = len(bigrams1 | bigrams2)

        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _generate_id(area: str, description: str) -> str:
        """生成问题的唯一标识."""
        return f"{area}::{description[:50]}"

    @staticmethod
    def _compress_text(text: str, max_chars: int) -> str:
        """压缩文本到指定长度."""
        if len(text) <= max_chars:
            return text
        # 保留开头和结尾，中间截断
        keep = max_chars - 20
        return text[:keep] + "\n  ...（已省略部分内容）"


class ReviewProgressSummary:
    """审查进度摘要.

    构建审查过程的全局视角，包括评分趋势、各轮概况。
    """

    def __init__(self):
        """初始化方法."""
        self._rounds: List[Dict[str, Any]] = []
        self._scores: List[float] = []

    def update(
        self,
        iteration: int,
        score: float,
        issue_tracker: Optional["IssueTracker"] = None,
    ) -> None:
        """每轮更新进度信息."""
        round_info: Dict[str, Any] = {
            "iteration": iteration,
            "score": score,
        }
        if issue_tracker:
            summary = issue_tracker.get_summary()
            round_info["issues_total"] = summary["total"]
            round_info["issues_open"] = summary["open"]
            round_info["issues_resolved"] = summary["resolved"]
            round_info["issues_recurring"] = summary["recurring"]
            round_info["resolved_this_round"] = len(issue_tracker.get_resolved_this_round())
            round_info["new_this_round"] = len(issue_tracker.get_new_this_round())

        self._rounds.append(round_info)
        self._scores.append(score)

    @property
    def score_trend(self) -> str:
        """获取评分趋势描述."""
        if len(self._scores) < 2:
            return "首轮评估"

        total_change = self._scores[-1] - self._scores[0]
        if total_change > 0.5:
            return "持续改善"
        elif total_change > 0:
            return "略有改善"
        elif total_change > -0.3:
            return "基本持平"
        else:
            return "有所下降"

    def format_for_reviewer(self, max_chars: int = 800) -> str:
        """生成给 Reviewer 的进度概览."""
        if not self._rounds:
            return ""

        lines = ["【审查进度】"]

        # 评分趋势
        scores_text = " → ".join(f"{s:.1f}" for s in self._scores)
        total_change = self._scores[-1] - self._scores[0] if len(self._scores) > 1 else 0
        change_text = (
            f"{'+'if total_change >= 0 else ''}{total_change:.1f}" if len(self._scores) > 1 else ""
        )
        lines.append(
            f"评分趋势：{scores_text}（{self.score_trend}{', ' + change_text if change_text else ''}）"
        )

        # 各轮概况
        if len(self._rounds) > 1:
            lines.append("各轮概况：")
            for r in self._rounds:
                parts = [f"第{r['iteration']}轮: {r['score']:.1f}分"]
                if "resolved_this_round" in r and r["resolved_this_round"] > 0:
                    parts.append(f"解决{r['resolved_this_round']}个问题")
                if "new_this_round" in r and r["new_this_round"] > 0:
                    parts.append(f"新增{r['new_this_round']}个")
                if "issues_recurring" in r and r["issues_recurring"] > 0:
                    parts.append(f"反复{r['issues_recurring']}个")
                lines.append(f"  {', '.join(parts)}")

        result = "\n".join(lines)
        if len(result) > max_chars:
            # 压缩：只保留评分趋势和最近2轮
            lines_compressed = lines[:2]  # 标题 + 趋势
            if len(self._rounds) > 2:
                lines_compressed.append("各轮概况（仅显示最近）：")
                for r in self._rounds[-2:]:
                    parts = [f"第{r['iteration']}轮: {r['score']:.1f}分"]
                    lines_compressed.append(f"  {', '.join(parts)}")
            result = "\n".join(lines_compressed)
        return result

    def format_for_builder(self, max_chars: int = 500) -> str:
        """生成给 Builder 的简洁进度文本."""
        if len(self._rounds) < 2:
            return ""

        scores_text = " → ".join(f"{s:.1f}" for s in self._scores)
        total_change = self._scores[-1] - self._scores[0]

        result = (
            f"【审查进度】经过{len(self._rounds)}轮迭代，"
            f"评分变化：{scores_text}（{self.score_trend}，"
            f"{'+'if total_change >= 0 else ''}{total_change:.1f}）"
        )

        if len(result) > max_chars:
            result = result[: max_chars - 10] + "..."
        return result


class BaseReviewLoopHandler(ABC, Generic[TContent, TResult, TReport]):
    """审查循环处理器基类.

    使用模板方法模式，将共同的迭代控制逻辑封装在基类中，
    子类只需实现特定领域的抽象方法。

    泛型参数：
        TContent: 被审查内容的类型（str/Dict/List）
        TResult: 审查结果类型（继承自 BaseReviewResult）
        TReport: 质量报告类型（继承自 BaseQualityReport）

    使用示例：
        class WorldReviewHandler(BaseReviewLoopHandler[Dict, WorldReviewResult, WorldQualityReport]):
            def _get_loop_name(self) -> str:
                return "WorldReview"

            # ... 实现其他抽象方法
    """

    def __init__(
        self,
        client: QwenClient,
        cost_tracker: CostTracker,
        quality_threshold: float = 7.0,
        max_iterations: int = 2,
        config: Optional[ReviewLoopConfig] = None,
        timeout: Optional[float] = None,
    ):
        """初始化审查循环处理器.

        Args:
            client: LLM 客户端
            cost_tracker: 成本追踪器
            quality_threshold: 质量阈值
            max_iterations: 最大迭代次数
            config: 可选的详细配置（覆盖上述参数）
            timeout: 单次迭代超时时间（秒），None 表示不限制
        """
        self.client = client
        self.cost_tracker = cost_tracker
        self.timeout = timeout

        # 使用配置或默认值
        if config:
            self.config = config
        else:
            self.config = ReviewLoopConfig(
                quality_threshold=quality_threshold,
                max_iterations=max_iterations,
            )

        # 快捷访问
        self.quality_threshold = self.config.quality_threshold
        self.max_iterations = self.config.max_iterations

        # 增强组件（在 execute() 中初始化）
        self._issue_tracker: Optional[IssueTracker] = None
        self._progress_summary: Optional[ReviewProgressSummary] = None
        self._quality_level: QualityLevel = QualityLevel.MEDIUM
        self._reflection_agent = None

    # ══════════════════════════════════════════════════════════════════════════
    # 模板方法（核心迭代逻辑）
    # ══════════════════════════════════════════════════════════════════════════

    async def execute(self, initial_content: TContent, **context) -> TResult:
        """执行审查循环（模板方法）.

        这是核心的模板方法，定义了审查循环的完整流程。
        子类通过实现抽象方法来定制特定领域的行为。

        Args:
            initial_content: 初始内容（由子类定义具体类型）
            **context: 额外的上下文参数（如世界观、角色等）

        Returns:
            审查结果（由子类定义具体类型）
        """
        loop_name = self._get_loop_name()
        current_content = initial_content
        result = self._create_result()
        last_report: Optional[TReport] = None
        previous_issues: List[str] = []

        # 最佳记录追踪 & 停滞检测
        best_score = 0.0
        best_content = initial_content
        best_report: Optional[TReport] = None
        stagnation_count = 0

        # 初始化增强组件（存为实例属性，供 _build_iteration_context 等方法自动读取）
        self._issue_tracker = (
            IssueTracker(match_threshold=self.config.issue_match_threshold)
            if self.config.enable_issue_tracking
            else None
        )
        self._progress_summary = (
            ReviewProgressSummary() if self.config.enable_progress_summary else None
        )
        self._quality_level = QualityLevel.MEDIUM

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"[{loop_name}] 第 {iteration}/{self.max_iterations} 轮审查")

            # 获取上一轮评分
            previous_score = last_report.overall_score if last_report else 0

            # ── Step 1: Reviewer 评估 ────────────────────────────
            review_data = await self._call_reviewer(
                content=current_content,
                iteration=iteration,
                previous_score=previous_score,
                previous_issues=previous_issues,
                **context,
            )

            # ── Step 2: 构造质量报告 ────────────────────────────
            score = float(review_data.get("overall_score", 0))
            # 防止 overall_score 缺失时降为 0，使用维度平均分降级
            if score == 0 and "dimension_scores" in review_data:
                dim = review_data["dimension_scores"]
                if dim and isinstance(dim, dict):
                    try:
                        score = sum(float(v) for v in dim.values()) / len(dim)
                    except (ValueError, TypeError):
                        pass
            last_report = self._create_quality_report(review_data)
            # 使用报告中经过降级处理的分数，确保 score 与 last_report 一致
            if score == 0 and last_report.overall_score > 0:
                score = last_report.overall_score

            # ── Step 2.5: 更新问题跟踪和进度摘要 ─────────────
            self._quality_level = self._determine_quality_level(score)
            if self._issue_tracker:
                self._issue_tracker.update_round(iteration, last_report, review_data)
            if self._progress_summary:
                self._progress_summary.update(iteration, score, self._issue_tracker)

            # ── Step 3: 记录迭代历史 ────────────────────────────
            self._record_iteration(
                result=result,
                iteration=iteration,
                score=score,
                report=last_report,
                review_data=review_data,
                quality_level=self._quality_level.value,
                issues_resolved=(
                    len(self._issue_tracker.get_resolved_this_round()) if self._issue_tracker else 0
                ),
                issues_new=(
                    len(self._issue_tracker.get_new_this_round()) if self._issue_tracker else 0
                ),
                issues_recurring=(
                    len(self._issue_tracker.get_recurring_issues()) if self._issue_tracker else 0
                ),
            )

            logger.info(
                f"[{loop_name}] score={score:.1f}, "
                f"passed={last_report.passed}, "
                f"issues={len(last_report.issues)}"
            )

            # 更新最佳记录
            if score > best_score:
                best_score = score
                best_content = current_content
                best_report = last_report

            # ── Step 4: 检查退出条件 ────────────────────────────
            if last_report.passed:
                logger.info(f"[{loop_name}] 质量达标")
                break

            if iteration >= self.max_iterations:
                logger.warning(
                    f"[{loop_name}] 达到最大迭代次数 ({self.max_iterations})，"
                    f"当前评分 {score:.1f}"
                )
                break

            # 评分停滞检测：连续 2 轮改善 < 0.3 则提前终止
            if iteration > 1:
                improvement = score - previous_score
                if improvement < 0.3:
                    stagnation_count += 1
                else:
                    stagnation_count = 0

                if stagnation_count >= 2:
                    logger.warning(
                        f"[{loop_name}] 评分连续{stagnation_count}轮无明显改善"
                        f"(score={score:.1f})，提前终止"
                    )
                    break

            # ── Step 5: Builder 修订 ────────────────────────────
            logger.info(f"[{loop_name}] 质量未达标，请求修订...")

            # 构建反馈文本
            feedback = self._build_feedback_text(last_report, review_data)
            issues_text = self._build_issues_text(last_report, review_data)

            # 调用 Builder 修订
            revised_content = await self._call_builder(
                score=score,
                feedback=feedback,
                issues=issues_text,
                original_content=current_content,
                report=last_report,
                review_data=review_data,
                **context,
            )

            # ── Step 6: 更新状态 ────────────────────────────────
            if self._validate_revision(revised_content, current_content):
                current_content = revised_content
                previous_issues = self._collect_issues_for_next_round(last_report, review_data)
                logger.info(f"[{loop_name}] 修订完成")
            else:
                logger.warning(f"[{loop_name}] 修订失败，保留原内容")
                break

        # ── 组装最终结果（使用最佳分数对应的内容） ─────────────
        final_content = best_content if best_score > 0 else current_content
        final_report = best_report if best_report else last_report
        self._finalize_result(result, final_content, final_report)

        logger.info(
            f"[{loop_name}] 完成: iterations={result.total_iterations}, "
            f"score={result.final_score:.1f}, converged={result.converged}"
        )

        # ── 短期反思钩子 ──────────────────────────────────────
        if hasattr(self, "_run_reflection_hook"):
            await self._run_reflection_hook(result, context)

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # 必须实现的抽象方法
    # ══════════════════════════════════════════════════════════════════════════

    @abstractmethod
    def _get_loop_name(self) -> str:
        """获取循环名称（用于日志）.

        Returns:
            如 "WorldReview", "CharacterReview", "PlotReview", "ReviewLoop"
        """

    @abstractmethod
    def _create_result(self) -> TResult:
        """创建空的结果对象.

        Returns:
            对应类型的审查结果实例
        """

    @abstractmethod
    def _create_quality_report(self, review_data: Dict[str, Any]) -> TReport:
        """从 Reviewer 响应创建质量报告.

        Args:
            review_data: Reviewer 返回的评估数据

        Returns:
            对应类型的质量报告实例
        """

    @abstractmethod
    def _get_reviewer_system_prompt(self) -> str:
        """获取 Reviewer 的 system prompt.

        Returns:
            Reviewer 角色的系统提示词
        """

    @abstractmethod
    def _build_reviewer_task_prompt(
        self,
        content: TContent,
        iteration: int,
        previous_score: float,
        previous_issues: List[str],
        **context,
    ) -> str:
        """构建 Reviewer 的任务提示词.

        Args:
            content: 当前被审查的内容
            iteration: 当前迭代轮次
            previous_score: 上一轮评分
            previous_issues: 上一轮发现的问题
            **context: 额外上下文

        Returns:
            完整的任务提示词
        """

    @abstractmethod
    def _get_builder_system_prompt(self) -> str:
        """获取 Builder 的 system prompt.

        Returns:
            Builder/Designer/Architect 角色的系统提示词
        """

    @abstractmethod
    def _build_revision_prompt(
        self,
        score: float,
        feedback: str,
        issues: str,
        original_content: TContent,
        report: TReport,
        review_data: Dict[str, Any],
        **context,
    ) -> str:
        """构建修订任务的提示词.

        Args:
            score: 当前评分
            feedback: 反馈文本
            issues: 问题列表文本
            original_content: 原始内容
            report: 质量报告
            review_data: 完整的审查数据
            **context: 额外上下文

        Returns:
            完整的修订任务提示词
        """

    @abstractmethod
    def _validate_revision(self, revised: TContent, original: TContent) -> bool:
        """验证修订结果是否有效.

        Args:
            revised: 修订后的内容
            original: 原始内容

        Returns:
            修订是否有效
        """

    @abstractmethod
    def _finalize_result(
        self,
        result: TResult,
        final_content: TContent,
        last_report: Optional[TReport],
    ) -> None:
        """填充最终结果.

        Args:
            result: 结果对象（原地修改）
            final_content: 最终内容
            last_report: 最后一轮的质量报告
        """

    # ══════════════════════════════════════════════════════════════════════════
    # 可选覆盖的钩子方法
    # ══════════════════════════════════════════════════════════════════════════

    def _get_reviewer_agent_name(self) -> str:
        """获取 Reviewer 的代理名称（用于成本追踪）."""
        return f"{self._get_loop_name()}审查员"

    def _get_builder_agent_name(self) -> str:
        """获取 Builder 的代理名称（用于成本追踪）."""
        return f"{self._get_loop_name()}修订者"

    def _get_dimension_names(self) -> Dict[str, str]:
        """获取维度名称映射（用于反馈文本）.

        Returns:
            英文维度名 -> 中文维度名的映射
        """
        return {}

    def _build_feedback_text(self, report: TReport, review_data: Dict[str, Any]) -> str:
        """构建反馈文本.

        自动读取 self._quality_level 和 self._issue_tracker，
        生成包含质量层级引导语和问题解决状态的增强反馈。

        Args:
            report: 质量报告
            review_data: 完整的审查数据

        Returns:
            格式化的反馈文本
        """
        lines = []

        # 质量层级引导语
        if self._quality_level:
            lines.append(self._quality_level.get_feedback_prefix())
            lines.append("")

        # 整体评价和维度评分
        lines.append(f"整体评价：{report.summary}")

        dim_names = self._get_dimension_names()
        for dim, dim_score in report.dimension_scores.items():
            dim_display = dim_names.get(dim, dim)
            lines.append(f"- {dim_display}: {dim_score}/10")

        # 问题解决状态摘要
        if self._issue_tracker and self._issue_tracker._current_round > 1:
            resolved = self._issue_tracker.get_resolved_this_round()
            recurring = self._issue_tracker.get_recurring_issues()
            if resolved:
                lines.append(f"\n本轮已解决 {len(resolved)} 个问题。")
            if recurring:
                lines.append(f"仍有 {len(recurring)} 个反复出现的问题需优先处理。")

        return "\n".join(lines)

    def _build_issues_text(self, report: TReport, review_data: Dict[str, Any]) -> str:
        """构建问题列表文本.

        默认实现：列出所有严重问题。
        子类可覆盖以添加特定领域的问题格式。

        Args:
            report: 质量报告
            review_data: 完整的审查数据

        Returns:
            格式化的问题列表文本
        """
        lines = []

        for issue in report.issues:
            area = issue.get("area", "")
            desc = issue.get("issue", "")
            severity = issue.get("severity", "medium")
            suggestion = issue.get("suggestion", "")

            lines.append(f"[{severity.upper()}] {area}: {desc}")
            if suggestion:
                lines.append(f"  建议: {suggestion}")

        # 添加缺失元素
        missing = review_data.get("missing_elements", [])
        if missing:
            lines.append("\n缺失的重要元素：")
            for m in missing:
                lines.append(f"  - {m}")

        return "\n".join(lines) if lines else "（无具体问题）"

    def _collect_issues_for_next_round(
        self, report: TReport, review_data: Dict[str, Any]
    ) -> List[str]:
        """收集问题用于下一轮审查.

        默认实现：收集所有 critical_issues。
        子类可覆盖以添加特定领域的问题收集逻辑。

        Args:
            report: 质量报告
            review_data: 完整的审查数据

        Returns:
            问题描述列表
        """
        issues = []

        for issue in report.issues:
            area = issue.get("area", "")
            desc = issue.get("issue", "")
            issues.append(f"{area}: {desc}" if area else desc)

        # 添加缺失元素
        missing = review_data.get("missing_elements", [])
        for m in missing:
            issues.append(f"缺失: {m}")

        return issues

    def _record_iteration(
        self,
        result: TResult,
        iteration: int,
        score: float,
        report: TReport,
        review_data: Dict[str, Any],
        **kwargs,
    ) -> None:
        """记录迭代历史.

        默认实现：使用 result.add_iteration()。
        子类可覆盖以添加额外字段。

        Args:
            result: 结果对象
            iteration: 迭代轮次
            score: 评分
            report: 质量报告
            review_data: 完整的审查数据
            **kwargs: 额外记录字段（如 quality_level, issues_resolved 等）
        """
        result.add_iteration(
            iteration=iteration,
            score=score,
            passed=report.passed,
            issue_count=len(report.issues),
            dimension_scores=report.dimension_scores,
            **kwargs,
        )

    def _build_iteration_context(
        self,
        iteration: int,
        previous_score: float,
        previous_issues: List[str],
    ) -> str:
        """构建迭代上下文文本.

        用于告诉 Reviewer 这是第几轮审查，上一轮的问题是什么。
        自动读取 self._issue_tracker 和 self._progress_summary 生成增强上下文。

        Args:
            iteration: 当前迭代轮次
            previous_score: 上一轮评分
            previous_issues: 上一轮发现的问题

        Returns:
            迭代上下文文本
        """
        if iteration == 1:
            return "【首轮审查】这是首次评估。"

        sections = []
        max_chars = self.config.max_context_chars

        # 第一段：全局进度（来自 ReviewProgressSummary）
        if self._progress_summary:
            progress_text = self._progress_summary.format_for_reviewer(max_chars=max_chars // 3)
            if progress_text:
                sections.append(progress_text)

        # 第二段：问题追踪（来自 IssueTracker）
        if self._issue_tracker:
            tracker_text = self._issue_tracker.format_for_reviewer(max_chars=max_chars // 3)
            if tracker_text:
                sections.append(tracker_text)

        # 如果增强组件均无数据，回退到原始逻辑
        if not sections:
            issues_text = "\n".join(f"  - {issue}" for issue in (previous_issues or [])[:10])
            sections.append(
                f"上一轮评分：{previous_score}/10\n"
                f"上一轮发现的主要问题：\n{issues_text or '  （无）'}"
            )

        # 第三段：评估指引
        sections.append(
            "请重点评估：\n"
            "1. 之前标记的问题是否已解决？\n"
            "2. 修订后是否引入了新问题？\n"
            "3. 整体质量是否有实质性提升？\n"
            "如果问题已解决且没有新问题，应给予更高评分。"
        )

        header = f"【第 {iteration} 轮审查】\n这是修订后的内容，请评估修订效果。\n"
        result = header + "\n".join(sections)

        # Token 预算控制
        if len(result) > max_chars:
            result = result[: max_chars - 20] + "\n...（上下文已截断）"

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # 增强审查循环的钩子方法
    # ══════════════════════════════════════════════════════════════════════════

    def _determine_quality_level(self, score: float) -> QualityLevel:
        """根据评分确定质量级别.

        子类可覆盖以自定义质量分界。
        """
        return QualityLevel.from_score(score)

    def _build_revision_strategy_text(self, quality_level: QualityLevel, score: float) -> str:
        """根据质量级别生成修订策略指引.

        子类可覆盖以添加领域特定的策略细节。
        """
        return quality_level.get_revision_strategy()

    def _enhance_revision_prompt(self, original_prompt: str) -> str:
        """在子类的 _build_revision_prompt 返回值前注入增强上下文.

        读取 self._quality_level, self._issue_tracker, self._progress_summary，
        组装修订策略、进度上下文和问题优先级清单。

        Args:
            original_prompt: 子类构建的原始修订 prompt

        Returns:
            增强后的修订 prompt
        """
        prefix_parts = []

        # 反思经验注入（Writer 建议）
        if self._reflection_agent:
            writer_lessons = self._reflection_agent.get_lessons_for_writer()
            if writer_lessons:
                prefix_parts.append(writer_lessons)

        # 修订策略
        if self._quality_level:
            strategy = self._build_revision_strategy_text(self._quality_level, 0)
            if strategy:
                prefix_parts.append(strategy)

        # 进度上下文
        if self._progress_summary:
            progress = self._progress_summary.format_for_builder(max_chars=500)
            if progress:
                prefix_parts.append(progress)

        # 问题优先级清单
        if self._issue_tracker:
            issues = self._issue_tracker.format_for_builder(max_chars=800)
            if issues:
                prefix_parts.append(issues)

        if not prefix_parts:
            return original_prompt

        prefix = "\n\n".join(prefix_parts)
        return f"{prefix}\n\n---以下是具体修订任务---\n\n{original_prompt}"

    def _get_enhanced_reviewer_system_suffix(self) -> str:
        """非首轮审查时追加到 Reviewer system prompt 的追踪指引."""
        return (
            "\n\n【审查追踪指引】\n"
            "如果这不是首轮审查，请特别注意：\n"
            "1. 对照「历史问题追踪」中列出的问题，逐一验证是否已改善\n"
            "2. 在 improvement_assessment 字段中明确列出每个历史问题的当前状态\n"
            "3. 新发现的问题请标注为 new_issues\n"
            "4. 评分应反映实际改善程度——如果关键问题已解决，应相应提高评分"
        )

    # ══════════════════════════════════════════════════════════════════════════
    # LLM 调用方法（可选覆盖）
    # ══════════════════════════════════════════════════════════════════════════

    async def _call_reviewer(
        self,
        content: TContent,
        iteration: int,
        previous_score: float,
        previous_issues: List[str],
        **context,
    ) -> Dict[str, Any]:
        """调用 Reviewer 进行评估.

        Args:
            content: 被评估的内容
            iteration: 当前迭代轮次
            previous_score: 上一轮评分
            previous_issues: 上一轮的问题
            **context: 额外上下文

        Returns:
            解析后的评估数据
        """
        task_prompt = self._build_reviewer_task_prompt(
            content=content,
            iteration=iteration,
            previous_score=previous_score,
            previous_issues=previous_issues,
            **context,
        )

        try:
            # 非首轮审查时追加追踪指引到 system prompt
            system_prompt = self._get_reviewer_system_prompt()
            if iteration > 1:
                system_prompt += self._get_enhanced_reviewer_system_suffix()

            # 添加超时保护
            if self.timeout:
                response = await asyncio.wait_for(
                    self.client.chat(
                        prompt=task_prompt,
                        system=system_prompt,
                        temperature=self.config.reviewer_temperature,
                        max_tokens=self.config.reviewer_max_tokens,
                    ),
                    timeout=self.timeout,
                )
            else:
                response = await self.client.chat(
                    prompt=task_prompt,
                    system=system_prompt,
                    temperature=self.config.reviewer_temperature,
                    max_tokens=self.config.reviewer_max_tokens,
                )

            usage = response["usage"]
            self.cost_tracker.record(
                agent_name=self._get_reviewer_agent_name(),
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )

            return JsonExtractor.extract_object(
                response["content"],
                default={
                    "overall_score": self.quality_threshold,
                    "critical_issues": [],
                },
            )

        except Exception as e:
            logger.error(f"[{self._get_loop_name()}] Reviewer 评估失败: {e}")
            return {"overall_score": self.quality_threshold, "critical_issues": []}

    async def _call_builder(
        self,
        score: float,
        feedback: str,
        issues: str,
        original_content: TContent,
        report: TReport,
        review_data: Dict[str, Any],
        **context,
    ) -> TContent:
        """调用 Builder 进行修订.

        Args:
            score: 当前评分
            feedback: 反馈文本
            issues: 问题列表文本
            original_content: 原始内容
            report: 质量报告
            review_data: 完整的审查数据
            **context: 额外上下文

        Returns:
            修订后的内容
        """
        task_prompt = self._build_revision_prompt(
            score=score,
            feedback=feedback,
            issues=issues,
            original_content=original_content,
            report=report,
            review_data=review_data,
            **context,
        )

        # 注入增强上下文（修订策略、进度、问题优先级）
        task_prompt = self._enhance_revision_prompt(task_prompt)

        try:
            # 添加超时保护
            if self.timeout:
                response = await asyncio.wait_for(
                    self.client.chat(
                        prompt=task_prompt,
                        system=self._get_builder_system_prompt(),
                        temperature=self.config.builder_temperature,
                        max_tokens=self.config.builder_max_tokens,
                    ),
                    timeout=self.timeout,
                )
            else:
                response = await self.client.chat(
                    prompt=task_prompt,
                    system=self._get_builder_system_prompt(),
                    temperature=self.config.builder_temperature,
                    max_tokens=self.config.builder_max_tokens,
                )

            usage = response["usage"]
            self.cost_tracker.record(
                agent_name=self._get_builder_agent_name(),
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )

            content = response["content"]
            # 尝试解析 JSON，失败时重试一次
            try:
                return self._parse_builder_response(content)
            except ValueError as e:
                # JSON 解析失败，记录警告但不立即返回空值
                # 因为可能是 LLM 输出格式问题，而非网络问题
                logger.warning(
                    f"[{self._get_loop_name()}] Builder 响应 JSON 解析失败: {e}\n"
                    f"响应片段: {content[:200]}..."
                )
                # 返回空内容，让审查循环继续（下次迭代会重新尝试）
                return self._get_empty_content()

        except asyncio.TimeoutError:
            logger.error(f"[{self._get_loop_name()}] Builder 超时（timeout={self.timeout}s）")
            return self._get_empty_content()
        except Exception as e:
            # 区分 Connection error 和其他错误
            error_type = type(e).__name__
            error_msg = str(e)
            is_connection_error = any(
                keyword in error_msg.lower()
                for keyword in ["connection", "connect", "timeout", "network"]
            )
            if is_connection_error:
                logger.error(
                    f"[{self._get_loop_name()}] Builder 网络错误: {error_type}: {error_msg}\n"
                    f"LLM 调用重试已由 qwen_client 处理，本次返回空内容"
                )
            else:
                logger.error(f"[{self._get_loop_name()}] Builder 修订失败: {error_type}: {error_msg}")
            return self._get_empty_content()

    def _parse_builder_response(self, response_text: str) -> TContent:
        """解析 Builder 响应.

        默认实现: 提取 JSON.
        章节审查子类应覆盖此方法以返回纯文本.

        Args:
            response_text: LLM 响应文本

        Returns:
            解析后的内容
        """
        return JsonExtractor.extract_json(response_text, default=self._get_empty_content())

    def _get_empty_content(self) -> TContent:
        """获取空内容（修订失败时的默认值）.

        子类应覆盖此方法返回正确类型的空值。

        Returns:
            空内容（{} 或 [] 或 ""）
        """
        return {}  # 默认返回空字典

    # ══════════════════════════════════════════════════════════════════════════
    # 工具方法
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def to_json(obj: Any, indent: int = 2, max_length: Optional[int] = None) -> str:
        """将对象转换为 JSON 字符串.

        Args:
            obj: 要转换的对象
            indent: 缩进空格数
            max_length: 可选的最大长度限制

        Returns:
            JSON 字符串
        """
        text = json.dumps(obj, ensure_ascii=False, indent=indent)
        if max_length and len(text) > max_length:
            return text[:max_length]
        return text
