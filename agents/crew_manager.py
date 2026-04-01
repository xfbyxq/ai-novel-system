"""CrewAI 风格的小说生成 Crew 管理器.

采用直接编排模式，通过 QwenClient 调用通义千问模型，
而非使用 CrewAI 的内置 LLM 集成。

集成 TeamContext 实现 Agent 间的信息共享和状态追踪。
集成审查反馈循环、投票共识、请求-应答协商机制。
"""

import json
import re
from typing import Any, Dict, Optional

from agents.agent_query_service import AgentQueryService
from agents.chapter_summary_generator import ChapterSummaryGenerator
from agents.character_review_loop import CharacterReviewHandler

# 反思机制
# 章节连续性增强组件
from agents.context_compressor import ContextCompressor
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
        quality_threshold: float = 7.5,
        max_review_iterations: int = 3,
        max_fix_iterations: int = 2,
        enable_voting: bool = True,
        enable_query: bool = True,
        enable_character_review: bool = True,
        enable_world_review: bool = True,
        enable_plot_review: bool = True,
        enable_outline_refinement: bool = True,
        character_quality_threshold: float = 7.0,
        world_quality_threshold: float = 7.0,
        plot_quality_threshold: float = 7.0,
        max_character_review_iterations: int = 2,
        max_world_review_iterations: int = 2,
        max_plot_review_iterations: int = 2,
    ):
        """初始化 Crew 管理器.

        Args:
            qwen_client: 通义千问客户端实例
            cost_tracker: 成本跟踪器实例
            quality_threshold: 质量评分阈值（达标即停止迭代）
            max_review_iterations: Writer-Editor 审查循环最大迭代次数
            max_fix_iterations: 连续性修复循环最大迭代次数
            enable_voting: 是否启用企划阶段投票共识
            enable_query: 是否启用写作过程中的设定查询
            enable_character_review: 是否启用角色设计审查循环
            enable_world_review: 是否启用世界观设计审查循环
            enable_plot_review: 是否启用大纲设计审查循环
            enable_outline_refinement: 是否启用章节大纲细化步骤
            character_quality_threshold: 角色设计质量阈值
            world_quality_threshold: 世界观设计质量阈值
            plot_quality_threshold: 大纲设计质量阈值
            max_character_review_iterations: 角色审查最大迭代次数
            max_world_review_iterations: 世界观审查最大迭代次数
            max_plot_review_iterations: 大纲审查最大迭代次数
        """
        self.client = qwen_client
        self.cost_tracker = cost_tracker
        self.pm = PromptManager

        # 协作配置
        self.quality_threshold = quality_threshold
        self.max_review_iterations = max_review_iterations
        self.max_fix_iterations = max_fix_iterations
        self.enable_voting = enable_voting
        self.enable_query = enable_query
        self.enable_character_review = enable_character_review
        self.enable_world_review = enable_world_review
        self.enable_plot_review = enable_plot_review
        self.enable_outline_refinement = enable_outline_refinement

        # 图数据库上下文注入开关（从配置读取）
        from backend.config import settings
        self.enable_graph_context = (
            settings.ENABLE_GRAPH_DATABASE
            and getattr(settings, "ENABLE_GRAPH_CONTEXT_INJECTION", True)
        )

        # 初始化协作组件
        self.review_handler = ReviewLoopHandler(
            client=qwen_client,
            cost_tracker=cost_tracker,
            quality_threshold=quality_threshold,
            max_iterations=max_review_iterations,
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
            quality_threshold=character_quality_threshold,
            max_iterations=max_character_review_iterations,
        )

        # 世界观审查处理器
        self.world_review_handler = WorldReviewHandler(
            client=qwen_client,
            cost_tracker=cost_tracker,
            quality_threshold=world_quality_threshold,
            max_iterations=max_world_review_iterations,
        )

        # 大纲审查处理器
        self.plot_review_handler = PlotReviewHandler(
            client=qwen_client,
            cost_tracker=cost_tracker,
            quality_threshold=plot_quality_threshold,
            max_iterations=max_plot_review_iterations,
        )

        # 章节连续性增强组件
        self.context_compressor = ContextCompressor()
        self.similarity_detector = SimilarityDetector()
        self.summary_generator = ChapterSummaryGenerator(
            client=qwen_client,
            cost_tracker=cost_tracker,
        )

        # 章节数据缓存（供压缩器和相似度检测器使用）
        self._chapter_summaries: dict[int, dict] = {}
        self._chapter_contents: dict[int, str] = {}
        self._chapter_detailed_outlines: dict[int, dict] = {}

        # 反思代理（初始化为None，需要时通过setup_reflection设置）
        self.reflection_agent = None

    def _extract_json_from_response(self, response: str) -> dict | list:
        """从 LLM 响应中提取 JSON.

        LLM 可能会在 JSON 前后添加 markdown 代码块标记或其他文本,
        这个方法使用多种策略找到 JSON 内容并解析。

        增强功能：
        - 支持中文引号自动转换为英文引号
        - 支持不规范的键名（无引号）
        - 支持截断的 JSON
        - 逐字段提取作为最后保障
        - 优先匹配根级别的 JSON 结构（字典优先于数组）
        - 更好的错误处理和异常捕获

        Args:
            response: LLM 的原始响应文本

        Returns:
            解析后的 JSON 对象（dict 或 list）

        Raises:
            ValueError: 如果无法找到或解析 JSON
        """
        if not response or not isinstance(response, str):
            raise ValueError(f"无效的响应类型: {type(response)}, 期望字符串")

        # 策略 1: 先尝试直接解析
        try:
            result = json.loads(response.strip())
            if isinstance(result, (dict, list)):
                return result
        except json.JSONDecodeError:
            pass

        # 策略 2: 尝试提取 markdown 代码块中的内容
        try:
            code_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```"
            for match in re.finditer(code_block_pattern, response):
                block_content = match.group(1).strip()
                if block_content:
                    try:
                        result = json.loads(block_content)
                        if isinstance(result, (dict, list)):
                            return result
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        # 策略 3: 优先匹配根级别的 JSON（字典优先于数组）
        # 先尝试匹配字典 { ... }
        try:
            result = self._find_json_by_brackets(response, "{", "}")
            if result is not None:
                return result
        except Exception:
            pass

        # 如果没有找到字典，尝试匹配数组 [ ... ]
        try:
            result = self._find_json_by_brackets(response, "[", "]")
            if result is not None:
                return result
        except Exception:
            pass

        # 策略 4: 修复中文引号后重试
        try:
            fixed_response = response.replace('"', '"').replace('"', '"')
            result = json.loads(fixed_response.strip())
            if isinstance(result, (dict, list)):
                return result
        except json.JSONDecodeError:
            pass

        # 策略 5: 逐字段提取（针对特定结构）
        try:
            extracted = self._extract_fields_manually(response)
            if extracted is not None:
                return extracted
        except Exception:
            pass

        # 如果所有策略都失败，抛出更详细的错误信息
        raise ValueError(
            f"无法从响应中提取有效的 JSON。响应长度: {len(response)}, 开头: {response[:200]}..."
        )

    def _find_json_by_brackets(
        self, response: str, start_char: str, end_char: str
    ) -> Optional[dict | list]:
        """使用括号匹配法找到完整的 JSON.

        Args:
            response: 原始响应文本
            start_char: 开始字符 '{' 或 '['
            end_char: 结束字符 '}' 或 ']'

        Returns:
            解析后的 JSON 对象，或 None 如果找不到
        """
        if not response or not isinstance(response, str):
            return None

        # 找到第一个指定类型开始字符的位置
        start_idx = -1
        try:
            for idx, ch in enumerate(response):
                if ch == start_char:
                    start_idx = idx
                    break
        except Exception:
            return None

        if start_idx == -1:
            return None

        # 使用括号计数匹配完整的 JSON
        depth = 0
        in_string = False
        escape_next = False
        try:
            for i in range(start_idx, len(response)):
                ch = response[i]
                if escape_next:
                    escape_next = False
                    continue
                if ch == "\\" and in_string:
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == start_char:
                    depth += 1
                elif ch == end_char:
                    depth -= 1
                    if depth == 0:
                        candidate = response[start_idx : i + 1]
                        try:
                            result = json.loads(candidate)
                            if isinstance(result, (dict, list)):
                                return result
                        except json.JSONDecodeError:
                            break
        except Exception:
            # 如果在解析过程中发生任何异常，返回 None
            return None
        return None

    def _extract_fields_manually(self, response: str) -> Optional[Dict[str, Any]]:
        """
        手动提取常见字段作为最后保障.

        适用于连续性审查员等特定 Agent 的输出
        """
        if not response or not isinstance(response, str):
            return None

        result = {}

        # 提取 has_issues
        has_issues_match = re.search(
            r'"has_issues"\s*:\s*(true|false)', response, re.IGNORECASE
        )
        if has_issues_match:
            result["has_issues"] = has_issues_match.group(1).lower() == "true"

        # 提取 quality_score
        score_match = re.search(r'"quality_score"\s*:\s*([\d.]+)', response)
        if score_match:
            result["quality_score"] = float(score_match.group(1))

        # 提取 overall_assessment
        assessment_match = re.search(r'"overall_assessment"\s*:\s*"([^"]+)"', response)
        if assessment_match:
            result["overall_assessment"] = assessment_match.group(1)

        # 如果有至少一个字段，返回部分结果
        if result:
            # 尝试提取 issues 数组
            try:
                issues_match = re.search(r'"issues"\s*:\s*\[', response)
                if issues_match:
                    result["issues"] = []  # 简化处理，返回空数组
            except Exception:
                pass

            return result

        return None

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
            if expect_json:
                try:
                    result = self._extract_json_from_response(content)
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
                logger.info(
                    f"✅ [{agent_name}] 执行成功，返回文本内容（{len(content)} 字符）"
                )
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
                result = self._extract_json_from_response(last_response)
                logger.info(f"✅ [{agent_name}] JSON重试成功 (第{attempt}次)")
                return result
            except ValueError:
                continue

        raise ValueError(
            f"[{agent_name}] JSON提取在{max_retries}次重试后仍失败: "
            f"{last_response[:200]}..."
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
                topic_analysis=(
                    topic_analysis if isinstance(topic_analysis, dict) else {}
                ),
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
            characters_list = (
                characters if isinstance(characters, list) else [characters]
            )

            review_result = await self.character_review_handler.execute(
                initial_characters=characters_list,
                world_setting=world_setting if isinstance(world_setting, dict) else {},
                topic_analysis=(
                    topic_analysis if isinstance(topic_analysis, dict) else {}
                ),
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
            characters_list = (
                characters if isinstance(characters, list) else [characters]
            )

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
            team_context.add_agent_output(
                "章节策划师", chapter_plan, f"第{chapter_number}章策划"
            )

        # ── 1.5 章节大纲细化（可选步骤） ─────────────────────
        detailed_outline = {}
        detailed_outline_text = "（未启用大纲细化）"

        if self.enable_outline_refinement:
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
                prev_outline_text = json.dumps(
                    prev_detailed, ensure_ascii=False, indent=2
                )
            else:
                prev_outline_text = (
                    "（无上一章细化大纲，本章为起始章或上一章未启用细化）"
                )

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
            detailed_outline_text = json.dumps(
                detailed_outline, ensure_ascii=False, indent=2
            )

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
        chapter_characters = chapter_plan.get("scenes", [{}])[0].get("characters", [])
        character_info = ""
        for char in characters:
            if isinstance(char, dict) and char.get("name") in chapter_characters:
                character_info += f"\n- {char.get('name')}：{char.get('personality', '')}，{char.get('background', '')[:50]}..."

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

        # ── 使用分层压缩构建前章结尾 ─────────────────────
        compressed = self.context_compressor.compress(
            chapter_number=chapter_number,
            chapter_summaries=self._chapter_summaries,
            chapter_contents=self._chapter_contents,
            world_setting=world_setting,
            characters=characters,
            plot_outline=plot_outline,
        )
        # 前章结尾优先使用压缩器提取的 500 字
        previous_ending = compressed.previous_ending or (
            previous_chapters_summary[-500:]
            if previous_chapters_summary
            else "（本章为开篇）"
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
                previous_ending=previous_ending,
                chapter_title=chapter_plan.get("title", ""),
                query_answers="",
                previous_key_events=previous_key_events,
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
                previous_ending=previous_ending,
                chapter_title=chapter_plan.get("title", ""),
                previous_key_events=previous_key_events,
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
            )

        # 记录到 TeamContext
        if team_context:
            team_context.add_agent_output(
                "作家", {"draft_length": len(draft)}, f"第{chapter_number}章初稿"
            )

        # ── 3. Writer-Editor 审查反馈循环 ─────────────────────
        chapter_plan_json = json.dumps(chapter_plan, ensure_ascii=False, indent=2)
        review_result = await self.review_handler.execute(
            initial_draft=draft,
            chapter_number=chapter_number,
            chapter_title=chapter_plan.get("title", ""),
            chapter_summary=chapter_plan.get("summary", ""),
            chapter_plan_json=chapter_plan_json,
            writer_system_prompt=writer_system,
            team_context=team_context,
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

        # ── 4. 连续性检查 + 修复循环 ─────────────────────────
        final_content = edited_content
        continuity_report = None

        for fix_round in range(1, self.max_fix_iterations + 1):
            continuity_task = self.pm.format(
                self.pm.CONTINUITY_CHECKER_TASK,
                current_chapter=final_content,
                world_setting_brief=world_brief,
                character_info=character_info or "（主要角色）",
                previous_key_info=previous_chapters_summary or "（本章为第一章）",
            )

            # 注入反思经验到连续性检查系统提示词
            continuity_system = self.pm.CONTINUITY_CHECKER_SYSTEM
            if self.reflection_agent:
                continuity_lessons = self.reflection_agent.get_lessons_for_continuity()
                if continuity_lessons:
                    continuity_system += "\n" + continuity_lessons

            continuity_report = await self._call_agent(
                agent_name="连续性审查员",
                system_prompt=continuity_system,
                task_prompt=continuity_task,
                temperature=0.5,
                expect_json=True,
            )

            # 检查是否有严重问题
            issues = continuity_report.get("issues", [])
            high_severity = [i for i in issues if i.get("severity") == "high"]

            if not high_severity:
                logger.info(
                    f"[连续性检查] 第 {fix_round} 轮: 无严重问题 "
                    f"(score={continuity_report.get('quality_score', 'N/A')})"
                )
                break

            if fix_round >= self.max_fix_iterations:
                logger.warning(
                    f"[连续性检查] 达到最大修复轮次 ({self.max_fix_iterations}), "
                    f"仍有 {len(high_severity)} 个严重问题"
                )
                break

            # 调用修复
            logger.info(
                f"[连续性检查] 第 {fix_round} 轮: 发现 {len(high_severity)} 个严重问题, "
                f"请求修复..."
            )
            fix_suggestions = "\n".join(
                f"- [{i.get('type', '')}] {i.get('description', '')}: {i.get('suggestion', '')}"
                for i in high_severity
            )
            fix_task = f"""以下章节存在连续性问题，请修复.

原文：
{final_content}

发现的问题：
{fix_suggestions}

请输出修复后的完整章节内容，不要输出修改说明。"""

            fixed = await self._call_agent(
                agent_name="编辑(修复)",
                system_prompt=self.pm.EDITOR_SYSTEM,
                task_prompt=fix_task,
                temperature=0.5,
                max_tokens=4096,
                expect_json=False,
            )
            if fixed and len(fixed) > len(final_content) * 0.3:
                final_content = fixed

        # 记录到 TeamContext
        if team_context:
            team_context.add_agent_output(
                "连续性审查员", continuity_report, f"第{chapter_number}章检查"
            )
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

        quality_score = (
            continuity_report.get("quality_score", 0) if continuity_report else 0
        )

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

前一章结尾：
{previous_ending}

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

        logger.info("=" * 60)
        logger.info(f"🎉 第 {chapter_number} 章写作完成！")
        logger.info(
            f"   审查循环：{review_result.total_iterations} 轮, "
            f"score={review_result.final_score:.1f}, "
            f"converged={review_result.converged}"
        )
        logger.info(f"   连续性评分：{quality_score}")
        logger.info(
            f"   发现问题：{len(continuity_report.get('issues', []))} 个"
            if continuity_report
            else ""
        )
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
            "similarity_report": (
                similarity_report.to_dict() if similarity_report else None
            ),
            "chapter_summary": chapter_summary,
        }

    def _build_plot_outline_context(
        self, plot_outline: dict | list, volume_number: int, chapter_number: int
    ) -> str:
        """从全局大纲中提取与当前章节相关的上下文信息.

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

        # 处理 dict 格式
        if isinstance(plot_outline, dict):
            # 主线剧情
            main_plot = plot_outline.get("main_plot", {})
            if main_plot:
                parts.append(
                    f"【主线剧情】核心冲突：{main_plot.get('core_conflict', '未知')}"
                )
                parts.append(f"  主题：{main_plot.get('theme', '未知')}")

            # 黄金三章（前3章适用）
            if chapter_number <= 3:
                golden = plot_outline.get("golden_three_chapters", {})
                if golden:
                    parts.append("【黄金三章设计】")
                    for key, val in golden.items():
                        parts.append(f"  {key}: {val}")

            # 关键转折点
            turning_points = plot_outline.get("key_turning_points", [])
            if turning_points:
                parts.append("【全局关键转折点】")
                for tp in turning_points[:5]:
                    if isinstance(tp, str):
                        parts.append(f"  - {tp}")
                    elif isinstance(tp, dict):
                        parts.append(
                            f"  - {tp.get('event', tp.get('description', str(tp)))}"
                        )

            # 当前卷信息
            volumes = plot_outline.get("volumes", [])
            for vol in volumes:
                if vol.get("volume_num") == volume_number:
                    parts.append(
                        f"【当前卷】第{volume_number}卷 - {vol.get('title', '')}"
                    )
                    parts.append(f"  概要：{vol.get('summary', '')}")

                    # 张力循环
                    tension_cycles = vol.get("tension_cycles", [])
                    if tension_cycles:
                        parts.append("  张力循环：")
                        for tc in tension_cycles:
                            if isinstance(tc, dict):
                                suppress = tc.get(
                                    "suppress_event", tc.get("suppress", "")
                                )
                                release = tc.get("release_event", tc.get("release", ""))
                                parts.append(
                                    f"    - 压制: {suppress} → 释放: {release}"
                                )
                            elif isinstance(tc, str):
                                parts.append(f"    - {tc}")

                    # 升级里程碑
                    milestone = vol.get("upgrade_milestone", "")
                    if milestone:
                        parts.append(f"  升级里程碑：{milestone}")
                    else:
                        milestones = vol.get(
                            "upgrade_milestones", vol.get("power_milestones", [])
                        )
                        if milestones:
                            parts.append("  升级里程碑：")
                            for ms in milestones:
                                if isinstance(ms, str):
                                    parts.append(f"    - {ms}")
                                elif isinstance(ms, dict):
                                    parts.append(f"    - {ms.get('event', str(ms))}")
                    break

        elif isinstance(plot_outline, list):
            # 直接是卷列表格式
            for vol in plot_outline:
                if vol.get("volume_num") == volume_number:
                    parts.append(
                        f"【当前卷】第{volume_number}卷 - {vol.get('title', '')}"
                    )
                    parts.append(f"  概要：{vol.get('summary', '')}")
                    break

        return "\n".join(parts) if parts else "（无全局大纲信息）"

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
                kb_map = {
                    "world": json.dumps(world_setting, ensure_ascii=False),
                    "character": json.dumps(characters, ensure_ascii=False),
                    "plot": json.dumps(plot_outline, ensure_ascii=False),
                }
                answer = await self.query_service.query(
                    requester="作家",
                    target_type=q["type"],
                    question=q["question"],
                    knowledge_base=kb_map.get(q["type"], ""),
                    chapter_number=chapter_number,
                )
                answers.append(f"关于「{q['question'][:30]}」的回答: {answer}")

            # 用查询答案重新调用 Writer
            query_answers_text = (
                "以下是你之前提出的设定疑问的回答，请据此完善内容：\n"
                + "\n".join(answers)
            )
            AgentQueryService.remove_query_tags(draft)

            rewrite_task = self.pm.format(
                self.pm.WRITER_WITH_QUERY_TASK,
                chapter_number=chapter_number,
                chapter_plan=json.dumps(chapter_plan, ensure_ascii=False, indent=2),
                detailed_outline=detailed_outline_text,
                world_setting_brief=world_brief,
                character_info=character_info or "（主要角色）",
                previous_ending=(
                    previous_chapters_summary[-200:]
                    if previous_chapters_summary
                    else "（本章为开篇）"
                ),
                chapter_title=chapter_plan.get("title", ""),
                query_answers=query_answers_text,
                previous_key_events=previous_key_events,
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

            # 检查是否达到质量阈值或收敛
            if self._should_stop_refinement(analysis_result, options):
                logger.info(f"✅ 完善在第 {round_num} 轮达到质量要求")
                break

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

        optimization_prompt = f"""
请根据以下优化建议修改小说大纲：

原大纲：
{json.dumps(outline, ensure_ascii=False, indent=2)}

优化建议：
{json.dumps(suggestions, ensure_ascii=False, indent=2)}

世界观设定：
{json.dumps(world_setting, ensure_ascii=False, indent=2)}

请输出优化后的大纲，保持原有结构格式，只做必要的改进。
"""

        optimized_outline = await self._call_agent(
            agent_name="大纲重构师",
            system_prompt="你是一位专业的小说大纲重构师，能够精准地改进大纲内容。",
            task_prompt=optimization_prompt,
            temperature=0.4,
            expect_json=True,
        )

        return optimized_outline

    def _extract_improvements(
        self, original: dict, optimized: dict, suggestions: list
    ) -> list:
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

        has_positive_words = any(
            word in overall_assessment for word in positive_indicators
        )
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

    def _extract_improvements(
        self, original: dict, optimized: dict, suggestions: list
    ) -> list:
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

        has_positive_words = any(
            word in overall_assessment for word in positive_indicators
        )
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

            # 1. 查询本章出场角色的关系网络（限制数量）
            max_chars = getattr(settings, "GRAPH_CONTEXT_MAX_CHARACTERS", 5)
            network_contexts = []
            for char_name in chapter_characters[:max_chars]:
                try:
                    network = await mixin.query_character_network(char_name, depth=1)
                    if network:
                        network_contexts.append(mixin.format_network_context(network))
                except Exception as e:
                    logger.debug(f"[GraphContext] 角色{char_name}网络查询失败: {e}")

            if network_contexts:
                sections.append("## 角色关系网络\n" + "\n".join(network_contexts))

            # 2. 查询待回收伏笔
            try:
                foreshadowings = await mixin.query_pending_foreshadowings(
                    chapter_number
                )
                if foreshadowings:
                    max_f = getattr(settings, "GRAPH_CONTEXT_MAX_FORESHADOWINGS", 3)
                    sections.append(
                        mixin.format_foreshadowings_context(foreshadowings[:max_f])
                    )
            except Exception as e:
                logger.debug(f"[GraphContext] 伏笔查询失败: {e}")

            # 3. 检测一致性冲突（仅包含本章出场角色相关的冲突）
            try:
                conflicts = await mixin.check_conflicts()
                if conflicts:
                    # 过滤出与本章角色相关的冲突
                    char_conflicts = [
                        c
                        for c in conflicts
                        if any(ch in c.characters for ch in chapter_characters)
                    ]
                    if char_conflicts:
                        sections.append(mixin.format_conflicts_context(char_conflicts))
            except Exception as e:
                logger.debug(f"[GraphContext] 冲突检测失败: {e}")

            if sections:
                logger.info(
                    f"[GraphContext] 第{chapter_number}章注入图上下文: "
                    f"{len(sections)}个部分"
                )
                return "\n\n".join(sections)

            return ""

        except Exception as e:
            logger.warning(f"[GraphContext] 图查询失败: {e}")
            return ""
