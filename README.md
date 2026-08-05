# DISCORD_BOT

A small monorepo for a fun Discord bot, split into independently-versioned projects:

- [`contractsKIT`](contractsKIT) — shared pydantic contracts (`StandardResponse`, module manifests, rotating-log setup) that let the other two projects agree on a wire format without hard-coding each other's internals. See [`contractsKIT/README.md`](contractsKIT/README.md).
- [`modulesKIT`](modulesKIT) — one small FastAPI service per bot "module" (`anyquotes`, `tb1`, `llm`), each advertising its own routes so the bot can discover them at runtime. See [`modulesKIT/README.md`](modulesKIT/README.md).
- [`LuraminaKIT`](LuraminaKIT) — the Discord bot itself: discovers modulesKIT modules on startup and proxies matching messages to them over HTTP. See [`LuraminaKIT/README.md`](LuraminaKIT/README.md).

It's still a "work in progress" as of now... And there is a lot of room for improvement.

## THIRD-PARTY CONTENT

The `tb1` module (in `modulesKIT`) surfaces game data, wiki links, and images sourced from the [Terra Battle Wiki](https://terrabattle.fandom.com) and the game itself. This is an unofficial, non-commercial fan project — that content remains the property of its respective owners (Mistwalker/GungHo, and the wiki's own contributors, credited where used). If you're a rights holder and want something removed, open an issue and it'll come down.

## HOW THE PIECES FIT TOGETHER

```
Discord  <-->  LuraminaKIT  --HTTP-->  modulesKIT/<module>  (FastAPI, one process per module)
                    |                         |
                    +------ contractsKIT ------+
                    (shared StandardResponse / ModuleManifest contract)
```

A modulesKIT module never needs to know LuraminaKIT exists, and LuraminaKIT never hard-codes a module's routes — it reads them from `/api/<module>/url-list` at startup, using the shared contract types from `contractsKIT`. Adding a new module is meant to require no changes to LuraminaKIT's code, just a new entry in its `config.json`.

**Slash commands are a separate, LuraminaKIT-only thing.** Every command a modulesKIT module advertises (`tb1.char`, `!quote`, ...) is dispatched via the `!`-prefixed HTTP-proxy path shown above — that's the only interface a module ever needs to implement. LuraminaKIT's own `/help`, `/status`, `/reload` are registered directly on its Discord slash-command tree (`LuraminaKIT/modules/clients/discord_client.py`) and never touch a modulesKIT module or the HTTP-proxy path at all. A module cannot register a slash command today, and doesn't need to for anything built so far — see the `LuraminaKIT` README's "HOW IT WORKS" section for why (in short: slash commands require a live connection to Discord's gateway, which only LuraminaKIT itself has).

## INSTALLATION

See [`INSTALL.md`](INSTALL.md) for the full monorepo setup (one shared virtual environment, all three projects installed editable). Each project's own `INSTALL.md` covers the same ground if you only care about that one project in isolation.

## CONTRIBUTING

See [`HOWTO.md`](HOWTO.md) for the contribution workflow and commit conventions — and especially [`modulesKIT/HOWTO.md`](modulesKIT/HOWTO.md) if you want to build your own module.

## VERSIONS

Each project versions itself independently — see its own `README.md` for its version history.

## TABLE OF CONTENT

<!-- TOC -->

- [DISCORD\_BOT](#discord_bot)
  - [THIRD-PARTY CONTENT](#third-party-content)
  - [HOW THE PIECES FIT TOGETHER](#how-the-pieces-fit-together)
  - [INSTALLATION](#installation)
  - [CONTRIBUTING](#contributing)
  - [VERSIONS](#versions)
  - [TABLE OF CONTENT](#table-of-content)

<!-- /TOC -->
