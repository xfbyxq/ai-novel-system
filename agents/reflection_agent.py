"""反思代理 (Reflection Agent).

独立的反思模块，从审查循环的迭代历史中提取经验教训，
分为短期反思（纯 Python 规则/统计，零 LLM 开销）和长期反思（跨章节模式分析，1 次 LLM 调用）。

核心价值：
- 短期反思：每次审查循环结束后即时提取统计特征（评分趋势、停滞检测、问题分布）
- 长期反思：每 N 章做一次跨章节模式分析，识别反复出现的问题模式，生成写作建议
- 经验注入：将学到的 lessons 注入到 Writer/Reviewer/Continuity 的 prompt 中
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# 数据类
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class ReflectionConfig:
    """反思机制配置."""

    # 短期反思开关
    enable_short_term: bool = True

    # 长期反思开关
    enable_long_term: bool = True

    # 长期反思触发间隔（每 N 章分析一次）
    analysis_interval: int = 3

    # 最少需要多少章才能启动长期模式分析
    min_chapters_for_pattern: int = 3

    # 每种类型最多保留多少条活跃 lesson
    max_lessons_per_type: int = 5

    # 注入 prompt 时的字符预算
    lesson_budget_chars: int = 600

    # 长期反思 LLM 调用温度
    long_term_temperature: float = 0.3

    # 长期反思 LLM 最大 token 数
    long_term_max_tokens: int = 2048


@dataclass
class ReflectionInput:
    """反思输入数据（从审查循环结果中提取）."""

    # 审查循环类型: "chapter", "world", "character", "plot"
    loop_type: str

    # 章节编号（企划阶段可为 0）
    chapter_number: int

    # 迭代总轮数
    total_iterations: int

    # 是否在阈值内收敛
    converged: bool

    # 各轮评分序列
    score_progression: List[float] = field(default_factory=list)

    # 首轮各维度评分
    dimension_scores_first: Dict[str, float] = field(default_factory=dict)

    # 末轮各维度评分
    dimension_scores_final: Dict[str, float] = field(default_factory=dict)

    # 反复出现的问题列表（IssueTracker 的 recurring issues）
    recurring_issues: List[Dict[str, Any]] = field(default_factory=list)

    # 已解决的问题列表
    resolved_issues: List[Dict[str, Any]] = field(default_factory=list)

    # 未解决的问题列表
    unresolved_issues: List[Dict[str, Any]] = field(default_factory=list)

    # 章节类型标记（如 "opening", "climax", "normal" 等）
    chapter_type: str = "normal"


@dataclass
class ReflectionEntry:
    """单条反思记录（短期反思输出）."""

    novel_id: str
    loop_type: str
    chapter_number: int
    chapter_type: str
    total_iterations: int
    initial_score: float
    final_score: float
    converged: bool
    score_progression: List[float]
    dimension_scores_first: Dict[str, float]
    dimension_scores_final: Dict[str, float]
    issue_categories: List[str]
    recurring_issues: List[Dict[str, Any]]
    resolved_issues: List[Dict[str, Any]]
    unresolved_issues: List[Dict[str, Any]]
    effective_strategies: List[str]
    stagnation_detected: bool
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "novel_id": self.novel_id,
            "loop_type": self.loop_type,
            "chapter_number": self.chapter_number,
            "chapter_type": self.chapter_type,
            "total_iterations": self.total_iterations,
            "initial_score": self.initial_score,
            "final_score": self.final_score,
            "converged": self.converged,
            "score_progression": self.score_progression,
            "dimension_scores_first": self.dimension_scores_first,
            "dimension_scores_final": self.dimension_scores_final,
            "issue_categories": self.issue_categories,
            "recurring_issues": self.recurring_issues,
            "resolved_issues": self.resolved_issues,
            "unresolved_issues": self.unresolved_issues,
            "effective_strategies": self.effective_strategies,
            "stagnation_detected": self.stagnation_detected,
            "created_at": self.created_at,
        }


# ══════════════════════════════════════════════════════════════════════════
# ReflectionAgent 主类
# ══════════════════════════════════════════════════════════════════════════


class ReflectionAgent:
    """反思代理.

    职责：
    1. 短期反思 (reflect_on_loop): 每次审查循环结束后，零 LLM 开销地提取统计特征
    2. 长期反思 (analyze_cross_chapter_patterns): 每 N 章调用 1 次 LLM 做跨章节模式分析
    3. 经验注入 (get_lessons_for_*): 同步方法，将 lessons 格式化注入到 prompt
    4. 效果追踪 (record_lesson_effectiveness): 根据后续章节效果更新 lesson 权重
    """

    def __init__(
        self,
        client: QwenClient,
        cost_tracker: CostTracker,
        novel_id: str,
        storage,  # NovelMemoryStorage 实例
        config: Optional[ReflectionConfig] = None,
    ):
        """初始化方法."""
        self.client = client
        self.cost_tracker = cost_tracker
        self.novel_id = novel_id
        self.storage = storage
        self.config = config or ReflectionConfig()

    # ══════════════════════════════════════════════════════════════════════
    # 短期反思：纯 Python 规则/统计，零 LLM 开销
    # ══════════════════════════════════════════════════════════════════════

    async def reflect_on_loop(
        self, input_data: ReflectionInput
    ) -> Optional[ReflectionEntry]:
        """短期反思：从单次审查循环中提取统计特征.

        纯 Python 计算，不调用 LLM。提取以下信息：
        - 评分提升趋势
        - 停滞检测
        - 问题分类统计
        - 有效修订策略识别
        - 各维度改善分析

        Args:
            input_data: 审查循环的结果数据

        Returns:
            ReflectionEntry 或 None（如果短期反思被禁用）
        """
        if not self.config.enable_short_term:
            return None

        scores = input_data.score_progression
        if not scores:
            logger.warning("[ReflectionAgent] 评分序列为空，跳过短期反思")
            return None

        initial_score = scores[0]
        final_score = scores[-1]

        # 停滞检测：连续 2 轮改善 < 0.3
        stagnation_detected = self._detect_stagnation(scores)

        # 提取问题分类
        issue_categories = self._extract_issue_categories(input_data)

        # 识别有效策略
        effective_strategies = self._identify_effective_strategies(input_data, scores)

        entry = ReflectionEntry(
            novel_id=self.novel_id,
            loop_type=input_data.loop_type,
            chapter_number=input_data.chapter_number,
            chapter_type=input_data.chapter_type,
            total_iterations=input_data.total_iterations,
            initial_score=initial_score,
            final_score=final_score,
            converged=input_data.converged,
            score_progression=scores,
            dimension_scores_first=input_data.dimension_scores_first,
            dimension_scores_final=input_data.dimension_scores_final,
            issue_categories=issue_categories,
            recurring_issues=input_data.recurring_issues,
            resolved_issues=input_data.resolved_issues,
            unresolved_issues=input_data.unresolved_issues,
            effective_strategies=effective_strategies,
            stagnation_detected=stagnation_detected,
            created_at=datetime.now().isoformat(),
        )

        # 持久化到 SQLite
        try:
            self.storage.save_reflection_entry(self.novel_id, entry.to_dict())
            logger.info(
                f"[ReflectionAgent] 短期反思完成: "
                f"loop={input_data.loop_type}, ch={input_data.chapter_number}, "
                f"score={initial_score:.1f}->{final_score:.1f}, "
                f"iterations={input_data.total_iterations}, "
                f"stagnation={stagnation_detected}"
            )
        except Exception as e:
            logger.error(f"[ReflectionAgent] 保存反思记录失败: {e}")

        return entry

    # ── 短期反思内部方法 ──────────────────────────────────────

    def _detect_stagnation(self, scores: List[float]) -> bool:
        """检测评分是否出现停滞.

        规则：连续 2 轮改善 < 0.3 分
        """
        if len(scores) < 3:
            return False

        consecutive_stagnation = 0
        for i in range(1, len(scores)):
            improvement = scores[i] - scores[i - 1]
            if improvement < 0.3:
                consecutive_stagnation += 1
            else:
                consecutive_stagnation = 0
            if consecutive_stagnation >= 2:
                return True
        return False

    def _extract_issue_categories(self, input_data: ReflectionInput) -> List[str]:
        """从问题列表中提取问题分类（area 字段）."""
        categories = set()
        for issue_list in [
            input_data.recurring_issues,
            input_data.unresolved_issues,
        ]:
            for issue in issue_list:
                area = issue.get("area", "")
                if area:
                    categories.add(area)
        return sorted(categories)

    def _identify_effective_strategies(
        self, input_data: ReflectionInput, scores: List[float]
    ) -> List[str]:
        """识别有效的修订策略.

        通过分析维度分数变化识别哪些方面改善最大。
        """
        strategies = []
        first = input_data.dimension_scores_first
        final = input_data.dimension_scores_final

        if not first or not final:
            return strategies

        # 找出改善最大的维度
        improvements = {}
        for dim in first:
            if dim in final:
                delta = final[dim] - first[dim]
                if delta > 0.5:
                    improvements[dim] = delta

        # 按改善幅度排序，取 top 3
        sorted_dims = sorted(improvements.items(), key=lambda x: x[1], reverse=True)
        for dim, delta in sorted_dims[:3]:
            strategies.append(f"{dim}维度改善显著(+{delta:.1f})")

        # 检查已解决的问题数量
        resolved_count = len(input_data.resolved_issues)
        if resolved_count > 0:
            strategies.append(f"成功解决{resolved_count}个问题")

        # 检查收敛速度
        if input_data.converged and input_data.total_iterations <= 2:
            strategies.append("快速收敛(<=2轮)")

        return strategies

    # ══════════════════════════════════════════════════════════════════════
    # 长期反思：每 N 章调用 1 次 LLM 做跨章节模式分析
    # ══════════════════════════════════════════════════════════════════════

    async def analyze_cross_chapter_patterns(self, current_chapter: int) -> bool:
        """长期反思：跨章节模式分析.

        每 N 章触发一次（由 config.analysis_interval 控制）。
        聚合近期的 reflection_entries，调用 1 次 LLM 识别写作模式，
        生成 patterns 和 lessons 并持久化。

        Args:
            current_chapter: 当前已完成的章节编号

        Returns:
            是否成功执行了分析
        """
        if not self.config.enable_long_term:
            return False

        # 检查是否达到触发条件
        if current_chapter < self.config.min_chapters_for_pattern:
            logger.debug(
                f"[ReflectionAgent] 章节数不足({current_chapter} < "
                f"{self.config.min_chapters_for_pattern})，跳过长期反思"
            )
            return False

        if current_chapter % self.config.analysis_interval != 0:
            return False

        # 获取历史反思记录
        try:
            entries = self.storage.get_reflection_entries(
                self.novel_id, loop_type="chapter"
            )
        except Exception as e:
            logger.error(f"[ReflectionAgent] 读取反思记录失败: {e}")
            return False

        if len(entries) < self.config.min_chapters_for_pattern:
            logger.debug(
                f"[ReflectionAgent] 反思记录不足({len(entries)} < "
                f"{self.config.min_chapters_for_pattern})，跳过长期反思"
            )
            return False

        # 构建 LLM 分析的输入摘要
        analysis_input = self._build_analysis_summary(entries)

        # 获取现有的 patterns 和 lessons 以避免重复
        existing_patterns = self.storage.get_active_patterns(self.novel_id)
        existing_lessons = self.storage.get_applicable_lessons(
            self.novel_id, lesson_type="writer"
        )
        existing_lessons += self.storage.get_applicable_lessons(
            self.novel_id, lesson_type="reviewer"
        )
        existing_lessons += self.storage.get_applicable_lessons(
            self.novel_id, lesson_type="continuity"
        )

        # 调用 LLM 进行模式分析
        try:
            result = await self._call_llm_for_pattern_analysis(
                analysis_input, existing_patterns, existing_lessons
            )
        except Exception as e:
            logger.error(f"[ReflectionAgent] LLM 模式分析失败: {e}")
            return False

        # 持久化分析结果
        self._save_analysis_results(result, current_chapter)

        logger.info(
            f"[ReflectionAgent] 长期反思完成: chapter={current_chapter}, "
            f"new_patterns={len(result.get('patterns', []))}, "
            f"new_lessons={len(result.get('lessons', []))}"
        )
        return True

    def _build_analysis_summary(self, entries: List[Dict[str, Any]]) -> str:
        """将历史反思记录聚合为 LLM 分析所需的文本摘要."""
        lines = ["## 最近章节审查循环统计\n"]

        for entry in entries[-10:]:  # 最多取最近 10 条
            ch = entry.get("chapter_number", "?")
            init_s = entry.get("initial_score", 0)
            final_s = entry.get("final_score", 0)
            iters = entry.get("total_iterations", 0)
            converged = entry.get("converged", False)
            stagnation = entry.get("stagnation_detected", False)
            categories = entry.get("issue_categories", [])
            if isinstance(categories, str):
                try:
                    categories = json.loads(categories)
                except (json.JSONDecodeError, TypeError):
                    categories = []

            recurring = entry.get("recurring_issues", [])
            if isinstance(recurring, str):
                try:
                    recurring = json.loads(recurring)
                except (json.JSONDecodeError, TypeError):
                    recurring = []

            unresolved = entry.get("unresolved_issues", [])
            if isinstance(unresolved, str):
                try:
                    unresolved = json.loads(unresolved)
                except (json.JSONDecodeError, TypeError):
                    unresolved = []

            line = (
                f"- 第{ch}章: 初始{init_s:.1f}->最终{final_s:.1f}, "
                f"迭代{iters}轮, {'收敛' if converged else '未收敛'}"
            )
            if stagnation:
                line += ", 出现停滞"
            if categories:
                line += f", 问题类别: {', '.join(categories[:5])}"
            if recurring:
                recurring_descs = [r.get("description", "")[:30] for r in recurring[:3]]
                line += f", 反复问题: {'; '.join(recurring_descs)}"
            if unresolved:
                unresolved_descs = [
                    u.get("description", "")[:30] for u in unresolved[:3]
                ]
                line += f", 未解决: {'; '.join(unresolved_descs)}"
            lines.append(line)

        # 聚合统计
        total = len(entries)
        converged_count = sum(1 for e in entries if e.get("converged", False))
        stagnation_count = sum(
            1 for e in entries if e.get("stagnation_detected", False)
        )
        avg_iterations = (
            sum(e.get("total_iterations", 0) for e in entries) / total
            if total > 0
            else 0
        )
        avg_improvement = 0
        for e in entries:
            avg_improvement += e.get("final_score", 0) - e.get("initial_score", 0)
        avg_improvement = avg_improvement / total if total > 0 else 0

        lines.append(f"\n## 汇总统计")
        lines.append(f"- 总章节数: {total}")
        lines.append(f"- 收敛率: {converged_count}/{total}")
        lines.append(f"- 停滞率: {stagnation_count}/{total}")
        lines.append(f"- 平均迭代轮数: {avg_iterations:.1f}")
        lines.append(f"- 平均分数提升: {avg_improvement:.1f}")

        # 问题类别频率
        category_freq: Dict[str, int] = {}
        for e in entries:
            cats = e.get("issue_categories", [])
            if isinstance(cats, str):
                try:
                    cats = json.loads(cats)
                except (json.JSONDecodeError, TypeError):
                    cats = []
            for cat in cats:
                category_freq[cat] = category_freq.get(cat, 0) + 1

        if category_freq:
            sorted_cats = sorted(
                category_freq.items(), key=lambda x: x[1], reverse=True
            )
            lines.append(f"\n## 高频问题类别")
            for cat, freq in sorted_cats[:8]:
                lines.append(f"- {cat}: 出现 {freq} 次 ({freq}/{total})")

        return "\n".join(lines)

    async def _call_llm_for_pattern_analysis(
        self,
        analysis_input: str,
        existing_patterns: List[Dict[str, Any]],
        existing_lessons: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """调用 LLM 进行跨章节模式分析."""

        existing_patterns_text = ""
        if existing_patterns:
            pattern_descs = [
                p.get("description", "")[:50] for p in existing_patterns[:5]
            ]
            existing_patterns_text = f"\n已有模式（避免重复）：\n" + "\n".join(
                f"- {d}" for d in pattern_descs
            )

        existing_lessons_text = ""
        if existing_lessons:
            lesson_descs = [l.get("rule_text", "")[:50] for l in existing_lessons[:5]]
            existing_lessons_text = f"\n已有规则（避免重复）：\n" + "\n".join(
                f"- {d}" for d in lesson_descs
            )

        system_prompt = (
            "你是一个小说写作质量分析专家。根据多章节的审查循环统计数据，"
            "识别写作中反复出现的问题模式，并生成简洁、可操作的写作建议。"
        )

        task_prompt = f"""请分析以下多章节审查循环的统计数据，识别模式并生成建议.

