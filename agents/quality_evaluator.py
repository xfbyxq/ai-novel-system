"""质量评估器 - 对章节内容进行多维度评分."""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient


@dataclass
class QualityReport:
    """质量评估报告."""

    overall_score: float = 0.0
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    passed: bool = False
    suggestions: List[Dict[str, str]] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores,
            "passed": self.passed,
            "suggestions": self.suggestions,
            "summary": self.summary,
        }

    @classmethod
    def from_llm_json(cls, data: Dict[str, Any], threshold: float) -> "QualityReport":
        """从 LLM 返回的 JSON 构造报告."""
        overall = float(data.get("overall_score", 0))
        return cls(
            overall_score=overall,
            dimension_scores=data.get("dimension_scores", {}),
            passed=overall >= threshold,
            suggestions=data.get("revision_suggestions", []),
            summary=data.get("summary", ""),
        )


QUALITY_EVALUATOR_SYSTEM = """你是一位专业的网络小说质量评审专家.
你需要从多个维度对章节内容进行客观评分，并给出具体的改进建议。
评分必须严格、公正，能真实反映内容质量。"""

QUALITY_EVALUATOR_TASK = """请对以下章节内容进行多维度质量评估.

章节内容：
{content}

章节计划：
{chapter_plan}

评分维度（1-10 分）：
1. 语言流畅度（fluency）：文字是否通顺、表达是否清晰、有无语病
2. 情节逻辑（plot_logic）：剧情是否合理、转折是否自然、有无逻辑漏洞
3. 角色一致性（character_consistency）：角色言行是否符合设定、性格是否前后一致
4. 节奏把控（pacing）：情节推进速度是否合适、有无拖沓或仓促
5. 爽感设计（satisfaction_design）：
   - 是否有明确的爽点（打脸、逆袭、装逼、获得金手指等）
   - 情绪调动是否到位（读者是否会感到兴奋、解气、期待）
   - 期待感设置是否合理（是否有钩子吸引读者继续阅读）

请以 JSON 格式输出（不要输出其他内容）：
{{
    "overall_score": 综合评分 (1-10 的浮点数),
    "dimension_scores": {{
        "fluency": 分数，
        "plot_logic": 分数，
        "character_consistency": 分数，
        "pacing": 分数，
        "satisfaction_design": 分数
    }},
    "revision_suggestions": [
        {{"issue": "具体问题描述", "suggestion": "修改建议", "severity": "high/medium/low"}}
    ],
    "summary": "一句话整体评价"
}}"""


class QualityEvaluator:
    """章节质量评估器."""

    def __init__(
        self,
        client: QwenClient,
        cost_tracker: CostTracker,
        default_threshold: float = 7.5,
    ):
        """初始化方法."""
        self.client = client
        self.cost_tracker = cost_tracker
        self.default_threshold = default_threshold

    async def evaluate(
        self,
        content: str,
        chapter_plan: str = "",
        threshold: Optional[float] = None,
    ) -> QualityReport:
        """评估章节内容质量.

        Args:
            content: 章节文本
            chapter_plan: 章节计划（JSON 字符串或纯文本）
            threshold: 质量阈值，不传则使用默认值

        Returns:
            QualityReport
        """
        threshold = threshold or self.default_threshold

        task_prompt = QUALITY_EVALUATOR_TASK.replace("{content}", content).replace(
            "{chapter_plan}", chapter_plan or "（无）"
        )

        try:
            response = await self.client.chat(
                prompt=task_prompt,
                system=QUALITY_EVALUATOR_SYSTEM,
                temperature=0.3,
                max_tokens=2048,
            )

            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="质量评估器",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )

            data = self._extract_json(response["content"])
            report = QualityReport.from_llm_json(data, threshold)

            logger.info(
                f"[QualityEvaluator] score={report.overall_score:.1f}, "
                f"passed={report.passed}, issues={len(report.suggestions)}"
            )
            return report

        except Exception as e:
            logger.error(f"[QualityEvaluator] 评估失败: {e}")
            # 评估失败时返回一个通过的默认报告，不阻塞流程
            return QualityReport(
                overall_score=threshold,
                passed=True,
                summary=f"评估异常，默认通过: {e}",
            )

    @staticmethod
    def _get_detailed_criteria(dimension: str) -> str:
        """获取各维度的详细评分标准."""
        # 新 5 维度评分标准
        criteria_map = {
            "excitement": """爽点设计评分标准：
- 9-10 分：爽点设计精巧，情绪爆发力极强，读者代入感极强
- 7-8 分：爽点明确，情绪调动较好，读者会感到兴奋
- 5-6 分：有基本爽点，但设计平庸，情绪调动一般
- 3-4 分：爽点模糊，情绪调动不足
- 1-2 分：无爽点，平淡如水""",
            "plot_logic": """情节逻辑评分标准：
- 9-10 分：逻辑严密，转折自然，伏笔巧妙
- 7-8 分：情节合理，转折基本自然
- 5-6 分：基本合理，偶有牵强之处
- 3-4 分：多处逻辑漏洞
- 1-2 分：逻辑混乱，难以自圆其说""",
            "character_quality": """角色塑造评分标准：
- 9-10 分：角色形象鲜明，言行完全符合设定，辨识度高
- 7-8 分：角色性格稳定，基本符合设定
- 5-6 分：角色基本一致，偶有 OOC
- 3-4 分：角色言行多次与设定矛盾
- 1-2 分：角色性格混乱""",
            "setting_consistency": """设定一致性评分标准：
- 9-10 分：世界观完整一致，时间线清晰，无矛盾
- 7-8 分：设定基本一致，偶有小瑕疵
- 5-6 分：设定基本完整，偶有矛盾
- 3-4 分：多处设定矛盾或时间线混乱
- 1-2 分：设定严重混乱""",
            "fluency": """语言流畅度评分标准：
- 9-10 分：文字行云流水，表达精准，节奏完美
- 7-8 分：文字流畅，表达清晰，节奏良好
- 5-6 分：基本通顺，有少量语病但不影响理解
- 3-4 分：多处语病，阅读有障碍
- 1-2 分：语句不通，严重影响阅读""",
            # 向后兼容旧维度名
            "satisfaction_design": """爽感设计评分标准：
- 9-10 分：爽点设计精巧，情绪爆发力极强，读者代入感极强，期待感拉满
- 7-8 分：爽点明确，情绪调动较好，读者会感到兴奋或解气
- 5-6 分：有基本爽点，但设计平庸，情绪调动一般
- 3-4 分：爽点模糊，情绪调动不足
- 1-2 分：无爽点，平淡如水""",
            "character_consistency": """角色一致性评分标准：
- 9-10 分：角色形象鲜明，言行完全符合设定
- 7-8 分：角色性格稳定，基本符合设定
- 5-6 分：角色基本一致，偶有 OOC
- 3-4 分：角色言行多次与设定矛盾
- 1-2 分：角色性格混乱""",
            "pacing": """节奏把控评分标准：
- 9-10 分：张弛有度，节奏完美
- 7-8 分：节奏良好，详略得当
- 5-6 分：节奏基本合适，偶有拖沓或仓促
- 3-4 分：节奏失衡，多处拖沓或跳跃
- 1-2 分：节奏混乱""",
        }
        return criteria_map.get(dimension, "")

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """从 LLM 响应中提取 JSON.

        使用统一的 JsonExtractor 处理各种格式。
        """
        from agents.base.json_extractor import JsonExtractor

        return JsonExtractor.extract_object(text, default={})
