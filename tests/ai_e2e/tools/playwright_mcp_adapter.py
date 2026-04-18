"""Playwright CDP 适配器 — 模拟 chrome-devtools MCP 工具行为.

使用 Playwright 的 CDP (Chrome DevTools Protocol) 连接和 accessibility API，
生成与 chrome-devtools MCP take_snapshot 兼容的 a11y 快照格式，
并通过 a11y 节点 backendDOMNodeId 实现 UID → DOM 元素的定位和操作。

快照格式与 MCP 保持一致：
    uid=0_1 WebArea "页面标题"
      uid=0_2 button "创建小说"
      uid=0_3 textbox "标题" required

用法：
    adapter = await PlaywrightMCPAdapter.create(headless=False)
    tools = adapter.as_mcp_tools()  # 返回 dict[str, Callable]
    # 注入到 MCPToolRegistry 或直接传给 MCPExecutor
"""

from __future__ import annotations

import asyncio
from typing import Any

from core.logging_config import logger


class PlaywrightMCPAdapter:
    """基于 Playwright CDP 的 chrome-devtools MCP 适配器.

    通过 Playwright 的 accessibility snapshot 和 CDP session 实现：
    - take_snapshot: 递归遍历 a11y 树，输出 uid=X_Y role "name" 格式
    - click / fill / press_key: 通过 backendDOMNodeId 定位 DOM 节点操作
    - navigate_page / wait_for / take_screenshot: 直接使用 Playwright API
    """

    def __init__(
        self,
        page: Any,
        cdp_session: Any,
        browser: Any,
        context: Any,
        playwright_instance: Any,
    ) -> None:
        self._page = page
        self._cdp = cdp_session
        self._browser = browser
        self._context = context
        self._pw = playwright_instance
        # uid → backendDOMNodeId 的映射，每次 take_snapshot 时刷新
        self._uid_to_backend_id: dict[str, int] = {}
        # 页面索引（模拟 MCP 的多页面，当前固定为 0）
        self._page_index: int = 0

    @classmethod
    async def create(
        cls,
        headless: bool = False,
        base_url: str = "http://localhost:3000",
    ) -> PlaywrightMCPAdapter:
        """创建适配器实例 — 启动 Chromium 并建立 CDP 连接.

        Args:
            headless: 是否无头模式运行
            base_url: 前端基础 URL

        Returns:
            初始化完毕的适配器实例
        """
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(base_url=base_url)
        page = await context.new_page()
        cdp = await context.new_cdp_session(page)
        # 启用 accessibility 域
        await cdp.send("Accessibility.enable")

        logger.info(f"PlaywrightMCPAdapter 已创建 (headless={headless}, base_url={base_url})")
        return cls(
            page=page,
            cdp_session=cdp,
            browser=browser,
            context=context,
            playwright_instance=pw,
        )

    async def close(self) -> None:
        """关闭浏览器和 Playwright 实例."""
        try:
            await self._browser.close()
            await self._pw.stop()
        except Exception as e:
            logger.warning(f"关闭适配器时出错: {e}")

    # ---------------------------------------------------------------
    # MCP 工具实现
    # ---------------------------------------------------------------

    async def navigate_page(self, **kwargs: Any) -> str:
        """导航到指定 URL — 对应 MCP navigate_page."""
        nav_type = kwargs.get("type", "url")
        url = kwargs.get("url", "")

        if nav_type == "url" and url:
            await self._page.goto(url, wait_until="domcontentloaded")
        elif nav_type == "back":
            await self._page.go_back()
        elif nav_type == "forward":
            await self._page.go_forward()
        elif nav_type == "reload":
            await self._page.reload()

        return f"已导航到: {self._page.url}"

    async def click(self, **kwargs: Any) -> str:
        """点击指定 UID 的元素 — 对应 MCP click."""
        uid = kwargs.get("uid", "")
        backend_id = self._uid_to_backend_id.get(uid)

        if backend_id is None:
            raise ValueError(f"UID {uid} 不在当前快照映射中，请先调用 take_snapshot")

        # 通过 CDP 将 backendDOMNodeId 解析为 JS 对象并点击
        await self._click_by_backend_id(backend_id)
        await asyncio.sleep(0.3)
        return f"已点击 uid={uid}"

    async def fill(self, **kwargs: Any) -> str:
        """填充指定 UID 的输入框 — 对应 MCP fill."""
        uid = kwargs.get("uid", "")
        value = kwargs.get("value", "")
        backend_id = self._uid_to_backend_id.get(uid)

        if backend_id is None:
            raise ValueError(f"UID {uid} 不在当前快照映射中")

        # 先聚焦再输入
        await self._focus_by_backend_id(backend_id)
        await asyncio.sleep(0.1)
        # 清空已有内容
        await self._page.keyboard.press("Control+a")
        await self._page.keyboard.press("Backspace")
        await self._page.keyboard.type(value, delay=30)
        return f"已填充 uid={uid}: {value}"

    async def press_key(self, **kwargs: Any) -> str:
        """按键 — 对应 MCP press_key."""
        key = kwargs.get("key", "")
        await self._page.keyboard.press(key)
        return f"已按键: {key}"

    async def wait_for(self, **kwargs: Any) -> str:
        """等待文本出现 — 对应 MCP wait_for."""
        texts = kwargs.get("text", [])
        timeout = kwargs.get("timeout", 10000)

        if isinstance(texts, str):
            texts = [texts]

        for text in texts:
            await self._page.wait_for_selector(f"text={text}", timeout=timeout, state="visible")
        return f"文本已出现: {texts}"

    async def take_snapshot(self, **kwargs: Any) -> str:
        """获取 a11y 快照 — 输出与 chrome-devtools MCP 兼容的格式."""
        # 清空旧映射
        self._uid_to_backend_id.clear()

        # 通过 CDP 获取完整 a11y 树（包含 backendDOMNodeId）
        result = await self._cdp.send("Accessibility.getFullAXTree")
        nodes = result.get("nodes", [])

        # 构建 nodeId → node 的映射
        node_map: dict[str, dict] = {}
        for node in nodes:
            node_map[node["nodeId"]] = node

        # 找到根节点（parentId 为空的节点）
        root_nodes = [n for n in nodes if "parentId" not in n]

        # 递归构建快照文本
        lines: list[str] = []
        uid_counter = [0]

        def _walk(node: dict, depth: int) -> None:
            role_value = node.get("role", {}).get("value", "")
            name_value = node.get("name", {}).get("value", "")

            # 跳过 none/ignored 角色
            if role_value in ("none", "ignored", "InlineTextBox", ""):
                for child_id in node.get("childIds", []):
                    if child_id in node_map:
                        _walk(node_map[child_id], depth)
                return

            # 生成 UID
            uid = f"{self._page_index}_{uid_counter[0]}"
            uid_counter[0] += 1

            # 记录 UID → backendDOMNodeId 映射
            backend_id = node.get("backendDOMNodeId")
            if backend_id:
                self._uid_to_backend_id[uid] = backend_id

            # 构建属性列表
            attrs: list[str] = []
            properties = node.get("properties", [])
            for prop in properties:
                prop_name = prop.get("name", "")
                prop_val = prop.get("value", {}).get("value")
                if prop_name == "disabled" and prop_val:
                    attrs.append("disabled")
                elif prop_name == "required" and prop_val:
                    attrs.append("required")
                elif prop_name == "focused" and prop_val:
                    attrs.append("focused")

            # 格式化输出行
            indent = "  " * depth
            name_part = f' "{name_value}"' if name_value else ""
            attrs_part = f" {' '.join(attrs)}" if attrs else ""
            lines.append(f"{indent}uid={uid} {role_value}{name_part}{attrs_part}")

            # 递归子节点
            for child_id in node.get("childIds", []):
                if child_id in node_map:
                    _walk(node_map[child_id], depth + 1)

        for root in root_nodes:
            _walk(root, 0)

        snapshot_text = "\n".join(lines)
        logger.debug(f"快照生成: {len(lines)} 个节点, {len(self._uid_to_backend_id)} 个可操作")
        return snapshot_text

    async def take_screenshot(self, **kwargs: Any) -> str:
        """截图 — 对应 MCP take_screenshot."""
        path = kwargs.get("path", "screenshot.png")
        await self._page.screenshot(path=path)
        return f"截图已保存: {path}"

    # ---------------------------------------------------------------
    # CDP 辅助方法
    # ---------------------------------------------------------------

    async def _click_by_backend_id(self, backend_id: int) -> None:
        """通过 backendDOMNodeId 点击元素."""
        # 将 backendDOMNodeId 解析为 remoteObject
        result = await self._cdp.send("DOM.resolveNode", {"backendNodeId": backend_id})
        object_id = result["object"]["objectId"]

        # 使用 Runtime.callFunctionOn 在元素上执行 click
        await self._cdp.send(
            "Runtime.callFunctionOn",
            {
                "objectId": object_id,
                "functionDeclaration": """function() {
                    this.scrollIntoViewIfNeeded();
                    this.click();
                }""",
                "awaitPromise": False,
            },
        )

    async def _focus_by_backend_id(self, backend_id: int) -> None:
        """通过 backendDOMNodeId 聚焦元素."""
        result = await self._cdp.send("DOM.resolveNode", {"backendNodeId": backend_id})
        object_id = result["object"]["objectId"]

        await self._cdp.send(
            "Runtime.callFunctionOn",
            {
                "objectId": object_id,
                "functionDeclaration": """function() {
                    this.scrollIntoViewIfNeeded();
                    this.focus();
                }""",
                "awaitPromise": False,
            },
        )

    # ---------------------------------------------------------------
    # 工具导出
    # ---------------------------------------------------------------

    def as_mcp_tools(self) -> dict[str, Any]:
        """将适配器方法导出为 MCPExecutor 期望的 callable 字典.

        Returns:
            符合 mcp_tools fixture 契约的工具字典
        """
        return {
            "navigate": self.navigate_page,
            "click": self.click,
            "fill": self.fill,
            "press_key": self.press_key,
            "wait_for": self.wait_for,
            "take_snapshot": self.take_snapshot,
            "take_screenshot": self.take_screenshot,
        }
