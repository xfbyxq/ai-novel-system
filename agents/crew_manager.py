"""CrewAI 风格的小说生成 Crew 管理器

采用直接编排模式，通过 QwenClient 调用通义千问模型，
而非使用 CrewAI 的内置 LLM 集成。
"""

import json
import logging
import re
from typing import Any

from llm.cost_tracker import CostTracker
from llm.prompt_manager import PromptManager
from llm.qwen_client import QwenClient

logger = logging.getLogger(__name__)


class NovelCrewManager:
    """小说生成 Crew 管理器
    
    负责协调企划阶段和写作阶段的所有 Agent,
    通过直接调用 QwenClient 实现 Agent 间的数据传递和任务编排。
    """

    def __init__(self, qwen_client: QwenClient, cost_tracker: CostTracker):
        """初始化 Crew 管理器
        
        Args:
            qwen_client: 通义千问客户端实例
            cost_tracker: 成本跟踪器实例
        """
        self.client = qwen_client
        self.cost_tracker = cost_tracker
        self.pm = PromptManager

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

    def _call_agent(
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
            response = self.client.chat(
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

    def run_planning_phase(
        self,
        genre: str | None = None,
        tags: list[str] | None = None,
        context: str = "",
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

        topic_task = self.pm.format(
            self.pm.TOPIC_ANALYST_TASK,
            context=topic_context,
        )
        
        topic_analysis = self._call_agent(
            agent_name="主题分析师",
            system_prompt=self.pm.TOPIC_ANALYST_SYSTEM,
            task_prompt=topic_task,
            temperature=0.8,
            expect_json=True,
        )

        # 2. 世界观构建
        world_task = self.pm.format(
            self.pm.WORLD_BUILDER_TASK,
            topic_analysis=json.dumps(topic_analysis, ensure_ascii=False, indent=2),
        )
        
        world_setting = self._call_agent(
            agent_name="世界观架构师",
            system_prompt=self.pm.WORLD_BUILDER_SYSTEM,
            task_prompt=world_task,
            temperature=0.7,
            max_tokens=6000,
            expect_json=True,
        )

        # 3. 角色设计
        character_task = self.pm.format(
            self.pm.CHARACTER_DESIGNER_TASK,
            topic_analysis=json.dumps(topic_analysis, ensure_ascii=False, indent=2),
            world_setting=json.dumps(world_setting, ensure_ascii=False, indent=2),
        )
        
        characters = self._call_agent(
            agent_name="角色设计师",
            system_prompt=self.pm.CHARACTER_DESIGNER_SYSTEM,
            task_prompt=character_task,
            temperature=0.8,
            max_tokens=6000,
            expect_json=True,
        )

        # 4. 情节架构
        plot_task = self.pm.format(
            self.pm.PLOT_ARCHITECT_TASK,
            world_setting=json.dumps(world_setting, ensure_ascii=False, indent=2),
            characters=json.dumps(characters, ensure_ascii=False, indent=2),
        )
        
        plot_outline = self._call_agent(
            agent_name="情节架构师",
            system_prompt=self.pm.PLOT_ARCHITECT_SYSTEM,
            task_prompt=plot_task,
            temperature=0.7,
            max_tokens=6000,
            expect_json=True,
        )

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

    def run_writing_phase(
        self,
        novel_data: dict[str, Any],
        chapter_number: int,
        volume_number: int = 1,
        previous_chapters_summary: str = "",
        character_states: str = "",
        writing_style: str = "modern",
    ) -> dict[str, Any]:
        """执行单章写作阶段
        
        顺序执行以下步骤：
        1. 章节策划师：制定章节计划
        2. 作家：撰写章节初稿
        3. 编辑：润色和优化文本
        4. 连续性审查员：检查一致性和质量
        
        Args:
            novel_data: 小说数据（包含 world_setting, characters, plot_outline 等）
            chapter_number: 章节号
            volume_number: 卷号
            previous_chapters_summary: 前几章摘要
            character_states: 当前角色状态
            
        Returns:
            包含以下键的字典：
            - chapter_plan: 章节计划
            - draft: 初稿
            - edited_content: 编辑后内容
            - final_content: 最终内容（与 edited_content 相同）
            - continuity_report: 连续性检查报告
            - quality_score: 质量评分
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

        # 从大纲中找到当前章节所属的卷
        volumes = plot_outline.get("volumes", [])
        current_volume = None
        for vol in volumes:
            if vol.get("volume_num") == volume_number:
                current_volume = vol
                break
        
        plot_context = ""
        if current_volume:
            plot_context = f"""
当前卷：第 {volume_number} 卷 - {current_volume.get('title', '')}
卷概要：{current_volume.get('summary', '')}
关键事件：{', '.join(current_volume.get('key_events', []))}
"""
        else:
            plot_context = json.dumps(plot_outline, ensure_ascii=False, indent=2)

        # 1. 章节策划
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
        
        chapter_plan = self._call_agent(
            agent_name="章节策划师",
            system_prompt=self.pm.CHAPTER_PLANNER_SYSTEM,
            task_prompt=planner_task,
            temperature=0.7,
            expect_json=True,
        )

        # 2. 撰写初稿
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

        writer_task = self.pm.format(
            self.pm.WRITER_TASK,
            chapter_number=chapter_number,
            chapter_plan=json.dumps(chapter_plan, ensure_ascii=False, indent=2),
            world_setting_brief=world_brief,
            character_info=character_info or "（主要角色）",
            previous_ending=previous_chapters_summary[-200:] if previous_chapters_summary else "（本章为开篇）",
            chapter_title=chapter_plan.get("title", ""),
        )
        
        writer_system = self.pm.format(
            self.pm.WRITER_SYSTEM,
            genre=genre,
        )
        
        draft = self._call_agent(
            agent_name="作家",
            system_prompt=writer_system,
            task_prompt=writer_task,
            temperature=0.85,
            max_tokens=4096,
            expect_json=False,  # 返回纯文本
        )

        # 3. 编辑润色
        editor_task = self.pm.format(
            self.pm.EDITOR_TASK,
            draft_content=draft,
            chapter_number=chapter_number,
            chapter_title=chapter_plan.get("title", ""),
            chapter_summary=chapter_plan.get("summary", ""),
        )
        
        edited_content = self._call_agent(
            agent_name="编辑",
            system_prompt=self.pm.EDITOR_SYSTEM,
            task_prompt=editor_task,
            temperature=0.6,
            max_tokens=4096,
            expect_json=False,
        )

        # 4. 连续性检查
        continuity_task = self.pm.format(
            self.pm.CONTINUITY_CHECKER_TASK,
            current_chapter=edited_content,
            world_setting_brief=world_brief,
            character_info=character_info or "（主要角色）",
            previous_key_info=previous_chapters_summary or "（本章为第一章）",
        )
        
        continuity_report = self._call_agent(
            agent_name="连续性审查员",
            system_prompt=self.pm.CONTINUITY_CHECKER_SYSTEM,
            task_prompt=continuity_task,
            temperature=0.5,
            expect_json=True,
        )

        logger.info("=" * 60)
        logger.info(f"🎉 第 {chapter_number} 章写作完成！")
        logger.info(f"   质量评分：{continuity_report.get('quality_score', 'N/A')}")
        logger.info(f"   发现问题：{len(continuity_report.get('issues', []))} 个")
        logger.info("=" * 60)

        return {
            "chapter_plan": chapter_plan,
            "draft": draft,
            "edited_content": edited_content,
            "final_content": edited_content,  # 最终内容即编辑后内容
            "continuity_report": continuity_report,
            "quality_score": continuity_report.get("quality_score", 0),
        }
