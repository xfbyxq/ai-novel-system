"""迭代控制器 - 管理 Agent 间反馈循环的迭代次数与退出条件.

支持基于章节类型的动态迭代策略。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from core.logging_config import logger


class ChapterType(str, Enum):
    """章节类型枚举."""

    CLIMAX = "climax"  # 高潮章节：战斗、揭秘、重大转折
    TRANSITION = "transition"  # 过渡章节：日常、铺垫、信息传递
    SETUP = "setup"  # 铺垫章节：世界观构建、角色引入
    CHARACTER = "character"  # 人物塑造型：角色成长、关系发展
    WORLD_BUILDING = "world_building"  # 世界观构建型：力量体系、地理、势力
    NORMAL = "normal"  # 普通章节


@dataclass
class IterationStrategy:
    """迭代策略配置."""

    max_iterations: int = 3
    quality_threshold: float = 7.5
    cost_weight: float = 0.5  # 成本敏感度 (0.0-1.0)


@dataclass
class IterationRecord:
    """单轮迭代记录."""

    iteration: int
    score: float
    action: str  # "write" / "revise" / "fix" / "review"
    agent: str
    passed: bool
    cost_delta: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "score": self.score,
            "action": self.action,
            "agent": self.agent,
            "passed": self.passed,
            "cost_delta": self.cost_delta,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class IterationController:
    """控制反馈循环的迭代次数和退出条件.

    支持三种退出条件：
    1. 质量达标（score >= threshold）
    2. 达到最大迭代次数
    3. 成本超限

    支持基于章节类型的动态策略：
    - climax: 5 次迭代，8.5 分阈值（质量优先）
    - transition: 2 次迭代，7.0 分阈值（效率优先）
    - character/setup: 4 次迭代，8.0 分阈值
    - world_building: 3 次迭代，7.5 分阈值
    - normal: 3 次迭代，7.5 分阈值（默认）
    """

    # 章节类型对应的默认策略
    DEFAULT_STRATEGIES: Dict[ChapterType, IterationStrategy] = {
        ChapterType.CLIMAX: IterationStrategy(
            max_iterations=5,
            quality_threshold=8.5,
            cost_weight=0.3,  # 低成本敏感度，质量优先
        ),
        ChapterType.CHARACTER: IterationStrategy(
            max_iterations=4, quality_threshold=8.0, cost_weight=0.4
        ),
        ChapterType.SETUP: IterationStrategy(
            max_iterations=4, quality_threshold=8.0, cost_weight=0.5
        ),
        ChapterType.WORLD_BUILDING: IterationStrategy(
            max_iterations=3, quality_threshold=7.5, cost_weight=0.6
        ),
        ChapterType.TRANSITION: IterationStrategy(
            max_iterations=2,
            quality_threshold=7.0,
            cost_weight=0.8,  # 高成本敏感度，效率优先
        ),
        ChapterType.NORMAL: IterationStrategy(
            max_iterations=3, quality_threshold=7.5, cost_weight=0.5
        ),
    }

    def __init__(
        self,
        chapter_type: ChapterType = ChapterType.NORMAL,
        custom_strategy: Optional[IterationStrategy] = None,
        cost_limit: Optional[float] = None,
    ):
        """初始化迭代控制器.

        Args:
            chapter_type: 章节类型
            custom_strategy: 自定义策略（覆盖默认）
            cost_limit: 本轮循环的成本上限（元），None 表示不限
        """
        # 根据章节类型加载策略
        base_strategy = self.DEFAULT_STRATEGIES.get(
            chapter_type, self.DEFAULT_STRATEGIES[ChapterType.NORMAL]
        )

        if custom_strategy:
            self.strategy = custom_strategy
        else:
            self.strategy = base_strategy

        self.quality_threshold = self.strategy.quality_threshold
        self.max_iterations = self.strategy.max_iterations
        self.cost_weight = self.strategy.cost_weight
        self.cost_limit = cost_limit

        self.history: List[IterationRecord] = []
        self.current_iteration: int = 0
        self.cumulative_cost: float = 0.0
        self.chapter_type: ChapterType = chapter_type

    def should_continue(
        self,
        score: float,
        iteration: Optional[int] = None,
        cost_delta: float = 0.0,
    ) -> bool:
        """判断是否需要继续迭代.

        Args:
            score: 当前迭代的质量分数
            iteration: 当前迭代次数（不传则使用内部计数）
            cost_delta: 本轮新增成本

        Returns:
            True 表示应继续迭代，False 表示应停止
        """
        it = iteration if iteration is not None else self.current_iteration
        self.cumulative_cost += cost_delta

        if score >= self.quality_threshold:
            logger.info(
                f"[IterationController] 质量达标 "
                f"(score={score:.1f} >= threshold={self.quality_threshold}), 停止迭代"
            )
            return False

        if it >= self.max_iterations:
            logger.warning(
                f"[IterationController] 达到最大迭代次数 ({self.max_iterations}), "
                f"当前 score={score:.1f}, 强制停止"
            )
            return False

        if self.cost_limit is not None and self.cumulative_cost >= self.cost_limit:
            logger.warning(
                f"[IterationController] 成本超限 "
                f"(cumulative={self.cumulative_cost:.4f} >= limit={self.cost_limit}), "
                f"当前 score={score:.1f}, 强制停止"
            )
            return False

        logger.info(
            f"[IterationController] 继续迭代 "
            f"(iteration={it}, score={score:.1f}, threshold={self.quality_threshold})"
        )
        return True

    def log_iteration(
        self,
        score: float,
        action: str,
        agent: str,
        passed: bool,
        cost_delta: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> IterationRecord:
        """记录一轮迭代."""
        self.current_iteration += 1
        self.cumulative_cost += cost_delta
        record = IterationRecord(
            iteration=self.current_iteration,
            score=score,
            action=action,
            agent=agent,
            passed=passed,
            cost_delta=cost_delta,
            details=details or {},
        )
        self.history.append(record)
        return record

    def get_summary(self) -> Dict[str, Any]:
        """获取迭代摘要."""
        scores = [r.score for r in self.history if r.score > 0]
        return {
            "total_iterations": self.current_iteration,
            "max_iterations": self.max_iterations,
            "quality_threshold": self.quality_threshold,
            "final_score": scores[-1] if scores else 0.0,
            "score_progression": scores,
            "cumulative_cost": round(self.cumulative_cost, 4),
            "converged": bool(scores and scores[-1] >= self.quality_threshold),
        }

    def reset(self):
        """重置控制器（用于下一章）."""
        self.history.clear()
        self.current_iteration = 0
        self.cumulative_cost = 0.0

    @staticmethod
    async def identify_chapter_type(
        chapter_content: str,
        chapter_title: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ChapterType:
        """基于内容自动识别章节类型.

        使用轻量级 LLM 调用识别章节类型，避免额外成本。

        Args:
            chapter_content: 章节内容
            chapter_title: 章节标题
            context: 可选的上下文信息

        Returns:
            ChapterType: 识别的章节类型
        """
        from llm.qwen_client import QwenClient

        # 只使用前 500 字进行识别，降低成本
        content_preview = chapter_content[:500] if chapter_content else ""

        prompt = f"""请判断以下小说章节的类型：

