#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command discovery bookkeeping and dispatch logic, kept separate from Discord API glue."""

import difflib
import logging
import urllib.parse

import aiohttp
import discord

from contractsKIT import StatusFunction, ModuleManifest, ParamDescriptor, RouteDescriptor, CategoryHelp
from LuraminaKIT.modules.helpers import req_mngr

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Hard cap on a category's *short* hint (its line in a parent listing) -- a
# safety net, not the primary control: short hints are meant to be
# hand-written short already (see command_help.json's "short" field), but this
# guarantees a tree listing stays bounded even if one isn't. Doesn't apply to
# the full `summary` shown when a category is drilled all the way into.
MAX_CATEGORY_HINT_LENGTH = 80
_TRUNCATION_MARKER = ' [...]'


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


def _format_param(param: ParamDescriptor) -> str:
    """Render one query param as `<name>`/`[name]`, tagged with its type when non-default.

    `type_` defaults to `'str'` on most params (the common case, e.g. a free-text
    `query`), so only showing it when it differs (`int`/`bool`/...) keeps the
    usual case uncluttered while still surfacing the cases where getting the
    type wrong would actually break the call (e.g. `!tb1roll`'s `pulls`/`pof`).

    Args:
        param: The param to render.

    Returns:
        `<name>`/`[name]`, or `<name:type>`/`[name:type]` if `type_ != 'str'`.
    """
    label = param.name if param.type_ == 'str' else f"{param.name}:{param.type_}"
    return f"<{label}>" if param.required else f"[{label}]"


def _format_usage(command: CommandEntry, prefix: str) -> str:
    """Render a single command's usage line: `prefix name <required> [optional]`,
    plus its aliases if it has any.

    Args:
        command: The command to render.
        prefix: The bot's command prefix (e.g. `"!"`).

    Returns:
        The command's invocation, e.g. `` `!tb1roll <pulls:int> <pof:bool> <base>` (alias: `!roll1`) ``.
    """
    tokens = [f"{prefix}{command.name}", *(_format_param(param) for param in command.query_params)]
    usage = f"`{' '.join(tokens)}`"

    if command.aliases:
        usage += " (alias: " + ', '.join(f"`{prefix}{alias}`" for alias in command.aliases) + ")"

    return usage


def _canonical_commands(commands: dict[str, CommandEntry]) -> list[CommandEntry]:
    """Every discovered command once, de-duplicated across its name and aliases.

    `commands` has one dict entry per name *and* per alias, all pointing at the
    same `CommandEntry` -- this keeps only the entry actually keyed by its own
    canonical name.

    Args:
        commands: Currently known commands.

    Returns:
        One `CommandEntry` per real command.
    """
    return [command for name, command in commands.items()
            if name != 'get_all_urls' and name == command.name]


def suggest_command(typed: str, commands: dict[str, CommandEntry], limit: int = 3, cutoff: float = 0.6) -> list[str]:
    """Suggest known command names closest to a mistyped one.

    Only covers `!`-prefixed module commands -- `/help`/`/status`/`/reload` are
    slash commands now, in their own separate namespace Discord itself handles
    autocomplete for, so there's nothing to typo-correct there. Tries canonical
    names first (the form shown in `/help`). Only falls back to also matching
    against aliases if nothing canonical scored well enough -- aliases catch
    more typos, but tend to surface several near-duplicate suggestions for the
    same underlying command, which is worse when a canonical match exists.

    Args:
        typed: The mistyped command name, as the user typed it (already
            lowercased by the caller, matching how `commands` is keyed).
        commands: Currently known commands, keyed by every name/alias (see `build_commands`).
        limit: Max number of suggestions to return.
        cutoff: Minimum `difflib` similarity ratio (0-1) to count as a match --
            see `difflib.get_close_matches`.

    Returns:
        Up to `limit` suggested command names, closest first, or `[]` if
        nothing scored above `cutoff`.
    """
    canonical_names = [command.name for command in _canonical_commands(commands)]
    matches = difflib.get_close_matches(typed, canonical_names, n=limit, cutoff=cutoff)
    if matches:
        return matches

    return difflib.get_close_matches(typed, list(commands.keys()), n=limit, cutoff=cutoff)


def _next_segment(name: str, path: str) -> str:
    """The dot-segment of `name` immediately after `path`.

    Args:
        name: A canonical command name, e.g. `tb1.kino.bahamut`.
        path: The path already drilled into, e.g. `tb1` or `''` for the root.

    Returns:
        The next segment, e.g. `kino` for `name="tb1.kino.bahamut"`, `path="tb1"`.
    """
    remainder = name[len(path) + 1:] if path else name
    return remainder.split('.', 1)[0]


def _render_leaf(command: CommandEntry, prefix: str) -> str:
    """Render one command as a single bulleted usage + description line.

    Kept deliberately compact -- full per-parameter detail (hints, types,
    required/optional) lives in `_render_command_card`, one `/help
    path:<command>` away, rather than repeated inline for every command in
    a listing that might show a dozen of them at once.

    Args:
        command: The command to render.
        prefix: The bot's command prefix (e.g. `"!"`).

    Returns:
        A single markdown bullet line.
    """
    usage = _format_usage(command, prefix)
    return f"- {usage} -- {command.description}" if command.description else f"- {usage}"


