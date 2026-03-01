"""角色审查反馈循环 - 确保角色设计的深度和质量

通过 Designer-Reviewer 循环迭代，确保角色具有：
- 心理深度和内在矛盾
- 独特性（与其他角色区分）
- 成长弧线的合理性
- 关系网络的复杂性
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient


@dataclass
class CharacterQualityReport:
    """角色质量评估报告"""

    overall_score: float = 0.0
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    passed: bool = False
    issues: List[Dict[str, Any]] = field(default_factory=list)
    uniqueness_analysis: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores,
            "passed": self.passed,
            "issues": self.issues,
            "uniqueness_analysis": self.uniqueness_analysis,
            "summary": self.summary,
        }


@dataclass
class CharacterReviewResult:
    """角色审查循环的最终结果"""

    final_characters: List[Dict[str, Any]] = field(default_factory=list)
    final_score: float = 0.0
    total_iterations: int = 0
    converged: bool = False
    iterations: List[Dict[str, Any]] = field(default_factory=list)
    quality_report: Optional[CharacterQualityReport] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "final_score": self.final_score,
            "total_iterations": self.total_iterations,
            "converged": self.converged,
            "iterations": self.iterations,
            "character_count": len(self.final_characters),
        }


# ── 角色审查专用提示词 ──────────────────────────────────────────

CHARACTER_REVIEWER_SYSTEM = """你是一位资深的网络小说角色评审专家，专注于角色设计的深度和质量。

你需要从以下维度严格评估角色设计：

1. **心理深度** (psychological_depth)：
   - 角色是否有内在矛盾和挣扎？
   - 动机是否复杂而非单一？
   - 是否有隐藏的恐惧、欲望或秘密？

2. **独特性** (uniqueness)：
   - 角色之间是否有足够的区分度？
   - 是否避免了脸谱化和刻板印象？
   - 每个角色是否有独特的说话方式或行为习惯？

3. **成长潜力** (growth_potential)：
   - 成长弧线是否合理、有说服力？
   - 是否有足够的挑战和转折点？
   - 角色的弱点是否会在故事中被考验？

4. **关系复杂性** (relationship_complexity)：
   - 角色之间的关系是否多层次？
   - 是否有潜在的冲突和张力？
   - 关系是否会随剧情发展而变化？

5. **世界观契合度** (world_fit)：
   - 角色背景是否与世界观设定一致？
   - 角色能力是否符合力量体系？
   - 角色在世界中的位置是否合理？

【重要】评分原则：
- 你必须给出精确的评分，不要给出"安全"的中间分数
- 如果角色有明显深度和创新设计，应给 8.0 以上
- 如果有明显问题未解决，应给 7.0 以下
- 评分应该反映真实质量，而不是折中

评分标准：
- 9-10分：卓越，角色极具魅力和深度
- 8-9分：优秀，角色立体丰满，有深度
- 7-8分：良好，基本立体但有改进空间
- 6-7分：及格，存在明显问题需要修改
- 6分以下：不合格，需要大幅重做"""

CHARACTER_REVIEWER_TASK = """请对以下角色设计进行全面质量评估。

{iteration_context}

世界观设定：
{world_setting}

角色列表：
{characters}