章节标题：{chapter_title}
章节内容（前 500 字）：{content_preview}

可选类型：
- climax: 高潮章节（战斗、揭秘、重大转折）
- transition: 过渡章节（日常、铺垫、信息传递）
- setup: 铺垫章节（世界观构建、角色引入）
- character: 人物塑造型（角色成长、关系发展）
- world_building: 世界观构建型（力量体系、地理、势力）
- normal: 普通章节

只返回类型名称（如：climax）"""

        try:
            client = QwenClient()
            response = await client.chat(
                prompt=prompt,
                system="你是一个专业的小说编辑，擅长识别章节类型。",
                temperature=0.1,  # 低温度保证稳定性
                max_tokens=50,
            )

            type_str = response["content"].strip().lower()

            # 映射到 ChapterType
            type_map = {
                "climax": ChapterType.CLIMAX,
                "transition": ChapterType.TRANSITION,
                "setup": ChapterType.SETUP,
                "character": ChapterType.CHARACTER,
                "world_building": ChapterType.WORLD_BUILDING,
                "normal": ChapterType.NORMAL,
            }

            chapter_type = type_map.get(type_str, ChapterType.NORMAL)

            logger.info(
                f"[IterationController] 章节类型识别：{chapter_title} -> {chapter_type.value}"
            )

            return chapter_type

        except Exception as e:
            logger.warning(
                f"[IterationController] 章节类型识别失败：{e}，使用默认类型 NORMAL"
            )
            return ChapterType.NORMAL
