# How to build a modulesKIT module

This walks through building a new module from scratch, using the existing `anyquotes` module as the reference implementation. By the end you'll have a new FastAPI service that [LuraminaKIT](../LuraminaKIT) can discover and call without any changes to LuraminaKIT's own code.

If you haven't set up the project yet, see [`INSTALL.md`](INSTALL.md) first.

## Anatomy of a module

Everything lives inside the installed `modulesKIT` package (`src/modulesKIT/modules/<name>/`), except the launcher script, which sits at the project root next to `config.json`:

```
modulesKIT/
  config.json                       # add your module's entry here
  main_<name>.py                    # thin launcher, mirrors main_anyquotes.py
  data/<name>/                      # optional: your module's data files
  src/modulesKIT/modules/<name>/
    __init__.py
    <name>.py                       # your domain logic (plain classes/pydantic models)
    api_views.py                    # FastAPI routes, subclasses GenericViews
```

Two shared building blocks make this work, and you shouldn't need to modify either of them:

- **`modules/helpers/generic_api_views.GenericViews`** — base class for your `api_views.py`. Gives you `self.add_route(...)` to register a route *and* have it automatically advertised at `/api/<name>/url-list` (and `self.tokens`, populated from `AppConfig.tokens` if your module ever needs a shared secret). `add_route` also rejects a name/alias your own `__init__` already registered earlier, at registration time — so a copy-pasted route declaration fails loudly right where the mistake was made, not later as a silently-skipped collision when LuraminaKIT builds its command table.
- **`modules/helpers/generic_app.generic_launcher`** — your entire `main_<name>.py` is one call to this. Handles config-loading/logging bootstrap, builds the FastAPI app, and runs it with uvicorn, including routing a uvicorn startup failure (e.g. the port already being in use) through the same crash-logging path as any other error.

Both come from `contractsKIT`'s `StandardResponse`/`RouteDescriptor`/`ParamDescriptor` — the shared contract LuraminaKIT parses. See [`contractsKIT/HOWTO.md`](../contractsKIT/HOWTO.md) if you need to extend that contract itself (you usually won't).

## Step by step: a worked example

We'll build a tiny `echo` module: `!echo_text hello` replies `HELLO`. It's deliberately trivial so the wiring is easy to see — `anyquotes` is a better reference once you need config-driven behavior or data files.

### 1. Scaffold the package

```bash
mkdir -p modulesKIT/src/modulesKIT/modules/echo
touch modulesKIT/src/modulesKIT/modules/echo/__init__.py
```

### 2. Write your domain logic (optional, but recommended)

Keep business logic out of `api_views.py` so it's testable without spinning up FastAPI — this is what `anyquotes.py`'s `AnyQuotes` class does. For something this simple we can skip a separate logic module, but for anything non-trivial, follow that pattern: plain classes and pydantic models (never raw `dict`s for structured data — see `anyquotes.py`'s `Quote`/`QuoteFileInfo` models for the style).

### 3. Expose it via `api_views.py`

```python
# src/modulesKIT/modules/echo/api_views.py
import logging

from contractsKIT import StandardResponse, ParamDescriptor
from modulesKIT.modules.helpers import generic_api_views

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class EchoView(generic_api_views.GenericViews):
    """Exposes the `/echo` route."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.add_route("/echo",
                       self.echo_text,
                       methods=['GET'],
                       response_model=StandardResponse[str],
                       description="Echoes back the given text, uppercased.",
                       params=[ParamDescriptor(name='text', required=True)])

    async def echo_text(self, text: str) -> StandardResponse[str]:
        """Echo `text` back, uppercased.

        Args:
            text: Text to echo back.

        Returns:
            A `StandardResponse` wrapping the uppercased text.
        """
        return StandardResponse[str].ok(text.upper())
```

**The one detail that's easy to miss**: `text: str` in the endpoint signature is what makes FastAPI actually treat it as a query parameter — `add_route`'s `params=[...]` list is a *separate* declaration used only to advertise it in the manifest. They have to agree, and their **order matters**: LuraminaKIT matches the words a user types after a command to `query_params` positionally (first word → first param, etc.), not by name. If your route takes more than one parameter, list them in `params=` in the same order your endpoint expects them.

If your module needs config or data files, look at `anyquotes/api_views.py`'s `QuotesView.__init__` — it takes an optional `modules_config: 'AppConfig | None'` (under `TYPE_CHECKING` since it's only used as a type hint) and passes it to its logic class.

### 4. Write the launcher script

