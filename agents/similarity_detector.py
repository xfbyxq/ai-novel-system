"""内容相似度检测器 - 检测章节之间的内容重复.

使用多种轻量级文本相似度算法（无需外部依赖）：
1. N-gram 重叠检测
2. 关键句重复检测
3. 结构相似度检测
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.logging_config import logger


@dataclass
class SimilarityReport:
    """相似度检测报告."""

    is_duplicate: bool = False  # 是否判定为重复
    overall_similarity: float = 0.0  # 总体相似度 (0-1)
    ngram_similarity: float = 0.0  # N-gram 相似度
    sentence_overlap: float = 0.0  # 句子重叠比例
    structure_similarity: float = 0.0  # 结构相似度
    plot_similarity: float = 0.0  # 情节相似度
    duplicate_sentences: List[str] = field(default_factory=list)  # 重复句子
    plot_duplicate_reasons: List[str] = field(default_factory=list)  # 情节重复原因
    most_similar_chapter: int = 0  # 最相似的章节号

    def to_dict(self) -> dict:
        return {
            "is_duplicate": self.is_duplicate,
            "overall_similarity": round(self.overall_similarity, 3),
            "ngram_similarity": round(self.ngram_similarity, 3),
            "sentence_overlap": round(self.sentence_overlap, 3),
            "structure_similarity": round(self.structure_similarity, 3),
            "plot_similarity": round(self.plot_similarity, 3),
            "duplicate_sentences_count": len(self.duplicate_sentences),
            "plot_duplicate_reasons": self.plot_duplicate_reasons,
            "most_similar_chapter": self.most_similar_chapter,
        }


@dataclass
class PlotVector:
    """情节向量 - 章节的核心情节结构.

    用于检测情节层面的重复，而不仅仅是文字层面的重复。
    例如：相同的解谜方式、相似的对抗模式、重复的爽点设计等。
    """

    chapter_number: int = 0
    protagonist_goal: str = ""  # 主角目标
    conflict_type: str = ""  # 冲突类型：对抗/竞速/解谜/成长/探索
    obstacle_level: str = ""  # 障碍等级：高/中/低
    resolution_method: str = ""  # 解决方式：武力/智谋/妥协/逃避/意外
    outcome: str = ""  # 结果：成功/失败/部分/逆转
    emotional_arc: str = ""  # 情感弧线：上扬/下抑/波折/平缓
    key_scenes: List[str] = field(default_factory=list)  # 关键场景类型
    confidence: float = 0.0  # 提取置信度

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "chapter_number": self.chapter_number,
            "protagonist_goal": self.protagonist_goal,
            "conflict_type": self.conflict_type,
            "obstacle_level": self.obstacle_level,
            "resolution_method": self.resolution_method,
            "outcome": self.outcome,
            "emotional_arc": self.emotional_arc,
            "key_scenes": self.key_scenes,
            "confidence": self.confidence,
        }


class SimilarityDetector:
    """章节内容相似度检测器.

    用于检测新生成的章节是否与前几章存在严重内容重复。
    支持文字层面和情节层面的重复检测。
    """

    # 判定阈值
    DUPLICATE_THRESHOLD = 0.25  # 总体相似度超过 25% 判定为重复（从 0.30 降低）
    PLOT_DUPLICATE_THRESHOLD = 0.60  # 情节相似度超过 60% 判定为情节重复
    NGRAM_SIZE = 4  # N-gram 的 N 值
    MIN_SENTENCE_LENGTH = 8  # 最短有效句子长度

    # 情节模式定义 - 检测固定叙事模式重复
    PLOT_PATTERNS = {
        "battle_loop": {
            "name": "战斗循环模式",
            "steps": ["敌人来袭", "主角应对", "快速击败", "发现线索"],
            "keywords": [
                ["来袭", "闯入", "杀来", "逼近", "包围"],
                ["应对", "出手", "迎上", "闪身", "抬眼"],
                ["击败", "击杀", "击飞", "秒杀", "制服", "倒飞"],
                ["线索", "令牌", "铁片", "玉简", "印记", "发现"],
            ],
        },
        "training_upgrade": {
            "name": "修炼升级模式",
            "steps": ["开始修炼", "遇到困难", "突破瓶颈", "实力提升"],
            "keywords": [
                ["修炼", "打坐", "闭目", "运转", "功法"],
                ["阻碍", "不通", "难以", "瓶颈", "停滞"],
                ["突破", "松动", "涌入", "贯通", "顿悟"],
                ["提升", "进阶", "突破", "淬炼", "蜕变"],
            ],
        },
    }

    # LLM 情节向量提取提示词模板
    PLOT_VECTOR_LLM_PROMPT = """你是一个小说情节分析专家。请从以下章节内容中提取情节向量。

