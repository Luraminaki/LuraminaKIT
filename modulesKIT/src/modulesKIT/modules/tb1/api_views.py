#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Luraminaki
"""

import logging
import pathlib
import random

from collections.abc import Coroutine
from typing import Callable, TYPE_CHECKING

from fastapi.responses import FileResponse

from contractsKIT import StandardResponse, ParamDescriptor
from modulesKIT.modules.helpers import generic_api_views
from modulesKIT.modules.tb1 import buddy, characters, daily_quest, events, items, monsters, pact_roll, recode

if TYPE_CHECKING:
    from modulesKIT.modules.helpers.generic_config import AppConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _make_event_handler(catalog: events.EventCatalog, key: str) -> Callable[[], Coroutine[None, None, StandardResponse[str]]]:
    """Build a route handler for one event.

    A separate `async def <key>(self): ...` method per event doesn't scale to the
    dozens of static event-info commands this module has -- one shared handler
    factory, looped over every entry in `catalog`, keeps this file's size independent
    of how many events exist. The Discord command name (`key`, e.g. `tb1.kino.odin`)
    is passed to `add_route`'s `name=` explicitly rather than set as this function's
    own `__name__`, since it isn't a valid Python identifier.

    Args:
        catalog: The loaded event catalog to render from.
        key: The event's key in `catalog.events`.

    Returns:
        A coroutine function suitable for `GenericViews.add_route`.
    """
    async def handler() -> StandardResponse[str]:
        return StandardResponse[str].ok(catalog.render(key))

    return handler


def _make_flowchart_handler(path: pathlib.Path) -> Callable[[], Coroutine[None, None, FileResponse]]:
    """Build a route handler serving one local flowchart image as raw bytes.

    Registered directly on `self.api_router`, not via `add_route` -- raw bytes
    don't fit `StandardResponse[T]`. `path` is resolved once at registration time
    (the caller already confirmed it exists via `EventCatalog.flowchart_path`),
    rather than re-checked on every request.

    Args:
        path: The flowchart image file to serve.

    Returns:
        A coroutine function suitable for `self.api_router.add_api_route`.
    """
    async def handler() -> FileResponse:
        return FileResponse(path, filename=path.name)

    return handler


class TB1View(generic_api_views.GenericViews):
    """Exposes `tb1.utils.roll`, `tb1.utils.dq`, `tb1.char`, and one route per
    event in `data/tb1/events.json`.

    Command names are dotted (`tb1.kino.odin`, `tb1.world.mutohlambda`, ...), not
    valid Python identifiers, so every route here passes `add_route`'s `name=`
    explicitly rather than relying on the endpoint's own `__name__`.
    """

    def __init__(self, modules_config: 'AppConfig | None' = None, *args, **kwargs) -> None:
        """Load pact/event data and register this module's routes.

        Args:
            modules_config: Loaded application configuration.
            *args: Forwarded to `GenericViews`.
            **kwargs: Forwarded to `GenericViews`.
        """
        super().__init__(*args, modules_config=modules_config, **kwargs)

        self.roller: pact_roll.PactRoller = pact_roll.PactRoller(self.module_name, modules_config)
        self.schedule: daily_quest.DailyQuestSchedule = daily_quest.DailyQuestSchedule()
        self.catalog: events.EventCatalog = events.EventCatalog(self.module_name, modules_config)
        self.roster: characters.CharacterCatalog = characters.CharacterCatalog(self.module_name, modules_config)
        self.monster_roster: monsters.MonsterCatalog = monsters.MonsterCatalog(self.module_name, modules_config)
        self.item_catalog: items.ItemCatalog = items.ItemCatalog(self.module_name, modules_config)
        self.buddy_catalog: buddy.BuddyCatalog = buddy.BuddyCatalog(self.module_name, modules_config)
        self.recode_catalog: recode.RecodeCatalog = recode.RecodeCatalog(self.roster, self.monster_roster)

        # description= is deliberately omitted below -- every one of these commands
        # has a matching entry in data/tb1/command_help.json, which add_route already
        # prefers over description= when present (see GenericViews.add_route). Keeping
        # a second, always-overridden copy of the same text here would just be a
        # second place to (mis)maintain the same wording.
        self.add_route("/roll", self.tb1roll,
                       methods=['GET'],
                       response_model=StandardResponse[str],
                       name='tb1.utils.roll',
                       aliases=['tb1.r'],
                       params=[ParamDescriptor(name='pulls', required=True, type_='int'),
                               ParamDescriptor(name='pof', required=True, type_='bool'),
                               ParamDescriptor(name='base', required=True)])

        self.add_route("/daily_quest", self.tb1dq,
                       methods=['GET'],
                       response_model=StandardResponse[str],
                       name='tb1.utils.dq',
                       aliases=['tb1.dq'],
                       params=[ParamDescriptor(name='days', required=False, type_='int')])

        self.add_route("/characters", self.tb1char,
                       methods=['GET'],
                       response_model=StandardResponse[str],
                       name='tb1.char',
                       params=[ParamDescriptor(name='query', required=False)])

        self.add_route("/monsters", self.tb1mon,
                       methods=['GET'],
                       response_model=StandardResponse[str],
                       name='tb1.mon',
                       params=[ParamDescriptor(name='query', required=False)])

        self.add_route("/items", self.tb1item,
                       methods=['GET'],
                       response_model=StandardResponse[str],
                       name='tb1.item',
                       params=[ParamDescriptor(name='query', required=False)])

        self.add_route("/buddies", self.tb1buddy,
                       methods=['GET'],
                       response_model=StandardResponse[str],
                       name='tb1.buddy',
                       params=[ParamDescriptor(name='query', required=False),
                               ParamDescriptor(name='filter2', required=False)])

        self.add_route("/search", self.tb1search,
                       methods=['GET'],
                       response_model=StandardResponse[str],
                       name='tb1.search',
                       params=[ParamDescriptor(name='query', required=False)])

        self.add_route("/recode", self.tb1recode,
                       methods=['GET'],
                       response_model=StandardResponse[str],
                       name='tb1.recode',
                       params=[ParamDescriptor(name='query', required=False)])

        for key, info in self.catalog.events.items():
            flowchart_path = self.catalog.flowchart_path(key)
            attachment_paths: list[str] = []

            if flowchart_path is not None:
                flowchart_route = f"/events/{key}/flowchart"
                attachment_paths.append(flowchart_route)
                self.api_router.add_api_route(flowchart_route, _make_flowchart_handler(flowchart_path), methods=['GET'])

            self.add_route(f"/events/{key}", _make_event_handler(self.catalog, key),
                           methods=['GET'],
                           response_model=StandardResponse[str],
                           description=info.title,
                           name=key,
                           aliases=info.aliases,
                           attachment_paths=attachment_paths)

    async def tb1roll(self, pulls: int, pof: bool, base: str) -> StandardResponse[str]:
        """Simulate `pulls` TB1 pact rolls.

        Args:
            pulls: Number of rolls to simulate, 1-100.
            pof: Whether Pact of Fellowship has been completed.
            base: Lowest remaining rarity in the player's pool (`B`/`A`/`S`/`SS`/`Z`).

        Returns:
            A `StandardResponse` wrapping the rendered roll results, or an error
            if `pulls`/`base` were invalid.
        """
        try:
            results = self.roller.roll(pulls, pof, base)
        except ValueError as err:
            logger.error("%r", err)
            return StandardResponse[str].fail(repr(err))

        return StandardResponse[str].ok(self.roller.render(results))

    async def tb1char(self, query: str = '') -> StandardResponse[str]:
        """List one TB1 rarity tier, or look up one character by name.

        Args:
            query: A rarity grade (`Z`, `SS`, `S`, `A`, `B`, any casing) to list
                that tier, a character name to look it up (spaces/apostrophes/
                casing don't matter, see `_catalog.normalize`), or empty for
                a usage hint. Deliberately doesn't default to dumping the whole
                190-character roster.

        Returns:
            A `StandardResponse` wrapping the rendered tier, character info
            card, or usage hint -- or an error if `query` matched neither a
            known rarity nor a known character.
        """
        if not query:
            return StandardResponse[str].ok(self.roster.render_usage())

        if query.strip().lower() == 'random':
            return StandardResponse[str].ok(self.roster.render_entry(random.choice(self.roster.characters)))

        rarity = self.roster.find_rarity(query)
        if rarity is not None:
            return StandardResponse[str].ok(self.roster.render_tier(rarity))

        entry = self.roster.find(query)
        if entry is not None:
            return StandardResponse[str].ok(self.roster.render_entry(entry))

        return StandardResponse[str].fail(f"Unknown character or rarity: {query!r}")

    async def tb1mon(self, query: str = '') -> StandardResponse[str]:
        """List one TB1 rarity tier of monsters, or look up one monster by name.

        Args:
            query: A rarity grade (`Z`, `SS`, `S`, `A`, `B`, `C`, `D`, any casing)
                to list that tier, a monster name to look it up, or empty for a
                usage hint.

        Returns:
            A `StandardResponse` wrapping the rendered tier, monster info card,
            or usage hint -- or an error if `query` matched neither a known
            rarity nor a known monster.
        """
        if not query:
            return StandardResponse[str].ok(self.monster_roster.render_usage())

        if query.strip().lower() == 'random':
            return StandardResponse[str].ok(self.monster_roster.render_entry(random.choice(self.monster_roster.monsters)))

        rarity = self.monster_roster.find_rarity(query)
        if rarity is not None:
            return StandardResponse[str].ok(self.monster_roster.render_tier(rarity))

        entry = self.monster_roster.find(query)
        if entry is not None:
            return StandardResponse[str].ok(self.monster_roster.render_entry(entry))

        return StandardResponse[str].fail(f"Unknown monster or rarity: {query!r}")

    async def tb1item(self, query: str = '') -> StandardResponse[str]:
        """List one TB1 item category, or look up one item by name.

        Args:
            query: A category name (spaces/hyphens optional, e.g. `Tickets` or
                `power-up`) to list that category, an item name to look it up,
                or empty for a usage hint.

        Returns:
            A `StandardResponse` wrapping the rendered category, item info card,
            or usage hint -- or an error if `query` matched neither a known
            category nor a known item.
        """
        if not query:
            return StandardResponse[str].ok(self.item_catalog.render_usage())

        if query.strip().lower() == 'random':
            return StandardResponse[str].ok(self.item_catalog.render_entry(random.choice(self.item_catalog.items)))

        category = self.item_catalog.find_category(query)
        if category is not None:
            return StandardResponse[str].ok(self.item_catalog.render_category(category))

        entry = self.item_catalog.find(query)
        if entry is not None:
            return StandardResponse[str].ok(self.item_catalog.render_entry(entry))

        return StandardResponse[str].fail(f"Unknown item or category: {query!r}")

    async def tb1buddy(self, query: str = '', filter2: str = '') -> StandardResponse[str]:
        """List TB1 companions by rarity/type/Omicron tier (optionally two combined), or look one up by name.

        Args:
            query: A rarity grade, wiki type, or Omicron tier to list, a
                companion name to look it up, or empty for a usage hint.
            filter2: A second rarity/type/Omicron tier to additionally filter
                by (any order relative to `query`), or empty for a single-axis
                listing / name lookup.

        Returns:
            A `StandardResponse` wrapping the rendered listing, companion info
            card, or usage hint -- or an error if nothing matched.
        """
        if not query:
            return StandardResponse[str].ok(self.buddy_catalog.render_usage())

        if query.strip().lower() == 'random':
            return StandardResponse[str].ok(self.buddy_catalog.render_entry(random.choice(self.buddy_catalog.buddies)))

        if not filter2:
            rarity = self.buddy_catalog.find_rarity(query)
            if rarity is not None:
                return StandardResponse[str].ok(self.buddy_catalog.render_tier(rarity))

            type_ = self.buddy_catalog.find_type(query)
            if type_ is not None:
                return StandardResponse[str].ok(self.buddy_catalog.render_type(type_))

            tier = self.buddy_catalog.find_omicron_tier(query)
            if tier is not None:
                return StandardResponse[str].ok(self.buddy_catalog.render_omicron_tier(tier))

            entry = self.buddy_catalog.find(query)
            if entry is not None:
                return StandardResponse[str].ok(self.buddy_catalog.render_entry(entry))

            return StandardResponse[str].fail(f"Unknown companion, rarity, type, or Omicron tier: {query!r}")

        axes: dict[str, str] = {}
        unresolved: list[str] = []

        for token in (query, filter2):
            resolved = self.buddy_catalog.resolve_axis(token)
            if resolved is None:
                unresolved.append(token)
                continue

            axis, value = resolved
            if axis in axes:
                return StandardResponse[str].fail(f"Both {value!r} and {axes[axis]!r} are a {axis.rstrip('_')} -- give at most one of each axis.")
            axes[axis] = value

        if unresolved:
            return StandardResponse[str].fail(f"Unknown rarity/type/Omicron tier: {unresolved!r}")

        return StandardResponse[str].ok(self.buddy_catalog.render_filtered(**axes))

    async def tb1search(self, query: str = '') -> StandardResponse[str]:
        """Search characters, monsters, items, and companions at once for a name.

        Saves having to already know which of the four catalogs a name belongs
        to -- useful since a few names exist in more than one (e.g. "Bahamut" is
        both a playable character and a companion), in which case every match
        is returned, labeled by which catalog it came from.

        Args:
            query: Name to search for, in any casing/spacing (see `_catalog.normalize`).

        Returns:
            A `StandardResponse` wrapping the matching info card(s), or an error
            if `query` was empty or matched nothing.
        """
        if not query:
            return StandardResponse[str].fail("Give a name to search for, e.g. `!tb1.search Bahamut`.")

        hits: list[tuple[str, str]] = []

        character = self.roster.find(query)
        if character is not None:
            hits.append(("Character", self.roster.render_entry(character)))

        monster = self.monster_roster.find(query)
        if monster is not None:
            hits.append(("Monster", self.monster_roster.render_entry(monster)))

        item = self.item_catalog.find(query)
        if item is not None:
            hits.append(("Item", self.item_catalog.render_entry(item)))

        companion = self.buddy_catalog.find(query)
        if companion is not None:
            hits.append(("Companion", self.buddy_catalog.render_entry(companion)))

        if not hits:
            return StandardResponse[str].fail(f"No character, monster, item, or companion named {query!r}.")

        if len(hits) == 1:
            return StandardResponse[str].ok(hits[0][1])

        return StandardResponse[str].ok('\n\n'.join(f"**[{label}]**\n{card}" for label, card in hits))

    async def tb1recode(self, query: str = '') -> StandardResponse[str]:
        """List every recode pair, or show one pair's wiki links by ID.

        Args:
            query: A 1-based pair ID (per the list's own numbering) to show that
                pair's wiki links, or empty for the full numbered list.

        Returns:
            A `StandardResponse` wrapping the rendered list or pair card, or an
            error if `query` was given but wasn't a valid pair ID.
        """
        if not query:
            return StandardResponse[str].ok(self.recode_catalog.render_list())

        try:
            pair_id = int(query)
        except ValueError:
            return StandardResponse[str].fail(f"Expected a numeric ID, got {query!r}. Use `!tb1.recode` to see the list.")

        rendered = self.recode_catalog.render_pair(pair_id)
        if rendered is None:
            return StandardResponse[str].fail(f"No recode pair with ID {pair_id} (valid range: 1-{len(self.recode_catalog.pairs)}).")

        return StandardResponse[str].ok(rendered)

    async def tb1dq(self, days: int = 3) -> StandardResponse[str]:
        """Forecast the daily quest rotation for the next `days` days.

        Args:
            days: Number of days to forecast, 1-7. Defaults to 3.

        Returns:
            A `StandardResponse` wrapping the rendered forecast, or an error if
            `days` was out of range.
        """
        try:
            entries = self.schedule.forecast(days)
        except ValueError as err:
            logger.error("%r", err)
            return StandardResponse[str].fail(repr(err))

        return StandardResponse[str].ok(self.schedule.render(entries))
