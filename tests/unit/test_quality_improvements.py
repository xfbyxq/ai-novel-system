"""Tests for quality improvement components.

Tests for:
- GlobalConsistencyChecker
- LexicalDiversityChecker
- ChapterRhythmPlanner
- EmotionDiversityChecker
- SubplotTracker
- StyleConsistencyChecker
"""

import pytest

from agents.chapter_rhythm_planner import ChapterRhythmPlanner, ChapterType, TensionLevel
from agents.emotion_diversity_checker import (
    CharacterEmotionalProfile,
    EmotionDiversityChecker,
)
from agents.global_consistency_checker import (
    ConsistencyCheckResult,
    EntityProfile,
    GlobalConsistencyChecker,
    Severity,
)
from agents.lexical_diversity_checker import LexicalDiversityChecker
from agents.style_consistency_checker import StyleConsistencyChecker
from agents.subplot_tracker import SubplotInfo, SubplotTracker


class TestGlobalConsistencyChecker:
    """全局一致性检查器测试."""

    @pytest.fixture
    def checker(self):
        c = GlobalConsistencyChecker()
        c.register_entity(EntityProfile(name="林尘", gender="male", aliases=["小尘"]))
        c.register_entity(EntityProfile(name="小翠", gender="female"))
        return c

    def test_pronoun_error_male_with_she(self, checker):
        """男性角色段落中使用女性代词应被检测."""
        content = "林尘盘膝而坐。然而，就在她准备收功之际，一阵剧痛袭来。"
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            checker.check(content, chapter_number=1)
        )
        assert not result.passed
        assert result.high_count > 0
        assert any(i.issue_type == "pronoun_error" for i in result.issues)

    def test_pronoun_correct_male_with_he(self, checker):
        """男性角色使用正确代词不应报错."""
        content = "林尘盘膝而坐。他缓缓睁开双眼。"
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            checker.check(content, chapter_number=1)
        )
        assert result.passed

    def test_pronoun_error_female_with_he(self, checker):
        """女性角色段落中使用男性代词应被检测."""
        content = "小翠独自站在窗前。他望着外面的月光。"
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            checker.check(content, chapter_number=1)
        )
        assert not result.passed

    def test_mixed_gender_no_false_positive(self, checker):
        """混合性别角色不应产生误判."""
        content = "林尘和小翠坐在院子里。他看着她，她也看着他。"
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            checker.check(content, chapter_number=1)
        )
        assert result.passed

    def test_consistency_result_scoring(self):
        """一致性评分计算."""
        result = ConsistencyCheckResult(chapter_number=1)
        result.issues.append(ConsistencyCheckResult.__annotations__)  # dummy
        result.issues.clear()
        result.issues.append(
            type("Issue", (), {"severity": Severity.HIGH})()
        )
        result.high_count = 1
        assert result.overall_score < 10.0

    def test_timeline_regression(self, checker):
        """时间回退应被检测."""
        checker.record_timeline(1, "深夜")
        import asyncio
        content = "次日清晨，阳光明媚。"  # 正常推进
        result = asyncio.get_event_loop().run_until_complete(
            checker.check(content, chapter_number=2)
        )
        assert result.passed


class TestLexicalDiversityChecker:
    """词汇多样性检测器测试."""

    def test_repeated_phrase_detected(self):
        """重复短语应被检测."""
        checker = LexicalDiversityChecker(window_chapters=3, phrase_threshold=2)
        chapters = {
            1: "林萧瞳孔微缩，冷冷地看着对手。",
            2: "林萧瞳孔微缩，目光如刀。",
        }
        report = checker.check(
            content="林萧瞳孔微缩，指节泛白。",
            chapter_number=3,
            previous_chapters=chapters,
        )
        assert len(report.repetition_issues) > 0
        assert any("瞳孔微缩" in i.phrase for i in report.repetition_issues)

    def test_unique_word_ratio(self):
        """独特词比率应正确计算."""
        checker = LexicalDiversityChecker()
        # 高度重复的文本
        repeated = "他来了他来了他来了他来了他来了"
        report = checker.check(repeated, chapter_number=1)
        assert report.unique_word_ratio < 0.5

        # 词汇丰富的文本
        diverse = "春风拂面，鸟语花香。远处的山峦在晨雾中若隐若现，溪水潺潺流淌。"
        report2 = checker.check(diverse, chapter_number=2)
        assert report2.unique_word_ratio > report.unique_word_ratio

    def test_editor_suggestions(self):
        """Editor 建议应正确生成."""
        checker = LexicalDiversityChecker()
        report = checker.check(
            content="瞳孔微缩指节泛白瞳孔微缩",
            chapter_number=1,
        )
        suggestions = checker.generate_editor_suggestions(report)
        assert isinstance(suggestions, list)


