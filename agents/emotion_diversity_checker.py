"""EmotionDiversityChecker - 角色情感多样性检测器.

检测角色在最近N章中是否展现了足够的情感多样性。
防止主角/配角只有单一情感状态。

解决根本问题：
- 林萧6章只有"冷静"一种情绪
- 小翠全程"害怕→哭泣"
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from core.logging_config import logger

# 情感分类词典
EMOTION_CATEGORIES = {
    "冷静": ["冷静", "平静", "镇定", "沉稳", "淡然", "从容"],
    "愤怒": ["愤怒", "怒火", "暴怒", "怒火中烧", "怒不可遏", "怒极", "愤然"],
    "温柔": ["温柔", "柔和", "温存", "怜惜", "关切", "温和"],
    "幽默": ["幽默", "调侃", "玩笑", "打趣", "自嘲", "戏谑", "俏皮"],
    "悲伤": ["悲伤", "悲哀", "难过", "心痛", "心酸", "黯然", "伤感", "悲凉"],
    "恐惧": ["恐惧", "害怕", "惊恐", "惊骇", "胆寒", "心悸"],
    "坚定": ["坚定", "决然", "毅然", "果断", "坚决"],
    "犹豫": ["犹豫", "迟疑", "踌躇", "迟疑不决", "拿不定主意"],
    "喜悦": ["喜悦", "高兴", "欣喜", "欢欣", "激动", "振奋", "兴奋"],
    "警惕": ["警惕", "警觉", "戒备", "防备", "小心", "谨慎"],
    "无奈": ["无奈", "苦笑", "叹气", "叹息", "苦笑不已"],
    "轻蔑": ["轻蔑", "不屑", "鄙夷", "冷笑", "嘲讽", "讥讽"],
}

# 情感→情感大类映射
EMOTION_TO_CATEGORY: Dict[str, str] = {}
for category, keywords in EMOTION_CATEGORIES.items():
    for kw in keywords:
        EMOTION_TO_CATEGORY[kw] = category


@dataclass
class CharacterEmotionState:
    """角色情感状态记录."""

    character_name: str
    chapter_number: int
    detected_emotions: List[str]  # 检测到的情感列表
    dominant_emotion: str = ""  # 主导情感
    emotional_complexity: float = 0.0  # 情感复杂度 0-1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "character_name": self.character_name,
            "chapter_number": self.chapter_number,
            "detected_emotions": self.detected_emotions,
            "dominant_emotion": self.dominant_emotion,
            "emotional_complexity": round(self.emotional_complexity, 2),
        }


@dataclass
class EmotionDiversityReport:
    """角色情感多样性报告."""

    chapter_number: int
    character_name: str

    # 当前章情感
    current_emotions: List[str] = field(default_factory=list)
    dominant_emotion: str = ""

    # 窗口统计
    emotion_history: List[CharacterEmotionState] = field(default_factory=list)
    unique_emotions: Set[str] = field(default_factory=set)
    emotion_distribution: Dict[str, int] = field(default_factory=dict)

    # 评估结果
    diversity_score: float = 10.0  # 0-10
    passed: bool = True
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_number": self.chapter_number,
            "character_name": self.character_name,
            "current_emotions": self.current_emotions,
            "dominant_emotion": self.dominant_emotion,
            "unique_emotion_count": len(self.unique_emotions),
            "emotion_distribution": self.emotion_distribution,
            "diversity_score": round(self.diversity_score, 2),
            "passed": self.passed,
            "issues": self.issues,
            "suggestions": self.suggestions,
        }


@dataclass
class CharacterEmotionalProfile:
    """角色情感档案.

    定义角色应具备的情感范围。
    """

    name: str
    emotional_range: List[str]  # 该角色应具备的情感种类
    dominant_emotion: str = ""  # 主导情感
    forbidden_emotions: List[str] = field(default_factory=list)  # 不该出现的情感
    min_emotion_variety_per_window: int = 2  # 窗口内最少情感种类

    @classmethod
    def default_for_protagonist(cls, name: str) -> "CharacterEmotionalProfile":
        """为主角创建默认情感档案."""
        return cls(
            name=name,
            emotional_range=["冷静", "愤怒", "温柔", "幽默", "坚定", "无奈"],
            dominant_emotion="冷静",
            min_emotion_variety_per_window=3,
        )

    @classmethod
    def default_for_supporting(cls, name: str) -> "CharacterEmotionalProfile":
        """为配角创建默认情感档案."""
        return cls(
            name=name,
            emotional_range=["害怕", "勇敢", "温柔", "坚定", "悲伤"],
            min_emotion_variety_per_window=2,
        )


class EmotionDiversityChecker:
    """角色情感多样性检测器.

    功能：
    1. 从文本中检测情感表达
    2. 追踪角色情感历史
    3. 评估情感多样性
    4. 生成改进建议
    """

    def __init__(
        self,
        window_chapters: int = 3,
        min_emotion_variety: int = 2,
    ):
        """初始化情感多样性检测器.

        Args:
            window_chapters: 检查的章节窗口大小
            min_emotion_variety: 窗口内最少情感种类数
        """
        self.window_chapters = window_chapters
        self.min_emotion_variety = min_emotion_variety
        # 角色情感档案
        self._profiles: Dict[str, CharacterEmotionalProfile] = {}
        # 历史情感记录
        self._history: Dict[str, List[CharacterEmotionState]] = {}

    def register_profile(self, profile: CharacterEmotionalProfile) -> None:
        """注册角色情感档案."""
        self._profiles[profile.name] = profile
        if profile.name not in self._history:
            self._history[profile.name] = []
        logger.info(
            f"[EmotionChecker] 注册角色情感档案: {profile.name}, "
            f"情感范围: {profile.emotional_range}"
        )

    def check(
        self,
        content: str,
        character_name: str,
        chapter_number: int,
        previous_chapters: Optional[Dict[int, str]] = None,
    ) -> EmotionDiversityReport:
        """检查角色的情感多样性.

        Args:
            content: 当前章节内容
            character_name: 角色名
            chapter_number: 当前章节号
            previous_chapters: 前序章节内容

        Returns:
            EmotionDiversityReport
        """
        report = EmotionDiversityReport(
            chapter_number=chapter_number,
            character_name=character_name,
        )

        # 0. 如果有前序章节，先检测其情感（构建历史基线）
        if previous_chapters:
            for ch_num in sorted(previous_chapters.keys()):
                ch_content = previous_chapters[ch_num]
                prev_emotions = self._detect_emotions(ch_content, character_name)
                if prev_emotions:
                    emotion_counts_prev: Dict[str, int] = {}
                    for em in prev_emotions:
                        emotion_counts_prev[em] = emotion_counts_prev.get(em, 0) + 1
                    dominant_prev = max(emotion_counts_prev, key=emotion_counts_prev.get)
                    self._history.setdefault(character_name, []).append(
                        CharacterEmotionState(
                            character_name=character_name,
                            chapter_number=ch_num,
                            detected_emotions=prev_emotions,
                            dominant_emotion=dominant_prev,
                        )
                    )

        # 1. 检测当前章的情感
        current_emotions = self._detect_emotions(content, character_name)
        report.current_emotions = current_emotions
        if current_emotions:
            # 统计频率最高的情感
            emotion_counts: Dict[str, int] = {}
            for em in current_emotions:
                emotion_counts[em] = emotion_counts.get(em, 0) + 1
            report.dominant_emotion = max(emotion_counts, key=emotion_counts.get)

        # 2. 更新历史记录
        state = CharacterEmotionState(
            character_name=character_name,
            chapter_number=chapter_number,
            detected_emotions=current_emotions,
            dominant_emotion=report.dominant_emotion,
        )
        self._history.setdefault(character_name, []).append(state)

        # 3. 构建窗口内的唯一情感集合
        history = self._history.get(character_name, [])
        recent = history[-self.window_chapters:] if len(history) > self.window_chapters else history

        all_emotions = set()
        distribution: Dict[str, int] = {}
        for h in recent:
            for em in h.detected_emotions:
                all_emotions.add(em)
                distribution[em] = distribution.get(em, 0) + 1

        report.unique_emotions = all_emotions
        report.emotion_distribution = distribution

        # 4. 评估多样性
        report.diversity_score = self._calculate_diversity_score(
            current_emotions, all_emotions, distribution
        )

        # 5. 检查是否通过
        profile = self._profiles.get(character_name)
        if profile:
            min_variety = profile.min_emotion_variety_per_window
        else:
            min_variety = self.min_emotion_variety

        if len(all_emotions) < min_variety and len(recent) >= min_variety:
            report.passed = False
            report.issues.append(
                f"角色「{character_name}」在最近{len(recent)}章中仅展现了 "
                f"{len(all_emotions)} 种情感（要求≥{min_variety}种）"
            )
            # 生成建议
            if profile:
                missing = set(profile.emotional_range) - all_emotions
                if missing:
                    report.suggestions.append(
                        f"建议让{character_name}展现以下情感：{'、'.join(list(missing)[:3])}"
                    )

        # 6. 检测单一情感持续
        if len(recent) >= 2:
            recent_dominants = [h.dominant_emotion for h in recent if h.dominant_emotion]
            if len(recent_dominants) >= 2 and len(set(recent_dominants)) == 1:
                report.issues.append(
                    f"角色「{character_name}」连续{len(recent_dominants)}章主导情感均为 "
                    f"「{recent_dominants[0]}」，缺乏情感变化"
                )
                report.suggestions.append(
                    f"尝试在后续章节中展现{character_name}的其他情感层面"
                )

        logger.info(
            f"[EmotionChecker] {character_name} 第{chapter_number}章: "
            f"情感={current_emotions}, 多样性={report.diversity_score:.1f}, "
            f"通过={report.passed}"
        )

        return report

    def _detect_emotions(self, content: str, character_name: str) -> List[str]:
        """从文本中检测角色的情感表达.

        策略：在角色名字附近的窗口内搜索情感关键词。
        """
        emotions_found = []
        window_size = 80  # 角色名前后80字

        # 找到所有角色名字出现的位置
        positions = []
        start = 0
        while True:
            pos = content.find(character_name, start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + 1

        # 在每个位置附近搜索情感词
        for pos in positions:
            win_start = max(0, pos - window_size)
            win_end = min(len(content), pos + len(character_name) + window_size)
            window = content[win_start:win_end]

            for emotion_keyword, category in EMOTION_TO_CATEGORY.items():
                if emotion_keyword in window:
                    emotions_found.append(category)

        return emotions_found

    def _calculate_diversity_score(
        self,
        current_emotions: List[str],
        all_emotions: Set[str],
        distribution: Dict[str, int],
    ) -> float:
        """计算情感多样性评分 (0-10)."""
        if not current_emotions and not all_emotions:
            return 5.0  # 未检测到情感，中性评分

        score = 10.0

        # 唯一情感种类少 → 扣分
        unique_count = len(all_emotions)
        if unique_count < 2:
            score -= 4.0
        elif unique_count < 3:
            score -= 2.0
        elif unique_count < 4:
            score -= 1.0

        # 情感分布极度不均 → 扣分
        if distribution:
            max_count = max(distribution.values())
            total = sum(distribution.values())
            concentration = max_count / total if total > 0 else 0
            if concentration > 0.8:
                score -= 2.0
            elif concentration > 0.6:
                score -= 1.0

        return max(0.0, min(10.0, score))

    def build_writer_prompt(self, report: EmotionDiversityReport) -> str:
        """构建注入 Writer 提示词的情感约束文本."""
        lines = [
            f"## 角色情感要求 — {report.character_name}",
        ]

        profile = self._profiles.get(report.character_name)
        if profile:
            lines.append(f"- 角色情感范围：{'、'.join(profile.emotional_range)}")

        if report.current_emotions:
            lines.append(f"- 本章已检测情感：{'、'.join(report.current_emotions)}")

        if not report.passed:
            lines.append("- 【必须】本章需展现新的情感，避免单一情感状态")
            if report.suggestions:
                lines.append(f"- 建议：{'；'.join(report.suggestions)}")

        if profile and profile.dominant_emotion:
            lines.append(
                f"- 虽然{profile.dominant_emotion}是主导情感，但需在场景中展现其他情感"
            )

        return "\n".join(lines)
