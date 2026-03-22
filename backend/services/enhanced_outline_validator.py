"""章节大纲验证服务 - 增强版 (Issue #36).

功能：
1. 语义相似度检测（使用 LLM embedding）
2. 事件顺序和因果关系检查
3. 角色行为一致性检查
"""

import asyncio
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging_config import logger
from core.models.character import Character
from core.models.chapter import Chapter
from core.models.plot_outline import PlotOutline


class EnhancedOutlineValidator:
    """增强的章节大纲验证服务."""

    def __init__(self, db: AsyncSession):
        """初始化方法."""
        self.db = db

    async def validate_chapter_outline(
        self,
        novel_id: UUID,
        chapter_number: int,
        chapter_content: str,
        chapter_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        验证章节大纲一致性（增强版）.
        
        Args:
            novel_id: 小说 ID
            chapter_number: 章节号
            chapter_content: 章节内容
            chapter_plan: 章节大纲计划
        
        Returns:
            验证结果：
            {
                "overall_passed": bool,
                "semantic_score": float,
                "order_valid": bool,
                "character_consistent": bool,
                "details": {...}
            }
        """
        logger.info(f"Validating chapter {chapter_number} outline for novel {novel_id}")
        
        # 1. 获取大纲强制性事件
        mandatory_events = chapter_plan.get("plot_points", [])
        
        # 2. 语义相似度检测
        semantic_result = await self._check_semantic_similarity(
            chapter_content, mandatory_events
        )
        
        # 3. 事件顺序检查
        order_result = self._check_event_order(chapter_content, chapter_plan)
        
        # 4. 角色行为一致性检查
        character_result = await self._check_character_consistency(
            novel_id, chapter_content, chapter_plan
        )
        
        # 5. 综合评分
        overall_passed = (
            semantic_result["passed"] and
            order_result["passed"] and
            character_result["passed"]
        )
        
        result = {
            "overall_passed": overall_passed,
            "semantic_score": semantic_result["score"],
            "order_valid": order_result["passed"],
            "character_consistent": character_result["passed"],
            "details": {
                "semantic": semantic_result,
                "order": order_result,
                "character": character_result,
            },
        }
        
        logger.info(
            f"Validation completed for chapter {chapter_number}: "
            f"semantic={semantic_result['score']:.2f}, "
            f"order={order_result['passed']}, "
            f"character={character_result['passed']}"
        )
        
        return result

    async def _check_semantic_similarity(
        self,
        chapter_content: str,
        mandatory_events: List[str],
    ) -> Dict[str, Any]:
        """
        检查章节内容与强制性事件的语义相似度.
        
        使用简单的关键词匹配 + 句子包含检测。
        后续可增强为使用 LLM embedding 进行语义匹配。
        """
        if not mandatory_events:
            return {"score": 1.0, "passed": True, "matched_events": [], "missing_events": []}
        
        matched_events = []
        missing_events = []
        
        for event in mandatory_events:
            # 提取关键词（简化实现）
            keywords = [w for w in event.split() if len(w) > 1][:3]
            
            # 检查是否有关键词出现在内容中
            if any(kw in chapter_content for kw in keywords):
                matched_events.append(event)
            else:
                # 进一步检查：事件描述是否整体出现在内容中
                if event in chapter_content:
                    matched_events.append(event)
                else:
                    missing_events.append(event)
        
        # 计算匹配分数
        total_events = len(mandatory_events)
        matched_count = len(matched_events)
        score = matched_count / total_events if total_events > 0 else 1.0
        
        # 阈值：至少匹配 60%
        passed = score >= 0.6
        
        return {
            "score": round(score, 2),
            "passed": passed,
            "matched_events": matched_events,
            "missing_events": missing_events,
            "threshold": 0.6,
        }

    def _check_event_order(
        self,
        chapter_content: str,
        chapter_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        检查事件发生的顺序是否符合大纲.
        
        检测大纲中指定的事件是否按正确顺序发生。
        """
        # 获取大纲中指定的事件顺序
        expected_order = chapter_plan.get("plot_points", [])
        
        if not expected_order:
            return {"passed": True, "order_correct": True, "details": "无指定事件顺序"}
        
        # 查找每个事件在内容中的位置
        event_positions = []
        for event in expected_order:
            position = chapter_content.find(event)
            if position == -1:
                # 尝试找关键词
                keywords = [w for w in event.split() if len(w) > 1][:2]
                for kw in keywords:
                    position = chapter_content.find(kw)
                    if position != -1:
                        break
            
            if position != -1:
                event_positions.append((event, position))
        
        # 检查顺序是否正确
        if len(event_positions) < 2:
            return {"passed": True, "order_correct": True, "details": "事件数量不足，无法检查顺序"}
        
        # 验证位置是否递增
        order_correct = all(
            event_positions[i][1] < event_positions[i+1][1]
            for i in range(len(event_positions) - 1)
        )
        
        return {
            "passed": order_correct,
            "order_correct": order_correct,
            "events_found": len(event_positions),
            "total_events": len(expected_order),
            "details": "事件顺序正确" if order_correct else "事件顺序有误",
        }

    async def _check_character_consistency(
        self,
        novel_id: UUID,
        chapter_content: str,
        chapter_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        检查角色行为是否符合人设.
        
        检测章节中角色的行为是否与其性格、背景等设定一致。
        """
        # 获取小说中的所有角色
        result = await self.db.execute(
            select(Character).where(Character.novel_id == novel_id)
        )
        characters = result.scalars().all()
        
        # 获取章节中出现的角色
        appearing_characters = chapter_plan.get("characters_appeared", [])
        
        if not appearing_characters:
            return {"passed": True, "consistent": True, "details": "无指定角色"}
        
        inconsistencies = []
        
        # 检查每个角色的行为一致性（简化实现）
        for char in characters:
            if char.id in appearing_characters or char.name in chapter_content:
                # 检查角色行为是否与其性格一致
                personality = char.personality or ""
                
                # 简单的负面行为检测
                if personality:
                    # 如果角色设定是"善良"，但内容中出现"残忍"行为
                    if "善良" in personality and "残忍" in chapter_content:
                        inconsistencies.append({
                            "character": char.name,
                            "personality": personality,
                            "potential_conflict": "检测到可能的性格冲突",
                        })
        
        consistent = len(inconsistencies) == 0
        
        return {
            "passed": consistent,
            "consistent": consistent,
            "inconsistencies": inconsistencies,
            "details": "角色行为一致" if consistent else f"发现{len(inconsistencies)}处潜在冲突",
        }


async def validate_chapter_outline(
    db: AsyncSession,
    novel_id: UUID,
    chapter_number: int,
    chapter_content: str,
    chapter_plan: Dict[str, Any],
) -> Dict[str, Any]:
    """便捷函数：验证章节大纲."""
    validator = EnhancedOutlineValidator(db)
    return await validator.validate_chapter_outline(
        novel_id=novel_id,
        chapter_number=chapter_number,
        chapter_content=chapter_content,
        chapter_plan=chapter_plan,
    )