def _truncate(text: str, max_len: int) -> str:
    """Hard-cap `text` at `max_len` characters, marking it if cut.

    Args:
        text: The text to cap.
        max_len: Maximum length of the returned string, marker included.

    Returns:
        `text` unchanged if it already fits, else cut short with a trailing
        `` [...] `` marker whose own length counts toward `max_len`.
    """
    if len(text) <= max_len:
        return text
    return text[:max_len - len(_TRUNCATION_MARKER)].rstrip() + _TRUNCATION_MARKER


def _render_param_detail(param: ParamDescriptor) -> str:
    """Render one query param as a bulleted `name (type, required/optional)` line.

    Args:
        param: The param to render.

    Returns:
        A bullet line like `- name (type, required)`, plus ` -- hint` if the
        param has one. `type` is omitted when it's the default `'str'`,
        matching `_format_param`.
    """
    tags = [] if param.type_ == 'str' else [param.type_]
    tags.append('required' if param.required else 'optional')
    base = f"- `{param.name}` ({', '.join(tags)})"
    return f"{base} -- {param.hint}" if param.hint else base


def _render_command_card(command: CommandEntry, prefix: str) -> str:
    """Render one command as a full "info card" -- usage (with aliases,
    doubling as the title), description, and one line per parameter.

    Used when `/help path:<command>` names an exact command with nothing
    nested under it, i.e. asking about one specific command directly -- as
    opposed to `_render_leaf`'s compact one-liner, used when a command is just
    one entry among several other commands/categories being listed together.

    Args:
        command: The command to render.
        prefix: The bot's command prefix (e.g. `"!"`).

    Returns:
        Markdown text: the usage line as a fenced code block (doubling as the
        card's title -- no separate bold heading), aliases, the description
        (if any), and a `**Parameters**` block (only if the command takes any).
        The usage line is a fenced block rather than inline code specifically
        so Discord's one-click copy button shows on it -- this is the one
        place in `/help` spread out enough for a block-level element not to
        break a compact line (unlike `_render_leaf`'s tree lines).
    """
    usage_tokens = [f"{prefix}{command.name}", *(_format_param(param) for param in command.query_params)]
    usage_block = [f"```\n{' '.join(usage_tokens)}\n```"]
    if command.aliases:
        usage_block.append("Alias: " + ', '.join(f"`{prefix}{alias}`" for alias in command.aliases))
    blocks = ['\n'.join(usage_block)]

    if command.description:
        blocks.append(command.description)

    if command.query_params:
        param_block = ['**Parameters**', *(_render_param_detail(param) for param in command.query_params)]
        blocks.append('\n'.join(param_block))

    return '\n\n'.join(blocks)


