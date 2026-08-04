# LURAMINAKIT

Trying to make a fun Discord bot...

It's still a "work in progress" as of now... And there is a lot of room for improvement.

LuraminaKIT is the Discord-facing half of this repository. It doesn't implement commands itself — on startup (and via `on_ready`), it polls every module listed in its `config.json` at that module's `/url-list` route (see [modulesKIT](../modulesKIT) and the shared [`contractsKIT`](../contractsKIT) contract), builds a command table from what each module advertises, and proxies matching Discord messages to the right module over HTTP.

## HOW IT WORKS

Two independent command surfaces exist side by side:

- **`!`-prefixed module commands** (`config.json`'s `bot_params.cmd_prefix`, default `"!"`) — e.g. `!quote` looks up a command named `quote` discovered from a module. Any text typed after the command name is forwarded as positional arguments to the module's route, matched in order against the query parameters that module advertised. This is the *only* interface a modulesKIT module ever needs to implement — see [modulesKIT](../modulesKIT) and the shared [`contractsKIT`](../contractsKIT) contract.
- **Slash commands** — `/help`, `/status`, `/reload` are LuraminaKIT's own built-in utility commands, registered directly on a `discord.app_commands.CommandTree` in `discord_client.py` (`_register_slash_commands`) and synced per-guild on `on_ready`. They exist entirely outside the module-discovery/HTTP-proxy mechanism above: a modulesKIT module cannot register one and doesn't need to for anything built so far. The reason is architectural, not a missing feature — a slash command needs a live connection to Discord's own gateway to respond to, and only this process (LuraminaKIT itself) ever holds one; a modulesKIT service is a plain stateless HTTP microservice with no Discord connection of its own. `/reload` additionally checks the caller against the bot application's owner (fetched once via `application_info()` in `setup_hook`) before running.

Other things worth knowing:

- `@<bot>` (a plain mention) gets a simple mention back.
- Modules are matched to LuraminaKIT via the `modules` list in `config.json` (`name`/`port`/`prefix` must match the corresponding modulesKIT `config.json` entry).
- Every outgoing message is split to fit Discord's 2000-character limit before sending (`modules/helpers/message_chunking.py`), using markdown-aware boundaries (headers, code fences, lists) rather than a blind character slice — useful now that responses can come from modules whose output length varies a lot (e.g. a future LLM-backed module).
- A single shared `aiohttp.ClientSession` (`DiscordClient.http_session`) is used for every HTTP call to every module for the process's whole life, rather than opening a new one per request.
- Only one LuraminaKIT process can hold the same Discord token at a time — a PID-file lock (`modules/helpers/singleton_lock.py`) makes a second instance abort loudly on startup instead of both silently receiving and double-handling every Discord message.

The parsing/dispatch/logging logic for the `!`-prefixed path lives in `modules/helpers/command_dispatch.py`, kept separate from `modules/clients/discord_client.py`, which wires Discord's event hooks (both the message-based and slash-command ones) to that logic and performs the actual Discord API calls.

## INSTALLATION

See [`INSTALL.md`](INSTALL.md) for step-by-step setup instructions (Windows, Debian/Ubuntu, Arch Linux).

## CONFIGURATION

Configuration is split across two sources, merged at startup (`modules/helpers/settings.py`):

- **`config.json`** — bot behavior and the modules to poll. Not a secret, safe to commit.
- **`.env`** — the Discord bot token, kept out of `config.json` on purpose. Copy the template and fill it in:
  ```bash
  cp .env.example .env
  ```
  then edit `.env` and set `DISCORD_TOKEN=<your token>`. `.env` is gitignored; `.env.example` (empty, committed) documents what's expected. If `.env` is missing, a warning is logged and the token falls back to empty — the bot will start but fail to log in to Discord.

## RUNNING

With the shared venv active, and at least one modulesKIT module already running:

```bash
python main.py
```

The launcher resolves `config.json`, `.env`, and `logs/` relative to its own location (not your current directory). Pass `-c /path/to/other-config.json` to use a different config file.

## CONTRIBUTING

See [`HOWTO.md`](HOWTO.md) for how the code is organized, how to add a new secret, and how to test dispatch logic without a live Discord connection.

## VERSIONS

- 0.1.0-alpha: First release

## TABLE OF CONTENT

<!-- TOC -->

- [LURAMINAKIT](#luraminakit)
  - [HOW IT WORKS](#how-it-works)
  - [INSTALLATION](#installation)
  - [CONFIGURATION](#configuration)
  - [RUNNING](#running)
  - [CONTRIBUTING](#contributing)
  - [VERSIONS](#versions)
  - [TABLE OF CONTENT](#table-of-content)

<!-- /TOC -->
