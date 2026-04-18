"""StyleConsistencyChecker - 风格一致性检测器.

检测章节整体风格是否与设定的风格定位一致。
基于关键词和情感分析检测风格偏差。

解决根本问题：
- 简介标注"轻松幽默"，但6章正文完全是严肃复仇风格
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from core.logging_config import logger


@dataclass
class StyleReport:
    """风格一致性报告."""

    chapter_number: int
    target_style: str  # 目标风格

    # 检测结果
    detected_style: str = ""  # 检测到的风格
    style_match_score: float = 0.0  # 风格匹配度 0-1

    # 幽默元素检测
    humor_count: int = 0
    humor_examples: List[str] = field(default_factory=list)

    # 情感基调
    overall_tone: str = ""  # "严肃"/"轻松"/"悲壮"/"欢快"等
    tone_confidence: float = 0.0

    # 评估
    passed: bool = True
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_number": self.chapter_number,
            "target_style": self.target_style,
            "detected_style": self.detected_style,
            "style_match_score": round(self.style_match_score, 2),
            "humor_count": self.humor_count,
            "humor_examples": self.humor_examples[:3],
            "overall_tone": self.overall_tone,
            "passed": self.passed,
            "issues": self.issues,
            "suggestions": self.suggestions,
        }


class StyleConsistencyChecker:
    """风格一致性检测器.

    功能：
    1. 幽默元素检测
    2. 情感基调分析
    3. 风格匹配评估
    4. 生成改进建议
    """

    # 幽默关键词
    HUMOR_KEYWORDS = [
        # 自嘲
        "苦笑", "自嘲", "自娱自乐", "苦笑一声", "无奈地",
        # 调侃
        "打趣", "调侃", "揶揄", "开玩笑", "戏谑",
        # 俏皮
        "俏皮", "吐了吐舌头", "眨了眨眼", "翻了个白眼",
        # 反差
        "一本正经", "一本正经地胡说八道", "装模作样",
        # 吐槽
        "吐槽", "腹诽", "心中暗道", "暗骂",
        # 轻松语气
        "倒是", "也罢", "管他呢", "算了算了", "有意思",
        # 幽默比喻
        "像个", "活像", "宛如", "简直像",
        # 口语化
        "嘿", "嘿哟", "得了吧", "可不是嘛", "那还用说",
    ]

    # 严肃/沉重关键词
    SERIOUS_KEYWORDS = [
        "凝重", "沉重", "肃杀", "冷冽", "阴沉",
        "杀气", "杀意", "怒火", "狰狞", "狰狞",
        "冰冷", "森然", "凛然", "威压",
    ]

    # 轻松/温暖关键词
    LIGHT_KEYWORDS = [
        "温和", "柔和", "轻松", "温暖", "和煦",
        "笑容", "笑意", "微笑", "轻笑", "莞尔",
        "阳光", "明媚", "舒适", "惬意",
    ]

    # 风格特征权重
    STYLE_WEIGHTS = {
        "轻松幽默": {
            "humor_ratio": 0.4,
            "light_ratio": 0.3,
            "serious_penalty": 0.3,
        },
        "严肃正剧": {
            "humor_ratio": 0.1,
            "light_ratio": 0.2,
            "serious_ratio": 0.4,
        },
        "黑暗残酷": {
            "serious_ratio": 0.5,
            "dark_ratio": 0.3,
        },
    }

    def __init__(self, target_style: str = "轻松幽默"):
        """初始化风格一致性检测器.

        Args:
            target_style: 目标风格（从小说设定中读取）
        """
        self.target_style = target_style

    def check(self, content: str, chapter_number: int) -> StyleReport:
        """执行风格一致性检查.

        Args:
            content: 章节内容
            chapter_number: 章节号

        Returns:
            StyleReport
        """
        report = StyleReport(
            chapter_number=chapter_number,
            target_style=self.target_style,
        )

        # 1. 幽默元素检测
        report.humor_count, report.humor_examples = self._detect_humor(content)

        # 2. 情感基调分析
        report.overall_tone, report.tone_confidence = self._analyze_tone(content)

        # 3. 风格匹配评分
        report.style_match_score = self._calculate_style_match(content)
        report.detected_style = self._classify_style(content)

        # 4. 评估是否通过
        report.passed = self._evaluate(report)

        # 5. 生成建议
        if not report.passed:
            report.issues, report.suggestions = self._generate_feedback(report)

        logger.info(
            f"[StyleChecker] 第{chapter_number}章: "
            f"风格={report.detected_style}, "
            f"匹配度={report.style_match_score:.1%}, "
            f"幽默元素={report.humor_count}个, "
            f"通过={report.passed}"
        )

        return report

    def _detect_humor(self, content: str) -> Tuple[int, List[str]]:
        """检测幽默元素数量.

        Returns:
            (幽默元素数量, 幽默元素例句)
        """
        count = 0
        examples = []

        for keyword in self.HUMOR_KEYWORDS:
            # 使用正则匹配，确保是完整词语
            pattern = re.compile(re.escape(keyword))
            matches = list(pattern.finditer(content))
            for m in matches:
                count += 1
                # 提取例句（包含上下文）
                start = max(0, m.start() - 20)
                end = min(len(content), m.end() + 20)
                example = content[start:end].strip()
                if len(example) > 40:
                    example = example[:40] + "..."
                examples.append(f"「{keyword}」: ...{example}...")

        return count, examples[:5]

    def _analyze_tone(self, content: str) -> Tuple[str, float]:
        """分析整体情感基调.

        Returns:
            (基调描述, 置信度)
        """
        serious_count = 0
        light_count = 0

        for kw in self.SERIOUS_KEYWORDS:
            serious_count += content.count(kw)

        for kw in self.LIGHT_KEYWORDS:
            light_count += content.count(kw)

        total = serious_count + light_count
        if total == 0:
            return "中性", 0.0

        if light_count > serious_count * 1.5:
            return "轻松", light_count / total
        elif serious_count > light_count * 1.5:
            return "严肃", serious_count / total
        else:
            return "混合", max(light_count, serious_count) / total

    def _calculate_style_match(self, content: str) -> float:
        """计算风格匹配度.

        Returns:
            匹配度 0-1
        """
        # 风格权重通过 self.STYLE_WEIGHTS 直接使用

        # 幽默比例
        humor_count, _ = self._detect_humor(content)
        total_words = len(content) / 100  # 每100字为一个单位
        humor_ratio = humor_count / max(total_words, 1)

        # 轻松词比例
        light_count = sum(content.count(kw) for kw in self.LIGHT_KEYWORDS)
        light_ratio = light_count / max(total_words, 1)

        # 严肃词比例
        serious_count = sum(content.count(kw) for kw in self.SERIOUS_KEYWORDS)
        serious_ratio = serious_count / max(total_words, 1)

        score = 0.0
        if self.target_style == "轻松幽默":
            # 轻松幽默风格：高幽默+高轻松+低严肃
            humor_score = min(1.0, humor_ratio * 5)  # 每100字0.2个幽默词满分
            light_score = min(1.0, light_ratio * 3)
            serious_penalty = max(0.0, 1.0 - serious_ratio * 3)
            score = (
                humor_score * 0.5
                + light_score * 0.3
                + serious_penalty * 0.2
            )
        elif self.target_style == "严肃正剧":
            serious_score = min(1.0, serious_ratio * 2)
            score = serious_score * 0.6 + 0.4  # 基础分

        return min(1.0, max(0.0, score))

    def _classify_style(self, content: str) -> str:
        """分类检测到的风格."""
        humor_count, _ = self._detect_humor(content)
        serious_count = sum(content.count(kw) for kw in self.SERIOUS_KEYWORDS)
        light_count = sum(content.count(kw) for kw in self.LIGHT_KEYWORDS)

        if humor_count >= 5 and light_count > serious_count:
            return "轻松幽默"
        elif humor_count >= 3:
            return "偏轻松"
        elif serious_count > light_count * 2:
            return "严肃沉重"
        elif serious_count > light_count:
            return "偏严肃"
        else:
            return "中性"

    def _evaluate(self, report: StyleReport) -> bool:
        """评估是否通过风格检查."""
        if self.target_style == "轻松幽默":
            # 轻松幽默风格的要求
            if report.humor_count == 0:
                return False
            if report.style_match_score < 0.3:
                return False
        return True

    def _generate_feedback(
        self, report: StyleReport
    ) -> Tuple[List[str], List[str]]:
        """生成风格问题的反馈和建议."""
        issues = []
        suggestions = []

        if report.humor_count == 0:
            issues.append("本章未检测到任何幽默元素")
            suggestions.append(
                "建议增加至少1处幽默元素，如：主角内心自嘲、配角俏皮对话、"
                "反差式描写（如严肃场景中突然的日常吐槽）"
            )
        elif report.humor_count < 2:
            issues.append(f"本章仅检测到{report.humor_count}处幽默元素，偏少")
            suggestions.append("可适当增加幽默元素，丰富阅读体验")

        if report.style_match_score < 0.3:
            issues.append(f"风格匹配度仅{report.style_match_score:.0%}，严重偏离目标风格「{self.target_style}」")
            suggestions.append(
                "当前章节风格偏向严肃，建议：\n"
                "  1. 在对话中加入角色的俏皮回应或打趣\n"
                "  2. 在主角内心独白中加入自嘲或吐槽\n"
                "  3. 严肃场景中可穿插角色的日常小动作来调节气氛"
            )

        return issues, suggestions

    def build_writer_prompt(self, report: StyleReport) -> str:
        """构建注入 Writer 提示词的风格约束文本."""
        lines = [
            f"## 风格定位要求 — {self.target_style}",
            f"- 目标风格：{self.target_style}",
            f"- 本章检测：{report.humor_count}个幽默元素，风格={report.detected_style}",
        ]

        if not report.passed:
            lines.append("- 【必须】本章需增加幽默元素，使风格更贴合定位")
            lines.extend([f"- {s}" for s in report.suggestions])

        lines.append("")
        lines.append("【幽默技法参考】")
        lines.append("- 自嘲：主角对自身处境的调侃（如：'重生回来还是这么穷，真是'）")
        lines.append("- 吐槽：主角对不合理现象的内心吐槽")
        lines.append("- 反差：严肃场景中突然的日常元素（如：大战前突然关心晚饭吃什么）")
        lines.append("- 配角诙谐：配角有独特的说话方式或行为习惯")

        return "\n".join(lines)
