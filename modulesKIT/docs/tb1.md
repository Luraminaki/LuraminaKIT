# tb1

Terra Battle 1 companion commands, ported from the `tb1` command group of
[bokochaos/hisobot](https://github.com/bokochaos/hisobot) (a JS Discord bot for the
TB1 community). Only `tb1`'s commands were ported — `tb2` and `general` were out of
scope. `metal` (Metal Zone schedule) was dropped rather than ported: Metal Zones
were made permanently open near the game's end of life, so there's no real
schedule left to advertise.

- **Launcher**: `main_tb1.py`
- **Default port**: `8002`
- **Data**: `data/tb1/pact.json` — copied as-is from hisobot (community-estimated
  pact rates, banners, unit pools). Rarities: `B < A < S < SS < Z`.
- **Daily-quest rotation and epoch** are *not* from hisobot's own copy — they're
  ported from a reverse-engineered analysis of the game's own daily-quest
  computation, so forecasts match the game's actual rotation logic. See
  `daily_quest.py`'s module docstring for the source attribution.
- **`data/tb1/command_help.json`** — optional `/help` wording: a summary and
  per-parameter hint for each of the 8 static commands below, plus a one-line
  explanation for each category (`special`/`kino`/`8b`/`hunt`/`world`/`descent`/
  `utils`) shown on `/help`'s collapsed category lines. See
  `modules/helpers/command_help.py` for the loading/merge mechanism -- it's
  generic, any module can add its own.

## Routes / Discord commands

Commands are dotted and namespaced by category: `tb1.utils.*` (roll/forecast
logic), and `tb1.<category>.<name>` for every event/boss info card, split
across `tb1.special.*`, `tb1.kino.*`, `tb1.8b.*`, `tb1.hunt.*`, `tb1.world.*`,
and `tb1.descent.*`. What each category actually means is deliberately not
re-described here — that lives entirely in `command_help.json` (see
`/help path:tb1.<category>` for what a Discord user sees live, e.g.
`/help path:tb1.kino`), so there's exactly one place to keep it accurate
instead of two that can drift apart.

| Discord command | Route | Params | Notes |
|---|---|---|---|
| `tb1.utils.roll` (alias `tb1.r`) | `GET /api/tb1/roll` | `pulls` (int, 1-100), `pof` (bool), `base` (rarity letter) | Simulates pact rolls. The pool always includes all 3 discontinued special-pact banners merged in -- by the time the game shut down they'd all run concurrently, so there's no real "pick a subset" state left to simulate. `pulls`/`pof`/`base` positional order matters for Discord dispatch. |
| `tb1.utils.dq` (alias `tb1.dq`) | `GET /api/tb1/daily_quest` | `days` (int, 1-7, default 3, optional) | Forecasts the 41-day daily-quest rotation, starting today (UTC). |
| `tb1.char` | `GET /api/tb1/characters` | `query` (rarity grade, name, or `random`; optional) | Lists a rarity tier of TB1's playable roster, or looks up one character by name. See `characters.py`. |
| `tb1.mon` | `GET /api/tb1/monsters` | `query` (rarity grade, name, or `random`; optional) | Same shape as `tb1.char`, for monsters. See `monsters.py`. |
| `tb1.item` | `GET /api/tb1/items` | `query` (category, name, or `random`; optional) | Lists an item category, or looks up one item by name. See `items.py`. |
| `tb1.buddy` | `GET /api/tb1/buddies` | `query`, `filter2` (rarity/wiki-type/Omicron-tier, name, or `random`; both optional) | Lists TB1 companions by rarity, wiki type, or Omicron tier -- combine two of `query`/`filter2` to narrow a listing that's too big on its own (e.g. `tb1.buddy Z Sword`). See `buddy.py`'s module docstring for why 3 axes exist and how the oversized-listing prompt works. |
| `tb1.recode` | `GET /api/tb1/recode` | `query` (1-based pair ID, optional) | Lists every base -> awakened (Λ) recode pair, or shows one pair's wiki links by ID. Resolves across both the character and monster rosters (a recoded monster can "graduate" to a playable character) -- see `recode.py`. |
| `tb1.search` | `GET /api/tb1/search` | `query` (name, required) | Searches characters/monsters/items/companions at once for a name, instead of requiring you to already know which catalog it's in. Returns every match if a name exists in more than one catalog (e.g. "Bahamut" is both a character and a companion). |
| one per entry in `data/tb1/events.json` | `GET /api/tb1/events/<key>` | none | Info card for one TB1 event/special quest/boss. **`events.json` is the source of truth for the full roster** — not duplicated here as a table, since it's dozens of entries and would drift. `/help path:tb1` lists every currently-registered one (with its aliases) at runtime; `curl .../api/tb1/url-list` does too. |

