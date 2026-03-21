"""内容相似度检测器 - 检测章节之间的内容重复.

使用多种轻量级文本相似度算法（无需外部依赖）：
1. N-gram 重叠检测
2. 关键句重复检测
3. 结构相似度检测
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from core.logging_config import logger


@dataclass
class SimilarityReport:
    """相似度检测报告."""

    is_duplicate: bool = False  # 是否判定为重复
    overall_similarity: float = 0.0  # 总体相似度 (0-1)
    ngram_similarity: float = 0.0  # N-gram 相似度
    sentence_overlap: float = 0.0  # 句子重叠比例
    structure_similarity: float = 0.0  # 结构相似度
    duplicate_sentences: List[str] = field(default_factory=list)  # 重复句子
    most_similar_chapter: int = 0  # 最相似的章节号

    def to_dict(self) -> dict:
        return {
            "is_duplicate": self.is_duplicate,
            "overall_similarity": round(self.overall_similarity, 3),
            "ngram_similarity": round(self.ngram_similarity, 3),
            "sentence_overlap": round(self.sentence_overlap, 3),
            "structure_similarity": round(self.structure_similarity, 3),
            "duplicate_sentences_count": len(self.duplicate_sentences),
            "most_similar_chapter": self.most_similar_chapter,
        }


class SimilarityDetector:
    """章节内容相似度检测器.

    用于检测新生成的章节是否与前几章存在严重内容重复.
    """

    # 判定阈值
    DUPLICATE_THRESHOLD = 0.30  # 总体相似度超过 30% 判定为重复
    NGRAM_SIZE = 4  # N-gram 的 N 值
    MIN_SENTENCE_LENGTH = 8  # 最短有效句子长度

    def __init__(
        self,
        duplicate_threshold: float = 0.30,
        compare_chapters: int = 3,
    ):
        """
        Args:
            duplicate_threshold: 重复判定阈值 (0-1)
            compare_chapters: 向前比较的章节数
        """
        self.duplicate_threshold = duplicate_threshold
        self.compare_chapters = compare_chapters

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

    def _compare_two_texts(self, text_a: str, text_b: str) -> SimilarityReport:
        """比较两段文本的相似度."""
        report = SimilarityReport()

        # 1. N-gram 相似度
        report.ngram_similarity = self._ngram_similarity(text_a, text_b)

        # 2. 句子重叠检测
        overlap, dup_sentences = self._sentence_overlap(text_a, text_b)
        report.sentence_overlap = overlap
        report.duplicate_sentences = dup_sentences[:5]  # 最多记录 5 个

        # 3. 结构相似度
        report.structure_similarity = self._structure_similarity(text_a, text_b)

        # 加权计算总体相似度
        report.overall_similarity = (
            report.ngram_similarity * 0.35
            + report.sentence_overlap * 0.45
            + report.structure_similarity * 0.20
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
