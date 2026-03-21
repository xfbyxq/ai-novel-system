"""
CrewManager 连贯性保障集成示例

本文档展示如何将连贯性保障组件集成到 CrewManager 中。

注意：这是示例代码，实际集成需要根据现有 CrewManager 的代码结构进行调整。
"""
import logging
from typing import Any, Dict, List, Optional
from agents.continuity_integration_module import ContinuityIntegrationModule
from agents.enhanced_context_manager import EnhancedContextManager
from agents.theme_guardian import ThemeGuardian
from agents.chapter_outline_mapper import ChapterOutlineMapper
from agents.character_consistency_tracker import CharacterConsistencyTracker
from agents.foreshadowing_auto_injector import ForeshadowingAutoInjector
from agents.prevention_continuity_checker import PreventionContinuityChecker
from tests.continuity_system_test import ContinuityIntegrationResult

logger = logging.getLogger(__name__)


class EnhancedCrewManager:
    """
    增强版 CrewManager - 集成连贯性保障系统
    
    这是在原有 CrewManager 基础上的增强版本，
    添加了完整的连贯性保障流程。
    """
    
    def __init__(self, novel_id: str, novel_data: Dict[str, Any]):
        """
        初始化增强版 CrewManager
        
        Args:
            novel_id: 小说 ID
            novel_data: 小说数据
        """
        self.novel_id = novel_id
        self.novel_data = novel_data
        
        # 初始化连贯性保障模块
        self.continuity_module = ContinuityIntegrationModule(novel_id, novel_data)
        
        # 原有的 CrewManager 初始化代码...
        # self.pm = PromptManager()
        # self.agents = [...]
    
    async def run_writing_phase(
        self,
        chapter_number: int,
        volume_number: int = 1,
        **kwargs
    ) -> Dict[str, Any]:
        """
        运行写作阶段（带连贯性保障）
        
        新增流程：
        1. 准备阶段：构建增强上下文、获取大纲任务
        2. 策划阶段：章节策划 + 连贯性审查
        3. 生成阶段：使用增强提示词生成
        4. 验证阶段：生成后验证
        
        Args:
            chapter_number: 章节号
            volume_number: 卷号
            **kwargs: 其他参数
        
        Returns:
            写作结果
        """
        logger.info(f"Starting enhanced writing phase for chapter {chapter_number}")
        
        # ========== 步骤 1：准备阶段 ==========
        prep_result = await self._prepare_chapter_generation(
            chapter_number=chapter_number,
            volume_number=volume_number,
            **kwargs
        )
        
        # ========== 步骤 2：策划阶段 ==========
        chapter_plan = await self._run_enhanced_planning(
            chapter_number=chapter_number,
            prep_result=prep_result,
            **kwargs
        )
        
        # ========== 步骤 3：连贯性审查 ==========
        review_result = await self.continuity_module.review_chapter_plan(
            chapter_plan=chapter_plan,
            chapter_number=chapter_number,
            previous_chapter=kwargs.get("previous_chapter")
        )
        
        # 如果审查未通过，要求重新策划
        if not review_result.passed:
            logger.warning(
                f"Chapter {chapter_number} plan review failed: "
                f"score={review_result.overall_score:.1f}"
            )
            
            # 根据建议修正策划
            chapter_plan = await self._fix_chapter_plan(
                original_plan=chapter_plan,
                review_result=review_result
            )
        
        # ========== 步骤 4：生成阶段 ==========
        writing_result = await self._generate_chapter_content(
            chapter_plan=chapter_plan,
            prep_result=prep_result,
            **kwargs
        )
        
        # ========== 步骤 5：验证阶段 ==========
        # （可选）生成后的最终验证
        
        logger.info(f"Enhanced writing phase completed for chapter {chapter_number}")
        
        return {
            **writing_result,
            "chapter_plan": chapter_plan,
            "continuity_review": review_result.to_dict(),
            "preparation": {
                "context_tokens": prep_result["enhanced_context"].estimate_tokens(),
                "outline_task": prep_result["outline_task"].to_prompt()
            }
        }
    
    async def _prepare_chapter_generation(
        self,
        chapter_number: int,
        volume_number: int = 1,
        **kwargs
    ) -> Dict[str, Any]:
        """
        准备章节生成：构建增强的上下文
        
        整合：
        - EnhancedContextManager
        - ChapterOutlineMapper
        - ThemeGuardian
        - ForeshadowingAutoInjector
        """
        # 从 kwargs 中提取数据
        chapter_summaries = kwargs.get("chapter_summaries", {})
        chapter_contents = kwargs.get("chapter_contents", {})
        conflicts = kwargs.get("conflicts", [])
        
        # 调用集成模块
        prep_result = await self.continuity_module.prepare_chapter_generation(
            chapter_number=chapter_number,
            volume_number=volume_number,
            chapter_summaries=chapter_summaries,
            chapter_contents=chapter_contents,
            conflicts=conflicts
        )
        
        return prep_result
    
    async def _run_enhanced_planning(
        self,
        chapter_number: int,
        prep_result: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        运行增强的章节策划
        
        在原有策划流程基础上，添加：
        - 大纲任务约束
        - 主题指导
        - 伏笔要求
        - 角色一致性要求
        """
        # 构建增强的策划提示词
        enhanced_prompt = self._build_enhanced_planner_prompt(
            prep_result=prep_result,
            **kwargs
        )
        
        # 调用原有的策划流程（简化示例）
        chapter_plan = await self._call_chapter_planner(enhanced_prompt)
        
        return chapter_plan
    
    def _build_enhanced_planner_prompt(
        self,
        prep_result: Dict[str, Any],
        **kwargs
    ) -> str:
        """
        构建增强的策划提示词
        
        整合所有连贯性要求
        """
        parts = []
        
        # 1. 基础信息（原有的）
        base_info = kwargs.get("base_prompt", "")
        parts.append(base_info)
        
        # 2. 增强的上下文（新增）
        parts.append("\n\n【剧情上下文】")
        parts.append(prep_result["context_prompt"])
        
        # 3. 大纲任务（新增）
        parts.append("\n\n【本章大纲任务】")
        parts.append(prep_result["outline_task_prompt"])
        
        # 4. 主题指导（新增）
        parts.append("\n\n【主题指导】")
        parts.append(prep_result["theme_guidance"])
        
        # 5. 伏笔要求（新增）
        parts.append("\n\n【伏笔要求】")
        parts.append(prep_result["foreshadowing_requirements"])
        
        # 6. 角色一致性要求（新增）
        if prep_result.get("character_consistency_requirements"):
            parts.append("\n\n【角色一致性要求】")
            parts.append(prep_result["character_consistency_requirements"])
        
        # 7. 创作要求总结
        parts.append("\n\n【创作要求总结】")
        parts.append("""
请根据以上所有要求，策划本章内容：

1. **必须完成**大纲任务中列出的事件
2. **必须回收**伏笔要求中标记为"必须回收"的伏笔
3. **必须符合**主题指导中的要求
4. **必须保持**角色行为一致性
5. **必须回应**上一章的结尾状态

请确保本章既推进剧情，又保持连贯性！
""")
        
        return "\n".join(parts)
    
    async def _call_chapter_planner(self, prompt: str) -> Dict[str, Any]:
        """
        调用章节策划师（简化示例）
        
        实际应该调用 LLM 生成策划
        """
        # 这里简化为返回示例策划
        chapter_plan = {
            "main_events": ["示例事件"],
            "character_actions": [],
            "plot_points": []
        }
        
        return chapter_plan
    
    async def _fix_chapter_plan(
        self,
        original_plan: Dict[str, Any],
        review_result: ContinuityIntegrationResult
    ) -> Dict[str, Any]:
        """
        根据审查结果修正策划
        
        Args:
            original_plan: 原策划
            review_result: 审查结果
        
        Returns:
            修正后的策划
        """
        fixed_plan = original_plan.copy()
        
        # 1. 添加缺失的约束回应
        if review_result.issues:
            if "constraint_responses" not in fixed_plan:
                fixed_plan["constraint_responses"] = []
            
            for issue in review_result.issues:
                fixed_plan["constraint_responses"].append({
                    "issue": issue,
                    "response": f"在本章中回应{issue.get('description', '')}"
                })
        
        # 2. 添加建议的剧情推进
        if review_result.suggestions:
            if "additional_events" not in fixed_plan:
                fixed_plan["additional_events"] = []
            
            for suggestion in review_result.suggestions[:3]:  # 最多添加 3 个
                fixed_plan["additional_events"].append({
                    "type": "suggestion",
                    "description": suggestion
                })
        
        return fixed_plan
    
    async def _generate_chapter_content(
        self,
        chapter_plan: Dict[str, Any],
        prep_result: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成章节内容
        
        使用增强的提示词（包含所有连贯性要求）
        """
        # 构建生成提示词
        generation_prompt = self._build_generation_prompt(
            chapter_plan=chapter_plan,
            prep_result=prep_result,
            **kwargs
        )
        
        # 调用作家 Agent 生成内容（简化示例）
        chapter_content = await self._call_writer_agent(generation_prompt)
        
        return {
            "content": chapter_content,
            "word_count": len(chapter_content)
        }
    
    def _build_generation_prompt(
        self,
        chapter_plan: Dict[str, Any],
        prep_result: Dict[str, Any],
        **kwargs
    ) -> str:
        """构建生成提示词"""
        parts = []
        
        # 1. 章节策划
        parts.append("【章节策划】")
        parts.append(str(chapter_plan))
        
        # 2. 上下文
        parts.append("\n\n【剧情上下文】")
        parts.append(prep_result["context_prompt"])
        
        # 3. 创作要求
        parts.append("\n\n【创作要求】")
        parts.append("""
请根据以上策划和上下文，创作本章内容。

要求：
1. 完成策划中的所有主要事件
2. 保持与上一章的连贯性
3. 回收指定的伏笔
4. 保持角色行为一致性
5. 符合主题指导

开始创作：
""")
        
        return "\n".join(parts)
    
    async def _call_writer_agent(self, prompt: str) -> str:
        """调用作家 Agent（简化示例）"""
        return "本章内容..."


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    # 准备小说数据
    novel_data = {
        "topic_analysis": {
            "core_theme": "成长与牺牲",
            "central_question": "主角能否拯救世界？"
        },
        "plot_outline": {
            "volumes": [
                {
                    "volume_num": 1,
                    "title": "第一卷",
                    "chapters_range": [1, 10],
                    "tension_cycles": [
                        {
                            "chapters": [1, 10],
                            "suppress_events": ["被嘲笑"],
                            "release_event": "首次胜利"
                        }
                    ]
                }
            ]
        },
        "characters": [
            {
                "name": "主角",
                "core_motivation": "拯救世界",
                "personal_code": "保护弱者",
                "personality_traits": ["勇敢", "善良"]
            }
        ],
        "foreshadowings": []
    }
    
    # 创建增强版 CrewManager
    crew_manager = EnhancedCrewManager(
        novel_id="novel-001",
        novel_data=novel_data
    )
    
    # 运行写作阶段
    result = await crew_manager.run_writing_phase(
        chapter_number=3,
        volume_number=1,
        chapter_summaries={
            1: {"title": "第 1 章", "plot_progress": "..."},
            2: {"title": "第 2 章", "plot_progress": "..."}
        },
        previous_chapter={
            "ending_state": "第 2 章结尾",
            "chapter_number": 2
        }
    )
    
    # 输出结果
    print(f"章节生成完成:")
    print(f"字数：{result['word_count']}")
    print(f"连贯性评分：{result['continuity_review']['overall_score']}")
    print(f"是否通过：{result['continuity_review']['passed']}")


# 运行示例
if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
