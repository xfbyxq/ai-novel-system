"""章节数据处理器 - 处理章节数据提取和格式化."""

from typing import Any


class ChapterDataProcessor:
    """章节数据处理器，负责从章节内容提取结构化数据."""

    def extract_chapter_summary(
        self, content: str, chapter_plan: dict, chapter_number: int
    ) -> dict:
        """从章节内容提取结构化摘要.

        保留完整内容，不再进行固定截取。
        情节摘要和结尾状态保留完整文本，由上下文压缩器统一处理。

        Args:
            content: 章节完整内容
            chapter_plan: 章节大纲（包含plot_points, foreshadowing等）
            chapter_number: 章节号

        Returns:
            结构化摘要字典
        """
        # 保留完整情节摘要（由压缩器统一处理）
        plot_progress = content if content else ""

        # 保留完整结尾状态（由压缩器统一处理）
        ending_state = ""
        if content:
            # 取最后800字作为结尾段落（增加内容保留）
            ending_length = min(800, len(content))
            ending_state = content[-ending_length:]
            # 尝试从句子开头开始
            first_period = ending_state.find("。")
            if 0 < first_period < 150:
                ending_state = ending_state[first_period + 1 :]

        return {
            "chapter_number": chapter_number,
            "title": chapter_plan.get("title", f"第{chapter_number}章"),
            "key_events": chapter_plan.get("plot_points", []),  # 保留完整事件列表
            "character_changes": self.extract_character_mentions(content),  # 角色变化
            "plot_progress": plot_progress,  # 完整情节摘要
            "foreshadowing": chapter_plan.get("foreshadowing", []),  # 伏笔
            "ending_state": ending_state,  # 完整结尾状态
        }

    def format_character_states(self, states_dict: dict) -> str:
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

    def extract_character_mentions(self, content: str) -> str:
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


# 模块级单例，方便直接使用
_chapter_data_processor: ChapterDataProcessor | None = None


def get_chapter_data_processor() -> ChapterDataProcessor:
    """获取章节数据处理器单例."""
    global _chapter_data_processor
    if _chapter_data_processor is None:
        _chapter_data_processor = ChapterDataProcessor()
    return _chapter_data_processor
