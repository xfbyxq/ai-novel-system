"""生成服务 - 连接 API 层和 Agent 层"""

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agents.agent_dispatcher import AgentDispatcher
from core.models.chapter import Chapter, ChapterStatus
from core.models.character import Character, RoleType, Gender
from core.models.generation_task import GenerationTask, TaskStatus, TaskType
from core.models.novel import Novel, NovelStatus
from core.models.plot_outline import PlotOutline
from core.models.token_usage import TokenUsage
from core.models.world_setting import WorldSetting
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient

# Use the project-wide logger
from core.logging_config import logger


class GenerationService:
    """小说生成服务，编排 CrewManager 并将结果持久化到数据库。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = QwenClient()
        self.cost_tracker = CostTracker()
        self.dispatcher = AgentDispatcher(self.client, self.cost_tracker)

    async def run_planning(self, novel_id: UUID, task_id: UUID) -> dict:
        """执行企划阶段并保存结果到数据库。"""
        # 加载小说
        result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id)
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
                task_type="planning",
                phase="planning",
                input_data={},
                status=TaskStatus.running,
                started_at=datetime.now(timezone.utc)
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
            )

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

                character = Character(
                    novel_id=novel_id,
                    name=char_data.get("name", "未命名"),
                    role_type=role_type_map.get(role_type_str, RoleType.minor),
                    gender=gender_map.get(gender_str),
                    age=char_data.get("age"),
                    appearance=char_data.get("appearance", ""),
                    personality=char_data.get("personality", ""),
                    background=char_data.get("background", ""),
                    goals=char_data.get("goals", ""),
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
            plot_outline = PlotOutline(
                novel_id=novel_id,
                structure_type=plot_data.get("structure_type", "three_act"),
                volumes=plot_data.get("volumes", []),
                main_plot=plot_data.get("main_plot", {}),
                sub_plots=plot_data.get("sub_plots", []),
                key_turning_points=plot_data.get("key_turning_points", []),
                climax_chapter=plot_data.get("climax_chapter"),
                raw_content=json.dumps(plot_data, ensure_ascii=False),
            )
            self.db.add(plot_outline)

            # 更新小说状态
            novel.status = NovelStatus.writing

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
            novel.token_cost = (novel.token_cost or Decimal("0")) + Decimal(str(cost_summary["total_cost"]))

            await self.db.commit()

            logger.info(f"企划阶段完成，总消耗 {cost_summary['total_tokens']} tokens, 成本 ¥{cost_summary['total_cost']:.4f}")
            return planning_result

        except Exception as e:
            logger.error(f"企划阶段失败: {e}")
            if task:
                task.status = TaskStatus.failed
                task.error_message = str(e)
                await self.db.commit()
            raise

    async def run_chapter_writing(
        self,
        novel_id: UUID,
        task_id: UUID,
        chapter_number: int,
        volume_number: int = 1,
    ) -> dict:
        """执行单章写作并保存结果到数据库。"""
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
                started_at=datetime.now(timezone.utc)
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
                characters_list.append({
                    "name": char.name,
                    "role_type": char.role_type.value if char.role_type else "minor",
                    "personality": char.personality or "",
                    "background": char.background or "",
                    "abilities": char.abilities or {},
                })

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

            # 构建前几章摘要
            previous_summary = ""
            for ch in sorted(novel.chapters, key=lambda c: c.chapter_number):
                if ch.chapter_number < chapter_number and ch.content:
                    # 取每章内容前200字作为摘要
                    previous_summary += f"\n第{ch.chapter_number}章 {ch.title or ''}：{ch.content[:200]}...\n"

            novel_data = {
                "title": novel.title,
                "genre": novel.genre,
                "world_setting": world_setting_dict,
                "characters": characters_list,
                "plot_outline": plot_outline_dict,
            }

            # 初始化Agent调度器
            await self.dispatcher.initialize()
            
            # 执行写作阶段
            self.cost_tracker.reset()
            writing_result = await self.dispatcher.run_chapter_writing(
                novel_id=novel_id,
                task_id=task_id,
                chapter_number=chapter_number,
                volume_number=volume_number,
                novel_data=novel_data,
                previous_chapters_summary=previous_summary,
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
            )
            self.db.add(chapter)

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
                    "title": chapter_plan.get("title", ""),
                    "word_count": word_count,
                    "quality_score": writing_result.get("quality_score", 0),
                }
                task.token_usage = cost_summary["total_tokens"]
                task.cost = cost_summary["total_cost"]

            from decimal import Decimal
            novel.token_cost = (novel.token_cost or Decimal("0")) + Decimal(str(cost_summary["total_cost"]))

            await self.db.commit()

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
        """执行批量章节写作并保存结果到数据库。"""
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
                started_at=datetime.now(timezone.utc)
            )
            self.db.add(task)
        else:
            task.status = TaskStatus.running
            task.started_at = datetime.now(timezone.utc)
        await self.db.commit()

        try:
            total_chapters = to_chapter - from_chapter + 1
            completed_chapters = 0
            failed_chapters = []
            all_results = []

            logger.info(
                f"开始批量生成章节: 第{from_chapter}-{to_chapter}章，"
                f"共 {total_chapters} 章"
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
                characters_list.append({
                    "name": char.name,
                    "role_type": char.role_type.value if char.role_type else "minor",
                    "personality": char.personality or "",
                    "background": char.background or "",
                    "abilities": char.abilities or {},
                })

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
            
            # 执行批量写作
            batch_result = await self.dispatcher.run_batch_writing(
                novel_id=novel_id,
                task_id=task_id,
                from_chapter=from_chapter,
                to_chapter=to_chapter,
                volume_number=volume_number,
                novel_data=novel_data
            )
            
            # 处理批量写作结果
            all_results = batch_result.get("results", [])
            completed_chapters = batch_result.get("completed_chapters", 0)
            failed_chapters_list = batch_result.get("failed_chapters", 0)
            
            # 更新任务进度
            if task:
                task.output_data = {
                    "total_chapters": total_chapters,
                    "completed_chapters": completed_chapters,
                    "failed_chapters": failed_chapters_list,
                    "progress": f"{completed_chapters}/{total_chapters}",
                }
                await self.db.commit()

            logger.info(
                f"批量生成完成 "
                f"({completed_chapters}/{total_chapters})"
            )

            # 更新任务状态
            if task:
                total_tokens = sum(r.get("token_usage", 0) for r in all_results)
                total_cost = sum(r.get("cost", 0) for r in all_results)

                task.status = TaskStatus.completed if failed_chapters_list == 0 else TaskStatus.failed
                task.completed_at = datetime.now(timezone.utc)
                task.output_data = {
                    "total_chapters": total_chapters,
                    "completed_chapters": completed_chapters,
                    "failed_chapters": failed_chapters_list,
                    "summary": f"成功 {completed_chapters} 章，失败 {failed_chapters_list} 章",
                }
                task.token_usage = total_tokens
                task.cost = total_cost
                task.error_message = (
                    f"{failed_chapters_list} 章生成失败" if failed_chapters_list > 0 else None
                )
                await self.db.commit()

            logger.info(
                f"批量生成完成: 成功 {completed_chapters} 章，"
                f"失败 {failed_chapters_list} 章"
            )

            return {
                "total_chapters": total_chapters,
                "completed_chapters": completed_chapters,
                "failed_chapters": failed_chapters_list,
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
        """内部方法：生成单个章节（不创建任务记录）。"""
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
            characters_list.append({
                "name": char.name,
                "role_type": char.role_type.value if char.role_type else "minor",
                "personality": char.personality or "",
                "background": char.background or "",
                "abilities": char.abilities or {},
            })

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

        # 构建前几章摘要
        previous_summary = ""
        for ch in sorted(novel.chapters, key=lambda c: c.chapter_number):
            if ch.chapter_number < chapter_number and ch.content:
                previous_summary += f"\n第{ch.chapter_number}章 {ch.title or ''}：{ch.content[:200]}...\n"

        novel_data = {
            "title": novel.title,
            "genre": novel.genre,
            "world_setting": world_setting_dict,
            "characters": characters_list,
            "plot_outline": plot_outline_dict,
        }

        # 初始化Agent调度器
        await self.dispatcher.initialize()
        
        # 执行写作阶段
        self.cost_tracker.reset()
        writing_result = await self.dispatcher.run_chapter_writing(
            novel_id=novel_id,
            task_id=None,  # 内部方法调用，无任务ID
            chapter_number=chapter_number,
            volume_number=volume_number,
            novel_data=novel_data,
            previous_chapters_summary=previous_summary,
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
        )
        self.db.add(chapter)

        # 更新小说统计
        novel.chapter_count = (novel.chapter_count or 0) + 1
        novel.word_count = (novel.word_count or 0) + word_count

        # 更新 token 成本
        cost_summary = self.cost_tracker.get_summary()
        from decimal import Decimal
        novel.token_cost = (novel.token_cost or Decimal("0")) + Decimal(str(cost_summary["total_cost"]))

        await self.db.commit()

        return {
            "chapter_number": chapter_number,
            "title": chapter_plan.get("title", ""),
            "word_count": word_count,
            "quality_score": writing_result.get("quality_score", 0),
            "token_usage": cost_summary["total_tokens"],
            "cost": cost_summary["total_cost"],
        }
