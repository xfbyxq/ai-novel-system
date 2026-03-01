"""审查反馈循环 - Writer 与 Editor 间的质量驱动迭代"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient

from agents.iteration_controller import IterationController
from agents.quality_evaluator import QualityEvaluator, QualityReport
from agents.team_context import AgentReview, NovelTeamContext


@dataclass
class ReviewLoopResult:
    """审查反馈循环的最终结果"""

    final_content: str = ""
    final_score: float = 0.0
    total_iterations: int = 0
    converged: bool = False
    iterations: List[Dict[str, Any]] = field(default_factory=list)
    quality_report: Optional[QualityReport] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "final_score": self.final_score,
            "total_iterations": self.total_iterations,
            "converged": self.converged,
            "iterations": self.iterations,
        }


# ── 审查专用提示词 ──────────────────────────────────────────

EDITOR_REVIEW_SYSTEM = """你是一位资深的网络小说编辑，负责审查章节内容并给出详细评分和润色。

你的工作包含两个部分：
1. 对内容进行多维度评分
2. 润色并输出修改后的完整内容

评分维度（1-10分）：
- fluency：语言流畅度
- plot_logic：情节逻辑
- character_consistency：角色一致性
- pacing：节奏把控"""

EDITOR_REVIEW_TASK = """请审查并润色以下章节内容。

原文：
{draft_content}

章节信息：
- 章节号：第{chapter_number}章
- 标题：{chapter_title}
- 章节目标：{chapter_summary}

请以JSON格式输出（不要输出其他内容）：
{{
    "overall_score": 综合评分(1-10浮点数),
    "dimension_scores": {{
        "fluency": 分数,
        "plot_logic": 分数,
        "character_consistency": 分数,
        "pacing": 分数
    }},
    "revision_suggestions": [
        {{"issue": "问题描述", "suggestion": "修改建议", "severity": "high/medium/low"}}
    ],
    "edited_content": "润色后的完整章节内容"
}}"""

WRITER_REVISION_TASK = """你之前写的第{chapter_number}章（{chapter_title}）经过编辑审查，需要修订。

编辑评分：{score}/10
编辑反馈：
{suggestions}

你的上一版内容：
{previous_content}

章节计划：
{chapter_plan}

