"""LexicalDiversityChecker - 词汇多样性检测器.

检测章节之间的词汇重复和句式模板化，提供同义词替换建议。
在 Editor 审查中作为自动化检查项运行。

解决根本问题：
- "瞳孔微缩"出现8次
- "指节泛白"出现5次
- 句式"林萧XX，目光XX"高度模板化
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logging_config import logger


@dataclass
class RepetitionIssue:
    """重复问题."""

    phrase: str
    total_count: int  # 在当前检查窗口内的总出现次数
    threshold: int  # 触发阈值
    chapter_counts: Dict[int, int]  # {章节号: 出现次数}
    suggestion: str
    alternatives: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phrase": self.phrase,
            "total_count": self.total_count,
            "threshold": self.threshold,
            "chapter_counts": self.chapter_counts,
            "suggestion": self.suggestion,
            "alternatives": self.alternatives,
        }


@dataclass
class PatternIssue:
    """句式模板问题."""

    pattern: str
    pattern_name: str
    examples: List[str]  # 发现的具体例句
    count: int
    suggestion: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern,
            "pattern_name": self.pattern_name,
            "example_count": len(self.examples),
            "examples": self.examples[:3],
            "total_count": self.count,
            "suggestion": self.suggestion,
        }


@dataclass
class LexicalDiversityReport:
    """词汇多样性报告."""

    chapter_number: int
    diversity_score: float = 10.0  # 0-10，越高越好
    repetition_issues: List[RepetitionIssue] = field(default_factory=list)
    pattern_issues: List[PatternIssue] = field(default_factory=list)
    unique_word_ratio: float = 0.0  # 独特词/总词比
    issue_count: int = 0

    @property
    def passed(self) -> bool:
        return self.diversity_score >= 6.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_number": self.chapter_number,
            "diversity_score": round(self.diversity_score, 2),
            "passed": self.passed,
            "unique_word_ratio": round(self.unique_word_ratio, 3),
            "repetition_count": len(self.repetition_issues),
            "pattern_count": len(self.pattern_issues),
            "repetition_issues": [i.to_dict() for i in self.repetition_issues],
            "pattern_issues": [i.to_dict() for i in self.pattern_issues],
        }


class LexicalDiversityChecker:
    """词汇多样性检测器.

    功能：
    1. 短语频率分析 - 检测高频短语重复
    2. 句式模式检测 - 检测固定句式模板
    3. 同义词建议 - 提供替换方案
    4. 多样性评分 - 计算词汇多样性分数
    """

    # 高频词黑名单及替代方案（基于质量分析报告提取）
    PHRASE_BLACKLIST: Dict[str, Dict[str, Any]] = {
        "瞳孔微缩": {
            "threshold": 2,
            "window_chapters": 10,
            "alternatives": ["眼神一凝", "目光骤冷", "眸光微动", "双目微眯", "眼底掠过一丝冷光"],
        },
        "指节泛白": {
            "threshold": 2,
            "window_chapters": 10,
            "alternatives": ["手指攥紧", "握拳用力", "骨节微微绷紧", "拳头不自觉地收紧"],
        },
        "摇摇欲坠": {
            "threshold": 1,
            "window_chapters": 10,
            "alternatives": ["吱呀作响", "斑驳破旧", "岌岌可危", "破败不堪"],
        },
        "古井": {
            "threshold": 2,
            "window_chapters": 10,
            "alternatives": ["深潭", "寒星", "幽暗的眼眸", "深邃的目光"],
            "context_check": True,  # 需要检查上下文是否用于形容眼神
        },
        "拉风箱": {
            "threshold": 2,
            "window_chapters": 10,
            "alternatives": ["粗重的喘息", "气息急促", "呼吸粗重", "喘息声此起彼伏"],
        },
        "不容置疑": {
            "threshold": 2,
            "window_chapters": 10,
            "alternatives": ["斩钉截铁", "掷地有声", "毫无商量余地", "语气坚决"],
        },
        "万年寒冰": {
            "threshold": 1,
            "window_chapters": 10,
            "alternatives": ["千年玄冰", "刺骨冰寒", "冷若冰霜", "寒意透骨"],
        },
        "万年玄冰": {
            "threshold": 1,
            "window_chapters": 10,
            "alternatives": ["千年寒冰", "刺骨寒意", "冷彻骨髓", "寒彻心扉"],
        },
    }

    # 句式模板检测（正则模式）
    SENTENCE_PATTERNS: List[Dict[str, Any]] = [
        {
            "pattern": r"(.{1,4})，目光.{2,6}",
            "name": "XX，目光YY 句式",
            "threshold": 3,
            "window_chapters": 5,
            "suggestion": "变换句式结构，可用动作、心理活动或环境描写代替",
        },
        {
            "pattern": r"(.{1,4})，心中一[震动惊]",
            "name": "XX，心中一震/惊/动 句式",
            "threshold": 3,
            "window_chapters": 5,
            "suggestion": "用具体的身体反应或环境变化代替抽象的情感描述",
        },
        {
            "pattern": r"(.{1,4})，[脸面]色一[变白沉]",
            "name": "XX，面色一变/白/沉 句式",
            "threshold": 3,
            "window_chapters": 5,
            "suggestion": "用更具体的表情/动作描写代替笼统的面色变化",
        },
        {
            "pattern": r"(.{1,4})，[眼眸双]中.{1,3}闪过",
            "name": "XX，眼中闪过YY 句式",
            "threshold": 3,
            "window_chapters": 5,
            "suggestion": "变换描写方式，可用微表情或直接行为代替",
        },
        {
            "pattern": r"(.{1,4})，[冷冷冷冷地]看着",
            "name": "XX，冷冷地看着 句式",
            "threshold": 2,
            "window_chapters": 5,
            "suggestion": "用具体的行为或对话代替简单的眼神描写",
        },
    ]

    def __init__(self, window_chapters: int = 10, phrase_threshold: int = 2):
        """初始化词汇多样性检测器.

        Args:
            window_chapters: 检查的章节窗口大小
            phrase_threshold: 短语重复触发阈值
        """
        self.window_chapters = window_chapters
        self.phrase_threshold = phrase_threshold
        # 存储历史章节的词汇统计
        self._chapter_vocabulary: Dict[int, Dict[str, Any]] = {}

    def check(
        self,
        content: str,
        chapter_number: int,
        previous_chapters: Optional[Dict[int, str]] = None,
    ) -> LexicalDiversityReport:
        """执行词汇多样性检查.

        Args:
            content: 当前章节内容
            chapter_number: 当前章节号
            previous_chapters: 前序章节内容 {章节号: 内容}

        Returns:
            LexicalDiversityReport
        """
        report = LexicalDiversityReport(chapter_number=chapter_number)

        # 构建检查窗口（当前章 + 前N章）
        chapters_to_check = {chapter_number: content}
        if previous_chapters:
            sorted_prev = sorted(
                previous_chapters.items(),
                key=lambda x: x[0],
                reverse=True,
            )
            for ch_num, ch_content in sorted_prev[:self.window_chapters - 1]:
                chapters_to_check[ch_num] = ch_content

        # 1. 短语频率分析
        report.repetition_issues = self._check_phrase_repetition(chapters_to_check)

        # 2. 句式模式检测
        report.pattern_issues = self._check_sentence_patterns(content, chapter_number)

        # 3. 计算词汇多样性分数
        report.unique_word_ratio = self._calculate_unique_word_ratio(content)

        # 综合评分
        diversity_score = 10.0
        # 每个重复问题扣 1.5 分
        diversity_score -= len(report.repetition_issues) * 1.5
        # 每个句式模板问题扣 1.0 分
        diversity_score -= len(report.pattern_issues) * 1.0
        # 独特词比率低扣分
        if report.unique_word_ratio < 0.3:
            diversity_score -= 2.0
        elif report.unique_word_ratio < 0.5:
            diversity_score -= 1.0

        report.diversity_score = max(0.0, min(10.0, diversity_score))
        report.issue_count = len(report.repetition_issues) + len(report.pattern_issues)

        # 缓存当前章节词汇
        self._chapter_vocabulary[chapter_number] = {
            "content_length": len(content),
            "unique_ratio": report.unique_word_ratio,
        }

        if report.issue_count > 0:
            logger.warning(
                f"[LexicalChecker] 第{chapter_number}章发现 {report.issue_count} 个词汇问题 "
                f"(多样性评分={report.diversity_score:.1f})"
            )
        else:
            logger.info(
                f"[LexicalChecker] 第{chapter_number}章词汇多样性检查通过 "
                f"(评分={report.diversity_score:.1f}, 独特词比={report.unique_word_ratio:.2%})"
            )

        return report

    def _check_phrase_repetition(
        self, chapters: Dict[int, str]
    ) -> List[RepetitionIssue]:
        """检查短语重复.

        遍历黑名单短语，统计其在所有章节中的出现频率。
        """
        issues = []

        for phrase, config in self.PHRASE_BLACKLIST.items():
            threshold = config.get("threshold", self.phrase_threshold)
            window = config.get("window_chapters", self.window_chapters)
            alternatives = config.get("alternatives", [])
            context_check = config.get("context_check", False)

            # 只检查最近 window 章
            sorted_chapters = sorted(chapters.items(), reverse=True)[:window]

            total_count = 0
            chapter_counts = {}

            for ch_num, ch_content in sorted_chapters:
                count = ch_content.count(phrase)
                if context_check:
                    # 上下文检查：仅当用于形容眼神时计数
                    count = self._count_with_context(ch_content, phrase, "眼神")
                if count > 0:
                    chapter_counts[ch_num] = count
                    total_count += count

            if total_count >= threshold:
                alt_str = "、".join(alternatives[:5])
                issues.append(RepetitionIssue(
                    phrase=phrase,
                    total_count=total_count,
                    threshold=threshold,
                    chapter_counts=chapter_counts,
                    suggestion=f"「{phrase}」在{len(chapter_counts)}章中出现{total_count}次"
                               f"（阈值={threshold}），建议替换为：{alt_str}",
                    alternatives=alternatives,
                ))

        return issues

    def _count_with_context(
        self, content: str, phrase: str, context_keyword: str
    ) -> int:
        """带上下文检查的短语计数.

        仅当短语出现在特定上下文中时才计数。
        """
        count = 0
        idx = 0
        while True:
            pos = content.find(phrase, idx)
            if pos == -1:
                break
            # 检查前后50字是否包含上下文关键词
            context_start = max(0, pos - 50)
            context_end = min(len(content), pos + len(phrase) + 50)
            context = content[context_start:context_end]
            if context_keyword in context:
                count += 1
            idx = pos + len(phrase)
        return count

    def _check_sentence_patterns(
        self, content: str, chapter_number: int
    ) -> List[PatternIssue]:
        """检查句式模板重复.

        使用正则匹配检测固定句式。
        """
        issues = []

        for pattern_config in self.SENTENCE_PATTERNS:
            pattern = pattern_config["pattern"]
            name = pattern_config["name"]
            threshold = pattern_config["threshold"]
            suggestion = pattern_config["suggestion"]

            matches = re.findall(pattern, content)
            if len(matches) >= threshold:
                # 提取完整例句
                examples = []
                for m in re.finditer(pattern, content):
                    # 提取包含匹配的完整句子
                    start = max(0, m.start() - 5)
                    end = min(len(content), m.end() + 10)
                    sentence = content[start:end].strip()
                    if len(sentence) > 30:
                        sentence = sentence[:30] + "..."
                    examples.append(sentence)
                    if len(examples) >= 3:
                        break

                issues.append(PatternIssue(
                    pattern=pattern,
                    pattern_name=name,
                    examples=examples,
                    count=len(matches),
                    suggestion=suggestion,
                ))

        return issues

    def _calculate_unique_word_ratio(self, content: str) -> float:
        """计算独特词比率.

        独特词数 / 总词数（按中文字符估算）。
        """
        # 提取所有中文字符对（二元词）
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", content)
        if len(chinese_chars) < 2:
            return 0.0

        # 二元词（bigram）
        bigrams = set()
        for i in range(len(chinese_chars) - 1):
            bigrams.add(chinese_chars[i] + chinese_chars[i + 1])

        # 独特词比率 = 独特二元词数 / 总二元词数
        total_bigrams = len(chinese_chars) - 1
        if total_bigrams == 0:
            return 0.0

        return len(bigrams) / total_bigrams

    def generate_editor_suggestions(self, report: LexicalDiversityReport) -> List[str]:
        """生成 Editor 可用的修订建议.

        将词汇问题转换为 Editor 可直接使用的建议格式。
        """
        suggestions = []

        for issue in report.repetition_issues:
            suggestions.append(
                f"[MEDIUM] 词汇重复：「{issue.phrase}」出现{issue.total_count}次"
                f"（超过阈值{issue.threshold}）→ 建议使用：{'、'.join(issue.alternatives[:3])}"
            )

        for issue in report.pattern_issues:
            suggestions.append(
                f"[MEDIUM] 句式模板化：{issue.pattern_name} 出现{issue.count}次"
                f" → {issue.suggestion}"
            )

        return suggestions
