#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TB1 item catalog lookup, loaded from `data/tb1/items.json`.

Built by parsing the wiki's own "Items" hub page (terrabattle.fandom.com/wiki/Items)
directly -- that page already lists every item as a real wiki link grouped under
16 category headings (Tickets, Power-up items, Candy items, ..., Event items), so
no per-item page visits were needed, just extracting that page's own link
structure per section. The "Eidolon items" section was dropped entirely -- Eidolons
were removed from the game, so there's nothing there worth cataloguing.

The "Event items"/"Unique items" sections turned out to mix true items with
character/monster recruit-reward links (e.g. "Bahamut Descended" drops either the
item "Blazing Wand" OR the character "Bahamut" -- the wiki page lists both under
the same heading). Those were filtered out by cross-referencing against the
already-built `characters.json`/`monsters.json` rosters at build time, not at
runtime -- see the build script's own comment for the exact list removed.

Shares its name-normalization/grid-rendering/name-lookup plumbing with
`characters.py`/`monsters.py`/`buddy.py` via `_catalog.py` -- see that module's
own docstring for why the category-indexing logic below still isn't shared.
`_catalog.normalize`'s `Λ`-handling is simply a no-op for every item name (none
contain it), so sharing it doesn't change behavior here.

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


class ItemEntry(BaseModel):
    """One TB1 item.

    Attributes:
        name: Display name, e.g. `"Metal Ticket"`.
        category: Category heading it was listed under on the wiki.
        link: Wiki page for the item.
    """

    name: str
    category: str
    link: str


class ItemCatalog(_catalog.NameIndexedCatalog[ItemEntry]):
    """Loads the TB1 item catalog from `items.json`, keyed by display name."""

    def __init__(self, module_name: str | None = None,
                 modules_config: 'AppConfig | None' = None) -> None:
        """Load this module's item data file.

        Args:
            module_name: Name of this module, used to look up its data folder.
            modules_config: Loaded application configuration.

        Raises:
            ValueError: If `module_name` or `modules_config` is missing.
        """
        if not modules_config or not module_name:
            raise ValueError(f"{self.__class__.__name__} -- Invalid module_name configuration file provided -- {module_name} : {modules_config}")

        data_path = pathlib.Path(modules_config.directories.data_directory) / module_name / 'items.json'
        raw: dict[str, dict[str, object]] = json.loads(data_path.read_text(encoding='utf-8'))

        self.items: list[ItemEntry] = [ItemEntry.model_validate({'name': name, **info})
                                       for name, info in raw.items()]
        super().__init__(self.items)

        self._by_category: dict[str, list[str]] = {}
        self._category_labels: dict[str, str] = {}
        for entry in self.items:
            key = _catalog.normalize(entry.category)
            self._by_category.setdefault(key, []).append(entry.name)
            self._category_labels[key] = entry.category

        # Declaration order (roughly the wiki's own, most-common-first) reads
        # better here than an alphabetical sort would.
        self.categories_present: list[str] = list(self._category_labels.values())

    def find_category(self, query: str) -> str | None:
        """Resolve a user-typed category, tolerant of spacing/hyphenation.

        Args:
            query: Category as typed by the user (`tickets`, `power-up`, ...).

        Returns:
            The matching category's canonical label, or `None` if `query`
            doesn't resolve to one.
        """
        return self._category_labels.get(_catalog.normalize(query))

    def render_usage(self) -> str:
        """Render the `!tb1.item` usage hint shown when no query was given.

        Returns:
            Markdown-formatted usage text listing the categories in use.
        """
        categories = ', '.join(f"`{category}`" for category in self.categories_present)
        return '\n'.join(["**Terra Battle Items**",
                          "Specify a category or an item name:",
                          f"- `!tb1.item <category>` -- lists that category, e.g. `!tb1.item Tickets` (categories: {categories})",
                          "- `!tb1.item <name>` -- looks up an item's wiki page, e.g. `!tb1.item MetalTicket` (spaces optional)",
                          "- `!tb1.item random` -- looks up a random item"])

    def render_category(self, category: str) -> str:
        """Render one category's items as a name grid.

        Args:
            category: A canonical label returned by `find_category`.

        Returns:
            Markdown-formatted category listing.
        """
        names = self._by_category[_catalog.normalize(category)]
        return _catalog.render_grid(f"{category} ({len(names)})", names)

    def render_entry(self, entry: ItemEntry) -> str:
        """Render one item's info card as markdown text.

        Args:
            entry: The entry to render.

        Returns:
            Markdown-formatted item info: name, category, and a wiki link left
            unmasked so Discord auto-embeds a preview of the page.
        """
        return '\n'.join([f"## **{entry.name}**",
                          f"-# {entry.category}",
                          f"- [Wiki Content]({entry.link})"])
