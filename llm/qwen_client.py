"""通义千问 LLM 客户端封装."""

import asyncio
import logging
from typing import Any, AsyncIterator, Optional

import dashscope
from dashscope import Generation
from openai import AsyncOpenAI

from backend.config import settings

logger = logging.getLogger(__name__)


class QwenClient:
    """封装 DashScope API 调用，支持重试和流式输出."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        """初始化方法."""
        self.api_key = api_key or settings.DASHSCOPE_API_KEY
        self.model = model or settings.DASHSCOPE_MODEL
        self.base_url = base_url or settings.DASHSCOPE_BASE_URL

        # 判断是否使用 OpenAI 兼容模式
        self.use_openai_mode = bool(
            self.base_url
            and ("coding.dashscope" in self.base_url or "dashscope.aliyuncs.com" in self.base_url)
        )

        if self.use_openai_mode:
            # 使用 OpenAI 兼容模式（异步）
            import httpx

            # 增加超时时间：LLM 响应较慢，特别是复杂任务可能需要 2-5 分钟
            self.openai_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=httpx.Timeout(
                    timeout=300.0,  # 总超时 300 秒（5 分钟）
                    connect=10.0,  # 连接超时 10 秒
                    read=300.0,  # 读取超时 300 秒（5 分钟）
                    write=300.0,  # 写入超时 300 秒（5 分钟）
                ),
            )
            logger.info(f"使用 OpenAI 兼容模式：{self.base_url}，超时配置：300s")
        else:
            # 使用标准 DashScope SDK
            dashscope.api_key = self.api_key
            if self.base_url:
                dashscope.base_http_api_url = self.base_url
                logger.info(f"使用自定义 base URL: {self.base_url}")

    async def chat(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,  # None 表示不限制，避免截断
        top_p: float = 0.9,
        retries: int = 3,
    ) -> dict:
        """异步调用通义千问 API.

        Returns:
            dict: {"content": str, "usage": {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}}
        """
        if self.use_openai_mode:
            return await self._chat_openai(prompt, system, temperature, max_tokens, retries)
        else:
            return await self._chat_dashscope(
                prompt, system, temperature, max_tokens, top_p, retries
            )

    async def _chat_openai(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        retries: int = 3,
    ) -> dict:
        """使用 OpenAI 兼容模式调用 API.

        增强的重试机制：
        - 对于 Connection error 类错误，使用更长的退避时间
        - 记录详细的错误类型，便于诊断
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_error = None
        last_error_type = None
        is_connection_error = False
        for attempt in range(retries):
            try:
                # 构建请求参数，max_tokens 仅在有值时传递
                params: dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if max_tokens is not None:
                    params["max_tokens"] = max_tokens
                response = await self.openai_client.chat.completions.create(**params)

                content = response.choices[0].message.content
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
                return {"content": content, "usage": usage}

            except Exception as e:
                last_error = str(e)
                last_error_type = type(e).__name__
                # 对于连接错误，使用更长的退避时间
                is_connection_error = any(
                    keyword in last_error.lower()
                    for keyword in ["connection", "connect", "timeout", "network"]
                )
                logger.warning(
                    f"Attempt {attempt + 1}/{retries} exception: {last_error_type}: {last_error}"
                )

            if attempt < retries - 1:
                # Connection error 使用更长退避（5s, 10s, 20s）
                # 其他错误使用标准退避（1s, 2s, 4s）
                if is_connection_error:
                    wait = 5 * (2 ** attempt)
                    logger.warning(f"Connection error detected, extended retry in {wait}s...")
                else:
                    wait = 2 ** attempt
                    logger.info(f"Retrying in {wait}s...")
                await asyncio.sleep(wait)

        raise RuntimeError(
            f"QwenClient.chat (OpenAI mode) failed after {retries} attempts: {last_error_type}: {last_error}"
        )

    async def _chat_dashscope(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: float = 0.9,
        retries: int = 3,
    ) -> dict:
        """使用标准 DashScope SDK 调用 API."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_error = None
        for attempt in range(retries):
            try:
                # 使用线程池执行同步调用，避免阻塞事件循环
                loop = asyncio.get_event_loop()
                # 构建 Generation.call 参数
                call_params: dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "top_p": top_p,
                    "result_format": "message",
                }
                if max_tokens is not None:
                    call_params["max_tokens"] = max_tokens
                response = await loop.run_in_executor(
                    None,
                    lambda: Generation.call(**call_params),
                )

                if response.status_code == 200:
                    content = response.output.choices[0].message.content
                    usage = {
                        "prompt_tokens": response.usage.input_tokens,
                        "completion_tokens": response.usage.output_tokens,
                        "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                    }
                    return {"content": content, "usage": usage}
                else:
                    last_error = f"API error {response.status_code}: {response.message}"
                    logger.warning(f"Attempt {attempt + 1}/{retries} failed: {last_error}")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1}/{retries} exception: {last_error}")

            if attempt < retries - 1:
                wait = 2**attempt
                logger.info(f"Retrying in {wait}s...")
                await asyncio.sleep(wait)

        raise RuntimeError(f"QwenClient.chat failed after {retries} attempts: {last_error}")

    async def stream_chat(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> "AsyncIterator[str]":
        """流式调用通义千问 API，逐块返回文本."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # 处理不同模式的流式调用
        if self.use_openai_mode:
            # 使用 OpenAI 兼容模式的流式调用
            async for chunk in self._stream_chat_openai(prompt, system, temperature, max_tokens):
                yield chunk
        else:
            # 使用标准 DashScope SDK 的流式调用
            # 使用线程池执行同步流式调用
            loop = asyncio.get_event_loop()
            call_params: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "result_format": "message",
                "stream": True,
                "incremental_output": True,
            }
            if max_tokens is not None:
                call_params["max_tokens"] = max_tokens
            responses = await loop.run_in_executor(
                None,
                lambda: Generation.call(**call_params),
            )

            for response in responses:
                if response.status_code == 200:
                    content = response.output.choices[0].message.content
                    if content:
                        yield content
                else:
                    raise RuntimeError(f"Stream error {response.status_code}: {response.message}")

    async def _stream_chat_openai(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> "AsyncIterator[str]":
        """使用 OpenAI 兼容模式进行流式调用."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # 需要先 await 获取流式响应对象
        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        stream = await self.openai_client.chat.completions.create(**params)
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        retries: int = 3,
    ) -> dict:
        """调用模型并支持工具调用.

        Args:
            messages: 消息列表，格式如 [{"role": "user", "content": "..."}]
            tools: 工具定义列表，格式如 [{
                "type": "function",
                "function": {
                    "name": "func_name",
                    "description": "...",
                    "parameters": {...}
                }
            }]
            tool_choice: 工具选择策略，"auto", "none" 或 {"type": "function", "function": {"name": "xxx"}}
            temperature: 温度参数
            max_tokens: 最大token数
            retries: 重试次数

        Returns:
            dict: {"type": "tool_call", "tool_calls": [...]} 或 {"type": "text", "content": str}
        """
        if self.use_openai_mode:
            return await self._chat_with_tools_openai(
                messages, tools, tool_choice, temperature, max_tokens, retries
            )
        else:
            raise NotImplementedError(
                "chat_with_tools 仅支持 OpenAI 兼容模式，当前为 DashScope 模式"
            )

    async def _chat_with_tools_openai(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        retries: int = 3,
    ) -> dict:
        """使用 OpenAI 兼容模式调用工具."""
        last_error = None
        for attempt in range(retries):
            try:
                params: dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,  # type: ignore[arg-type]
                    "tools": tools,  # type: ignore[arg-type]
                    "tool_choice": tool_choice,  # type: ignore[arg-type]
                    "temperature": temperature,
                }
                if max_tokens is not None:
                    params["max_tokens"] = max_tokens
                response = await self.openai_client.chat.completions.create(**params)

                message = response.choices[0].message

                # 检查是否有工具调用
                if message.tool_calls:
                    tool_calls = []
                    for tc in message.tool_calls:
                        # 处理 function 类型的工具调用
                        tc_any: Any = tc
                        if hasattr(tc_any, "function") and tc_any.function:
                            tool_calls.append(
                                {
                                    "id": tc_any.id,
                                    "type": tc_any.type,
                                    "function": {
                                        "name": tc_any.function.name,
                                        "arguments": tc_any.function.arguments,
                                    },
                                }
                            )
                    if tool_calls:
                        return {"type": "tool_call", "tool_calls": tool_calls}

                # 返回文本内容
                content = message.content or ""
                return {"type": "text", "content": str(content)}

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1}/{retries} exception: {last_error}")

            if attempt < retries - 1:
                wait = 2**attempt
                logger.info(f"Retrying in {wait}s...")
                await asyncio.sleep(wait)

        raise RuntimeError(
            f"QwenClient.chat_with_tools failed after {retries} attempts: {last_error}"
        )


# Module-level singleton
qwen_client = QwenClient()
