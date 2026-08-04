#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TB1 character roster lookup, loaded from `data/tb1/characters.json`.

`characters.json` was built by cross-referencing `chrdb_full.json` (the game's own
character database dump -- filtered to `kind == 2 and chr_type == 1`, the actual
playable adventurers, excluding generic recruitable mobs like "Mage" and named
monster/boss entries that share the same `infos` table) against the Terra Battle
Wiki's `Category:Characters` via its MediaWiki API (the wiki's own HTML is behind
a Cloudflare challenge, but `api.php` isn't). One wiki page not filed under that
category (`Xaepha`) was still found via the API's page-title resolution. Two
`chrdb_full.json` entries share the display name "Lucia" (chr_id 718, the real
one, and 769, a story decoy with the same localized name) and collapse to a
single roster entry, since both point at the same wiki page.

`chrdb_full.json`'s numeric `rarity` (2-8 among playable adventurers) was
converted to the game's own letter grades -- D, C, B, A, S, SS, Z, matching
`pact.json`/`pact_roll.py`'s own `B`/`A`/`S`/`SS`/`Z` tier vocabulary for
this same module -- rather than kept as a bare number.

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

RARITY_ORDER = _catalog.RARITY_ORDER


class CharacterEntry(BaseModel):
    """One playable TB1 character.

    Attributes:
        name: Display name, e.g. `"Bahl"` or `"Bahl Λ"` for its awakened form.
        rarity: Rarity grade, one of `RARITY_ORDER`.
        link: Wiki page for the character.
    """

    name: str
    rarity: str
    link: str


class CharacterCatalog(_catalog.NameIndexedCatalog[CharacterEntry]):
    """Loads the TB1 character roster from `characters.json`, keyed by display name."""

    def __init__(self, module_name: str | None = None,
                 modules_config: 'AppConfig | None' = None) -> None:
        """Load this module's character data file.

        Args:
            module_name: Name of this module, used to look up its data folder.
            modules_config: Loaded application configuration.

        Raises:
            ValueError: If `module_name` or `modules_config` is missing.
        """
        if not modules_config or not module_name:
            raise ValueError(f"{self.__class__.__name__} -- Invalid module_name configuration file provided -- {module_name} : {modules_config}")

        data_path = pathlib.Path(modules_config.directories.data_directory) / module_name / 'characters.json'
        raw: dict[str, dict[str, object]] = json.loads(data_path.read_text(encoding='utf-8'))

        self.characters: list[CharacterEntry] = [CharacterEntry.model_validate({'name': name, **info})
                                                 for name, info in raw.items()]
        super().__init__(self.characters)

        self._by_rarity: dict[str, list[str]] = {}
        for entry in self.characters:
            self._by_rarity.setdefault(entry.rarity, []).append(entry.name)

        # Rarities actually present in the loaded roster, highest first -- drives
        # the usage hint so it never advertises a grade (e.g. `D`/`C`) that would
        # just come back empty.
        self.rarities_present: list[str] = [rarity for rarity in reversed(RARITY_ORDER) if rarity in self._by_rarity]

    def find_rarity(self, query: str) -> str | None:
        """Resolve a user-typed rarity grade, case-insensitively.

        Args:
            query: Rarity grade as typed by the user (`z`, `Z`, `ss`, ...).

        Returns:
            The matching grade from `RARITY_ORDER`, or `None` if `query` isn't
            one, or is one with no characters actually in it.
        """
        rarity = query.strip().upper()
        return rarity if rarity in self._by_rarity else None

    def render_usage(self) -> str:
        """Render the `!tb1.char` usage hint shown when no query was given.

        Returns:
            Markdown-formatted usage text listing the rarities in use.
        """
        rarities = ', '.join(f"`{rarity}`" for rarity in self.rarities_present)
        return '\n'.join(["**Terra Battle Characters**",
                          "Specify a rarity grade or a character name:",
                          f"- `!tb1.char <rarity>` -- lists that tier, e.g. `!tb1.char Z` (grades in use: {rarities})",
                          "- `!tb1.char <name>` -- looks up a character's wiki page, e.g. `!tb1.char JadeDragon` (spaces/apostrophes optional)",
                          "- `!tb1.char random` -- looks up a random character"])

    def render_tier(self, rarity: str) -> str:
        """Render one rarity tier's characters as a name grid.

        Args:
            rarity: A grade returned by `find_rarity` (i.e. known non-empty).

        Returns:
            Markdown-formatted tier listing.
        """
        names = self._by_rarity[rarity]
        return _catalog.render_grid(f"{rarity} ({len(names)})", names)

    def render_entry(self, entry: CharacterEntry) -> str:
        """Render one character's info card as markdown text.

        Args:
            entry: The entry to render.

        Returns:
            Markdown-formatted character info: name, rarity, and a wiki link
            left unmasked so Discord auto-embeds a preview of the page.
        """
        return '\n'.join([f"## **{entry.name}**",
                          f"-# Rarity {entry.rarity}",
                          f"- [Wiki Content]({entry.link})"])
