# How to extend contractsKIT

`contractsKIT` is the wire contract both [modulesKIT](../modulesKIT) and [LuraminaKIT](../LuraminaKIT) depend on. Changes here ripple into both — this is the one project in the monorepo where a "small" change can break something you're not currently looking at.

If you haven't set up the project yet, see [`INSTALL.md`](INSTALL.md) first.

## What lives here

- **`envelope.py`** — `StatusFunction`, `StandardResponse[T]`. The `{status, data, error}` shape every modulesKIT route returns and every LuraminaKIT request parses.
- **`manifest.py`** — `ParamDescriptor`, `RouteDescriptor`, `ModuleManifest`. What a module advertises at `/url-list`, and what LuraminaKIT discovers commands from.
- **`logging_utils.py`** / **`logreset.py`** — `configure_launcher_logging`, shared rotating-file logging setup used by both projects' launcher scripts.

## Before changing anything here, ask

**Is this actually a shared-contract change, or module-specific?** If only one module needs a new field, it usually belongs in that module's own config/response model (see `modulesKIT`'s `ModuleConfig.data: dict[str, str]` free-form bucket), not here. Add to `contractsKIT` only when both modulesKIT *and* LuraminaKIT genuinely need to agree on the new shape.

## Adding a field

Example: adding an optional `latency_ms` to `StandardResponse`:

```python
class StandardResponse(BaseModel, Generic[T]):
    status: StatusFunction
    data: T | None = None
    error: str = ''
    latency_ms: float | None = None   # new, optional, defaults so existing callers don't break
```

Keep new fields **optional with a default** unless you're prepared to update every call site in both other projects in the same change — a required new field breaks every existing `StandardResponse[T].ok(...)`/`.fail(...)` call immediately.

## Testing a change

Since both dependents install this editable, changes take effect immediately — no rebuild needed. But you do need to re-verify both sides:

```bash
# from the repo root, with the shared venv active
python modulesKIT/main_anyquotes.py &
curl http://127.0.0.1:8001/api/anyquotes/url-list
curl http://127.0.0.1:8001/api/anyquotes/quote
```

Then confirm LuraminaKIT still parses the (possibly changed) response correctly — see `modulesKIT/HOWTO.md`'s verification section for a script that drives `DiscordClient.get_modules()`/`on_message()` against a running module without needing a live Discord connection.

If you renamed or removed a field instead of adding one, grep both other projects for it before assuming it's safe:

```bash
grep -rn "field_name" modulesKIT/src LuraminaKIT/src
```

## Style

Same conventions as the rest of the repo — see the root [`HOWTO.md`](../HOWTO.md). In particular: no `typing.Any`, Google-style docstrings, and keep `StandardResponse`/`RouteDescriptor`/etc. as plain pydantic models (they're the one place in this repo where "just use a dict" would seem tempting — don't, that's exactly what this package exists to replace).

## Committing

```
feat(contractsKIT): add latency_ms to StandardResponse
```
