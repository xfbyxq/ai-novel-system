"""大纲审查反馈循环 - 确保情节架构的完整性和吸引力

通过 Architect-Reviewer 循环迭代，确保大纲具有：
- 结构完整性（清晰的起承转合）
- 节奏把控（张弛有度）
- 冲突张力（足够的戏剧冲突）
- 角色利用度（充分发挥角色作用）
- 伏笔设计（合理的铺垫和回收）
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient


@dataclass
class PlotQualityReport:
    """大纲质量评估报告"""

    overall_score: float = 0.0
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    passed: bool = False
    issues: List[Dict[str, Any]] = field(default_factory=list)
    structure_analysis: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores,
            "passed": self.passed,
            "issues": self.issues,
            "structure_analysis": self.structure_analysis,
            "summary": self.summary,
        }


@dataclass
class PlotReviewResult:
    """大纲审查循环的最终结果"""

    final_plot_outline: Dict[str, Any] = field(default_factory=dict)
    final_score: float = 0.0
    total_iterations: int = 0
    converged: bool = False
    iterations: List[Dict[str, Any]] = field(default_factory=list)
    quality_report: Optional[PlotQualityReport] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "final_score": self.final_score,
            "total_iterations": self.total_iterations,
            "converged": self.converged,
            "iterations": self.iterations,
        }


# ── 大纲审查专用提示词 ──────────────────────────────────────────

PLOT_REVIEWER_SYSTEM = """你是一位资深的网络小说情节架构评审专家，专注于大纲设计的完整性、节奏和吸引力。

你需要从以下维度严格评估大纲设计：

1. **结构完整性** (structure)：
   - 是否有清晰的开头、发展、高潮、结局？
   - 各卷之间是否有递进关系？
   - 主线是否贯穿始终？

2. **节奏把控** (pacing)：
   - 情节推进是否张弛有度？
   - 高潮点分布是否合理？
   - 是否有足够的"爽点"和"低谷"交替？

3. **冲突张力** (conflict)：
   - 核心冲突是否足够吸引人？
   - 每卷是否有独立的冲突？
   - 敌对势力是否有威胁感？

4. **角色利用度** (character_usage)：
   - 主要角色是否都有戏份？
   - 角色成长是否与情节紧密结合？
   - 配角和反派是否有发挥空间？

5. **伏笔设计** (foreshadowing)：
   - 是否有合理的伏笔铺垫？
   - 关键转折是否有预兆？
   - 是否有未来可回收的悬念？

【重要】评分原则：
- 你必须给出精确的评分，不要给出"安全"的中间分数
- 如果大纲结构完整且有吸引力，应给 8.0 以上
- 如果有明显问题未解决，应给 7.0 以下
- 评分应该反映真实质量，而不是折中

评分标准：
- 9-10分：卓越，结构精妙、节奏完美、引人入胜
- 8-9分：优秀，结构完整、节奏紧凑、冲突强烈
- 7-8分：良好，基本完整但有改进空间
- 6-7分：及格，存在明显问题需要修改
- 6分以下：不合格，需要大幅重做"""

PLOT_REVIEWER_TASK = """请对以下情节大纲进行全面质量评估。

{iteration_context}

世界观设定：
{world_setting}

角色设定：
{characters}

情节大纲：
{plot_outline}

请以JSON格式输出评估结果（不要输出其他内容）：
{{
    "overall_score": 综合评分(1-10浮点数，请给出精确分数如7.3、8.1等，不要总是给7.0或7.5这样的整数),
    "dimension_scores": {{
        "structure": 结构完整性分数,
        "pacing": 节奏把控分数,
        "conflict": 冲突张力分数,
        "character_usage": 角色利用度分数,
        "foreshadowing": 伏笔设计分数
    }},
    "improvement_assessment": {{
        "issues_resolved": ["已解决的问题"],
        "issues_remaining": ["仍存在的问题"],
        "new_issues": ["新发现的问题"],
        "improvement_score": 改进程度分数(1-10，仅在非首轮审查时填写)
    }},
    "structure_analysis": {{
        "opening_hook": "开篇吸引力评价",
        "climax_strength": "高潮张力评价",
        "ending_satisfaction": "结局满意度评价",
        "volume_balance": "各卷平衡性评价"
    }},
    "volume_assessments": [
        {{
            "volume_num": 卷号,
            "strengths": ["优点"],
            "weaknesses": ["问题"],
            "pacing_issue": "节奏问题（如有）"
        }}
    ],
    "unused_elements": {{
        "characters": ["未充分利用的角色"],
        "world_settings": ["未利用的世界观元素"],
        "potential_conflicts": ["潜在但未使用的冲突"]
    }},
    "critical_issues": [
        {{"area": "问题领域", "issue": "具体问题", "severity": "high/medium/low", "suggestion": "改进建议"}}
    ],
    "missing_elements": ["缺失的重要情节元素"],
    "summary": "整体评价（50字以内）"
}}"""

PLOT_REVISION_TASK = """你之前设计的情节大纲经过专家评审，需要优化。

评审评分：{score}/10

评审反馈：
{feedback}

发现的问题：
{issues}

