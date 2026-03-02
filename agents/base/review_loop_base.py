"""审查循环处理器基类

使用模板方法模式封装 Designer-Reviewer 审查循环的核心迭代逻辑。
子类只需实现特定领域的方法即可获得完整的审查循环功能。

主要流程：
1. 初始化循环状态
2. for iteration in 1..max_iterations:
   a. Reviewer 评估当前内容
   b. 构造质量报告
   c. 记录迭代历史
   d. 检查退出条件（passed 或达到上限）
   e. Builder/Designer 修订内容
   f. 更新当前内容和问题列表
3. 组装并返回最终结果
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Generic, List, Optional, TypeVar

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient

from agents.base.json_extractor import JsonExtractor
from agents.base.quality_report import BaseQualityReport
from agents.base.review_result import BaseReviewResult


# 泛型类型
TContent = TypeVar("TContent")  # 内容类型：str, Dict, List
TResult = TypeVar("TResult", bound=BaseReviewResult)  # 结果类型
TReport = TypeVar("TReport", bound=BaseQualityReport)  # 报告类型


@dataclass
class ReviewLoopConfig:
    """审查循环配置
    
    封装循环控制相关的参数。
    """
    
    # 质量阈值（默认 7.0，章节审查可用 7.5）
    quality_threshold: float = 7.0
    
    # 最大迭代次数
    max_iterations: int = 2
    
    # Reviewer 调用温度
    reviewer_temperature: float = 0.5
    
    # Builder 调用温度
    builder_temperature: float = 0.7
    
    # Reviewer 最大 token 数
    reviewer_max_tokens: int = 4096
    
    # Builder 最大 token 数
    builder_max_tokens: int = 6000


class BaseReviewLoopHandler(ABC, Generic[TContent, TResult, TReport]):
    """审查循环处理器基类
    
    使用模板方法模式，将共同的迭代控制逻辑封装在基类中，
    子类只需实现特定领域的抽象方法。
    
    泛型参数：
        TContent: 被审查内容的类型（str/Dict/List）
        TResult: 审查结果类型（继承自 BaseReviewResult）
        TReport: 质量报告类型（继承自 BaseQualityReport）
    
    使用示例：
        class WorldReviewHandler(BaseReviewLoopHandler[Dict, WorldReviewResult, WorldQualityReport]):
            def _get_loop_name(self) -> str:
                return "WorldReview"
            
            # ... 实现其他抽象方法
    """
    
    def __init__(
        self,
        client: QwenClient,
        cost_tracker: CostTracker,
        quality_threshold: float = 7.0,
        max_iterations: int = 2,
        config: Optional[ReviewLoopConfig] = None,
    ):
        """初始化审查循环处理器
        
        Args:
            client: LLM 客户端
            cost_tracker: 成本追踪器
            quality_threshold: 质量阈值
            max_iterations: 最大迭代次数
            config: 可选的详细配置（覆盖上述参数）
        """
        self.client = client
        self.cost_tracker = cost_tracker
        
        # 使用配置或默认值
        if config:
            self.config = config
        else:
            self.config = ReviewLoopConfig(
                quality_threshold=quality_threshold,
                max_iterations=max_iterations,
            )
        
        # 快捷访问
        self.quality_threshold = self.config.quality_threshold
        self.max_iterations = self.config.max_iterations
    
    # ══════════════════════════════════════════════════════════════════════════
    # 模板方法（核心迭代逻辑）
    # ══════════════════════════════════════════════════════════════════════════
    
    async def execute(self, initial_content: TContent, **context) -> TResult:
        """执行审查循环（模板方法）
        
        这是核心的模板方法，定义了审查循环的完整流程。
        子类通过实现抽象方法来定制特定领域的行为。
        
        Args:
            initial_content: 初始内容（由子类定义具体类型）
            **context: 额外的上下文参数（如世界观、角色等）
        
        Returns:
            审查结果（由子类定义具体类型）
        """
        loop_name = self._get_loop_name()
        current_content = initial_content
        result = self._create_result()
        last_report: Optional[TReport] = None
        previous_issues: List[str] = []
        
        # 最佳记录追踪 & 停滞检测
        best_score = 0.0
        best_content = initial_content
        best_report: Optional[TReport] = None
        stagnation_count = 0
        
        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"[{loop_name}] 第 {iteration}/{self.max_iterations} 轮审查")
            
            # 获取上一轮评分
            previous_score = last_report.overall_score if last_report else 0
            
            # ── Step 1: Reviewer 评估 ────────────────────────────
            review_data = await self._call_reviewer(
                content=current_content,
                iteration=iteration,
                previous_score=previous_score,
                previous_issues=previous_issues,
                **context,
            )
            
            # ── Step 2: 构造质量报告 ────────────────────────────
            score = float(review_data.get("overall_score", 0))
            # 防止 overall_score 缺失时降为 0，使用维度平均分降级
            if score == 0 and "dimension_scores" in review_data:
                dim = review_data["dimension_scores"]
                if dim and isinstance(dim, dict):
                    try:
                        score = sum(float(v) for v in dim.values()) / len(dim)
                    except (ValueError, TypeError):
                        pass
            last_report = self._create_quality_report(review_data)
            # 使用报告中经过降级处理的分数，确保 score 与 last_report 一致
            if score == 0 and last_report.overall_score > 0:
                score = last_report.overall_score
            
            # ── Step 3: 记录迭代历史 ────────────────────────────
            self._record_iteration(
                result=result,
                iteration=iteration,
                score=score,
                report=last_report,
                review_data=review_data,
            )
            
            logger.info(
                f"[{loop_name}] score={score:.1f}, "
                f"passed={last_report.passed}, "
                f"issues={len(last_report.issues)}"
            )
            
            # 更新最佳记录
            if score > best_score:
                best_score = score
                best_content = current_content
                best_report = last_report
            
            # ── Step 4: 检查退出条件 ────────────────────────────
            if last_report.passed:
                logger.info(f"[{loop_name}] 质量达标")
                break
            
            if iteration >= self.max_iterations:
                logger.warning(
                    f"[{loop_name}] 达到最大迭代次数 ({self.max_iterations})，"
                    f"当前评分 {score:.1f}"
                )
                break
            
            # 评分停滞检测：连续 2 轮改善 < 0.3 则提前终止
            if iteration > 1:
                improvement = score - previous_score
                if improvement < 0.3:
                    stagnation_count += 1
                else:
                    stagnation_count = 0
                
                if stagnation_count >= 2:
                    logger.warning(
                        f"[{loop_name}] 评分连续{stagnation_count}轮无明显改善"
                        f"(score={score:.1f})，提前终止"
                    )
                    break
            
            # ── Step 5: Builder 修订 ────────────────────────────
            logger.info(f"[{loop_name}] 质量未达标，请求修订...")
            
            # 构建反馈文本
            feedback = self._build_feedback_text(last_report, review_data)
            issues_text = self._build_issues_text(last_report, review_data)
            
            # 调用 Builder 修订
            revised_content = await self._call_builder(
                score=score,
                feedback=feedback,
                issues=issues_text,
                original_content=current_content,
                report=last_report,
                review_data=review_data,
                **context,
            )
            
            # ── Step 6: 更新状态 ────────────────────────────────
            if self._validate_revision(revised_content, current_content):
                current_content = revised_content
                previous_issues = self._collect_issues_for_next_round(
                    last_report, review_data
                )
                logger.info(f"[{loop_name}] 修订完成")
            else:
                logger.warning(f"[{loop_name}] 修订失败，保留原内容")
                break
        
        # ── 组装最终结果（使用最佳分数对应的内容） ─────────────
        final_content = best_content if best_score > 0 else current_content
        final_report = best_report if best_report else last_report
        self._finalize_result(result, final_content, final_report)
        
        logger.info(
            f"[{loop_name}] 完成: iterations={result.total_iterations}, "
            f"score={result.final_score:.1f}, converged={result.converged}"
        )
        
        return result
    
    # ══════════════════════════════════════════════════════════════════════════
    # 必须实现的抽象方法
    # ══════════════════════════════════════════════════════════════════════════
    
    @abstractmethod
    def _get_loop_name(self) -> str:
        """获取循环名称（用于日志）
        
        Returns:
            如 "WorldReview", "CharacterReview", "PlotReview", "ReviewLoop"
        """
        pass
    
    @abstractmethod
    def _create_result(self) -> TResult:
        """创建空的结果对象
        
        Returns:
            对应类型的审查结果实例
        """
        pass
    
    @abstractmethod
    def _create_quality_report(self, review_data: Dict[str, Any]) -> TReport:
        """从 Reviewer 响应创建质量报告
        
        Args:
            review_data: Reviewer 返回的评估数据
            
        Returns:
            对应类型的质量报告实例
        """
        pass
    
    @abstractmethod
    def _get_reviewer_system_prompt(self) -> str:
        """获取 Reviewer 的 system prompt
        
        Returns:
            Reviewer 角色的系统提示词
        """
        pass
    
    @abstractmethod
    def _build_reviewer_task_prompt(
        self,
        content: TContent,
        iteration: int,
        previous_score: float,
        previous_issues: List[str],
        **context,
    ) -> str:
        """构建 Reviewer 的任务提示词
        
        Args:
            content: 当前被审查的内容
            iteration: 当前迭代轮次
            previous_score: 上一轮评分
            previous_issues: 上一轮发现的问题
            **context: 额外上下文
            
        Returns:
            完整的任务提示词
        """
        pass
    
    @abstractmethod
    def _get_builder_system_prompt(self) -> str:
        """获取 Builder 的 system prompt
        
        Returns:
            Builder/Designer/Architect 角色的系统提示词
        """
        pass
    
    @abstractmethod
    def _build_revision_prompt(
        self,
        score: float,
        feedback: str,
        issues: str,
        original_content: TContent,
        report: TReport,
        review_data: Dict[str, Any],
        **context,
    ) -> str:
        """构建修订任务的提示词
        
        Args:
            score: 当前评分
            feedback: 反馈文本
            issues: 问题列表文本
            original_content: 原始内容
            report: 质量报告
            review_data: 完整的审查数据
            **context: 额外上下文
            
        Returns:
            完整的修订任务提示词
        """
        pass
    
    @abstractmethod
    def _validate_revision(
        self, revised: TContent, original: TContent
    ) -> bool:
        """验证修订结果是否有效
        
        Args:
            revised: 修订后的内容
            original: 原始内容
            
        Returns:
            修订是否有效
        """
        pass
    
    @abstractmethod
    def _finalize_result(
        self,
        result: TResult,
        final_content: TContent,
        last_report: Optional[TReport],
    ) -> None:
        """填充最终结果
        
        Args:
            result: 结果对象（原地修改）
            final_content: 最终内容
            last_report: 最后一轮的质量报告
        """
        pass
    
    # ══════════════════════════════════════════════════════════════════════════
    # 可选覆盖的钩子方法
    # ══════════════════════════════════════════════════════════════════════════
    
    def _get_reviewer_agent_name(self) -> str:
        """获取 Reviewer 的代理名称（用于成本追踪）"""
        return f"{self._get_loop_name()}审查员"
    
    def _get_builder_agent_name(self) -> str:
        """获取 Builder 的代理名称（用于成本追踪）"""
        return f"{self._get_loop_name()}修订者"
    
    def _get_dimension_names(self) -> Dict[str, str]:
        """获取维度名称映射（用于反馈文本）
        
        Returns:
            英文维度名 -> 中文维度名的映射
        """
        return {}
    
    def _build_feedback_text(
        self, report: TReport, review_data: Dict[str, Any]
    ) -> str:
        """构建反馈文本
        
        默认实现：列出整体评价和各维度评分。
        子类可覆盖以添加特定领域的反馈。
        
        Args:
            report: 质量报告
            review_data: 完整的审查数据
            
        Returns:
            格式化的反馈文本
        """
        lines = [f"整体评价：{report.summary}"]
        
        dim_names = self._get_dimension_names()
        for dim, dim_score in report.dimension_scores.items():
            dim_display = dim_names.get(dim, dim)
            lines.append(f"- {dim_display}: {dim_score}/10")
        
        return "\n".join(lines)
    
    def _build_issues_text(
        self, report: TReport, review_data: Dict[str, Any]
    ) -> str:
        """构建问题列表文本
        
        默认实现：列出所有严重问题。
        子类可覆盖以添加特定领域的问题格式。
        
        Args:
            report: 质量报告
            review_data: 完整的审查数据
            
        Returns:
            格式化的问题列表文本
        """
        lines = []
        
        for issue in report.issues:
            area = issue.get("area", "")
            desc = issue.get("issue", "")
            severity = issue.get("severity", "medium")
            suggestion = issue.get("suggestion", "")
            
            lines.append(f"[{severity.upper()}] {area}: {desc}")
            if suggestion:
                lines.append(f"  建议: {suggestion}")
        
        # 添加缺失元素
        missing = review_data.get("missing_elements", [])
        if missing:
            lines.append("\n缺失的重要元素：")
            for m in missing:
                lines.append(f"  - {m}")
        
        return "\n".join(lines) if lines else "（无具体问题）"
    
    def _collect_issues_for_next_round(
        self, report: TReport, review_data: Dict[str, Any]
    ) -> List[str]:
        """收集问题用于下一轮审查
        
        默认实现：收集所有 critical_issues。
        子类可覆盖以添加特定领域的问题收集逻辑。
        
        Args:
            report: 质量报告
            review_data: 完整的审查数据
            
        Returns:
            问题描述列表
        """
        issues = []
        
        for issue in report.issues:
            area = issue.get("area", "")
            desc = issue.get("issue", "")
            issues.append(f"{area}: {desc}" if area else desc)
        
        # 添加缺失元素
        missing = review_data.get("missing_elements", [])
        for m in missing:
            issues.append(f"缺失: {m}")
        
        return issues
    
    def _record_iteration(
        self,
        result: TResult,
        iteration: int,
        score: float,
        report: TReport,
        review_data: Dict[str, Any],
    ) -> None:
        """记录迭代历史
        
        默认实现：使用 result.add_iteration()。
        子类可覆盖以添加额外字段。
        
        Args:
            result: 结果对象
            iteration: 迭代轮次
            score: 评分
            report: 质量报告
            review_data: 完整的审查数据
        """
        result.add_iteration(
            iteration=iteration,
            score=score,
            passed=report.passed,
            issue_count=len(report.issues),
            dimension_scores=report.dimension_scores,
        )
    
    def _build_iteration_context(
        self,
        iteration: int,
        previous_score: float,
        previous_issues: List[str],
    ) -> str:
        """构建迭代上下文文本
        
        用于告诉 Reviewer 这是第几轮审查，上一轮的问题是什么。
        
        Args:
            iteration: 当前迭代轮次
            previous_score: 上一轮评分
            previous_issues: 上一轮发现的问题
            
        Returns:
            迭代上下文文本
        """
        if iteration == 1:
            return "【首轮审查】这是首次评估。"
        
        issues_text = "\n".join(
            f"  - {issue}" for issue in (previous_issues or [])[:10]
        )
        
        return f"""【第 {iteration} 轮审查】
