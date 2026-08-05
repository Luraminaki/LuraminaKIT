#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command discovery bookkeeping: parsing incoming messages and building the
name/alias -> `CommandEntry` map from a module's advertised manifest. Kept
separate from Discord API glue -- see `LuraminaKIT/HOWTO.md`.
"""

import logging

import discord

from contractsKIT import ModuleManifest, RouteDescriptor, CategoryHelp

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class CommandEntry(RouteDescriptor):
    """A `RouteDescriptor` bound to the port and module that advertised it."""

    port: int
    module_name: str
    module_description: str
    category_help: dict[str, CategoryHelp]


def log_message(message: discord.Message) -> None:
    """Log an incoming Discord message's metadata and content.

    Args:
        message: The message to log.
    """
    guild_name: str = message.guild.name if message.guild is not None else ''
    channel_name: str = getattr(message.channel, 'name', '')

    if message.attachments:
        for attachement in message.attachments:
            logger.info("%s/%s - %s: %s (%s)", guild_name, channel_name, message.author.name,
                        attachement.filename, attachement.content_type)

    if message.content:
        logger.info("%s/%s - %s: %s", guild_name, channel_name, message.author.name, message.content)


def parse_command(content: str, prefix: str) -> tuple[str, list[str]] | None:
    """Split a prefixed message into a command name and its arguments.

    Args:
        content: Raw message content.
        prefix: The bot's command prefix (e.g. `"!"`).

    Returns:
        `(command_name, command_args)`, or `None` if `content` doesn't start with `prefix`.
    """
    if not content.startswith(prefix):
        return None

    message_parts = content[len(prefix):].split(' ', maxsplit=1)
    command_name = message_parts[0]
    command_args = message_parts[1].split() if len(message_parts) > 1 else []
    return command_name, command_args


def build_commands(port: int, manifest: ModuleManifest) -> dict[str, CommandEntry]:
    """Build a command-name -> `CommandEntry` map from a module's advertised manifest.

    Each route is registered under its own name *and* every alias it advertises,
    all pointing at the same `CommandEntry`. A name/alias that collides with one
    already claimed within this same module is logged and skipped rather than
    silently overwriting the earlier registration.

    Args:
        port: TCP port of the module that returned `manifest`.
        manifest: The module's advertised routes.

    Returns:
        Mapping of route name/alias to `CommandEntry`.
    """
    commands: dict[str, CommandEntry] = {}

    for route in manifest.routes:
        entry = CommandEntry.model_validate({
            'port': port,
            'module_name': manifest.module_name,
            'module_description': manifest.description,
            'category_help': manifest.category_help,
            **route.model_dump(),
        })

        for key in (route.name, *route.aliases):
            if key in commands:
                logger.warning("Module %s: command/alias %r collides with an existing one -- skipped",
                               manifest.module_name, key)
                continue
            commands[key] = entry

    return commands
