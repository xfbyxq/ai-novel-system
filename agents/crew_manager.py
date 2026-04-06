"""CrewAI 风格的小说生成 Crew 管理器.

采用直接编排模式，通过 QwenClient 调用通义千问模型，
而非使用 CrewAI 的内置 LLM 集成。

集成 TeamContext 实现 Agent 间的信息共享和状态追踪。
集成审查反馈循环、投票共识、请求-应答协商机制。
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Optional

from agents.agent_query_service import AgentQueryService
from agents.base.json_extractor import JsonExtractor
from agents.chapter_summary_generator import ChapterSummaryGenerator
from agents.character_review_loop import CharacterReviewHandler

# 反思机制
# 章节连续性增强组件
from agents.context_compressor import ContextCompressor
from agents.continuity_fixer import ContinuityFixerPipeline
from agents.plot_review_loop import PlotReviewHandler

# Agent 间协作组件
from agents.review_loop import ReviewLoopHandler
from agents.similarity_detector import SimilarityDetector

# TeamContext 用于 Agent 间信息共享
from agents.team_context import NovelTeamContext
from agents.voting_manager import VotingManager
from agents.world_review_loop import WorldReviewHandler

# Use the project-wide logger
from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.prompt_manager import PromptManager
from llm.qwen_client import QwenClient


@dataclass
class CrewConfig:
    """NovelCrewManager 的统一配置."""

    quality_threshold: float = 7.5
    max_review_iterations: int = 3
    max_fix_iterations: int = 2
    enable_voting: bool = True
    enable_query: bool = True
    enable_character_review: bool = True
    enable_world_review: bool = True
    enable_plot_review: bool = True
    enable_outline_refinement: bool = True
    character_quality_threshold: float = 7.0
    world_quality_threshold: float = 7.0
    plot_quality_threshold: float = 7.0
    max_character_review_iterations: int = 2
    max_world_review_iterations: int = 2
    max_plot_review_iterations: int = 2
    context_compressor_max_tokens: int = 8000  # 上下文压缩器token阈值


class NovelCrewManager:
    """小说生成 Crew 管理器.

    负责协调企划阶段和写作阶段的所有 Agent,
    通过直接调用 QwenClient 实现 Agent 间的数据传递和任务编排。

    支持的 Agent 间协作机制：
    - 审查反馈循环（Writer-Editor 质量驱动迭代）
    - 投票共识（企划阶段关键决策多视角投票）
    - 请求-应答协商（Writer 写作过程中查询设定）
    """

    def __init__(
        self,
        qwen_client: QwenClient,
        cost_tracker: CostTracker,
        config: CrewConfig | None = None,
    ):
        """初始化 Crew 管理器.

        Args:
            qwen_client: 通义千问客户端实例
            cost_tracker: 成本跟踪器实例
            config: 配置对象，包含所有质量阈值和功能开关参数
        """
        # 如果没有传入配置，从 Settings 加载
        if config is None:
            from backend.config import settings

            config = CrewConfig(
                quality_threshold=settings.CHAPTER_QUALITY_THRESHOLD,
                max_review_iterations=settings.MAX_CHAPTER_REVIEW_ITERATIONS,
                max_fix_iterations=settings.MAX_FIX_ITERATIONS,
                enable_voting=settings.ENABLE_VOTING,
                enable_query=settings.ENABLE_QUERY,
                enable_character_review=settings.ENABLE_CHARACTER_REVIEW,
                enable_world_review=settings.ENABLE_WORLD_REVIEW,
                enable_plot_review=settings.ENABLE_PLOT_REVIEW,
                enable_outline_refinement=settings.ENABLE_OUTLINE_REFINEMENT,
                character_quality_threshold=settings.CHARACTER_QUALITY_THRESHOLD,
                world_quality_threshold=settings.WORLD_QUALITY_THRESHOLD,
                plot_quality_threshold=settings.PLOT_QUALITY_THRESHOLD,
                max_character_review_iterations=settings.MAX_CHARACTER_REVIEW_ITERATIONS,
                max_world_review_iterations=settings.MAX_WORLD_REVIEW_ITERATIONS,
                max_plot_review_iterations=settings.MAX_PLOT_REVIEW_ITERATIONS,
                context_compressor_max_tokens=settings.CONTEXT_COMPRESSOR_MAX_TOKENS,
            )
        self.client = qwen_client
        self.cost_tracker = cost_tracker
        self.pm = PromptManager

        # 协作配置
        self.quality_threshold = config.quality_threshold
        self.max_review_iterations = config.max_review_iterations
        self.max_fix_iterations = config.max_fix_iterations
        self.enable_voting = config.enable_voting
        self.enable_query = config.enable_query
        self.enable_character_review = config.enable_character_review
        self.enable_world_review = config.enable_world_review
        self.enable_plot_review = config.enable_plot_review
        self.enable_outline_refinement = config.enable_outline_refinement

        # 图数据库上下文注入开关（从配置读取）
        from backend.config import settings

        self.enable_graph_context = settings.ENABLE_GRAPH_DATABASE and getattr(
            settings, "ENABLE_GRAPH_CONTEXT_INJECTION", True
        )

        # 初始化协作组件
        self.review_handler = ReviewLoopHandler(
            client=qwen_client,
            cost_tracker=cost_tracker,
            quality_threshold=config.quality_threshold,
            max_iterations=config.max_review_iterations,
        )
        self.voting_manager = VotingManager(
            client=qwen_client,
            cost_tracker=cost_tracker,
        )
        self.query_service = AgentQueryService(
            client=qwen_client,
            cost_tracker=cost_tracker,
        )

        # 角色审查处理器
        self.character_review_handler = CharacterReviewHandler(
            client=qwen_client,
            cost_tracker=cost_tracker,
            quality_threshold=config.character_quality_threshold,
            max_iterations=config.max_character_review_iterations,
        )

        # 世界观审查处理器
        self.world_review_handler = WorldReviewHandler(
            client=qwen_client,
            cost_tracker=cost_tracker,
            quality_threshold=config.world_quality_threshold,
            max_iterations=config.max_world_review_iterations,
        )

        # 大纲审查处理器
        self.plot_review_handler = PlotReviewHandler(
            client=qwen_client,
            cost_tracker=cost_tracker,
            quality_threshold=config.plot_quality_threshold,
            max_iterations=config.max_plot_review_iterations,
        )

        # 章节连续性增强组件
        self.context_compressor = ContextCompressor(
            max_total_tokens=config.context_compressor_max_tokens
        )
        self.similarity_detector = SimilarityDetector()
        self.summary_generator = ChapterSummaryGenerator(
            client=qwen_client,
            cost_tracker=cost_tracker,
        )
        self.continuity_fixer_pipeline = ContinuityFixerPipeline(
            qwen_client=qwen_client,
            cost_tracker=cost_tracker,
        )

        # 章节数据缓存（供压缩器和相似度检测器使用）
        self._chapter_summaries: dict[int, dict] = {}
        self._chapter_contents: dict[int, str] = {}
        self._chapter_detailed_outlines: dict[int, dict] = {}

        # 跨章节人物关系累积（用于关系确认）
        self._character_relationship_accumulator: dict[tuple[str, str], dict] = {}

        # 角色出场统计（用于判断角色重要性）
        self._character_appearance_tracker: dict[str, dict] = {}
        # 结构: {
        #   "角色名": {
        #       "first_appearance": 1,      # 首次出场章节
        #       "appearance_count": 3,      # 出场次数
        #       "chapters": [1, 3, 5],      # 出场章节列表
        #       "role_type": "supporting",  # 角色类型
        #       "is_important": True        # 是否重要角色
        #   }
        # }

        # 反思代理（初始化为None，需要时通过setup_reflection设置）
        self.reflection_agent = None

    # ============================================================
    # Agent 调用基础方法
    # ============================================================

    # 注意：JSON 提取方法已移至 agents.base.json_extractor.JsonExtractor
    # 使用 JsonExtractor.extract_json() 或 JsonExtractor.safe_extract() 替代

    async def _call_agent(
        self,
        agent_name: str,
        system_prompt: str,
        task_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        expect_json: bool = True,
    ) -> dict | str:
        """调用单个 Agent 并追踪成本.

        Args:
            agent_name: Agent 名称（用于日志和成本追踪）
            system_prompt: 系统提示词（定义 Agent 角色）
            task_prompt: 任务提示词（具体任务描述）
            temperature: 温度参数
            max_tokens: 最大 token 数
            expect_json: 是否期望返回 JSON（True 则解析 JSON，False 则返回原文）

        Returns:
            解析后的 JSON（dict）或原始文本（str）

        Raises:
            RuntimeError: API 调用失败
            ValueError: JSON 解析失败（当 expect_json=True 时，且重试后仍失败）
        """
        logger.info(f"🤖 [{agent_name}] 开始执行...")

        try:
            # 调用 LLM
            response = await self.client.chat(
                prompt=task_prompt,
                system=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # 记录成本
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name=agent_name,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )

            content = response["content"]

            # 如果需要 JSON，解析之
            # 使用 JsonExtractor 统一处理 JSON 提取，替代原有的重复方法
            if expect_json:
                try:
                    result = JsonExtractor.extract_json(content)
                    logger.info(f"✅ [{agent_name}] 执行成功，返回 JSON 数据")
                    return result
                except ValueError:
                    # JSON 提取失败，用修正提示词重试
                    logger.warning(f"[{agent_name}] JSON提取失败，开始重试...")
                    return await self._retry_json_extraction(
                        agent_name=agent_name,
                        system_prompt=system_prompt,
                        failed_response=content,
                        max_retries=2,
                    )
            else:
                logger.info(f"✅ [{agent_name}] 执行成功，返回文本内容（{len(content)} 字符）")
                return content

        except Exception as e:
            logger.error(f"❌ [{agent_name}] 执行失败: {e}")
            raise

    async def _retry_json_extraction(
        self,
        agent_name: str,
        system_prompt: str,
        failed_response: str,
        max_retries: int = 2,
    ) -> dict | list:
        """JSON 提取失败后，用修正提示词让 LLM 重新输出合法 JSON."""
        json_fix_prompt = (
            "你上一次的输出无法解析为有效的JSON。请仅输出修正后的合法JSON，"
            "不要添加任何解释文字或markdown标记。\n\n"
            "原始输出（前1500字符）：\n{response}\n\n"
            "请直接输出修正后的完整JSON："
        )

        last_response = failed_response
        for attempt in range(1, max_retries + 1):
            logger.warning(
                f"[{agent_name}] JSON重试 {attempt}/{max_retries}，"
                f"响应片段: {last_response[:100]}..."
            )
            fix_prompt = json_fix_prompt.format(response=last_response[:1500])
            response = await self.client.chat(
                prompt=fix_prompt,
                system=system_prompt,
                temperature=0.3,
                max_tokens=4096,
            )
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name=f"{agent_name}(JSON修正)",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )
            last_response = response["content"]
            try:
                # 使用 JsonExtractor 统一处理 JSON 提取
                result = JsonExtractor.extract_json(last_response)
                logger.info(f"✅ [{agent_name}] JSON重试成功 (第{attempt}次)")
                return result
            except ValueError:
                continue

        raise ValueError(
            f"[{agent_name}] JSON提取在{max_retries}次重试后仍失败: " f"{last_response[:200]}..."
        )

    # ============================================================
    # 企划阶段
    # ============================================================

    async def run_planning_phase(
        self,
        genre: str | None = None,
        tags: list[str] | None = None,
        context: str = "",
        length_type: str = "medium",
    ) -> dict[str, Any]:
        """执行完整的企划阶段.

        顺序执行以下步骤：
        1. 主题分析师：分析市场趋势，推荐选题
        2. 世界观架构师：构建世界观体系
        3. 角色设计师：设计主要角色
        4. 情节架构师：规划整体情节架构

        Args:
            genre: 指定类型（可选，如不指定则由主题分析师推荐）
            tags: 指定标签（可选）
            context: 额外的上下文信息

        Returns:
            包含以下键的字典：
            - topic_analysis: 主题分析结果
            - world_setting: 世界观设定
            - characters: 角色列表
            - plot_outline: 情节大纲
        """
        logger.info("=" * 60)
        logger.info("🎬 开始企划阶段")
        logger.info("=" * 60)

        # 1. 主题分析
        topic_context = context or ""
        if genre:
            topic_context += f"\n\n期望类型：{genre}"
        if tags:
            topic_context += f"\n期望标签：{', '.join(tags)}"
        if length_type:
            topic_context += f"\n\n篇幅类型：{length_type}（{'长篇小说' if length_type == 'long' else '中篇小说' if length_type == 'medium' else '短文'}）"

        # 根据篇幅类型调整提示词
        length_instructions = ""
        if length_type == "long":
            length_instructions = "\n\n重要要求：这是一部长篇小说，需要设计宏大的世界观、复杂的人物关系和多层次的剧情架构，确保有足够的内容支撑长期连载。"
        elif length_type == "short":
            length_instructions = "\n\n重要要求：这是一部短文，需要紧凑的剧情结构，集中的人物冲突，在有限篇幅内完成完整的故事弧。"

        topic_task = self.pm.format(
            self.pm.TOPIC_ANALYST_TASK,
            context=topic_context + length_instructions,
        )

        topic_analysis = await self._call_agent(
            agent_name="主题分析师",
            system_prompt=self.pm.TOPIC_ANALYST_SYSTEM,
            task_prompt=topic_task,
            temperature=0.8,
            expect_json=True,
        )

        # 2. 世界观构建
        world_length_instructions = ""
        if length_type == "long":
            world_length_instructions = "\n\n重要要求：为长篇小说设计宏大而详细的世界观，包括完整的历史背景、复杂的力量体系、多样的地理区域和丰富的势力组织，确保有足够的扩展空间。"
        elif length_type == "short":
            world_length_instructions = "\n\n重要要求：为短文设计简洁但完整的世界观，聚焦核心设定，避免过于复杂的背景，确保故事能在有限篇幅内展开。"

        world_task = (
            self.pm.format(
                self.pm.WORLD_BUILDER_TASK,
                topic_analysis=json.dumps(topic_analysis, ensure_ascii=False, indent=2),
            )
            + world_length_instructions
        )

        world_setting = await self._call_agent(
            agent_name="世界观架构师",
            system_prompt=self.pm.WORLD_BUILDER_SYSTEM,
            task_prompt=world_task,
            temperature=0.7,
            max_tokens=6000,
            expect_json=True,
        )

        # 2.5 世界观审查循环：确保世界观设计的一致性和深度
        world_review_result = None
        if self.enable_world_review:
            logger.info("🔍 启动世界观设计审查循环...")
            # 确保 world_setting 是字典格式
            world_dict = world_setting if isinstance(world_setting, dict) else {}
            if isinstance(world_setting, list) and world_setting:
                world_dict = world_setting[0]

            review_result = await self.world_review_handler.execute(
                initial_world_setting=world_dict,
                topic_analysis=(topic_analysis if isinstance(topic_analysis, dict) else {}),
            )

            # 使用审查后的世界观
            world_setting = review_result.final_world_setting
            world_review_result = review_result.to_dict()

            logger.info(
                f"🔍 世界观审查完成: iterations={review_result.total_iterations}, "
                f"score={review_result.final_score:.1f}, "
                f"converged={review_result.converged}"
            )

        # 3. 角色设计
        character_length_instructions = ""
        if length_type == "long":
            character_length_instructions = "\n\n重要要求：为长篇小说设计丰富多样的角色群像，包括主角、多个重要配角、反派势力等，每个主要角色都要有完整的背景故事和成长弧。"
        elif length_type == "short":
            character_length_instructions = "\n\n重要要求：为短文聚焦核心角色，主要围绕少数几个关键人物展开，确保角色关系清晰，性格鲜明。"

        character_task = (
            self.pm.format(
                self.pm.CHARACTER_DESIGNER_TASK,
                topic_analysis=json.dumps(topic_analysis, ensure_ascii=False, indent=2),
                world_setting=json.dumps(world_setting, ensure_ascii=False, indent=2),
            )
            + character_length_instructions
        )

        characters = await self._call_agent(
            agent_name="角色设计师",
            system_prompt=self.pm.CHARACTER_DESIGNER_SYSTEM,
            task_prompt=character_task,
            temperature=0.8,
            max_tokens=6000,
            expect_json=True,
        )

        # 3.5 角色审查循环：确保角色设计的深度和质量
        character_review_result = None
        if self.enable_character_review:
            logger.info("🔍 启动角色设计审查循环...")
            # 确保 characters 是列表格式
            characters_list = characters if isinstance(characters, list) else [characters]

            review_result = await self.character_review_handler.execute(
                initial_characters=characters_list,
                world_setting=world_setting if isinstance(world_setting, dict) else {},
                topic_analysis=(topic_analysis if isinstance(topic_analysis, dict) else {}),
            )

            # 使用审查后的角色
            characters = review_result.final_characters
            character_review_result = review_result.to_dict()

            logger.info(
                f"🔍 角色审查完成: iterations={review_result.total_iterations}, "
                f"score={review_result.final_score:.1f}, "
                f"converged={review_result.converged}"
            )

        # 4. 情节架构（使用带决策点标注的提示词）
        plot_length_instructions = ""
        if length_type == "long":
            plot_length_instructions = "\n\n重要要求：为长篇小说设计宏大的多卷情节架构，包括主线剧情、多条副线、多个高潮点和足够的伏笔，确保故事有长期发展的潜力。"
        elif length_type == "short":
            plot_length_instructions = "\n\n重要要求：为短文设计紧凑的单卷情节结构，有明确的开始、发展、高潮和结局，确保故事在有限篇幅内完整呈现。"

        # 构建章节配置
        chapter_config = {
            "total_chapters": 6,  # 默认 6 章
            "min_chapters": 3,
            "max_chapters": 12,
            "flexible": True,
        }

        # 启用投票时使用带决策点标注的模板
        plot_template = (
            self.pm.PLOT_ARCHITECT_WITH_DECISIONS_TASK
            if self.enable_voting
            else self.pm.PLOT_ARCHITECT_TASK
        )

        plot_task = (
            self.pm.format(
                plot_template,
                world_setting=json.dumps(world_setting, ensure_ascii=False, indent=2),
                characters=json.dumps(characters, ensure_ascii=False, indent=2),
                chapter_config=json.dumps(chapter_config, ensure_ascii=False, indent=2),
                total_chapters=chapter_config["total_chapters"],
                min_chapters=chapter_config["min_chapters"],
                max_chapters=chapter_config["max_chapters"],
            )
            + plot_length_instructions
        )

        plot_outline = await self._call_agent(
            agent_name="情节架构师",
            system_prompt=self.pm.PLOT_ARCHITECT_SYSTEM,
            task_prompt=plot_task,
            temperature=0.7,
            max_tokens=6000,
            expect_json=True,
        )

        # 4.5 投票共识：如果情节架构中包含决策点，发起多 Agent 投票
        if self.enable_voting:
            # 兼容 list 和 dict 两种返回格式
            if isinstance(plot_outline, dict):
                decision_points = plot_outline.get("decision_points", [])
            else:
                decision_points = []
            if decision_points:
                logger.info(f"🗳️  检测到 {len(decision_points)} 个决策点，发起投票...")
                resolved_decisions = []
                for dp in decision_points[:3]:  # 最多处理 3 个决策点
                    vote_result = await self.voting_manager.initiate_vote(
                        topic=dp.get("topic", ""),
                        options=dp.get("options", []),
                        context=f"世界观: {json.dumps(world_setting, ensure_ascii=False)[:1000]}\n"
                        f"角色: {json.dumps(characters, ensure_ascii=False)[:1000]}",
                        voters=[
                            {
                                "name": "世界观架构师",
                                "role": "世界观专家",
                                "perspective": "从世界观一致性和扩展性角度评估",
                            },
                            {
                                "name": "角色设计师",
                                "role": "角色专家",
                                "perspective": "从角色发展和关系深度角度评估",
                            },
                            {
                                "name": "情节架构师",
                                "role": "情节专家",
                                "perspective": "从情节张力和读者吸引力角度评估",
                            },
                        ],
                    )
                    resolved_decisions.append(vote_result.to_dict())
                    logger.info(
                        f"🗳️  决策「{dp.get('topic', '')}」投票结果: "
                        f"{vote_result.winning_option} "
                        f"(共识强度: {vote_result.consensus_strength:.2f})"
                    )

                    # 记录到 TeamContext（如果后续有的话）
                plot_outline["resolved_decisions"] = resolved_decisions

        # 4.6 大纲审查循环：确保情节架构的完整性和吸引力
        plot_review_result = None
        if self.enable_plot_review:
            logger.info("🔍 启动大纲设计审查循环...")
            # 确保 plot_outline 是字典格式
            plot_dict = plot_outline if isinstance(plot_outline, dict) else {}
            if isinstance(plot_outline, list):
                plot_dict = {"volumes": plot_outline, "structure_type": "multi_volume"}

            # 确保 characters 是列表格式
            characters_list = characters if isinstance(characters, list) else [characters]

            review_result = await self.plot_review_handler.execute(
                initial_plot_outline=plot_dict,
                world_setting=world_setting if isinstance(world_setting, dict) else {},
                characters=characters_list,
            )

            # 使用审查后的大纲
            plot_outline = review_result.final_plot_outline
            plot_review_result = review_result.to_dict()

            logger.info(
                f"🔍 大纲审查完成: iterations={review_result.total_iterations}, "
                f"score={review_result.final_score:.1f}, "
                f"converged={review_result.converged}"
            )

        logger.info("=" * 60)
        logger.info("🎉 企划阶段完成！")
        logger.info("=" * 60)

        result = {
            "topic_analysis": topic_analysis,
            "world_setting": world_setting,
            "characters": characters,
            "plot_outline": plot_outline,
        }

        # 添加审查结果（如果启用）
        if world_review_result:
            result["world_review"] = world_review_result
        if character_review_result:
            result["character_review"] = character_review_result
        if plot_review_result:
            result["plot_review"] = plot_review_result

        return result

    # ============================================================
    # 写作阶段
    # ============================================================

    async def run_writing_phase(
        self,
        novel_data: dict[str, Any],
        chapter_number: int,
        volume_number: int = 1,
        previous_chapters_summary: str = "",
        character_states: str = "",
        writing_style: str = "modern",
        team_context: Optional[NovelTeamContext] = None,
    ) -> dict[str, Any]:
        """执行单章写作阶段.

        流程：
        1. 章节策划师：制定章节计划
        1.5 大纲细化师：将章节计划展开为逐场景详细大纲（可选，由 enable_outline_refinement 控制）
        2. 作家撰写初稿（如果启用查询，解析并回答 [QUERY] 标记后重写）
        3. Writer-Editor 审查反馈循环（质量阈值驱动迭代）
        4. 连续性审查（如有问题则修复-重检循环）

        Args:
            novel_data: 小说数据（包含 world_setting, characters, plot_outline 等）
            chapter_number: 章节号
            volume_number: 卷号
            previous_chapters_summary: 前几章摘要
            character_states: 当前角色状态
            writing_style: 写作风格
            team_context: 团队共享上下文（可选，用于增强信息共享）

        Returns:
            包含以下键的字典：
            - chapter_plan: 章节计划
            - detailed_outline: 细化大纲（如未启用则为空 dict）
            - draft: 初稿
            - edited_content: 编辑后内容
            - final_content: 最终内容
            - continuity_report: 连续性检查报告
            - quality_score: 质量评分
            - review_loop_result: 审查循环结果（如有）
        """
        logger.info("=" * 60)
        logger.info(f"✍️  开始写作第 {chapter_number} 章（第 {volume_number} 卷）")
        logger.info("=" * 60)

        # 提取必要的信息
        world_setting = novel_data.get("world_setting", {})
        characters = novel_data.get("characters", [])
        plot_outline = novel_data.get("plot_outline", {})

        # 类型兼容性处理：确保各参数是正确的类型
        if isinstance(world_setting, list):
            world_setting = world_setting[0] if world_setting else {}
            logger.warning("world_setting 是列表格式，已转换为字典")
        if not isinstance(world_setting, dict):
            world_setting = {}

        if isinstance(characters, dict):
            characters = characters.get("characters", [])
            logger.warning("characters 是字典格式，已提取角色列表")
        if not isinstance(characters, list):
            characters = []

        if isinstance(plot_outline, list):
            plot_outline = {"volumes": plot_outline}
            logger.warning("plot_outline 是列表格式，已转换为字典格式")
        if not isinstance(plot_outline, dict):
            plot_outline = {}

        # 获取小说标题和类型
        novel_title = novel_data.get("title", "未命名小说")
        genre = novel_data.get("genre") or world_setting.get("world_type", "玄幻")

        # 初始化或更新 TeamContext
        if team_context:
            team_context.set_current_chapter(chapter_number, volume_number)
            if not team_context.world_setting:
                team_context.set_novel_data(novel_data)
            logger.info(f"使用 TeamContext，当前步数: {team_context.current_steps}")

        # 从大纲中找到当前章节所属的卷（兼容 list 和 dict 格式）
        if isinstance(plot_outline, dict):
            volumes = plot_outline.get("volumes", [])
        elif isinstance(plot_outline, list):
            volumes = plot_outline  # 直接是卷列表
        else:
            volumes = []
        current_volume = None
        for vol in volumes:
            if vol.get("volume_num") == volume_number:
                current_volume = vol
                break

        # 构建情节上下文（优先使用 TeamContext 的增强上下文）
        if team_context:
            plot_context = team_context.build_enhanced_context(chapter_number)
        elif current_volume:
            plot_context = f"""
