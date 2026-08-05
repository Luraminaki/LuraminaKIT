#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Luraminaki
"""

import logging

from typing import TYPE_CHECKING

import aiohttp

from contractsKIT import StandardResponse, ParamDescriptor
from modulesKIT.modules.helpers import generic_api_views
from modulesKIT.modules.llm import llm_client

if TYPE_CHECKING:
    from modulesKIT.modules.helpers.generic_config import AppConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class LlmView(generic_api_views.GenericViews):
    """Exposes the `/chat` route backed by `llm_client.LlmClient`."""

    def __init__(self, modules_config: 'AppConfig | None' = None, *args, **kwargs) -> None:
        """Load this module's completion-server settings and register `/chat`.

        Args:
            modules_config: Loaded application configuration.
            *args: Forwarded to `GenericViews`.
            **kwargs: Forwarded to `GenericViews`.
        """
        super().__init__(*args, modules_config=modules_config, **kwargs)

        self.client: llm_client.LlmClient = llm_client.LlmClient(self.module_name, modules_config)
        self.add_route("/chat",
                       self.chat,
                       methods=['GET'],
                       response_model=StandardResponse[str],
                       name='llm.chat',
                       params=[ParamDescriptor(name='prompt', required=True)],
                       timeout=self.client.timeout)

    async def chat(self, prompt: str) -> StandardResponse[str]:
        """Send `prompt` to the configured completion server.

        Args:
            prompt: The user's message.

        Returns:
            A `StandardResponse` wrapping the model's reply, or an error if the
            completion server is unreachable or returned something unusable.
        """
        try:
            reply = await self.client.complete(prompt)
        except aiohttp.ClientConnectorError as err:
            # By far the most likely failure for this module specifically -- the
            # completion server (e.g. llama-server) just isn't running. The raw
            # exception repr is full of socket/proxy internals that mean nothing
            # to a Discord user; a clean, actionable message is worth the special case.
            logger.error("Completion server unreachable at %s -- %r", self.client.base_url, err)
            return StandardResponse[str].fail(f"Can't reach the completion server at {self.client.base_url} "
                                              + "-- is it running?")
        except aiohttp.ClientError as err:
            logger.error("Completion server request failed -- %r", err)
            return StandardResponse[str].fail(f"Completion server request failed: {err!r}")
        except Exception as err:
            logger.error("%r", err)
            return StandardResponse[str].fail(repr(err))

        return StandardResponse[str].ok(reply)
