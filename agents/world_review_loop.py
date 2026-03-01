"""世界观审查反馈循环 - 确保世界观设计的深度和一致性

通过 Builder-Reviewer 循环迭代，确保世界观具有：
- 内在一致性（设定自洽）
- 深度与广度（足够的细节）
- 独特性与创新
- 可扩展性（支撑长期连载）
- 力量体系完整性
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient


@dataclass
class WorldQualityReport:
    """世界观质量评估报告"""

    overall_score: float = 0.0
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    passed: bool = False
    issues: List[Dict[str, Any]] = field(default_factory=list)
    consistency_analysis: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores,
            "passed": self.passed,
            "issues": self.issues,
            "consistency_analysis": self.consistency_analysis,
            "summary": self.summary,
        }


@dataclass
class WorldReviewResult:
    """世界观审查循环的最终结果"""

    final_world_setting: Dict[str, Any] = field(default_factory=dict)
    final_score: float = 0.0
    total_iterations: int = 0
    converged: bool = False
    iterations: List[Dict[str, Any]] = field(default_factory=list)
    quality_report: Optional[WorldQualityReport] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "final_score": self.final_score,
            "total_iterations": self.total_iterations,
            "converged": self.converged,
            "iterations": self.iterations,
        }


# ── 世界观审查专用提示词 ──────────────────────────────────────────

WORLD_REVIEWER_SYSTEM = """你是一位资深的网络小说世界观评审专家，专注于世界观设计的深度、一致性和创新性。

你需要从以下维度严格评估世界观设计：

1. **内在一致性** (consistency)：
   - 各个设定之间是否自洽？
   - 力量体系与世界规则是否矛盾？
   - 历史事件与当前状态是否匹配？

2. **深度与广度** (depth_breadth)：
   - 力量体系是否有足够的层次和细节？
   - 地理设定是否丰富且有特色？
   - 势力组织是否有清晰的架构和关系？

3. **独特性** (uniqueness)：
   - 是否有独特的世界观元素？
   - 是否避免了常见套路和模板化？
   - 创新点是否足以吸引读者？

4. **可扩展性** (expandability)：
   - 世界观是否有足够的发展空间？
   - 是否预留了未探索的区域和势力？
   - 力量体系是否有上升空间？

5. **力量体系完整性** (power_system)：
   - 等级划分是否清晰合理？
   - 升级机制是否有逻辑？
   - 是否有明确的能力上限和限制？

评分标准：
- 8-10分：优秀，世界观完整、一致、有创新
- 6-8分：良好，但有改进空间
- 4-6分：及格，存在明显问题
- 4分以下：不合格，需要大幅修改"""

WORLD_REVIEWER_TASK = """请对以下世界观设计进行全面质量评估。

题材信息：
{topic_analysis}

世界观设定：
{world_setting}

请以JSON格式输出评估结果（不要输出其他内容）：
{{
    "overall_score": 综合评分(1-10浮点数),
    "dimension_scores": {{
        "consistency": 内在一致性分数,
        "depth_breadth": 深度与广度分数,
        "uniqueness": 独特性分数,
        "expandability": 可扩展性分数,
        "power_system": 力量体系完整性分数
    }},
    "consistency_analysis": {{
        "contradictions": ["发现的矛盾点"],
        "logic_gaps": ["逻辑漏洞"],
        "timeline_issues": ["时间线问题"]
    }},
    "strengths": ["世界观的优点"],
    "weaknesses": ["世界观的问题"],
    "missing_elements": ["缺失的重要元素"],
    "critical_issues": [
        {{"area": "问题领域", "issue": "具体问题", "severity": "high/medium/low", "suggestion": "改进建议"}}
    ],
    "summary": "整体评价（50字以内）"
}}"""

WORLD_REVISION_TASK = """你之前设计的世界观经过专家评审，需要优化。

评审评分：{score}/10

评审反馈：
{feedback}

发现的问题：
{issues}

一致性分析：
{consistency_analysis}

原世界观设定：
{original_world}

题材信息（供参考）：
{topic_analysis}

