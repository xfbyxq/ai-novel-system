"""大纲动态更新器 - 根据实际写作内容动态调整后续大纲.

每 N 章触发一次偏差评估，分析实际内容与大纲的偏差，
自动更新未来章节的大纲（已写章节不受影响）。
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging_config import logger
from core.models.plot_outline import PlotOutline
from llm.cost_tracker import CostTracker
from llm.prompt_manager import PromptManager
from llm.qwen_client import QwenClient


@dataclass
class DeviationReport:
    """偏差分析报告."""

    character_deviation: float = 0.0  # 角色偏差分 (0-10)
    plot_deviation: float = 0.0  # 情节偏差分 (0-10)
    pacing_deviation: float = 0.0  # 节奏偏差分 (0-10)
    foreshadowing_deviation: float = 0.0  # 伏笔偏差分 (0-10)
    overall_deviation: float = 0.0  # 加权平均
    details: Dict[str, Any] = field(default_factory=dict)
    major_deviations: List[str] = field(default_factory=list)
    needs_update: bool = False

    def compute_overall(self) -> float:
        """计算加权平均偏差分."""
        self.overall_deviation = (
            self.character_deviation * 0.30
            + self.plot_deviation * 0.35
            + self.pacing_deviation * 0.20
            + self.foreshadowing_deviation * 0.15
        )
        return self.overall_deviation


@dataclass
class OutlineUpdatePlan:
    """大纲更新计划."""

    updated_volumes: Optional[List[Dict]] = None
    updated_sub_plots: Optional[List[Dict]] = None
    updated_key_turning_points: Optional[List[Dict]] = None
    updated_main_plot: Optional[Dict] = None
    updated_climax_chapter: Optional[int] = None
    change_summary: List[str] = field(default_factory=list)
    affected_chapter_range: Tuple[int, int] = (0, 0)


class OutlineDynamicUpdater:
    """大纲动态更新器.

    核心功能：
    1. 分析最近 N 章内容与大纲的偏差
    2. 生成更新方案（仅修改未写到的章节）
    3. 自动应用更新到数据库
    """

    def __init__(
        self,
        client: QwenClient,
        cost_tracker: CostTracker,
        deviation_threshold: float = 6.0,
    ):
        """初始化方法."""
        self.client = client
        self.cost_tracker = cost_tracker
        self.deviation_threshold = deviation_threshold
        self.pm = PromptManager

    async def run_dynamic_update(
        self,
        db: AsyncSession,
        novel_id: UUID,
        current_chapter: int,
        recent_chapters: List[Dict[str, Any]],
        outline_data: Dict[str, Any],
        world_setting: Dict[str, Any],
        characters: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """主编排方法：偏差分析 -> 判断 -> 生成更新 -> 应用.

        Args:
            db: 数据库会话
            novel_id: 小说 ID
            current_chapter: 当前写到第几章
            recent_chapters: 最近 N 章的摘要信息
            outline_data: 当前大纲数据
            world_setting: 世界观设定
            characters: 角色列表

        Returns:
            更新结果摘要
        """
        logger.info(
            f"[OutlineDynamicUpdater] 开始大纲偏差评估，当前进度：第{current_chapter}章"
        )

        # 步骤 1：偏差分析
        deviation = await self.analyze_deviation(
            recent_chapters=recent_chapters,
            outline_data=outline_data,
            current_chapter=current_chapter,
        )

        logger.info(
            f"[OutlineDynamicUpdater] 偏差分析完成: "
            f"角色={deviation.character_deviation:.1f}, "
            f"情节={deviation.plot_deviation:.1f}, "
            f"节奏={deviation.pacing_deviation:.1f}, "
            f"伏笔={deviation.foreshadowing_deviation:.1f}, "
            f"综合={deviation.overall_deviation:.1f}"
        )

        # 步骤 2：判断是否需要更新
        if not deviation.needs_update:
            logger.info(
                f"[OutlineDynamicUpdater] 偏差综合分 {deviation.overall_deviation:.1f} "
                f"低于阈值 {self.deviation_threshold}，跳过更新"
            )
            return {
                "updated": False,
                "deviation_report": {
                    "overall": deviation.overall_deviation,
                    "character": deviation.character_deviation,
                    "plot": deviation.plot_deviation,
                    "pacing": deviation.pacing_deviation,
                    "foreshadowing": deviation.foreshadowing_deviation,
                },
                "reason": "偏差在可接受范围内",
            }

        # 步骤 3：生成更新方案
        update_plan = await self.generate_outline_update(
            outline_data=outline_data,
            deviation=deviation,
            current_chapter=current_chapter,
            world_setting=world_setting,
            characters=characters,
        )

        if not update_plan.change_summary:
            logger.info("[OutlineDynamicUpdater] 更新方案为空，跳过")
            return {
                "updated": False,
                "deviation_report": {
                    "overall": deviation.overall_deviation,
                },
                "reason": "LLM 未生成有效的更新方案",
            }

        # 步骤 4：应用更新
        apply_result = await self.apply_update(
            db=db,
            novel_id=novel_id,
            update_plan=update_plan,
            current_chapter=current_chapter,
            deviation_report=(
                deviation.details
                if hasattr(deviation, "details")
                else deviation.__dict__
            ),
        )

        logger.info(
            f"[OutlineDynamicUpdater] 大纲更新完成: "
            f"{', '.join(update_plan.change_summary)}"
        )

        return {
            "updated": True,
            "deviation_report": {
                "overall": deviation.overall_deviation,
                "character": deviation.character_deviation,
                "plot": deviation.plot_deviation,
                "pacing": deviation.pacing_deviation,
                "foreshadowing": deviation.foreshadowing_deviation,
                "major_deviations": deviation.major_deviations,
            },
            "change_summary": update_plan.change_summary,
            "affected_chapters": list(
                range(
                    update_plan.affected_chapter_range[0],
                    update_plan.affected_chapter_range[1] + 1,
                )
            ),
            "apply_result": apply_result,
        }

    async def analyze_deviation(
        self,
        recent_chapters: List[Dict[str, Any]],
        outline_data: Dict[str, Any],
        current_chapter: int,
    ) -> DeviationReport:
        """分析最近章节内容与大纲的偏差.

        Args:
            recent_chapters: 最近 N 章的摘要
            outline_data: 当前大纲
            current_chapter: 当前章节号

        Returns:
            偏差分析报告
        """
        # 构建大纲中对应章节的计划摘要
        outline_plan = self._extract_outline_plan_for_chapters(
            outline_data, recent_chapters, current_chapter
        )

        # 构建最近章节摘要
        chapters_summary = self._format_recent_chapters(recent_chapters)
        chapter_count = len(recent_chapters)

        task_prompt = self.pm.format(
            self.pm.OUTLINE_DEVIATION_TASK,
            outline_plan=outline_plan,
            chapter_count=chapter_count,
            recent_chapters_summary=chapters_summary,
            current_chapter=current_chapter,
        )

        try:
            response = await self.client.chat(
                prompt=task_prompt,
                system=self.pm.OUTLINE_DEVIATION_SYSTEM,
                temperature=0.3,
                max_tokens=2048,
            )

            usage = response.get("usage", {})
            self.cost_tracker.record(
                agent_name="大纲偏差分析器",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                cost_category="base",
            )

            parsed = self._extract_json_object(response.get("content", ""))
            report = DeviationReport(
                character_deviation=float(parsed.get("character_deviation", 0)),
                plot_deviation=float(parsed.get("plot_deviation", 0)),
                pacing_deviation=float(parsed.get("pacing_deviation", 0)),
                foreshadowing_deviation=float(parsed.get("foreshadowing_deviation", 0)),
                details=parsed.get("details", {}),
                major_deviations=parsed.get("major_deviations", []),
            )
            report.compute_overall()
            report.needs_update = (
                report.overall_deviation >= self.deviation_threshold
                or parsed.get("recommend_update", False)
            )

            return report

        except Exception as e:
            logger.warning(f"[OutlineDynamicUpdater] 偏差分析 LLM 调用失败: {e}")
            return DeviationReport()

    async def generate_outline_update(
        self,
        outline_data: Dict[str, Any],
        deviation: DeviationReport,
        current_chapter: int,
        world_setting: Dict[str, Any],
        characters: List[Dict[str, Any]],
    ) -> OutlineUpdatePlan:
        """生成大纲更新方案.

        核心约束：仅修改 current_chapter 之后的章节。

        Args:
            outline_data: 当前大纲
            deviation: 偏差报告
            current_chapter: 当前章节号
            world_setting: 世界观设定
            characters: 角色列表

        Returns:
            更新方案
        """
        deviation_report_str = json.dumps(
            {
                "character_deviation": deviation.character_deviation,
                "plot_deviation": deviation.plot_deviation,
                "pacing_deviation": deviation.pacing_deviation,
                "foreshadowing_deviation": deviation.foreshadowing_deviation,
                "overall": deviation.overall_deviation,
                "details": deviation.details,
                "major_deviations": deviation.major_deviations,
            },
            ensure_ascii=False,
            indent=2,
        )

        # 精简大纲输出，避免 token 过长
        outline_str = json.dumps(outline_data, ensure_ascii=False, indent=2)
        if len(outline_str) > 4000:
            outline_str = outline_str[:4000] + "\n... (已截断)"

        # 精简世界观和角色信息
        world_summary = self._summarize_world_setting(world_setting)
        chars_summary = self._summarize_characters(characters)

        task_prompt = self.pm.format(
            self.pm.OUTLINE_UPDATE_TASK,
            current_chapter=current_chapter,
            next_chapter=current_chapter + 1,
            current_outline=outline_str,
            deviation_report=deviation_report_str,
            world_setting_summary=world_summary,
            characters_summary=chars_summary,
        )

        try:
            response = await self.client.chat(
                prompt=task_prompt,
                system=self.pm.OUTLINE_UPDATE_SYSTEM,
                temperature=0.5,
                max_tokens=4096,
            )

            usage = response.get("usage", {})
            self.cost_tracker.record(
                agent_name="大纲动态更新器",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                cost_category="base",
            )

            parsed = self._extract_json_object(response.get("content", ""))

            plan = OutlineUpdatePlan(
                updated_volumes=parsed.get("updated_volumes"),
                updated_sub_plots=parsed.get("updated_sub_plots"),
                updated_key_turning_points=parsed.get("updated_key_turning_points"),
                updated_main_plot=parsed.get("updated_main_plot"),
                updated_climax_chapter=parsed.get("updated_climax_chapter"),
                change_summary=parsed.get("change_summary", []),
            )

            # 计算受影响的章节范围
            plan.affected_chapter_range = self._compute_affected_range(
                plan, outline_data, current_chapter
            )

            return plan

        except Exception as e:
            logger.warning(f"[OutlineDynamicUpdater] 生成更新方案 LLM 调用失败: {e}")
            return OutlineUpdatePlan()

    async def apply_update(
        self,
        db: AsyncSession,
        novel_id: UUID,
        update_plan: OutlineUpdatePlan,
        current_chapter: int,
        deviation_report: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """将更新方案应用到数据库.

        Args:
            db: 数据库会话
            novel_id: 小说 ID
            update_plan: 更新方案
            current_chapter: 当前章节号
            deviation_report: 偏差报告（可选）

        Returns:
            应用结果摘要
        """
        try:
            stmt = select(PlotOutline).where(PlotOutline.novel_id == novel_id)
            result = await db.execute(stmt)
            plot_outline = result.scalar_one_or_none()

            if not plot_outline:
                logger.warning(
                    f"[OutlineDynamicUpdater] 未找到小说 {novel_id} 的大纲记录"
                )
                return {"applied": False, "reason": "大纲记录不存在"}

            updated_fields = []

            # 更新各字段（仅更新非 None 的字段）
            if update_plan.updated_volumes is not None:
                # 合并策略：保留已写卷的数据，替换未写卷的数据
                merged = self._merge_volumes(
                    plot_outline.volumes or [],
                    update_plan.updated_volumes,
                    current_chapter,
                )
                plot_outline.volumes = merged
                updated_fields.append("volumes")

            if update_plan.updated_sub_plots is not None:
                plot_outline.sub_plots = update_plan.updated_sub_plots
                updated_fields.append("sub_plots")

            if update_plan.updated_key_turning_points is not None:
                # 仅替换未发生的转折点
                merged_tp = self._merge_turning_points(
                    plot_outline.key_turning_points or [],
                    update_plan.updated_key_turning_points,
                    current_chapter,
                )
                plot_outline.key_turning_points = merged_tp
                updated_fields.append("key_turning_points")

            if update_plan.updated_main_plot is not None:
                # 仅更新 climax 和 resolution 部分
                existing_mp = plot_outline.main_plot or {}
                existing_mp.update(update_plan.updated_main_plot)
                plot_outline.main_plot = existing_mp
                updated_fields.append("main_plot")

            if update_plan.updated_climax_chapter is not None:
                if update_plan.updated_climax_chapter > current_chapter:
                    plot_outline.climax_chapter = update_plan.updated_climax_chapter
                    updated_fields.append("climax_chapter")

            # 更新版本号
            current_version = plot_outline.version or 1
            plot_outline.version = current_version + 1

            # 记录更新历史
            history = plot_outline.update_history or []

            # 从偏差报告中获取偏差分数
            deviation_score = 0
            if deviation_report and isinstance(deviation_report, dict):
                deviation_score = deviation_report.get("overall", 0)

            history.append(
                {
                    "version": plot_outline.version,
                    "updated_at": datetime.now().isoformat(),
                    "trigger_chapter": current_chapter,
                    "deviation_score": round(deviation_score, 1),
                    "change_summary": update_plan.change_summary,
                    "updated_fields": updated_fields,
                    "affected_chapters": list(
                        range(
                            update_plan.affected_chapter_range[0],
                            update_plan.affected_chapter_range[1] + 1,
                        )
                    ),
                }
            )
            plot_outline.update_history = history

            logger.info(
                f"[OutlineDynamicUpdater] 大纲更新已应用: "
                f"版本 v{current_version} -> v{plot_outline.version}, "
                f"更新字段: {updated_fields}"
            )

            return {
                "applied": True,
                "version": plot_outline.version,
                "updated_fields": updated_fields,
            }

        except Exception as e:
            logger.error(f"[OutlineDynamicUpdater] 应用更新失败: {e}")
            return {"applied": False, "reason": str(e)}

    # ─── 辅助方法 ───────────────────────────────────────────

    def _extract_outline_plan_for_chapters(
        self,
        outline_data: Dict[str, Any],
        recent_chapters: List[Dict[str, Any]],
        current_chapter: int,
    ) -> str:
        """提取大纲中与最近章节对应的计划信息."""
        parts = []

        # 从 volumes 中提取相关卷的信息
        volumes = outline_data.get("volumes", [])
        chapter_numbers = [ch.get("chapter_number", 0) for ch in recent_chapters]
        min_ch = min(chapter_numbers) if chapter_numbers else current_chapter
        max_ch = current_chapter

        for vol in volumes:
            ch_range = vol.get("chapters", vol.get("chapters_range", [0, 0]))
            if isinstance(ch_range, list) and len(ch_range) >= 2:
                vol_start, vol_end = ch_range[0], ch_range[1]
                if vol_start <= max_ch and vol_end >= min_ch:
                    parts.append(
                        f"### 第{vol.get('number', vol.get('volume_num', '?'))}卷: {vol.get('title', '')}"
                    )
                    parts.append(f"概要: {vol.get('summary', '')}")
                    key_events = vol.get("key_events", [])
                    if key_events:
                        parts.append("关键事件:")
                        for evt in key_events:
                            if isinstance(evt, dict):
                                parts.append(
                                    f"  - 第{evt.get('chapter', '?')}章: {evt.get('event', '')}"
                                )
                            else:
                                parts.append(f"  - {evt}")
                    tension_cycles = vol.get("tension_cycles", [])
                    if tension_cycles:
                        parts.append("张力循环:")
                        for tc in tension_cycles:
                            if isinstance(tc, dict):
                                parts.append(
                                    f"  - 压制: {tc.get('suppress_event', tc.get('suppress_events', ''))}, "
                                    f"释放: {tc.get('release_event', tc.get('release_events', ''))}"
                                )
                    parts.append("")

        # 添加关键转折点
        turning_points = outline_data.get("key_turning_points", [])
        relevant_tp = [
            tp
            for tp in turning_points
            if isinstance(tp, dict) and min_ch <= tp.get("chapter", 0) <= max_ch + 10
        ]
        if relevant_tp:
            parts.append("### 关键转折点")
            for tp in relevant_tp:
                parts.append(
                    f"  - 第{tp.get('chapter', '?')}章: "
                    f"{tp.get('event', '')} -> {tp.get('impact', '')}"
                )

        return "\n".join(parts) if parts else "（大纲中未找到对应章节的详细计划）"

    def _format_recent_chapters(self, recent_chapters: List[Dict[str, Any]]) -> str:
        """格式化最近章节的摘要信息."""
        parts = []
        for ch in recent_chapters:
            ch_num = ch.get("chapter_number", "?")
            parts.append(f"### 第{ch_num}章")

            # 从不同格式中提取信息
            if "key_events" in ch:
                events = ch["key_events"]
                if isinstance(events, list):
                    parts.append(f"关键事件: {'; '.join(str(e) for e in events)}")
            if "plot_progress" in ch:
                parts.append(f"情节推进: {ch['plot_progress']}")
            if "character_changes" in ch:
                parts.append(f"角色变化: {ch['character_changes']}")
            if "foreshadowing" in ch:
                foreshadowing = ch["foreshadowing"]
                if isinstance(foreshadowing, list) and foreshadowing:
                    parts.append(f"伏笔: {'; '.join(str(f) for f in foreshadowing)}")
            if "content" in ch:
                # 保留完整内容，由统一压缩处理
                content = ch["content"]
                parts.append(f"内容片段: {content}")

            parts.append("")

        return "\n".join(parts) if parts else "（无章节摘要信息）"

    @staticmethod
    def _summarize_world_setting(world_setting: Dict[str, Any]) -> str:
        """精简世界观信息."""
        if not world_setting:
            return "（无世界观设定）"
        parts = []
        if "world_type" in world_setting:
            parts.append(f"世界类型: {world_setting['world_type']}")
        if "power_system" in world_setting:
            ps = world_setting["power_system"]
            if isinstance(ps, dict):
                parts.append(f"力量体系: {ps.get('name', str(ps)[:100])}")
            else:
                parts.append(f"力量体系: {str(ps)[:100]}")
        if "geography" in world_setting:
            parts.append(f"地理: {str(world_setting['geography'])[:100]}")
        return "\n".join(parts) if parts else str(world_setting)[:300]

    @staticmethod
    def _summarize_characters(characters: List[Dict[str, Any]]) -> str:
        """精简角色信息."""
        if not characters:
            return "（无角色信息）"
        parts = []
        for c in characters[:10]:  # 限制最多 10 个角色
            name = c.get("name", "?")
            role = c.get("role_type", "?")
            parts.append(f"- {name} ({role})")
        return "\n".join(parts)

    @staticmethod
    def _merge_volumes(
        existing: List[Dict],
        updated: List[Dict],
        current_chapter: int,
    ) -> List[Dict]:
        """合并卷大纲：保留已写卷数据，替换未写卷数据."""
        existing_by_num = {}
        for vol in existing:
            num = vol.get("number", vol.get("volume_num"))
            if num is not None:
                existing_by_num[num] = vol

        updated_by_num = {}
        for vol in updated:
            num = vol.get("number", vol.get("volume_num"))
            if num is not None:
                updated_by_num[num] = vol

        result = []
        all_nums = sorted(
            set(list(existing_by_num.keys()) + list(updated_by_num.keys()))
        )

        for num in all_nums:
            existing_vol = existing_by_num.get(num)
            updated_vol = updated_by_num.get(num)

            if existing_vol:
                ch_range = existing_vol.get(
                    "chapters", existing_vol.get("chapters_range", [0, 0])
                )
                if isinstance(ch_range, list) and len(ch_range) >= 2:
                    vol_end = ch_range[1]
                    if vol_end <= current_chapter:
                        # 整卷已写完，保留原数据
                        result.append(existing_vol)
                        continue

            # 使用更新后的数据（或原数据作为兜底）
            if updated_vol:
                result.append(updated_vol)
            elif existing_vol:
                result.append(existing_vol)

        return result

    @staticmethod
    def _merge_turning_points(
        existing: List[Dict],
        updated: List[Dict],
        current_chapter: int,
    ) -> List[Dict]:
        """合并转折点：保留已发生的，替换未发生的."""
        # 保留已发生的转折点
        frozen = [
            tp
            for tp in existing
            if isinstance(tp, dict) and tp.get("chapter", 0) <= current_chapter
        ]
        # 使用更新后的未来转折点
        future_updated = [
            tp
            for tp in updated
            if isinstance(tp, dict) and tp.get("chapter", 0) > current_chapter
        ]
        return frozen + future_updated

    @staticmethod
    def _compute_affected_range(
        plan: OutlineUpdatePlan,
        outline_data: Dict[str, Any],
        current_chapter: int,
    ) -> Tuple[int, int]:
        """计算受影响的章节范围."""
        min_ch = current_chapter + 1
        max_ch = current_chapter + 1

        # 从更新的 volumes 中提取范围
        if plan.updated_volumes:
            for vol in plan.updated_volumes:
                ch_range = vol.get("chapters", vol.get("chapters_range", []))
                if isinstance(ch_range, list) and len(ch_range) >= 2:
                    max_ch = max(max_ch, ch_range[1])

        # 从更新的转折点中提取范围
        if plan.updated_key_turning_points:
            for tp in plan.updated_key_turning_points:
                if isinstance(tp, dict):
                    ch = tp.get("chapter", 0)
                    if ch > current_chapter:
                        max_ch = max(max_ch, ch)

        # 从高潮章节提取范围
        if (
            plan.updated_climax_chapter
            and plan.updated_climax_chapter > current_chapter
        ):
            max_ch = max(max_ch, plan.updated_climax_chapter)

        return (min_ch, max_ch)

    @staticmethod
    def _extract_json_object(text: str) -> Dict[str, Any]:
        """从 LLM 响应中提取 JSON 对象.

        多层策略，兼容各种 LLM 输出格式。
        """
        text = text.strip()

        # 策略 1: 直接解析
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        # 策略 2: 提取 markdown 代码块
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                result = json.loads(match.group(1).strip())
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

        # 策略 3: 提取花括号内的 JSON
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = text[start : end + 1]
            try:
                result = json.loads(json_str)
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                # 策略 4: 尝试修复不完整的 JSON
                open_braces = json_str.count("{")
                close_braces = json_str.count("}")
                if open_braces > close_braces:
                    try:
                        fixed = json_str + "}" * (open_braces - close_braces)
                        result = json.loads(fixed)
                        if isinstance(result, dict):
                            return result
                    except json.JSONDecodeError:
                        pass

        logger.warning(
            f"[OutlineDynamicUpdater] JSON 对象解析失败。" f"文本片段：{text[:100]}..."
        )
        return {}