`generic_launcher` handles everything a launcher script needs -- config loading, logging bootstrap, building the FastAPI app, and running it with uvicorn -- so `main_echo.py` is just:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: <you>
"""

from modulesKIT.modules.helpers.generic_app import generic_launcher
from modulesKIT.modules.echo import api_views

if __name__ == "__main__":
    generic_launcher(__file__, api_views.EchoView)

# fastapi dev main_echo.py
```

That's it -- no `create_app`/`main` boilerplate to copy or keep in sync. `generic_launcher` calls your view class as `EchoView(module_name=app_name, modules_config=config)`; if your view's `__init__` doesn't need `modules_config` (like `EchoView` here, since `echo` has no config-driven behavior), that's fine, it just goes unused -- only `AppConfig | None = None`-typed, unused-if-absent parameters like this are expected on every view's `__init__` for exactly this reason.

### 5. Register it in `config.json`

Add an entry under `modules`, picking a free port:

```json
"echo": {
    "port": 8002,
    "description": "Echoes back text, uppercased"
}
```

If your module needs its own settings (like `anyquotes`'s quote template), put them under a `datas` key — it's a free-form `dict[str, str]` your module reads however it likes.

By default the repo-root [`run.py`](../run.py) launcher starts every module it finds here (`auto_start` defaults to `true`). Set `"auto_start": false` on your entry if it's too heavy to want running automatically (e.g. on weaker hardware) — it still runs fine started directly via its own `main_<name>.py`, this flag only affects `run.py`'s discovery.

### 6. Run and verify it stands on its own

```bash
python main_echo.py
curl "http://127.0.0.1:8002/api/echo/url-list"
curl "http://127.0.0.1:8002/api/echo/echo?text=hello"
```

The first call should show your route in the manifest with `"query_params": [{"name": "text", "required": true, ...}]`; the second should return `{"status": "SUCCESS", "data": "HELLO", "error": ""}`.

### 7. Wire it into LuraminaKIT

Add a matching entry to `LuraminaKIT/config.json`'s `modules` list:

```json
{
    "name": "echo",
    "port": 8002,
    "prefix": "/api/echo"
}
```

Restart (or just start) LuraminaKIT — it discovers routes at startup via `get_modules()`, no code changes needed. The Discord command will be `!echo_text hello` — the command name LuraminaKIT dispatches on is the **route's Python function name** (`echo_text`), not the module name or the route path. That's a quirk worth knowing about, not a bug: `RouteDescriptor.name` defaults to `endpoint.__name__`.

### 8. (Optional) heavy or optional third-party dependencies

If your module needs something heavy that other modules shouldn't be forced to install, follow the pattern already set up for a future OCR module in `pyproject.toml`:

```toml
[project.optional-dependencies]
echo-extra = ["some-heavy-package"]
```

```bash
pip install -e "./modulesKIT[echo-extra]"
```

Otherwise just add it to the main `dependencies` list and re-run `pip install -e ./modulesKIT`.

### 9. (Optional) `command_help.json` for wording that's easy to tweak

If you want a command's description or per-parameter hints editable without
touching Python (or written by someone who isn't), add
`data/<name>/command_help.json`:

```json
{
  "echo_text": {
    "summary": "Echoes back the given text, uppercased.",
    "params": {
      "text": "The text to echo back."
    }
  }
}
```

`GenericViews.__init__` loads this file once (entirely optional -- a module
with no file just gets no hints, nothing breaks), and `add_route` merges a
matching entry over `description=`/each `ParamDescriptor`'s `hint` when both
exist -- JSON wins, the code's own `description=`/`params=` stay as the
fallback for anything the file doesn't cover. If your commands are dotted
into categories (see the next step), a key that matches a category prefix
instead of an exact command name (e.g. `"tb1.special"`) explains that whole
grouping on its collapsed `/help` line instead of one specific command's. See
`modules/helpers/command_help.py` and `data/tb1/command_help.json` for a real
example covering both cases.

### 10. If your module will have a lot of commands: dot-namespace them

`/help` renders as a drill-down tree, not a flat list — it's built by splitting
each command's name on `.`, not by which module advertised it (see
`LuraminaKIT/HOWTO.md`). A module with a handful of commands (like `echo`) doesn't
need this; a module with dozens (like `tb1`, e.g. `tb1.kino.bahamut`,
`tb1.world.mutohlambda`) does, or `/help` would have to print every single one
at the top level.

If you go this route, pass `name=` (and optionally `aliases=`) explicitly to
`add_route` instead of relying on the endpoint's own `__name__` — dots aren't
legal in a Python function name, so `async def tb1.kino.bahamut(self): ...` can't
exist; register it as `self.add_route(..., name='tb1.kino.bahamut', aliases=['tb1.k.baha'])`
on a normally-named method or handler instead. **The first segment before the dot
must be your own module's name** (`add_route` raises `ValueError` at registration
time if it isn't) — that's what stops one module's commands from ever showing up
filed under another's in the tree. See `modulesKIT/modules/tb1/api_views.py` for a
real example, including its generic per-entry route-registration loop for the
dozens of data-driven commands that don't warrant their own method each.

## Style checklist

This codebase follows a few conventions consistently — match them:

- Pydantic models for structured data, never raw `dict`s passed around as if typed (see `Quote`/`QuoteFileInfo` in `anyquotes.py`).
- No `typing.Any` — use a real type, or `object` if the value is genuinely unnarrowed at that point.
- `if TYPE_CHECKING: from ... import X` + a quoted `'X'` annotation for any import used *only* in a type hint (never instantiated/called in that file).
- Google-style docstrings (`Args:`, `Returns:`, `Raises:`) on public classes/functions.
- Logging via `logger.info("...%s...", value)` / lazy `%s`/`%r` placeholders — never f-strings inside a `logger.*()` call.
- Return `StandardResponse[T].ok(...)` / `StandardResponse[T].fail(...)` from every route, never a hand-rolled dict -- explicitly parameterized (e.g. `StandardResponse[str].ok(...)`), not the bare `StandardResponse.ok(...)` form. The bare form still runs fine, but accessing a `@classmethod` through an unparameterized `Generic[T]` class is a known basedpyright inference gap that collapses `T` to `Unknown` and cascades into dozens of spurious warnings at every call site.

## Committing your module

This repo uses [Conventional Commits](https://www.conventionalcommits.org/). For a new module, that's typically one commit:

```
feat(modulesKIT): add echo module
```

See the root [`HOWTO.md`](../HOWTO.md) for the full contribution workflow and commit conventions.
