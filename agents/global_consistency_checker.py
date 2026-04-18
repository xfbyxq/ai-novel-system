"""GlobalConsistencyChecker - 全局一致性检查器.

在章节生成后、入库前执行确定性规则检查，不依赖 LLM。
检测角色名字、性别代词、时间线、战力、关键事实等一致性问题。

解决根本问题：
- 主角名字不一致（林尘 vs 林萧）
- 性别代词错误（她 vs 他）
- 时间线回退
- 战力膨胀过快
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from core.logging_config import logger


class Severity(str, Enum):
    """问题严重程度."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ConsistencyIssue:
    """一致性问题."""

    issue_type: str  # name/pronoun/timeline/power/fact
    description: str
    severity: Severity
    suggestion: str
    location: str = ""  # 问题所在文本位置描述
    found_text: str = ""  # 发现问题的原文片段

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_type": self.issue_type,
            "description": self.description,
            "severity": self.severity.value,
            "suggestion": self.suggestion,
            "location": self.location,
            "found_text": self.found_text,
        }


@dataclass
class EntityProfile:
    """实体档案 - 用于一致性校验的标准化信息."""

    name: str  # 标准名称
    gender: str = "unknown"  # male / female / unknown
    aliases: List[str] = field(default_factory=list)  # 允许的别名/昵称/简称
    current_power_level: str = ""  # 当前境界/等级
    current_location: str = ""  # 当前位置
    is_alive: bool = True  # 是否存活
    items_owned: List[str] = field(default_factory=list)  # 持有的物品
    relationships: Dict[str, str] = field(default_factory=dict)  # 与其他角色的关系

    @property
    def all_names(self) -> List[str]:
        """获取所有可接受的名称（标准名+别名）."""
        return [self.name] + self.aliases

    def pronouns_for(self) -> Tuple[str, str]:
        """返回该实体对应的正确代词 (主格, 宾格)."""
        if self.gender == "male":
            return "他", "他"
        elif self.gender == "female":
            return "她", "她"
        return "", ""


@dataclass
class ConsistencyCheckResult:
    """一致性检查结果."""

    chapter_number: int
    passed: bool = True
    issues: List[ConsistencyIssue] = field(default_factory=list)
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    @property
    def overall_score(self) -> float:
        """计算一致性评分 (0-10)."""
        if not self.issues:
            return 10.0
        penalty = (
            self.high_count * 3.0
            + self.medium_count * 1.5
            + self.low_count * 0.5
        )
        return max(0.0, 10.0 - penalty)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_number": self.chapter_number,
            "passed": self.passed,
            "overall_score": round(self.overall_score, 2),
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "issues": [i.to_dict() for i in self.issues],
        }

    def build_fix_prompt(self) -> str:
        """生成修复指令提示词."""
        lines = [
            "检测到以下一致性问题，请修正：",
            "",
        ]
        for issue in sorted(self.issues, key=lambda x: x.severity.value):
            severity_map = {"high": "【必须修复】", "medium": "【建议修复】", "low": "【可选优化】"}
            prefix = severity_map.get(issue.severity.value, "")
            lines.append(f"- {prefix} {issue.description}")
            if issue.found_text:
                lines.append(f"  原文片段：「{issue.found_text}」")
            if issue.suggestion:
                lines.append(f"  修复建议：{issue.suggestion}")
            lines.append("")

        lines.append("请输出修正后的完整章节内容。")
        return "\n".join(lines)


