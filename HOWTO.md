# Contributing to this monorepo

This is the general contribution guide. For hands-on, project-specific instructions:

- [`modulesKIT/HOWTO.md`](modulesKIT/HOWTO.md) — build a new module (start here if that's what you're doing).
- [`LuraminaKIT/HOWTO.md`](LuraminaKIT/HOWTO.md) — contribute to the Discord bot itself.
- [`contractsKIT/HOWTO.md`](contractsKIT/HOWTO.md) — extend the shared contract between the two.

## Setup

See [`INSTALL.md`](INSTALL.md) for the full environment setup (one shared `.venv`, all three projects installed editable).

## Where things live

- [`contractsKIT`](contractsKIT) — shared pydantic contracts (`StandardResponse`, module manifests, rotating-log setup).
- [`modulesKIT`](modulesKIT) — one FastAPI service per bot "module".
- [`LuraminaKIT`](LuraminaKIT) — the Discord bot, discovers modulesKIT modules and proxies commands to them.

A change to `contractsKIT` can affect both of the other projects — check both READMEs' "how it works" sections before changing anything there.

## Style

The codebase follows a consistent set of conventions everywhere:

- Pydantic models for structured data — never raw `dict`s passed around as if they were typed.
- No `typing.Any` — use a real type, or `object` when a value is genuinely unnarrowed at that layer.
- `if TYPE_CHECKING: from ... import X` + a quoted `'X'` annotation for imports used *only* in a type hint (never instantiated/called at runtime in that file).
- Google-style docstrings (`Args:`, `Returns:`, `Raises:`) on public classes/functions.
- Logging via lazy `%s`/`%r` placeholders (`logger.info("...%s", value)`) — never f-strings inside a `logger.*()` call.
- No `Path.cwd()` — resolve paths relative to `pathlib.Path(__file__).resolve().parent` instead, so behavior never depends on where a script was launched from.
- Package layout: `pyproject.toml` + src-layout (`<Project>/src/<Project>/...`), no `requirements.txt`. Launcher scripts stay outside `src/`, next to their `config.json`/`data/`/`logs/`.

## Commit conventions

This repo follows [Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <description>`.

- **Types**: `feat`, `fix`, `refactor`, `docs`, `chore`, `style`, `test`, `build`, `ci`, `perf`.
- **Scope**: the project you're changing — `contractsKIT`, `modulesKIT`, or `LuraminaKIT`. Omit the scope for changes that span the whole repo (e.g. a root `docs:` or `chore:` commit).
- Keep commits scoped to one project/concern where practical — e.g. a new module is `feat(modulesKIT): add <name> module`, not bundled with unrelated bot changes.

Examples from this repo's own history:

```
feat(contractsKIT): add shared pydantic contracts and rotating-log setup
feat(modulesKIT): add FastAPI module host with the anyquotes module
feat(LuraminaKIT): add discord bot with module discovery, dispatch, and env-based secrets
docs: add root README and INSTALL for the monorepo
```

## Before committing

Run the smoke test relevant to what you touched:

- **modulesKIT**: start the module's launcher, `curl` its `/url-list` and any new routes.
- **LuraminaKIT**: drive `DiscordClient.get_modules()`/`on_message()` against a running module (see `modulesKIT/HOWTO.md`'s verification steps for the pattern) — no need for a live Discord connection to sanity-check dispatch logic.
- **contractsKIT**: since both other projects import it, re-run both of the checks above after any change here.
