"""审查循环增强组件单元测试。

测试 QualityLevel、IssueTracker、ReviewProgressSummary 的核心功能。
"""

import pytest
from dataclasses import dataclass
from typing import Any, Dict, List

from agents.base.review_loop_base import (
    IssueTracker,
    QualityLevel,
    ReviewLoopConfig,
    ReviewProgressSummary,
)
from agents.base.quality_report import BaseQualityReport


# ── 辅助：构造 mock QualityReport ──────────────────────────────


@dataclass
class MockQualityReport(BaseQualityReport):
    """用于测试的 mock 质量报告."""


def make_report(
    score: float = 7.0,
    issues: List[Dict[str, Any]] = None,
    summary: str = "测试摘要",
) -> MockQualityReport:
    """便捷构造 mock 报告."""
    return MockQualityReport(
        overall_score=score,
        dimension_scores={},
        passed=score >= 7.0,
        issues=issues or [],
        summary=summary,
    )


# ══════════════════════════════════════════════════════════════════
# QualityLevel 测试
# ══════════════════════════════════════════════════════════════════


class TestQualityLevel:
    """QualityLevel 枚举测试."""

    @pytest.mark.parametrize("score,expected", [
        (0.0, QualityLevel.CRITICAL),
        (3.5, QualityLevel.CRITICAL),
        (4.9, QualityLevel.CRITICAL),
        (5.0, QualityLevel.LOW),
        (5.5, QualityLevel.LOW),
        (5.9, QualityLevel.LOW),
        (6.0, QualityLevel.MEDIUM),
        (6.5, QualityLevel.MEDIUM),
        (6.9, QualityLevel.MEDIUM),
        (7.0, QualityLevel.HIGH),
        (7.5, QualityLevel.HIGH),
        (7.9, QualityLevel.HIGH),
        (8.0, QualityLevel.EXCELLENT),
        (9.0, QualityLevel.EXCELLENT),
        (10.0, QualityLevel.EXCELLENT),
    ])
    def test_from_score(self, score, expected):
        assert QualityLevel.from_score(score) == expected

    def test_get_revision_strategy_returns_nonempty(self):
        for level in QualityLevel:
            strategy = level.get_revision_strategy()
            assert isinstance(strategy, str)
            assert len(strategy) > 10

    def test_get_feedback_prefix_returns_nonempty(self):
        for level in QualityLevel:
            prefix = level.get_feedback_prefix()
            assert isinstance(prefix, str)
            assert len(prefix) > 10

    def test_critical_strategy_mentions_rewrite(self):
        strategy = QualityLevel.CRITICAL.get_revision_strategy()
        assert "重写" in strategy

    def test_excellent_strategy_mentions_fine_tune(self):
        strategy = QualityLevel.EXCELLENT.get_revision_strategy()
        assert "微调" in strategy


# ══════════════════════════════════════════════════════════════════
# IssueTracker 测试
# ══════════════════════════════════════════════════════════════════


class TestBigramSimilarity:
    """bigram 相似度算法测试."""

    def test_identical_strings(self):
        sim = IssueTracker._bigram_similarity("角色性格不一致", "角色性格不一致")
        assert sim == 1.0

    def test_empty_strings(self):
        assert IssueTracker._bigram_similarity("", "") == 0.0
        assert IssueTracker._bigram_similarity("", "abc") == 0.0
        assert IssueTracker._bigram_similarity("abc", "") == 0.0

    def test_similar_strings(self):
        sim = IssueTracker._bigram_similarity("角色性格不一致", "角色的性格不太一致")
        assert sim >= 0.4  # 相似但不完全相同

    def test_different_strings(self):
        sim = IssueTracker._bigram_similarity("力量体系混乱", "角色性格不一致")
        assert sim < 0.3

    def test_single_char_strings(self):
        sim = IssueTracker._bigram_similarity("a", "a")
        assert sim == 1.0

    def test_completely_different(self):
        sim = IssueTracker._bigram_similarity("ABCD", "WXYZ")
        assert sim == 0.0