当前卷：第 {volume_number} 卷 - {current_volume.get('title', '')}
卷概要：{current_volume.get('summary', '')}
关键事件：{', '.join(current_volume.get('key_events', []))}
"""
        else:
            plot_context = json.dumps(plot_outline, ensure_ascii=False, indent=2)

        # 使用 TeamContext 的角色状态（如果可用）
        if team_context and not character_states:
            character_states = team_context.format_character_states()

        # ── 1. 章节策划 ──────────────────────────────────────
        planner_task = self.pm.format(
            self.pm.CHAPTER_PLANNER_TASK,
            chapter_number=chapter_number,
            volume_number=volume_number,
            novel_title=novel_title,
            genre=genre,
            plot_context=plot_context,
            previous_summary=previous_chapters_summary or "（本章为第一章）",
            character_states=character_states or "（初始状态）",
        )

        chapter_plan = await self._call_agent(
            agent_name="章节策划师",
            system_prompt=self.pm.CHAPTER_PLANNER_SYSTEM,
            task_prompt=planner_task,
            temperature=0.7,
            expect_json=True,
        )

        # 如果返回的是列表，自动转换为字典格式
        if isinstance(chapter_plan, list):
            chapter_plan = {"scenes": chapter_plan}
            logger.warning("章节策划师返回了列表格式，已自动转换为字典格式")

        # 记录到 TeamContext
        if team_context:
            team_context.add_agent_output("章节策划师", chapter_plan, f"第{chapter_number}章策划")

        # ── 1.5 章节大纲细化（动态决定是否需要） ─────────────────────
        detailed_outline = {}
        # 默认使用章节策划师的输出作为大纲文本（简单章节跳过细化时）
        detailed_outline_text = json.dumps(chapter_plan, ensure_ascii=False, indent=2)

        # 根据章节复杂度动态决定是否需要细化
        if self.enable_outline_refinement and self._should_refine_outline(
            chapter_plan, chapter_number
        ):
            logger.info(f"📋 大纲细化：开始细化第 {chapter_number} 章大纲...")

            # 构建全局大纲上下文
            plot_outline_context = self._build_plot_outline_context(
                plot_outline, volume_number, chapter_number
            )

            # 获取上一章的详细大纲和实际生成内容（用于衔接）
            prev_detailed = self._chapter_detailed_outlines.get(chapter_number - 1)
            prev_content = self._chapter_contents.get(chapter_number - 1, "")
            prev_summary = self._chapter_summaries.get(chapter_number - 1, {})

            if prev_detailed:
                prev_outline_text = json.dumps(prev_detailed, ensure_ascii=False, indent=2)
            else:
                prev_outline_text = "（无上一章细化大纲，本章为起始章或上一章未启用细化）"

            # 构建上一章实际内容摘要
            if prev_summary:
                prev_actual_content = f"""
