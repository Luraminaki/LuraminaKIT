#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TB1 monster roster lookup, loaded from `data/tb1/monsters.json`.

Built the same way as `characters.py`'s roster: filtered from `chrdb_full.json`
(the game's own character database dump), but `kind == 1` (monsters) instead of
`kind == 2 and chr_type == 1` (playable adventurers) -- no further `chr_type`
restriction needed, `kind` alone cleanly separates the two per the wiki's own
framing ("Terra Battle classifies units as either Adventurers or Monsters").
Each entry's wiki link was resolved via the MediaWiki API directly (by title,
following redirects) rather than guessed from the name, since a chrdb name
doesn't always match its wiki page slug exactly.

Shares its name-normalization/grid-rendering/name-lookup plumbing with
`characters.py`/`items.py`/`buddy.py` via `_catalog.py` -- see that module's
own docstring for why the rarity-indexing logic below still isn't shared.

@author: Luraminaki
"""

import json
import logging
import pathlib

from typing import TYPE_CHECKING

from pydantic import BaseModel

from modulesKIT.modules.tb1 import _catalog

if TYPE_CHECKING:
    from modulesKIT.modules.helpers.generic_config import AppConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Monsters span the full scale (playable adventurers only ever reach B-Z).
RARITY_ORDER = _catalog.RARITY_ORDER


class MonsterEntry(BaseModel):
    """One TB1 monster.

    Attributes:
        name: Display name, e.g. `"Lich"` or `"Lich Λ"` for its awakened form.
        rarity: Rarity grade, one of `RARITY_ORDER`.
        link: Wiki page for the monster.
    """

    name: str
    rarity: str
    link: str


class MonsterCatalog(_catalog.NameIndexedCatalog[MonsterEntry]):
    """Loads the TB1 monster roster from `monsters.json`, keyed by display name."""

    def __init__(self, module_name: str | None = None,
                 modules_config: 'AppConfig | None' = None) -> None:
        """Load this module's monster data file.

        Args:
            module_name: Name of this module, used to look up its data folder.
            modules_config: Loaded application configuration.

        Raises:
            ValueError: If `module_name` or `modules_config` is missing.
        """
        if not modules_config or not module_name:
            raise ValueError(f"{self.__class__.__name__} -- Invalid module_name configuration file provided -- {module_name} : {modules_config}")

        data_path = pathlib.Path(modules_config.directories.data_directory) / module_name / 'monsters.json'
        raw: dict[str, dict[str, object]] = json.loads(data_path.read_text(encoding='utf-8'))

        self.monsters: list[MonsterEntry] = [MonsterEntry.model_validate({'name': name, **info})
                                             for name, info in raw.items()]
        super().__init__(self.monsters)

        self._by_rarity: dict[str, list[str]] = {}
        for entry in self.monsters:
            self._by_rarity.setdefault(entry.rarity, []).append(entry.name)

        self.rarities_present: list[str] = [rarity for rarity in reversed(RARITY_ORDER) if rarity in self._by_rarity]

    def find_rarity(self, query: str) -> str | None:
        """Resolve a user-typed rarity grade, case-insensitively.

        Args:
            query: Rarity grade as typed by the user (`d`, `D`, `ss`, ...).

        Returns:
            The matching grade from `RARITY_ORDER`, or `None` if `query` isn't
            one, or is one with no monsters actually in it.
        """
        rarity = query.strip().upper()
        return rarity if rarity in self._by_rarity else None

    def render_usage(self) -> str:
        """Render the `!tb1.mon` usage hint shown when no query was given.

        Returns:
            Markdown-formatted usage text listing the rarities in use.
        """
        rarities = ', '.join(f"`{rarity}`" for rarity in self.rarities_present)
        return '\n'.join(["**Terra Battle Monsters**",
                          "Specify a rarity grade or a monster name:",
                          f"- `!tb1.mon <rarity>` -- lists that tier, e.g. `!tb1.mon C` (grades in use: {rarities})",
                          "- `!tb1.mon <name>` -- looks up a monster's wiki page, e.g. `!tb1.mon Lich` (spaces/apostrophes optional)",
                          "- `!tb1.mon random` -- looks up a random monster"])

    def render_tier(self, rarity: str) -> str:
        """Render one rarity tier's monsters as a name grid.

        Args:
            rarity: A grade returned by `find_rarity` (i.e. known non-empty).

        Returns:
            Markdown-formatted tier listing.
        """
        names = self._by_rarity[rarity]
        return _catalog.render_grid(f"{rarity} ({len(names)})", names)

    def render_entry(self, entry: MonsterEntry) -> str:
        """Render one monster's info card as markdown text.

        Args:
            entry: The entry to render.

        Returns:
            Markdown-formatted monster info: name, rarity, and a wiki link left
            unmasked so Discord auto-embeds a preview of the page.
        """
        return '\n'.join([f"## **{entry.name}**",
                          f"-# Rarity {entry.rarity}",
                          f"- [Wiki Content]({entry.link})"])
