"""大纲 - 章节一致性监控服务 (Issue #37).

功能：
1. 定期扫描已写章节
2. 计算与大纲的偏差
3. 偏差超过阈值时发送告警
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging_config import logger
from core.models.chapter import Chapter
from core.models.plot_outline import PlotOutline


class OutlineDeviationMonitor:
    """大纲 - 章节一致性监控服务."""

    def __init__(self, db: AsyncSession):
        """初始化方法."""
        self.db = db
        self.deviation_threshold = 0.7  # 偏差阈值（70%）
        self.max_acceptable_deviations = 3  # 最大可接受偏差章节数

    async def check_deviation(
        self,
        novel_id: UUID,
    ) -> Dict[str, Any]:
        """
        检查小说的大纲偏差.
        
        Args:
            novel_id: 小说 ID
        
        Returns:
            偏差检查结果：
            {
                "has_deviation": bool,
                "deviation_count": int,
                "deviations": [...],
                "alert_needed": bool,
            }
        """
        logger.info(f"Checking outline deviation for novel {novel_id}")
        
        # 1. 获取大纲
        outline_result = await self.db.execute(
            select(PlotOutline).where(PlotOutline.novel_id == novel_id)
        )
        outline = outline_result.scalar_one_or_none()
        
        if not outline:
            logger.warning(f"No outline found for novel {novel_id}")
            return {
                "has_deviation": False,
                "deviation_count": 0,
                "deviations": [],
                "alert_needed": False,
                "message": "无大纲",
            }
        
        # 2. 获取所有章节
        chapters_result = await self.db.execute(
            select(Chapter)
            .where(Chapter.novel_id == novel_id)
            .order_by(Chapter.chapter_number)
        )
        chapters = chapters_result.scalars().all()
        
        if not chapters:
            return {
                "has_deviation": False,
                "deviation_count": 0,
                "deviations": [],
                "alert_needed": False,
                "message": "无章节",
            }
        
        # 3. 计算每个章节的偏差
        deviations = []
        for chapter in chapters:
            if not chapter.content:
                continue
            
            deviation = await self._calculate_chapter_deviation(chapter, outline)
            if deviation["score"] > self.deviation_threshold:
                deviations.append({
                    "chapter_number": chapter.chapter_number,
                    "score": deviation["score"],
                    "reasons": deviation["reasons"],
                })
        
        # 4. 判断是否需要告警
        has_deviation = len(deviations) > 0
        alert_needed = len(deviations) > self.max_acceptable_deviations
        
        result = {
            "has_deviation": has_deviation,
            "deviation_count": len(deviations),
            "deviations": deviations,
            "alert_needed": alert_needed,
            "total_chapters": len(chapters),
            "threshold": self.deviation_threshold,
            "message": self._generate_message(deviations, alert_needed),
        }
        
        logger.info(
            f"Deviation check completed for novel {novel_id}: "
            f"{len(deviations)} deviations found, alert_needed={alert_needed}"
        )
        
        return result

    async def _calculate_chapter_deviation(
        self,
        chapter: Chapter,
        outline: PlotOutline,
    ) -> Dict[str, Any]:
        """
        计算单个章节与大纲的偏差.
        
        Args:
            chapter: 章节对象
            outline: 大纲对象
        
        Returns:
            偏差信息：
            {
                "score": float,  # 偏差分数（0-1，越大越偏离）
                "reasons": list,  # 偏差原因列表
            }
        """
        reasons = []
        score = 0.0
        
        # 1. 检查章节是否包含大纲中的强制性事件
        chapter_plan = chapter.outline_task or {}
        mandatory_events = chapter_plan.get("plot_points", [])
        
        if mandatory_events and chapter.content:
            matched_events = 0
            for event in mandatory_events:
                # 简化实现：检查关键词
                keywords = [w for w in event.split() if len(w) > 1][:2]
                if any(kw in chapter.content for kw in keywords):
                    matched_events += 1
            
            event_match_rate = matched_events / len(mandatory_events)
            if event_match_rate < 0.6:
                reasons.append(f"强制性事件匹配率低 ({event_match_rate:.2f})")
                score += (1 - event_match_rate) * 0.5
        
        # 2. 检查章节字数是否异常
        expected_word_count = chapter_plan.get("expected_word_count", 3000)
        if chapter.word_count:
            word_count_ratio = chapter.word_count / expected_word_count
            if word_count_ratio < 0.5 or word_count_ratio > 2.0:
                reasons.append(f"字数异常 (期望{expected_word_count}, 实际{chapter.word_count})")
                score += 0.2
        
        # 3. 检查角色出场是否符合大纲
        expected_characters = chapter_plan.get("characters_appeared", [])
        actual_characters = chapter.characters_appeared or []
        
        if expected_characters and actual_characters:
            # 检查是否有重要角色未出场
            expected_set = set(str(c) for c in expected_characters)
            actual_set = set(str(c) for c in actual_characters)
            missing_characters = expected_set - actual_set
            
            if missing_characters:
                reasons.append(f"缺少重要角色出场 ({len(missing_characters)}个)")
                score += 0.3
        
        # 4. 检查伏笔是否回收
        foreshadowing = chapter.foreshadowing or []
        if foreshadowing:
            # 检查伏笔是否在后续章节回收（简化实现）
            reasons.append(f"有待回收伏笔 ({len(foreshadowing)}个)")
            score += 0.1
        
        # 归一化分数到 0-1
        score = min(1.0, score)
        
        return {
            "score": round(score, 2),
            "reasons": reasons,
            "is_deviant": score > self.deviation_threshold,
        }

    def _generate_message(
        self,
        deviations: List[Dict[str, Any]],
        alert_needed: bool,
    ) -> str:
        """生成偏差检查消息."""
        if not deviations:
            return "所有章节与大纲保持一致"
        
        if alert_needed:
            return (
                f"⚠️ 检测到{len(deviations)}个章节偏离大纲，"
                f"超过阈值 ({self.max_acceptable_deviations}个)，建议审查"
            )
        else:
            return (
                f"⚡ 检测到{len(deviations)}个章节偏离大纲，"
                f"在可接受范围内 (阈值：{self.max_acceptable_deviations}个)"
            )

    async def send_alert(
        self,
        novel_id: UUID,
        deviations: List[Dict[str, Any]],
    ) -> bool:
        """
        发送偏差告警.
        
        Args:
            novel_id: 小说 ID
            deviations: 偏差列表
        
        Returns:
            是否发送成功
        """
        logger.warning(f"Sending outline deviation alert for novel {novel_id}")
        
        # 这里可以集成飞书、邮件等通知方式
        # 简化实现：只记录日志
        
        alert_message = (
            f"🚨 大纲偏差告警\n"
            f"小说 ID: {novel_id}\n"
            f"偏离章节数：{len(deviations)}\n"
            f"偏离章节：{', '.join(str(d['chapter_number']) for d in deviations)}\n"
            f"建议：请及时审查并调整大纲或章节内容"
        )
        
        logger.warning(alert_message)
        
        # TODO: 集成飞书/邮件通知
        # await feishu_send_alert(...)
        
        return True


async def check_outline_deviation(
    db: AsyncSession,
    novel_id: UUID,
) -> Dict[str, Any]:
    """便捷函数：检查大纲偏差."""
    monitor = OutlineDeviationMonitor(db)
    result = await monitor.check_deviation(novel_id)
    
    # 如果需要告警，发送通知
    if result["alert_needed"]:
        await monitor.send_alert(novel_id, result["deviations"])
    
    return result