上一章实际生成内容摘要：
{prev_summary.get('summary', '无')}

关键事件：
{chr(10).join('- ' + e for e in prev_summary.get('key_events', [])[:3]) if prev_summary.get('key_events') else '无'}

情感基调：{prev_summary.get('emotional_tone', '未指定')}
"""
            elif prev_content:
                # 如果没有摘要，使用内容的前500字
                prev_actual_content = f"上一章内容片段：\n{prev_content[:500]}..."
            else:
                prev_actual_content = "（无上一章内容，本章为起始章）"

            refiner_task = self.pm.format(
                self.pm.OUTLINE_REFINER_TASK,
                chapter_plan=json.dumps(chapter_plan, ensure_ascii=False, indent=2),
                plot_outline_context=plot_outline_context,
                previous_chapter_detailed_outline=prev_outline_text,
                previous_chapter_actual_content=prev_actual_content,
                character_states=character_states or "（初始状态）",
                chapter_number=chapter_number,
            )

            detailed_outline = await self._call_agent(
                agent_name="大纲细化师",
                system_prompt=self.pm.OUTLINE_REFINER_SYSTEM,
                task_prompt=refiner_task,
                temperature=0.6,
                expect_json=True,
            )

            # 如果返回的是列表，自动转换为字典格式
            if isinstance(detailed_outline, list):
                detailed_outline = {"detailed_scenes": detailed_outline}
                logger.warning("大纲细化师返回了列表格式，已自动转换为字典格式")

            # 缓存细化大纲
            self._chapter_detailed_outlines[chapter_number] = detailed_outline
            detailed_outline_text = json.dumps(detailed_outline, ensure_ascii=False, indent=2)

            logger.info(
                f"📋 大纲细化：第 {chapter_number} 章细化完成，"
                f"包含 {len(detailed_outline.get('detailed_scenes', []))} 个场景"
            )

            # 记录到 TeamContext
            if team_context:
                team_context.add_agent_output(
                    "大纲细化师", detailed_outline, f"第{chapter_number}章大纲细化"
                )

        # ── 2. 撰写初稿（支持设定查询） ────────────────────
        # 构建世界观简要
        world_brief = f"""
世界名称：{world_setting.get('world_name', '')}
世界类型：{world_setting.get('world_type', '')}
力量体系：{world_setting.get('power_system', {}).get('name', '')}
"""

        # 构建角色信息（仅包含本章出场角色）
        scenes = chapter_plan.get("scenes", [{}]) if isinstance(chapter_plan, dict) else [{}]
        first_scene = scenes[0] if scenes and isinstance(scenes[0], dict) else {}
        chapter_characters = (
            first_scene.get("characters", []) if isinstance(first_scene, dict) else []
        )
        character_info = ""
        for char in characters:
            if isinstance(char, dict) and char.get("name") in chapter_characters:
                char_line = (
                    f"\n- {char.get('name')}：{char.get('personality', '')}，"
                    f"{char.get('background', '')[:50]}..."
                )
                # 注入角色关系信息，帮助 Writer 准确刻画人物互动
                rel = char.get("relationships", {})
                if rel and isinstance(rel, dict):
                    rel_str = "、".join(f"{t}({r})" for t, r in rel.items())
                    char_line += f"\n  关系: {rel_str}"
                character_info += char_line

        # ── [新增] 图数据库上下文查询 ────────────────────────
        # 为 Writer Agent 注入图数据库查询结果，包括：
        # - 角色关系网络
        # - 待回收伏笔
        # - 一致性冲突警告
        graph_context = ""
        if self.enable_graph_context:
            graph_context = await self._build_graph_context_for_writer(
                novel_id=novel_data.get("id", ""),
                chapter_number=chapter_number,
                chapter_characters=chapter_characters,
            )

        # ── 构建前章关键事件列表（防止重复） ────────────────
        previous_key_events = self._build_previous_key_events(chapter_number)

        # ── 动态生成卷级摘要（用于冷记忆）─────────────────────────
        # 优先使用动态生成的卷摘要（基于实际写作进度）
        volume_summaries = self._generate_volume_summaries_dynamically(
            chapter_number=chapter_number, plot_outline=plot_outline
        )

        # 如果动态生成失败，回退到静态大纲摘要
        if volume_summaries is None and plot_outline:
            volumes = plot_outline.get("volumes", [])
            if volumes and isinstance(volumes, list):
                volume_summaries = {}
                for vol in volumes:
                    # 防御性检查：确保vol是字典类型
                    if not isinstance(vol, dict):
                        logger.warning(f"[VolumeSummary] 跳过非字典类型的卷数据: {type(vol)}")
                        continue
                    vol_num = vol.get("number")
                    vol_summary = vol.get("summary", "")
                    vol_chapters = vol.get("chapters", [])
                    if vol_num and vol_summary:
                        volume_summaries[vol_num] = {
                            "summary": vol_summary,
                            "chapters": vol_chapters if isinstance(vol_chapters, list) else [],
                        }
                if not volume_summaries:
                    volume_summaries = None
                else:
                    logger.info(
                        f"[VolumeSummary] 使用静态大纲卷摘要: {list(volume_summaries.keys())}"
                    )

        if volume_summaries:
            logger.info(
                f"[VolumeSummary] 提取到 {len(volume_summaries)} 个卷摘要: "
                f"{list(volume_summaries.keys())}"
            )

        # ── 使用分层压缩构建前章结尾 ─────────────────────
        compressed = self.context_compressor.compress(
            chapter_number=chapter_number,
            chapter_summaries=self._chapter_summaries,
            chapter_contents=self._chapter_contents,
            world_setting=world_setting,
            characters=characters,
            plot_outline=plot_outline,
            volume_summaries=volume_summaries,
        )

        # 选择带查询能力的 Writer prompt 还是普通的
        if self.enable_query:
            writer_system = self.pm.format(
                self.pm.WRITER_WITH_QUERY_SYSTEM,
                genre=genre,
            )
            writer_task = self.pm.format(
                self.pm.WRITER_WITH_QUERY_TASK,
                chapter_number=chapter_number,
                chapter_plan=json.dumps(chapter_plan, ensure_ascii=False, indent=2),
                detailed_outline=detailed_outline_text,
                world_setting_brief=world_brief,
                character_info=character_info or "（主要角色）",
                graph_context=graph_context,
                chapter_title=chapter_plan.get("title", ""),
                query_answers="",
                previous_key_events=previous_key_events,
                compressed_context=compressed.to_prompt(),
            )
        else:
            writer_system = self.pm.format(self.pm.WRITER_SYSTEM, genre=genre)
            writer_task = self.pm.format(
                self.pm.WRITER_TASK,
                chapter_number=chapter_number,
                chapter_plan=json.dumps(chapter_plan, ensure_ascii=False, indent=2),
                detailed_outline=detailed_outline_text,
                world_setting_brief=world_brief,
                character_info=character_info or "（主要角色）",
                graph_context=graph_context,
                chapter_title=chapter_plan.get("title", ""),
                previous_key_events=previous_key_events,
                compressed_context=compressed.to_prompt(),
            )

        draft = await self._call_agent(
            agent_name="作家",
            system_prompt=writer_system,
            task_prompt=writer_task,
            temperature=0.85,
            max_tokens=4096,
            expect_json=False,  # 返回纯文本
        )

        # 处理 [QUERY] 标记（最多 2 轮查询）
        if self.enable_query:
            draft = await self._handle_writer_queries(
                draft=draft,
                world_setting=world_setting,
                characters=characters,
                plot_outline=plot_outline,
                chapter_number=chapter_number,
                chapter_plan=chapter_plan,
                writer_system=writer_system,
                world_brief=world_brief,
                character_info=character_info,
                previous_chapters_summary=previous_chapters_summary,
                detailed_outline_text=detailed_outline_text,
                previous_key_events=previous_key_events,
                compressed_context=compressed.to_prompt(),
            )

        # 记录到 TeamContext
        if team_context:
            team_context.add_agent_output(
                "作家", {"draft_length": len(draft)}, f"第{chapter_number}章初稿"
            )

        # ── 3. Writer-Editor 审查反馈循环（含跨章节连贯性检查） ─────────────────────
        chapter_plan_json = json.dumps(chapter_plan, ensure_ascii=False, indent=2)

        # 构建时间线锚点信息（用于跨章节时间一致性检查）
        timeline_anchor = ""
        if team_context and team_context.timeline:
            recent_events = team_context.get_recent_timeline(5)
            if recent_events:
                timeline_anchor = f"""当前故事时间：第 {team_context.current_story_day} 天
