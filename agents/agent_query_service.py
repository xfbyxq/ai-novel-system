"""Agent 请求-应答协商服务 - 写作过程中 Agent 间的设定确认."""

import json
from typing import Any, Dict, Optional

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient

QUERY_HANDLER_PROMPT = """你是{target_role}，收到来自{requester}的查询请求。

查询问题：
{question}

你的知识库：
{knowledge_base}

请根据知识库中的信息，简洁准确地回答查询。
回答不超过200字，直接输出回答文本，不要输出JSON。"""


class AgentQueryService:
    """Agent 间请求-应答协商服务。

    在 CrewManager 串行流程中模拟 Agent 间的查询交互：
    Writer 遇到设定疑问时，可通过标记触发查询，
    由本服务以对应 Agent 角色的视角调用 LLM 回答。
    """

    # 支持的查询目标及其角色描述
    ROLE_MAP = {
        "world": (
            "世界观架构师",
            "你精通小说世界观体系，包括力量体系、地理、势力和历史设定。",
        ),
        "character": ("角色设计师", "你精通角色设定，包括性格、背景、能力和人物关系。"),
        "plot": ("情节架构师", "你精通情节规划，包括主线支线、伏笔和转折设计。"),
    }

    def __init__(self, client: QwenClient, cost_tracker: CostTracker):
        self.client = client
        self.cost_tracker = cost_tracker

    async def query(
        self,
        requester: str,
        target_type: str,
        question: str,
        knowledge_base: str,
        chapter_number: int = 0,
    ) -> str:
        """发起一次跨 Agent 查询。

        Args:
            requester: 发起查询的 Agent 名称（如 "作家"）
            target_type: 查询目标类型（"world" / "character" / "plot"）
            question: 查询问题
            knowledge_base: 对应的设定数据（JSON 字符串或纯文本）
            chapter_number: 章节号（用于成本追踪）

        Returns:
            回答文本
        """
        role_name, role_desc = self.ROLE_MAP.get(
            target_type, ("专家", "你是领域专家。")
        )

        prompt = QUERY_HANDLER_PROMPT.format(
            target_role=role_name,
            requester=requester,
            question=question,
            knowledge_base=knowledge_base[:4000],  # 截断控制 token
        )

        try:
            response = await self.client.chat(
                prompt=prompt,
                system=f"你是{role_name}。{role_desc}",
                temperature=0.3,
                max_tokens=512,
            )
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name=f"查询-{role_name}",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                chapter_number=chapter_number,
                cost_category="query",
            )
            answer = response["content"].strip()
            logger.info(
                f"[AgentQuery] {requester} -> {role_name}: "
                f"Q={question[:50]}... A={answer[:80]}..."
            )
            return answer

        except Exception as e:
            logger.error(f"[AgentQuery] 查询失败: {e}")
            return f"（查询失败：{e}）"

    @staticmethod
    def parse_query_tags(text: str) -> list[dict[str, str]]:
        """从文本中解析 [QUERY:type]question[/QUERY] 标记。

        Returns:
            列表，每项包含 {"type": "world/character/plot", "question": "问题内容"}
        """
        import re

        pattern = r"\[QUERY:(\w+)\](.*?)\[/QUERY\]"
        matches = re.findall(pattern, text, re.DOTALL)
        return [
            {"type": m[0].strip(), "question": m[1].strip()}
            for m in matches
            if m[1].strip()
        ]

    @staticmethod
    def remove_query_tags(text: str) -> str:
        """移除文本中的 [QUERY] 标记."""
        import re

        return re.sub(r"\[QUERY:\w+\].*?\[/QUERY\]", "", text, flags=re.DOTALL).strip()
