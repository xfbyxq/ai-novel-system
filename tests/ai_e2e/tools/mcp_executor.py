"""MCP 执行器 — 将 TestStep 通过快照 UID 解析后调用 chrome-devtools MCP 工具.

核心流程：
1. take_snapshot 获取当前 a11y 快照
2. SnapshotResolver 将 ElementRef → UID
3. 调用对应 MCP 工具（click/fill/navigate 等）
4. 失败时触发 SelfHealer 自愈
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from core.logging_config import logger
from tests.ai_e2e.schemas.test_case_schema import StepResult, TestStep
from tests.ai_e2e.tools.snapshot_resolver import SnapshotResolver

if TYPE_CHECKING:
    from tests.ai_e2e.agents.self_healer import SelfHealer


class MCPExecutor:
    """将 TestStep 通过 a11y 快照 UID 解析后，调用 MCP chrome-devtools 工具执行.

    MCP 工具通过注入的 callable 调用（由 conftest.py 提供），
    避免直接依赖 MCP 框架，便于测试和解耦。
    """

    def __init__(
        self,
        mcp_navigate: Callable[..., Coroutine[Any, Any, Any]],
        mcp_click: Callable[..., Coroutine[Any, Any, Any]],
        mcp_fill: Callable[..., Coroutine[Any, Any, Any]],
        mcp_press_key: Callable[..., Coroutine[Any, Any, Any]],
        mcp_wait_for: Callable[..., Coroutine[Any, Any, Any]],
        mcp_take_snapshot: Callable[..., Coroutine[Any, Any, Any]],
        mcp_take_screenshot: Callable[..., Coroutine[Any, Any, Any]],
        resolver: SnapshotResolver | None = None,
        self_healer: SelfHealer | None = None,
        retry_count: int = 2,
    ):
        """初始化 MCP 执行器.

        Args:
            mcp_navigate: navigate_page MCP 工具的 callable
            mcp_click: click MCP 工具的 callable
            mcp_fill: fill MCP 工具的 callable
            mcp_press_key: press_key MCP 工具的 callable
            mcp_wait_for: wait_for MCP 工具的 callable
            mcp_take_snapshot: take_snapshot MCP 工具的 callable
            mcp_take_screenshot: take_screenshot MCP 工具的 callable
            resolver: 快照解析器实例
            self_healer: LLM 自愈器实例（可选）
            retry_count: 操作失败重试次数
        """
        self._navigate = mcp_navigate
        self._click = mcp_click
        self._fill = mcp_fill
        self._press_key = mcp_press_key
        self._wait_for = mcp_wait_for
        self._take_snapshot = mcp_take_snapshot
        self._take_screenshot = mcp_take_screenshot
        self.resolver = resolver or SnapshotResolver()
        self.self_healer = self_healer
        self.retry_count = retry_count
        self._latest_snapshot: str = ""

    @property
    def latest_snapshot(self) -> str:
        """最近一次获取的 a11y 快照文本."""
        return self._latest_snapshot

    async def refresh_snapshot(self) -> str:
        """调用 take_snapshot 刷新并返回快照文本."""
        result = await self._take_snapshot()
        self._latest_snapshot = str(result)
        return self._latest_snapshot

    async def take_failure_screenshot(self) -> str:
        """失败时截图，返回截图结果描述."""
        try:
            result = await self._take_screenshot()
            return str(result)
        except Exception as e:
            logger.warning(f"截图失败: {e}")
            return f"截图失败: {e}"

    async def execute_step(self, step: TestStep) -> StepResult:
        """执行单个测试步骤.

        流程：
        1. navigate / wait_for / screenshot / snapshot → 直接执行
        2. 需要元素交互的步骤 → refresh_snapshot → resolve UID → 调用 MCP
        3. resolve 失败 → SelfHealer 自愈 → 重试
        4. assert_* → 在快照上验证（由编排器处理）
        """
        start_time = time.monotonic()

        try:
            # 不需要元素解析的操作
            if step.action == "navigate":
                return await self._execute_navigate(step, start_time)
            if step.action == "wait_for":
                return await self._execute_wait_for(step, start_time)
            if step.action == "screenshot":
                await self._take_screenshot()
                return self._success_result(step, start_time)
            if step.action == "snapshot":
                await self.refresh_snapshot()
                return self._success_result(step, start_time)
            if step.action.startswith("assert_"):
                # assert 步骤由编排器的 Evaluator 处理
                return self._success_result(step, start_time, status="passed")
            if step.action == "press_key":
                return await self._execute_press_key(step, start_time)

            # 需要元素交互的操作: click, fill
            return await self._execute_element_action(step, start_time)

        except Exception as e:
            duration = int((time.monotonic() - start_time) * 1000)
            logger.error(f"步骤执行异常: {step.description} - {e}")
            return StepResult(
                step_index=0,
                status="failed",
                error=str(e),
                duration_ms=duration,
            )

    async def _execute_navigate(self, step: TestStep, start_time: float) -> StepResult:
        """执行导航操作."""
        url = step.url or step.value or ""
        await self._navigate(type="url", url=url)
        # 导航后等待一下再刷新快照
        await asyncio.sleep(1)
        await self.refresh_snapshot()
        return self._success_result(step, start_time)

    async def _execute_wait_for(self, step: TestStep, start_time: float) -> StepResult:
        """执行等待操作."""
        text = step.value or ""
        timeout = step.timeout_ms or 10000
        try:
            await self._wait_for(text=[text], timeout=timeout)
            # 等待成功后刷新快照，确保后续步骤拿到最新状态
            await self.refresh_snapshot()
            return self._success_result(step, start_time)
        except Exception as e:
            duration = int((time.monotonic() - start_time) * 1000)
            return StepResult(
                step_index=0,
                status="failed",
                error=f"等待 '{text}' 超时: {e}",
                duration_ms=duration,
            )

    async def _execute_press_key(self, step: TestStep, start_time: float) -> StepResult:
        """执行按键操作."""
        key = step.value or ""
        await self._press_key(key=key)
        return self._success_result(step, start_time)

    async def _execute_element_action(self, step: TestStep, start_time: float) -> StepResult:
        """执行需要元素定位的操作（click / fill）.

        流程：refresh_snapshot → resolve UID → 执行 → 失败则自愈重试
        """
        if not step.element:
            return StepResult(
                step_index=0,
                status="failed",
                error=f"步骤 '{step.description}' 缺少 element 定义",
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )

        # 获取最新快照
        snapshot = await self.refresh_snapshot()

        # 尝试解析 UID
        uid = self.resolver.resolve(snapshot, step.element)

        if uid:
            # 解析成功，执行操作
            try:
                await self._call_mcp_action(step.action, uid, step.value)
                return self._success_result(step, start_time, resolved_uid=uid)
            except Exception as e:
                logger.warning(f"MCP 操作失败 (uid={uid}): {e}")
                # 操作失败，尝试重新快照后重试
                for attempt in range(self.retry_count):
                    await asyncio.sleep(0.5)
                    snapshot = await self.refresh_snapshot()
                    uid = self.resolver.resolve(snapshot, step.element)
                    if uid:
                        try:
                            await self._call_mcp_action(step.action, uid, step.value)
                            return self._success_result(step, start_time, resolved_uid=uid)
                        except Exception as retry_err:
                            logger.warning(f"重试 {attempt + 1} 失败: {retry_err}")

        # SnapshotResolver 匹配失败 → 尝试 SelfHealer
        if self.self_healer:
            logger.info(f"触发自愈: {step.element.name}")
            healed_uid = await self.self_healer.find_element_uid(
                element=step.element,
                step_description=step.description,
                page_snapshot=snapshot,
            )
            if healed_uid:
                try:
                    await self._call_mcp_action(step.action, healed_uid, step.value)
                    duration = int((time.monotonic() - start_time) * 1000)
                    return StepResult(
                        step_index=0,
                        status="healed",
                        resolved_uid=healed_uid,
                        healed_by=f"LLM 推断 UID: {healed_uid}",
                        duration_ms=duration,
                    )
                except Exception as heal_err:
                    logger.error(f"自愈后操作仍失败: {heal_err}")

        # 全部失败
        duration = int((time.monotonic() - start_time) * 1000)
        await self.take_failure_screenshot()
        return StepResult(
            step_index=0,
            status="failed",
            error=f"无法定位元素: role={step.element.role}, name={step.element.name}",
            duration_ms=duration,
        )

    async def _call_mcp_action(self, action: str, uid: str, value: str | None) -> None:
        """根据 action 类型调用对应的 MCP 工具."""
        if action == "click":
            await self._click(uid=uid)
        elif action == "fill":
            if not value:
                raise ValueError("fill 操作必须提供 value")
            await self._fill(uid=uid, value=value)
        else:
            raise ValueError(f"不支持的元素操作: {action}")

    def _success_result(
        self,
        step: TestStep,
        start_time: float,
        *,
        status: str = "passed",
        resolved_uid: str | None = None,
    ) -> StepResult:
        """构造成功结果."""
        duration = int((time.monotonic() - start_time) * 1000)
        return StepResult(
            step_index=0,
            status=status,  # type: ignore[arg-type]
            resolved_uid=resolved_uid,
            duration_ms=duration,
        )