最近事件：
{recent_events}

**检查要点**：本章的时间推进是否合理？是否与前文时间线矛盾？"""

        # 查询图库中与本章角色相关的冲突（注入编辑进行跨章节连贯性检查）
        graph_conflicts_context = await self._query_graph_conflicts_for_continuity(
            novel_id=str(novel_data.get("id", "")),
            chapter_characters=chapter_characters,
            chapter_number=chapter_number,
        )

        review_result = await self.review_handler.execute(
            initial_draft=draft,
            chapter_number=chapter_number,
            chapter_title=chapter_plan.get("title", ""),
            chapter_summary=chapter_plan.get("summary", ""),
            chapter_plan_json=chapter_plan_json,
            writer_system_prompt=writer_system,
            team_context=team_context,
            previous_chapters_summary=previous_chapters_summary,
            timeline_anchor=timeline_anchor,
            graph_conflicts_context=graph_conflicts_context,
        )

        edited_content = review_result.final_content

        # 记录到 TeamContext
        if team_context:
            team_context.add_agent_output(
                "编辑",
                {
                    "edited_length": len(edited_content),
                    "review_iterations": review_result.total_iterations,
                    "final_score": review_result.final_score,
                },
                f"第{chapter_number}章审查循环",
            )

        # ── 4. 最终内容（连续性检查已合并到编辑中） ─────────────────────────
        final_content = edited_content
        continuity_report = None  # 连续性检查已合并到编辑的cross_chapter_coherence维度

        # 更新 TeamContext 的角色状态和时间线
        if team_context:
            # 更新本章出场角色的状态
            for char_name in chapter_characters:
                team_context.update_character_state(
                    char_name, last_appearance_chapter=chapter_number
                )
            # 添加时间线事件
            if chapter_plan.get("summary"):
                team_context.add_timeline_event(
                    chapter_number=chapter_number,
                    event=chapter_plan.get("summary", "")[:100],
                    characters=chapter_characters,
                )

        # 获取质量评分
        quality_score = review_result.final_score

        # ── 5. 相似度检测 ─────────────────────────────────────
        similarity_report = None
        if self._chapter_contents:
            # 取前 N 章内容进行比较
            compare_chapters = {}
            for ch in range(max(1, chapter_number - 3), chapter_number):
                if ch in self._chapter_contents:
                    compare_chapters[ch] = self._chapter_contents[ch]

            if compare_chapters:
                similarity_report = self.similarity_detector.detect(
                    new_content=final_content,
                    previous_chapters=compare_chapters,
                    current_chapter=chapter_number,
                )

                if similarity_report.is_duplicate:
                    logger.warning(
                        f"⚠️  第{chapter_number}章与第{similarity_report.most_similar_chapter}章"
                        f"内容相似度过高({similarity_report.overall_similarity:.1%})，"
                        f"请求重写..."
                    )
                    # 在提示词中加入差异化要求，重新生成
                    rewrite_task = f"""第{chapter_number}章的内容与第{similarity_report.most_similar_chapter}章过于相似.

以下句子在两章中重复出现：
{chr(10).join('- ' + s for s in similarity_report.duplicate_sentences[:3])}

请重新撰写第{chapter_number}章，要求：
1. 避免重复以上内容
2. 确保情节有实质性推进
3. 使用不同的开场方式和叙事角度

章节计划：
{json.dumps(chapter_plan, ensure_ascii=False, indent=2)}