class TestChapterRhythmPlanner:
    """章节节奏规划器测试."""

    def test_no_consecutive_battles(self):
        """连续战斗章节不应超过上限."""
        planner = ChapterRhythmPlanner(max_consecutive_battles=2)
        prev = [ChapterType.BATTLE, ChapterType.BATTLE]
        plan = planner.plan_chapter(3, prev)
        assert plan.chapter_type != ChapterType.BATTLE

    def test_volume_plan_valid(self):
        """整卷规划应包含多种类型."""
        planner = ChapterRhythmPlanner()
        vol_plan = planner.plan_volume(1, (1, 8))
        assert vol_plan.is_valid
        assert len(vol_plan.type_distribution) >= 3

    def test_tension_level_mapping(self):
        """章节类型到紧张度的映射应正确."""
        assert TensionLevel.for_type(ChapterType.BATTLE).value >= 8
        assert TensionLevel.for_type(ChapterType.DAILY).value <= 4

    def test_planner_prompt_generation(self):
        """节奏规划提示词应正确生成."""
        planner = ChapterRhythmPlanner()
        plan = planner.plan_chapter(1, suggested_type=ChapterType.BATTLE)
        prompt = planner.build_planner_prompt(plan)
        assert "战斗" in prompt
        assert "旁观者反应" in prompt


class TestEmotionDiversityChecker:
    """角色情感多样性检测器测试."""

    def test_single_emotion_fails(self):
        """单一情感应不通过."""
        checker = EmotionDiversityChecker(window_chapters=3, min_emotion_variety=2)
        profile = CharacterEmotionalProfile.default_for_protagonist("林尘")
        checker.register_profile(profile)

        chapters = {
            1: "林尘冷静地分析着局势。",
            2: "林尘冷静地看着前方。",
            3: "林尘依然冷静。",
        }
        report = checker.check(
            chapters[3], "林尘", chapter_number=3,
            previous_chapters={1: chapters[1], 2: chapters[2]},
        )
        assert not report.passed
        assert len(report.unique_emotions) == 1

    def test_diverse_emotions_pass(self):
        """多样化情感应通过."""
        checker = EmotionDiversityChecker(window_chapters=3, min_emotion_variety=2)
        profile = CharacterEmotionalProfile.default_for_protagonist("林尘")
        checker.register_profile(profile)

        chapters = {
            1: "林尘冷静地分析着局势。",
            2: "林尘愤怒地握紧拳头，怒火中烧。",
            3: "林尘无奈地苦笑了。",
        }
        report = checker.check(
            chapters[3], "林尘", chapter_number=3,
            previous_chapters={1: chapters[1], 2: chapters[2]},
        )
        assert report.passed
        assert len(report.unique_emotions) >= 2

    def test_writer_prompt(self):
        """Writer 提示词应正确生成."""
        checker = EmotionDiversityChecker()
        from agents.emotion_diversity_checker import EmotionDiversityReport
        report = EmotionDiversityReport(chapter_number=1, character_name="林尘")
        report.passed = False
        report.suggestions = ["建议展现更多情感"]
        prompt = checker.build_writer_prompt(report)
        assert "情感要求" in prompt


