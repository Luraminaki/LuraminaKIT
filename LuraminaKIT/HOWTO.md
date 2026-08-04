# How to contribute to LuraminaKIT

If you just want to **add a new modulesKIT module**, you don't need to change anything here — see [`modulesKIT/HOWTO.md`](../modulesKIT/HOWTO.md) and add an entry to `LuraminaKIT/config.json`'s `modules` list. This file is for changing the bot's own behavior.

If you haven't set up the project yet, see [`INSTALL.md`](INSTALL.md) first.

## Where the logic lives

`modules/clients/discord_client.py` is deliberately thin — it wires Discord's event hooks to logic that lives elsewhere, and performs the actual Discord API calls (typing indicator, sending messages):

- **`modules/helpers/command_dispatch.py`** — parsing (`parse_command`), discovery bookkeeping (`CommandEntry`, `build_commands`), calling a module (`process_command`), typo suggestions (`suggest_command`), and the `/help`/`/status` reply builders (`build_help_text`/`build_status_text`). No `discord.Message`/`Client` coupling except `log_message`, which only reads from a `discord.Message`.

  `build_help_text` is a **drill-down tree view**, not a flat list — it's built by splitting each command's dotted name on `.`, not by which module advertised it. `/help` alone shows only the first segment of every command (e.g. `tb1`, `quote`); `/help path:tb1` shows tb1's own next segment (`utils`, `kino`, ...); `/help path:tb1.kino` shows tb1.kino's actual commands. This is what keeps the top-level listing from growing forever as a module adds more commands — a module with dozens of commands should namespace them with dots (`tb1.kino.bahamut`, not `tb1kinobahamut`) to get this for free. `GenericViews.add_route` (modulesKIT) enforces that a dotted command name/alias starts with its own module's name, so one module's commands can never show up filed under another's in the tree.
- **`modules/clients/discord_client.py`**, `_register_slash_commands` — where `/help`/`/status`/`/reload` themselves are defined and registered on `self.tree`. This lives here, not in `command_dispatch.py`, because `discord.app_commands` requires binding to a live `discord.Client`/`CommandTree` instance — unlike everything else in `command_dispatch.py`, it can't be exercised without a real (or heavily mocked) Discord connection. If you're adding a 4th slash command, this is where it goes; if you're adding a module command, you don't touch this file at all (see [`modulesKIT/HOWTO.md`](../modulesKIT/HOWTO.md)).
- **`modules/helpers/message_chunking.py`** — `chunk_message`, splits any outgoing text to fit Discord's 2000-character limit at markdown-aware boundaries. `DiscordClient._send()`/`_send_interaction()` route *every* outgoing message (prefix or slash) through it, so you don't need to think about message length when adding a new reply — just return the full text.
- **`modules/helpers/settings.py`** — `Settings` (pydantic), `.env` + `config.json` loading/merging.
- **`modules/helpers/req_mngr.py`** — the HTTP client used to call modulesKIT routes, parses responses into `StandardResponse`. Every function takes a shared `aiohttp.ClientSession` as its first argument (`DiscordClient.http_session`, opened once in `setup_hook`) rather than opening its own per call.
- **`modules/helpers/singleton_lock.py`** — `SingleInstanceLock`, a PID-file guard so a second LuraminaKIT process (same token) aborts loudly instead of silently double-handling every Discord message. Wired into `main.py`'s `__main__` block, not something module/command code needs to touch.

**Rule of thumb**: if what you're adding doesn't need a `discord.Message`/`Client`/`channel`/`Interaction` object, it belongs in `command_dispatch.py` (or a new helper module next to it), not in `discord_client.py`. Keeping Discord API calls confined to `discord_client.py` is what makes the dispatch logic testable without a live gateway connection (see below) -- slash commands are the one exception, since `app_commands` itself demands that coupling.

## Adding a new secret

Follow the pattern already set up for the Discord token in `settings.py`:

1. Add a field to `Settings` (e.g. `some_api_key: str = ''`) — pydantic-settings matches it to an environment variable of the same name, case-insensitively (`SOME_API_KEY`).
2. Add `SOME_API_KEY=` to `.env.example` (committed, empty) and your own `.env` (gitignored, real value).
3. Never add it to `config.json` — that file is meant to be safe to commit.

## Testing without a live Discord connection

`discord.Client.__init__` needs a running event loop and validates its arguments strictly (e.g. `intents` must be a real `discord.Intents`, not a mock), so tests bypass it with `__new__` and set only the attributes the code under test actually needs. `self.user` is a read-only property on `discord.Client`, so override it on a throwaway subclass:

```python
import asyncio
from unittest.mock import MagicMock
from LuraminaKIT.modules.clients.discord_client import DiscordClient
from LuraminaKIT.modules.helpers.settings import Settings, ModuleEntry

class TestClient(DiscordClient):
    @property
    def user(self):
        return MagicMock(mention='<@BOT_ID>')

client = TestClient.__new__(TestClient)
client.custom_config = Settings(modules=[ModuleEntry(name='anyquotes', port=8001, prefix='/api/anyquotes')])
client.prefix = '!'
client.commands = {}
client.modules_base_route = 'http://127.0.0.1'
client.modules_api_routes = '/url-list'

class _AsyncCtx:
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False

async def main():
    await client.get_modules()          # hits a real running modulesKIT module over HTTP
    message = MagicMock()
    message.guild = None
    message.attachments = []
    message.content = "!quote"           # command name = the route's advertised name
    message.author.name = "tester"
    message.channel.typing = lambda: _AsyncCtx()
    sent = []
    async def fake_send(text):
        sent.append(text)
    message.channel.send = fake_send

    await client.on_message(message)
    print(sent)

asyncio.run(main())
```

This exercises the real `get_modules()`/`on_message()`/`_send()` code path — including chunking, if the response is long — against a real modulesKIT service, with nothing about Discord itself faked except the parts `discord.py` won't let you construct without a gateway connection.

This pattern is for the `!`-prefixed path specifically. `/help`/`/status`/`/reload` go through `discord.Interaction` instead of `discord.Message`, which isn't something you construct by hand the same way — verifying a slash command change means an actual restart against a real Discord connection (see the root `HOWTO.md`'s "before committing" checklist).

## Style

Same conventions as the rest of the repo — see the root [`HOWTO.md`](../HOWTO.md).

## Committing

```
feat(LuraminaKIT): <description>
fix(LuraminaKIT): <description>
```