请直接输出完整的重写内容。"""

                    rewritten = await self._call_agent(
                        agent_name="作家(重写)",
                        system_prompt=writer_system,
                        task_prompt=rewrite_task,
                        temperature=0.9,
                        max_tokens=4096,
                        expect_json=False,
                    )
                    if rewritten and len(rewritten) > len(final_content) * 0.3:
                        final_content = rewritten
                        logger.info(f"✅ 第{chapter_number}章重写完成")

        # ── 6. 生成 LLM 摘要并缓存 ──────────────────────────
        chapter_summary = await self.summary_generator.generate_summary(
            chapter_number=chapter_number,
            chapter_content=final_content,
            chapter_plan=chapter_plan,
        )
        self._chapter_summaries[chapter_number] = chapter_summary
        self._chapter_contents[chapter_number] = final_content

        # ── 7. 异步提取人物关系（基于前N章累积分析）────────────────
        # 使用 asyncio.create_task 实现异步执行，不阻塞主流程
        if chapter_number >= 2:
            asyncio.create_task(
                self._extract_relationships_from_recent_chapters(
                    chapter_number=chapter_number,
                    max_lookback=5,
                )
            )

        logger.info("=" * 60)
        logger.info(f"🎉 第 {chapter_number} 章写作完成！")
        logger.info(
            f"   审查循环：{review_result.total_iterations} 轮, "
            f"score={review_result.final_score:.1f}, "
            f"converged={review_result.converged}"
        )
        logger.info(f"   连续性评分：{quality_score}")
        # 处理 continuity_report 可能是 list 或 dict 的情况
        if isinstance(continuity_report, dict):
            issues_count = len(continuity_report.get("issues", []))
        elif isinstance(continuity_report, list):
            issues_count = len(continuity_report)
        else:
            issues_count = 0
        logger.info(f"   发现问题：{issues_count} 个")
        logger.info("=" * 60)

        return {
            "chapter_plan": chapter_plan,
            "detailed_outline": detailed_outline,
            "draft": draft,
            "edited_content": edited_content,
            "final_content": final_content,
            "continuity_report": continuity_report,
            "quality_score": quality_score,
            "review_loop_result": review_result.to_dict(),
            "similarity_report": (similarity_report.to_dict() if similarity_report else None),
            "chapter_summary": chapter_summary,
        }

    def _update_character_importance(
        self,
        characters: list,
        chapter_number: int,
    ) -> list[str]:
        """更新角色出场统计并返回重要角色列表.

        Args:
            characters: 本章抽取的角色列表
            chapter_number: 当前章节号

        Returns:
            重要角色名称列表
        """
        from backend.services.entity_extractor_service import ExtractedCharacter

        important_chars = []

        for char in characters:
            if not isinstance(char, ExtractedCharacter):
                continue

            name = char.name
            if not name:
                continue

            # 更新出场统计
            if name not in self._character_appearance_tracker:
                self._character_appearance_tracker[name] = {
                    "first_appearance": chapter_number,
                    "appearance_count": 0,
                    "chapters": [],
                    "role_type": char.role_type,
                    "is_important": False,
                }

            tracker = self._character_appearance_tracker[name]
            tracker["appearance_count"] += 1
            tracker["chapters"].append(chapter_number)

            # 更新角色类型（如果新抽取的类型更具体）
            if char.role_type != "minor" and tracker["role_type"] == "minor":
                tracker["role_type"] = char.role_type

            # 判断角色重要性
            # 规则1: 出场次数 >= 2
            # 规则2: 角色类型不是 minor (protagonist/supporting/antagonist)
            # 规则3: 在首章出场
            is_important = (
                tracker["appearance_count"] >= 2
                or tracker["role_type"] in ["protagonist", "supporting", "antagonist"]
                or tracker["first_appearance"] == 1
            )

            tracker["is_important"] = is_important

            if is_important:
                important_chars.append(name)

        return important_chars

    async def _extract_relationships_from_recent_chapters(
        self,
        chapter_number: int,
        max_lookback: int = 5,
    ) -> list[dict]:
        """异步提取最近章节的人物关系.

        基于前N章内容累积分析，提高关系判定准确性。

        Args:
            chapter_number: 当前章节号
            max_lookback: 最大回溯章节数（默认5章）

        Returns:
            确认的人物关系列表
        """
        # 确定要分析的章节范围
        start_chapter = max(1, chapter_number - max_lookback + 1)
        chapters_to_analyze = list(range(start_chapter, chapter_number + 1))

        if len(chapters_to_analyze) < 2:
            logger.info("[RelationshipExtraction] 章节数不足，跳过关系提取")
            return []

        # 收集可用章节内容
        available_chapters = {}
        for ch in chapters_to_analyze:
            if ch in self._chapter_contents:
                available_chapters[ch] = self._chapter_contents[ch]

        if len(available_chapters) < 2:
            logger.info("[RelationshipExtraction] 可用章节内容不足，跳过关系提取")
            return []

        logger.info(
            f"[RelationshipExtraction] 开始分析第{start_chapter}-{chapter_number}章的人物关系，"
            f"共{len(available_chapters)}章可用"
        )

        try:
            # 构建合并的章节内容（不截断单章内容）
            combined_content = ""
            for ch_num in sorted(available_chapters.keys()):
                content = available_chapters[ch_num]
                # 不再截断单章内容，完整使用每章内容
                # 平均每章3000-4000字符，5章最多约20000字符
                combined_content += f"\n\n=== 第{ch_num}章 ===\n{content}"

            # 仅作为安全保护，限制极端情况下的总长度（如超长章节）
            if len(combined_content) > 25000:
                combined_content = combined_content[:25000] + "\n...（内容过长已截断）"
                logger.warning("[RelationshipExtraction] 合并内容超过25000字符，已截断")

            # 调用LLM提取关系
            from backend.services.entity_extractor_service import EntityExtractorService

            extractor = EntityExtractorService()

            # 获取已知角色
            known_characters = list(
                set(
                    name
                    for rel_key in self._character_relationship_accumulator.keys()
                    for name in rel_key
                )
            )

            # 提取实体和关系
            extraction_result = await extractor.extract_from_chapter(
                chapter_number=chapter_number,
                chapter_content=combined_content,
                known_characters=known_characters if known_characters else None,
            )

            # 更新角色重要性统计
            important_chars = self._update_character_importance(
                extraction_result.characters, chapter_number
            )

            logger.info(
                f"[RelationshipExtraction] 本章发现 {len(extraction_result.characters)} 个角色，"
                f"其中重要角色 {len(important_chars)} 个: {important_chars[:5]}..."
            )

            # 过滤关系：只保留重要角色之间的关系
            filtered_relationships = []
            for rel in extraction_result.relationships:
                if rel.from_character in important_chars and rel.to_character in important_chars:
                    filtered_relationships.append(rel)
                elif rel.from_character in important_chars or rel.to_character in important_chars:
                    # 保留涉及至少一个重要角色的关系
                    filtered_relationships.append(rel)

            logger.info(
                f"[RelationshipExtraction] 原始关系 {len(extraction_result.relationships)} 个，"
                f"过滤后保留 {len(filtered_relationships)} 个（涉及重要角色）"
            )

            # 累积关系信息（只处理过滤后的关系）
            confirmed_relationships = []
            for rel in filtered_relationships:
                rel_key = (rel.from_character, rel.to_character)
                reverse_key = (rel.to_character, rel.from_character)

                # 检查是否已有记录
                if rel_key in self._character_relationship_accumulator:
                    acc = self._character_relationship_accumulator[rel_key]
                elif reverse_key in self._character_relationship_accumulator:
                    acc = self._character_relationship_accumulator[reverse_key]
                else:
                    acc = {
                        "mentions": 0,
                        "types": [],
                        "strengths": [],
                        "first_chapter": chapter_number,
                    }
                    self._character_relationship_accumulator[rel_key] = acc

                # 更新累积信息
                acc["mentions"] += 1
                acc["types"].append(rel.relation_type)
                acc["strengths"].append(rel.strength)
                acc["last_chapter"] = chapter_number

                # 当关系被多次提及时，确认为稳定关系
                if acc["mentions"] >= 2:
                    # 使用多数投票确定关系类型
                    from collections import Counter

                    type_counts = Counter(acc["types"])
                    confirmed_type = type_counts.most_common(1)[0][0]
                    avg_strength = sum(acc["strengths"]) / len(acc["strengths"])

                    confirmed_rel = {
                        "from_character": rel.from_character,
                        "to_character": rel.to_character,
                        "relation_type": confirmed_type,
                        "strength": round(avg_strength, 1),
                        "mentions": acc["mentions"],
                        "is_confirmed": True,
                    }
                    if confirmed_rel not in confirmed_relationships:
                        confirmed_relationships.append(confirmed_rel)

            logger.info(
                f"[RelationshipExtraction] 关系提取完成: "
                f"发现{len(extraction_result.relationships)}个关系，"
                f"确认{len(confirmed_relationships)}个稳定关系"
            )

            return confirmed_relationships

        except Exception as e:
            logger.error(f"[RelationshipExtraction] 关系提取失败: {e}")
            return []

    def get_important_character_relationships(self) -> dict:
        """获取重要角色的关系网络.

        Returns:
            {
                "characters": {
                    "角色名": {
                        "appearance_count": 3,
                        "role_type": "supporting",
                        "relationships": [
                            {"to": "角色B", "type": "friend", "strength": 8}
                        ]
                    }
                },
                "confirmed_relationships": [...]
            }
        """
        result = {"characters": {}, "confirmed_relationships": []}

        # 收集重要角色
        for name, tracker in self._character_appearance_tracker.items():
            if tracker.get("is_important", False):
                result["characters"][name] = {
                    "appearance_count": tracker["appearance_count"],
                    "chapters": tracker["chapters"],
                    "role_type": tracker["role_type"],
                    "relationships": [],
                }

        # 收集已确认的关系
        for (from_char, to_char), acc in self._character_relationship_accumulator.items():
            if acc["mentions"] >= 2:
                from collections import Counter

                confirmed_type = Counter(acc["types"]).most_common(1)[0][0]
                avg_strength = sum(acc["strengths"]) / len(acc["strengths"])

                rel_info = {
                    "from": from_char,
                    "to": to_char,
                    "type": confirmed_type,
                    "strength": round(avg_strength, 1),
                    "mentions": acc["mentions"],
                }
                result["confirmed_relationships"].append(rel_info)

                # 添加到角色的关系列表
                if from_char in result["characters"]:
                    result["characters"][from_char]["relationships"].append(
                        {"to": to_char, "type": confirmed_type, "strength": round(avg_strength, 1)}
                    )

        return result

    def _should_refine_outline(self, chapter_plan: dict, chapter_number: int) -> bool:
        """评估章节是否需要细化步骤.

        根据章节复杂度动态决定是否需要调用大纲细化师。
        复杂章节启用细化可以提供更详细的写作指导。

        Args:
            chapter_plan: 章节策划结果
            chapter_number: 章节号

        Returns:
            True 表示需要细化，False 表示可以跳过细化步骤
        """
        reasons_to_refine = []

        # 1. 场景数量 > 3 则需要细化
        scenes = chapter_plan.get("scenes", [])
        if len(scenes) > 3:
            reasons_to_refine.append("多场景章节")

        # 2. 检查章节类型标记
        if chapter_plan.get("is_milestone") or chapter_plan.get("is_climax"):
            reasons_to_refine.append("关键章节")

        # 3. 黄金三章（前3章）需要细化
        if chapter_number <= 3:
            reasons_to_refine.append("黄金三章")

        # 4. 涉及多个转折点
        plot_points = chapter_plan.get("plot_points", [])
        if len(plot_points) > 2:
            reasons_to_refine.append("多转折点")

        if reasons_to_refine:
            logger.info(f"章节{chapter_number}需要细化: {', '.join(reasons_to_refine)}")
            return True

        logger.info(f"章节{chapter_number}复杂度较低，跳过细化步骤")
        return False

    def _build_plot_outline_context(
        self, plot_outline: dict | list, volume_number: int, chapter_number: int
    ) -> str:
        """构建大纲上下文（入口方法）.

        提取内容包括：
        - 主线剧情核心冲突
        - 当前卷的关键转折点
        - 张力循环（欲扬先抑）位置
        - 升级里程碑
        - 黄金三章设计（前3章适用）

        Args:
            plot_outline: 全局情节大纲
            volume_number: 当前卷号
            chapter_number: 当前章节号

        Returns:
            格式化的大纲上下文字符串
        """
        if not plot_outline:
            return "（无全局大纲信息）"

        parts = []
        parts.extend(self._extract_main_plot_context(plot_outline))
        parts.extend(self._extract_golden_chapters_context(plot_outline, chapter_number))
        parts.extend(self._extract_turning_points_context(plot_outline))
        parts.extend(self._extract_volume_context(plot_outline, volume_number))
        return "\n".join(parts) if parts else "（无全局大纲信息）"

    def _extract_main_plot_context(self, plot_outline: dict | list) -> list[str]:
        """提取主线剧情相关上下文.

        Args:
            plot_outline: 全局情节大纲

        Returns:
            主线剧情上下文字符串列表
        """
        parts = []
        if isinstance(plot_outline, dict):
            main_plot = plot_outline.get("main_plot", {})
            if main_plot:
                parts.append(f"【主线剧情】核心冲突：{main_plot.get('core_conflict', '未知')}")
                parts.append(f"  主题：{main_plot.get('theme', '未知')}")
        return parts

    def _extract_golden_chapters_context(
        self, plot_outline: dict | list, chapter_number: int
    ) -> list[str]:
        """提取黄金三章/关键章节上下文.

        Args:
            plot_outline: 全局情节大纲
            chapter_number: 当前章节号

        Returns:
            黄金三章上下文字符串列表
        """
        parts = []
        if isinstance(plot_outline, dict) and chapter_number <= 3:
            golden = plot_outline.get("golden_three_chapters", {})
            if golden:
                parts.append("【黄金三章设计】")
                for key, val in golden.items():
                    parts.append(f"  {key}: {val}")
        return parts

    def _extract_turning_points_context(self, plot_outline: dict | list) -> list[str]:
        """提取转折点上下文.

        Args:
            plot_outline: 全局情节大纲

        Returns:
            转折点上下文字符串列表
        """
        parts = []
        if isinstance(plot_outline, dict):
            turning_points = plot_outline.get("key_turning_points", [])
            if turning_points:
                parts.append("【全局关键转折点】")
                for tp in turning_points[:5]:
                    if isinstance(tp, str):
                        parts.append(f"  - {tp}")
                    elif isinstance(tp, dict):
                        parts.append(f"  - {tp.get('event', tp.get('description', str(tp)))}")
        return parts

    def _extract_volume_context(self, plot_outline: dict | list, volume_number: int) -> list[str]:
        """提取分卷上下文.

        Args:
            plot_outline: 全局情节大纲
            volume_number: 当前卷号

        Returns:
            分卷上下文字符串列表
        """
        parts = []
        if isinstance(plot_outline, dict):
            volumes = plot_outline.get("volumes", [])
            for vol in volumes:
                if vol.get("volume_num") == volume_number:
                    parts.append(f"【当前卷】第{volume_number}卷 - {vol.get('title', '')}")
                    parts.append(f"  概要：{vol.get('summary', '')}")
                    parts.extend(self._extract_tension_cycles(vol))
                    parts.extend(self._extract_upgrade_milestones(vol))
                    break
        elif isinstance(plot_outline, list):
            # 直接是卷列表格式
            for vol in plot_outline:
                if vol.get("volume_num") == volume_number:
                    parts.append(f"【当前卷】第{volume_number}卷 - {vol.get('title', '')}")
                    parts.append(f"  概要：{vol.get('summary', '')}")
                    break
        return parts

    def _extract_tension_cycles(self, vol: dict) -> list[str]:
        """提取张力循环信息.

        Args:
            vol: 卷信息字典

        Returns:
            张力循环上下文字符串列表
        """
        parts = []
        tension_cycles = vol.get("tension_cycles", [])
        if tension_cycles:
            parts.append("  张力循环：")
            for tc in tension_cycles:
                if isinstance(tc, dict):
                    suppress = tc.get("suppress_event", tc.get("suppress", ""))
                    release = tc.get("release_event", tc.get("release", ""))
                    parts.append(f"    - 压制: {suppress} → 释放: {release}")
                elif isinstance(tc, str):
                    parts.append(f"    - {tc}")
        return parts

    def _extract_upgrade_milestones(self, vol: dict) -> list[str]:
        """提取升级里程碑信息.

        Args:
            vol: 卷信息字典

        Returns:
            升级里程碑上下文字符串列表
        """
        parts = []
        milestone = vol.get("upgrade_milestone", "")
        if milestone:
            parts.append(f"  升级里程碑：{milestone}")
        else:
            milestones = vol.get("upgrade_milestones", vol.get("power_milestones", []))
            if milestones:
                parts.append("  升级里程碑：")
                for ms in milestones:
                    if isinstance(ms, str):
                        parts.append(f"    - {ms}")
                    elif isinstance(ms, dict):
                        parts.append(f"    - {ms.get('event', str(ms))}")
        return parts

    def _build_previous_key_events(self, chapter_number: int) -> str:
        """构建前几章的关键事件列表（用于防止重复）."""
        events = []
        for ch in range(max(1, chapter_number - 3), chapter_number):
            if ch not in self._chapter_summaries:
                continue
            summary = self._chapter_summaries[ch]
            key_events = summary.get("key_events", [])
            for event in key_events[:3]:
                if isinstance(event, str):
                    events.append(f"第{ch}章: {event}")
                elif isinstance(event, dict):
                    events.append(f"第{ch}章: {event.get('event', str(event))}")
        return "\n".join(events) if events else "（无前章记录）"

    def _generate_volume_summaries_dynamically(
        self, chapter_number: int, plot_outline: Optional[dict] = None
    ) -> Optional[dict[int, dict[str, any]]]:
        """基于已生成章节摘要动态生成卷摘要.

        Args:
            chapter_number: 当前章节号
            plot_outline: 大纲数据（用于获取卷章节范围）

        Returns:
            卷摘要字典: {卷号: {"summary": 摘要, "chapters": [start, end]}}
        """
        if not self._chapter_summaries:
            return None

        # 从大纲获取卷章节范围（如果可用）
        volume_ranges = {}
        if plot_outline:
            volumes = plot_outline.get("volumes", [])
            for vol in volumes:
                if isinstance(vol, dict):
                    vol_num = vol.get("number")
                    vol_chapters = vol.get("chapters", [])
                    if vol_num and isinstance(vol_chapters, list) and len(vol_chapters) >= 2:
                        volume_ranges[vol_num] = (vol_chapters[0], vol_chapters[1])

        # 按卷聚合章节摘要
        volume_summaries = {}
        cold_end = max(1, chapter_number - 10)  # 冷记忆起始点

        for ch_num, summary in self._chapter_summaries.items():
            if ch_num >= cold_end:
                continue  # 只处理冷记忆范围内的章节

            # 确定章节所属卷
            if volume_ranges:
                vol_num = None
                for vnum, (start, end) in volume_ranges.items():
                    if start <= ch_num <= end:
                        vol_num = vnum
                        break
            else:
                # 默认每卷10章
                vol_num = (ch_num - 1) // 10 + 1

            if vol_num is None:
                continue

            if vol_num not in volume_summaries:
                volume_summaries[vol_num] = {"summaries": [], "chapters": []}

            # 提取章节关键信息
            plot_progress = summary.get("plot_progress", "") if isinstance(summary, dict) else ""
            key_events = summary.get("key_events", []) if isinstance(summary, dict) else []

            volume_summaries[vol_num]["summaries"].append(
                {"chapter": ch_num, "plot_progress": plot_progress, "key_events": key_events}
            )
            volume_summaries[vol_num]["chapters"].append(ch_num)

        # 生成卷级摘要
        result = {}
        for vol_num, data in volume_summaries.items():
            if not data["summaries"]:
                continue

            # 聚合关键事件
            all_events = []
            for s in data["summaries"]:
                all_events.extend(s["key_events"])

            # 生成简洁的卷摘要
            event_text = "；".join(all_events[:5])  # 最多5个关键事件
            chapter_range = [min(data["chapters"]), max(data["chapters"])]

            result[vol_num] = {
                "summary": f"本卷包含第{chapter_range[0]}-{chapter_range[1]}章。{event_text}",
                "chapters": chapter_range,
            }

        return result if result else None

    async def _handle_writer_queries(
        self,
        draft: str,
        world_setting: dict,
        characters: list,
        plot_outline: dict,
        chapter_number: int,
        chapter_plan: dict,
        writer_system: str,
        world_brief: str,
        character_info: str,
        previous_chapters_summary: str,
        detailed_outline_text: str = "（未启用大纲细化）",
        previous_key_events: str = "（无前章记录）",
        max_query_rounds: int = 2,
        compressed_context: str = "",
    ) -> str:
        """处理 Writer 输出中的 [QUERY] 标记.

        解析查询标记，调用 AgentQueryService 获取答案，
        然后让 Writer 在答案基础上重新写作。

        Args:
            draft: Writer 的原始输出（可能包含 [QUERY] 标记）
            max_query_rounds: 最大查询轮次

        Returns:
            最终的章节内容（不含查询标记）
        """
        for round_num in range(1, max_query_rounds + 1):
            queries = AgentQueryService.parse_query_tags(draft)
            if not queries:
                return draft

            logger.info(f"[Query] 第 {round_num} 轮: 检测到 {len(queries)} 个查询")

            # 处理每个查询
            answers = []
            for q in queries[:3]:  # 每轮最多 3 个查询
                query_type = q["type"]

                # 处理图数据库查询
                if query_type.startswith("graph:"):
                    graph_answer = await self._handle_graph_query(
                        query=q, novel_id=getattr(self, "_novel_id", None)
                    )
                    answers.append(f"关于「{q['question'][:30]}」的回答: {graph_answer}")
                    continue

                kb_map = {
                    "world": json.dumps(world_setting, ensure_ascii=False),
                    "character": json.dumps(characters, ensure_ascii=False),
                    "plot": json.dumps(plot_outline, ensure_ascii=False),
                }
                answer = await self.query_service.query(
                    requester="作家",
                    target_type=query_type,
                    question=q["question"],
                    knowledge_base=kb_map.get(query_type, ""),
                    chapter_number=chapter_number,
                )
                answers.append(f"关于「{q['question'][:30]}」的回答: {answer}")

            # 用查询答案重新调用 Writer
            query_answers_text = "以下是你之前提出的设定疑问的回答，请据此完善内容：\n" + "\n".join(
                answers
            )
            AgentQueryService.remove_query_tags(draft)

            rewrite_task = self.pm.format(
                self.pm.WRITER_WITH_QUERY_TASK,
                chapter_number=chapter_number,
                chapter_plan=json.dumps(chapter_plan, ensure_ascii=False, indent=2),
                detailed_outline=detailed_outline_text,
                world_setting_brief=world_brief,
                character_info=character_info or "（主要角色）",
                graph_context="",
                chapter_title=chapter_plan.get("title", ""),
                query_answers=query_answers_text,
                previous_key_events=previous_key_events,
                compressed_context=compressed_context,
            )

            draft = await self._call_agent(
                agent_name="作家(重写)",
                system_prompt=writer_system,
                task_prompt=rewrite_task,
                temperature=0.80,
                max_tokens=4096,
                expect_json=False,
            )

        # 最终确保没有残留的查询标记
        return AgentQueryService.remove_query_tags(draft)

    async def _handle_graph_query(self, query: dict, novel_id: Optional[str] = None) -> str:
        """处理图数据库查询.

        支持以下查询类型：
        - graph:network: 查询角色关系网络
        - graph:path: 查询两个角色间的关系路径
        - graph:foreshadowing: 查询章节相关伏笔
        - graph:conflict: 查询角色相关冲突

        Args:
            query: 查询字典，包含 type 和 question
            novel_id: 小说ID

        Returns:
            查询结果文本
        """
        if not novel_id:
            return "（图数据库查询失败：小说ID未设置）"

        from backend.config import settings

        if not getattr(settings, "ENABLE_GRAPH_QUERY_FOR_WRITER", True):
            return "（图数据库查询功能未启用）"

        try:
            from agents.graph_query_mixin import GraphQueryMixin

            mixin = GraphQueryMixin()
            mixin.set_graph_context(novel_id)

            query_subtype = query["type"].replace("graph:", "")
            question = query["question"]

            # 处理不同类型的图查询
            if query_subtype == "network":
                # 查询角色关系网络
                network = await mixin.query_character_network(question, depth=2)
                if network:
                    return mixin.format_network_context(network)
                return f"（未找到角色 '{question}' 的关系网络）"

            elif query_subtype == "path":
                # 查询两个角色间路径，格式："角色A->角色B"
                if "->" in question:
                    chars = question.split("->")
                    if len(chars) == 2:
                        path = await mixin.query_character_path(chars[0].strip(), chars[1].strip())
                        if path:
                            return mixin.format_path_context(path)
                        return f"（未找到 '{chars[0]}' 到 '{chars[1]}' 的关系路径）"
                return "（路径查询格式错误，请使用：角色A->角色B）"

            elif query_subtype == "foreshadowing":
                # 查询章节相关伏笔
                try:
                    chapter_num = int(question)
                    foreshadowings = await mixin.query_pending_foreshadowings(chapter_num)
                    return mixin.format_foreshadowings_context(foreshadowings)
                except ValueError:
                    return "（伏笔查询需要章节号，请提供数字）"

            elif query_subtype == "conflict":
                # 查询角色相关冲突
                conflicts = await mixin.check_conflicts()
                char_conflicts = [c for c in conflicts if question in c.characters]
                if char_conflicts:
                    return mixin.format_conflicts_context(char_conflicts)
                return f"（未找到角色 '{question}' 相关的冲突）"

            else:
                return f"（未知的图查询类型：{query_subtype}）"

        except Exception as e:
            logger.warning(f"[GraphQuery] 处理查询失败: {e}")
            return f"（图数据库查询失败：{str(e)}）"

    async def refine_outline_comprehensive(
        self,
        outline: dict,
        world_setting: dict,
        characters: list,
        options: dict,
        max_rounds: int = 3,
    ) -> dict:
        """综合大纲完善功能.

        对现有大纲进行全面的质量评估和优化，包括：
        - 结构完整性检查
        - 角色发展弧线优化
        - 情节节奏调整
        - 世界观融合度提升
        - 伏笔和呼应完善

        Args:
            outline: 当前大纲
            world_setting: 世界观设定
            characters: 角色列表
            options: 完善选项
            max_rounds: 最大迭代轮次

        Returns:
            包含完善结果的字典
        """
        logger.info("🎯 开始综合大纲完善...")

        # 初始化结果
        current_outline = outline.copy()
        improvements_made = []
        round_history = []

        # 用于累积所有生成的字段
        accumulated_main_plot = outline.get("main_plot", {}) or {}

        for round_num in range(1, max_rounds + 1):
            logger.info(f"🔄 完善轮次 {round_num}/{max_rounds}")

            # 1. 分析当前大纲问题
            analysis_result = await self._analyze_outline_issues(
                current_outline, world_setting, characters
            )

            # 2. 生成优化建议
            suggestions = await self._generate_optimization_suggestions(
                analysis_result, current_outline, world_setting, characters
            )

            # 3. 应用优化
            optimized_outline = await self._apply_outline_optimizations(
                current_outline, suggestions, world_setting, characters
            )

            # 防御性检查：确保 optimized_outline 是 dict
            if not isinstance(optimized_outline, dict):
                logger.warning(
                    f"第{round_num}轮优化返回非dict类型 "
                    f"({type(optimized_outline).__name__})，跳过本轮"
                )
                continue

            # 4. 合并main_plot字段，确保不丢失已生成的字段
            optimized_main_plot = optimized_outline.get("main_plot", {}) or {}
            for field, value in optimized_main_plot.items():
                if value:  # 只保存非空值
                    accumulated_main_plot[field] = value

            # 确保optimized_outline包含累积的所有字段
            optimized_outline["main_plot"] = accumulated_main_plot.copy()

            # 记录本轮改进
            round_improvements = self._extract_improvements(
                current_outline, optimized_outline, suggestions
            )
            improvements_made.extend(round_improvements)

            round_history.append(
                {
                    "round": round_num,
                    "analysis": analysis_result,
                    "suggestions": suggestions,
                    "improvements": round_improvements,
                }
            )

            # 更新当前大纲
            current_outline = optimized_outline

            logger.info(f"第{round_num}轮后main_plot字段: {list(accumulated_main_plot.keys())}")

            # 检查是否达到质量阈值或收敛
            if self._should_stop_refinement(analysis_result, options):
                logger.info(f"✅ 完善在第 {round_num} 轮达到质量要求")
                break

        # 循环结束后，最终检查并补全缺失字段
        main_plot_fields = [
            "core_conflict",
            "protagonist_goal",
            "antagonist",
            "progression_path",
            "emotional_arc",
            "key_revelations",
            "character_growth",
            "resolution",
        ]
        final_main_plot = current_outline.get("main_plot", {}) or {}
        final_missing = [f for f in main_plot_fields if not final_main_plot.get(f)]

        if final_missing:
            logger.warning(f"完善循环结束后仍有缺失字段: {final_missing}，进行最终补全")
            try:
                generated = await self._generate_missing_main_plot_fields(
                    core_conflict=final_main_plot.get("core_conflict", ""),
                    existing_fields=final_main_plot,
                    missing_fields=final_missing,
                    world_setting=world_setting,
                    characters=characters,
                )
                for field, value in generated.items():
                    if value:
                        final_main_plot[field] = value
                current_outline["main_plot"] = final_main_plot
                logger.info(f"最终补全后main_plot字段: {list(final_main_plot.keys())}")
            except Exception as e:
                logger.error(f"最终补全失败: {e}")
                # 尝试简化版补全
                try:
                    simple_generated = await self._generate_missing_main_plot_fields_simple(
                        existing_fields=final_main_plot,
                        missing_fields=final_missing,
                        world_setting=world_setting,
                        characters=characters,
                    )
                    for field, value in simple_generated.items():
                        if value:
                            final_main_plot[field] = value
                    current_outline["main_plot"] = final_main_plot
                    logger.info(f"简化最终补全后main_plot字段: {list(final_main_plot.keys())}")
                except Exception as e2:
                    logger.error(f"简化最终补全也失败: {e2}")

        logger.info(f"🎯 大纲完善完成，共进行 {len(round_history)} 轮优化")

        return {
            "enhancement_result": {
                "enhanced_outline": current_outline,
                "improvements_made": improvements_made,
                "round_history": round_history,
                "total_rounds": len(round_history),
            }
        }

    async def _analyze_outline_issues(
        self, outline: dict, world_setting: dict, characters: list
    ) -> dict:
        """分析大纲存在的问题."""
        analysis_prompt = f"""
