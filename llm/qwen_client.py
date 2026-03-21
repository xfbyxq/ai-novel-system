"""通义千问 LLM 客户端封装."""

import asyncio
import logging
from typing import AsyncIterator, Iterator

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
            and (
                "coding.dashscope" in self.base_url
                or "dashscope.aliyuncs.com" in self.base_url
            )
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
        max_tokens: int = 4096,
        top_p: float = 0.9,
        retries: int = 3,
    ) -> dict:
        """异步调用通义千问 API.

        Returns:
            dict: {"content": str, "usage": {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}}
        """
        if self.use_openai_mode:
            return await self._chat_openai(
                prompt, system, temperature, max_tokens, retries
            )
        else:
            return await self._chat_dashscope(
                prompt, system, temperature, max_tokens, top_p, retries
            )

    async def _chat_openai(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        retries: int = 3,
    ) -> dict:
        """使用 OpenAI 兼容模式调用 API."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_error = None
        for attempt in range(retries):
            try:
                response = await self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                content = response.choices[0].message.content
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
                return {"content": content, "usage": usage}

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Attempt {attempt + 1}/{retries} exception: {last_error}"
                )

            if attempt < retries - 1:
                wait = 2**attempt
                logger.info(f"Retrying in {wait}s...")
                await asyncio.sleep(wait)

        raise RuntimeError(
            f"QwenClient.chat (OpenAI mode) failed after {retries} attempts: {last_error}"
        )

    async def _chat_dashscope(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
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
                response = await loop.run_in_executor(
                    None,
                    lambda: Generation.call(
                        model=self.model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        result_format="message",
                    ),
                )

                if response.status_code == 200:
                    content = response.output.choices[0].message.content
                    usage = {
                        "prompt_tokens": response.usage.input_tokens,
                        "completion_tokens": response.usage.output_tokens,
                        "total_tokens": response.usage.input_tokens
                        + response.usage.output_tokens,
                    }
                    return {"content": content, "usage": usage}
                else:
                    last_error = f"API error {response.status_code}: {response.message}"
                    logger.warning(
                        f"Attempt {attempt + 1}/{retries} failed: {last_error}"
                    )

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Attempt {attempt + 1}/{retries} exception: {last_error}"
                )

            if attempt < retries - 1:
                wait = 2**attempt
                logger.info(f"Retrying in {wait}s...")
                await asyncio.sleep(wait)

        raise RuntimeError(
            f"QwenClient.chat failed after {retries} attempts: {last_error}"
        )

    async def stream_chat(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> "AsyncIterator[str]":
        """流式调用通义千问 API，逐块返回文本."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # 处理不同模式的流式调用
        if self.use_openai_mode:
            # 使用 OpenAI 兼容模式的流式调用
            async for chunk in self._stream_chat_openai(
                prompt, system, temperature, max_tokens
            ):
                yield chunk
        else:
            # 使用标准 DashScope SDK 的流式调用
            # 使用线程池执行同步流式调用
            loop = asyncio.get_event_loop()
            responses = await loop.run_in_executor(
                None,
                lambda: Generation.call(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    result_format="message",
                    stream=True,
                    incremental_output=True,
                ),
            )

            for response in responses:
                if response.status_code == 200:
                    content = response.output.choices[0].message.content
                    if content:
                        yield content
                else:
                    raise RuntimeError(
                        f"Stream error {response.status_code}: {response.message}"
                    )

    async def _stream_chat_openai(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> "AsyncIterator[str]":
        """使用 OpenAI 兼容模式进行流式调用."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async for chunk in self.openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        ):
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# Module-level singleton
qwen_client = QwenClient()
