"""大纲质量评估器 - 扩展现有的质量评估维度"""

import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient

# 扩展的大纲质量评估维度
EXTENDED_OUTLINE_DIMENSIONS = {
    "structure_completeness": {
        "weight": 0.20,
        "description": "大纲结构完整性",
        "criteria": [
            "是否有清晰的三幕结构",
            "转折点是否合理分布",
            "结局是否完整",
            "卷级结构是否合理",
        ],
    },
    "setting_consistency": {
        "weight": 0.15,
        "description": "与世界观设定一致性",
        "criteria": [
            "力量体系使用是否符合设定",
            "地理环境描述是否一致",
            "势力关系是否合理",
            "历史文化背景是否统一",
        ],
    },
    "character_coherence": {
        "weight": 0.20,
        "description": "角色发展连贯性",
        "criteria": [
            "角色动机是否清晰",
            "成长轨迹是否合理",
            "关系变化是否自然",
            "主要角色戏份是否充足",
        ],
    },
    "tension_management": {
        "weight": 0.15,
        "description": "张力节奏控制",
        "criteria": [
            "冲突层次是否丰富",
            "高潮安排是否恰当",
            "节奏变化是否流畅",
            "张力循环是否合理",
        ],
    },
    "logical_flow": {
        "weight": 0.15,
        "description": "逻辑连贯性",
        "criteria": [
            "因果关系是否清晰",
            "时间线是否合理",
            "事件衔接是否自然",
            "伏笔回收是否到位",
        ],
    },
    "innovation_factor": {
        "weight": 0.15,
        "description": "创意新颖性",
        "criteria": [
            "是否有独特设定",
            "情节设计是否有新意",
            "角色塑造是否立体",
            "主题表达是否有深度",
        ],
    },
}


@dataclass
class OutlineQualityScore:
    """大纲质量评分结果"""

    overall_score: float
    dimension_scores: Dict[str, float]
    strengths: List[str]
    weaknesses: List[str]
    improvement_suggestions: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "improvement_suggestions": self.improvement_suggestions,
        }


