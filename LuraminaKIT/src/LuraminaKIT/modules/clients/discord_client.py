#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov 10 18:05:32 2025

@author: Luraminaki
"""

import io
import logging
import time
from typing import override

import asyncio
import aiohttp
import discord
import psutil
from discord import app_commands

from contractsKIT import StatusFunction, ModuleManifest
from LuraminaKIT.modules.helpers import req_mngr, host_metrics
from LuraminaKIT.modules.helpers.settings import Settings
from LuraminaKIT.modules.helpers.message_chunking import chunk_message
from LuraminaKIT.modules.helpers.command_dispatch import (
    CommandEntry,
    build_commands,
    build_help_text,
    build_status_embed,
    fetch_attachments,
    log_message,
    parse_command,
    process_command,
    suggest_command,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DiscordClient(discord.Client):
    """Discord client that discovers modulesKIT commands and proxies messages to them.

    The "intelligence" behind each event (parsing, logging, dispatching, calling a
    module) lives in `modules.helpers.command_dispatch` and `.message_chunking` — this
    class only wires Discord's event hooks to that logic and performs the actual
    Discord API calls (typing indicator, sending messages).
    """

    bg_task: asyncio.Task[None] | None = None
    # One shared session for the process's whole life, not one per request --
    # each aiohttp.ClientSession() owns its own connection pool, so opening a
    # fresh one per HTTP call (as this used to do) throws away keep-alive and
    # pays reconnect overhead on every single dispatched command. Created in
    # `setup_hook`, closed in `close`.
    http_session: aiohttp.ClientSession | None = None
    # `time.monotonic()` (not wall-clock time) so a system clock adjustment can't
    # make uptime jump backwards or forwards -- set in `setup_hook`.
    start_time: float = 0.0
    # Count of module commands successfully dispatched since startup -- for `!lurastatus`.
    commands_run: int = 0
    # The bot application's owner, fetched once in `setup_hook` -- gates `/reload`.
    owner_id: int | None = None

    def __init__(self, *args, **kwargs) -> None:
        """Read bot settings from `custom_config` and initialize `discord.Client`.

        Args:
            *args: Forwarded to `discord.Client`.
            **kwargs: Forwarded to `discord.Client`. `custom_config` (a `Settings`)
                is popped out for this client's own use.
        """
        self.custom_config: Settings = kwargs.get('custom_config', Settings())

        self.prefix: str = self.custom_config.bot_params.cmd_prefix
        self.commands: dict[str, CommandEntry] = {}

        self.modules_base_route: str = self.custom_config.bot_params.modules_base_route
        self.modules_api_routes: str = self.custom_config.bot_params.modules_api_routes

        super().__init__(*args, **kwargs)

        # Admin/utility commands (help/status/reload) are slash-only -- they used
        # to also have a `!`-prefixed form (`!lurahelp` etc., the `lura` prefix
        # existing purely to dodge collisions in the flat `!` namespace), but
        # having the same 3 commands reachable two different ways under two
        # different names was more confusing than either option alone, and
        # slash commands don't have that collision problem to begin with
        # (Discord scopes them per-application). The dozens of tb1/anyquotes
        # module commands stay `!`-prefixed only: there are far too many for a
        # slash-command tree to stay pleasant, and new ones are added by a pure
        # `events.json`/catalog data change today, not a code change -- turning
        # that into "also re-register and re-sync a slash command" would undo
        # exactly the thing that design was for.
        self.tree: app_commands.CommandTree = app_commands.CommandTree(self)
        self._register_slash_commands()

    def _register_slash_commands(self) -> None:
        """Register `/help`, `/status`, `/reload` on `self.tree`.

        Defining commands here only registers them locally -- `self.tree.sync`
        (called per-guild in `on_ready`) is what actually publishes them to
        Discord.
        """
        @self.tree.command(name='help', description="List available commands.")
        async def slash_help(interaction: discord.Interaction, path: str = '') -> None:
            await self._send_interaction(interaction, build_help_text(self.commands, self.prefix, path.lower()))

        @self.tree.command(name='status', description="Show uptime, commands run, memory/CPU/GPU usage, and server count.")
        async def slash_status(interaction: discord.Interaction) -> None:
            uptime_seconds = time.monotonic() - self.start_time
            memory_mb = psutil.Process().memory_info().rss / (1024 * 1024)
            hardware = host_metrics.static_hardware_info()
            cpu_percent = host_metrics.cpu_load_percent()
            cpu_temp = host_metrics.cpu_temp_celsius()
            amd_gpu_temp = host_metrics.amd_gpu_temp_celsius()
            gpu_metrics = host_metrics.nvidia_gpu_metrics()
            # `/status` never needs chunking (it's always one bounded embed) --
            # send directly rather than through `_send_interaction`, which is
            # built for the arbitrarily-long plain-text replies `/help` produces.
            embed = build_status_embed(len(self.guilds), self.commands_run, uptime_seconds, memory_mb,
                                       hardware, cpu_percent, cpu_temp, amd_gpu_temp, gpu_metrics)
            _ = await interaction.response.send_message(embed=embed)

        @self.tree.command(name='reload', description="Re-poll every configured module for new/changed commands.")
        async def slash_reload(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.owner_id:
                _ = await interaction.response.send_message("Only the bot owner can run this.", ephemeral=True)
                return
            await self.get_modules()
            _ = await interaction.response.send_message(f"Reloaded -- {len(self.commands)} command names/aliases known.")

    async def get_modules(self) -> None:
        """Poll every configured module's `/url-list` and (re)build `self.commands`.

        Always polls every configured module and rebuilds from scratch (never an
        incremental update), so this is safe to call again later -- e.g. from
        `/reload` -- to pick up route/alias changes without a full bot restart.
        Resetting first also avoids every already-known command falsely
        reporting a collision against its own previous registration.
        """
        assert self.http_session is not None, "get_modules() called before setup_hook() opened http_session"

        self.commands = {}

        for module in self.custom_config.modules:
            logger.info("Loading module: %s", module.name)
            api_route: str = f"{self.modules_base_route}:{module.port}{module.prefix}{self.modules_api_routes}"

            resp = await req_mngr.request(self.http_session, api_route)

            if resp.status != StatusFunction.SUCCESS:
                logger.error("Module %s: %s", module.name, resp.error)
                continue

            manifest = ModuleManifest.model_validate(resp.data)

            # A blind dict.update() would let a later module silently shadow an earlier
            # one's command/alias -- log and keep the first registration instead.
            for name, entry in build_commands(module.port, manifest).items():
                if name in self.commands:
                    logger.warning("Module %s: command/alias %r collides with one already registered by %s -- skipped",
                                  module.name, name, self.commands[name].module_name)
                    continue
                self.commands[name] = entry

    async def _send(self, channel: discord.abc.Messageable, text: str,
                    files: list[discord.File] | None = None) -> None:
        """Send `text` to `channel`, splitting it into Discord-sized chunks first.

        Args:
            channel: Where to send the message(s).
            text: The text to send; split via `chunk_message` if it's too long.
            files: Attachments to send alongside the first chunk, if any.
        """
        for i, chunk in enumerate(chunk_message(text)):
            # discord.py's `send` overloads don't accept `files=None` explicitly
            # (only omitting the kwarg entirely, or a real non-empty sequence) --
            # so this can't be one call with a `files=... if ... else None` ternary.
            if i == 0 and files:
                _ = await channel.send(chunk, files=files)
            else:
                _ = await channel.send(chunk)

    async def _send_interaction(self, interaction: discord.Interaction, text: str) -> None:
        """Send `text` as a slash command's response, splitting it into Discord-sized chunks first.

        A slash command interaction's first reply must go through
        `interaction.response.send_message` specifically -- any further chunks
        need `interaction.followup.send` instead, unlike a plain channel message
        where every chunk sends the same way (see `_send`).

        Args:
            interaction: The slash command interaction to respond to.
            text: The text to send; split via `chunk_message` if it's too long.
        """
        chunks = chunk_message(text)
        _ = await interaction.response.send_message(chunks[0])
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk)

    async def update_activity(self) -> None:
        """Keep the bot's presence refreshed while connected.

        Cycles through `bot_params.activities` one at a time, refreshing hourly
        -- falls back to a `/help`-pointer default when none are configured
        (an empty list is the out-of-the-box `config.json` value).
        """
        await self.wait_until_ready()

        activities = self.custom_config.bot_params.activities or ["/help for commands"]
        index = 0

        while not self.is_closed():
            await self.change_presence(activity=discord.Game(name=activities[index % len(activities)]))
            index += 1
            await asyncio.sleep(3600)  # task runs every 3600 seconds

    @override
    async def setup_hook(self) -> None:
        """Open the shared HTTP session, record startup state, and start the presence task."""
        self.http_session = aiohttp.ClientSession()
        self.start_time = time.monotonic()
        host_metrics.prime_cpu_load()

        app_info = await self.application_info()
        self.owner_id = app_info.owner.id

        self.bg_task = self.loop.create_task(self.update_activity())

    @override
    async def close(self) -> None:
        """Close the shared HTTP session before shutting down the Discord connection."""
        if self.http_session is not None:
            await self.http_session.close()
        await super().close()

    async def on_ready(self) -> None:
        """Discover modules, publish slash commands, and log active guilds.

        Slash commands are synced per-guild (not globally) since every guild
        this bot is in is already known upfront -- a per-guild sync publishes
        instantly, while a global sync can take up to an hour to propagate.
        `copy_global_to` is required before that: commands registered via
        `self.tree.command()` with no `guild=` are *global* commands, and
        `tree.sync(guild=...)` only syncs a guild's own local command set --
        without copying the global set into it first, there's nothing there to
        sync (discord.py returns an empty list, not an error).
        """
        logger.info("Logged on as %s", self.user)

        await self.get_modules()

        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Synced %d slash command(s) to %s", len(synced), guild.name)
            logger.info("###############################################################")
            logger.info("%s added to %s by %s at %s", self.user, guild.name, guild.owner, guild.me.joined_at)

    async def on_message(self, message: discord.Message) -> None:
        """Dispatch an incoming Discord message to the matching command, if any.

        Args:
            message: The incoming message.
        """
        log_message(message)

        if self.user is None or message.author == self.user:
            return

        if message.content.startswith(self.user.mention):
            async with message.channel.typing():
                await self._send(message.channel, message.author.mention)
            return

        parsed = parse_command(message.content, self.prefix)
        if parsed is None:
            return

        command_name, command_args = parsed
        command_name = command_name.lower()

        if command_name in self.commands:
            assert self.http_session is not None, "on_message() fired before setup_hook() opened http_session"

            async with message.channel.typing():
                command = self.commands[command_name]
                resp = await process_command(self.http_session, self.modules_base_route, command, command_args)
                self.commands_run += 1

                files = None
                if command.attachment_paths:
                    attachments = await fetch_attachments(self.http_session, self.modules_base_route, command)
                    if attachments:
                        files = [discord.File(io.BytesIO(content), filename=filename)
                                for content, filename in attachments]

                await self._send(message.channel, resp, files)

        else:
            async with message.channel.typing():
                suggestions = suggest_command(command_name, self.commands)
                if suggestions:
                    guesses = ', '.join(f'`{self.prefix}{name}`' for name in suggestions)
                    text = f"Unknown command `{self.prefix}{command_name}` -- did you mean {guesses}?"
                else:
                    text = 'Use `/help` or `@me`'
                await self._send(message.channel, text)