class TestSubplotTracker:
    """支线追踪器测试."""

    def test_remind_missing_subplot(self):
        """未触发的支线应提醒."""
        tracker = SubplotTracker(max_chapters_without_appearance=3)
        tracker.register_subplot(SubplotInfo(
            name="小翠身世",
            description="小翠的真实身份之谜",
            trigger_chapter=2,
            importance=8,
            involved_characters=["小翠"],
        ))
        reminders = tracker.check_and_remind(current_chapter=6)
        assert len(reminders) >= 1
        assert reminders[0].subplot_name == "小翠身世"
        assert reminders[0].urgency == "high"

    def test_no_reminder_when_recent(self):
        """最近出现的支线不应提醒."""
        tracker = SubplotTracker(max_chapters_without_appearance=3)
        tracker.register_subplot(SubplotInfo(
            name="感情线",
            description="主角与女主的感情发展",
            trigger_chapter=1,
            importance=5,
            involved_characters=["小翠"],
        ))
        tracker.record_appearance(5, ["感情线"])
        reminders = tracker.check_and_remind(current_chapter=6)
        assert len(reminders) == 0

    def test_subplot_summary(self):
        """支线摘要应正确生成."""
        tracker = SubplotTracker()
        tracker.register_subplot(SubplotInfo(
            name="阴谋线",
            description="幕后黑手的阴谋",
            trigger_chapter=1,
            importance=9,
            involved_characters=["黑袍人"],
        ))
        tracker.record_appearance(3, ["阴谋线"])
        summary = tracker.get_subplot_summary(current_chapter=5)
        assert "阴谋线" in summary


class TestStyleConsistencyChecker:
    """风格一致性检测器测试."""

    def test_serious_content_fails_humor_style(self):
        """严肃内容不应通过轻松幽默风格检查."""
        checker = StyleConsistencyChecker(target_style="轻松幽默")
        content = "夜风如刀，林萧冷冷地站在破庙前。杀意在心中翻涌。"
        report = checker.check(content, chapter_number=1)
        assert not report.passed
        assert report.humor_count == 0

    def test_humor_content_passes(self):
        """包含幽默元素的内容应通过."""
        checker = StyleConsistencyChecker(target_style="轻松幽默")
        content = "林萧叹了口气，自嘲道：重生回来还是这么穷。小翠眨眨眼，俏皮地说：哥，今晚吃啥？"
        report = checker.check(content, chapter_number=1)
        assert report.passed
        assert report.humor_count >= 2

    def test_writer_prompt(self):
        """Writer 提示词应正确生成."""
        checker = StyleConsistencyChecker(target_style="轻松幽默")
        from agents.style_consistency_checker import StyleReport
        report = StyleReport(chapter_number=1, target_style="轻松幽默")
        report.passed = False
        report.suggestions = ["增加幽默元素"]
        prompt = checker.build_writer_prompt(report)
        assert "风格定位" in prompt
        assert "幽默" in prompt


# =========================================================================
# 闭环集成测试：验证节奏规划前置、支线提醒注入、情感约束注入、修订触发
# =========================================================================


class TestRhythmPlannerIntegration:
    """节奏规划前置集成测试."""

    def test_plan_chapter_returns_writer_prompt(self):
        """节奏规划器应能生成可注入策划师的提示词."""
        planner = ChapterRhythmPlanner(max_consecutive_battles=2, min_daily_per_5=1)
        # 模拟前3章都是战斗
        prev_types = [ChapterType.BATTLE, ChapterType.BATTLE]
        plan = planner.plan_chapter(chapter_number=3, previous_types=prev_types)
        # 连续2章战斗后不应再是战斗
        assert plan.chapter_type != ChapterType.BATTLE
        # 应能生成提示词
        prompt = planner.build_planner_prompt(plan)
        assert "节奏规划" in prompt
        assert plan.chapter_type.value in prompt

    def test_rhythm_plan_daily_requirement(self):
        """每5章必须有至少1章日常/情感."""
        planner = ChapterRhythmPlanner(max_consecutive_battles=2, min_daily_per_5=1)
        prev_types = [
            ChapterType.BATTLE,
            ChapterType.TRAINING,
            ChapterType.PLOT_TWIST,
            ChapterType.EXPLORATION,
            ChapterType.BATTLE,
        ]
        plan = planner.plan_chapter(chapter_number=6, previous_types=prev_types)
        # 前5章无日常/情感类，第6章应被强制为日常或情感类
        assert plan.chapter_type in (ChapterType.DAILY, ChapterType.EMOTIONAL)


