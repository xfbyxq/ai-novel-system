"""LLM 章节摘要生成器 - 使用 LLM 生成高质量结构化摘要.

替代简单的文本截断，生成包含关键事件、角色变化、情节推进等维度的摘要。
"""

import json
from typing import Any, Dict, Optional

from core.logging_config import logger
from llm.cost_tracker import CostTracker
from llm.prompt_manager import PromptManager
from llm.qwen_client import QwenClient


class ChapterSummaryGenerator:
    """使用 LLM 生成高质量的章节摘要."""

    def __init__(self, client: QwenClient, cost_tracker: CostTracker):
        """初始化方法."""
        self.client = client
        self.cost_tracker = cost_tracker
        self.pm = PromptManager

    async def generate_summary(
        self,
        chapter_number: int,
        chapter_content: str,
        chapter_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """使用 LLM 生成结构化章节摘要.

        Args:
            chapter_number: 章节号
            chapter_content: 章节完整内容
            chapter_plan: 章节计划（可选，用于补充关键信息）

        Returns:
            结构化摘要字典
        """
        logger.info(f"[SummaryGenerator] 生成第{chapter_number}章 LLM 摘要...")

        # 截取内容（避免过长 token）
        content_for_summary = chapter_content[:6000]

        task_prompt = self.pm.format(
            self.pm.CHAPTER_SUMMARY_TASK,
            chapter_number=chapter_number,
            chapter_content=content_for_summary,
        )

        try:
            response = await self.client.chat(
                prompt=task_prompt,
                system=self.pm.CHAPTER_SUMMARY_SYSTEM,
                temperature=0.3,
                max_tokens=2048,  # 增加 max_tokens 避免 JSON 被截断
            )

            usage = response["usage"]
            self.cost_tracker.record(
                agent_name="摘要生成器",
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                cost_category="base",
            )

            # 提取 JSON（已增强容错性）
            summary = self._extract_json(response["content"])

            # 检查是否返回了空摘要（解析失败的标志）
            if not summary.get("key_events") and not summary.get("plot_progress"):
                logger.warning(
                    f"[SummaryGenerator] JSON 解析返回空摘要，使用回退方案..."
                )
                return self._fallback_summary(chapter_content, chapter_plan)

            # 确保必要字段
            summary.setdefault("key_events", [])
            summary.setdefault("character_changes", "")
            summary.setdefault("plot_progress", "")
            summary.setdefault("foreshadowing", [])
            summary.setdefault("ending_state", "")
            summary.setdefault("new_information", "")

            # 补充 ending_state（从原文结尾提取作为备份）
            if not summary["ending_state"] and chapter_content:
                summary["ending_state"] = self._extract_ending(chapter_content)

            # 如果有章节计划，合并 foreshadowing
            if chapter_plan:
                plan_foreshadowing = chapter_plan.get("foreshadowing", [])
                for f in plan_foreshadowing:
                    if f not in summary["foreshadowing"]:
                        summary["foreshadowing"].append(f)

            logger.info(
                f"[SummaryGenerator] 第{chapter_number}章摘要生成完成: "
                f"events={len(summary['key_events'])}, "
                f"foreshadowing={len(summary['foreshadowing'])}"
            )

            return summary

        except Exception as e:
            logger.error(f"[SummaryGenerator] LLM 摘要生成失败: {e}")
            return self._fallback_summary(chapter_content, chapter_plan)

    def _fallback_summary(
        self,
        content: str,
        chapter_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """回退方案：从原文截取摘要."""
        plot_progress = content[:200] if content else ""
        last_period = plot_progress.rfind("。")
        if last_period > 100:
            plot_progress = plot_progress[: last_period + 1]

        ending_state = self._extract_ending(content)

        key_events = []
        if chapter_plan:
            key_events = chapter_plan.get("plot_points", [])[:5]

        return {
            "key_events": key_events,
            "character_changes": "",
            "plot_progress": plot_progress,
            "foreshadowing": (
                chapter_plan.get("foreshadowing", []) if chapter_plan else []
            ),
            "ending_state": ending_state,
            "new_information": "",
        }

    @staticmethod
    def _extract_ending(content: str, length: int = 100) -> str:
        """从内容中提取结尾部分."""
        if not content:
            return ""
        ending = content[-length:]
        first_period = ending.find("。")
        if 0 < first_period < 50:
            ending = ending[first_period + 1 :]
        return ending.strip()

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """从 LLM 响应中提取 JSON.

        使用多层策略：
        1. 直接解析完整文本
        2. 提取 markdown 代码块中的 JSON
        3. 提取花括号内的 JSON 片段
        4. 尝试修复不完整的 JSON（添加缺失的闭合括号）
        5. 返回空字典作为最后手段

        Args:
            text: LLM 响应的原始文本

        Returns:
            解析后的字典，如全部失败则返回空字典
        """
        text = text.strip()

        # 策略 1: 直接解析完整文本
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 策略 2: 提取 markdown 代码块中的 JSON
        import re

        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 策略 3: 提取花括号内的 JSON 片段
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = text[start : end + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # 策略 4: 尝试修复不完整的 JSON
                # 计算缺失的闭合括号数量
                open_braces = json_str.count("{")
                close_braces = json_str.count("}")
                missing_braces = open_braces - close_braces

                if missing_braces > 0:
                    try:
                        # 添加缺失的闭合括号
                        fixed_json = json_str + "}" * missing_braces
                        return json.loads(fixed_json)
                    except json.JSONDecodeError:
                        # 尝试更激进的修复：移除最后一个不完整的项目
                        try:
                            # 找到最后一个逗号并截断
                            last_comma = json_str.rfind(",")
                            if last_comma > start + 1:
                                truncated = json_str[:last_comma] + "}"
                                return json.loads(truncated)
                        except json.JSONDecodeError:
                            pass

                # 策略 5: 记录警告并返回空字典
                logger.warning(f"JSON 解析失败，返回空摘要。文本片段：{text[:100]}...")

        # 全部失败，返回空字典
        return {
            "key_events": [],
            "character_changes": "",
            "plot_progress": text[:200] if text else "",
            "foreshadowing": [],
            "ending_state": "",
            "new_information": "",
        }
