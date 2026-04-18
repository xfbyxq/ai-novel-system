"""LLM 自愈器 — SnapshotResolver 匹配失败时，用 LLM 从快照中定位目标元素 UID."""

from __future__ import annotations

import json

from core.logging_config import logger
from llm.qwen_client import QwenClient
from tests.ai_e2e.schemas.test_case_schema import ElementRef

# LLM 自愈使用的 system prompt
_SYSTEM_PROMPT = """你是一个精通 Web 无障碍（a11y）树和 Ant Design 组件结构的前端测试专家。

你的任务是：根据用户给出的目标元素描述和当前页面的 a11y 快照，找到目标元素对应的 UID。

a11y 快照格式说明：
- 每行格式: uid=<UID> <role> "<name>" [属性...]
- role: 元素的无障碍角色（button, textbox, combobox, menuitem, heading 等）
- name: 元素的可访问名称
- 属性: 如 disabled, focused, required, expandable 等

请严格按 JSON 格式返回，不要包含其他内容：
{"uid": "找到的UID", "reason": "简要说明匹配理由"}

如果确实无法找到目标元素，返回：
{"uid": null, "reason": "说明为什么找不到"}"""


class SelfHealer:
    """SnapshotResolver 匹配失败时，利用 LLM 从 a11y 快照找到正确的 UID.

    LLM 可以理解上下文语义（如"类型下拉框"可能在快照中显示为
    `combobox "* 类型"`），比纯字符串匹配更灵活。
    """

    def __init__(self, qwen_client: QwenClient, temperature: float = 0.1):
        """初始化自愈器.

        Args:
            qwen_client: LLM 客户端实例
            temperature: LLM 温度参数，自愈场景用低温度保证确定性
        """
        self.client = qwen_client
        self.temperature = temperature
        self._total_tokens: int = 0

    @property
    def total_tokens_used(self) -> int:
        """累计消耗的 token 数."""
        return self._total_tokens

    async def find_element_uid(
        self,
        element: ElementRef,
        step_description: str,
        page_snapshot: str,
    ) -> str | None:
        """调用 LLM 从快照中定位目标元素的 UID.

        Args:
            element: 目标元素的语义引用
            step_description: 步骤的自然语言描述（提供操作上下文）
            page_snapshot: 当前页面的 a11y 快照文本

        Returns:
            匹配的 UID 字符串，或 None（无法定位）
        """
        # 构建 user prompt
        role_info = f"角色(role): {element.role}" if element.role else "角色: 未指定"
        user_prompt = (
            f"目标元素：\n"
            f"  名称(name): {element.name}\n"
            f"  {role_info}\n"
            f"  操作目的: {step_description}\n\n"
            f"当前页面 a11y 快照：\n{page_snapshot}"
        )

        try:
            result = await self.client.chat(
                prompt=user_prompt,
                system=_SYSTEM_PROMPT,
                temperature=self.temperature,
                max_tokens=256,
            )
            content = result.get("content", "")
            usage = result.get("usage", {})
            self._total_tokens += usage.get("total_tokens", 0)

            # 解析 LLM 返回的 JSON
            parsed = json.loads(content)
            uid = parsed.get("uid")
            reason = parsed.get("reason", "")

            if uid:
                logger.info(f"自愈成功: {element.name} → uid={uid} ({reason})")
                return str(uid)

            logger.info(f"自愈未找到元素: {element.name} ({reason})")
            return None

        except json.JSONDecodeError:
            logger.warning(f"自愈 LLM 返回非 JSON 格式: {content[:200]}")
            return None
        except Exception as e:
            logger.error(f"自愈调用 LLM 失败: {e}")
            return None