请分析以下小说大纲存在的问题和不足之处：

大纲内容：
{json.dumps(outline, ensure_ascii=False, indent=2)}

世界观设定：
{json.dumps(world_setting, ensure_ascii=False, indent=2)}

角色列表：
{json.dumps(characters, ensure_ascii=False, indent=2)}

请从以下维度进行分析：
1. 结构完整性（是否有清晰的起承转合）
2. 角色发展（主要角色是否有完整的成长弧线）
3. 情节节奏（高潮和低谷分布是否合理）
4. 世界观融合（大纲是否充分利用了世界观设定）
5. 伏笔呼应（是否有足够的伏笔和呼应）

输出格式：
{{
    "structural_issues": ["问题1", "问题2"],
    "character_development_issues": ["问题1", "问题2"],
    "pacing_issues": ["问题1", "问题2"],
    "world_integration_issues": ["问题1", "问题2"],
    "foreshadowing_issues": ["问题1", "问题2"],
    "overall_assessment": "总体评价"
}}
"""

        analysis = await self._call_agent(
            agent_name="大纲分析师",
            system_prompt="你是一位专业的小说大纲分析师，擅长发现大纲结构和内容上的问题。",
            task_prompt=analysis_prompt,
            temperature=0.3,
            expect_json=True,
        )

        return analysis

    async def _generate_optimization_suggestions(
        self,
        analysis_result: dict,
        outline: dict,
        world_setting: dict,
        characters: list,
    ) -> list:
        """基于分析结果生成优化建议."""
        suggestions_prompt = f"""
