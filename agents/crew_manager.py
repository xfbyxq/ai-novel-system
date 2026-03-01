"""CrewAI 风格的小说生成 Crew 管理器

采用直接编排模式，通过 QwenClient 调用通义千问模型，
而非使用 CrewAI 的内置 LLM 集成。

集成 TeamContext 实现 Agent 间的信息共享和状态追踪。
集成审查反馈循环、投票共识、请求-应答协商机制。
"""

import json
import re
from typing import Any, Optional

from llm.cost_tracker import CostTracker
from llm.prompt_manager import PromptManager
from llm.qwen_client import QwenClient

# Use the project-wide logger
from core.logging_config import logger

# TeamContext 用于 Agent 间信息共享
from agents.team_context import NovelTeamContext

# Agent 间协作组件
from agents.review_loop import ReviewLoopHandler
from agents.voting_manager import VotingManager
from agents.agent_query_service import AgentQueryService


class NovelCrewManager:
    """小说生成 Crew 管理器
    
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
    ):
        """初始化 Crew 管理器
        
        Args:
            qwen_client: 通义千问客户端实例
            cost_tracker: 成本跟踪器实例
            quality_threshold: 质量评分阈值（达标即停止迭代）
            max_review_iterations: Writer-Editor 审查循环最大迭代次数
            max_fix_iterations: 连续性修复循环最大迭代次数
            enable_voting: 是否启用企划阶段投票共识
            enable_query: 是否启用写作过程中的设定查询
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

    def _extract_json_from_response(self, response: str) -> dict | list:
        """从 LLM 响应中提取 JSON
        
        LLM 可能会在 JSON 前后添加 markdown 代码块标记或其他文本,
        这个方法使用多种策略找到 JSON 内容并解析。
        
        Args:
            response: LLM 的原始响应文本
            
        Returns:
            解析后的 JSON 对象（dict 或 list）
            
        Raises:
            ValueError: 如果无法找到或解析 JSON
        """
        # 先尝试直接解析
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            pass

        # 尝试提取 markdown 代码块中的内容（先找```json...```的边界，再解析内部内容）
        code_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```"
        for match in re.finditer(code_block_pattern, response):
            block_content = match.group(1).strip()
            if block_content:
                try:
                    return json.loads(block_content)
                except json.JSONDecodeError:
                    continue

        # 使用括号匹配法找到完整的 JSON 对象或数组
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            start_idx = response.find(start_char)
            if start_idx == -1:
                continue
            
            # 从起始位置向后扫描，使用括号计数找到匹配的闭合
            depth = 0
            in_string = False
            escape_next = False
            for i in range(start_idx, len(response)):
                ch = response[i]
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\' and in_string:
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
                        candidate = response[start_idx:i + 1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            break  # 这个起始位置不行，试下一个策略

        raise ValueError(f"无法从响应中提取有效的 JSON: {response[:200]}...")

    async def _call_agent(
        self,
        agent_name: str,
        system_prompt: str,
        task_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        expect_json: bool = True,
    ) -> dict | str:
        """调用单个 Agent 并追踪成本

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
            ValueError: JSON 解析失败（当 expect_json=True 时）
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
                result = self._extract_json_from_response(content)
                logger.info(f"✅ [{agent_name}] 执行成功，返回 JSON 数据")
                return result
            else:
                logger.info(f"✅ [{agent_name}] 执行成功，返回文本内容（{len(content)} 字符）")
                return content
                
        except Exception as e:
            logger.error(f"❌ [{agent_name}] 执行失败: {e}")
            raise

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
        """执行完整的企划阶段

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

        world_task = self.pm.format(
            self.pm.WORLD_BUILDER_TASK,
            topic_analysis=json.dumps(topic_analysis, ensure_ascii=False, indent=2),
        ) + world_length_instructions
        
        world_setting = await self._call_agent(
            agent_name="世界观架构师",
            system_prompt=self.pm.WORLD_BUILDER_SYSTEM,
            task_prompt=world_task,
            temperature=0.7,
            max_tokens=6000,
            expect_json=True,
        )

        # 3. 角色设计
        character_length_instructions = ""
        if length_type == "long":
            character_length_instructions = "\n\n重要要求：为长篇小说设计丰富多样的角色群像，包括主角、多个重要配角、反派势力等，每个主要角色都要有完整的背景故事和成长弧。"
        elif length_type == "short":
            character_length_instructions = "\n\n重要要求：为短文聚焦核心角色，主要围绕少数几个关键人物展开，确保角色关系清晰，性格鲜明。"

        character_task = self.pm.format(
            self.pm.CHARACTER_DESIGNER_TASK,
            topic_analysis=json.dumps(topic_analysis, ensure_ascii=False, indent=2),
            world_setting=json.dumps(world_setting, ensure_ascii=False, indent=2),
        ) + character_length_instructions
        
        characters = await self._call_agent(
            agent_name="角色设计师",
            system_prompt=self.pm.CHARACTER_DESIGNER_SYSTEM,
            task_prompt=character_task,
            temperature=0.8,
            max_tokens=6000,
            expect_json=True,
        )

        # 4. 情节架构（使用带决策点标注的提示词）
        plot_length_instructions = ""
        if length_type == "long":
            plot_length_instructions = "\n\n重要要求：为长篇小说设计宏大的多卷情节架构，包括主线剧情、多条副线、多个高潮点和足够的伏笔，确保故事有长期发展的潜力。"
        elif length_type == "short":
            plot_length_instructions = "\n\n重要要求：为短文设计紧凑的单卷情节结构，有明确的开始、发展、高潮和结局，确保故事在有限篇幅内完整呈现。"

        # 启用投票时使用带决策点标注的模板
        plot_template = (
            self.pm.PLOT_ARCHITECT_WITH_DECISIONS_TASK
            if self.enable_voting
            else self.pm.PLOT_ARCHITECT_TASK
        )

        plot_task = self.pm.format(
            plot_template,
            world_setting=json.dumps(world_setting, ensure_ascii=False, indent=2),
            characters=json.dumps(characters, ensure_ascii=False, indent=2),
        ) + plot_length_instructions
        
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
                            {"name": "世界观架构师", "role": "世界观专家",
                             "perspective": "从世界观一致性和扩展性角度评估"},
                            {"name": "角色设计师", "role": "角色专家",
                             "perspective": "从角色发展和关系深度角度评估"},
                            {"name": "情节架构师", "role": "情节专家",
                             "perspective": "从情节张力和读者吸引力角度评估"},
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

        logger.info("=" * 60)
        logger.info("🎉 企划阶段完成！")
        logger.info("=" * 60)

        return {
            "topic_analysis": topic_analysis,
            "world_setting": world_setting,
            "characters": characters,
            "plot_outline": plot_outline,
        }

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
        """执行单章写作阶段

        流程：
        1. 章节策划师：制定章节计划
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
        
        # 记录到 TeamContext
        if team_context:
            team_context.add_agent_output("章节策划师", chapter_plan, f"第{chapter_number}章策划")

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
                world_setting_brief=world_brief,
                character_info=character_info or "（主要角色）",
                previous_ending=previous_chapters_summary[-200:] if previous_chapters_summary else "（本章为开篇）",
                chapter_title=chapter_plan.get("title", ""),
                query_answers="",
            )
        else:
            writer_system = self.pm.format(self.pm.WRITER_SYSTEM, genre=genre)
            writer_task = self.pm.format(
                self.pm.WRITER_TASK,
                chapter_number=chapter_number,
                chapter_plan=json.dumps(chapter_plan, ensure_ascii=False, indent=2),
                world_setting_brief=world_brief,
                character_info=character_info or "（主要角色）",
                previous_ending=previous_chapters_summary[-200:] if previous_chapters_summary else "（本章为开篇）",
                chapter_title=chapter_plan.get("title", ""),
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
            )

        # 记录到 TeamContext
        if team_context:
            team_context.add_agent_output("作家", {"draft_length": len(draft)}, f"第{chapter_number}章初稿")

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
                "编辑", {"edited_length": len(edited_content),
                        "review_iterations": review_result.total_iterations,
                        "final_score": review_result.final_score},
                f"第{chapter_number}章审查循环"
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
            
            continuity_report = await self._call_agent(
                agent_name="连续性审查员",
                system_prompt=self.pm.CONTINUITY_CHECKER_SYSTEM,
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
            fix_task = f"""以下章节存在连续性问题，请修复。

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
            team_context.add_agent_output("连续性审查员", continuity_report, f"第{chapter_number}章检查")
            # 更新本章出场角色的状态
            for char_name in chapter_characters:
                team_context.update_character_state(
                    char_name, 
                    last_appearance_chapter=chapter_number
                )
            # 添加时间线事件
            if chapter_plan.get("summary"):
                team_context.add_timeline_event(
                    chapter_number=chapter_number,
                    event=chapter_plan.get("summary", "")[:100],
                    characters=chapter_characters
                )

        quality_score = continuity_report.get("quality_score", 0) if continuity_report else 0

        logger.info("=" * 60)
        logger.info(f"🎉 第 {chapter_number} 章写作完成！")
        logger.info(f"   审查循环：{review_result.total_iterations} 轮, "
                     f"score={review_result.final_score:.1f}, "
                     f"converged={review_result.converged}")
        logger.info(f"   连续性评分：{quality_score}")
        logger.info(f"   发现问题：{len(continuity_report.get('issues', []))} 个" if continuity_report else "")
        logger.info("=" * 60)

        return {
            "chapter_plan": chapter_plan,
            "draft": draft,
            "edited_content": edited_content,
            "final_content": final_content,
            "continuity_report": continuity_report,
            "quality_score": quality_score,
            "review_loop_result": review_result.to_dict(),
        }

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
        max_query_rounds: int = 2,
    ) -> str:
        """处理 Writer 输出中的 [QUERY] 标记

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
            query_answers_text = "以下是你之前提出的设定疑问的回答，请据此完善内容：\n" + "\n".join(answers)
            clean_draft = AgentQueryService.remove_query_tags(draft)

            rewrite_task = self.pm.format(
                self.pm.WRITER_WITH_QUERY_TASK,
                chapter_number=chapter_number,
                chapter_plan=json.dumps(chapter_plan, ensure_ascii=False, indent=2),
                world_setting_brief=world_brief,
                character_info=character_info or "（主要角色）",
                previous_ending=previous_chapters_summary[-200:] if previous_chapters_summary else "（本章为开篇）",
                chapter_title=chapter_plan.get("title", ""),
                query_answers=query_answers_text,
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