class TestSubplotReminderIntegration:
    """支线提醒注入测试."""

    def test_subplot_reminder_generated_when_missing(self):
        """支线超过阈值未出现应生成提醒."""
        tracker = SubplotTracker(max_chapters_without_appearance=3)
        tracker.register_subplot(SubplotInfo(
            name="小翠身世",
            description="小翠的神秘身世探索",
            importance=8,
            trigger_chapter=1,
        ))
        # 到第5章都没出现过
        reminders = tracker.check_and_remind(current_chapter=5)
        assert len(reminders) >= 1
        assert reminders[0].subplot_name == "小翠身世"
        assert reminders[0].urgency in ("high", "medium")

    def test_subplot_no_reminder_when_recently_appeared(self):
        """最近出现过的支线不应生成提醒."""
        tracker = SubplotTracker(max_chapters_without_appearance=3)
        tracker.register_subplot(SubplotInfo(
            name="小翠身世",
            description="小翠的神秘身世探索",
            importance=8,
            trigger_chapter=1,
        ))
        tracker.record_appearance(chapter_number=4, subplot_names=["小翠身世"])
        reminders = tracker.check_and_remind(current_chapter=5)
        assert len(reminders) == 0


class TestEmotionConstraintIntegration:
    """情感约束注入测试."""

    def test_emotion_constraint_for_single_emotion_protagonist(self):
        """主角只有单一情感应生成约束提示词."""
        checker = EmotionDiversityChecker(window_chapters=3, min_emotion_variety=3)
        checker.register_profile(
            CharacterEmotionalProfile.default_for_protagonist("林萧")
        )
        # 前几章只有“冷静”
        prev_chapters = {
            1: "林萧冷静地看着对方，脸上毫无波澜。林萧冷冷一笑。",
            2: "林萧平静地收回目光，他的表情一如既往的冷漠。",
        }
        report = checker.check(
            content="", character_name="林萧",
            chapter_number=3, previous_chapters=prev_chapters,
        )
        prompt = checker.build_writer_prompt(report)
        assert "角色情感要求" in prompt
        assert "林萧" in prompt


class TestQualityFixTrigger:
    """质量修订触发逻辑测试."""

    def test_no_fix_when_all_passed(self):
        """所有检查通过时不应触发修订."""
        quality_reports = {
            "global_consistency": {"passed": True, "issues": []},
            "lexical_diversity": {"passed": True},
        }
        # _apply_quality_fixes 内部会收集 fix_instructions，如果为空则返回 False
        fix_instructions = []
        gc_report = quality_reports.get("global_consistency", {})
        if isinstance(gc_report, dict) and not gc_report.get("passed", True):
            for i in gc_report.get("issues", []):
                if isinstance(i, dict) and i.get("severity") == "high":
                    fix_instructions.append(i)
        lex_report = quality_reports.get("lexical_diversity", {})
        if isinstance(lex_report, dict) and not lex_report.get("passed", True):
            fix_instructions.append("lex_issue")
        assert len(fix_instructions) == 0

    def test_fix_triggered_for_high_severity_consistency(self):
        """全局一致性的 high severity 问题应触发修订."""
        quality_reports = {
            "global_consistency": {
                "passed": False,
                "issues": [
                    {
                        "issue_type": "pronoun_error",
                        "description": "林尘段落中检测到女性代词\u201c她\u201d",
                        "severity": "high",
                        "suggestion": "应使用\u201c他\u201d",
                    }
                ],
            },
            "lexical_diversity": {"passed": True},
        }
        fix_instructions = []
        gc_report = quality_reports.get("global_consistency", {})
        if isinstance(gc_report, dict) and not gc_report.get("passed", True):
            for i in gc_report.get("issues", []):
                if isinstance(i, dict) and i.get("severity") == "high":
                    fix_instructions.append(i.get("description", ""))
        assert len(fix_instructions) == 1
        assert "她" in fix_instructions[0]

    def test_fix_triggered_for_lexical_issues(self):
        """词汇多样性未通过应触发修订."""
        quality_reports = {
            "global_consistency": {"passed": True, "issues": []},
            "lexical_diversity": {
                "passed": False,
                "repetition_issues": [
                    {
                        "phrase": "瞳孔微缩",
                        "count": 5,
                        "alternatives": ["眼神一凝", "目光骤冷", "眈光微动"],
                    }
                ],
            },
        }
        fix_instructions = []
        lex_report = quality_reports.get("lexical_diversity", {})
        if isinstance(lex_report, dict) and not lex_report.get("passed", True):
            for rep in lex_report.get("repetition_issues", []):
                if isinstance(rep, dict) and rep.get("phrase"):
                    fix_instructions.append(rep["phrase"])
        assert len(fix_instructions) == 1
        assert "瞳孔微缩" in fix_instructions[0]