基于以下大纲分析结果，请生成具体的优化建议：

分析结果：
{json.dumps(analysis_result, ensure_ascii=False, indent=2)}

原大纲：
{json.dumps(outline, ensure_ascii=False, indent=2)}

请为每个发现的问题提供具体的解决方案，输出格式：
[
    {{
        "issue_category": "问题类别",
        "specific_issue": "具体问题描述",
        "solution": "解决方案",
        "implementation_details": "实施细节"
    }}
]
"""

        suggestions = await self._call_agent(
            agent_name="大纲优化师",
            system_prompt="你是一位专业的小说大纲优化师，能够提供具体可行的改进建议。",
            task_prompt=suggestions_prompt,
            temperature=0.6,
            expect_json=True,
        )

        return suggestions if isinstance(suggestions, list) else []

    async def _apply_outline_optimizations(
        self, outline: dict, suggestions: list, world_setting: dict, characters: list
    ) -> dict:
        """应用优化建议到大纲."""
        if not suggestions:
            return outline

        # 获取总章节数，用于生成卷结构
        total_chapters = outline.get("climax_chapter", 100)
        if isinstance(total_chapters, int) and total_chapters > 0:
            total_chapters = max(total_chapters, 50)
        else:
            total_chapters = 100

        # 计算推荐的卷数（每卷约20-30章）
        recommended_volumes = max(3, min(10, total_chapters // 25))

        optimization_prompt = f"""
请根据以下优化建议修改小说大纲，生成完整且详细的大纲结构：

原大纲：
{json.dumps(outline, ensure_ascii=False, indent=2)}

优化建议：
{json.dumps(suggestions, ensure_ascii=False, indent=2)}

世界观设定：
{json.dumps(world_setting, ensure_ascii=False, indent=2)}

角色列表：
{json.dumps(characters, ensure_ascii=False, indent=2)}

请输出优化后的大纲，必须包含以下完整结构：

1. **structure_type**: 结构类型（如：三幕式、英雄之旅、多线叙事等）

2. **main_plot**: 主线剧情对象，包含以下字段：
   - core_conflict: 核心冲突
   - protagonist_goal: 主角目标
   - antagonist: 反派/阻碍
   - progression_path: 升级路径
   - emotional_arc: 情感弧光
   - key_revelations: 关键揭示
   - character_growth: 角色成长
   - resolution: 结局描述

3. **main_plot_detailed**: 详细主线剧情对象，包含：
   - setup: 起始设定详细描述
   - conflict: 冲突发展阶段
   - climax: 高潮详细设计
   - resolution: 结局详细描述
   - turning_points: 关键转折点列表

4. **volumes**: 卷结构数组（建议生成{recommended_volumes}卷，总章节数约{total_chapters}章），每卷必须包含：
   - number: 卷号（从1开始）
   - title: 卷标题（有吸引力的名称）
   - summary: 卷概要（100-200字）
   - chapters: 章节范围数组 [起始章节, 结束章节]
   - core_conflict: 本卷核心矛盾
   - main_events: 主线事件数组，每项包含 {{chapter: 章节号, event: 事件描述, impact: 影响}}
   - key_turning_points: 关键转折点数组，每项包含 {{chapter: 章节号, event: 事件描述, significance: 重要性}}
   - tension_cycles: 张力循环数组，每项包含 {{chapters: [起始, 结束], suppress_events: [压抑事件列表], release_event: 释放事件, tension_level: 张力等级1-10}}
   - emotional_arc: 情感变化曲线描述
   - character_arcs: 角色发展弧线数组，每项包含 {{character_id: 角色ID或名称, arc_description: 弧线描述, key_moments: [关键章节号列表]}}
   - side_plots: 支线情节数组，每项包含 {{name: 支线名称, description: 描述, chapters: [涉及章节范围]}}
   - foreshadowing: 伏笔分配数组，每项包含 {{description: 伏笔描述, setup_chapter: 设置章节, payoff_chapter: 回收章节}}
   - themes: 本卷主题列表
   - word_count_range: 字数范围 [最小值, 最大值]

5. **sub_plots**: 支线剧情数组，每项包含：
   - name: 支线名称
   - description: 描述
   - characters: 涉及角色列表
   - chapters: 涉及章节范围
   - arc: 支线发展弧线

6. **key_turning_points**: 全书关键转折点数组，每项包含：
   - chapter: 章节号
   - event: 事件描述
   - impact: 对剧情的影响
   - significance: 重要性说明

7. **climax_chapter**: 高潮章节号（整数）

重要提示：
- 确保volumes数组完整且每个卷都有详细的字段填充
- 各卷之间要有清晰的剧情递进关系
- 伏笔和呼应要贯穿各卷
- 角色发展弧线要在不同卷中有体现
- 返回的必须是有效的JSON格式
"""

        optimized_outline = await self._call_agent(
            agent_name="大纲重构师",
            system_prompt="你是一位专业的小说大纲重构师，擅长设计详细完整的卷章结构和剧情发展。",
            task_prompt=optimization_prompt,
            temperature=0.5,
            expect_json=True,
            max_tokens=4096,
        )

        # 防御性检查：确保 optimized_outline 是 dict 类型
        if not isinstance(optimized_outline, dict):
            logger.warning(
                "_apply_outline_optimizations: LLM返回了非dict类型 "
                f"({type(optimized_outline).__name__})，回退到原始大纲"
            )
            # 如果是list且包含dict元素，尝试提取
            if isinstance(optimized_outline, list) and len(optimized_outline) > 0:
                for item in optimized_outline:
                    if isinstance(item, dict) and ("main_plot" in item or "volumes" in item):
                        optimized_outline = item
                        logger.info("从list中成功提取dict元素")
                        break
                else:
                    return outline  # 回退到原始大纲
            else:
                return outline  # 回退到原始大纲

        # 确保返回的数据包含完整的结构
        if isinstance(optimized_outline, dict):
            # 如果volumes为空或不完整，尝试保留原volumes
            if not optimized_outline.get("volumes") and outline.get("volumes"):
                optimized_outline["volumes"] = outline["volumes"]
            # 确保每个卷都有number字段
            if optimized_outline.get("volumes"):
                for idx, vol in enumerate(optimized_outline["volumes"]):
                    if isinstance(vol, dict) and "number" not in vol:
                        vol["number"] = vol.get("volume_num", idx + 1)

            # 确保main_plot包含所有必要字段
            # 注意：字段累积逻辑已在refine_outline_comprehensive中处理
            # 这里只检查并生成缺失的字段
            current_main_plot = optimized_outline.get("main_plot", {}) or {}

            # 定义main_plot应该包含的字段
            main_plot_fields = [
                "core_conflict",
                "protagonist_goal",
                "antagonist",
                "progression_path",
                "emotional_arc",
                "key_revelations",
                "character_growth",
                "resolution",
            ]

            # 检查是否有缺失的字段
            missing_fields = [
                f
                for f in main_plot_fields
                if f not in current_main_plot or not current_main_plot[f]
            ]

            # 移除对 core_conflict 的前置条件检查，即使没有 core_conflict 也尝试补全
            if missing_fields:
                logger.info(f"main_plot缺失字段，将使用AI生成: {missing_fields}")
                # 使用AI生成缺失的字段
                try:
                    generated_fields = await self._generate_missing_main_plot_fields(
                        core_conflict=current_main_plot.get("core_conflict", ""),
                        existing_fields=current_main_plot,
                        missing_fields=missing_fields,
                        world_setting=world_setting,
                        characters=characters,
                    )
                    # 合并生成的字段
                    for field, value in generated_fields.items():
                        if field in missing_fields and value:
                            current_main_plot[field] = value
                            logger.info(f"已生成字段 {field}: {value[:50]}...")
                except Exception as e:
                    logger.warning(f"生成缺失字段时出错: {e}，尝试使用简化提示词重试")
                    # 异常时不直接跳过，尝试使用简化提示词重试
                    try:
                        simplified_fields = await self._generate_missing_main_plot_fields_simple(
                            existing_fields=current_main_plot,
                            missing_fields=missing_fields,
                            world_setting=world_setting,
                            characters=characters,
                        )
                        for field, value in simplified_fields.items():
                            if field in missing_fields and value:
                                current_main_plot[field] = value
                                logger.info(f"简化重试后生成字段 {field}: {value[:50]}...")
                    except Exception as e2:
                        logger.error(f"简化重试仍然失败: {e2}")

            optimized_outline["main_plot"] = current_main_plot

            logger.info(
                f"_apply_outline_optimizations后main_plot字段: {list(current_main_plot.keys())}"
            )

        return optimized_outline

    async def _generate_missing_main_plot_fields(
        self,
        core_conflict: str,
        existing_fields: dict,
        missing_fields: list,
        world_setting: dict,
        characters: list,
    ) -> dict:
        """基于核心冲突生成缺失的main_plot字段.

        Args:
            core_conflict: 核心冲突描述
            existing_fields: 已存在的字段
            missing_fields: 需要生成的字段列表
            world_setting: 世界观设定
            characters: 角色列表

        Returns:
            生成的字段字典
        """
        field_descriptions = {
            "core_conflict": "故事的核心矛盾和冲突，是推动剧情发展的主要动力",
            "protagonist_goal": "主角想要达成的具体目标，应该与核心冲突直接相关",
            "antagonist": "反派角色或主要阻碍的描述，包括其动机和能力",
            "progression_path": "主角的成长路径或力量体系升级路线",
            "emotional_arc": "主角在故事中的情感变化历程",
            "key_revelations": "故事中的重要揭示和转折点",
            "character_growth": "主角的性格和能力如何随着故事发展而改变",
            "resolution": "故事的最终结局，如何解决了核心冲突",
        }

        # 构建需要生成的字段描述
        fields_to_generate = {f: field_descriptions.get(f, f) for f in missing_fields}

        # 根据 core_conflict 是否为空选择不同的提示词策略
        if core_conflict and core_conflict.strip():
            # 有核心冲突时，基于核心冲突生成
            prompt = f"""
基于以下核心冲突，请生成小说大纲中缺失的字段内容：

核心冲突：
{core_conflict}

世界观设定：
{json.dumps(world_setting, ensure_ascii=False, indent=2)}

角色列表：
{json.dumps(characters, ensure_ascii=False, indent=2)}

已填写的字段：
{json.dumps({k: v for k, v in existing_fields.items() if k not in missing_fields}, ensure_ascii=False, indent=2)}

请生成以下缺失字段的内容（每项100-300字）：
{json.dumps(fields_to_generate, ensure_ascii=False, indent=2)}

输出格式（必须是有效的JSON）：
{{
    "protagonist_goal": "...",
    "antagonist": "...",
    ...
}}

注意：
1. 只输出JSON格式，不要其他说明文字
2. 生成的内容必须与核心冲突逻辑一致
3. 每个字段都要详细具体，不要泛泛而谈
"""
        else:
            # 没有核心冲突时，基于世界观和角色生成
            prompt = f"""
请基于世界观和角色信息，生成小说大纲中缺失的字段内容：

世界观设定：
{json.dumps(world_setting, ensure_ascii=False, indent=2)}

角色列表：
{json.dumps(characters, ensure_ascii=False, indent=2)}

已填写的字段：
{json.dumps({k: v for k, v in existing_fields.items() if k not in missing_fields}, ensure_ascii=False, indent=2)}

请生成以下缺失字段的内容（每项100-300字）：
{json.dumps(fields_to_generate, ensure_ascii=False, indent=2)}

输出格式（必须是有效的JSON）：
{{
    "core_conflict": "...",
    "protagonist_goal": "...",
    "antagonist": "...",
    ...
}}

