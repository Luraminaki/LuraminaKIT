# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A monorepo for a Discord bot, split into three independently-versioned Python packages, each with its own `pyproject.toml`/`README.md`/`HOWTO.md`/`INSTALL.md`:

- **`contractsKIT`** — shared pydantic contracts (`StandardResponse[T]`, `ModuleManifest`/`RouteDescriptor`/`ParamDescriptor`, rotating-log setup). No launcher of its own.
- **`modulesKIT`** — one small FastAPI service per bot "module" (currently `anyquotes`, `tb1`, `llm`), each its own process, each advertising its own routes at `/api/<module>/url-list`.
- **`LuraminaKIT`** — the Discord bot itself: discovers modulesKIT modules at startup over HTTP and proxies matching messages to them. Never hard-codes a module's routes.

```
Discord  <-->  LuraminaKIT  --HTTP-->  modulesKIT/<module>  (FastAPI, one process per module)
                    |                         |
                    +------ contractsKIT ------+
                    (shared StandardResponse / ModuleManifest contract)
```

Adding a new module requires zero changes to LuraminaKIT's code — just a new entry in `LuraminaKIT/config.json`. See `modulesKIT/HOWTO.md` for the full worked example (building an `echo` module from scratch).

## Commands

**Install** (one shared venv, all three projects editable, `contractsKIT` first since the other two depend on it):
```bash
python3.12 -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\Activate.ps1 on Windows
pip install -e ./contractsKIT -e ./modulesKIT -e ./LuraminaKIT
```

**Run everything at once** (discovers modules from `modulesKIT/config.json`, honors each module's `auto_start` flag, bot's logs stream to the terminal, Ctrl+C tears down modules cleanly):
```bash
python run.py
```

**Run one piece directly** (each launcher resolves its own `config.json`/`.env`/`data/`/`logs/` relative to its own file location, so these work from anywhere):
```bash
python modulesKIT/main_anyquotes.py   # port 8001 by default
python modulesKIT/main_tb1.py         # port 8002 by default
python LuraminaKIT/main.py            # the bot itself; needs LuraminaKIT/.env's DISCORD_TOKEN
```

**Verify a modulesKIT route directly** (no Discord needed):
```bash
curl "http://127.0.0.1:8001/api/anyquotes/url-list"
curl "http://127.0.0.1:8001/api/anyquotes/quote"
```

**Type-check** (no local install; every project ships `py.typed`):
```bash
npx -y basedpyright .
```
There is no repo-configured lint/format tool (no `.flake8`/`ruff.toml`/lint section in any `pyproject.toml`) — `basedpyright` run ad hoc via `npx` is the established way this codebase gets checked. It's noticeably stricter than plain `pyright`'s default mode (`reportAny`, `reportUnannotatedClassAttribute`, etc.) — a clean `pyright` run is not the same as a clean `basedpyright` run.

**Tests**: none exist yet (explicitly deferred). `LuraminaKIT/HOWTO.md`'s "Testing without a live Discord connection" section documents the pattern for when they're added — bypassing `discord.Client.__init__` via `__new__` and driving `get_modules()`/`on_message()` against a real running modulesKIT service.

## Architecture

### Module discovery and dispatch

A modulesKIT module's `GenericViews.add_route(...)` both registers a FastAPI route *and* records a `RouteDescriptor` (path, name, description, params, aliases, attachment paths) for advertisement at that module's `/url-list`. `LuraminaKIT.get_modules()` polls every configured module's `/url-list`, parses the `ModuleManifest`, and builds a flat `command_name -> CommandEntry` map (`command_dispatch.build_commands`) — one dict entry per route name *and* per alias, all pointing at the same entry. A user's `!`-prefixed message gets its command name looked up in that map and proxied over HTTP (`process_command`); the response text (and any `attachment_paths` files) gets sent back, chunked to Discord's 2000-char limit by `message_chunking.chunk_message`.

**Slash commands are a completely separate mechanism** from the above, registered directly on `discord_client.py`'s `app_commands.CommandTree` (`/help`, `/status`, `/reload`). A modulesKIT module can never implement a slash command — that requires a live `discord.Client`/gateway connection, which only LuraminaKIT holds. Every module command is `!`-prefixed HTTP-proxy only; that's the one interface a module needs to implement.

