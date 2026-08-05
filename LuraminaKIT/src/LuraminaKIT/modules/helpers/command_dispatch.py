#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP dispatch logic for calling a discovered command's route, kept separate
from Discord API glue -- see `LuraminaKIT/HOWTO.md`. Command discovery lives in
`command_discovery.py`, `/help` rendering in `command_help.py`, `/status`
rendering in `status_embed.py`.
"""

import logging
import urllib.parse

import aiohttp

from contractsKIT import StatusFunction, ParamDescriptor
from LuraminaKIT.modules.helpers import req_mngr
from LuraminaKIT.modules.helpers.command_discovery import CommandEntry

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _match_params(query_params: list[ParamDescriptor], command_params: list[str]) -> dict[str, str]:
    """Match user-typed words to a command's declared params, positionally --
    except the *last* declared param, which absorbs every remaining word
    (rejoined with single spaces) instead of only the next one.

    Without this, a plain `zip()` silently truncates any free-text param to
    its first word: `!tb1.char Jade Dragon` would send only `query=Jade`,
    quietly dropping "Dragon" -- broken for every multi-word lookup
    (`tb1.char`/`tb1.mon`/`tb1.item`/`tb1.buddy`/`tb1.search`) today, and a
    hard blocker for anything that takes a genuine free-text sentence (e.g.
    a future LLM prompt).

    Args:
        query_params: The command's declared params, in positional order.
        command_params: Words typed by the user after the command name.

    Returns:
        Param name -> matched value. Fewer typed words than params leaves the
        trailing params unset entirely (unchanged from the old behavior) --
        the modulesKIT route's own validation reports that as a real error.
    """
    matched: dict[str, str] = {}
    last_index = len(query_params) - 1

    for index, param in enumerate(query_params):
        if index >= len(command_params):
            break
        if index == last_index:
            matched[param.name] = ' '.join(command_params[index:])
        else:
            matched[param.name] = command_params[index]

    return matched


async def process_command(session: aiohttp.ClientSession, base_route: str, command: CommandEntry,
                          command_params: list[str]) -> str:
    """Call a discovered command's route, forwarding any user-supplied arguments.

    Args:
        session: Shared `aiohttp.ClientSession` (see `DiscordClient.http_session`).
        base_route: Modules' base URL (scheme + host), e.g. `"http://127.0.0.1"`.
        command: The command to call.
        command_params: Positional arguments typed by the user, matched in order
            against `command.query_params`.

    Returns:
        The command's response, or a fallback error message describing what
        went wrong. Never `''` -- an empty string reaches `DiscordClient._send`
        as an empty message, which Discord's API rejects outright, so the
        command would silently appear to do nothing instead of reporting the
        actual failure.
    """
    api_route: str = f"{base_route}:{command.port}{command.path}"

    if command.query_params and command_params:
        matched = _match_params(command.query_params, command_params)
        if matched:
            api_route = f"{api_route}?{urllib.parse.urlencode(matched)}"

    resp = await req_mngr.request(session, api_route, timeout=command.timeout)

    if resp.status != StatusFunction.SUCCESS:
        logger.error("Module %s: %s", command.name, resp.error)
        help_hint = f" -- see `/help path:{command.name}` for usage."
        return (f"⚠️ `{command.name}` failed: {resp.error}{help_hint}" if resp.error
                else f"⚠️ `{command.name}` failed.{help_hint}")

    return str(resp.data)


async def fetch_attachments(session: aiohttp.ClientSession, base_route: str,
                            command: CommandEntry) -> list[tuple[bytes, str]]:
    """Fetch every one of a command's companion attachment files.

    Args:
        session: Shared `aiohttp.ClientSession` (see `DiscordClient.http_session`).
        base_route: Modules' base URL (scheme + host), e.g. `"http://127.0.0.1"`.
        command: The command to fetch attachments for.

    Returns:
        `(content, filename)` for each attachment that fetched successfully. A
        single failed fetch is logged (by `req_mngr.request_bytes`) and skipped
        rather than failing the whole batch.
    """
    results: list[tuple[bytes, str]] = []

    for attachment_path in command.attachment_paths:
        api_route = f"{base_route}:{command.port}/api/{command.module_name}{attachment_path}"
        fetched = await req_mngr.request_bytes(session, api_route, timeout=command.timeout)
        if fetched is not None:
            results.append(fetched)

    return results
