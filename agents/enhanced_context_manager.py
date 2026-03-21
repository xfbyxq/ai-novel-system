"""
EnhancedContextManager - 增强型上下文管理器

采用四层记忆架构，确保关键信息不丢失：
1. 核心层（始终携带）：主题、核心冲突、主角终极目标
2. 关键层（动态保留）：伏笔、未解决冲突、角色重大决策
3. 近期层（最近 3 章）：详细摘要 + 结尾原文
4. 历史层（更早章节）：卷级摘要 + 关键事件索引

解决根本原因 1：上下文信息丢失严重
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.logging_config import logger


@dataclass
class CoreLayer:
    """核心层：小说的核心要素."""

    theme: str = ""  # 核心主题
    central_question: str = ""  # 核心问题
    main_conflict: str = ""  # 主线冲突
    protagonist_goal: str = ""  # 主角终极目标
    genre: str = ""  # 类型

    def to_prompt(self) -> str:
        """转换为提示词格式."""
        parts = []
        if self.theme:
            parts.append(f"**核心主题**: {self.theme}")
        if self.central_question:
            parts.append(f"**核心问题**: {self.central_question}")
        if self.main_conflict:
            parts.append(f"**主线冲突**: {self.main_conflict}")
        if self.protagonist_goal:
            parts.append(f"**主角目标**: {self.protagonist_goal}")
        if self.genre:
            parts.append(f"**类型**: {self.genre}")

        return "\n".join(parts) if parts else "（无核心设定）"


@dataclass
class CriticalElement:
    """关键元素：必须在上下文中保留的信息."""

    id: str
    type: str  # "foreshadowing", "conflict", "decision", "goal"
    content: str
    planted_chapter: int
    importance: int  # 1-10
    urgency: int  # 距离埋设/发生的章节数
    status: str = "pending"  # pending/resolved/abandoned
    related_characters: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def priority_score(self) -> int:
        """计算优先级分数（重要性 * 紧急程度）."""
        return self.importance * max(1, self.urgency)

    def to_prompt(self) -> str:
        """转换为提示词."""
        if self.type == "foreshadowing":
            return f"[伏笔] 第{self.planted_chapter}章：{self.content} (已{self.urgency}章未回收，重要性：{self.importance})"
        elif self.type == "conflict":
            return f"[未解决冲突] {self.content} (始于第{self.planted_chapter}章)"
        elif self.type == "decision":
            return f"[待决事项] {self.content} (第{self.planted_chapter}章提出)"
        else:
            return f"[{self.type}] {self.content}"


@dataclass
class RecentChapter:
    """近期章节：详细摘要."""

    chapter_number: int
    title: str
    summary: str
    key_events: List[str]
    character_changes: Dict[str, str]
    ending_state: str
    foreshadowings: List[str]
    word_count: int = 0

    def to_prompt(self) -> str:
        """转换为提示词."""
        parts = [f"## 第{self.chapter_number}章 {self.title}"]

        if self.summary:
            parts.append(f"**剧情**: {self.summary[:300]}")

        if self.key_events:
            events = "、".join(self.key_events[:5])
            parts.append(f"**关键事件**: {events}")

        if self.character_changes:
            changes = "; ".join(
                f"{k}: {v}" for k, v in list(self.character_changes.items())[:3]
            )
            parts.append(f"**角色变化**: {changes}")

        if self.foreshadowings:
            foreshadows = "、".join(self.foreshadowings[:3])
            parts.append(f"**伏笔**: {foreshadows}")

        if self.ending_state:
            parts.append(f"**结尾状态**: {self.ending_state[:200]}")

        return "\n".join(parts)


@dataclass
class HistoricalIndex:
    """历史索引：早期章节的索引式回顾."""

    volume_number: int
    volume_title: str
    chapter_range: tuple  # (start, end)
    summary: str
    key_events: List[Dict[str, Any]]  # {chapter, event, importance}
    milestones: List[str]  # 重大里程碑

    def to_prompt(self) -> str:
        """转换为提示词."""
        parts = [f"## 第{self.volume_number}卷：{self.volume_title}"]
        parts.append(f"章节范围：第{self.chapter_range[0]}-{self.chapter_range[1]}章")

        if self.summary:
            parts.append(f"**卷概要**: {self.summary[:200]}")

        if self.key_events:
            parts.append("**关键事件**:")
            for event in self.key_events[:5]:
                parts.append(f"  - 第{event['chapter']}章：{event['event']}")

        if self.milestones:
            parts.append("**里程碑**:")
            for milestone in self.milestones[:3]:
                parts.append(f"  - {milestone}")

        return "\n".join(parts)


@dataclass
class EnhancedContext:
    """增强型上下文."""

    core_layer: CoreLayer = field(default_factory=CoreLayer)
    critical_layer: List[CriticalElement] = field(default_factory=list)
    recent_layer: List[RecentChapter] = field(default_factory=list)
    historical_layer: List[HistoricalIndex] = field(default_factory=list)

    # 元数据
    current_chapter: int = 0
    total_chapters: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_prompt(self) -> str:
        """转换为完整的提示词."""
        parts = []

        # 1. 核心层（始终在最前面）
        parts.append("【核心设定】")
        parts.append(self.core_layer.to_prompt())

        # 2. 关键层（动态重要信息）
        if self.critical_layer:
            parts.append("\n【关键信息（必须关注）】")
            # 按优先级排序
            sorted_elements = sorted(
                self.critical_layer, key=lambda x: x.priority_score(), reverse=True
            )
            for element in sorted_elements[:10]:  # 最多显示 10 个
                parts.append(f"- {element.to_prompt()}")

        # 3. 历史层（早期回顾）
        if self.historical_layer:
            parts.append("\n【早期剧情回顾】")
            for hist in self.historical_layer:
                parts.append(hist.to_prompt())

        # 4. 近期层（详细信息）
        if self.recent_layer:
            parts.append("\n【近期剧情详情】")
            for chapter in self.recent_layer:
                parts.append(chapter.to_prompt())

        return "\n\n".join(parts)

    def estimate_tokens(self) -> int:
        """估算 token 数（中文约 1.5 字符/token）."""
        prompt = self.to_prompt()
        return int(len(prompt) / 1.5)


class EnhancedContextManager:
    """
    增强型上下文管理器

    核心功能：
    1. 智能提取关键信息（不只是压缩，而是保留重要内容）
    2. 基于重要性和紧急程度动态调整上下文
    3. 确保第 3 章生成时，第 1 章的核心伏笔仍然在上下文中
    """

    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        self.context_cache: Dict[int, EnhancedContext] = {}
        logger.info(f"EnhancedContextManager initialized for novel: {novel_id}")

    def build_context_for_chapter(
        self,
        chapter_number: int,
        novel_data: Dict[str, Any],
        chapter_summaries: Dict[int, Dict[str, Any]],
        chapter_contents: Dict[int, str],
        foreshadowings: List[Dict[str, Any]],
        conflicts: List[Dict[str, Any]],
        volume_summaries: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> EnhancedContext:
        """
        为指定章节构建增强的上下文

        Args:
            chapter_number: 当前要写的章节号
            novel_data: 小说核心数据
            chapter_summaries: 章节摘要 {chapter_num: summary_dict}
            chapter_contents: 章节内容 {chapter_num: content}
            foreshadowings: 伏笔列表
            conflicts: 冲突列表
            volume_summaries: 卷摘要

        Returns:
            EnhancedContext 实例
        """
        logger.info(f"Building enhanced context for chapter {chapter_number}")

        ctx = EnhancedContext()
        ctx.current_chapter = chapter_number
        ctx.total_chapters = len(chapter_summaries)

        # 1. 构建核心层
        ctx.core_layer = self._build_core_layer(novel_data)

        # 2. 构建关键层（动态识别重要信息）
        ctx.critical_layer = self._build_critical_layer(
            chapter_number=chapter_number,
            foreshadowings=foreshadowings,
            conflicts=conflicts,
            chapter_summaries=chapter_summaries,
        )

        # 3. 构建近期层（最近 3 章详细信息）
        ctx.recent_layer = self._build_recent_layer(
            chapter_number=chapter_number,
            chapter_summaries=chapter_summaries,
            chapter_contents=chapter_contents,
            last_n=3,
        )

        # 4. 构建历史层（早期章节索引）
        ctx.historical_layer = self._build_historical_layer(
            chapter_number=chapter_number,
            chapter_summaries=chapter_summaries,
            volume_summaries=volume_summaries,
        )

        # 缓存上下文
        self.context_cache[chapter_number] = ctx

        # 日志统计
        token_count = ctx.estimate_tokens()
        logger.info(
            f"Enhanced context built: {len(ctx.critical_layer)} critical elements, "
            f"{len(ctx.recent_layer)} recent chapters, "
            f"~{token_count} tokens"
        )

        return ctx

    def _build_core_layer(self, novel_data: Dict[str, Any]) -> CoreLayer:
        """构建核心层."""
        core = CoreLayer()

        # 从主题分析中提取
        topic_analysis = novel_data.get("topic_analysis", {})
        core.theme = topic_analysis.get("core_theme", "")
        core.central_question = topic_analysis.get("central_question", "")
        core.genre = novel_data.get("genre", "")

        # 从大纲中提取主线冲突
        plot_outline = novel_data.get("plot_outline", {})
        if isinstance(plot_outline, dict):
            main_plot = plot_outline.get("main_plot", {})
            core.main_conflict = main_plot.get("core_conflict", "")
            core.protagonist_goal = main_plot.get("protagonist_goal", "")

        return core

    def _build_critical_layer(
        self,
        chapter_number: int,
        foreshadowings: List[Dict[str, Any]],
        conflicts: List[Dict[str, Any]],
        chapter_summaries: Dict[int, Dict[str, Any]],
    ) -> List[CriticalElement]:
        """
        构建关键层

        关键改进：
        - 识别"如果这章不写，后面就忘了"的信息
        - 基于重要性和紧急程度排序
        """
        elements = []

        # 1. 处理伏笔
        for foreshadow in foreshadowings:
            if foreshadow.get("status") != "pending":
                continue

            planted_chapter = foreshadow.get("planted_chapter", 0)
            urgency = chapter_number - planted_chapter
            importance = foreshadow.get("importance", 5)

            # 高重要性 + 超 3 章 = 必须携带
            if importance >= 7 and urgency >= 3:
                elements.append(
                    CriticalElement(
                        id=foreshadow.get("id", ""),
                        type="foreshadowing",
                        content=foreshadow.get("content", ""),
                        planted_chapter=planted_chapter,
                        importance=importance,
                        urgency=urgency,
                        related_characters=foreshadow.get("related_characters", []),
                        metadata={
                            "expected_resolve": foreshadow.get(
                                "expected_resolve_chapter"
                            )
                        },
                    )
                )
            # 中等重要性 + 超 5 章 = 建议携带
            elif importance >= 5 and urgency >= 5:
                elements.append(
                    CriticalElement(
                        id=foreshadow.get("id", ""),
                        type="foreshadowing",
                        content=foreshadow.get("content", ""),
                        planted_chapter=planted_chapter,
                        importance=importance,
                        urgency=urgency,
                        related_characters=foreshadow.get("related_characters", []),
                    )
                )

        # 2. 处理未解决冲突
        for conflict in conflicts:
            if conflict.get("resolved", False):
                continue

            related_chapters = conflict.get("related_chapters", [])
            if not related_chapters:
                continue

            last_chapter = max(related_chapters)
            urgency = chapter_number - last_chapter

            # 超过 2 章未解决的冲突 = 关键
            if urgency >= 2:
                elements.append(
                    CriticalElement(
                        id=conflict.get("id", ""),
                        type="conflict",
                        content=conflict.get("description", ""),
                        planted_chapter=last_chapter,
                        importance=conflict.get("importance", 7),
                        urgency=urgency,
                        related_characters=conflict.get("characters", []),
                    )
                )

        # 3. 处理角色重大待决事项
        for ch_num in range(max(1, chapter_number - 5), chapter_number):
            if ch_num not in chapter_summaries:
                continue

            summary = chapter_summaries[ch_num]
            character_changes = summary.get("character_changes", {})

            # 识别重大变化/决策
            if isinstance(character_changes, dict):
                for char_name, change in character_changes.items():
                    if "决定" in change or "目标" in change or "承诺" in change:
                        elements.append(
                            CriticalElement(
                                id=f"decision_{ch_num}_{char_name}",
                                type="decision",
                                content=f"{char_name}: {change}",
                                planted_chapter=ch_num,
                                importance=6,
                                urgency=chapter_number - ch_num,
                                related_characters=[char_name],
                            )
                        )

        # 按优先级排序
        elements.sort(key=lambda x: x.priority_score(), reverse=True)

        return elements

    def _build_recent_layer(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
        chapter_contents: Dict[int, str],
        last_n: int = 3,
    ) -> List[RecentChapter]:
        """构建近期层（最近 N 章的详细信息）."""
        chapters = []

        start_chapter = max(1, chapter_number - last_n)

        for ch in range(start_chapter, chapter_number):
            if ch not in chapter_summaries:
                continue

            summary = chapter_summaries[ch]

            # 构建详细摘要
            recent = RecentChapter(
                chapter_number=ch,
                title=summary.get("title", f"第{ch}章"),
                summary=summary.get("plot_progress", ""),
                key_events=summary.get("key_events", []),
                character_changes=summary.get("character_changes", {}),
                ending_state=summary.get("ending_state", ""),
                foreshadowings=summary.get("foreshadowing", []),
                word_count=(
                    len(chapter_contents.get(ch, "")) if ch in chapter_contents else 0
                ),
            )

            chapters.append(recent)

        return chapters

    def _build_historical_layer(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
        volume_summaries: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> List[HistoricalIndex]:
        """构建历史层（早期章节的索引式回顾）."""
        historical_indices = []

        # 冷记忆起始点：跳过热记忆覆盖的章节
        cold_end = max(1, chapter_number - 3)

        if cold_end <= 1:
            return historical_indices

        # 如果有预计算的卷摘要，直接使用
        if volume_summaries:
            for vol_num, vol_data in sorted(volume_summaries.items()):
                vol_start = (vol_num - 1) * 10 + 1
                vol_end = vol_num * 10

                if vol_end < cold_end:
                    historical_indices.append(
                        HistoricalIndex(
                            volume_number=vol_num,
                            volume_title=vol_data.get("title", f"第{vol_num}卷"),
                            chapter_range=(vol_start, vol_end),
                            summary=vol_data.get("summary", ""),
                            key_events=vol_data.get("key_events", []),
                            milestones=vol_data.get("milestones", []),
                        )
                    )
        else:
            # 按卷聚合章节摘要
            volumes: Dict[int, Dict[str, Any]] = {}
            for ch in range(1, cold_end):
                if ch not in chapter_summaries:
                    continue

                vol_num = (ch - 1) // 10 + 1
                if vol_num not in volumes:
                    volumes[vol_num] = {"chapters": [], "events": [], "milestones": []}

                summary = chapter_summaries[ch]
                volumes[vol_num]["chapters"].append(
                    {
                        "chapter": ch,
                        "summary": summary.get("plot_progress", ""),
                        "key_events": summary.get("key_events", []),
                    }
                )

            # 转换为 HistoricalIndex
            for vol_num, vol_data in sorted(volumes.items()):
                vol_start = (vol_num - 1) * 10 + 1
                vol_end = vol_num * 10

                # 合并章节摘要
                combined_summary = "；".join(
                    ch["summary"][:50] for ch in vol_data["chapters"][:5]
                )

                # 提取关键事件
                key_events = []
                for ch in vol_data["chapters"]:
                    for event in ch.get("key_events", [])[:2]:
                        key_events.append(
                            {
                                "chapter": ch["chapter"],
                                "event": (
                                    event if isinstance(event, str) else str(event)
                                ),
                                "importance": 5,
                            }
                        )

                historical_indices.append(
                    HistoricalIndex(
                        volume_number=vol_num,
                        volume_title=f"第{vol_num}卷",
                        chapter_range=(vol_start, min(vol_end, cold_end - 1)),
                        summary=combined_summary,
                        key_events=key_events[:10],
                        milestones=[],
                    )
                )

        return historical_indices

    def get_context(self, chapter_number: int) -> Optional[EnhancedContext]:
        """从缓存获取上下文."""
        return self.context_cache.get(chapter_number)

    def clear_cache(self):
        """清除缓存."""
        self.context_cache.clear()
        logger.info("Context cache cleared")


# 便捷函数
def build_enhanced_context(
    novel_id: str, chapter_number: int, **kwargs
) -> EnhancedContext:
    """便捷函数：构建增强上下文."""
    manager = EnhancedContextManager(novel_id)
    return manager.build_context_for_chapter(chapter_number, **kwargs)