class OutlineQualityEvaluator:
    """大纲质量评估器"""

    def __init__(
        self,
        client: Optional[QwenClient] = None,
        cost_tracker: Optional[CostTracker] = None,
    ):
        self.client = client or QwenClient()
        self.cost_tracker = cost_tracker or CostTracker()
        self.dimensions = EXTENDED_OUTLINE_DIMENSIONS

    async def evaluate_outline_comprehensively(
        self,
        outline: Dict[str, Any],
        world_setting: Dict[str, Any],
        characters: List[Dict[str, Any]],
    ) -> OutlineQualityScore:
        """执行综合大纲质量评估"""
        logger.info("开始执行综合大纲质量评估")

        try:
            # 1. 执行各个维度的评估
            dimension_scores = await self._evaluate_all_dimensions(
                outline, world_setting, characters
            )

            # 2. 计算综合评分
            overall_score = self._calculate_weighted_score(dimension_scores)

            # 3. 识别优势和劣势
            strengths = self._identify_strengths(dimension_scores)
            weaknesses = self._identify_weaknesses(dimension_scores)

            # 4. 生成改进建议
            improvement_suggestions = await self._generate_improvement_suggestions(
                outline, dimension_scores, weaknesses
            )

            result = OutlineQualityScore(
                overall_score=overall_score,
                dimension_scores=dimension_scores,
                strengths=strengths,
                weaknesses=weaknesses,
                improvement_suggestions=improvement_suggestions,
            )

            logger.info(f"大纲质量评估完成，综合评分：{overall_score:.2f}")
            return result

        except Exception as e:
            logger.error(f"大纲质量评估失败：{e}")
            # 返回默认评分
            return OutlineQualityScore(
                overall_score=5.0,
                dimension_scores={dim: 5.0 for dim in self.dimensions.keys()},
                strengths=[],
                weaknesses=["评估过程出现错误"],
                improvement_suggestions=[
                    {
                        "type": "system_error",
                        "priority": "high",
                        "description": "系统评估失败，请人工审核",
                        "details": str(e),
                    }
                ],
            )

    async def _evaluate_all_dimensions(
        self,
        outline: Dict[str, Any],
        world_setting: Dict[str, Any],
        characters: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """评估所有维度"""
        dimension_scores = {}

        # 结构完整性评估
        dimension_scores["structure_completeness"] = (
            await self._evaluate_structure_completeness(outline)
        )

        # 世界观一致性评估
        dimension_scores["setting_consistency"] = (
            await self._evaluate_setting_consistency(outline, world_setting)
        )

        # 角色连贯性评估
        dimension_scores["character_coherence"] = (
            await self._evaluate_character_coherence(outline, characters)
        )

        # 张力节奏评估
        dimension_scores["tension_management"] = (
            await self._evaluate_tension_management(outline)
        )

        # 逻辑连贯性评估
        dimension_scores["logical_flow"] = await self._evaluate_logical_flow(outline)

        # 创意新颖性评估
        dimension_scores["innovation_factor"] = await self._evaluate_innovation_factor(
            outline
        )

        return dimension_scores

    async def _evaluate_structure_completeness(self, outline: Dict[str, Any]) -> float:
        """评估结构完整性"""
        try:
            score = 5.0

            # 检查必要字段
            required_fields = ["main_plot", "volumes", "key_turning_points"]
            present_fields = sum(1 for field in required_fields if field in outline)
            score += (present_fields / len(required_fields)) * 3

            # 检查卷数合理性
            volumes = outline.get("volumes", [])
            if 2 <= len(volumes) <= 8:
                score += 2

            # 检查转折点数量
            turning_points = outline.get("key_turning_points", [])
            if len(turning_points) >= 3:
                score += 1

            return min(10.0, max(1.0, score))

        except Exception:
            return 5.0

    async def _evaluate_setting_consistency(
        self, outline: Dict[str, Any], world_setting: Dict[str, Any]
    ) -> float:
        """评估世界观一致性"""
        try:
            score = 5.0
            outline_text = json.dumps(outline, ensure_ascii=False)

            # 检查力量体系一致性
            power_system = world_setting.get("power_system", {})
            if power_system and power_system.get("name"):
                if power_system["name"] in outline_text:
                    score += 2

            # 检查势力一致性
            factions = world_setting.get("factions", [])
            faction_mentions = 0
            for faction in factions:
                if faction.get("name") and faction["name"] in outline_text:
                    faction_mentions += 1

            if faction_mentions > 0:
                score += min(2, faction_mentions * 0.5)

            # 检查地理环境一致性
            geography = world_setting.get("geography", {})
            if geography and any(loc in outline_text for loc in str(geography).split()):
                score += 1

            return min(10.0, max(1.0, score))

        except Exception:
            return 5.0

    async def _evaluate_character_coherence(
        self, outline: Dict[str, Any], characters: List[Dict[str, Any]]
    ) -> float:
        """评估角色连贯性"""
        try:
            score = 5.0
            outline_text = json.dumps(outline, ensure_ascii=False)

            # 检查主要角色的存在感
            main_characters = [
                c for c in characters if c.get("importance", "supporting") == "main"
            ]
            character_presence_score = 0

            for character in main_characters:
                name = character.get("name", "")
                if name:
                    mentions = outline_text.count(name)
                    if mentions >= 3:
                        character_presence_score += 1
                    elif mentions >= 1:
                        character_presence_score += 0.5

            score += min(3, character_presence_score)

            # 检查角色关系描述
            relationship_keywords = ["关系", "互动", "合作", "对抗", "情感"]
            relationship_score = sum(
                1 for keyword in relationship_keywords if keyword in outline_text
            )
            score += min(2, relationship_score * 0.4)

            return min(10.0, max(1.0, score))

        except Exception:
            return 5.0

    async def _evaluate_tension_management(self, outline: Dict[str, Any]) -> float:
        """评估张力节奏控制"""
        try:
            score = 5.0

            # 检查张力循环
            volumes = outline.get("volumes", [])
            total_cycles = 0

            for volume in volumes:
                cycles = volume.get("tension_cycles", [])
                total_cycles += len(cycles)

            # 评估循环密度
            avg_cycles = total_cycles / len(volumes) if volumes else 0
            if 1.0 <= avg_cycles <= 3.0:
                score += 3
            elif avg_cycles > 0:
                score += 1

            # 检查高潮安排
            climax_chapter = outline.get("climax_chapter")
            if climax_chapter and isinstance(climax_chapter, int):
                total_chapters = sum(vol.get("chapters", [0, 0])[1] for vol in volumes)
                climax_position = (
                    climax_chapter / total_chapters if total_chapters > 0 else 0
                )
                # 高潮应在70%-90%位置
                if 0.7 <= climax_position <= 0.9:
                    score += 2

            return min(10.0, max(1.0, score))

        except Exception:
            return 5.0

    async def _evaluate_logical_flow(self, outline: Dict[str, Any]) -> float:
        """评估逻辑连贯性"""
        try:
            score = 5.0
            outline_text = json.dumps(outline, ensure_ascii=False)

            # 检查因果关系词汇
            causal_words = ["因为", "所以", "由于", "因此", "导致", "引发", "结果"]
            causal_score = sum(1 for word in causal_words if word in outline_text)
            score += min(2, causal_score * 0.3)

            # 检查时间序列词汇
            temporal_words = ["首先", "然后", "接着", "最后", "之前", "之后", "同时"]
            temporal_score = sum(1 for word in temporal_words if word in outline_text)
            score += min(2, temporal_score * 0.3)

            # 检查逻辑连接词
            logical_connectors = [
                "但是",
                "然而",
                "不过",
                "尽管",
                "虽然",
                "而且",
                "此外",
            ]
            connector_score = sum(
                1 for word in logical_connectors if word in outline_text
            )
            score += min(1, connector_score * 0.2)

            return min(10.0, max(1.0, score))

        except Exception:
            return 5.0

    async def _evaluate_innovation_factor(self, outline: Dict[str, Any]) -> float:
        """评估创意新颖性"""
        try:
            score = 5.0
            outline_text = json.dumps(outline, ensure_ascii=False)

            # 检查独特设定词汇
            unique_words = ["独特", "创新", "前所未有", "突破", "颠覆", "原创"]
            unique_score = sum(1 for word in unique_words if word in outline_text)
            score += min(2, unique_score * 0.4)

            # 检查复杂情节词汇
            complex_words = ["复杂", "多线", "交错", "悬念", "反转", "意外"]
            complex_score = sum(1 for word in complex_words if word in outline_text)
            score += min(2, complex_score * 0.4)

            # 检查深度主题词汇
            depth_words = ["深刻", "哲理", "思考", "人性", "社会", "命运"]
            depth_score = sum(1 for word in depth_words if word in outline_text)
            score += min(1, depth_score * 0.2)

            return min(10.0, max(1.0, score))

        except Exception:
            return 5.0

    def _calculate_weighted_score(self, dimension_scores: Dict[str, float]) -> float:
        """计算加权综合评分"""
        total_score = 0.0
        total_weight = 0.0

        for dimension, score in dimension_scores.items():
            weight = self.dimensions[dimension]["weight"]
            total_score += score * weight
            total_weight += weight

        return total_score / total_weight if total_weight > 0 else 5.0

    def _identify_strengths(self, dimension_scores: Dict[str, float]) -> List[str]:
        """识别优势维度"""
        strengths = []
        for dimension, score in dimension_scores.items():
            if score >= 8.0:
                description = self.dimensions[dimension]["description"]
                strengths.append(f"{description} ({score:.1f}分)")
        return strengths

    def _identify_weaknesses(self, dimension_scores: Dict[str, float]) -> List[str]:
        """识别劣势维度"""
        weaknesses = []
        for dimension, score in dimension_scores.items():
            if score < 7.0:
                description = self.dimensions[dimension]["description"]
                weaknesses.append(f"{description} ({score:.1f}分)")
        return weaknesses

    async def _generate_improvement_suggestions(
        self,
        outline: Dict[str, Any],
        dimension_scores: Dict[str, float],
        weaknesses: List[str],
    ) -> List[Dict[str, Any]]:
        """生成改进建议"""
        suggestions = []

        # 基于低分维度生成具体建议
        for dimension, score in dimension_scores.items():
            if score < 7.0:
                criteria = self.dimensions[dimension]["criteria"]
                suggestions.append(
                    {
                        "type": dimension,
                        "priority": "high" if score < 6.0 else "medium",
                        "description": self.dimensions[dimension]["description"],
                        "specific_issues": [f"评分较低：{score:.1f}分"],
                        "improvement_directions": criteria[:2],  # 取前两个标准作为建议
                    }
                )

        # 基于大纲内容的通用建议
        if not outline.get("main_plot"):
            suggestions.append(
                {
                    "type": "structure",
                    "priority": "high",
                    "description": "缺少主线剧情定义",
                    "specific_issues": ["未定义主线剧情"],
                    "improvement_directions": ["补充主线剧情的起承转合结构"],
                }
            )

        if len(outline.get("volumes", [])) < 2:
            suggestions.append(
                {
                    "type": "structure",
                    "priority": "medium",
                    "description": "卷级结构过于简单",
                    "specific_issues": [f"仅有{len(outline.get('volumes', []))}卷"],
                    "improvement_directions": ["建议增加卷数以丰富故事层次"],
                }
            )

        return suggestions