请以JSON格式输出评估结果（不要输出其他内容）：
{{
    "overall_score": 综合评分(1-10浮点数，请给出精确分数如7.3、8.1等，不要总是给7.0或7.5这样的整数),
    "dimension_scores": {{
        "psychological_depth": 心理深度分数,
        "uniqueness": 独特性分数,
        "growth_potential": 成长潜力分数,
        "relationship_complexity": 关系复杂性分数,
        "world_fit": 世界观契合度分数
    }},
    "improvement_assessment": {{
        "issues_resolved": ["已解决的问题"],
        "issues_remaining": ["仍存在的问题"],
        "new_issues": ["新发现的问题"],
        "improvement_score": 改进程度分数(1-10，仅在非首轮审查时填写)
    }},
    "character_assessments": [
        {{
            "name": "角色名",
            "score": 该角色评分,
            "strengths": ["优点1", "优点2"],
            "weaknesses": ["问题1", "问题2"],
            "improvement_suggestions": ["具体改进建议"]
        }}
    ],
    "uniqueness_analysis": {{
        "similar_pairs": [["角色A", "角色B", "相似之处"]],
        "missing_archetypes": ["缺少的角色类型"],
        "relationship_gaps": ["缺失的关系维度"]
    }},
    "critical_issues": [
        {{"character": "角色名", "issue": "严重问题", "severity": "high/medium/low"}}
    ],
    "summary": "整体评价（50字以内）"
}}"""

CHARACTER_REVISION_TASK = """你之前设计的角色经过专家评审，需要优化。

评审评分：{score}/10

评审反馈：
{feedback}

各角色的具体问题：
{character_issues}

原角色设计：
{original_characters}

世界观设定（供参考）：
{world_setting}

请根据评审意见优化角色设计，重点解决以下问题：
1. 增加角色的心理深度和内在矛盾
2. 强化角色之间的差异性
3. 完善成长弧线，添加具体的转折点
4. 丰富角色关系，增加潜在冲突

