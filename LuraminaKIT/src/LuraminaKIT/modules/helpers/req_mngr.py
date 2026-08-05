#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 26 11:23:51 2024

@author: Luraminaki
"""

import enum
import logging

import aiohttp

from contractsKIT import StandardResponse

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class HeaderType(enum.Enum):
    """Which HTTP headers to send with a request."""

    DEFAULT = 0
    NONE = 1


def set_headers(ht: HeaderType = HeaderType.DEFAULT) -> dict[str, str]:
    """Build the HTTP headers for a request.

    Args:
        ht: Which header set to use.

    Returns:
        The headers to send.
    """
    if ht == HeaderType.DEFAULT:
        return {'Content-Type': 'application/json'}

    return {}


def process_response(response: str) -> StandardResponse[object]:
    """Parse a modulesKIT HTTP response body into a `StandardResponse`.

    Args:
        response: Raw response body.

    Returns:
        The parsed `StandardResponse`, or a failed one if parsing raised.
    """
    try:
        return StandardResponse[object].model_validate_json(response)

    except Exception as err:
        logger.error("%r", err)
        return StandardResponse[object].fail(repr(err))


async def request_bytes(session: aiohttp.ClientSession, api_route: str, timeout: float = 5) -> tuple[bytes, str] | None:
    """Issue a GET request against a modulesKIT route and return its raw response body.

    Unlike `request`, this doesn't parse the body as a `StandardResponse` -- for
    modulesKIT routes that serve raw file bytes (e.g. a flowchart image) rather
    than JSON, such as a route advertised via a command's `attachment_path`.

    Args:
        session: Shared `aiohttp.ClientSession` -- callers reuse one for the
            process's lifetime rather than opening a new connection pool per
            request (see `DiscordClient.http_session`).
        api_route: Full URL to request.
        timeout: Request timeout in seconds.

    Returns:
        `(content, filename)` -- `filename` comes from the response's
        `Content-Disposition` header if the server set one (modulesKIT's
        `FileResponse(path, filename=...)` does), falling back to the URL's own
        last path segment otherwise. `None` if the request failed or didn't
        return a 200 status.
    """
    try:
        async with session.get(api_route, timeout=aiohttp.ClientTimeout(timeout)) as response:
            if response.status != 200:
                logger.error("Attachment request failed: %s -- HTTP %s", api_route, response.status)
                return None

            content = await response.content.read()
            disposition = response.content_disposition
            filename = disposition.filename if disposition and disposition.filename else api_route.rsplit('/', 1)[-1]
            return content, filename

    except Exception as err:
        logger.error("%r", err)
        return None


async def request(session: aiohttp.ClientSession, api_route: str, header: HeaderType = HeaderType.DEFAULT,
                  cookies: dict[str, str] | None = None, timeout: float = 5) -> StandardResponse[object]:
    """Issue a GET request against a modulesKIT route and parse its response.

    Args:
        session: Shared `aiohttp.ClientSession` -- callers reuse one for the
            process's lifetime rather than opening a new connection pool per
            request (see `DiscordClient.http_session`).
        api_route: Full URL to request.
        header: Which header set to send.
        cookies: Cookies to send, if any.
        timeout: Request timeout in seconds -- see `contractsKIT.RouteDescriptor.timeout`
            for why this isn't just a fixed value.

    Returns:
        The parsed `StandardResponse`, or a failed one if the request raised.
    """
    if cookies is None:
        cookies = {}

    head = set_headers(header)

    try:
        async with session.get(api_route, headers=head, cookies=cookies, timeout=aiohttp.ClientTimeout(timeout)) as response:
            if response.status != 200:
                logger.error("Request failed: %s -- HTTP %s", api_route, response.status)
                return StandardResponse[object].fail(f"HTTP {response.status}")

            content: bytes = await response.content.read()
            return process_response(content.decode('utf-8'))

    except Exception as err:
        logger.error("%r", err)
        return StandardResponse[object].fail(repr(err))