A dotted command name (e.g. `tb1.kino.bahamut`) **must start with its own module's name** — `add_route` raises `ValueError` at registration time otherwise, so one module's commands can never show up filed under another's in `/help`'s drill-down tree (`command_dispatch.build_help_text`, grouped by splitting each command's dotted name on `.`, not by which module advertised it).

### `command_help.json` — optional, JSON-driven `/help` wording

A module can drop `data/<module>/command_help.json` to supply a command's description/per-parameter hints, and a short-vs-full explanation for a dotted category prefix (e.g. `"tb1.special"`), without touching Python. Loaded once in `GenericViews.__init__` (`modulesKIT/modules/helpers/command_help.py`); `add_route` merges a matching entry over the code's own `description=`/`params=` when present, falling back to them otherwise. Entirely optional per module — no file means no hints, nothing breaks. See `modulesKIT/data/tb1/command_help.json` for a real example and `modulesKIT/HOWTO.md`'s step 9.

### The `StandardResponse[T]` generic-classmethod gotcha

Every modulesKIT route returns `StandardResponse[T].ok(data)` / `StandardResponse[T].fail(error)` — **always explicitly parameterized** (`StandardResponse[str].ok(...)`, not bare `StandardResponse.ok(...)`). The bare form runs identically at runtime but is a known basedpyright inference gap: accessing a `@classmethod` through an unparameterized `Generic[T]` class collapses `T` to `Unknown` and cascades into dozens of spurious warnings at every call site. This isn't a style nitpick — it measurably changes the basedpyright warning count.

### Data-driven, not hardcoded

The established pattern for anything with more than a handful of entries is a JSON file in `data/<module>/`, not a Python literal: `pact.json` (rates/pools), `events.json` (one entry per TB1 event/boss info card — `TB1View.__init__` registers one route per entry automatically via a shared handler factory, so adding an event is a pure data change), `characters.json`/`monsters.json`/`items.json`/`buddy.json` (loaded via `Model.model_validate(entry)`, not `Model(**entry)` — the latter breaks per-field type-checking when the source dict is `dict[str, object]`). `command_help.json` follows the same philosophy for `/help` wording.

### Config split

Two separate `config.json` files that look similar but serve different purposes: `modulesKIT/config.json` configures how each module *runs* (port, description, `auto_start`, per-module `data`); `LuraminaKIT/config.json` configures what LuraminaKIT *polls* (name/port/prefix per module it should discover). They must stay in sync by hand when adding a module (`modulesKIT/HOWTO.md` walks through both).

### Everything is a live-restart, not a hot-reload

There's no code-reload mechanism; verifying a change means byte-compiling (`python -m py_compile <file>`), restarting the affected process(es), and re-checking via `curl` against the module directly and/or a live Discord round-trip. `/reload` (owner-only slash command) re-polls every module's `/url-list` without a full bot restart, for picking up route/alias changes in an already-running module.

## Commit habits

- **Only commit/push when explicitly asked.** Land the actual code/doc changes first and let them be reviewed in-conversation; commit/push is its own separate step the user asks for afterward, not something that happens automatically once work is done.
- [Conventional Commits](https://www.conventionalcommits.org/), matching the existing log exactly: `feat`/`fix`/`chore`/`docs`, scoped to the project touched when the change is one project's alone (`feat(modulesKIT): ...`, `fix(LuraminaKIT): ...`), comma-scoped when it spans more than one (`fix(modulesKIT,LuraminaKIT): ...`), or unscoped for a monorepo-wide change that doesn't cleanly belong to one project (`feat: add one-command launcher for the bot and its modules`).
- One commit per cohesive unit of work, not one per file and not one per conversational turn — a multi-file feature built up across many turns (e.g. the `command_help.json` mechanism) is still a single commit once it's ready. Genuinely unrelated changes that happened to land around the same time get split into separate commits instead of bundled together.
- Bodies explain *why*, not just *what* — see the existing log for the expected depth (a short summary line, then paragraphs/bullets covering the reasoning, what was verified, and any bugs found along the way). A one-line message is fine only for a genuinely one-line change.
- Review what's actually staged before committing (`git status`/`git diff --stat`); don't reach for `git add -A`/`git add .` without checking the result first. A `CODE_REVIEW.md` scratch file once got committed by accident this way and had to be `git rm --cached` + amend + force-push (with `--force-with-lease`, and only because the user explicitly asked for that specific fix) to remove from an already-pushed history.