`tb1.char`/`tb1.mon`/`tb1.item`/`tb1.buddy` all accept the literal word `random` as
`query` to look up a random entry from that catalog instead of a specific rarity/
type/name.

`characters.py`/`monsters.py`/`items.py`/`buddy.py` share their name-normalization,
grid-rendering, and name-lookup plumbing via `_catalog.py` (extracted after the
same block-chunking bugfix had to be hand-applied to all four independently --
see that module's own docstring for what's shared and, just as importantly, what
deliberately isn't).

### Aliases

Routes can advertise extra command names via `RouteDescriptor.aliases`
(`GenericViews.add_route(..., aliases=[...])`); LuraminaKIT dispatches any of them
to the same handler. Every command name/alias in this module is dotted (e.g.
`tb1.kino.odin` / `tb1.k.odin`) and namespaced to avoid collisions between
same-named bosses across different families (e.g. `tb1.8b.spinetrich` vs.
`tb1.kino.spinetrich` are two distinct commands). A name/alias that collides with
one already claimed (within this module, or against another module's) is logged
and skipped rather than silently shadowing the earlier registration — see
`command_discovery.build_commands` / `discord_client.get_modules`. `/help
path:<alias>` (e.g. `/help path:tb1.r`) resolves to the same entry `/help
path:<canonical name>` would, not a "not found" -- `build_help_text` resolves
through `commands`, which is keyed by every name *and* alias.

## Known caveats

- `6004`'s quest name (`Particle Hoarder Horde?`) is marked uncertain in the
  upstream source comment — carried over as-is rather than presented as confirmed.
- `tb1.special.arachnobot`'s original chart image (an old-style pre-2023 Discord CDN
  attachment link from the 2018 command) is confirmed **dead** (404, re-verified
  directly) — not just a theoretical rot risk. `image_url` now points at the wiki's
  official banner instead; the original fan-made flowchart (recovered and dropped
  in locally by hand, not re-fetchable from Discord anymore) is archived at
  `data/tb1/events/tb1.special.arachnobot/` but not linked/displayed.
- Every event beyond `tb1.special.vengefulheart`/`tb1.special.arachnobot` has no
  hisobot precedent to port from — hisobot's `tb1` folder only ever shipped those
  two event-chart commands (checked its current commands, `commands/etc`, and
  `Archived`: nothing else). All other content in `events.json` is sourced directly
  from the Terra Battle Wiki.
- `image_url` always points at each event's official wiki **banner**, not a
  fan-made flowchart/chart, even where one exists (`vh`/`arachnobot` both have
  fan-made charts archived locally alongside their banner, kept for a separate
  planned use rather than displayed). Where a genuine image exists at all, it's
  archived locally under `data/tb1/events/<key>/` as a resilience backup (see that
  folder's `README.md`) — Discord always renders the *live* external URL, the
  archive isn't served by anything. `meltingpotbeastfolk`, `meltingpothuman`, and
  `ultimatefive` have no image at all (verified: their wiki pages fall back to the
  site's generic logo, no dedicated art exists).
- A handful of researched events were deliberately left out of the roster after
  review: The Death of Shay and Arionne (judged not significant enough despite the
  wiki write-up), KINO World (content not yet verified/recovered), and Orbling
  Cavern (too minor). Don't re-add them without checking first — they were cut on
  purpose, not missed. The Captive Golem and Hunting the Jade Dragon were
  initially cut for being retired content (removed in Version 5.5.0) but were
  added back later at explicit request (`tb1.special.captivegolem`/
  `tb1.special.jadedragon`) — being retired isn't itself disqualifying, just the
  reason they weren't included by default in the first pass.

## Adding or editing an event

Pure data change: add/edit an entry in `data/tb1/events.json` and restart `tb1` —
`TB1View` registers one route per entry automatically (`api_views.py`'s
`_make_event_handler`), no code change needed. Unlike most of this codebase, keys
here are *not* required to be valid Python identifiers — they're dotted command
names (e.g. `tb1.kino.odin`), passed to `add_route`'s `name=` override rather than
relied on as the handler function's own `__name__`.

## Example

```bash
curl "http://127.0.0.1:8002/api/tb1/roll?pulls=10&pof=true&base=B"
curl "http://127.0.0.1:8002/api/tb1/daily_quest?days=7"
```