这是修订后的内容，请评估修订效果。
上一轮评分：{previous_score}/10
上一轮发现的主要问题：
{issues_text or "  （无）"}

请重点评估：
1. 上述问题是否已解决？
2. 修订后是否引入了新问题？
3. 整体质量是否有实质性提升？
如果问题已解决且没有新问题，应给予更高评分。"""
    
    # ══════════════════════════════════════════════════════════════════════════
    # LLM 调用方法（可选覆盖）
    # ══════════════════════════════════════════════════════════════════════════
    
    async def _call_reviewer(
        self,
        content: TContent,
        iteration: int,
        previous_score: float,
        previous_issues: List[str],
        **context,
    ) -> Dict[str, Any]:
        """调用 Reviewer 进行评估
        
        Args:
            content: 被评估的内容
            iteration: 当前迭代轮次
            previous_score: 上一轮评分
            previous_issues: 上一轮的问题
            **context: 额外上下文
            
        Returns:
            解析后的评估数据
        """
        task_prompt = self._build_reviewer_task_prompt(
            content=content,
            iteration=iteration,
            previous_score=previous_score,
            previous_issues=previous_issues,
            **context,
        )
        
        try:
            response = await self.client.chat(
                prompt=task_prompt,
                system=self._get_reviewer_system_prompt(),
                temperature=self.config.reviewer_temperature,
                max_tokens=self.config.reviewer_max_tokens,
            )
            
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name=self._get_reviewer_agent_name(),
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            
            return JsonExtractor.extract_object(
                response["content"],
                default={"overall_score": self.quality_threshold, "critical_issues": []},
            )
            
        except Exception as e:
            logger.error(f"[{self._get_loop_name()}] Reviewer 评估失败: {e}")
            return {"overall_score": self.quality_threshold, "critical_issues": []}
    
    async def _call_builder(
        self,
        score: float,
        feedback: str,
        issues: str,
        original_content: TContent,
        report: TReport,
        review_data: Dict[str, Any],
        **context,
    ) -> TContent:
        """调用 Builder 进行修订
        
        Args:
            score: 当前评分
            feedback: 反馈文本
            issues: 问题列表文本
            original_content: 原始内容
            report: 质量报告
            review_data: 完整的审查数据
            **context: 额外上下文
            
        Returns:
            修订后的内容
        """
        task_prompt = self._build_revision_prompt(
            score=score,
            feedback=feedback,
            issues=issues,
            original_content=original_content,
            report=report,
            review_data=review_data,
            **context,
        )
        
        try:
            response = await self.client.chat(
                prompt=task_prompt,
                system=self._get_builder_system_prompt(),
                temperature=self.config.builder_temperature,
                max_tokens=self.config.builder_max_tokens,
            )
            
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name=self._get_builder_agent_name(),
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            
            return self._parse_builder_response(response["content"])
            
        except Exception as e:
            logger.error(f"[{self._get_loop_name()}] Builder 修订失败: {e}")
            return self._get_empty_content()
    
    def _parse_builder_response(self, response_text: str) -> TContent:
        """解析 Builder 响应
        
        默认实现：提取 JSON。
        章节审查子类应覆盖此方法以返回纯文本。
        
        Args:
            response_text: LLM 响应文本
            
        Returns:
            解析后的内容
        """
        return JsonExtractor.extract_json(response_text, default=self._get_empty_content())
    
    def _get_empty_content(self) -> TContent:
        """获取空内容（修订失败时的默认值）
        
        子类应覆盖此方法返回正确类型的空值。
        
        Returns:
            空内容（{} 或 [] 或 ""）
        """
        return {}  # 默认返回空字典
    
    # ══════════════════════════════════════════════════════════════════════════
    # 工具方法
    # ══════════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def to_json(obj: Any, indent: int = 2, max_length: Optional[int] = None) -> str:
        """将对象转换为 JSON 字符串
        
        Args:
            obj: 要转换的对象
            indent: 缩进空格数
            max_length: 可选的最大长度限制
            
        Returns:
            JSON 字符串
        """
        text = json.dumps(obj, ensure_ascii=False, indent=indent)
        if max_length and len(text) > max_length:
            return text[:max_length]
        return text