结构分析：
{structure_analysis}

未充分利用的元素：
{unused_elements}

原情节大纲：
{original_plot}

世界观设定（供参考）：
{world_setting}

角色设定（供参考）：
{characters}

请根据评审意见优化情节大纲，重点解决以下问题：
1. 完善结构，确保有清晰的起承转合
2. 优化节奏，增加高潮点和悬念
3. 强化冲突，提升情节张力
4. 充分利用角色和世界观设定
5. 增加伏笔和悬念

请以JSON格式输出优化后的完整情节大纲：
{{
    "structure_type": "叙事结构类型",
    "main_plot": {{
        "core_conflict": "核心冲突（具体、有张力）",
        "resolution_path": "解决路径（有波折、不直线）",
        "theme": "主题",
        "central_question": "故事的核心问题（读者最想知道的答案）"
    }},
    "volumes": [
        {{
            "volume_num": 卷号,
            "title": "卷名",
            "summary": "本卷概要（100字）",
            "chapters_range": [起始章, 结束章],
            "volume_conflict": "本卷主要冲突",
            "key_events": ["关键事件1", "关键事件2", "关键事件3"],
            "power_level": "主角当前实力",
            "emotional_arc": "情感线发展",
            "cliffhanger": "本卷结尾悬念"
        }}
    ],
    "sub_plots": [
        {{"name": "支线名", "description": "描述", "involved_characters": ["角色名"], "resolution_volume": 解决卷号}}
    ],
    "key_turning_points": [
        {{"chapter": 章节号, "event": "转折事件", "impact": "对主角/剧情的影响", "foreshadowing_chapter": 伏笔章节号}}
    ],
    "foreshadowing_map": [
        {{"setup_chapter": 埋设章节, "payoff_chapter": 回收章节, "content": "伏笔内容"}}
    ],
    "climax_chapter": 全书最大高潮章节号,
    "hooks_and_mysteries": ["悬念和谜团（保持读者兴趣）"]
}}"""


class PlotReviewHandler:
    """情节大纲审查循环处理器

    流程：
    1. Architect 生成/修订大纲
    2. Reviewer 多维度评估 + 结构分析
    3. 如果 score < threshold 且未达上限 → 反馈给 Architect → 回到 1
    4. 返回最终大纲 + 迭代历史
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
        initial_plot_outline: Dict[str, Any],
        world_setting: Dict[str, Any],
        characters: List[Dict[str, Any]],
    ) -> PlotReviewResult:
        """执行情节大纲审查循环"""
        current_plot = initial_plot_outline
        result = PlotReviewResult()
        last_report: Optional[PlotQualityReport] = None
        previous_issues: List[str] = []

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"[PlotReview] 第 {iteration}/{self.max_iterations} 轮审查")

            # 获取上一轮评分
            previous_score = last_report.overall_score if last_report else 0

            # ── Reviewer 审查评分（带迭代上下文）──────────────────
            review_data = await self._reviewer_evaluate(
                plot_outline=current_plot,
                world_setting=world_setting,
                characters=characters,
                iteration=iteration,
                previous_score=previous_score,
                previous_issues=previous_issues,
            )

            score = float(review_data.get("overall_score", 0))
            critical_issues = review_data.get("critical_issues", [])
            structure_analysis = review_data.get("structure_analysis", {})

            last_report = PlotQualityReport(
                overall_score=score,
                dimension_scores=review_data.get("dimension_scores", {}),
                passed=score >= self.quality_threshold,
                issues=critical_issues,
                structure_analysis=structure_analysis,
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
                f"[PlotReview] score={score:.1f}, "
                f"passed={last_report.passed}, "
                f"issues={len(critical_issues)}"
            )

            if last_report.passed:
                logger.info("[PlotReview] 情节大纲质量达标")
                break

            if iteration >= self.max_iterations:
                logger.warning(f"[PlotReview] 达到最大迭代次数，当前评分 {score:.1f}")
                break

            # ── Architect 修订 ───────────────────────────────────
            logger.info("[PlotReview] 质量未达标，请求架构师修订...")

            feedback_lines = [f"整体评价：{last_report.summary}"]
            for dim, dim_score in last_report.dimension_scores.items():
                dim_names = {
                    "structure": "结构完整性",
                    "pacing": "节奏把控",
                    "conflict": "冲突张力",
                    "character_usage": "角色利用度",
                    "foreshadowing": "伏笔设计",
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

            # 添加各卷问题
            volume_assessments = review_data.get("volume_assessments", [])
            for va in volume_assessments:
                weaknesses = va.get("weaknesses", [])
                if weaknesses:
                    issues_lines.append(f"\n第{va.get('volume_num', '?')}卷问题：")
                    for w in weaknesses:
                        issues_lines.append(f"  - {w}")

            structure_text = json.dumps(structure_analysis, ensure_ascii=False, indent=2) if structure_analysis else "（无）"
            unused_elements = review_data.get("unused_elements", {})
            unused_text = json.dumps(unused_elements, ensure_ascii=False, indent=2) if unused_elements else "（无）"

            revised_plot = await self._architect_revise(
                score=score,
                feedback="\n".join(feedback_lines),
                issues="\n".join(issues_lines) or "（无具体问题）",
                structure_analysis=structure_text,
                unused_elements=unused_text,
                original_plot=current_plot,
                world_setting=world_setting,
                characters=characters,
            )

            if revised_plot and isinstance(revised_plot, dict) and (revised_plot.get("volumes") or revised_plot.get("main_plot")):
                current_plot = revised_plot
                # 收集本轮问题，供下一轮审查参考
                previous_issues = [
                    f"{issue.get('area', '')}: {issue.get('issue', '')}"
                    for issue in critical_issues
                ]
                # 添加缺失元素
                previous_issues.extend([f"缺失: {m}" for m in missing])
                # 添加各卷问题
                for va in volume_assessments:
                    vol_num = va.get("volume_num", "?")
                    for w in va.get("weaknesses", []):
                        previous_issues.append(f"第{vol_num}卷: {w}")
                logger.info("[PlotReview] 架构师修订完成")
            else:
                logger.warning("[PlotReview] 修订失败，保留原设计")
                break

        result.final_plot_outline = current_plot
        result.final_score = last_report.overall_score if last_report else 0
        result.total_iterations = len(result.iterations)
        result.converged = last_report.passed if last_report else False
        result.quality_report = last_report

        logger.info(
            f"[PlotReview] 完成: iterations={result.total_iterations}, "
            f"score={result.final_score:.1f}, converged={result.converged}"
        )
        return result

    async def _reviewer_evaluate(
        self,
        plot_outline: Dict[str, Any],
        world_setting: Dict[str, Any],
        characters: List[Dict[str, Any]],
        iteration: int = 1,
        previous_score: float = 0,
        previous_issues: List[str] = None,
    ) -> Dict[str, Any]:
        """调用 Reviewer 进行大纲评估
        
        Args:
            plot_outline: 情节大纲
            world_setting: 世界观设定
            characters: 角色列表
            iteration: 当前迭代轮次
            previous_score: 上一轮评分
            previous_issues: 上一轮发现的问题
        """
        # 构建迭代上下文
        if iteration == 1:
            iteration_context = "【首轮审查】这是情节大纲的首次评估。"
        else:
            issues_text = "\n".join(f"  - {issue}" for issue in (previous_issues or [])[:10])
            iteration_context = f"""【第 {iteration} 轮审查】
这是修订后的情节大纲，请评估修订效果。
上一轮评分：{previous_score}/10
上一轮发现的主要问题：
{issues_text or "  （无）"}

请重点评估：
1. 上述问题是否已解决？
2. 修订后是否引入了新问题？
3. 大纲整体质量是否有实质性提升？
如果问题已解决且没有新问题，应给予更高评分。"""

        task_prompt = PLOT_REVIEWER_TASK.format(
            iteration_context=iteration_context,
            world_setting=json.dumps(world_setting, ensure_ascii=False, indent=2)[:2000],
            characters=json.dumps(characters, ensure_ascii=False, indent=2)[:2000],
            plot_outline=json.dumps(plot_outline, ensure_ascii=False, indent=2),
        )

        try:
            response = await self.client.chat(
                prompt=task_prompt,
                system=PLOT_REVIEWER_SYSTEM,
                temperature=0.5,  # 稍微提高温度，避免固定评分
                max_tokens=4096,
            )
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="大纲审查员",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            return self._extract_json(response["content"])
        except Exception as e:
            logger.error(f"[PlotReview] Reviewer 评估失败: {e}")
            return {"overall_score": self.quality_threshold, "critical_issues": []}

    async def _architect_revise(
        self,
        score: float,
        feedback: str,
        issues: str,
        structure_analysis: str,
        unused_elements: str,
        original_plot: Dict[str, Any],
        world_setting: Dict[str, Any],
        characters: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """调用 Architect 修订大纲"""
        task_prompt = PLOT_REVISION_TASK.format(
            score=f"{score:.1f}",
            feedback=feedback,
            issues=issues,
            structure_analysis=structure_analysis,
            unused_elements=unused_elements,
            original_plot=json.dumps(original_plot, ensure_ascii=False, indent=2),
            world_setting=json.dumps(world_setting, ensure_ascii=False, indent=2)[:1500],
            characters=json.dumps(characters, ensure_ascii=False, indent=2)[:1500],
        )

        from llm.prompt_manager import PromptManager
        architect_system = PromptManager.PLOT_ARCHITECT_SYSTEM

        try:
            response = await self.client.chat(
                prompt=task_prompt,
                system=architect_system,
                temperature=0.7,
                max_tokens=6000,
            )
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="情节架构师(修订)",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            return self._extract_json(response["content"])
        except Exception as e:
            logger.error(f"[PlotReview] Architect 修订失败: {e}")
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

        # 尝试找 JSON 数组（大纲可能是卷列表）
        start = text.find("[")
        if start != -1:
            end = text.rfind("]")
            if end > start:
                try:
                    result = json.loads(text[start:end + 1])
                    # 包装为标准格式
                    return {"volumes": result, "structure_type": "multi_volume"}
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
