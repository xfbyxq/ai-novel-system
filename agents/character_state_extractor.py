"""角色状态提取器 - 从章节内容中自动提取角色状态变化.

补充 LLM 返回的 character_updates，确保角色状态始终更新。
"""

import json
import re
from typing import Any, Dict, List, Optional

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient


class CharacterStateExtractor:
    """从章节内容中自动提取角色状态变化."""

    def __init__(self, client: QwenClient, cost_tracker: CostTracker):
        """初始化方法.

        Args:
            client: LLM 客户端
            cost_tracker: 成本跟踪器
        """
        self.client = client
        self.cost_tracker = cost_tracker

    async def extract_from_chapter(
        self,
        chapter_number: int,
        chapter_content: str,
        known_characters: List[str],
        existing_states: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """从章节内容中提取角色状态.

        Args:
            chapter_number: 章节号
            chapter_content: 章节完整内容
            known_characters: 已知角色列表
            existing_states: 当前角色状态（用于增量更新）

        Returns:
            {角色名: {emotional_state, current_location, relationships_changed, status_summary}}
        """
        # 找出章节中实际出场的角色
        appearing_chars = self._find_appearing_characters(chapter_content, known_characters)
        if not appearing_chars:
            logger.debug(f"[CharExtractor] 第{chapter_number}章未检测到已知角色出场")
            return {}

        logger.info(
            f"[CharExtractor] 第{chapter_number}章检测到 {len(appearing_chars)} 个出场角色: "
            f"{appearing_chars}"
        )

        # 截取内容（避免 token 过多）
        content_excerpt = chapter_content[:6000]

        # 构建已知状态信息
        existing_info = ""
        if existing_states:
            existing_lines = []
            for char_name in appearing_chars:
                if char_name in existing_states:
                    state = existing_states[char_name]
                    existing_lines.append(
                        f"- {char_name}: "
                        f"情感={state.get('emotional_state', '未知')}, "
                        f"位置={state.get('current_location', '未知')}"
                    )
            if existing_lines:
                existing_info = "\n之前状态：\n" + "\n".join(existing_lines)

        prompt = (
            f"请分析以下章节内容，提取出场角色的当前状态。\n\n"
            f"出场角色：{', '.join(appearing_chars)}\n"
            f"{existing_info}\n\n"
            f"章节内容（节选）：\n{content_excerpt}\n\n"
            f"请为每个出场角色输出以下信息（JSON格式）：\n"
            f"{{\n"
            f'  "角色名": {{\n'
            f'    "emotional_state": "情感状态（如：愤怒、平静、悲伤、坚定）",\n'
            f'    "current_location": "当前位置",\n'
            f'    "relationships_changed": {{"其他角色名": "关系变化描述"}},\n'
            f'    "status_summary": "角色在本章的状态总结（50字以内）"\n'
            f"  }}\n"
            f"}}\n\n"
            f"请直接输出JSON，不要有其他文字："
        )

        try:
            response = await self.client.chat(
                prompt=prompt,
                system="你是小说分析助手，擅长从文本中提取角色状态信息。请严格输出JSON格式。",
                temperature=0.3,
                max_tokens=2048,
            )

            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="角色状态提取",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                cost_category="base",
            )

            # 提取 JSON
            states = self._extract_json(response["content"])

            if states:
                logger.info(f"[CharExtractor] 成功提取 {len(states)} 个角色状态")
                return states
            else:
                logger.warning("[CharExtractor] 提取返回空结果")
                return {}

        except Exception as e:
            logger.error(f"[CharExtractor] 提取失败: {e}")
            return {}

    def _find_appearing_characters(
        self, content: str, known_characters: List[str]
    ) -> List[str]:
        """从内容中找出已知角色的出现情况."""
        appearing = []
        for char_name in known_characters:
            # 使用正则匹配角色名称，避免部分匹配
            pattern = re.escape(char_name)
            if re.search(pattern, content):
                appearing.append(char_name)
        return appearing

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """从 LLM 响应中提取 JSON."""
        text = text.strip()

        # 策略 1: 直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 策略 2: 提取 markdown 代码块
        import re as re_mod

        match = re_mod.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 策略 3: 提取花括号内的内容
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

        logger.warning(f"[CharExtractor] JSON 提取失败，文本: {text[:100]}...")
        return {}