请以JSON数组格式输出优化后的完整角色列表：
[
    {{
        "name": "姓名",
        "role_type": "protagonist/supporting/antagonist",
        "gender": "male/female",
        "age": 年龄,
        "appearance": "外貌描述（具体、有特点）",
        "personality": "性格特点（包含优点和缺点）",
        "inner_conflict": "内在矛盾或心理挣扎（新增）",
        "background": "背景故事（详细、有创伤或特殊经历）",
        "goals": "目标与动机（表层目标和深层需求）",
        "fears": "恐惧或弱点（新增）",
        "secrets": "角色秘密（可选，新增）",
        "speech_pattern": "说话方式或口头禅（新增）",
        "abilities": {{"main_ability": "主要能力", "special_trait": "特殊特质", "limitation": "能力限制"}},
        "relationships": {{"角色名": "关系描述（包含情感和潜在冲突）"}},
        "growth_arc": {{
            "start": "初始状态（性格缺陷或困境）",
            "catalyst": "触发改变的事件",
            "middle": "中期发展（面临的考验）",
            "crisis": "最大危机点",
            "end": "最终状态（成长或改变）"
        }}
    }}
]"""


class CharacterReviewHandler:
    """角色设计审查循环处理器

    流程：
    1. Designer 生成/修订角色
    2. Reviewer 多维度评估 + 问题识别
    3. 如果 score < threshold 且未达上限 → 反馈给 Designer → 回到 1
    4. 返回最终角色列表 + 迭代历史
    """

    def __init__(
        self,
        client: QwenClient,
        cost_tracker: CostTracker,
        quality_threshold: float = 7.0,
        max_iterations: int = 2,
    ):
        """初始化角色审查处理器

        Args:
            client: LLM 客户端
            cost_tracker: 成本追踪器
            quality_threshold: 质量阈值（默认7.0，比章节略低）
            max_iterations: 最大迭代次数
        """
        self.client = client
        self.cost_tracker = cost_tracker
        self.quality_threshold = quality_threshold
        self.max_iterations = max_iterations

    async def execute(
        self,
        initial_characters: List[Dict[str, Any]],
        world_setting: Dict[str, Any],
        topic_analysis: Dict[str, Any],
    ) -> CharacterReviewResult:
        """执行角色设计审查循环

        Args:
            initial_characters: 初始角色列表
            world_setting: 世界观设定
            topic_analysis: 主题分析结果

        Returns:
            CharacterReviewResult
        """
        current_characters = initial_characters
        result = CharacterReviewResult()
        last_report: Optional[CharacterQualityReport] = None
        previous_issues: List[str] = []

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"[CharacterReview] 第 {iteration}/{self.max_iterations} 轮审查")

            # 获取上一轮评分
            previous_score = last_report.overall_score if last_report else 0

            # ── Reviewer 审查评分（带迭代上下文）──────────────────
            review_data = await self._reviewer_evaluate(
                characters=current_characters,
                world_setting=world_setting,
                iteration=iteration,
                previous_score=previous_score,
                previous_issues=previous_issues,
            )

            score = float(review_data.get("overall_score", 0))
            character_assessments = review_data.get("character_assessments", [])
            critical_issues = review_data.get("critical_issues", [])
            uniqueness_analysis = review_data.get("uniqueness_analysis", {})

            # 构造质量报告
            last_report = CharacterQualityReport(
                overall_score=score,
                dimension_scores=review_data.get("dimension_scores", {}),
                passed=score >= self.quality_threshold,
                issues=critical_issues,
                uniqueness_analysis=uniqueness_analysis,
                summary=review_data.get("summary", ""),
            )

            # 记录迭代
            result.iterations.append({
                "iteration": iteration,
                "score": score,
                "passed": last_report.passed,
                "issue_count": len(critical_issues),
                "dimension_scores": last_report.dimension_scores,
            })

            logger.info(
                f"[CharacterReview] score={score:.1f}, "
                f"passed={last_report.passed}, "
                f"issues={len(critical_issues)}"
            )

            # ── 判断是否继续迭代 ──────────────────────────────
            if last_report.passed:
                logger.info("[CharacterReview] 角色设计质量达标")
                break

            if iteration >= self.max_iterations:
                logger.warning(
                    f"[CharacterReview] 达到最大迭代次数 ({self.max_iterations})，"
                    f"当前评分 {score:.1f}"
                )
                break

            # ── Designer 修订 ───────────────────────────────────
            logger.info("[CharacterReview] 质量未达标，请求设计师修订...")

            # 构建反馈文本
            feedback_lines = [f"整体评价：{last_report.summary}"]
            for dim, dim_score in last_report.dimension_scores.items():
                dim_names = {
                    "psychological_depth": "心理深度",
                    "uniqueness": "独特性",
                    "growth_potential": "成长潜力",
                    "relationship_complexity": "关系复杂性",
                    "world_fit": "世界观契合度",
                }
                feedback_lines.append(f"- {dim_names.get(dim, dim)}: {dim_score}/10")

            # 构建角色问题文本
            character_issues_lines = []
            for assessment in character_assessments:
                char_name = assessment.get("name", "未知")
                weaknesses = assessment.get("weaknesses", [])
                suggestions = assessment.get("improvement_suggestions", [])
                if weaknesses or suggestions:
                    character_issues_lines.append(f"\n【{char_name}】")
                    for w in weaknesses:
                        character_issues_lines.append(f"  - 问题：{w}")
                    for s in suggestions:
                        character_issues_lines.append(f"  - 建议：{s}")

            # 添加严重问题
            for issue in critical_issues:
                char = issue.get("character", "")
                desc = issue.get("issue", "")
                severity = issue.get("severity", "medium")
                character_issues_lines.append(f"\n[{severity.upper()}] {char}: {desc}")

            revised_characters = await self._designer_revise(
                score=score,
                feedback="\n".join(feedback_lines),
                character_issues="\n".join(character_issues_lines) or "（无具体问题）",
                original_characters=current_characters,
                world_setting=world_setting,
            )

            if revised_characters and len(revised_characters) > 0:
                current_characters = revised_characters
                # 收集本轮问题，供下一轮审查参考
                previous_issues = [
                    f"{issue.get('character', '')}: {issue.get('issue', '')}"
                    for issue in critical_issues
                ]
                # 添加角色评估中的问题
                for assessment in character_assessments:
                    char_name = assessment.get("name", "")
                    for w in assessment.get("weaknesses", []):
                        previous_issues.append(f"{char_name}: {w}")
                logger.info(f"[CharacterReview] 设计师修订完成，{len(revised_characters)} 个角色")
            else:
                logger.warning("[CharacterReview] 修订失败，保留原设计")
                break

        # 组装最终结果
        result.final_characters = current_characters
        result.final_score = last_report.overall_score if last_report else 0
        result.total_iterations = len(result.iterations)
        result.converged = last_report.passed if last_report else False
        result.quality_report = last_report

        logger.info(
            f"[CharacterReview] 完成: iterations={result.total_iterations}, "
            f"score={result.final_score:.1f}, converged={result.converged}"
        )
        return result

    async def _reviewer_evaluate(
        self,
        characters: List[Dict[str, Any]],
        world_setting: Dict[str, Any],
        iteration: int = 1,
        previous_score: float = 0,
        previous_issues: List[str] = None,
    ) -> Dict[str, Any]:
        """调用 Reviewer 进行角色评估
        
        Args:
            characters: 角色列表
            world_setting: 世界观设定
            iteration: 当前迭代轮次
            previous_score: 上一轮评分
            previous_issues: 上一轮发现的问题
        """
        # 构建迭代上下文
        if iteration == 1:
            iteration_context = "【首轮审查】这是角色的首次评估。"
        else:
            issues_text = "\n".join(f"  - {issue}" for issue in (previous_issues or [])[:10])
            iteration_context = f"""【第 {iteration} 轮审查】
