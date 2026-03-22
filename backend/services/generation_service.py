"""生成服务 - 连接 API 层和 Agent 层."""

import json
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agents.agent_dispatcher import AgentDispatcher
from agents.foreshadowing_tracker import ForeshadowingTracker
from agents.team_context import NovelTeamContext
from backend.config import settings

# Use the project-wide logger
from core.logging_config import logger
from core.models.chapter import Chapter, ChapterStatus
from core.models.character import Character, Gender, RoleType
from core.models.generation_task import GenerationTask, TaskStatus
from core.models.novel import Novel, NovelStatus
from core.models.plot_outline import PlotOutline
from core.models.token_usage import TokenUsage
from core.models.world_setting import WorldSetting
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient

from .agentmesh_memory_adapter import get_novel_memory_adapter
from .memory_service import get_novel_memory_service
from .agent_activity_recorder import get_agent_activity_recorder
from .context_manager import UnifiedContextManager


class GenerationService:
    """小说生成服务，编排 CrewManager 并将结果持久化到数据库."""

    def __init__(self, db: AsyncSession):
        """初始化方法."""
        self.db = db
        self.client = QwenClient()
        self.cost_tracker = CostTracker()

        # 初始化 Agent 活动记录器
        self.activity_recorder = get_agent_activity_recorder(db)

        # 从配置文件读取审查循环配置
        self.dispatcher = AgentDispatcher(
            self.client,
            self.cost_tracker,
            # 章节审查配置
            quality_threshold=settings.CHAPTER_QUALITY_THRESHOLD,
            max_review_iterations=settings.MAX_CHAPTER_REVIEW_ITERATIONS,
            max_fix_iterations=settings.MAX_FIX_ITERATIONS,
            # 功能开关
            enable_voting=settings.ENABLE_VOTING,
            enable_query=settings.ENABLE_QUERY,
            enable_world_review=settings.ENABLE_WORLD_REVIEW,
            enable_character_review=settings.ENABLE_CHARACTER_REVIEW,
            enable_plot_review=settings.ENABLE_PLOT_REVIEW,
            # 大纲细化开关
            enable_outline_refinement=settings.ENABLE_OUTLINE_REFINEMENT,
            # 各阶段质量阈值
            world_quality_threshold=settings.WORLD_QUALITY_THRESHOLD,
            character_quality_threshold=settings.CHARACTER_QUALITY_THRESHOLD,
            plot_quality_threshold=settings.PLOT_QUALITY_THRESHOLD,
            # 各阶段最大迭代次数
            max_world_review_iterations=settings.MAX_WORLD_REVIEW_ITERATIONS,
            max_character_review_iterations=settings.MAX_CHARACTER_REVIEW_ITERATIONS,
            max_plot_review_iterations=settings.MAX_PLOT_REVIEW_ITERATIONS,
        )

        self.memory_service = get_novel_memory_service()
        # 新增：持久化记忆适配器（SQLite + FTS5）
        self.persistent_memory = get_novel_memory_adapter()
        # 统一上下文管理器
        self._context_managers: dict[str, UnifiedContextManager] = {}
        # 章节写作计数器（用于大纲动态更新触发）
        self._chapter_write_counter: dict[str, int] = {}
        # 记录小说最后活跃时间，用于清理长期未使用的计数器
        self._last_active_time: dict[str, datetime] = {}

    def _get_context_manager(self, novel_id: UUID) -> UnifiedContextManager:
        """
        获取或创建小说的上下文管理器.
        
        Args:
            novel_id: 小说 ID
        
        Returns:
            UnifiedContextManager 实例
        """
        novel_id_str = str(novel_id)
        
        if novel_id_str not in self._context_managers:
            self._context_managers[novel_id_str] = UnifiedContextManager(
                db=self.db,
                novel_id=novel_id,
                cache_max_size=100,
                cache_ttl_minutes=30,
            )
            logger.info(f"Created context manager for novel {novel_id}")
        
        # 更新活跃时间
        self._last_active_time[novel_id_str] = datetime.now(timezone.utc)
        
        return self._context_managers[novel_id_str]

    async def run_planning(self, novel_id: UUID, task_id: UUID) -> dict:
        """执行企划阶段并保存结果到数据库."""
        # 加载小说
        result = await self.db.execute(select(Novel).where(Novel.id == novel_id))
        novel = result.scalar_one_or_none()
        if not novel:
            raise ValueError(f"小说 {novel_id} 不存在")

        # 并发控制：检查是否已有企划任务在运行
        existing_result = await self.db.execute(
            select(GenerationTask)
            .where(
                GenerationTask.novel_id == novel_id,
                GenerationTask.task_type == "planning",
                GenerationTask.id != task_id,  # 排除当前任务本身
                GenerationTask.status.in_(["pending", "running"]),
            )
            .order_by(GenerationTask.created_at.desc())
        )
        existing_task = existing_result.scalar_one_or_none()
        if existing_task:
            raise ValueError(f"该小说已有企划任务在运行中 (Task ID: {existing_task.id})")

        # 更新任务状态
        task_result = await self.db.execute(
            select(GenerationTask).where(GenerationTask.id == task_id)
        )
        task = task_result.scalar_one_or_none()
        if not task:
            # 创建新任务记录
            task = GenerationTask(
                id=task_id,
                novel_id=novel_id,
                task_type="planning",
                phase="planning",
                input_data={},
                status=TaskStatus.running,
                started_at=datetime.now(timezone.utc),
            )
            self.db.add(task)
        else:
            task.status = TaskStatus.running
            task.started_at = datetime.now(timezone.utc)
        await self.db.commit()

        try:
            # 初始化Agent调度器
            await self.dispatcher.initialize()

            # 执行企划阶段
            self.cost_tracker.reset()
            planning_result = await self.dispatcher.run_planning(
                novel_id=novel_id,
                task_id=task_id,
                genre=novel.genre,
                tags=novel.tags or [],
                context=novel.synopsis or "",
                length_type=(
                    novel.length_type
                    if novel.length_type and novel.length_type != "medium"
                    else "medium"
                ),
            )

            # 删除旧的企划数据（如果存在），以便重新生成
            from sqlalchemy import delete

            await self.db.execute(delete(WorldSetting).where(WorldSetting.novel_id == novel_id))
            await self.db.execute(delete(Character).where(Character.novel_id == novel_id))
            await self.db.execute(delete(PlotOutline).where(PlotOutline.novel_id == novel_id))
            await self.db.flush()

            # 保存世界观设定（LLM 可能返回非标准结构）
            world_data = planning_result.get("world_setting", {})
            if isinstance(world_data, list):
                world_data = world_data[0] if world_data else {}
            if not isinstance(world_data, dict):
                world_data = {}
            world_setting = WorldSetting(
                novel_id=novel_id,
                world_name=world_data.get("world_name", ""),
                world_type=world_data.get("world_type", ""),
                power_system=world_data.get("power_system", {}),
                geography=world_data.get("geography", {}),
                factions=world_data.get("factions", []),
                rules=world_data.get("rules", []),
                timeline=world_data.get("timeline", []),
                special_elements=world_data.get("special_elements", []),
                raw_content=json.dumps(world_data, ensure_ascii=False),
            )
            self.db.add(world_setting)

            # 保存角色
            characters_data = planning_result.get("characters", [])
            if isinstance(characters_data, dict):
                characters_data = [characters_data]
            for char_data in characters_data:
                role_type_str = char_data.get("role_type", "minor")
                role_type_map = {
                    "protagonist": RoleType.protagonist,
                    "supporting": RoleType.supporting,
                    "antagonist": RoleType.antagonist,
                    "minor": RoleType.minor,
                }
                gender_str = char_data.get("gender", "")
                gender_map = {
                    "male": Gender.male,
                    "female": Gender.female,
                    "other": Gender.other,
                }

                # 处理 age 字段，确保是整数类型
                age_value = char_data.get("age")
                if age_value is not None:
                    if isinstance(age_value, str):
                        # 尝试从字符串中提取数字
                        numbers = re.findall(r"\d+", str(age_value))
                        if numbers:
                            age_value = int(numbers[0])  # 取第一个数字
                        else:
                            age_value = None  # 无法解析则设为 None
                    elif not isinstance(age_value, int):
                        age_value = None  # 非数字类型设为 None

                # 处理 Text 字段：LLM 可能返回 dict/list，需要序列化为字符串
                def _to_str(val) -> str:
                    if isinstance(val, (dict, list)):
                        return json.dumps(val, ensure_ascii=False)
                    return str(val) if val else ""

                character = Character(
                    novel_id=novel_id,
                    name=char_data.get("name", "未命名"),
                    role_type=role_type_map.get(role_type_str, RoleType.minor),
                    gender=gender_map.get(gender_str),
                    age=age_value,
                    appearance=_to_str(char_data.get("appearance", "")),
                    personality=_to_str(char_data.get("personality", "")),
                    background=_to_str(char_data.get("background", "")),
                    goals=_to_str(char_data.get("goals", "")),
                    abilities=char_data.get("abilities", {}),
                    relationships=char_data.get("relationships", {}),
                    growth_arc=char_data.get("growth_arc", {}),
                )
                self.db.add(character)

            # 保存情节大纲（LLM 可能返回 list 或 dict）
            plot_data = planning_result.get("plot_outline", {})
            if isinstance(plot_data, list):
                # LLM 直接返回了卷列表，包装为标准 dict
                plot_data = {
                    "structure_type": "multi_volume",
                    "volumes": plot_data,
                    "main_plot": {},
                    "sub_plots": [],
                    "key_turning_points": [],
                }

            # 保存主线剧情详细字段（如果存在）
            main_plot_detailed = plot_data.get("main_plot_detailed", {})

            plot_outline = PlotOutline(
                novel_id=novel_id,
                structure_type=plot_data.get("structure_type", "three_act"),
                volumes=plot_data.get("volumes", []),
                main_plot=plot_data.get("main_plot", {}),
                main_plot_detailed=main_plot_detailed,  # 新增：保存详细主线剧情
                sub_plots=plot_data.get("sub_plots", []),
                key_turning_points=plot_data.get("key_turning_points", []),
                climax_chapter=plot_data.get("climax_chapter"),
                raw_content=json.dumps(plot_data, ensure_ascii=False),
            )
            self.db.add(plot_outline)

            # 更新小说状态
            novel.status = NovelStatus.writing

            # 初始化持久化记忆（长期记忆：世界观、角色、大纲）
            await self._initialize_novel_persistent_memory(
                novel_id=novel_id, planning_result=planning_result
            )

            # 保存 token 使用记录
            cost_summary = self.cost_tracker.get_summary()
            for record in self.cost_tracker.records:
                token_usage = TokenUsage(
                    novel_id=novel_id,
                    task_id=task_id,
                    agent_name=record["agent_name"],
                    prompt_tokens=record["prompt_tokens"],
                    completion_tokens=record["completion_tokens"],
                    total_tokens=record["total_tokens"],
                    cost=record["cost"],
                )
                self.db.add(token_usage)

            # 更新任务状态
            if task:
                task.status = TaskStatus.completed
                task.completed_at = datetime.now(timezone.utc)
                task.output_data = {
                    "topic_analysis": planning_result.get("topic_analysis", {}),
                    "summary": "企划阶段完成",
                }
                task.token_usage = cost_summary["total_tokens"]
                task.cost = cost_summary["total_cost"]

            # 更新小说 token 成本
            from decimal import Decimal

            novel.token_cost = (novel.token_cost or Decimal("0")) + Decimal(
                str(cost_summary["total_cost"])
            )

            await self.db.commit()

            logger.info(
                f"企划阶段完成，总消耗 {cost_summary['total_tokens']} tokens, 成本 ¥{cost_summary['total_cost']:.4f}"
            )

            # 记录企划阶段的 Agent 活动摘要
            await self._record_planning_activities(
                novel_id=novel_id,
                task_id=task_id,
                planning_result=planning_result,
                cost_summary=cost_summary,
            )

            return planning_result

        except Exception as e:
            logger.error(f"企划阶段失败: {e}")
            try:
                await self.db.rollback()
                if task:
                    task.status = TaskStatus.failed
                    task.error_message = str(e)[:500]
                    await self.db.commit()
            except Exception as rollback_err:
                logger.error(f"企划失败后回滚/记录异常: {rollback_err}")
            raise

    async def run_outline_refinement(self, novel_id: UUID, task_id: UUID) -> dict:
        """执行大纲完善任务并保存结果到数据库."""
        from agents.crew_manager import NovelCrewManager
        from core.models.plot_outline import PlotOutline
        from core.models.world_setting import WorldSetting
        from core.models.character import Character
        from sqlalchemy import select

        # 加载小说和相关数据
        result = await self.db.execute(select(Novel).where(Novel.id == novel_id))
        novel = result.scalar_one_or_none()
        if not novel:
            raise ValueError(f"小说 {novel_id} 不存在")

        # 并发控制：检查是否已有大纲完善任务在运行
        existing_result = await self.db.execute(
            select(GenerationTask)
            .where(
                GenerationTask.novel_id == novel_id,
                GenerationTask.task_type == "outline_refinement",
                GenerationTask.id != task_id,  # 排除当前任务本身
                GenerationTask.status.in_(["pending", "running"]),
            )
            .order_by(GenerationTask.created_at.desc())
        )
        existing_tasks = existing_result.scalars().all()
        if existing_tasks:
            existing_task = existing_tasks[0]  # 取最新的一条
            raise ValueError(f"该小说已有大纲完善任务在运行中 (Task ID: {existing_task.id})")

        # 更新任务状态
        task_result = await self.db.execute(
            select(GenerationTask).where(GenerationTask.id == task_id)
        )
        task = task_result.scalar_one_or_none()
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")

        task.status = TaskStatus.running
        task.started_at = datetime.now(timezone.utc)
        await self.db.commit()

        try:
            # 获取当前大纲数据
            outline_result = await self.db.execute(
                select(PlotOutline).where(PlotOutline.novel_id == novel_id)
            )
            outline = outline_result.scalar_one_or_none()
            if not outline:
                raise ValueError(f"小说 {novel_id} 没有大纲数据")

            # 获取世界观设定
            world_result = await self.db.execute(
                select(WorldSetting).where(WorldSetting.novel_id == novel_id)
            )
            world_setting = world_result.scalar_one_or_none()

            # 获取角色列表
            characters_result = await self.db.execute(
                select(Character).where(Character.novel_id == novel_id)
            )
            characters = characters_result.scalars().all()

            # 准备输入数据 - 确保是字典格式
            outline_data = {
                "structure_type": outline.structure_type,
                "volumes": outline.volumes or [],
                "main_plot": outline.main_plot or {},
                "main_plot_detailed": outline.main_plot_detailed or {},
                "sub_plots": outline.sub_plots or [],
                "key_turning_points": outline.key_turning_points or [],
                "climax_chapter": outline.climax_chapter,
            }

            # 确保outline_data是字典类型
            if not isinstance(outline_data, dict):
                logger.error(f"outline_data类型错误: {type(outline_data)}, 内容: {outline_data}")
                raise ValueError(f"大纲数据格式错误，期望dict，实际得到{type(outline_data)}")

            world_data = (
                {
                    "world_name": world_setting.world_name if world_setting else "",
                    "world_type": world_setting.world_type if world_setting else "",
                    "power_system": world_setting.power_system if world_setting else {},
                    "geography": world_setting.geography if world_setting else {},
                    "factions": world_setting.factions if world_setting else [],
                    "rules": world_setting.rules if world_setting else [],
                    "timeline": world_setting.timeline if world_setting else [],
                    "special_elements": (world_setting.special_elements if world_setting else []),
                }
                if world_setting
                else {}
            )

            characters_data = [
                {
                    "name": char.name,
                    "role_type": (
                        char.role_type.value
                        if hasattr(char.role_type, "value")
                        else str(char.role_type)
                    ),
                    "gender": (
                        char.gender.value
                        if char.gender and hasattr(char.gender, "value")
                        else (str(char.gender) if char.gender else None)
                    ),
                    "age": char.age,
                    "appearance": char.appearance,
                    "personality": char.personality,
                    "background": char.background,
                    "goals": char.goals,
                    "abilities": char.abilities or {},
                    "relationships": char.relationships or {},
                    "growth_arc": char.growth_arc or {},
                }
                for char in characters
            ]

            # 获取完善选项
            options = task.input_data.get(
                "options",
                {
                    "max_iterations": 3,
                    "quality_threshold": 8.0,
                    "preserve_user_edits": True,
                },
            )

            # 初始化Agent调度器
            await self.dispatcher.initialize()

            # 执行大纲完善
            self.cost_tracker.reset()

            # 使用crew_manager执行完善
            crew_manager = NovelCrewManager(self.client, self.cost_tracker)
            enhancement_result = await crew_manager.refine_outline_comprehensive(
                outline=outline_data,
                world_setting=world_data,
                characters=characters_data,
                options=options,
                max_rounds=options.get("max_iterations", 3),
            )

            # 调试：检查返回数据格式
            logger.info(f"enhancement_result类型: {type(enhancement_result)}")
            logger.info(f"enhancement_result内容: {enhancement_result}")

            if "enhancement_result" in enhancement_result:
                enhanced_outline = enhancement_result["enhancement_result"]["enhanced_outline"]
                logger.info(f"enhanced_outline类型: {type(enhanced_outline)}")
                logger.info(f"enhanced_outline内容: {enhanced_outline}")

            # 保存完善结果到任务输出
            task_output = {
                "original_outline": outline_data,
                "enhanced_outline": enhancement_result["enhancement_result"]["enhanced_outline"],
                "improvements_made": enhancement_result["enhancement_result"]["improvements_made"],
                "round_history": enhancement_result["enhancement_result"]["round_history"],
                "total_rounds": enhancement_result["enhancement_result"]["total_rounds"],
                "quality_comparison": {},  # 可以在这里添加质量对比逻辑
            }

            # 保存 token 使用记录
            cost_summary = self.cost_tracker.get_summary()
            for record in self.cost_tracker.records:
                token_usage = TokenUsage(
                    novel_id=novel_id,
                    task_id=task_id,
                    agent_name=record["agent_name"],
                    prompt_tokens=record["prompt_tokens"],
                    completion_tokens=record["completion_tokens"],
                    total_tokens=record["total_tokens"],
                    cost=record["cost"],
                )
                self.db.add(token_usage)

            # 更新任务状态
            task.status = TaskStatus.completed
            task.completed_at = datetime.now(timezone.utc)
            task.output_data = task_output
            task.token_usage = cost_summary["total_tokens"]
            task.cost = cost_summary["total_cost"]

            # 自动应用增强结果到大纲表
            enhanced_outline = enhancement_result["enhancement_result"]["enhanced_outline"]
            if enhanced_outline and isinstance(enhanced_outline, dict):
                # 更新PlotOutline表中的数据
                outline.main_plot = enhanced_outline.get("main_plot", outline.main_plot)
                outline.main_plot_detailed = enhanced_outline.get(
                    "main_plot_detailed", outline.main_plot_detailed
                )
                outline.sub_plots = enhanced_outline.get("sub_plots", outline.sub_plots)
                outline.key_turning_points = enhanced_outline.get(
                    "key_turning_points", outline.key_turning_points
                )
                outline.volumes = enhanced_outline.get("volumes", outline.volumes)
                outline.structure_type = enhanced_outline.get(
                    "structure_type", outline.structure_type
                )
                logger.info("已自动应用大纲增强结果到数据库")

            # 更新小说 token 成本
            from decimal import Decimal

            novel.token_cost = (novel.token_cost or Decimal("0")) + Decimal(
                str(cost_summary["total_cost"])
            )

            await self.db.commit()

            logger.info(
                f"大纲完善任务完成，总消耗 {cost_summary['total_tokens']} tokens, 成本 ¥{cost_summary['total_cost']:.4f}"
            )

            return task_output

        except Exception as e:
            logger.error(f"大纲完善任务失败: {e}")
            try:
                await self.db.rollback()
                task.status = TaskStatus.failed
                task.error_message = str(e)[:500]
                task.completed_at = datetime.now(timezone.utc)
                await self.db.commit()
            except Exception as rollback_err:
                logger.error(f"大纲完善失败后回滚/记录异常: {rollback_err}")
            raise

    async def run_chapter_writing(
        self,
        novel_id: UUID,
        task_id: UUID,
        chapter_number: int,
        volume_number: int = 1,
    ) -> dict:
        """执行单章写作并保存结果到数据库."""
        # 加载小说及相关数据
        result = await self.db.execute(
            select(Novel)
            .where(Novel.id == novel_id)
            .options(
                selectinload(Novel.world_setting),
                selectinload(Novel.characters),
                selectinload(Novel.plot_outline),
                selectinload(Novel.chapters),
            )
        )
        novel = result.scalar_one_or_none()
        if not novel:
            raise ValueError(f"小说 {novel_id} 不存在")

        # 更新任务状态
        task_result = await self.db.execute(
            select(GenerationTask).where(GenerationTask.id == task_id)
        )
        task = task_result.scalar_one_or_none()
        if not task:
            # 创建新任务记录
            task = GenerationTask(
                id=task_id,
                novel_id=novel_id,
                task_type="writing",
                phase="planning",
                input_data={},
                status=TaskStatus.running,
                started_at=datetime.now(timezone.utc),
            )
            self.db.add(task)
        else:
            task.status = TaskStatus.running
            task.started_at = datetime.now(timezone.utc)
        await self.db.commit()

        try:
            # 构建 novel_data 给 dispatcher
            world_setting_dict = {}
            if novel.world_setting:
                ws = novel.world_setting
                world_setting_dict = {
                    "world_name": ws.world_name,
                    "world_type": ws.world_type,
                    "power_system": ws.power_system or {},
                    "geography": ws.geography or {},
                    "factions": ws.factions or {},
                    "rules": ws.rules or [],
                }

            characters_list = []
            for char in novel.characters:
                characters_list.append(
                    {
                        "name": char.name,
                        "role_type": (
                            char.role_type.value
                            if hasattr(char.role_type, "value")
                            else str(char.role_type or "minor")
                        ),
                        "personality": char.personality or "",
                        "background": char.background or "",
                        "abilities": char.abilities or {},
                    }
                )

            plot_outline_dict = {}
            if novel.plot_outline:
                po = novel.plot_outline
                plot_outline_dict = {
                    "structure_type": po.structure_type,
                    "volumes": po.volumes or [],
                    "main_plot": po.main_plot or {},
                    "sub_plots": po.sub_plots or [],
                    "key_turning_points": po.key_turning_points or [],
                }

            # 构建前几章摘要（使用统一上下文管理器）
            context_manager = self._get_context_manager(novel_id)
            previous_summary = await context_manager.build_previous_context(
                chapter_number=chapter_number,
                count=3,
            )

            # 获取角色状态（优先从持久化记忆获取）
            character_states_dict = self.persistent_memory.storage.get_all_character_states(
                str(novel_id)
            )
            if character_states_dict:
                # 将字典格式转换为字符串格式（用于提示词）
                character_states = self._format_character_states(character_states_dict)
            else:
                # 回退到内存缓存
                character_states = self.memory_service.get_character_states(str(novel_id))

            novel_data = {
                "title": novel.title,
                "genre": novel.genre,
                "world_setting": world_setting_dict,
                "characters": characters_list,
                "plot_outline": plot_outline_dict,
            }

            # 确保内存缓存中有小说记忆（供 update_chapter_summary 等方法使用）
            if not self.memory_service.get_novel_memory(str(novel_id)):
                self.memory_service.set_novel_memory(
                    str(novel_id),
                    {
                        "id": str(novel_id),
                        "title": novel.title,
                        "genre": novel.genre,
                        "world_setting": world_setting_dict,
                        "characters": characters_list,
                        "plot_outline": plot_outline_dict,
                        "synopsis": novel.synopsis or "",
                    },
                )

            # 获取或创建 TeamContext
            team_context = self._get_or_create_team_context(
                novel_id=str(novel_id), novel_title=novel.title, novel_data=novel_data
            )

            # 初始化Agent调度器
            await self.dispatcher.initialize()

            # 初始化反思代理（需要 novel_id 和持久化存储）
            self.dispatcher.crew_manager.setup_reflection(
                novel_id=str(novel_id),
                storage=self.persistent_memory.storage,
            )

            # 预加载前一章的细化大纲到 crew_manager 缓存（跨会话恢复）
            if chapter_number > 1:
                prev_chapter = next(
                    (ch for ch in novel.chapters if ch.chapter_number == chapter_number - 1),
                    None,
                )
                if prev_chapter and prev_chapter.detailed_outline:
                    self.dispatcher.crew_manager._chapter_detailed_outlines[chapter_number - 1] = (
                        prev_chapter.detailed_outline
                    )

            # 执行写作阶段（传递 TeamContext）
            self.cost_tracker.reset()
            writing_result = await self.dispatcher.run_chapter_writing(
                novel_id=novel_id,
                task_id=task_id,
                chapter_number=chapter_number,
                volume_number=volume_number,
                novel_data=novel_data,
                previous_chapters_summary=previous_summary,
                character_states=character_states,
                team_context=team_context,
            )

            # 保存章节
            final_content = writing_result.get("final_content", "")
            word_count = len(final_content)
            chapter_plan = writing_result.get("chapter_plan", {})

            # 构建章节标题：确保包含章节号
            raw_title = chapter_plan.get("title", "")
            if raw_title:
                # 如果标题已包含章节号，直接使用
                if f"第{chapter_number}章" in raw_title:
                    title = raw_title
                else:
                    # 否则添加章节号前缀
                    title = f"第{chapter_number}章：{raw_title}"
            else:
                # 没有标题，使用默认值
                title = f"第{chapter_number}章"

            chapter = Chapter(
                novel_id=novel_id,
                chapter_number=chapter_number,
                volume_number=volume_number,
                title=title,
                content=final_content,
                word_count=word_count,
                status=ChapterStatus.draft,
                outline=chapter_plan,
                plot_points=chapter_plan.get("plot_points", []),
                foreshadowing=chapter_plan.get("foreshadowing", []),
                quality_score=writing_result.get("quality_score", 0),
                continuity_issues=writing_result.get("continuity_report", {}).get("issues", []),
                detailed_outline=writing_result.get("detailed_outline", {}),
            )
            self.db.add(chapter)

            # 提取并存储章节摘要到记忆系统
            chapter_summary = self._extract_chapter_summary(
                content=final_content,
                chapter_plan=chapter_plan,
                chapter_number=chapter_number,
            )
            self.memory_service.update_chapter_summary(
                str(novel_id), chapter_number, chapter_summary
            )

            # 同时保存到持久化记忆系统
            await self.persistent_memory.save_chapter_memory(
                novel_id=str(novel_id),
                chapter_number=chapter_number,
                content=final_content,
                summary=chapter_summary,
            )

            # 更新角色状态（如果 writing_result 中包含角色更新信息）
            character_updates = writing_result.get("character_updates", {})
            for char_name, state in character_updates.items():
                self.memory_service.update_character_state(str(novel_id), char_name, state)
                # 同时更新持久化记忆
                await self.persistent_memory.update_character_state(
                    novel_id=str(novel_id),
                    character_name=char_name,
                    chapter_number=chapter_number,
                    updates=state,
                )

            # ===== 新增：角色自动检测 =====
            if settings.ENABLE_CHARACTER_AUTO_DETECTION:
                try:
                    from backend.services.character_auto_detector import (
                        CharacterAutoDetector,
                    )

                    detector = CharacterAutoDetector(self.db, self.client, self.cost_tracker)
                    new_characters = await detector.detect_and_register_new_characters(
                        novel_id=novel_id,
                        chapter_number=chapter_number,
                        chapter_content=final_content,
                        existing_characters=list(novel.characters),
                    )
                    if new_characters:
                        logger.info(
                            f"第{chapter_number}章检测到 {len(new_characters)} 个新角色: "
                            f"{[c.name for c in new_characters]}"
                        )
                except Exception as e:
                    logger.warning(f"新角色检测失败（不影响章节生成）: {e}")
            # ===== 角色自动检测结束 =====

            # 更新小说统计
            novel.chapter_count = (novel.chapter_count or 0) + 1
            novel.word_count = (novel.word_count or 0) + word_count

            # 保存 token 使用记录
            cost_summary = self.cost_tracker.get_summary()
            for record in self.cost_tracker.records:
                token_usage = TokenUsage(
                    novel_id=novel_id,
                    task_id=task_id,
                    agent_name=record["agent_name"],
                    prompt_tokens=record["prompt_tokens"],
                    completion_tokens=record["completion_tokens"],
                    total_tokens=record["total_tokens"],
                    cost=record["cost"],
                )
                self.db.add(token_usage)

            # 更新任务状态
            if task:
                task.status = TaskStatus.completed
                task.completed_at = datetime.now(timezone.utc)
                task.output_data = {
                    "chapter_number": chapter_number,
                    "title": title,  # 使用已构建好的完整标题
                    "word_count": word_count,
                    "quality_score": writing_result.get("quality_score", 0),
                }
                task.token_usage = cost_summary["total_tokens"]
                task.cost = cost_summary["total_cost"]

            from decimal import Decimal

            novel.token_cost = (novel.token_cost or Decimal("0")) + Decimal(
                str(cost_summary["total_cost"])
            )

            await self.db.commit()

            # ===== 新增：大纲动态更新触发 =====
            if settings.ENABLE_DYNAMIC_OUTLINE_UPDATE:
                novel_id_str = str(novel_id)
                self._chapter_write_counter[novel_id_str] = (
                    self._chapter_write_counter.get(novel_id_str, 0) + 1
                )
                # 更新最后活跃时间
                self._last_active_time[novel_id_str] = datetime.now()
                if (
                    self._chapter_write_counter[novel_id_str] % settings.OUTLINE_UPDATE_INTERVAL
                    == 0
                ):
                    await self._try_dynamic_outline_update(novel_id, chapter_number)
            # ===== 大纲动态更新触发结束 =====

            logger.info(
                f"第{chapter_number}章写作完成，"
                f"{word_count}字，质量评分 {writing_result.get('quality_score', 'N/A')}，"
                f"消耗 {cost_summary['total_tokens']} tokens"
            )
            return writing_result

        except Exception as e:
            logger.error(f"第{chapter_number}章写作失败: {e}")
            if task:
                task.status = TaskStatus.failed
                task.error_message = str(e)
                await self.db.commit()
            raise

    async def run_batch_writing(
        self,
        novel_id: UUID,
        task_id: UUID,
        from_chapter: int,
        to_chapter: int,
        volume_number: int = 1,
    ) -> dict:
        """执行批量章节写作并保存结果到数据库."""
        # 更新任务状态
        task_result = await self.db.execute(
            select(GenerationTask).where(GenerationTask.id == task_id)
        )
        task = task_result.scalar_one_or_none()
        if not task:
            # 创建新任务记录
            task = GenerationTask(
                id=task_id,
                novel_id=novel_id,
                task_type="writing",
                phase="planning",
                input_data={},
                status=TaskStatus.running,
                started_at=datetime.now(timezone.utc),
            )
            self.db.add(task)
        else:
            task.status = TaskStatus.running
            task.started_at = datetime.now(timezone.utc)
        await self.db.commit()

        try:
            total_chapters = to_chapter - from_chapter + 1
            completed_chapters = 0
            all_results = []

            logger.info(
                f"开始批量生成章节: 第{from_chapter}-{to_chapter}章，" f"共 {total_chapters} 章"
            )

            # 初始化Agent调度器
            await self.dispatcher.initialize()

            # 构建小说数据
            novel_result = await self.db.execute(
                select(Novel)
                .where(Novel.id == novel_id)
                .options(
                    selectinload(Novel.world_setting),
                    selectinload(Novel.characters),
                    selectinload(Novel.plot_outline),
                    selectinload(Novel.chapters),
                )
            )
            novel = novel_result.scalar_one_or_none()
            if not novel:
                raise ValueError(f"小说 {novel_id} 不存在")

            # 构建 novel_data
            world_setting_dict = {}
            if novel.world_setting:
                ws = novel.world_setting
                world_setting_dict = {
                    "world_name": ws.world_name,
                    "world_type": ws.world_type,
                    "power_system": ws.power_system or {},
                    "geography": ws.geography or {},
                    "factions": ws.factions or {},
                    "rules": ws.rules or [],
                }

            characters_list = []
            for char in novel.characters:
                characters_list.append(
                    {
                        "name": char.name,
                        "role_type": (
                            char.role_type.value
                            if hasattr(char.role_type, "value")
                            else str(char.role_type or "minor")
                        ),
                        "personality": char.personality or "",
                        "background": char.background or "",
                        "abilities": char.abilities or {},
                    }
                )

            plot_outline_dict = {}
            if novel.plot_outline:
                po = novel.plot_outline
                plot_outline_dict = {
                    "structure_type": po.structure_type,
                    "volumes": po.volumes or [],
                    "main_plot": po.main_plot or {},
                    "sub_plots": po.sub_plots or [],
                    "key_turning_points": po.key_turning_points or [],
                }

            novel_data = {
                "title": novel.title,
                "genre": novel.genre,
                "world_setting": world_setting_dict,
                "characters": characters_list,
                "plot_outline": plot_outline_dict,
            }

            # 执行批量写作（带连续失败检测和中断机制）
            all_results = []
            failed_chapters_list = 0
            continuous_failures = 0
            max_continuous_failures = 2  # 连续失败阈值
            batch_interrupted = False
            last_completed_chapter = from_chapter - 1  # 记录最后成功完成的章节

            for chapter_num in range(from_chapter, to_chapter + 1):
                try:
                    result = await self.run_chapter_writing(
                        novel_id=novel_id,
                        task_id=task_id,
                        chapter_number=chapter_num,
                        volume_number=volume_number,
                    )
                    all_results.append(result)
                    continuous_failures = 0  # 重置连续失败计数
                    last_completed_chapter = chapter_num  # 更新最后成功完成的章节
                    logger.info(f"✅ 第{chapter_num}章生成并保存成功")
                except Exception as e:
                    logger.error(f"❌ 第{chapter_num}章生成失败: {e}")
                    all_results.append({"error": str(e), "chapter_number": chapter_num})
                    failed_chapters_list += 1
                    continuous_failures += 1

                    # 连续失败超过阈值，中断批量生成
                    if continuous_failures >= max_continuous_failures:
                        logger.error(
                            f"⚠️ 连续{max_continuous_failures}章生成失败，"
                            f"中止批量生成以防止上下文断裂"
                        )
                        batch_interrupted = True
                        # 记录剩余未生成的章节
                        remaining_chapters = list(range(chapter_num + 1, to_chapter + 1))
                        if remaining_chapters:
                            logger.warning(f"剩余未生成章节: {remaining_chapters}")
                        break

            completed_chapters = len([r for r in all_results if "error" not in r])
            skipped_chapters = (
                to_chapter - from_chapter + 1 - len(all_results)
            )  # 因中断而跳过的章节数

            # 更新任务进度
            if task:
                task.output_data = {
                    "total_chapters": total_chapters,
                    "completed_chapters": completed_chapters,
                    "failed_chapters": failed_chapters_list,
                    "skipped_chapters": skipped_chapters,
                    "batch_interrupted": batch_interrupted,
                    "progress": f"{completed_chapters}/{total_chapters}",
                }
                await self.db.commit()

            logger.info(
                f"批量生成完成 "
                f"({completed_chapters}/{total_chapters})"
                f"{' [已中断]' if batch_interrupted else ''}"
            )

            # 更新任务状态
            if task:
                total_tokens = sum(r.get("token_usage", 0) for r in all_results)
                total_cost = sum(r.get("cost", 0) for r in all_results)

                # 根据是否中断和失败情况确定任务状态
                if batch_interrupted:
                    task.status = TaskStatus.failed
                elif failed_chapters_list == 0:
                    task.status = TaskStatus.completed
                else:
                    task.status = TaskStatus.failed

                task.completed_at = datetime.now(timezone.utc)

                # 构建摘要信息
                summary = f"成功 {completed_chapters} 章，失败 {failed_chapters_list} 章"
                if batch_interrupted:
                    summary += f"，因连续失败中断（跳过 {skipped_chapters} 章）"

                task.output_data = {
                    "total_chapters": total_chapters,
                    "completed_chapters": completed_chapters,
                    "failed_chapters": failed_chapters_list,
                    "skipped_chapters": skipped_chapters,
                    "batch_interrupted": batch_interrupted,
                    "summary": summary,
                }
                task.token_usage = total_tokens
                task.cost = total_cost

                # 构建错误信息
                if batch_interrupted:
                    task.error_message = f"连续{max_continuous_failures}章生成失败，批量任务已中断"
                    task.checkpoint_data = {
                        "last_completed_chapter": last_completed_chapter,
                        "next_chapter": last_completed_chapter + 1,
                        "remaining_chapters": list(
                            range(last_completed_chapter + 1, to_chapter + 1)
                        ),
                        "original_from_chapter": from_chapter,
                        "original_to_chapter": to_chapter,
                        "volume_number": volume_number,
                        "can_resume": True,
                    }
                elif failed_chapters_list > 0:
                    task.error_message = f"{failed_chapters_list} 章生成失败"
                else:
                    task.error_message = None

                await self.db.commit()

            logger.info(
                f"批量生成完成: 成功 {completed_chapters} 章，"
                f"失败 {failed_chapters_list} 章"
                f"{f'，跳过 {skipped_chapters} 章' if skipped_chapters > 0 else ''}"
            )

            return {
                "total_chapters": total_chapters,
                "completed_chapters": completed_chapters,
                "failed_chapters": failed_chapters_list,
                "skipped_chapters": skipped_chapters,
                "batch_interrupted": batch_interrupted,
                "results": all_results,
            }

        except Exception as e:
            logger.error(f"批量写作失败: {e}")
            if task:
                task.status = TaskStatus.failed
                task.error_message = str(e)
                await self.db.commit()
            raise

    async def _write_single_chapter(
        self,
        novel_id: UUID,
        chapter_number: int,
        volume_number: int = 1,
    ) -> dict:
        """内部方法：生成单个章节（不创建任务记录）."""
        # 加载小说及相关数据
        result = await self.db.execute(
            select(Novel)
            .where(Novel.id == novel_id)
            .options(
                selectinload(Novel.world_setting),
                selectinload(Novel.characters),
                selectinload(Novel.plot_outline),
                selectinload(Novel.chapters),
            )
        )
        novel = result.scalar_one_or_none()
        if not novel:
            raise ValueError(f"小说 {novel_id} 不存在")

        # 构建 novel_data
        world_setting_dict = {}
        if novel.world_setting:
            ws = novel.world_setting
            world_setting_dict = {
                "world_name": ws.world_name,
                "world_type": ws.world_type,
                "power_system": ws.power_system or {},
                "geography": ws.geography or {},
                "factions": ws.factions or {},
                "rules": ws.rules or [],
            }

        characters_list = []
        for char in novel.characters:
            characters_list.append(
                {
                    "name": char.name,
                    "role_type": (
                        char.role_type.value
                        if hasattr(char.role_type, "value")
                        else str(char.role_type or "minor")
                    ),
                    "personality": char.personality or "",
                    "background": char.background or "",
                    "abilities": char.abilities or {},
                }
            )

        plot_outline_dict = {}
        if novel.plot_outline:
            po = novel.plot_outline
            plot_outline_dict = {
                "structure_type": po.structure_type,
                "volumes": po.volumes or [],
                "main_plot": po.main_plot or {},
                "sub_plots": po.sub_plots or [],
                "key_turning_points": po.key_turning_points or [],
            }

        # 构建前几章摘要（使用统一上下文管理器）
        context_manager = self._get_context_manager(novel_id)
        previous_summary = await context_manager.build_previous_context(
            chapter_number=chapter_number,
            count=3,
        )

        # 获取角色状态
        character_states = self.memory_service.get_character_states(str(novel_id))

        novel_data = {
            "title": novel.title,
            "genre": novel.genre,
            "world_setting": world_setting_dict,
            "characters": characters_list,
            "plot_outline": plot_outline_dict,
        }

        # 初始化Agent调度器
        await self.dispatcher.initialize()

        # 预加载前一章的细化大纲到 crew_manager 缓存（跨会话恢复）
        if chapter_number > 1:
            prev_chapter = next(
                (ch for ch in novel.chapters if ch.chapter_number == chapter_number - 1),
                None,
            )
            if prev_chapter and prev_chapter.detailed_outline:
                self.dispatcher.crew_manager._chapter_detailed_outlines[chapter_number - 1] = (
                    prev_chapter.detailed_outline
                )

        # 执行写作阶段
        self.cost_tracker.reset()
        writing_result = await self.dispatcher.run_chapter_writing(
            novel_id=novel_id,
            task_id=None,  # 内部方法调用，无任务ID
            chapter_number=chapter_number,
            volume_number=volume_number,
            novel_data=novel_data,
            previous_chapters_summary=previous_summary,
            character_states=character_states,
        )

        # 保存章节
        final_content = writing_result.get("final_content", "")
        word_count = len(final_content)
        chapter_plan = writing_result.get("chapter_plan", {})

        chapter = Chapter(
            novel_id=novel_id,
            chapter_number=chapter_number,
            volume_number=volume_number,
            title=chapter_plan.get("title", f"第{chapter_number}章"),
            content=final_content,
            word_count=word_count,
            status=ChapterStatus.draft,
            outline=chapter_plan,
            plot_points=chapter_plan.get("plot_points", []),
            foreshadowing=chapter_plan.get("foreshadowing", []),
            quality_score=writing_result.get("quality_score", 0),
            continuity_issues=writing_result.get("continuity_report", {}).get("issues", []),
            detailed_outline=writing_result.get("detailed_outline", {}),
        )
        self.db.add(chapter)

        # 提取并存储章节摘要到记忆系统
        chapter_summary = self._extract_chapter_summary(
            content=final_content,
            chapter_plan=chapter_plan,
            chapter_number=chapter_number,
        )
        self.memory_service.update_chapter_summary(str(novel_id), chapter_number, chapter_summary)

        # ===== 新增：角色自动检测 =====
        if settings.ENABLE_CHARACTER_AUTO_DETECTION:
            try:
                from backend.services.character_auto_detector import (
                    CharacterAutoDetector,
                )

                detector = CharacterAutoDetector(self.db, self.client, self.cost_tracker)
                new_characters = await detector.detect_and_register_new_characters(
                    novel_id=novel_id,
                    chapter_number=chapter_number,
                    chapter_content=final_content,
                    existing_characters=list(novel.characters),
                )
                if new_characters:
                    logger.info(
                        f"[_write_single_chapter] 第{chapter_number}章检测到 "
                        f"{len(new_characters)} 个新角色: "
                        f"{[c.name for c in new_characters]}"
                    )
            except Exception as e:
                logger.warning(f"新角色检测失败（不影响章节生成）: {e}")
        # ===== 角色自动检测结束 =====

        # 更新小说统计
        novel.chapter_count = (novel.chapter_count or 0) + 1
        novel.word_count = (novel.word_count or 0) + word_count

        # 更新 token 成本
        cost_summary = self.cost_tracker.get_summary()
        from decimal import Decimal

        novel.token_cost = (novel.token_cost or Decimal("0")) + Decimal(
            str(cost_summary["total_cost"])
        )

        await self.db.commit()

        # ===== 新增：大纲动态更新触发 =====
        if settings.ENABLE_DYNAMIC_OUTLINE_UPDATE:
            novel_id_str = str(novel_id)
            self._chapter_write_counter[novel_id_str] = (
                self._chapter_write_counter.get(novel_id_str, 0) + 1
            )
            # 更新最后活跃时间
            self._last_active_time[novel_id_str] = datetime.now()
            if self._chapter_write_counter[novel_id_str] % settings.OUTLINE_UPDATE_INTERVAL == 0:
                await self._try_dynamic_outline_update(novel_id, chapter_number)
        # ===== 大纲动态更新触发结束 =====

        return {
            "chapter_number": chapter_number,
            "title": chapter_plan.get("title", ""),
            "word_count": word_count,
            "quality_score": writing_result.get("quality_score", 0),
            "token_usage": cost_summary["total_tokens"],
            "cost": cost_summary["total_cost"],
        }

    # ==================== 大纲动态更新 ====================

    async def _try_dynamic_outline_update(self, novel_id: UUID, current_chapter: int) -> None:
        """尝试执行大纲动态更新（不阻塞章节写作流程）."""
        try:
            logger.info(f"[DynamicOutline] 触发大纲偏差评估，当前章节: {current_chapter}")

            # 加载最近 N 章的摘要
            interval = settings.OUTLINE_UPDATE_INTERVAL
            recent_chapters = []
            start_ch = max(1, current_chapter - interval + 1)
            for ch_num in range(start_ch, current_chapter + 1):
                summary = self.memory_service.get_chapter_summaries(str(novel_id)).get(
                    str(ch_num), {}
                )
                if summary:
                    summary["chapter_number"] = ch_num
                    recent_chapters.append(summary)

            if not recent_chapters:
                logger.info("[DynamicOutline] 未找到最近章节摘要，跳过")
                return

            # 加载大纲、世界观、角色
            result = await self.db.execute(
                select(Novel)
                .where(Novel.id == novel_id)
                .options(
                    selectinload(Novel.world_setting),
                    selectinload(Novel.characters),
                    selectinload(Novel.plot_outline),
                )
            )
            novel = result.scalar_one_or_none()
            if not novel or not novel.plot_outline:
                logger.info("[DynamicOutline] 未找到小说或大纲，跳过")
                return

            po = novel.plot_outline
            outline_data = {
                "structure_type": po.structure_type,
                "volumes": po.volumes or [],
                "main_plot": po.main_plot or {},
                "main_plot_detailed": po.main_plot_detailed or {},
                "sub_plots": po.sub_plots or [],
                "key_turning_points": po.key_turning_points or [],
                "climax_chapter": po.climax_chapter,
            }

            world_setting_dict = {}
            if novel.world_setting:
                ws = novel.world_setting
                world_setting_dict = {
                    "world_name": ws.world_name,
                    "world_type": ws.world_type,
                    "power_system": ws.power_system or {},
                    "geography": ws.geography or {},
                }

            characters_list = [
                {
                    "name": c.name,
                    "role_type": (
                        c.role_type.value
                        if hasattr(c.role_type, "value")
                        else str(c.role_type or "minor")
                    ),
                    "personality": c.personality or "",
                }
                for c in novel.characters
            ]

            # 执行动态更新
            from agents.outline_dynamic_updater import OutlineDynamicUpdater

            updater = OutlineDynamicUpdater(
                client=self.client,
                cost_tracker=self.cost_tracker,
                deviation_threshold=settings.OUTLINE_DEVIATION_THRESHOLD,
            )
            update_result = await updater.run_dynamic_update(
                db=self.db,
                novel_id=novel_id,
                current_chapter=current_chapter,
                recent_chapters=recent_chapters,
                outline_data=outline_data,
                world_setting=world_setting_dict,
                characters=characters_list,
            )

            if update_result.get("updated"):
                logger.info(
                    f"[DynamicOutline] 大纲已更新: " f"{update_result.get('change_summary', [])}"
                )
                await self.db.commit()
            else:
                logger.info(
                    f"[DynamicOutline] 跳过更新: " f"{update_result.get('reason', '未知原因')}"
                )

        except Exception as e:
            logger.warning(f"[DynamicOutline] 大纲动态更新失败（不影响章节生成）: {e}")
        finally:
            # 定期清理过期的计数器，防止内存泄漏
            self._cleanup_expired_counters()

    # ==================== 辅助方法 ====================

    def _cleanup_expired_counters(self, max_inactive_hours: int = 24):
        """清理长期未活跃的小说计数器，防止内存泄漏.

        Args:
            max_inactive_hours: 最大非活跃小时数，默认24小时
        """
        from datetime import timedelta

        cutoff_time = datetime.now() - timedelta(hours=max_inactive_hours)
        expired_novels = []

        for novel_id, last_active in self._last_active_time.items():
            if last_active < cutoff_time:
                expired_novels.append(novel_id)

        # 删除过期的小说计数器和活跃时间记录
        for novel_id in expired_novels:
            self._chapter_write_counter.pop(novel_id, None)
            self._last_active_time.pop(novel_id, None)
            logger.debug(f"清理过期计数器: {novel_id}")

    def _build_previous_context(self, novel_id: UUID, novel: Novel, chapter_number: int) -> str:
        """构建结构化的前置章节上下文.

        优先使用记忆系统中的结构化摘要，回退到智能截取.

        Args:
            novel_id: 小说ID
            novel: Novel对象（包含已加载的chapters）
            chapter_number: 当前章节号

        Returns:
            前置章节上下文字符串
        """
        # 首先尝试从记忆系统获取结构化摘要
        summaries = self.memory_service.get_chapter_summaries(str(novel_id))

        previous_context = ""
        for ch in sorted(novel.chapters, key=lambda c: c.chapter_number):
            if ch.chapter_number < chapter_number and ch.content:
                ch_num_str = str(ch.chapter_number)
                if ch_num_str in summaries:
                    # 使用结构化摘要
                    summary = summaries[ch_num_str]
                    previous_context += f"\n## 第{ch.chapter_number}章 {ch.title or ''}\n"

                    key_events = summary.get("key_events", [])
                    if key_events:
                        if isinstance(key_events, list):
                            previous_context += (
                                f"**主要事件**: {', '.join(str(e) for e in key_events[:5])}\n"
                            )
                        else:
                            previous_context += f"**主要事件**: {key_events}\n"

                    char_changes = summary.get("character_changes", "")
                    if char_changes:
                        previous_context += f"**角色变化**: {char_changes}\n"

                    plot_progress = summary.get("plot_progress", "")
                    if plot_progress:
                        # 限制情节摘要长度
                        if len(plot_progress) > 300:
                            plot_progress = plot_progress[:300] + "..."
                        previous_context += f"**情节推进**: {plot_progress}\n"

                    foreshadowing = summary.get("foreshadowing", [])
                    if foreshadowing:
                        if isinstance(foreshadowing, list) and foreshadowing:
                            previous_context += (
                                f"**伏笔**: {', '.join(str(f) for f in foreshadowing[:3])}\n"
                            )
                else:
                    # 回退到智能截取（取前500字，找到完整句子边界）
                    content = ch.content[:500]
                    last_period = content.rfind("。")
                    if last_period > 300:
                        content = content[: last_period + 1]
                    previous_context += (
                        f"\n## 第{ch.chapter_number}章 {ch.title or ''}\n{content}\n"
                    )

        return previous_context

    def _extract_chapter_summary(
        self, content: str, chapter_plan: dict, chapter_number: int
    ) -> dict:
        """从章节内容提取结构化摘要.

        Args:
            content: 章节完整内容
            chapter_plan: 章节大纲（包含plot_points, foreshadowing等）
            chapter_number: 章节号

        Returns:
            结构化摘要字典
        """
        # 从章节内容中提取摘要信息
        plot_progress = ""
        if content:
            # 取内容前200字作为情节摘要
            plot_progress = content[:200]
            # 尝试找到完整句子
            last_period = plot_progress.rfind("。")
            if last_period > 100:
                plot_progress = plot_progress[: last_period + 1]

        # 提取结尾状态（最后100字）
        ending_state = ""
        if content and len(content) > 100:
            ending_state = content[-100:]
            # 尝试从句子开头开始
            first_period = ending_state.find("。")
            if first_period > 0 and first_period < 50:
                ending_state = ending_state[first_period + 1 :]
        elif content:
            ending_state = content

        return {
            "chapter_number": chapter_number,
            "title": chapter_plan.get("title", f"第{chapter_number}章"),
            "key_events": chapter_plan.get("plot_points", [])[:5],  # 主要事件（最多5个）
            "character_changes": self._extract_character_mentions(content),  # 角色变化
            "plot_progress": plot_progress,  # 情节摘要
            "foreshadowing": chapter_plan.get("foreshadowing", []),  # 伏笔
            "ending_state": ending_state,  # 结尾状态
        }

    def _format_character_states(self, states_dict: dict) -> str:
        """将角色状态字典格式化为提示词字符串.

        Args:
            states_dict: 角色状态字典 {角色名: 状态信息}

        Returns:
            格式化的角色状态字符串
        """
        if not states_dict:
            return ""

        parts = []
        for name, state in states_dict.items():
            info = [f"**{name}**"]
            if state.get("current_location"):
                info.append(f"  - 位置: {state['current_location']}")
            if state.get("cultivation_level"):
                info.append(f"  - 修为: {state['cultivation_level']}")
            if state.get("emotional_state"):
                info.append(f"  - 情绪: {state['emotional_state']}")
            if state.get("status") and state["status"] != "active":
                info.append(f"  - 状态: {state['status']}")
            if state.get("pending_events"):
                events = state["pending_events"]
                if isinstance(events, list) and events:
                    info.append(f"  - 待办: {', '.join(str(e) for e in events[:3])}")
            parts.append("\n".join(info))

        return "\n\n".join(parts) if parts else ""

    def _extract_character_mentions(self, content: str) -> str:
        """提取角色变化描述.

        简化实现：返回内容中可能的角色状态变化关键词.
        后续可增强为 LLM 提取或更复杂的规则匹配。

        Args:
            content: 章节内容

        Returns:
            角色变化描述字符串
        """
        if not content:
            return ""

        # 简化实现：检测常见的状态变化关键词
        change_keywords = [
            "突破",
            "晋升",
            "受伤",
            "死亡",
            "离开",
            "加入",
            "觉醒",
            "领悟",
            "失去",
            "获得",
            "决定",
            "背叛",
        ]

        found_changes = []
        for keyword in change_keywords:
            if keyword in content:
                # 找到关键词所在的句子
                idx = content.find(keyword)
                start = max(0, content.rfind("。", 0, idx) + 1)
                end = content.find("。", idx)
                if end == -1:
                    end = min(len(content), idx + 50)
                else:
                    end = min(end + 1, idx + 100)

                sentence = content[start:end].strip()
                if sentence and len(sentence) < 80:
                    found_changes.append(sentence)
                    if len(found_changes) >= 3:  # 最多提取3个变化
                        break

        return "; ".join(found_changes) if found_changes else ""

    # ==================== 新增：持久化记忆集成方法 ====================

    def _get_or_create_team_context(
        self, novel_id: str, novel_title: str, novel_data: dict
    ) -> NovelTeamContext:
        """获取或创建小说的 TeamContext.

        TeamContext 在整个小说生成过程中复用，用于 Agent 间信息共享.

        Args:
            novel_id: 小说ID
            novel_title: 小说标题
            novel_data: 小说数据字典

        Returns:
            NovelTeamContext 实例
        """
        if novel_id not in self._team_contexts:
            team_context = NovelTeamContext(novel_id, novel_title)
            team_context.set_novel_data(novel_data)

            # 集成伏笔追踪器
            team_context.foreshadowing_tracker = ForeshadowingTracker(novel_id)

            self._team_contexts[novel_id] = team_context
            logger.info(f"Created new TeamContext for novel {novel_id}")

        return self._team_contexts[novel_id]

    async def _initialize_novel_persistent_memory(self, novel_id: UUID, planning_result: dict):
        """初始化小说的持久化长期记忆.

        在企划阶段完成后调用，保存世界观、角色、大纲等核心设定.

        Args:
            novel_id: 小说ID
            planning_result: 企划结果
        """
        novel_id_str = str(novel_id)

        # 提取核心数据
        world_setting = planning_result.get("world_setting", {})
        characters = planning_result.get("characters", [])
        plot_outline = planning_result.get("plot_outline", {})
        topic_analysis = planning_result.get("topic_analysis", {})

        # 初始化持久化记忆
        await self.persistent_memory.initialize_novel_memory(
            novel_id=novel_id_str,
            novel_data={
                "title": topic_analysis.get("recommended_title", ""),
                "genre": topic_analysis.get("genre", ""),
                "synopsis": topic_analysis.get("synopsis", ""),
                "world_setting": world_setting,
                "characters": characters,
                "plot_outline": plot_outline,
            },
        )

        logger.info(f"Initialized persistent memory for novel {novel_id}")

    async def _build_previous_context_enhanced(
        self, novel_id: UUID, novel: Novel, chapter_number: int
    ) -> str:
        """构建增强的前置章节上下文.

        优先使用持久化记忆系统，回退到内存缓存和数据库.

        Args:
            novel_id: 小说ID
            novel: Novel对象
            chapter_number: 当前章节号

        Returns:
            前置章节上下文字符串
        """
        novel_id_str = str(novel_id)

        # 1. 首先尝试从持久化记忆获取上下文
        try:
            persistent_context = await self.persistent_memory.get_chapter_context(
                novel_id=novel_id_str, chapter_number=chapter_number, context_chapters=5
            )
            if persistent_context:
                logger.debug(f"Using persistent memory context for chapter {chapter_number}")
                return persistent_context
        except Exception as e:
            logger.warning(f"Failed to get persistent memory context: {e}")

        # 2. 回退到统一上下文管理器
        context_manager = self._get_context_manager(novel_id)
        return await context_manager.build_previous_context(
            chapter_number=chapter_number,
            count=3,
        )

    async def _record_planning_activities(
        self,
        novel_id: UUID,
        task_id: UUID,
        planning_result: dict,
        cost_summary: dict,
        cost_records: list = None,
    ):
        """记录企划阶段的 Agent 活动摘要.
    
        Args:
            novel_id: 小说 ID
            task_id: 任务 ID
            planning_result: 企划结果
            cost_summary: 成本摘要
            cost_records: 可选的 token 消耗记录列表，用于按 Agent 分别统计
        """
        try:
            # 从 cost_records 中按 Agent 提取 token 消耗
            agent_costs = {}
            if cost_records:
                for record in cost_records:
                    agent_name = record.get("agent_name", "")
                    if agent_name not in agent_costs:
                        agent_costs[agent_name] = {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                            "cost": 0,
                        }
                    agent_costs[agent_name]["prompt_tokens"] += record.get(
                        "prompt_tokens", 0
                    )
                    agent_costs[agent_name]["completion_tokens"] += record.get(
                        "completion_tokens", 0
                    )
                    agent_costs[agent_name]["total_tokens"] += record.get(
                        "total_tokens", 0
                    )
                    agent_costs[agent_name]["cost"] += record.get("cost", 0)
    
            # 辅助函数：获取 Agent 的 token 消耗
            def get_agent_cost(agent_name: str) -> tuple:
                if agent_name in agent_costs:
                    c = agent_costs[agent_name]
                    return c["total_tokens"], c["cost"]
                return 0, 0
    
            # 记录主题分析活动
            if "topic_analysis" in planning_result:
                tokens, cost = get_agent_cost("主题分析师")
                # 如果没找到，尝试从总成本中分配（兼容旧数据）
                if tokens == 0 and cost_summary.get("total_tokens", 0) > 0:
                    tokens = cost_summary.get("total_tokens", 0)
                    cost = cost_summary.get("total_cost", 0)
                await self.activity_recorder.record_planning_activity(
                    novel_id=novel_id,
                    task_id=task_id,
                    agent_name="主题分析师",
                    agent_role="市场趋势分析和选题推荐",
                    activity_subtype="topic_analysis",
                    input_data={"genre": planning_result.get("genre")},
                    output_data=planning_result.get("topic_analysis", {}),
                    total_tokens=tokens,
                    cost=cost,
                )
    
            # 记录世界观构建活动
            if "world_setting" in planning_result:
                tokens, cost = get_agent_cost("世界观架构师")
                # 尝试多个可能的 Agent 名称
                if tokens == 0:
                    for name in ["世界观审查员", "世界观察审查员"]:
                        if name in agent_costs:
                            tokens, cost = get_agent_cost(name)
                            break
                await self.activity_recorder.record_planning_activity(
                    novel_id=novel_id,
                    task_id=task_id,
                    agent_name="世界观架构师",
                    agent_role="世界观体系构建",
                    activity_subtype="world_building",
                    input_data={"topic_analysis": planning_result.get("topic_analysis")},
                    output_data=planning_result.get("world_setting", {}),
                    total_tokens=tokens,
                    cost=cost,
                )
    
            # 记录角色设计活动
            if "characters" in planning_result:
                tokens, cost = get_agent_cost("角色设计师")
                if tokens == 0:
                    for name in ["角色审查员", "角色审查"]:
                        if name in agent_costs:
                            tokens, cost = get_agent_cost(name)
                            break
                await self.activity_recorder.record_planning_activity(
                    novel_id=novel_id,
                    task_id=task_id,
                    agent_name="角色设计师",
                    agent_role="主要角色设计",
                    activity_subtype="character_design",
                    input_data={"world_setting": planning_result.get("world_setting")},
                    output_data={
                        "characters_count": len(planning_result.get("characters", []))
                    },
                    total_tokens=tokens,
                    cost=cost,
                    output_data={"characters_count": len(planning_result.get("characters", []))},
                )
    
            # 记录情节架构活动
            if "plot_outline" in planning_result:
                tokens, cost = get_agent_cost("情节架构师")
                if tokens == 0:
                    for name in ["大纲审查员", "情节审查员", "PlotReview"]:
                        if name in agent_costs:
                            tokens, cost = get_agent_cost(name)
                            break
                await self.activity_recorder.record_planning_activity(
                    novel_id=novel_id,
                    task_id=task_id,
                    agent_name="情节架构师",
                    agent_role="整体情节架构规划",
                    activity_subtype="plot_architecture",
                    input_data={
                        "world_setting": planning_result.get("world_setting"),
                        "characters": planning_result.get("characters"),
                    },
                    output_data={
                        "structure_type": planning_result.get("plot_outline", {}).get(
                            "structure_type"
                        ),
                        "volumes_count": len(
                            planning_result.get("plot_outline", {}).get("volumes", [])
                        ),
                    },
                    total_tokens=tokens,
                    cost=cost,
                )
    
            logger.info(f"✅ 企划阶段 Agent 活动记录完成")
        except Exception as e:
            logger.error(f"记录企划阶段 Agent 活动失败：{e}")
