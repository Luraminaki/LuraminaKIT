# llm

Chat completions via a locally-running OpenAI-compatible completion server —
[llama.cpp](https://github.com/ggml-org/llama.cpp)'s own `llama-server` is the
intended target, but anything speaking the same `/v1/chat/completions` shape
(Ollama, LM Studio, vLLM) works with zero code changes here, since this module
never embeds an inference engine itself. Swapping which model answers is
entirely that server's own concern — e.g. restarting `llama-server` with a
different `-m <path-to-gguf>` — this module just talks to whatever's currently
listening at its configured `base_url`.

- **Launcher**: `main_llm.py`
- **Default port**: `8003`
- **`auto_start`: `false`** by default (`modulesKIT/config.json`) — unlike
  `anyquotes`/`tb1`, this module is genuinely heavy *by proxy*: it doesn't run
  a model itself, but it's useless without a completion server that does, and
  that server can easily need a real GPU/lots of RAM. `python run.py` skips it
  unless you flip that flag; it still runs fine started directly
  (`python main_llm.py`) once a completion server is actually up. See
  `run.py`'s own docs for the `auto_start` mechanism generally.
- **Config** (`modulesKIT/config.json`, under `modules.llm.data` — all
  free-form strings, parsed by `llm_client.LlmClient`):
  - `base_url` — where the completion server's OpenAI-compatible API lives
    (default `http://127.0.0.1:8080`, `llama-server`'s own default).
  - `model` — sent in the request body; largely cosmetic for a server that's
    only ever serving one model at a time (as `llama-server` is), but some
    backends use it for routing.
  - `system_prompt`, `max_tokens`, `temperature` — the usual chat-completion knobs.
  - `timeout` — seconds LuraminaKIT waits for a reply before giving up
    (default `60`; capped at 120 by `contractsKIT.RouteDescriptor.timeout` —
    see that field's docstring for why this is per-route, not a single global
    value). Generation is inherently slower than every other route in this
    repo, especially on weaker hardware — raise this in `config.json` if 60s
    isn't enough for your setup, rather than in code.

## Routes / Discord commands

| Discord command | Route | Params |
|---|---|---|
| `llm.chat` | `GET /api/llm/chat` | `prompt` (free text, required) |

`prompt` is genuinely free text — everything typed after the command name is
sent as one message, not just the first word (`command_dispatch._match_params`
specifically supports this: a command's *last* declared param absorbs every
remaining typed word, rejoined with spaces, rather than only the next one).

## Example

Needs a real completion server already running and reachable at the
configured `base_url` — this module has nothing to serve on its own:

```bash
python main_llm.py
curl "http://127.0.0.1:8003/api/llm/chat?prompt=hello"
```

If the completion server isn't reachable, the route fails with a clear
`StandardResponse.fail(...)` message telling you so (not a raw connection
error) — see `api_views.LlmView.chat`'s handling of `aiohttp.ClientConnectorError`.

## See also

- [`../HOWTO.md`](../HOWTO.md) — `anyquotes` is the reference implementation
  walked through there for building a new module from scratch; this module
  follows the same shape (`llm_client.py` for domain logic, `api_views.py` for
  the FastAPI route, kept separate per that HOWTO's own convention).
- `data/llm/command_help.json` — this module's `/help` wording, editable
  without touching Python (see `../HOWTO.md`'s step on `command_help.json`).