class GlobalConsistencyChecker:
    """全局一致性检查器.

    在 Editor 审查后、入库前运行，使用确定性规则（正则/关键词匹配）
    检测以下几类问题：

    1. 名字一致性：角色名称与设定档对比
    2. 代词一致性：基于角色性别检测代词使用
    3. 时间线：检测时间回退
    4. 战力合理性：检测战力超出合理范围
    5. 事实一致性：已死亡角色复活、已毁物品重现等
    """

    # 中文代词模式
    PRONOUN_PATTERNS = {
        "male": re.compile(r"他[的们]?|他的|他们"),
        "female": re.compile(r"她[的们]?|她的|她们"),
    }

    # 中文姓名模式（2-4个汉字，排除常见非人名词）
    CHINESE_NAME_PATTERN = re.compile(
        r"[\u4e00-\u9fa5]{2,4}"
    )

    def __init__(self):
        self.entity_registry: Dict[str, EntityProfile] = {}
        self.dead_characters: Set[str] = set()
        self.destroyed_items: Set[str] = set()
        self.chapter_timeline: Dict[int, str] = {}  # {chapter_number: time_mark}
        self.chapter_power_levels: Dict[int, Dict[str, str]] = {}  # {chapter: {char: level}}

    def register_entity(self, entity: EntityProfile) -> None:
        """注册实体到注册表."""
        self.entity_registry[entity.name] = entity
        # 同时注册别名
        for alias in entity.aliases:
            self.entity_registry[alias] = entity
        logger.info(f"[GlobalChecker] 注册实体: {entity.name} (性别={entity.gender})")

    def register_dead_character(self, name: str) -> None:
        """标记角色为已死亡."""
        self.dead_characters.add(name)
        logger.info(f"[GlobalChecker] 标记已死亡角色: {name}")

    def register_destroyed_item(self, name: str) -> None:
        """标记物品为已毁坏."""
        self.destroyed_items.add(name)
        logger.info(f"[GlobalChecker] 标记已毁坏物品: {name}")

    def record_timeline(self, chapter_number: int, time_mark: str) -> None:
        """记录章节时间标记."""
        self.chapter_timeline[chapter_number] = time_mark

    def record_power_level(self, chapter_number: int, character: str, level: str) -> None:
        """记录角色在某章的战力等级."""
        if chapter_number not in self.chapter_power_levels:
            self.chapter_power_levels[chapter_number] = {}
        self.chapter_power_levels[chapter_number][character] = level

    async def check(
        self,
        content: str,
        chapter_number: int,
        entity_registry: Optional[Dict[str, EntityProfile]] = None,
        timeline_state: Optional[Dict[int, str]] = None,
        power_level_state: Optional[Dict[int, Dict[str, str]]] = None,
    ) -> ConsistencyCheckResult:
        """执行一致性检查.

        Args:
            content: 章节内容
            chapter_number: 章节号
            entity_registry: 实体注册表（可选，不传则使用内置）
            timeline_state: 时间线状态（可选）
            power_level_state: 战力状态（可选）

        Returns:
            ConsistencyCheckResult
        """
        if entity_registry:
            self.entity_registry = entity_registry
        if timeline_state:
            self.chapter_timeline.update(timeline_state)
        if power_level_state:
            self.chapter_power_levels.update(power_level_state)

        result = ConsistencyCheckResult(chapter_number=chapter_number)

        # 1. 名字一致性检查
        name_issues = self._check_name_consistency(content)
        result.issues.extend(name_issues)

        # 2. 代词一致性检查
        pronoun_issues = self._check_pronoun_consistency(content)
        result.issues.extend(pronoun_issues)

        # 3. 时间线检查
        timeline_issues = self._check_timeline_consistency(chapter_number, content)
        result.issues.extend(timeline_issues)

        # 4. 事实一致性检查（死亡角色/毁坏物品）
        fact_issues = self._check_fact_consistency(content)
        result.issues.extend(fact_issues)

        # 5. 战力合理性检查
        power_issues = self._check_power_level_consistency(
            content, chapter_number
        )
        result.issues.extend(power_issues)

        # 统计严重程度
        result.high_count = sum(1 for i in result.issues if i.severity == Severity.HIGH)
        result.medium_count = sum(1 for i in result.issues if i.severity == Severity.MEDIUM)
        result.low_count = sum(1 for i in result.issues if i.severity == Severity.LOW)

        result.passed = result.high_count == 0

        if result.issues:
            logger.warning(
                f"[GlobalChecker] 第{chapter_number}章发现 {len(result.issues)} 个一致性问题 "
                f"(高={result.high_count}, 中={result.medium_count}, 低={result.low_count})"
            )
        else:
            logger.info(f"[GlobalChecker] 第{chapter_number}章一致性检查通过")

        return result

    # ══════════════════════════════════════════════════════════════════════════
    # 名字一致性检查
    # ══════════════════════════════════════════════════════════════════════════

    def _check_name_consistency(self, content: str) -> List[ConsistencyIssue]:
        """检查角色名称一致性.

        检测标准名和别名是否正确使用，排除未注册的"相似名"。
        """
        issues = []
        if not self.entity_registry:
            return issues

        # 提取所有出现在文本中的已知角色名
        found_names: Dict[str, List[str]] = {}  # {standard_name: [found_variants]}
        for name, profile in self.entity_registry.items():
            if name == profile.name:  # 只处理标准名
                found_variants = []
                for variant in profile.all_names:
                    if variant in content:
                        found_variants.append(variant)
                if found_variants:
                    found_names[profile.name] = found_variants

        # 检测是否有"相似但未注册"的名字（疑似拼写错误）
        # 使用模糊匹配检测 2-4 字中文名
        all_known_names = set()
        for profile in self.entity_registry.values():
            if profile.name == profile.name:  # standard
                all_known_names.add(profile.name)
                all_known_names.update(profile.aliases)

        # 简单模糊检测：检查是否存在与已知名只差1个字的变体
        suspicious_names = self._find_similar_names(content, list(all_known_names))
        for suspicious in suspicious_names:
            issues.append(ConsistencyIssue(
                issue_type="name_mismatch",
                description=f"发现疑似角色名拼写错误：「{suspicious}」",
                severity=Severity.HIGH,
                suggestion="请确认是否应使用已注册的角色名",
                found_text=suspicious,
            ))

        return issues

    def _find_similar_names(
        self, content: str, known_names: List[str]
    ) -> List[str]:
        """查找与已知名相似但未注册的中文名.

        使用简单策略：提取 2-4 字中文名，检查是否与已知名有共同字但不同。
        """
        suspicious = []
        # 已知名的单字集合
        known_chars = set()
        for name in known_names:
            known_chars.update(name)

        # 提取文本中的2-4字候选名（排除已知名）
        candidates = set(self.CHINESE_NAME_PATTERN.findall(content))
        # 过滤：至少2个字符在已知字符集中，且不在已知名列表中
        for candidate in candidates:
            if candidate in known_names:
                continue
            if len(candidate) < 2 or len(candidate) > 4:
                continue
            # 检查是否与某个已知名有大部分字符重叠
            for known in known_names:
                if len(known) != len(candidate):
                    continue
                overlap = sum(1 for c in candidate if c in known)
                # 如果超过一半字符相同但名字不同，可能是拼写错误
                if overlap >= len(known) // 2 + 1 and candidate not in known_names:
                    # 确认不在任何实体的别名中
                    is_known_alias = False
                    for profile in self.entity_registry.values():
                        if candidate in profile.aliases:
                            is_known_alias = True
                            break
                    if not is_known_alias and candidate not in suspicious:
                        suspicious.append(candidate)

        return suspicious

    # ══════════════════════════════════════════════════════════════════════════
    # 代词一致性检查
    # ══════════════════════════════════════════════════════════════════════════

    def _check_pronoun_consistency(self, content: str) -> List[ConsistencyIssue]:
        """检查代词使用是否与角色性别一致.

        策略：按段落分割，在段落范围内检查代词与角色性别匹配。
        当段落中只有一种性别的角色出现时，所有代词应与该性别匹配。
        """
        issues = []

        # 构建性别映射
        male_chars = []
        female_chars = []
        for profile in self.entity_registry.values():
            if profile.name == profile.name:  # standard name
                if profile.gender == "male":
                    male_chars.append(profile.name)
                elif profile.gender == "female":
                    female_chars.append(profile.name)

        if not male_chars and not female_chars:
            return issues

        # 按段落分割
        paragraphs = content.split('\n')

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 检测段落中出现的角色
            male_in_para = [c for c in male_chars if c in para]
            female_in_para = [c for c in female_chars if c in para]

            has_only_male = bool(male_in_para) and not bool(female_in_para)
            has_only_female = bool(female_in_para) and not bool(male_in_para)

            if has_only_male:
                # 段落中只有男性角色，检查是否出现"她"
                for m in re.finditer(r'她(?!们)', para):
                    # 排除引用/回忆场景
                    context = para[max(0, m.start() - 30):m.end() + 30]
                    if not self._is_in_flashback(context):
                        issues.append(ConsistencyIssue(
                            issue_type="pronoun_error",
                            description=f"段落中仅有男性角色「{male_in_para[0]}」但使用了女性代词",
                            severity=Severity.HIGH,
                            suggestion="将「她」改为「他」",
                            found_text=para[:60],
                        ))
                        break  # 每段只报告一次

            elif has_only_female:
                # 段落中只有女性角色，检查是否出现"他"（排除"他们"）
                m = re.search(r'他(?!们)', para)
                if m:
                    context = para[max(0, m.start() - 30):m.end() + 30]
                    if not self._is_in_flashback(context):
                        issues.append(ConsistencyIssue(
                            issue_type="pronoun_error",
                            description=f"段落中仅有女性角色「{female_in_para[0]}」但使用了男性代词",
                            severity=Severity.HIGH,
                            suggestion="将「他」改为「她」",
                            found_text=para[:60],
                        ))
                        break  # 每段只报告一次

        return issues

    def _find_wrong_pronouns_near_name(
        self,
        text: str,
        name: str,
        expected_gender: str,
        window: int = 30,
    ) -> List[Tuple[str, int]]:
        """在角色名附近窗口内查找错误的代词.

        Returns:
            [(错误代词文本, 位置), ...]
        """
        wrong_pronouns = []
        pos = 0
        while True:
            idx = text.find(name, pos)
            if idx == -1:
                break

            # 确定窗口范围
            win_start = max(0, idx - window)
            win_end = min(len(text), idx + len(name) + window)
            window_text = text[win_start:win_end]

            if expected_gender == "male":
                # 男性角色不应出现"她"
                for m in re.finditer(r"她", window_text):
                    wrong_pronouns.append((m.group(), win_start + m.start()))
            elif expected_gender == "female":
                # 女性角色不应出现"他"（除非是"他们"等复数）
                for m in re.finditer(r"他(?!们)", window_text):
                    wrong_pronouns.append((m.group(), win_start + m.start()))

            pos = idx + len(name)

        return wrong_pronouns

    # ══════════════════════════════════════════════════════════════════════════
    # 时间线一致性检查
    # ══════════════════════════════════════════════════════════════════════════

    def _check_timeline_consistency(
        self, chapter_number: int, content: str
    ) -> List[ConsistencyIssue]:
        """检查时间线一致性.

        检测时间回退和时间跳跃是否合理。
        """
        issues = []

        # 从内容中提取时间标记
        current_time_mark = self._extract_time_mark(content)
        if current_time_mark:
            self.record_timeline(chapter_number, current_time_mark)

        # 检查时间回退
        if chapter_number > 1:
            prev_mark = self.chapter_timeline.get(chapter_number - 1)
            if prev_mark and current_time_mark:
                prev_order = self._time_mark_to_order(prev_mark)
                curr_order = self._time_mark_to_order(current_time_mark)
                if curr_order < prev_order:
                    issues.append(ConsistencyIssue(
                        issue_type="timeline_regression",
                        description=f"第{chapter_number}章时间标记「{current_time_mark}」"
                                    f"早于第{chapter_number - 1}章的「{prev_mark}」",
                        severity=Severity.HIGH,
                        suggestion="请确认时间推进是否合理，如确认为回退需添加时间回溯说明",
                        found_text=f"上章: {prev_mark} → 本章: {current_time_mark}",
                    ))

        return issues

    def _extract_time_mark(self, content: str) -> Optional[str]:
        """从内容中提取主要时间标记.

        返回标准化的时间标记字符串。
        """
        # 尝试提取显式时间表达
        time_expressions = [
            (r"第([一二三四五六七八九十\d]+)天", "day"),
            (r"(故事第\d+天)", "story_day"),
            (r"(次日|翌日|第二天)", "next_day"),
            (r"(黎明|清晨|早晨|上午|中午|下午|傍晚|黄昏|夜晚|深夜|午夜|凌晨)", "time_of_day"),
            (r"(数?日?后|\d+天后|\d+日后)", "after"),
        ]

        for pattern, mark_type in time_expressions:
            match = re.search(pattern, content)
            if match:
                return match.group(1) if match.lastindex else match.group(0)

        return None

    def _time_mark_to_order(self, mark: str) -> int:
        """将时间标记转换为可比较的顺序值.

        值越大表示时间越晚。
        """
        day_patterns = [
            (r"第(\d+)天", lambda m: int(m.group(1)) * 100),
            (r"故事第(\d+)天", lambda m: int(m.group(1)) * 100),
            (r"(\d+)天后", lambda m: int(m.group(1)) * 100),
            (r"(\d+)日后", lambda m: int(m.group(1)) * 100),
        ]

        for pattern, extractor in day_patterns:
            match = re.search(pattern, mark)
            if match:
                return extractor(match)

        # 相对时间标记
        relative_markers = {
            "次日": 100,
            "翌日": 100,
            "第二天": 100,
        }
        for marker, order in relative_markers.items():
            if marker in mark:
                return order

        # 时段顺序
        time_order = {
            "凌晨": 1,
            "黎明": 2,
            "清晨": 3,
            "早晨": 4,
            "上午": 5,
            "中午": 6,
            "下午": 7,
            "傍晚": 8,
            "黄昏": 9,
            "夜晚": 10,
            "深夜": 11,
            "午夜": 12,
        }
        for marker, order in time_order.items():
            if marker in mark:
                return order

        return 0  # 未知标记

    # ══════════════════════════════════════════════════════════════════════════
    # 事实一致性检查
    # ══════════════════════════════════════════════════════════════════════════

    def _check_fact_consistency(self, content: str) -> List[ConsistencyIssue]:
        """检查事实一致性.

        检测已死亡角色出现、已毁坏物品重现等矛盾。
        """
        issues = []

        # 检查已死亡角色是否出现
        for dead_name in self.dead_characters:
            if dead_name in content:
                # 检查是否是回忆/ flashback（允许在回忆中出现）
                context_window = self._get_name_context(content, dead_name)
                if not self._is_in_flashback(context_window):
                    issues.append(ConsistencyIssue(
                        issue_type="fact_contradiction",
                        description=f"已死亡角色「{dead_name}」在本章出现",
                        severity=Severity.HIGH,
                        suggestion="请确认是否为回忆场景，如非回忆需删除该角色",
                        found_text=dead_name,
                    ))

        # 检查已毁坏物品是否出现
        for item_name in self.destroyed_items:
            if item_name in content:
                context_window = self._get_name_context(content, item_name)
                if not self._is_in_flashback(context_window):
                    issues.append(ConsistencyIssue(
                        issue_type="fact_contradiction",
                        description=f"已毁坏物品「{item_name}」在本章出现",
                        severity=Severity.MEDIUM,
                        suggestion="请确认是否为回忆或描述残骸",
                        found_text=item_name,
                    ))

        return issues

   # ══════════════════════════════════════════════════════════════════════════
    # 战力合理性检查
    # ══════════════════════════════════════════════════════════════════════════

    # 境界等级序列（低→高），用于判定境界提升合理性
    POWER_LEVEL_HIERARCHY = [
        "凡人", "淬体", "淬火", "锻骨", "通脉", "凝气",
        "开光", "融合", "心动", "金丹", "元婴", "化神",
        "炼虚", "合体", "大乘", "渡劫",
    ]

    # 战斗规模关键词——用于推断战斗中对手数量
    MULTI_OPPONENT_PATTERNS = [
        re.compile(r"(十余|二十|三十|数十|上百|百余)(?:人|名|个|位)"),
        re.compile(r"(一群|一伙|一队|一帮|一批)(?:人|\S{1,4})"),
    ]

    # 境界子级别关键词
    SUB_LEVEL_KEYWORDS = ["初期", "中期", "后期", "巅峰", "大圆满"]

    def _check_power_level_consistency(
        self,
        content: str,
        chapter_number: int,
        min_chapters_per_level_up: int = 5,
    ) -> List[ConsistencyIssue]:
        """检查战力合理性.

        校验规则：
        1. 境界提升间隔不得低于 min_chapters_per_level_up 章
        2. 单章中不应出现"秒杀"大量同等级对手的描述
        3. 境界不得跳级（淬体→金丹）

        Args:
            content: 章节内容
            chapter_number: 章节号
            min_chapters_per_level_up: 境界提升最小章节间隔

        Returns:
            一致性问题列表
        """
        issues: List[ConsistencyIssue] = []

        # --- 1) 检测境界提升速度 ---
        for name, profile in self.entity_registry.items():
            if name != profile.name:
                continue  # 跳过别名条目
            if not profile.current_power_level:
                continue

            current_level = profile.current_power_level
            current_base = self._extract_base_level(current_level)
            current_idx = self._level_index(current_base)
            if current_idx < 0:
                continue

            # 查找该角色最近一次境界变化的章节
            prev_chapter, prev_level = self._find_last_level_change(
                profile.name, chapter_number
            )
            if prev_level:
                prev_base = self._extract_base_level(prev_level)
                prev_idx = self._level_index(prev_base)
                if prev_idx >= 0 and current_idx > prev_idx:
                    gap = chapter_number - prev_chapter
                    # 跳级检测（跨越2个及以上大境界）
                    if current_idx - prev_idx >= 2:
                        issues.append(ConsistencyIssue(
                            issue_type="power_level",
                            description=(
                                f"角色「{profile.name}」在第{prev_chapter}章为"
                                f"「{prev_level}」，第{chapter_number}章跳到"
                                f"「{current_level}」，跨越多个大境界"
                            ),
                            severity=Severity.HIGH,
                            suggestion=(
                                "境界提升应逐级递进，"
                                "不可跳过中间境界"
                            ),
                        ))
                    # 提升过快检测
                    elif gap < min_chapters_per_level_up:
                        issues.append(ConsistencyIssue(
                            issue_type="power_level",
                            description=(
                                f"角色「{profile.name}」境界提升过快："
                                f"第{prev_chapter}章「{prev_level}」→"
                                f"第{chapter_number}章「{current_level}」，"
                                f"仅间隔{gap}章（要求>={min_chapters_per_level_up}章）"
                            ),
                            severity=Severity.MEDIUM,
                            suggestion=(
                                f"建议至少间隔{min_chapters_per_level_up}章"
                                "再进行境界突破"
                            ),
                        ))

        # --- 2) 检测以少敌多/秒杀大量对手 ---
        for pattern in self.MULTI_OPPONENT_PATTERNS:
            matches = pattern.findall(content)
            for match_text in matches:
                context = self._get_name_context(content, match_text, window=80)
                # 如果上下文包含"秒杀""一击""轻松击败"等关键词
                overkill_kw = [
                    "秒杀", "一击", "轻松击败", "瞬间解决",
                    "毫无还手之力", "轻而易举", "碾压",
                ]
                if any(kw in context for kw in overkill_kw):
                    issues.append(ConsistencyIssue(
                        issue_type="power_level",
                        description=(
                            f"检测到主角轻松击败大量对手的描述："
                            f"「{context[:60]}…」"
                        ),
                        severity=Severity.MEDIUM,
                        suggestion=(
                            "建议增加战斗难度描写，"
                            "或减少敌方人数以符合当前境界"
                        ),
                        found_text=context[:100],
                    ))
                    break  # 一章只报一次

        return issues

    def _extract_base_level(self, level_str: str) -> str:
        """从境界字符串中提取基础等级（去掉子级别如'初期'）."""
        result = level_str
        for sub in self.SUB_LEVEL_KEYWORDS:
            result = result.replace(sub, "")
        return result.strip()

    def _level_index(self, base_level: str) -> int:
        """获取境界在等级序列中的索引，未匹配返回-1."""
        for i, lvl in enumerate(self.POWER_LEVEL_HIERARCHY):
            if lvl in base_level or base_level in lvl:
                return i
        return -1

    def _find_last_level_change(
        self, character_name: str, before_chapter: int
    ) -> Tuple[int, str]:
        """查找角色在指定章节之前的最近一次境界记录.

        Returns:
            (章节号, 境界字符串)，无记录则返回 (0, "")
        """
        last_chapter = 0
        last_level = ""
        for ch_num in sorted(self.chapter_power_levels.keys()):
            if ch_num >= before_chapter:
                break
            ch_levels = self.chapter_power_levels[ch_num]
            if character_name in ch_levels:
                last_chapter = ch_num
                last_level = ch_levels[character_name]
        return last_chapter, last_level

    def _get_name_context(self, content: str, name: str, window: int = 50) -> str:
        """获取名字附近的上下文."""
        idx = content.find(name)
        if idx == -1:
            return ""
        start = max(0, idx - window)
        end = min(len(content), idx + len(name) + window)
        return content[start:end]

    def _is_in_flashback(self, context: str) -> bool:
        """判断上下文是否在回忆/闪回场景中."""
        flashback_keywords = [
            "回忆", "回想", "记得", "想起", "记忆中", "曾经",
            " flashback", "往事", "过去", "昔日", "当年", "从前",
        ]
        return any(kw in context for kw in flashback_keywords)