class TestIssueTracker:
    """IssueTracker 核心逻辑测试."""

    def _make_tracker(self, threshold: float = 0.5) -> IssueTracker:
        return IssueTracker(match_threshold=threshold)

    def test_first_round_all_open(self):
        """第一轮：所有问题都标记为 open."""
        tracker = self._make_tracker()
        report = make_report(issues=[
            {"area": "一致性", "issue": "时间线存在矛盾", "severity": "high"},
            {"area": "深度", "issue": "力量体系描述不够详细", "severity": "medium"},
        ])
        tracker.update_round(1, report, {})

        assert len(tracker.get_open_issues()) == 2
        assert len(tracker.get_resolved_issues()) == 0
        assert len(tracker.get_recurring_issues()) == 0

    def test_issue_resolved_when_not_in_next_round(self):
        """第二轮未出现的问题标记为 resolved."""
        tracker = self._make_tracker()

        # 第1轮：2个问题
        report1 = make_report(issues=[
            {"area": "一致性", "issue": "时间线存在矛盾", "severity": "high"},
            {"area": "深度", "issue": "力量体系描述不够详细", "severity": "medium"},
        ])
        tracker.update_round(1, report1, {})
        assert len(tracker.get_open_issues()) == 2

        # 第2轮：只有1个新问题
        report2 = make_report(issues=[
            {"area": "独特性", "issue": "设定缺乏新意", "severity": "low"},
        ])
        tracker.update_round(2, report2, {})

        assert len(tracker.get_resolved_issues()) == 2  # 前2个被解决
        assert len(tracker.get_open_issues()) == 1  # 新的1个
        assert len(tracker.get_new_this_round()) == 1

    def test_issue_becomes_recurring(self):
        """同一问题连续出现变为 recurring."""
        tracker = self._make_tracker()

        # 第1轮
        report1 = make_report(issues=[
            {"area": "一致性", "issue": "时间线存在矛盾", "severity": "high"},
        ])
        tracker.update_round(1, report1, {})
        assert tracker.get_open_issues()[0].status == "open"

        # 第2轮：同一问题再次出现
        report2 = make_report(issues=[
            {"area": "一致性", "issue": "时间线存在矛盾", "severity": "high"},
        ])
        tracker.update_round(2, report2, {})

        recurring = tracker.get_recurring_issues()
        assert len(recurring) == 1
        assert recurring[0].first_seen_round == 1
        assert recurring[0].last_seen_round == 2

    def test_fuzzy_matching(self):
        """模糊匹配：措辞略有不同但属于同一问题."""
        tracker = self._make_tracker(threshold=0.4)

        # 第1轮
        report1 = make_report(issues=[
            {"area": "一致性", "issue": "世界观内部时间线存在矛盾", "severity": "high"},
        ])
        tracker.update_round(1, report1, {})

        # 第2轮：相似问题（措辞略有不同）
        report2 = make_report(issues=[
            {"area": "一致性", "issue": "世界观内部的时间线有矛盾", "severity": "high"},
        ])
        tracker.update_round(2, report2, {})

        # 应匹配为同一问题（recurring），而不是新增
        assert len(tracker.get_recurring_issues()) == 1
        assert len(tracker.get_new_this_round()) == 0

    def test_extract_issues_from_critical_issues(self):
        """从 review_data['critical_issues'] 提取问题."""
        tracker = self._make_tracker()
        report = make_report(issues=[])
        review_data = {
            "critical_issues": [
                {"area": "力量体系", "issue": "等级划分不清晰", "severity": "high"},
            ]
        }
        tracker.update_round(1, report, review_data)
        assert len(tracker.get_open_issues()) == 1

    def test_extract_issues_from_revision_suggestions(self):
        """从 review_data['revision_suggestions'] 提取问题."""
        tracker = self._make_tracker()
        report = make_report(issues=[])
        review_data = {
            "revision_suggestions": [
                {"issue": "节奏过快", "suggestion": "增加过渡段", "severity": "medium"},
            ]
        }
        tracker.update_round(1, report, review_data)
        assert len(tracker.get_open_issues()) == 1

    def test_extract_issues_from_character_assessments(self):
        """从 review_data['character_assessments'] 提取问题."""
        tracker = self._make_tracker()
        report = make_report(issues=[])
        review_data = {
            "character_assessments": [
                {"name": "主角", "weaknesses": ["性格不鲜明", "缺少内在矛盾"]},
            ]
        }
        tracker.update_round(1, report, review_data)
        assert len(tracker.get_open_issues()) == 2

    def test_dedup_issues(self):
        """相同描述的问题应去重."""
        tracker = self._make_tracker()
        report = make_report(issues=[
            {"area": "一致性", "issue": "时间线矛盾", "severity": "high"},
        ])
        review_data = {
            "critical_issues": [
                {"area": "一致性", "issue": "时间线矛盾", "severity": "high"},
            ]
        }
        tracker.update_round(1, report, review_data)
        assert len(tracker.get_open_issues()) == 1  # 去重后只有1个

    def test_get_summary(self):
        """get_summary 返回正确统计."""
        tracker = self._make_tracker()

        report1 = make_report(issues=[
            {"area": "A", "issue": "问题1", "severity": "high"},
            {"area": "B", "issue": "问题2", "severity": "medium"},
        ])
        tracker.update_round(1, report1, {})

        report2 = make_report(issues=[
            {"area": "C", "issue": "问题3", "severity": "low"},
        ])
        tracker.update_round(2, report2, {})

        summary = tracker.get_summary()
        assert summary["total"] == 3
        assert summary["resolved"] == 2
        assert summary["open"] == 1

    def test_format_for_reviewer_empty(self):
        """无记录时返回空字符串."""
        tracker = self._make_tracker()
        assert tracker.format_for_reviewer() == ""

    def test_format_for_reviewer_with_data(self):
        """有数据时返回包含关键信息的文本."""
        tracker = self._make_tracker()

        report1 = make_report(issues=[
            {"area": "一致性", "issue": "时间线矛盾", "severity": "high"},
        ])
        tracker.update_round(1, report1, {})

        report2 = make_report(issues=[
            {"area": "一致性", "issue": "时间线矛盾", "severity": "high"},
        ])
        tracker.update_round(2, report2, {})

        text = tracker.format_for_reviewer()
        assert "历史问题追踪" in text
        assert "仍未解决" in text
        assert "时间线矛盾" in text

    def test_format_for_builder_with_data(self):
        """Builder 格式化包含优先级排序."""
        tracker = self._make_tracker()

        report1 = make_report(issues=[
            {"area": "A", "issue": "反复问题", "severity": "high"},
        ])
        tracker.update_round(1, report1, {})

        report2 = make_report(issues=[
            {"area": "A", "issue": "反复问题", "severity": "high"},
            {"area": "B", "issue": "新问题", "severity": "medium"},
        ])
        tracker.update_round(2, report2, {})

        text = tracker.format_for_builder()
        assert "待解决问题清单" in text
        assert "反复出现" in text
        assert "反复问题" in text

    def test_format_respects_max_chars(self):
        """格式化输出遵守 max_chars 限制."""
        tracker = self._make_tracker()

        # 添加很多问题
        issues = [
            {"area": f"领域{i}", "issue": f"这是一个比较长的问题描述{i}" * 5, "severity": "high"}
            for i in range(20)
        ]
        report = make_report(issues=issues)
        tracker.update_round(1, report, {})

        text = tracker.format_for_reviewer(max_chars=200)
        assert len(text) <= 220  # 允许少量超出（截断标记）

    def test_resolved_this_round(self):
        """get_resolved_this_round 只返回本轮解决的."""
        tracker = self._make_tracker()

        report1 = make_report(issues=[
            {"area": "A", "issue": "问题1", "severity": "high"},
            {"area": "B", "issue": "问题2", "severity": "medium"},
        ])
        tracker.update_round(1, report1, {})
        assert len(tracker.get_resolved_this_round()) == 0

        report2 = make_report(issues=[])
        tracker.update_round(2, report2, {})
        assert len(tracker.get_resolved_this_round()) == 2


