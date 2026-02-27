"""Agent调度器 - 负责在不同Agent实现之间进行调度"""

import asyncio
from typing import Dict, Any, Optional, Union
from uuid import UUID, uuid4

from agents.agent_manager import get_agent_manager
from agents.agent_scheduler import AgentTask, TaskStatus, TaskPriority
from agents.crew_manager import NovelCrewManager
from llm.qwen_client import QwenClient
from llm.cost_tracker import CostTracker

# Use the project-wide logger
from core.logging_config import logger


class AgentDispatcher:
    """Agent调度器，负责在不同Agent实现之间进行调度"""
    
    def __init__(self, client: QwenClient, cost_tracker: CostTracker):
        """初始化Agent调度器
        
        Args:
            client: LLM客户端
            cost_tracker: 成本跟踪器
        """
        self.client = client
        self.cost_tracker = cost_tracker
        self.agent_manager = get_agent_manager()
        self.crew_manager = NovelCrewManager(client, cost_tracker)
        self.use_scheduled_agents = False  # 默认使用CrewAI风格系统，确保完整的企划阶段
    
    async def initialize(self):
        """初始化Agent调度器
        
        - 初始化Agent管理器
        - 启动所有Agent
        """
        logger.info("🎮 初始化Agent调度器...")
        await self.agent_manager.initialize()
        await self.agent_manager.start()
        logger.info("🎮 Agent调度器初始化完成！")
    
    def set_use_scheduled_agents(self, use_scheduled: bool):
        """设置是否使用基于调度器的Agent系统
        
        Args:
            use_scheduled: 是否使用基于调度器的Agent系统
        """
        self.use_scheduled_agents = use_scheduled
        logger.info(f"🎮 Agent调度器模式设置为: {'基于调度器' if use_scheduled else 'CrewAI风格'}")
    
    async def run_planning(self, novel_id: UUID, task_id: UUID, **kwargs) -> Dict[str, Any]:
        """执行企划阶段
        
        Args:
            novel_id: 小说ID
            task_id: 任务ID
            **kwargs: 额外参数
            
        Returns:
            Dict[str, Any]: 企划结果
        """
        if self.use_scheduled_agents:
            return await self._run_planning_with_scheduled_agents(novel_id, task_id, **kwargs)
        else:
            return await self._run_planning_with_crew_manager(novel_id, **kwargs)
    
    async def _run_planning_with_scheduled_agents(self, novel_id: UUID, task_id: UUID, **kwargs) -> Dict[str, Any]:
        """使用基于调度器的Agent系统执行企划阶段
        
        Args:
            novel_id: 小说ID
            task_id: 任务ID
            **kwargs: 额外参数
            
        Returns:
            Dict[str, Any]: 企划结果
        """
        logger.info(f"🎮 使用基于调度器的Agent系统执行企划阶段 - 小说ID: {novel_id}")
        
        try:
            # 获取调度器
            scheduler = self.agent_manager.get_scheduler()
            if not scheduler:
                logger.error("❌ 调度器未初始化")
                return await self._run_planning_with_crew_manager(novel_id, **kwargs)
            
            # 提取参数
            genre = kwargs.get('genre')
            tags = kwargs.get('tags', [])
            context = kwargs.get('context', '')
            
            # 构建市场分析任务
            market_task = AgentTask(
                task_id=uuid4(),
                task_name=f"市场分析 - 小说 {novel_id}",
                task_type="market_analysis",
                priority=TaskPriority.HIGH,
                input_data={
                    "market_data": [],
                    "platform": "all",
                    "genre": genre,
                    "tags": tags,
                    "context": context,
                }
            )
            
            # 提交市场分析任务
            market_task_id = await scheduler.submit_task(market_task)
            logger.info(f"🎮 提交市场分析任务: {market_task_id}")
            
            # 等待任务完成
            await self._wait_for_task_completion(scheduler, market_task_id)
            
            # 获取任务结果
            market_task_result = scheduler.tasks.get(market_task_id)
            if not market_task_result or market_task_result.status != TaskStatus.COMPLETED:
                logger.error("❌ 市场分析任务失败")
                return await self._run_planning_with_crew_manager(novel_id, **kwargs)
            
            market_analysis = market_task_result.result or {}
            
            # 构建内容策划任务
            content_task = AgentTask(
                task_id=uuid4(),
                task_name=f"内容策划 - 小说 {novel_id}",
                task_type="content_planning",
                priority=TaskPriority.HIGH,
                dependencies=[market_task_id],
                input_data={
                    "market_analysis": market_analysis,
                    "user_preferences": {
                        "genre": genre,
                        "tags": tags,
                        "context": context,
                    },
                }
            )
            
            # 提交内容策划任务
            content_task_id = await scheduler.submit_task(content_task)
            logger.info(f"🎮 提交内容策划任务: {content_task_id}")
            
            # 等待任务完成
            await self._wait_for_task_completion(scheduler, content_task_id)
            
            # 获取任务结果
            content_task_result = scheduler.tasks.get(content_task_id)
            if not content_task_result or content_task_result.status != TaskStatus.COMPLETED:
                logger.error("❌ 内容策划任务失败")
                return await self._run_planning_with_crew_manager(novel_id, **kwargs)
            
            content_planning = content_task_result.result or {}
            
            # 当前调度器实现还不完善，降级到 CrewManager
            logger.warning("⚠️  调度器当前仅支持市场分析，降级到 CrewManager 执行完整企划")
            return await self._run_planning_with_crew_manager(novel_id, **kwargs)
            
        except Exception as e:
            logger.error(f"❌ 基于调度器的企划阶段执行失败: {e}")
            return await self._run_planning_with_crew_manager(novel_id, **kwargs)
    
    async def _run_planning_with_crew_manager(self, novel_id: UUID, **kwargs) -> Dict[str, Any]:
        """使用CrewAI风格系统执行企划阶段

        Args:
            novel_id: 小说ID
            **kwargs: 额外参数

        Returns:
            Dict[str, Any]: 企划结果
        """
        logger.info(f"🎮 使用CrewAI风格系统执行企划阶段 - 小说ID: {novel_id}")
        
        # 提取参数
        genre = kwargs.get('genre')
        tags = kwargs.get('tags', [])
        context = kwargs.get('context', '')
        length_type = kwargs.get('length_type', 'medium')
        
        # 使用CrewManager执行企划
        return await self.crew_manager.run_planning_phase(
            genre=genre,
            tags=tags,
            context=context,
            length_type=length_type,
        )
    
    async def run_chapter_writing(self, novel_id: UUID, task_id: UUID, chapter_number: int, volume_number: int = 1, **kwargs) -> Dict[str, Any]:
        """执行单章写作
        
        Args:
            novel_id: 小说ID
            task_id: 任务ID
            chapter_number: 章节号
            volume_number: 卷号
            **kwargs: 额外参数
            
        Returns:
            Dict[str, Any]: 写作结果
        """
        if self.use_scheduled_agents:
            return await self._run_chapter_writing_with_scheduled_agents(novel_id, task_id, chapter_number, volume_number, **kwargs)
        else:
            return await self._run_chapter_writing_with_crew_manager(novel_id, chapter_number, volume_number, **kwargs)
    
    async def _run_chapter_writing_with_scheduled_agents(self, novel_id: UUID, task_id: UUID, chapter_number: int, volume_number: int = 1, **kwargs) -> Dict[str, Any]:
        """使用基于调度器的Agent系统执行单章写作
        
        Args:
            novel_id: 小说ID
            task_id: 任务ID
            chapter_number: 章节号
            volume_number: 卷号
            **kwargs: 额外参数
            
        Returns:
            Dict[str, Any]: 写作结果
        """
        logger.info(f"🎮 使用基于调度器的Agent系统执行第{chapter_number}章写作 - 小说ID: {novel_id}")
        
        # 这里需要实现基于调度器的写作阶段逻辑
        # 暂时使用CrewAI风格系统作为备选
        logger.warning("⚠️  基于调度器的写作阶段尚未实现，使用CrewAI风格系统作为备选")
        return await self._run_chapter_writing_with_crew_manager(novel_id, chapter_number, volume_number, **kwargs)
    
    async def _run_chapter_writing_with_crew_manager(self, novel_id: UUID, chapter_number: int, volume_number: int = 1, **kwargs) -> Dict[str, Any]:
        """使用CrewAI风格系统执行单章写作

        Args:
            novel_id: 小说ID
            chapter_number: 章节号
            volume_number: 卷号
            **kwargs: 额外参数

        Returns:
            Dict[str, Any]: 写作结果
        """
        logger.info(f"🎮 使用CrewAI风格系统执行第{chapter_number}章写作 - 小说ID: {novel_id}")
        
        # 提取参数
        novel_data = kwargs.get('novel_data')
        previous_chapters_summary = kwargs.get('previous_chapters_summary', '')
        character_states = kwargs.get('character_states', '')
        writing_style = kwargs.get('writing_style', 'modern')
        team_context = kwargs.get('team_context', None)
        
        # 使用CrewManager执行写作
        return await self.crew_manager.run_writing_phase(
            novel_data=novel_data,
            chapter_number=chapter_number,
            volume_number=volume_number,
            previous_chapters_summary=previous_chapters_summary,
            character_states=character_states,
            writing_style=writing_style,
            team_context=team_context,
        )
    
    async def run_batch_writing(self, novel_id: UUID, task_id: UUID, from_chapter: int, to_chapter: int, volume_number: int = 1, **kwargs) -> Dict[str, Any]:
        """执行批量写作
        
        Args:
            novel_id: 小说ID
            task_id: 任务ID
            from_chapter: 起始章节
            to_chapter: 结束章节
            volume_number: 卷号
            **kwargs: 额外参数
            
        Returns:
            Dict[str, Any]: 批量写作结果
        """
        logger.info(f"🎮 执行批量写作 - 小说ID: {novel_id}, 章节范围: {from_chapter}-{to_chapter}")
        
        # 批量写作暂时使用CrewAI风格系统
        results = []
        for chapter_num in range(from_chapter, to_chapter + 1):
            try:
                result = await self.run_chapter_writing(
                    novel_id=novel_id,
                    task_id=task_id,
                    chapter_number=chapter_num,
                    volume_number=volume_number,
                    **kwargs
                )
                results.append(result)
                logger.info(f"🎮 第{chapter_num}章写作完成")
            except Exception as e:
                logger.error(f"❌ 第{chapter_num}章写作失败: {e}")
                results.append({"error": str(e), "chapter_number": chapter_num})
        
        return {
            "total_chapters": to_chapter - from_chapter + 1,
            "completed_chapters": len([r for r in results if "error" not in r]),
            "failed_chapters": len([r for r in results if "error" in r]),
            "results": results
        }
    
    async def get_agent_statuses(self) -> Dict[str, str]:
        """获取所有Agent状态
        
        Returns:
            Dict[str, str]: Agent名称到状态的映射
        """
        return await self.agent_manager.get_all_agent_statuses()
    
    async def _wait_for_task_completion(self, scheduler, task_id, timeout=300):
        """等待任务完成
        
        Args:
            scheduler: 调度器实例
            task_id: 任务ID
            timeout: 超时时间（秒）
        """
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            task = scheduler.tasks.get(task_id)
            if task:
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    return
            await asyncio.sleep(2)
        logger.warning(f"⚠️  任务 {task_id} 超时")
    
    async def _run_chapter_writing_with_scheduled_agents(self, novel_id: UUID, task_id: UUID, chapter_number: int, volume_number: int = 1, **kwargs) -> Dict[str, Any]:
        """使用基于调度器的Agent系统执行单章写作
        
        Args:
            novel_id: 小说ID
            task_id: 任务ID
            chapter_number: 章节号
            volume_number: 卷号
            **kwargs: 额外参数
            
        Returns:
            Dict[str, Any]: 写作结果
        """
        logger.info(f"🎮 使用基于调度器的Agent系统执行第{chapter_number}章写作 - 小说ID: {novel_id}")
        
        try:
            # 获取调度器
            scheduler = self.agent_manager.get_scheduler()
            if not scheduler:
                logger.error("❌ 调度器未初始化")
                return await self._run_chapter_writing_with_crew_manager(novel_id, chapter_number, volume_number, **kwargs)
            
            # 提取参数
            novel_data = kwargs.get('novel_data')
            previous_chapters_summary = kwargs.get('previous_chapters_summary', '')
            
            # 构建写作任务
            writing_task = AgentTask(
                task_id=uuid4(),
                task_name=f"写作 - 小说 {novel_id} 第{chapter_number}章",
                task_type="writing",
                priority=TaskPriority.HIGH,
                input_data={
                    "content_plan": novel_data.get("plot_outline", {}),
                    "chapter_number": chapter_number,
                    "world_setting": novel_data.get("world_setting", {}),
                    "characters": novel_data.get("characters", []),
                    "plot_outline": novel_data.get("plot_outline", {}),
                }
            )
            
            # 提交写作任务
            writing_task_id = await scheduler.submit_task(writing_task)
            logger.info(f"🎮 提交写作任务: {writing_task_id}")
            
            # 等待任务完成
            await self._wait_for_task_completion(scheduler, writing_task_id)
            
            # 获取任务结果
            writing_task_result = scheduler.tasks.get(writing_task_id)
            if not writing_task_result or writing_task_result.status != TaskStatus.COMPLETED:
                logger.error("❌ 写作任务失败")
                return await self._run_chapter_writing_with_crew_manager(novel_id, chapter_number, volume_number, **kwargs)
            
            writing_result = writing_task_result.result or {}
            
            # 构建编辑任务
            editing_task = AgentTask(
                task_id=uuid4(),
                task_name=f"编辑 - 小说 {novel_id} 第{chapter_number}章",
                task_type="editing",
                priority=TaskPriority.MEDIUM,
                dependencies=[writing_task_id],
                input_data={
                    "draft_content": writing_result.get("content", ""),
                    "chapter_number": chapter_number,
                    "chapter_title": writing_result.get("chapter_title", f"第{chapter_number}章"),
                    "chapter_summary": "",
                }
            )
            
            # 提交编辑任务
            editing_task_id = await scheduler.submit_task(editing_task)
            logger.info(f"🎮 提交编辑任务: {editing_task_id}")
            
            # 等待任务完成
            await self._wait_for_task_completion(scheduler, editing_task_id)
            
            # 获取任务结果
            editing_task_result = scheduler.tasks.get(editing_task_id)
            if not editing_task_result or editing_task_result.status != TaskStatus.COMPLETED:
                logger.error("❌ 编辑任务失败")
                return await self._run_chapter_writing_with_crew_manager(novel_id, chapter_number, volume_number, **kwargs)
            
            editing_result = editing_task_result.result or {}
            
            # 构建写作结果
            final_result = {
                "chapter_plan": {},
                "draft": writing_result.get("content", ""),
                "edited_content": editing_result.get("edited_content", writing_result.get("content", "")),
                "final_content": editing_result.get("edited_content", writing_result.get("content", "")),
                "continuity_report": {},
                "quality_score": 0,
            }
            
            logger.info("✅ 基于调度器的写作阶段执行完成")
            return final_result
            
        except Exception as e:
            logger.error(f"❌ 基于调度器的写作阶段执行失败: {e}")
            return await self._run_chapter_writing_with_crew_manager(novel_id, chapter_number, volume_number, **kwargs)
    
    async def shutdown(self):
        """关闭Agent调度器
        
        - 停止所有Agent
        """
        logger.info("🎮 关闭Agent调度器...")
        await self.agent_manager.stop()
        logger.info("🎮 Agent调度器关闭完成！")