【提取规则】
1. 冲突类型：从"对抗/竞速/解谜/成长/探索/日常/悬疑"中选择最匹配的一个
2. 解决方式：从"武力/智谋/妥协/逃避/意外/协商"中选择最匹配的一个
3. 障碍等级：从"高/中/低"中选择一个
4. 结果：从"成功/失败/逆转/部分/悬念"中选择一个
5. 情感弧线：从"上扬/下抑/波折/平缓"中选择一个
6. 关键场景：从"战斗/修炼/谈判/探险/情感/日常/会议/发现"中选择最多3个

【章节内容】
{content}

请以JSON格式输出，不要输出其他内容：
{{
    "protagonist_goal": "主角在本章的核心目标（10字以内）",
    "conflict_type": "冲突类型",
    "obstacle_level": "障碍等级",
    "resolution_method": "解决方式",
    "outcome": "结果",
    "emotional_arc": "情感弧线",
    "key_scenes": ["场景1", "场景2"],
    "confidence": 0.8
}}"""

    # 权重配置
    WEIGHTS = {
        "ngram": 0.20,
        "sentence": 0.30,
        "structure": 0.15,
        "plot": 0.35,
    }

    def __init__(
        self,
        duplicate_threshold: float = 0.30,
        compare_chapters: int = 3,
        enable_plot_detection: bool = True,
        llm_client=None,
        cost_tracker=None,
    ):
        """
        Args:
            duplicate_threshold: 重复判定阈值 (0-1)
            compare_chapters: 向前比较的章节数
            enable_plot_detection: 是否启用情节重复检测
            llm_client: LLM 客户端（可选，用于 LLM 情节向量提取）
            cost_tracker: 成本追踪器（可选）
        """
        self.duplicate_threshold = duplicate_threshold
        self.compare_chapters = compare_chapters
        self.enable_plot_detection = enable_plot_detection
        self.llm_client = llm_client
        self.cost_tracker = cost_tracker

        # 缓存情节向量
        self._plot_vectors: Dict[int, PlotVector] = {}

    def detect(
        self,
        new_content: str,
        previous_chapters: Dict[int, str],
        current_chapter: int = 0,
    ) -> SimilarityReport:
        """检测新内容与前几章的相似度.

        Args:
            new_content: 新生成的章节内容
            previous_chapters: {章节号: 内容} 前几章的内容
            current_chapter: 当前章节号（用于日志）

        Returns:
            SimilarityReport
        """
        if not new_content or not previous_chapters:
            return SimilarityReport()

        # 对每个前序章节计算相似度
        best_report = SimilarityReport()

        for ch_num, ch_content in sorted(previous_chapters.items(), reverse=True):
            report = self._compare_two_texts(new_content, ch_content)

            if report.overall_similarity > best_report.overall_similarity:
                best_report = report
                best_report.most_similar_chapter = ch_num

        best_report.is_duplicate = (
            best_report.overall_similarity >= self.duplicate_threshold
        )

        if best_report.is_duplicate:
            logger.warning(
                f"[SimilarityDetector] 第{current_chapter}章与第"
                f"{best_report.most_similar_chapter}章内容高度相似! "
                f"相似度={best_report.overall_similarity:.1%}"
            )
        else:
            logger.info(
                f"[SimilarityDetector] 第{current_chapter}章相似度检测通过 "
                f"(最高={best_report.overall_similarity:.1%})"
            )

        return best_report

    def _compare_two_texts(
        self,
        text_a: str,
        text_b: str,
        plot_vector_a: Optional[PlotVector] = None,
        plot_vector_b: Optional[PlotVector] = None,
    ) -> SimilarityReport:
        """比较两段文本的相似度.

        Args:
            text_a: 文本A
            text_b: 文本B
            plot_vector_a: 文本A的情节向量（可选）
            plot_vector_b: 文本B的情节向量（可选）
        """
        report = SimilarityReport()

        # 1. N-gram 相似度
        report.ngram_similarity = self._ngram_similarity(text_a, text_b)

        # 2. 句子重叠检测
        overlap, dup_sentences = self._sentence_overlap(text_a, text_b)
        report.sentence_overlap = overlap
        report.duplicate_sentences = dup_sentences[:5]  # 最多记录 5 个

        # 3. 结构相似度
        report.structure_similarity = self._structure_similarity(text_a, text_b)

        # 4. 情节相似度（如果启用且有数据）
        if self.enable_plot_detection and plot_vector_a and plot_vector_b:
            plot_sim, reasons = self._plot_similarity(plot_vector_a, plot_vector_b)
            report.plot_similarity = plot_sim
            report.plot_duplicate_reasons = reasons

        # 加权计算总体相似度
        report.overall_similarity = (
            report.ngram_similarity * self.WEIGHTS["ngram"]
            + report.sentence_overlap * self.WEIGHTS["sentence"]
            + report.structure_similarity * self.WEIGHTS["structure"]
            + report.plot_similarity * self.WEIGHTS["plot"]
        )

        return report

    def _ngram_similarity(self, text_a: str, text_b: str) -> float:
        """计算 N-gram 相似度 (Jaccard)."""
        ngrams_a = self._extract_ngrams(text_a)
        ngrams_b = self._extract_ngrams(text_b)

        if not ngrams_a or not ngrams_b:
            return 0.0

        intersection = len(ngrams_a & ngrams_b)
        union = len(ngrams_a | ngrams_b)

        return intersection / union if union > 0 else 0.0

    def _extract_ngrams(self, text: str) -> set:
        """提取文本的 N-gram 集合."""
        # 清理文本：去除标点、空白
        clean = re.sub(r"[^\u4e00-\u9fff\w]", "", text)
        if len(clean) < self.NGRAM_SIZE:
            return set()

        return {
            clean[i : i + self.NGRAM_SIZE]
            for i in range(len(clean) - self.NGRAM_SIZE + 1)
        }

    def _sentence_overlap(self, text_a: str, text_b: str) -> Tuple[float, List[str]]:
        """检测句子级别的重叠."""
        sentences_a = self._split_sentences(text_a)
        sentences_b = self._split_sentences(text_b)

        if not sentences_a or not sentences_b:
            return 0.0, []

        # 构建 B 的句子集合（去除短句）
        set_b = set(
            s.strip() for s in sentences_b if len(s.strip()) >= self.MIN_SENTENCE_LENGTH
        )

        duplicates = []
        for s in sentences_a:
            s = s.strip()
            if len(s) < self.MIN_SENTENCE_LENGTH:
                continue
            if s in set_b:
                duplicates.append(s)

        total_valid = sum(
            1 for s in sentences_a if len(s.strip()) >= self.MIN_SENTENCE_LENGTH
        )

        overlap_ratio = len(duplicates) / total_valid if total_valid > 0 else 0.0
        return overlap_ratio, duplicates

    def _split_sentences(self, text: str) -> List[str]:
        """按中文标点分句."""
        return re.split(r"[。！？；\n]+", text)

    def _structure_similarity(self, text_a: str, text_b: str) -> float:
        """检测结构相似度（段落长度模式）."""
        paras_a = [p.strip() for p in text_a.split("\n") if p.strip()]
        paras_b = [p.strip() for p in text_b.split("\n") if p.strip()]

        if not paras_a or not paras_b:
            return 0.0

        # 归一化段落长度模式
        lens_a = self._normalize_lengths(paras_a)
        lens_b = self._normalize_lengths(paras_b)

        # 比较长度分布
        min_len = min(len(lens_a), len(lens_b))
        if min_len == 0:
            return 0.0

        matches = 0
        for i in range(min_len):
            if lens_a[i] == lens_b[i]:
                matches += 1

        return matches / min_len

    def _normalize_lengths(self, paragraphs: List[str]) -> List[str]:
        """将段落长度归一化为分类标签."""
        labels = []
        for p in paragraphs:
            length = len(p)
            if length < 50:
                labels.append("short")
            elif length < 200:
                labels.append("medium")
            else:
                labels.append("long")
        return labels

    # ══════════════════════════════════════════════════════════════════════════
    # 情节向量相关方法
    # ══════════════════════════════════════════════════════════════════════════

    def _plot_similarity(
        self,
        vector_a: PlotVector,
        vector_b: PlotVector,
    ) -> Tuple[float, List[str]]:
        """计算情节结构相似度.

        Args:
            vector_a: 情节向量A
            vector_b: 情节向量B

        Returns:
            (相似度, 重复原因列表)
        """
        if not vector_a or not vector_b:
            return 0.0, []

        # 各维度的权重
        weights = {
            "conflict_type": 0.25,
            "resolution_method": 0.25,
            "obstacle_level": 0.15,
            "outcome": 0.15,
            "emotional_arc": 0.20,
        }

        reasons = []
        similarity = 0.0

        # 比较各维度
        if vector_a.conflict_type and vector_b.conflict_type:
            if vector_a.conflict_type == vector_b.conflict_type:
                similarity += weights["conflict_type"]
                reasons.append(f"相同的冲突类型：{vector_a.conflict_type}")

        if vector_a.resolution_method and vector_b.resolution_method:
            if vector_a.resolution_method == vector_b.resolution_method:
                similarity += weights["resolution_method"]
                reasons.append(f"相同的解决方式：{vector_a.resolution_method}")

        if vector_a.obstacle_level and vector_b.obstacle_level:
            if vector_a.obstacle_level == vector_b.obstacle_level:
                similarity += weights["obstacle_level"]

        if vector_a.outcome and vector_b.outcome:
            if vector_a.outcome == vector_b.outcome:
                similarity += weights["outcome"]
                reasons.append(f"相同的结果：{vector_a.outcome}")

        if vector_a.emotional_arc and vector_b.emotional_arc:
            if vector_a.emotional_arc == vector_b.emotional_arc:
                similarity += weights["emotional_arc"]

        # 检查关键场景重叠
        if vector_a.key_scenes and vector_b.key_scenes:
            common_scenes = set(vector_a.key_scenes) & set(vector_b.key_scenes)
            if common_scenes:
                similarity += 0.1 * min(len(common_scenes), 3) / 3
                reasons.append(f"重复的场景类型：{', '.join(common_scenes)}")

        return min(similarity, 1.0), reasons

    def extract_plot_vector(
        self,
        content: str,
        chapter_number: int = 0,
    ) -> PlotVector:
        """从章节内容提取情节向量.

        优先使用 LLM 提取（如果可用），否则回退到关键词匹配。

        Args:
            content: 章节内容
            chapter_number: 章节号

        Returns:
            情节向量
        """
        # 优先使用 LLM 提取
        if self.llm_client:
            try:
                vector = self._extract_plot_vector_llm(content, chapter_number)
                if vector and vector.confidence >= 0.6:
                    # 缓存情节向量
                    if chapter_number > 0:
                        self._plot_vectors[chapter_number] = vector
                    return vector
            except Exception as e:
                logger.warning(
                    f"[SimilarityDetector] LLM 情节向量提取失败，回退到关键词匹配: {e}"
                )

        # 回退到关键词匹配
        return self._extract_plot_vector_keywords(content, chapter_number)

    async def _extract_plot_vector_llm(
        self,
        content: str,
        chapter_number: int = 0,
    ) -> PlotVector:
        """使用 LLM 提取情节向量.

        Args:
            content: 章节内容
            chapter_number: 章节号

        Returns:
            情节向量
        """
        import json

        # 截断内容避免 token 超限（取前 4000 字）
        truncated = content[:4000] if len(content) > 4000 else content

        prompt = self.PLOT_VECTOR_LLM_PROMPT.format(content=truncated)

        response = await self.llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=512,
        )

        text = response.get("content", "") if isinstance(response, dict) else str(response)

        # 解析 JSON 响应
        try:
            # 尝试直接解析
            data = json.loads(text)
        except json.JSONDecodeError:
            # 尝试从 markdown 代码块中提取
            import re
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
            else:
                # 尝试找到第一个 { 到最后一个 }
                start = text.find("{")
                end = text.rfind("}")
                if start >= 0 and end > start:
                    data = json.loads(text[start : end + 1])
                else:
                    raise ValueError(f"无法从 LLM 响应中提取 JSON: {text[:200]}")

        vector = PlotVector(
            chapter_number=chapter_number,
            protagonist_goal=data.get("protagonist_goal", ""),
            conflict_type=data.get("conflict_type", ""),
            obstacle_level=data.get("obstacle_level", ""),
            resolution_method=data.get("resolution_method", ""),
            outcome=data.get("outcome", ""),
            emotional_arc=data.get("emotional_arc", ""),
            key_scenes=data.get("key_scenes", []),
            confidence=data.get("confidence", 0.5),
        )

        self.logger.info(
            f"[SimilarityDetector] LLM 情节向量提取: 第{chapter_number}章, "
            f"冲突={vector.conflict_type}, 解决={vector.resolution_method}, "
            f"情感={vector.emotional_arc}"
        )

        return vector

    def _extract_plot_vector_keywords(
        self,
        content: str,
        chapter_number: int = 0,
    ) -> PlotVector:
        """使用关键词匹配提取情节向量（回退方案）.

        Args:
            content: 章节内容
            chapter_number: 章节号

        Returns:
            情节向量
        """
        vector = PlotVector(chapter_number=chapter_number)

        # 冲突类型关键词
        conflict_keywords = {
            "对抗": ["对决", "战斗", "交锋", "厮杀", "搏斗", "打斗", "交手"],
            "竞速": ["追赶", "追逐", "赛跑", "抢夺", "争先"],
            "解谜": ["破解", "解开", "推理", "推测", "分析", "调查", "探索"],
            "成长": ["突破", "领悟", "修炼", "进阶", "觉醒", "蜕变"],
            "探索": ["发现", "探索", "寻访", "搜寻", "探查"],
        }

        for conflict_type, keywords in conflict_keywords.items():
            if any(kw in content for kw in keywords):
                vector.conflict_type = conflict_type
                break

        # 解决方式关键词
        resolution_keywords = {
            "武力": ["击败", "击杀", "打败", "制服", "镇压", "斩杀"],
            "智谋": ["计策", "计谋", "策略", "设计", "布局", "诱敌"],
            "妥协": ["和解", "妥协", "协商", "退让", "交易"],
            "逃避": ["逃脱", "逃离", "躲避", "撤退", "逃走"],
            "意外": ["意外", "偶然", "巧合", "突然", "不料"],
        }

        for method, keywords in resolution_keywords.items():
            if any(kw in content for kw in keywords):
                vector.resolution_method = method
                break

        # 障碍等级（基于危险程度词汇）
        high_obstacle = ["绝境", "必死", "九死一生", "命悬一线", "危机" ]
        low_obstacle = ["轻松", "简单", "容易", "轻而易举"]

        if any(kw in content for kw in high_obstacle):
            vector.obstacle_level = "高"
        elif any(kw in content for kw in low_obstacle):
            vector.obstacle_level = "低"
        else:
            vector.obstacle_level = "中"

        # 结果关键词
        outcome_keywords = {
            "成功": ["成功", "获胜", "胜利", "达成", "得手"],
            "失败": ["失败", "落败", "失利", "惨败", "功亏一篑"],
            "逆转": ["逆转", "翻盘", "反败为胜", "扭转"],
            "部分": ["勉强", "险胜", "惨胜", "部分成功"],
        }

        for outcome, keywords in outcome_keywords.items():
            if any(kw in content for kw in keywords):
                vector.outcome = outcome
                break

        # 情感弧线关键词
        emotional_keywords = {
            "上扬": ["振奋", "激动", "兴奋", "喜悦", "豪情", "热血沸腾"],
            "下抑": ["失落", "悲伤", "沮丧", "绝望", "痛苦"],
            "波折": ["起伏", "跌宕", "波折", "悬念", "反转"],
            "平缓": ["平静", "平淡", "安宁", "祥和"],
        }

        for arc, keywords in emotional_keywords.items():
            if any(kw in content for kw in keywords):
                vector.emotional_arc = arc
                break

        # 关键场景类型
        scene_patterns = [
            ("战斗场景", ["战场", "战斗", "对决"]),
            ("修炼场景", ["修炼", "打坐", "闭关"]),
            ("谈判场景", ["谈判", "协商", "交涉"]),
            ("探险场景", ["探险", "探索", "发现"]),
            ("情感场景", ["感动", "思念", "温情"]),
        ]

        for scene_type, keywords in scene_patterns:
            if any(kw in content for kw in keywords):
                vector.key_scenes.append(scene_type)

        # 计算置信度
        confidence = 0.0
        if vector.conflict_type:
            confidence += 0.25
        if vector.resolution_method:
            confidence += 0.25
        if vector.outcome:
            confidence += 0.2
        if vector.emotional_arc:
            confidence += 0.15
        if vector.key_scenes:
            confidence += 0.15
        vector.confidence = confidence

        # 缓存情节向量
        if chapter_number > 0:
            self._plot_vectors[chapter_number] = vector

        return vector

    def detect_with_plot_vectors(
        self,
        new_content: str,
        previous_chapters: Dict[int, str],
        current_chapter: int = 0,
        previous_plot_vectors: Optional[Dict[int, PlotVector]] = None,
    ) -> SimilarityReport:
        """检测新内容与前几章的相似度（包含情节向量比对）.

        Args:
            new_content: 新生成的章节内容
            previous_chapters: {章节号: 内容} 前几章的内容
            current_chapter: 当前章节号
            previous_plot_vectors: {章节号: 情节向量} 前几章的情节向量（可选）

        Returns:
            SimilarityReport
        """
        if not new_content or not previous_chapters:
            return SimilarityReport()

        # 提取当前章节的情节向量
        current_plot_vector = None
        if self.enable_plot_detection:
            current_plot_vector = self.extract_plot_vector(new_content, current_chapter)

        # 对每个前序章节计算相似度
        best_report = SimilarityReport()

        for ch_num, ch_content in sorted(previous_chapters.items(), reverse=True):
            # 获取或提取情节向量
            prev_plot_vector = None
            if self.enable_plot_detection:
                if previous_plot_vectors and ch_num in previous_plot_vectors:
                    prev_plot_vector = previous_plot_vectors[ch_num]
                elif ch_num in self._plot_vectors:
                    prev_plot_vector = self._plot_vectors[ch_num]
                else:
                    prev_plot_vector = self.extract_plot_vector(ch_content, ch_num)

            report = self._compare_two_texts(
                new_content,
                ch_content,
                current_plot_vector,
                prev_plot_vector,
            )

            if report.overall_similarity > best_report.overall_similarity:
                best_report = report
                best_report.most_similar_chapter = ch_num

        best_report.is_duplicate = (
            best_report.overall_similarity >= self.duplicate_threshold
        )

        # 额外检查：情节重复严重但文字重复不明显
        if best_report.plot_similarity >= self.PLOT_DUPLICATE_THRESHOLD:
            logger.warning(
                f"[SimilarityDetector] 第{current_chapter}章与第"
                f"{best_report.most_similar_chapter}章情节高度相似! "
                f"情节相似度={best_report.plot_similarity:.1%}"
            )
            if best_report.plot_duplicate_reasons:
                logger.warning(
                    f"情节重复原因：{', '.join(best_report.plot_duplicate_reasons)}"
                )

        if best_report.is_duplicate:
            logger.warning(
                f"[SimilarityDetector] 第{current_chapter}章与第"
                f"{best_report.most_similar_chapter}章内容高度相似! "
                f"相似度={best_report.overall_similarity:.1%}"
            )
        else:
            logger.info(
                f"[SimilarityDetector] 第{current_chapter}章相似度检测通过 "
                f"(最高={best_report.overall_similarity:.1%})"
            )

        return best_report

    def get_plot_vector(self, chapter_number: int) -> Optional[PlotVector]:
        """获取缓存的情节向量."""
        return self._plot_vectors.get(chapter_number)

    # ══════════════════════════════════════════════════════════════════════════
    # 情节模式重复检测
    # ══════════════════════════════════════════════════════════════════════════

    def detect_plot_pattern_repetition(
        self,
        chapters: Dict[int, str],
        min_consecutive: int = 3,
    ) -> Dict[str, Any]:
        """检测连续章节是否使用相同的情节模式.

        针对"敌人来袭→主角应对→快速击败→发现线索"等固定模式，
        检测是否在连续章节中反复出现。

        Args:
            chapters: {章节号: 内容}
            min_consecutive: 最少连续命中次数才判定为重复

        Returns:
            {
                "has_pattern_repetition": bool,
                "pattern_name": str,
                "affected_chapters": [int],
                "consecutive_count": int,
                "suggestion": str
            }
        """
        # 对每章匹配情节模式
        chapter_patterns: Dict[int, str] = {}

        for ch_num, content in chapters.items():
            matched_pattern = self._match_plot_pattern(content)
            if matched_pattern:
                chapter_patterns[ch_num] = matched_pattern

        if not chapter_patterns:
            return {"has_pattern_repetition": False}

        # 查找连续相同模式
        sorted_chapters = sorted(chapter_patterns.keys())
        best_pattern = None
        best_start = 0
        best_count = 0

        current_pattern = None
        current_start = 0
        current_count = 0

        for ch in sorted_chapters:
            pattern = chapter_patterns[ch]
            if pattern == current_pattern:
                current_count += 1
            else:
                if current_count >= min_consecutive and current_count > best_count:
                    best_count = current_count
                    best_pattern = current_pattern
                    best_start = current_start

                current_pattern = pattern
                current_start = ch
                current_count = 1

        # 检查最后一段
        if current_count >= min_consecutive and current_count > best_count:
            best_count = current_count
            best_pattern = current_pattern
            best_start = current_start

        if best_pattern and best_count >= min_consecutive:
            affected = list(range(best_start, best_start + best_count))
            pattern_info = self.PLOT_PATTERNS.get(best_pattern, {})
            pattern_name = pattern_info.get("name", best_pattern)

            return {
                "has_pattern_repetition": True,
                "pattern_name": pattern_name,
                "affected_chapters": affected,
                "consecutive_count": best_count,
                "suggestion": (
                    f"连续{best_count}章使用「{pattern_name}」模式，"
                    f"建议改变叙事结构，如：增加智谋对决、利用环境因素、"
                    f"引入第三方势力、设置反转等"
                ),
            }

        return {"has_pattern_repetition": False}

    def _match_plot_pattern(self, content: str) -> Optional[str]:
        """匹配章节内容的情节模式.

        Returns:
            匹配的模式名，未匹配则返回 None
        """
        for pattern_name, pattern_config in self.PLOT_PATTERNS.items():
            steps_matched = 0
            keywords_list = pattern_config["keywords"]

            for step_keywords in keywords_list:
                if any(kw in content for kw in step_keywords):
                    steps_matched += 1

            # 如果匹配了 70% 以上的步骤，认为命中该模式
            total_steps = len(keywords_list)
            if total_steps > 0 and steps_matched / total_steps >= 0.7:
                return pattern_name

        return None