# ══════════════════════════════════════════════════════════════════
# ReviewProgressSummary 测试
# ══════════════════════════════════════════════════════════════════


class TestReviewProgressSummary:
    """ReviewProgressSummary 测试."""

    def test_initial_state(self):
        summary = ReviewProgressSummary()
        assert summary.format_for_reviewer() == ""
        assert summary.format_for_builder() == ""

    def test_single_round(self):
        summary = ReviewProgressSummary()
        summary.update(1, 5.2, None)

        text = summary.format_for_reviewer()
        assert "5.2" in text
        assert summary.score_trend == "首轮评估"

    def test_improving_trend(self):
        summary = ReviewProgressSummary()
        summary.update(1, 5.2, None)
        summary.update(2, 6.5, None)
        summary.update(3, 7.8, None)

        assert summary.score_trend == "持续改善"

        reviewer_text = summary.format_for_reviewer()
        assert "5.2" in reviewer_text
        assert "7.8" in reviewer_text
        assert "持续改善" in reviewer_text

    def test_stagnating_trend(self):
        summary = ReviewProgressSummary()
        summary.update(1, 6.5, None)
        summary.update(2, 6.6, None)

        assert summary.score_trend == "略有改善"

    def test_declining_trend(self):
        summary = ReviewProgressSummary()
        summary.update(1, 7.0, None)
        summary.update(2, 6.5, None)

        assert summary.score_trend == "有所下降"

    def test_flat_trend(self):
        summary = ReviewProgressSummary()
        summary.update(1, 7.0, None)
        summary.update(2, 7.1, None)

        assert summary.score_trend == "略有改善"

    def test_format_for_builder_needs_two_rounds(self):
        summary = ReviewProgressSummary()
        summary.update(1, 5.0, None)
        assert summary.format_for_builder() == ""  # 需要至少2轮

        summary.update(2, 6.0, None)
        text = summary.format_for_builder()
        assert "审查进度" in text
        assert "5.0" in text
        assert "6.0" in text

    def test_with_issue_tracker_integration(self):
        """与 IssueTracker 集成."""
        tracker = IssueTracker()
        summary = ReviewProgressSummary()

        report1 = make_report(issues=[
            {"area": "A", "issue": "问题1", "severity": "high"},
        ])
        tracker.update_round(1, report1, {})
        summary.update(1, 5.5, tracker)

        report2 = make_report(issues=[])
        tracker.update_round(2, report2, {})
        summary.update(2, 7.0, tracker)

        text = summary.format_for_reviewer()
        assert "解决" in text

    def test_format_respects_max_chars(self):
        summary = ReviewProgressSummary()
        for i in range(1, 11):
            summary.update(i, 5.0 + i * 0.3, None)

        text = summary.format_for_reviewer(max_chars=150)
        assert len(text) <= 200  # 允许少量超出


# ══════════════════════════════════════════════════════════════════
# ReviewLoopConfig 扩展字段测试
# ══════════════════════════════════════════════════════════════════


class TestReviewLoopConfig:
    """ReviewLoopConfig 新增字段测试."""

    def test_default_values(self):
        """新增字段的默认值."""
        config = ReviewLoopConfig()
        assert config.enable_issue_tracking is True
        assert config.enable_progress_summary is True
        assert config.max_context_chars == 2000
        assert config.issue_match_threshold == 0.5

    def test_backward_compatible_construction(self):
        """不传新字段时仍能正常构造（向后兼容）."""
        config = ReviewLoopConfig(
            quality_threshold=7.5,
            max_iterations=3,
        )
        assert config.quality_threshold == 7.5
        assert config.max_iterations == 3
        assert config.enable_issue_tracking is True

    def test_custom_new_fields(self):
        """自定义新字段值."""
        config = ReviewLoopConfig(
            enable_issue_tracking=False,
            enable_progress_summary=False,
            max_context_chars=1000,
            issue_match_threshold=0.6,
        )
        assert config.enable_issue_tracking is False
        assert config.enable_progress_summary is False
        assert config.max_context_chars == 1000
        assert config.issue_match_threshold == 0.6
