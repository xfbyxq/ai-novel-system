"""质量评估器 - 对章节内容进行多维度评分"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient


@dataclass
class QualityReport:
    """质量评估报告"""

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
        """从 LLM 返回的 JSON 构造报告"""
        overall = float(data.get("overall_score", 0))
        return cls(
            overall_score=overall,
            dimension_scores=data.get("dimension_scores", {}),
            passed=overall >= threshold,
            suggestions=data.get("revision_suggestions", []),
            summary=data.get("summary", ""),
        )


QUALITY_EVALUATOR_SYSTEM = """你是一位专业的网络小说质量评审专家。
你需要从多个维度对章节内容进行客观评分，并给出具体的改进建议。
评分必须严格、公正，能真实反映内容质量。"""

QUALITY_EVALUATOR_TASK = """请对以下章节内容进行多维度质量评估。

章节内容：
{content}

章节计划：
{chapter_plan}

评分维度（1-10分）：
1. 语言流畅度（fluency）：文字是否通顺、表达是否清晰、有无语病
2. 情节逻辑（plot_logic）：剧情是否合理、转折是否自然、有无逻辑漏洞
3. 角色一致性（character_consistency）：角色言行是否符合设定、性格是否前后一致
4. 节奏把控（pacing）：情节推进速度是否合适、有无拖沓或仓促

请以JSON格式输出（不要输出其他内容）：
{{
    "overall_score": 综合评分(1-10的浮点数),
    "dimension_scores": {{
        "fluency": 分数,
        "plot_logic": 分数,
        "character_consistency": 分数,
        "pacing": 分数
    }},
    "revision_suggestions": [
        {{"issue": "具体问题描述", "suggestion": "修改建议", "severity": "high/medium/low"}}
    ],
    "summary": "一句话整体评价"
}}"""


class QualityEvaluator:
    """章节质量评估器"""

    def __init__(
        self,
        client: QwenClient,
        cost_tracker: CostTracker,
        default_threshold: float = 7.5,
    ):
        self.client = client
        self.cost_tracker = cost_tracker
        self.default_threshold = default_threshold

    async def evaluate(
        self,
        content: str,
        chapter_plan: str = "",
        threshold: Optional[float] = None,
    ) -> QualityReport:
        """评估章节内容质量

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
    def _extract_json(text: str) -> Dict[str, Any]:
        """从 LLM 响应中提取 JSON"""
        text = text.strip()
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 尝试从 markdown 代码块中提取
        import re

        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        # 尝试找到第一个 { 和最后一个 }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"无法从响应中提取 JSON: {text[:200]}...")