{analysis_input}
{existing_patterns_text}
{existing_lessons_text}

请返回 JSON 格式的分析结果：
```json
{{
  "patterns": [
    {{
      "pattern_type": "weakness|strength|trend",
      "description": "简短描述(50字内)",
      "confidence": 0.8,
      "affected_dimension": "语言流畅度|情节逻辑|角色一致性|...",
      "evidence": "支撑证据(50字内)"
    }}
  ],
  "lessons": [
    {{
      "lesson_type": "writer|reviewer|continuity",
      "rule_text": "简洁可操作的规则(80字内)",
      "reasoning": "为什么需要这条规则(50字内)",
      "priority": 1
    }}
  ]
}}
```

要求：
1. patterns 最多 5 个，只保留高置信度(>0.6)的模式
2. lessons 最多 5 个，必须简洁可操作，能直接插入写作/审查 prompt
3. 不要重复已有的模式和规则
4. lesson_type 说明：writer=给写手的建议, reviewer=给审查员的建议, continuity=给连贯性检查的建议"""

        response = await self.client.chat(
            prompt=task_prompt,
            system=system_prompt,
            temperature=self.config.long_term_temperature,
            max_tokens=self.config.long_term_max_tokens,
        )

        usage = response["usage"]
        self.cost_tracker.record(
            agent_name="ReflectionAgent",
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
        )

        # 解析 JSON 响应
        from agents.base.json_extractor import JsonExtractor

        result = JsonExtractor.extract(response["content"])
        if not result:
            logger.warning("[ReflectionAgent] LLM 响应无法解析为 JSON")
            return {"patterns": [], "lessons": []}

        return result

    def _save_analysis_results(
        self, result: Dict[str, Any], current_chapter: int
    ) -> None:
        """将分析结果持久化到 SQLite."""
        now = datetime.now().isoformat()

        # 保存 patterns
        for pattern in result.get("patterns", []):
            if pattern.get("confidence", 0) < 0.6:
                continue
            try:
                self.storage.save_pattern(
                    self.novel_id,
                    {
                        "pattern_type": pattern.get("pattern_type", "weakness"),
                        "description": pattern.get("description", ""),
                        "confidence": pattern.get("confidence", 0.7),
                        "evidence_chapters": json.dumps(
                            [current_chapter], ensure_ascii=False
                        ),
                        "affected_dimension": pattern.get("affected_dimension", ""),
                        "occurrence_count": 1,
                        "last_seen_chapter": current_chapter,
                        "status": "active",
                        "created_at": now,
                        "updated_at": now,
                    },
                )
            except Exception as e:
                logger.error(f"[ReflectionAgent] 保存 pattern 失败: {e}")

        # 保存 lessons
        for lesson in result.get("lessons", []):
            lesson_type = lesson.get("lesson_type", "writer")
            # 检查是否超出每类型上限
            existing = self.storage.get_applicable_lessons(
                self.novel_id, lesson_type=lesson_type
            )
            if len(existing) >= self.config.max_lessons_per_type:
                # 淘汰最低优先级或最低效果的 lesson
                self._evict_lowest_priority_lesson(existing)

            try:
                self.storage.save_lesson(
                    self.novel_id,
                    {
                        "lesson_type": lesson_type,
                        "rule_text": lesson.get("rule_text", ""),
                        "reasoning": lesson.get("reasoning", ""),
                        "source_pattern_id": None,
                        "applicable_chapter_types": json.dumps(
                            ["normal"], ensure_ascii=False
                        ),
                        "priority": lesson.get("priority", 1),
                        "times_applied": 0,
                        "effectiveness_score": 0.5,
                        "status": "active",
                        "created_at": now,
                        "updated_at": now,
                    },
                )
            except Exception as e:
                logger.error(f"[ReflectionAgent] 保存 lesson 失败: {e}")

    def _evict_lowest_priority_lesson(self, lessons: List[Dict[str, Any]]) -> None:
        """淘汰最低优先级或效果最差的 lesson."""
        if not lessons:
            return

        # 按 effectiveness_score 升序 + priority 升序排序
        sorted_lessons = sorted(
            lessons,
            key=lambda x: (
                x.get("effectiveness_score", 0.5),
                x.get("priority", 1),
            ),
        )
        worst = sorted_lessons[0]
        lesson_id = worst.get("id")
        if lesson_id:
            try:
                self.storage.update_lesson_effectiveness(
                    self.novel_id, lesson_id, status="deprecated"
                )
                logger.info(
                    f"[ReflectionAgent] 淘汰低效 lesson: {worst.get('rule_text', '')[:30]}"
                )
            except Exception as e:
                logger.error(f"[ReflectionAgent] 淘汰 lesson 失败: {e}")

    # ══════════════════════════════════════════════════════════════════════
    # 经验注入：同步方法，格式化 lessons 注入到 prompt
    # ══════════════════════════════════════════════════════════════════════

    def get_lessons_for_writer(self, chapter_type: str = "normal") -> str:
        """获取给 Writer 的经验建议.

        Args:
            chapter_type: 章节类型，用于筛选适用的 lessons

        Returns:
            格式化的建议文本（可直接拼接到 prompt），空字符串表示无建议
        """
        return self._format_lessons("writer", chapter_type)

    def get_lessons_for_reviewer(self, chapter_type: str = "normal") -> str:
        """获取给 Reviewer 的经验建议."""
        return self._format_lessons("reviewer", chapter_type)

    def get_lessons_for_continuity(self, chapter_type: str = "normal") -> str:
        """获取给 Continuity Checker 的经验建议."""
        return self._format_lessons("continuity", chapter_type)

    def _format_lessons(self, lesson_type: str, chapter_type: str) -> str:
        """格式化指定类型的 lessons 为 prompt 文本.

        遵循字符预算限制，返回 top N 条 lessons。
        """
        try:
            lessons = self.storage.get_applicable_lessons(
                self.novel_id, lesson_type=lesson_type
            )
        except Exception as e:
            logger.error(f"[ReflectionAgent] 读取 lessons 失败: {e}")
            return ""

        if not lessons:
            return ""

        # 按 priority 降序 + effectiveness_score 降序排序
        sorted_lessons = sorted(
            lessons,
            key=lambda x: (
                x.get("priority", 1),
                x.get("effectiveness_score", 0.5),
            ),
            reverse=True,
        )

        budget = self.config.lesson_budget_chars
        type_labels = {
            "writer": "写作经验提示",
            "reviewer": "审查经验提示",
            "continuity": "连贯性检查提示",
        }
        header = f"\n【{type_labels.get(lesson_type, '经验提示')}】\n"
        lines = [header]
        current_len = len(header)

        for i, lesson in enumerate(sorted_lessons):
            rule = lesson.get("rule_text", "")
            if not rule:
                continue
            line = f"{i + 1}. {rule}\n"
            if current_len + len(line) > budget:
                break
            lines.append(line)
            current_len += len(line)

        if len(lines) <= 1:
            return ""
        return "".join(lines)

    # ══════════════════════════════════════════════════════════════════════
    # 辅助方法
    # ══════════════════════════════════════════════════════════════════════

    def get_loop_history_summary(self, loop_type: str = "chapter") -> str:
        """获取循环历史的简要摘要（用于调试/日志）."""
        try:
            entries = self.storage.get_reflection_entries(
                self.novel_id, loop_type=loop_type
            )
        except Exception:
            return ""

        if not entries:
            return "暂无历史反思数据"

        total = len(entries)
        converged = sum(1 for e in entries if e.get("converged", False))
        avg_final = (
            sum(e.get("final_score", 0) for e in entries) / total if total > 0 else 0
        )

        return (
            f"反思历史: {total}章, 收敛率 {converged}/{total}, "
            f"平均最终分 {avg_final:.1f}"
        )

    async def record_lesson_effectiveness(
        self,
        lesson_id: str,
        chapter_number: int,
        was_effective: bool,
    ) -> None:
        """记录 lesson 的实际应用效果.

        根据应用后的审查循环结果，更新 lesson 的 effectiveness_score。
        如果连续无效，自动将其标记为 deprecated。

        Args:
            lesson_id: lesson 的 ID
            chapter_number: 应用 lesson 的章节编号
            was_effective: 本次应用是否有效
        """
        try:
            lessons = self.storage.get_applicable_lessons(
                self.novel_id, lesson_type=None
            )
            target = None
            for l in lessons:
                if l.get("id") == lesson_id:
                    target = l
                    break

            if not target:
                logger.warning(
                    f"[ReflectionAgent] 未找到 lesson {lesson_id}，跳过效果记录"
                )
                return

            times_applied = target.get("times_applied", 0) + 1
            old_score = target.get("effectiveness_score", 0.5)

            # 指数移动平均更新效果分数
            alpha = 0.3
            new_effect = 1.0 if was_effective else 0.0
            new_score = old_score * (1 - alpha) + new_effect * alpha

            # 判断是否需要废弃
            status = "active"
            if times_applied >= 3 and new_score < 0.3:
                status = "deprecated"
                logger.info(
                    f"[ReflectionAgent] 自动废弃低效 lesson: "
                    f"{target.get('rule_text', '')[:30]} (score={new_score:.2f})"
                )

            self.storage.update_lesson_effectiveness(
                self.novel_id,
                lesson_id,
                times_applied=times_applied,
                effectiveness_score=new_score,
                status=status,
            )
        except Exception as e:
            logger.error(f"[ReflectionAgent] 记录 lesson 效果失败: {e}")