请根据评审意见优化世界观设计，重点解决以下问题：
1. 修复逻辑矛盾和设定冲突
2. 补充缺失的重要元素
3. 增加世界观的深度和独特性
4. 完善力量体系的细节

请以JSON格式输出优化后的完整世界观：
{{
    "world_name": "世界名称",
    "world_type": "世界类型",
    "core_concept": "核心概念（一句话描述世界的独特之处）",
    "power_system": {{
        "name": "体系名称",
        "core_principle": "核心原理（修炼/升级的底层逻辑）",
        "levels": [
            {{"level": 1, "name": "等级名", "description": "描述", "typical_abilities": ["能力"], "breakthrough_condition": "突破条件"}}
        ],
        "special_abilities": ["特殊能力类型"],
        "limitations": ["体系限制和代价"],
        "unique_elements": ["独特元素"]
    }},
    "geography": {{
        "overview": "地理概述",
        "major_regions": [
            {{"name": "地名", "description": "描述", "importance": "重要性", "unique_feature": "独特特征", "controlling_force": "控制势力"}}
        ],
        "unexplored_areas": ["未探索区域（为后续剧情预留）"]
    }},
    "factions": [
        {{"name": "势力名", "type": "类型", "description": "描述", "power_level": "实力等级", "internal_conflicts": "内部矛盾", "external_relations": "外部关系"}}
    ],
    "rules": ["世界规则（不可违背的底层法则）"],
    "timeline": [
        {{"era": "时代", "event": "事件", "impact": "影响", "related_mysteries": "相关谜团"}}
    ],
    "special_elements": ["特殊元素"],
    "mysteries": ["未解之谜（可作为后续剧情钩子）"],
    "taboos": ["禁忌或危险区域"]
}}"""


class WorldReviewHandler:
    """世界观设计审查循环处理器

    流程：
    1. Builder 生成/修订世界观
    2. Reviewer 多维度评估 + 一致性检查
    3. 如果 score < threshold 且未达上限 → 反馈给 Builder → 回到 1
    4. 返回最终世界观 + 迭代历史
    """

    def __init__(
        self,
        client: QwenClient,
        cost_tracker: CostTracker,
        quality_threshold: float = 7.0,
        max_iterations: int = 2,
    ):
        self.client = client
        self.cost_tracker = cost_tracker
        self.quality_threshold = quality_threshold
        self.max_iterations = max_iterations

    async def execute(
        self,
        initial_world_setting: Dict[str, Any],
        topic_analysis: Dict[str, Any],
    ) -> WorldReviewResult:
        """执行世界观设计审查循环"""
        current_world = initial_world_setting
        result = WorldReviewResult()
        last_report: Optional[WorldQualityReport] = None

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"[WorldReview] 第 {iteration}/{self.max_iterations} 轮审查")

            # ── Reviewer 审查评分 ──────────────────────────────
            review_data = await self._reviewer_evaluate(
                world_setting=current_world,
                topic_analysis=topic_analysis,
            )

            score = float(review_data.get("overall_score", 0))
            critical_issues = review_data.get("critical_issues", [])
            consistency_analysis = review_data.get("consistency_analysis", {})

            last_report = WorldQualityReport(
                overall_score=score,
                dimension_scores=review_data.get("dimension_scores", {}),
                passed=score >= self.quality_threshold,
                issues=critical_issues,
                consistency_analysis=consistency_analysis,
                summary=review_data.get("summary", ""),
            )

            result.iterations.append({
                "iteration": iteration,
                "score": score,
                "passed": last_report.passed,
                "issue_count": len(critical_issues),
                "dimension_scores": last_report.dimension_scores,
            })

            logger.info(
                f"[WorldReview] score={score:.1f}, "
                f"passed={last_report.passed}, "
                f"issues={len(critical_issues)}"
            )

            if last_report.passed:
                logger.info("[WorldReview] 世界观设计质量达标")
                break

            if iteration >= self.max_iterations:
                logger.warning(f"[WorldReview] 达到最大迭代次数，当前评分 {score:.1f}")
                break

            # ── Builder 修订 ───────────────────────────────────
            logger.info("[WorldReview] 质量未达标，请求架构师修订...")

            feedback_lines = [f"整体评价：{last_report.summary}"]
            for dim, dim_score in last_report.dimension_scores.items():
                dim_names = {
                    "consistency": "内在一致性",
                    "depth_breadth": "深度与广度",
                    "uniqueness": "独特性",
                    "expandability": "可扩展性",
                    "power_system": "力量体系完整性",
                }
                feedback_lines.append(f"- {dim_names.get(dim, dim)}: {dim_score}/10")

            issues_lines = []
            for issue in critical_issues:
                area = issue.get("area", "")
                desc = issue.get("issue", "")
                severity = issue.get("severity", "medium")
                suggestion = issue.get("suggestion", "")
                issues_lines.append(f"[{severity.upper()}] {area}: {desc}")
                if suggestion:
                    issues_lines.append(f"  建议: {suggestion}")

            # 添加缺失元素
            missing = review_data.get("missing_elements", [])
            if missing:
                issues_lines.append("\n缺失的重要元素：")
                for m in missing:
                    issues_lines.append(f"  - {m}")

            consistency_text = json.dumps(consistency_analysis, ensure_ascii=False, indent=2) if consistency_analysis else "（无）"

            revised_world = await self._builder_revise(
                score=score,
                feedback="\n".join(feedback_lines),
                issues="\n".join(issues_lines) or "（无具体问题）",
                consistency_analysis=consistency_text,
                original_world=current_world,
                topic_analysis=topic_analysis,
            )

            if revised_world and isinstance(revised_world, dict) and revised_world.get("world_name"):
                current_world = revised_world
                logger.info("[WorldReview] 架构师修订完成")
            else:
                logger.warning("[WorldReview] 修订失败，保留原设计")
                break

        result.final_world_setting = current_world
        result.final_score = last_report.overall_score if last_report else 0
        result.total_iterations = len(result.iterations)
        result.converged = last_report.passed if last_report else False
        result.quality_report = last_report

        logger.info(
            f"[WorldReview] 完成: iterations={result.total_iterations}, "
            f"score={result.final_score:.1f}, converged={result.converged}"
        )
        return result

    async def _reviewer_evaluate(
        self,
        world_setting: Dict[str, Any],
        topic_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """调用 Reviewer 进行世界观评估"""
        task_prompt = WORLD_REVIEWER_TASK.format(
            topic_analysis=json.dumps(topic_analysis, ensure_ascii=False, indent=2),
            world_setting=json.dumps(world_setting, ensure_ascii=False, indent=2),
        )

        try:
            response = await self.client.chat(
                prompt=task_prompt,
                system=WORLD_REVIEWER_SYSTEM,
                temperature=0.4,
                max_tokens=4096,
            )
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="世界观审查员",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            return self._extract_json(response["content"])
        except Exception as e:
            logger.error(f"[WorldReview] Reviewer 评估失败: {e}")
            return {"overall_score": self.quality_threshold, "critical_issues": []}

    async def _builder_revise(
        self,
        score: float,
        feedback: str,
        issues: str,
        consistency_analysis: str,
        original_world: Dict[str, Any],
        topic_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """调用 Builder 修订世界观"""
        task_prompt = WORLD_REVISION_TASK.format(
            score=f"{score:.1f}",
            feedback=feedback,
            issues=issues,
            consistency_analysis=consistency_analysis,
            original_world=json.dumps(original_world, ensure_ascii=False, indent=2),
            topic_analysis=json.dumps(topic_analysis, ensure_ascii=False, indent=2)[:1500],
        )

        from llm.prompt_manager import PromptManager
        builder_system = PromptManager.WORLD_BUILDER_SYSTEM

        try:
            response = await self.client.chat(
                prompt=task_prompt,
                system=builder_system,
                temperature=0.7,
                max_tokens=6000,
            )
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="世界观架构师(修订)",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            return self._extract_json(response["content"])
        except Exception as e:
            logger.error(f"[WorldReview] Builder 修订失败: {e}")
            return {}

    @staticmethod
    def _extract_json(text: str) -> Any:
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
        if start != -1:
            end = text.rfind("}")
            if end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass

        raise ValueError(f"无法从响应中提取 JSON: {text[:200]}...")