注意：
1. 只输出JSON格式，不要其他说明文字
2. 先理解世界观和角色的特点，再推导合理的剧情要素
3. 每个字段都要详细具体，确保逻辑一致性
"""

        result = await self._call_agent(
            agent_name="大纲补全师",
            system_prompt="你是一位专业的小说大纲设计师，擅长根据核心冲突推导完整的剧情要素。",
            task_prompt=prompt,
            temperature=0.6,
            expect_json=True,
            max_tokens=2048,
        )

        if isinstance(result, dict):
            return result
        return {}

    async def _generate_missing_main_plot_fields_simple(
        self, existing_fields: dict, missing_fields: list, world_setting: dict, characters: list
    ) -> dict:
        """简化版字段生成方法，当主方法失败时使用.

        使用更简单的提示词，基于世界观和角色信息生成缺失字段。

        Args:
            existing_fields: 已存在的字段
            missing_fields: 需要生成的字段列表
            world_setting: 世界观设定
            characters: 角色列表

        Returns:
            生成的字段字典
        """
        field_descriptions = {
            "core_conflict": "故事的核心矛盾和冲突",
            "protagonist_goal": "主角想要达成的具体目标",
            "antagonist": "反派角色或主要阻碍",
            "progression_path": "主角的成长路径",
            "emotional_arc": "主角的情感变化历程",
            "key_revelations": "故事中的重要揭示",
            "character_growth": "主角的成长变化",
            "resolution": "故事的最终结局",
        }

        # 构建需要生成的字段描述
        fields_to_generate = {
            f: field_descriptions.get(f, f) for f in missing_fields if f in field_descriptions
        }

        # 使用更简洁的提示词
        prompt = f"""
请根据世界观和角色信息，生成小说大纲的缺失字段。

世界观：
{json.dumps(world_setting, ensure_ascii=False, indent=2)[:500]}

主要角色：
{json.dumps(characters[:3] if len(characters) > 3 else characters, ensure_ascii=False, indent=2)}

需要生成：
{json.dumps(fields_to_generate, ensure_ascii=False, indent=2)}

输出JSON格式，每个字段50-150字。
"""

        try:
            result = await self._call_agent(
                agent_name="大纲补全师",
                system_prompt="你是专业小说大纲设计师，简洁高效。",
                task_prompt=prompt,
                temperature=0.7,
                expect_json=True,
                max_tokens=1024,
            )
            if isinstance(result, dict):
                return result
            return {}
        except Exception as e:
            logger.error(f"简化生成也失败: {e}")
            return {}

    def _extract_improvements(self, original: dict, optimized: dict, suggestions: list) -> list:
        """提取本次优化的具体改进点."""
        improvements = []

        # 基于建议生成改进描述
        for suggestion in suggestions:
            if isinstance(suggestion, dict):
                improvements.append(
                    f"优化了{suggestion.get('issue_category', '某方面')}："
                    f"{suggestion.get('specific_issue', '某个问题')} → "
                    f"{suggestion.get('solution', '已解决')}"
                )

        # 如果没有具体建议，生成通用描述
        if not improvements:
            improvements.append("对大纲结构进行了综合性优化")

        return improvements

    def _should_stop_refinement(self, analysis_result: dict, options: dict) -> bool:
        """判断是否应该停止完善迭代."""
        options.get("quality_threshold", 8.0)

        # 简单的质量评估逻辑
        # 实际项目中可以根据analysis_result的具体内容进行更复杂的判断
        overall_assessment = analysis_result.get("overall_assessment", "").lower()

        # 如果评估中包含"良好"、"优秀"等正面词汇，或者问题很少
        positive_indicators = ["良好", "优秀", "完善", "完整"]
        structural_issues = len(analysis_result.get("structural_issues", []))
        character_issues = len(analysis_result.get("character_development_issues", []))

        has_positive_words = any(word in overall_assessment for word in positive_indicators)
        few_issues = (structural_issues + character_issues) <= 2

        return has_positive_words or few_issues

    def setup_reflection(self, storage, novel_id: str = "unknown", config=None):
        """设置反思代理.

        Args:
            storage: 存储实例（如 NovelMemoryStorage）
            novel_id: 小说ID
            config: ReflectionConfig 配置，如果为 None 则使用默认配置
        """
        from agents.reflection_agent import ReflectionAgent, ReflectionConfig

        self.reflection_agent = ReflectionAgent(
            client=self.client,
            cost_tracker=self.cost_tracker,
            novel_id=novel_id,
            storage=storage,
            config=config or ReflectionConfig(),
        )
        return self.reflection_agent

    def _extract_improvements(self, original: dict, optimized: dict, suggestions: list) -> list:
        """提取本次优化的具体改进点."""
        improvements = []

        # 基于建议生成改进描述
        for suggestion in suggestions:
            if isinstance(suggestion, dict):
                improvements.append(
                    f"优化了{suggestion.get('issue_category', '某方面')}："
                    f"{suggestion.get('specific_issue', '某个问题')} → "
                    f"{suggestion.get('solution', '已解决')}"
                )

        # 如果没有具体建议，生成通用描述
        if not improvements:
            improvements.append("对大纲结构进行了综合性优化")

        return improvements

    def _should_stop_refinement(self, analysis_result: dict, options: dict) -> bool:
        """判断是否应该停止完善迭代."""
        options.get("quality_threshold", 8.0)

        # 简单的质量评估逻辑
        # 实际项目中可以根据analysis_result的具体内容进行更复杂的判断
        overall_assessment = analysis_result.get("overall_assessment", "").lower()

        # 如果评估中包含"良好"、"优秀"等正面词汇，或者问题很少
        positive_indicators = ["良好", "优秀", "完善", "完整"]
        structural_issues = len(analysis_result.get("structural_issues", []))
        character_issues = len(analysis_result.get("character_development_issues", []))

        has_positive_words = any(word in overall_assessment for word in positive_indicators)
        few_issues = (structural_issues + character_issues) <= 2

        return has_positive_words or few_issues

    # =========================================================================
    # 图数据库上下文方法
    # =========================================================================

    async def _build_graph_context_for_writer(
        self,
        novel_id: str,
        chapter_number: int,
        chapter_characters: list,
    ) -> str:
        """构建图数据库上下文，注入到 Writer prompt.

        查询内容包括：
        1. 本章出场角色的关系网络
        2. 待回收的伏笔提醒
        3. 一致性冲突警告

        Args:
            novel_id: 小说ID
            chapter_number: 当前章节号
            chapter_characters: 本章出场角色名称列表

        Returns:
            格式化的上下文字符串，可插入到 prompt 中
            如果图数据库未启用或查询失败，返回空字符串
        """
        from backend.config import settings

        if not self.enable_graph_context:
            return ""

        try:
            from agents.graph_query_mixin import GraphQueryMixin

            mixin = GraphQueryMixin()
            mixin.set_graph_context(novel_id)

            sections = []

            # 1. 查询本章出场角色的关系网络（支持可配置深度）
            max_chars = getattr(settings, "GRAPH_CONTEXT_MAX_CHARACTERS", 5)
            query_depth = getattr(settings, "GRAPH_QUERY_DEPTH", 2)
            network_contexts = []
            indirect_relations = []

            for char_name in chapter_characters[:max_chars]:
                try:
                    # 使用配置的查询深度（默认2层，可识别"朋友的朋友"）
                    network = await mixin.query_character_network(char_name, depth=query_depth)
                    if network:
                        network_contexts.append(mixin.format_network_context(network))

                        # 提取间接关联角色（depth>=2时）
                        if query_depth >= 2 and getattr(
                            settings, "GRAPH_ENABLE_INDIRECT_RELATIONS", True
                        ):
                            for node in network.nodes:
                                if node.get("name") != char_name:
                                    indirect_relations.append(
                                        {
                                            "from": char_name,
                                            "to": node.get("name"),
                                            "role_type": node.get("role_type", "unknown"),
                                        }
                                    )
                except Exception as e:
                    logger.debug(f"[GraphContext] 角色{char_name}网络查询失败: {e}")

            if network_contexts:
                sections.append("## 角色关系网络\n" + "\n".join(network_contexts))

                # 添加间接关系提示（帮助识别潜在关联）
                if indirect_relations:
                    unique_relations = []
                    seen_pairs = set()
                    for rel in indirect_relations:
                        pair = tuple(sorted([rel["from"], rel["to"]]))
                        if pair not in seen_pairs:
                            seen_pairs.add(pair)
                            unique_relations.append(rel)

                    if unique_relations:
                        indirect_text = "## 潜在关联角色（通过关系网络识别）\n"
                        indirect_text += "以下角色可能在本章产生互动或影响：\n"
                        for rel in unique_relations[:10]:  # 限制数量
                            indirect_text += f"- {rel['from']} ↔ {rel['to']}\n"
                        sections.append(indirect_text)

            # 2. 查询待回收伏笔（增强策略）
            try:
                foreshadowings = await mixin.query_pending_foreshadowings(chapter_number)

                # 额外查询与出场角色相关的伏笔
                if getattr(settings, "GRAPH_QUERY_RELATED_FORESHADOWINGS", True):
                    related_fs = await mixin.query_foreshadowings_by_characters(
                        chapter_characters, current_chapter=chapter_number
                    )
                    # 合并并去重
                    seen_ids = {f.get("id") for f in foreshadowings}
                    for f in related_fs:
                        if f.get("id") not in seen_ids:
                            foreshadowings.append(f)

                if foreshadowings:
                    max_f = getattr(settings, "GRAPH_CONTEXT_MAX_FORESHADOWINGS", 5)
                    sections.append(mixin.format_foreshadowings_context(foreshadowings[:max_f]))
            except Exception as e:
                logger.debug(f"[GraphContext] 伏笔查询失败: {e}")

            # 3. 检测一致性冲突（仅包含本章出场角色相关的冲突）
            try:
                conflicts = await mixin.check_conflicts()
                if conflicts:
                    # 过滤出与本章角色相关的冲突
                    char_conflicts = [
                        c for c in conflicts if any(ch in c.characters for ch in chapter_characters)
                    ]
                    if char_conflicts:
                        sections.append(mixin.format_conflicts_context(char_conflicts))
            except Exception as e:
                logger.debug(f"[GraphContext] 冲突检测失败: {e}")

            if sections:
                logger.info(
                    f"[GraphContext] 第{chapter_number}章注入图上下文: " f"{len(sections)}个部分"
                )
                return "\n\n".join(sections)

            return ""

        except Exception as e:
            logger.warning(f"[GraphContext] 图查询失败: {e}")
            return ""

    async def _query_graph_conflicts_for_continuity(
        self,
        novel_id: str,
        chapter_characters: list,
        chapter_number: int,
    ) -> str:
        """查询图库中与本章角色相关的一致性冲突.

        在连续性审查前调用，将图库检测到的关系冲突注入到审查提示词中。

        Args:
            novel_id: 小说ID
            chapter_characters: 本章出场角色名称列表
            chapter_number: 当前章节号

        Returns:
            格式化的冲突信息字符串，可插入到连续性审查 prompt 中
            如果图数据库未启用或查询失败，返回空字符串
        """
        from backend.config import settings

        # 检查是否启用图库连续性检查
        if not getattr(settings, "ENABLE_GRAPH_CONTINUITY_CHECK", True):
            return ""

        if not self.enable_graph_context:
            return ""

        try:
            from agents.graph_query_mixin import GraphQueryMixin

            mixin = GraphQueryMixin()
            mixin.set_graph_context(novel_id)

            # 调用图库冲突检测
            conflicts = await mixin.check_conflicts()

            if not conflicts:
                return ""

            # 过滤与本章角色相关的冲突
            relevant_conflicts = []
            for conflict in conflicts[:10]:  # 最多处理10个
                conflict_chars = conflict.characters if hasattr(conflict, "characters") else []
                if conflict_chars and any(c in chapter_characters for c in conflict_chars):
                    relevant_conflicts.append(conflict)

            if not relevant_conflicts:
                return ""

            # 格式化为提示词
            lines = ["【图库检测到以下潜在一致性问题】"]
            for i, c in enumerate(relevant_conflicts, 1):
                severity = c.severity if hasattr(c, "severity") else "medium"
                description = c.description if hasattr(c, "description") else str(c)
                lines.append(f"{i}. [{severity}] {description}")

            logger.info(
                f"[GraphContinuity] 第{chapter_number}章检测到 {len(relevant_conflicts)} 个图库冲突"
            )
            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"[GraphContinuity] 图库冲突查询失败: {e}")
            return ""