这是修订后的角色设计，请评估修订效果。
上一轮评分：{previous_score}/10
上一轮发现的主要问题：
{issues_text or "  （无）"}

请重点评估：
1. 上述问题是否已解决？
2. 修订后是否引入了新问题？
3. 角色整体质量是否有实质性提升？
如果问题已解决且没有新问题，应给予更高评分。"""

        task_prompt = CHARACTER_REVIEWER_TASK.format(
            iteration_context=iteration_context,
            world_setting=json.dumps(world_setting, ensure_ascii=False, indent=2),
            characters=json.dumps(characters, ensure_ascii=False, indent=2),
        )

        try:
            response = await self.client.chat(
                prompt=task_prompt,
                system=CHARACTER_REVIEWER_SYSTEM,
                temperature=0.5,  # 稍微提高温度，避免固定评分
                max_tokens=4096,
            )
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="角色审查员",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            return self._extract_json(response["content"])
        except Exception as e:
            logger.error(f"[CharacterReview] Reviewer 评估失败: {e}")
            return {"overall_score": self.quality_threshold, "critical_issues": []}

    async def _designer_revise(
        self,
        score: float,
        feedback: str,
        character_issues: str,
        original_characters: List[Dict[str, Any]],
        world_setting: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """调用 Designer 修订角色"""
        task_prompt = CHARACTER_REVISION_TASK.format(
            score=f"{score:.1f}",
            feedback=feedback,
            character_issues=character_issues,
            original_characters=json.dumps(original_characters, ensure_ascii=False, indent=2),
            world_setting=json.dumps(world_setting, ensure_ascii=False, indent=2)[:2000],
        )

        # 使用原有的角色设计师 system prompt
        from llm.prompt_manager import PromptManager
        designer_system = PromptManager.CHARACTER_DESIGNER_SYSTEM

        try:
            response = await self.client.chat(
                prompt=task_prompt,
                system=designer_system,
                temperature=0.8,
                max_tokens=6000,
            )
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="角色设计师(修订)",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            result = self._extract_json(response["content"])
            # 确保返回列表
            if isinstance(result, dict):
                return [result]
            return result
        except Exception as e:
            logger.error(f"[CharacterReview] Designer 修订失败: {e}")
            return []

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

        # 尝试找 JSON 数组
        start = text.find("[")
        if start != -1:
            end = text.rfind("]")
            if end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass

        # 尝试找 JSON 对象
        start = text.find("{")
        if start != -1:
            end = text.rfind("}")
            if end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass

        raise ValueError(f"无法从响应中提取 JSON: {text[:200]}...")