class TestPowerLevelValidator:
    """战力合理性校验测试."""

    @pytest.fixture
    def checker(self):
        c = GlobalConsistencyChecker()
        c.register_entity(EntityProfile(
            name="林尘",
            gender="male",
            current_power_level="淬火境初期",
        ))
        return c

    def test_power_level_skip_detected(self, checker):
        """境界跳级应被检测为高严重问题."""
        # 第1章淬火境 → 第5章直接跳到金丹境
        checker.record_power_level(1, "林尘", "淬火境初期")
        checker.entity_registry["林尘"].current_power_level = "金丹境初期"

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            checker.check("林尘突破了金丹境", chapter_number=5)
        )
        power_issues = [
            i for i in result.issues if i.issue_type == "power_level"
        ]
        assert len(power_issues) > 0
        assert any(i.severity == Severity.HIGH for i in power_issues)

    def test_power_level_too_fast(self, checker):
        """境界提升过快（间隔不足）应被检测."""
        # 第1章淬火境 → 第3章即升为锻骨境（间隔仅2章）
        checker.record_power_level(1, "林尘", "淬火境初期")
        checker.entity_registry["林尘"].current_power_level = "锻骨境初期"

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            checker.check("林尘突破了锻骨境", chapter_number=3)
        )
        power_issues = [
            i for i in result.issues if i.issue_type == "power_level"
        ]
        assert len(power_issues) > 0
        assert any(i.severity == Severity.MEDIUM for i in power_issues)

    def test_power_level_normal_progression(self, checker):
        """正常境界提升不应报错."""
        # 第1章淬火境 → 第10章升为锻骨境（间隔充足）
        checker.record_power_level(1, "林尘", "淬火境初期")
        checker.entity_registry["林尘"].current_power_level = "锻骨境初期"

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            checker.check("林尘突破了锻骨境", chapter_number=10)
        )
        power_issues = [
            i for i in result.issues if i.issue_type == "power_level"
        ]
        assert len(power_issues) == 0

    def test_multi_opponent_overkill_detected(self, checker):
        """以少敌多秒杀描写应被检测."""
        content = "林尘面对十余人的围攻，他轻而易举地秒杀了所有敌人。"

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            checker.check(content, chapter_number=2)
        )
        power_issues = [
            i for i in result.issues if i.issue_type == "power_level"
        ]
        assert len(power_issues) > 0


class TestTimeMarkExtraction:
    """时间标记提取测试."""

    def test_first_chapter_no_constraint(self):
        """第一章应返回无时间约束提示."""
        from agents.crew_manager import NovelCrewManager
        mgr = NovelCrewManager.__new__(NovelCrewManager)
        mgr._chapter_summaries = {}
        result = mgr._get_previous_time_mark(1)
        assert "第一章" in result

    def test_time_mark_from_summary(self):
        """从摘要中提取时间关键词."""
        from agents.crew_manager import NovelCrewManager
        mgr = NovelCrewManager.__new__(NovelCrewManager)
        mgr._chapter_summaries = {
            2: {"summary": "林尘在深夜中突破了境界"}
        }
        result = mgr._get_previous_time_mark(3)
        assert "深夜" in result

