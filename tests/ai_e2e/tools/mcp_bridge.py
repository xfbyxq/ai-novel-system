"""MCP chrome-devtools 工具桥接层.

将 MCP chrome-devtools server 的工具函数封装为统一的 callable 接口，
供 MCPExecutor 通过依赖注入使用。

在 Qoder 环境中，MCP 工具通过 LoadMcp 加载后以全局函数形式可用。
本模块提供 get_mcp_tools() 函数，返回所有必要工具的 callable 字典。

非 Qoder 环境（如 CI）中，可通过 MockMCPTools 提供 mock 实现。
"""

from __future__ import annotations

from typing import Any


async def _noop(**kwargs: Any) -> str:
    """默认空操作 — 用于未注入工具时的占位."""
    return f"[noop] kwargs={kwargs}"


class MCPToolRegistry:
    """MCP 工具注册表 — 支持运行时注入工具函数.

    使用方式：
    1. 创建实例
    2. 通过 register() 注入 MCP 工具 callable
    3. 通过 get_tools() 获取工具字典供 MCPExecutor 使用
    """

    def __init__(self) -> None:
        self._tools: dict[str, Any] = {
            "navigate": _noop,
            "click": _noop,
            "fill": _noop,
            "press_key": _noop,
            "wait_for": _noop,
            "take_snapshot": _noop,
            "take_screenshot": _noop,
        }

    def register(self, name: str, func: Any) -> None:
        """注册单个 MCP 工具函数.

        Args:
            name: 工具名称（navigate / click / fill / press_key /
                  wait_for / take_snapshot / take_screenshot）
            func: 对应的 async callable
        """
        if name not in self._tools:
            raise ValueError(f"未知的 MCP 工具名称: {name}，可选: {list(self._tools.keys())}")
        self._tools[name] = func

    def register_all(self, tools: dict[str, Any]) -> None:
        """批量注册 MCP 工具函数.

        Args:
            tools: 工具名称到 callable 的映射字典
        """
        for name, func in tools.items():
            self.register(name, func)

    def get_tools(self) -> dict[str, Any]:
        """获取所有已注册的工具函数字典.

        Returns:
            工具名称到 callable 的映射
        """
        return dict(self._tools)


# 全局注册表实例
_registry = MCPToolRegistry()


def get_mcp_tools() -> dict[str, Any]:
    """获取 MCP 工具函数字典.

    Returns:
        包含所有 MCP chrome-devtools 工具 callable 的字典

    Raises:
        ImportError: MCP 工具不可用时抛出
    """
    # 检查是否有工具已被注入（非 noop）
    tools = _registry.get_tools()
    has_real_tools = any(func is not _noop for func in tools.values())
    if not has_real_tools:
        raise ImportError(
            "MCP chrome-devtools 工具尚未注入。"
            "请在 Qoder 环境中通过 MCPToolRegistry.register_all() 注入工具，"
            "或在 CI 环境中使用 MockMCPTools。"
        )
    return tools


def get_registry() -> MCPToolRegistry:
    """获取全局 MCP 工具注册表实例."""
    return _registry