def build_help_text(commands: dict[str, CommandEntry], prefix: str, path: str = '') -> str:
    """Render discovered commands for the `/help` reply, drilling into `path`.

    Commands are grouped by splitting their dotted name on `.`, not by which
    module advertised them: `/help` alone shows only the first segment of every
    command (e.g. `tb1`, `quote`); `/help path:tb1` shows tb1's own next segment
    (`utils`, `kino`, ...); `/help path:tb1.kino` shows tb1.kino's actual
    commands. A segment with no further children (e.g. `quote`, or
    `tb1.kino.bahamut`) is rendered as a full command line at whatever depth it's
    reached, instead of a collapsed category -- this is what keeps the top-level
    listing from growing forever as more dotted commands are added. Naming one
    specific command exactly (e.g. `/help path:tb1.utils.roll`) instead renders
    that command alone as a full info card (`_render_command_card`) -- title,
    description, usage, and one line per parameter -- rather than the compact
    single-line form used everywhere else.

    `commands` only ever holds module-discovered (`!`-prefixed) commands --
    `/help`/`/status`/`/reload` themselves are registered directly on the bot's
    slash command tree, not via a module's `/url-list`, so they'd otherwise be
    entirely invisible here. The root-level listing calls them out explicitly
    instead, since "the help command doesn't mention its own siblings" is exactly
    the kind of gap that makes a help command less useful than it should be.

    Args:
        commands: Currently known commands.
        prefix: The bot's command prefix (e.g. `"!"`), shown in usage lines.
        path: Dot-separated path already drilled into, e.g. `"tb1.kino"`. Empty
            (the default) means the root listing.

    Returns:
        Markdown text for the requested level, or a "nothing found" message if
        `path` doesn't match any known command or category.
    """
    canonical = _canonical_commands(commands)

    if not canonical:
        return "No commands discovered yet -- is a modulesKIT module running?"

    # `commands` is keyed by every name *and* alias (see `build_commands`) -- resolve
    # an alias to its canonical name first, so `/help path:<alias>` (e.g. `tb1.r`)
    # finds the same entry `/help path:<canonical name>` (`tb1.utils.roll`) would.
    if path in commands:
        path = commands[path].name

    exact = next((command for command in canonical if path and command.name == path), None)
    nested = [command for command in canonical if path and command.name.startswith(f"{path}.")] \
        if path else canonical

    if exact is None and not nested:
        return f"No commands found under `{path}` -- try `/help` with no path."

    # A pure single-command lookup (nothing nested under it) gets the full
    # "info card" layout instead of the compact tree-listing format below,
    # which is built for showing several commands/categories at once.
    if exact is not None and not nested:
        return _render_command_card(exact, prefix)

    # The `exact` leaf line (only present in the hybrid case: a command that's
    # *also* a category prefix for other commands) always leads, before the
    # Categories/Commands split below.
    lines = [_render_leaf(exact, prefix)] if exact is not None else []

    groups: dict[str, list[CommandEntry]] = {}
    for command in nested:
        groups.setdefault(_next_segment(command.name, path), []).append(command)

    # Split into two labeled sections instead of one interleaved list, and show
    # a category's *short* hint (truncated, hard-capped) rather than spelling out
    # every child command by name -- both trims needed to keep a big listing
    # (e.g. `/help path:tb1`) under Discord's 2000-character limit without
    # relying on the message chunker to split it across multiple messages.
    category_lines: list[str] = []
    command_lines: list[str] = []

    for segment in sorted(groups):
        members = groups[segment]
        full_path = f"{path}.{segment}" if path else segment

        if len(members) == 1 and members[0].name == full_path:
            command_lines.append(_render_leaf(members[0], prefix))
        else:
            category_help_entry = next((member.category_help[full_path] for member in members
                                        if full_path in member.category_help), None)
            short_hint = ''
            if category_help_entry is not None:
                short_hint = _truncate(category_help_entry.short or category_help_entry.summary,
                                       MAX_CATEGORY_HINT_LENGTH)
            hint_suffix = f" -- {short_hint}" if short_hint else ""
            category_lines.append(f"- **{full_path}** ({len(members)}){hint_suffix} (`/help path:{full_path}`)")

    if category_lines:
        lines.append('\n'.join(["**Categories**", *category_lines]))
    if command_lines:
        lines.append('\n'.join(["**Commands**", *command_lines]))

    if path:
        # Same category_help lookup the collapsed child-line above uses, but for
        # `path` itself -- without this, drilling all the way into a category only
        # ever shows its bare name, never the explanation shown one level up. Uses
        # the full `summary` (not the tree line's truncated `short`), since this
        # is the one place with room for it.
        relevant = ([exact] if exact is not None else []) + nested
        category_help_entry = next((entry.category_help[path] for entry in relevant if path in entry.category_help), None)
        category_hint = category_help_entry.summary if category_help_entry is not None else ''
        header = f"**{path}** -- {category_hint}" if category_hint else f"**{path}**"
        return '\n\n'.join([header, *lines])

    # Grouped by the module that actually advertised each command, not by the
    # command's own first dot-segment -- those two agree for a module like tb1
    # (`tb1.char` etc.) but not for one like anyquotes, whose single `quote`
    # command doesn't share its module's name at all.
    modules_seen: dict[str, str] = {}
    for command in canonical:
        _ = modules_seen.setdefault(command.module_name, command.module_description)
    module_lines = [f"- **{name}** -- {description}" if description else f"- **{name}**"
                    for name, description in sorted(modules_seen.items())]

    preamble = '\n'.join([
        "**Modules**",
        *module_lines,
        "",
        "**Available commands**",
        "`/help [path]`, `/status`, `/reload` -- bot utility commands (slash-only; `/reload` is owner-only)",
        f"Module commands below use the `{prefix}` prefix instead (not slash), e.g. `{prefix}tb1.char Z`:",
    ])
    return '\n\n'.join([preamble, *lines])


def _format_uptime(seconds: float) -> str:
    """Render a duration as a compact `1d 2h 3m` string.

    Args:
        seconds: Duration in seconds.

    Returns:
        The formatted duration, always including minutes even if `0m` (so a
        freshly-started bot doesn't report a blank uptime).
    """
    total = int(seconds)
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")

    return ' '.join(parts)


def build_status_text(guild_count: int, commands_run: int, uptime_seconds: float, memory_mb: float) -> str:
    """Render the `/status` reply.

    Args:
        guild_count: Number of guilds the bot is currently in.
        commands_run: Number of module commands successfully dispatched since startup.
        uptime_seconds: Seconds since the bot's `setup_hook` ran.
        memory_mb: The bot process's own resident memory, in MiB -- not the
            modulesKIT services it talks to, which run as separate processes.

    Returns:
        Markdown-formatted status report.
    """
    return '\n'.join(["**LuraminaKIT status**",
                      f"- Uptime: {_format_uptime(uptime_seconds)}",
                      f"- Commands run: {commands_run}",
                      f"- Connected servers: {guild_count}",
                      f"- Memory usage: {memory_mb:.1f} MB"])


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
