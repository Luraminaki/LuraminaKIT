#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Client for a locally-running OpenAI-compatible completion server.

Deliberately doesn't embed an inference engine (e.g. `llama-cpp-python`) in
this process -- this module is a thin HTTP client to whatever's already
serving an OpenAI-compatible `/v1/chat/completions` endpoint (llama.cpp's own
`llama-server`, matching this module's intended use, but also Ollama/LM
Studio/vLLM without any code change here). Swapping the model being served is
entirely that server's own concern (e.g. restarting `llama-server` with a
different `-m` path) -- this client never needs to know or care which model
answered.

@author: Luraminaki
"""

import logging

from typing import TYPE_CHECKING

import aiohttp

from pydantic import BaseModel

if TYPE_CHECKING:
    from modulesKIT.modules.helpers.generic_config import AppConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_DEFAULT_BASE_URL = 'http://127.0.0.1:8080'
_DEFAULT_MODEL = 'local-model'
_DEFAULT_SYSTEM_PROMPT = 'You are a helpful assistant.'
_DEFAULT_MAX_TOKENS = 512
_DEFAULT_TEMPERATURE = 0.7
_DEFAULT_TIMEOUT = 60.0


class _ChatMessage(BaseModel):
    """One message in an OpenAI-style chat completion response."""

    role: str = ''
    content: str = ''


class _ChatChoice(BaseModel):
    """One completion choice in an OpenAI-style chat completion response."""

    message: _ChatMessage = _ChatMessage()


class _ChatCompletionResponse(BaseModel):
    """The subset of an OpenAI-style `/v1/chat/completions` response this client needs."""

    choices: list[_ChatChoice] = []


class LlmClient:
    """Sends chat completions to a configured OpenAI-compatible server."""

    def __init__(self, module_name: str | None = None,
                 modules_config: 'AppConfig | None' = None) -> None:
        """Read this module's connection settings from its own config `data`.

        Args:
            module_name: Name of this module, used to look up its config.
            modules_config: Loaded application configuration.

        Raises:
            ValueError: If `module_name` or `modules_config` is missing.
        """
        if not modules_config or not module_name:
            raise ValueError(f"{self.__class__.__name__} -- Invalid module_name configuration file provided -- {module_name} : {modules_config}")

        data = modules_config.modules[module_name].data
        self.base_url: str = data.get('base_url', _DEFAULT_BASE_URL).rstrip('/')
        self.model: str = data.get('model', _DEFAULT_MODEL)
        self.system_prompt: str = data.get('system_prompt', _DEFAULT_SYSTEM_PROMPT)
        self.max_tokens: int = int(data.get('max_tokens', str(_DEFAULT_MAX_TOKENS)))
        self.temperature: float = float(data.get('temperature', str(_DEFAULT_TEMPERATURE)))
        self.timeout: float = float(data.get('timeout', str(_DEFAULT_TIMEOUT)))

        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return the shared session, opening it on first use.

        Not opened in `__init__` -- that runs before uvicorn starts the event
        loop, and `aiohttp.ClientSession` needs one already running.

        Returns:
            The shared, reused-across-calls session.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def complete(self, prompt: str) -> str:
        """Send `prompt` as a single-turn chat completion request.

        Args:
            prompt: The user's message.

        Returns:
            The model's reply, stripped of leading/trailing whitespace.

        Raises:
            aiohttp.ClientError: On a connection failure or non-2xx response
                (e.g. the completion server isn't running).
            ValueError: If the response parsed but carried no usable content.
        """
        session = await self._get_session()
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': self.system_prompt},
                {'role': 'user', 'content': prompt},
            ],
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'stream': False,
        }

        async with session.post(f"{self.base_url}/v1/chat/completions", json=payload,
                                timeout=aiohttp.ClientTimeout(self.timeout)) as response:
            response.raise_for_status()
            raw_body = await response.text()

        parsed = _ChatCompletionResponse.model_validate_json(raw_body)
        content = parsed.choices[0].message.content.strip() if parsed.choices else ''

        if not content:
            raise ValueError(f"Completion response carried no usable content: {raw_body!r}")

        return content