请根据编辑的反馈修订内容，重点解决指出的问题。
直接输出修订后的完整章节内容，不要输出JSON或其他格式标记。"""


class ReviewLoopHandler:
    """Writer-Editor 审查反馈循环处理器

    流程：
    1. Writer 生成/修订内容
    2. Editor 审查 + 评分 + 润色
    3. 如果 score < threshold 且未达上限 → 将 suggestions 注入 Writer prompt → 回到 1
    4. 返回最终内容 + 迭代历史
    """

    def __init__(
        self,
        client: QwenClient,
        cost_tracker: CostTracker,
        quality_threshold: float = 7.5,
        max_iterations: int = 3,
    ):
        self.client = client
        self.cost_tracker = cost_tracker
        self.quality_threshold = quality_threshold
        self.max_iterations = max_iterations

    async def execute(
        self,
        initial_draft: str,
        chapter_number: int,
        chapter_title: str,
        chapter_summary: str,
        chapter_plan_json: str,
        writer_system_prompt: str,
        team_context: Optional[NovelTeamContext] = None,
    ) -> ReviewLoopResult:
        """执行 Writer-Editor 反馈循环

        Args:
            initial_draft: Writer 的首版初稿
            chapter_number: 章节号
            chapter_title: 章节标题
            chapter_summary: 章节概要
            chapter_plan_json: 章节计划 JSON 字符串
            writer_system_prompt: Writer 的 system prompt（含风格）
            team_context: 团队上下文（可选，用于记录审查反馈）

        Returns:
            ReviewLoopResult
        """
        controller = IterationController(
            quality_threshold=self.quality_threshold,
            max_iterations=self.max_iterations,
        )

        current_content = initial_draft
        result = ReviewLoopResult()
        last_report: Optional[QualityReport] = None

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"[ReviewLoop] 第 {iteration}/{self.max_iterations} 轮审查")

            # ── Editor 审查 + 评分 + 润色 ──────────────────────
            review_data = await self._editor_review(
                content=current_content,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                chapter_summary=chapter_summary,
            )

            score = float(review_data.get("overall_score", 0))
            suggestions = review_data.get("revision_suggestions", [])
            edited_content = review_data.get("edited_content", "")

            # 如果 Editor 返回了润色后的内容，使用它
            if edited_content and len(edited_content) > len(current_content) * 0.5:
                current_content = edited_content

            # 构造 QualityReport
            last_report = QualityReport(
                overall_score=score,
                dimension_scores=review_data.get("dimension_scores", {}),
                passed=score >= self.quality_threshold,
                suggestions=suggestions,
                summary=review_data.get("summary", ""),
            )

            # 记录到 TeamContext
            if team_context:
                review = AgentReview(
                    reviewer="编辑",
                    target_agent="作家",
                    task_desc=f"第{chapter_number}章-第{iteration}轮审查",
                    score=score,
                    passed=last_report.passed,
                    suggestions=suggestions,
                    chapter_number=chapter_number,
                )
                team_context.add_review(review)
                team_context.add_iteration_log({
                    "type": "review_loop",
                    "chapter": chapter_number,
                    "iteration": iteration,
                    "score": score,
                    "passed": last_report.passed,
                    "suggestion_count": len(suggestions),
                })

            # 记录到结果
            result.iterations.append({
                "iteration": iteration,
                "score": score,
                "passed": last_report.passed,
                "suggestion_count": len(suggestions),
                "dimension_scores": last_report.dimension_scores,
            })

            prev_score = result.iterations[-2]["score"] if len(result.iterations) > 1 else 0
            logger.info(
                f"[ReviewLoop] score={score:.1f}"
                + (f" (prev={prev_score:.1f})" if prev_score else "")
                + f", passed={last_report.passed}"
            )

            # ── 判断是否继续迭代 ──────────────────────────────
            if not controller.should_continue(score, iteration):
                break

            # ── Writer 修订 ───────────────────────────────────
            logger.info(f"[ReviewLoop] 质量未达标，请求 Writer 修订...")
            suggestions_text = "\n".join(
                f"- [{s.get('severity', 'medium')}] {s.get('issue', '')}: {s.get('suggestion', '')}"
                for s in suggestions
            )

            revision_prompt = WRITER_REVISION_TASK.format(
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                score=score,
                suggestions=suggestions_text or "（无具体建议）",
                previous_content=current_content,
                chapter_plan=chapter_plan_json,
            )

            try:
                revision_response = await self.client.chat(
                    prompt=revision_prompt,
                    system=writer_system_prompt,
                    temperature=0.75,
                    max_tokens=4096,
                )
                usage = revision_response["usage"]
                self.cost_tracker.record(
                    agent_name="作家(修订)",
                    prompt_tokens=usage["prompt_tokens"],
                    completion_tokens=usage["completion_tokens"],
                )
                revised = revision_response["content"]
                if revised and len(revised) > len(current_content) * 0.3:
                    current_content = revised
                    logger.info(f"[ReviewLoop] Writer 修订完成，{len(revised)} 字符")
            except Exception as e:
                logger.error(f"[ReviewLoop] Writer 修订失败: {e}")
                break

        # 组装最终结果
        result.final_content = current_content
        result.final_score = last_report.overall_score if last_report else 0
        result.total_iterations = len(result.iterations)
        result.converged = last_report.passed if last_report else False
        result.quality_report = last_report

        logger.info(
            f"[ReviewLoop] 完成: iterations={result.total_iterations}, "
            f"score={result.final_score:.1f}, converged={result.converged}"
        )
        return result

    async def _editor_review(
        self,
        content: str,
        chapter_number: int,
        chapter_title: str,
        chapter_summary: str,
    ) -> Dict[str, Any]:
        """调用 Editor 进行审查评分+润色"""
        task_prompt = EDITOR_REVIEW_TASK.format(
            draft_content=content,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_summary=chapter_summary,
        )

        try:
            response = await self.client.chat(
                prompt=task_prompt,
                system=EDITOR_REVIEW_SYSTEM,
                temperature=0.5,
                max_tokens=6144,
            )
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="编辑(审查)",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            return self._extract_json(response["content"])
        except Exception as e:
            logger.error(f"[ReviewLoop] Editor 审查失败: {e}")
            return {"overall_score": self.quality_threshold, "revision_suggestions": []}

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """从 LLM 响应中提取 JSON"""
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        import re

        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"无法从 Editor 响应中提取 JSON: {text[:200]}...")
