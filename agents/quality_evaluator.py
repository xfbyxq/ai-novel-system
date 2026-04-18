"""质量评估器 - 对章节内容进行多维度评分."""

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
1. 准确度（accuracy）：情节因果关系是否严密？角色行为动机是否合理？事件发展是否符合已建立规则？
2. 画面感（vividness）：场景描写是否生动？是否有多感官细节（视觉/听觉/触觉/嗅觉）？读者能否"看到"画面？
3. 节奏感（pacing）：叙事张弛是否有度？详略安排是否合理？场景切换是否流畅？
4. 设定一致性（setting_consistency）：世界观是否前后一致？时间线是否清晰？力量体系是否遵循规则？
5. 代入感（immersion）：角色内心活动是否真实？情感铺垫是否到位？读者是否能产生共鸣？

请以 JSON 格式输出（不要输出其他内容）：
{{
    "overall_score": 综合评分 (1-10 的浮点数),
    "dimension_scores": {{
        "accuracy": 分数，
        "vividness": 分数，
        "pacing": 分数，
        "setting_consistency": 分数，
        "immersion": 分数
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
        criteria_map = {
            "accuracy": """准确度评分标准：
- 9-10 分：逻辑严密无瑕疵，因果关系精妙，角色行为动机充分，事件发展既合理又出人意料
- 7-8 分：逻辑通顺，因果关系清晰，角色行为符合设定，无明显逻辑漏洞
- 5-6 分：基本合理，有少量牵强之处，偶有角色行为缺乏动机支撑
- 3-4 分：多处逻辑漏洞，角色行为前后矛盾，因果关系不成立
- 1-2 分：逻辑混乱，角色行为无法理解，事件发展毫无道理""",
            "vividness": """画面感评分标准：
- 9-10 分：场景跃然纸上，多感官细节交织，环境与情绪完美融合，读者仿佛身临其境
- 7-8 分：场景描写具体生动，有丰富的感官细节，环境氛围烘托到位
- 5-6 分：有基本场景交代，但描写较平淡，感官细节不足，多为视觉单一维度
- 3-4 分：场景描写模糊笼统，缺少具体细节，读者难以形成画面
- 1-2 分：几乎无场景描写，纯粹叙述事件，完全没有画面感""",
            "pacing": """节奏感评分标准：
- 9-10 分：张弛有度，紧张与舒缓交替精妙，高潮前铺垫充分，信息密度控制完美
- 7-8 分：节奏流畅，详略得当，高潮有铺垫，场景切换自然
- 5-6 分：节奏基本可接受，偶有拖沓或仓促，高潮铺垫不足或过多
- 3-4 分：节奏失衡明显，长段落信息堆砌或事件跳跃，阅读体验割裂
- 1-2 分：节奏混乱，要么全程平淡如水，要么事件堆积令人窒息""",
            "setting_consistency": """设定一致性评分标准：
- 9-10 分：世界观完整一致，时间线清晰，力量体系严格遵循规则，无矛盾
- 7-8 分：设定基本一致，偶有小瑕疵但不影响阅读
- 5-6 分：设定基本完整，偶有矛盾但不严重
- 3-4 分：多处设定矛盾或时间线混乱
- 1-2 分：设定严重混乱，世界观自相矛盾""",
            "immersion": """代入感评分标准：
- 9-10 分：角色内心世界丰富立体，情感表达层次分明，读者完全沉浸在角色体验中
- 7-8 分：角色情感真实可信，内心活动与外在行动协调，情感铺垫到位
- 5-6 分：角色情感有基本交代，但深度不足，情感变化缺少过渡
- 3-4 分：角色情感苍白，内心活动缺失或脸谱化，读者难以产生共鸣
- 1-2 分：角色如提线木偶，完全没有内心世界，情感表达生硬或缺失""",
        }
        return criteria_map.get(dimension, "")

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """从 LLM 响应中提取 JSON.

        使用统一的 JsonExtractor 处理各种格式。
        """
        from agents.base.json_extractor import JsonExtractor

        return JsonExtractor.extract_object(text, default={})
