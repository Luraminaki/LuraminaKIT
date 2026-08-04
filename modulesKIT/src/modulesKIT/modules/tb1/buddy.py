#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TB1 companion ("buddy") catalog lookup, loaded from `data/tb1/buddy.json`.

Companion rarity/name comes from the game's own `buddydb_full.json` dump (497
entries, 8 of which are unused placeholder rows literally named `"text"` --
dropped at build time). None of that dump carries type/attribute/Omicron
classification, so those three came from the wiki's own category listings
instead: `Category:Companions` (489 members) supplied the ground-truth wiki
title for each companion, cross-referenced by name against the dump; the 7
`Category:*_companion` "type" subcategories (100% coverage, no companion is
untyped) and 11 attribute subcategories (only ~45% coverage -- most companions
have no elemental attribute at all) tagged each entry; `Category:Omicron_companion`
flagged the recoded-tier variants. Only category-listing API calls were made,
never a per-companion page scrape -- 489 individual page visits would have been
needlessly heavy for data three category listings + the local dump already gave.

Three lookup axes exist because none sorts evenly on its own: 7 rarity tiers
span D-Z (mirrors `monsters.py`), 7 wiki types (`Bow`/`Metal`/`Other`/`Shield`/
`Spear`/`Staff`/`Sword`) have 100% coverage, and Omicron (recoded-tier)
companions split cleanly into 3 sub-tiers (`Ο`/`ΟⅡ`/`ΟⅢ` in their own names --
I/II/III). Omicron entries are excluded from the default rarity/type listings
(they overwhelmingly cluster in Z-rarity and the "Other" type -- 129 of 131 are
Z, 126 of 131 are "Other" -- and dominating those buckets is exactly what made
them oversized) and get their own tier listing instead. Even after that split,
"Other" alone still has 202 non-Omicron entries (~2500 characters, over
Discord's 2000-char message limit) -- `resolve_axis`/`render_filtered` let a
second token narrow any listing by a second axis (e.g. `!tb1.buddy Z Sword`),
which keeps every combination comfortably under the limit (worst case: 37).
Attribute is still shown only on a single entry's own info card, not as a
lookup axis, since its ~45% coverage makes it too sparse to browse by.

None of this replaces the bot's own `chunk_message` (still a safety net for
`!tb1.buddy Other` on its own, or anything else that ends up oversized) -- it
just means normal browsing rarely needs to fall back on it.

Shares its name-normalization/grid-rendering/name-lookup plumbing with
`characters.py`/`monsters.py`/`items.py` via `_catalog.py` -- see that module's
own docstring for why the rarity/type/Omicron-indexing logic below (which has
real per-catalog differences, e.g. the Omicron-exclusion this file's own axes
need) still isn't shared.

@author: Luraminaki
"""

import json
import logging
import pathlib

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from modulesKIT.modules.tb1 import _catalog

if TYPE_CHECKING:
    from modulesKIT.modules.helpers.generic_config import AppConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Companions span the full scale, same as monsters (unlike playable characters,
# which only ever reach B-Z).
RARITY_ORDER = _catalog.RARITY_ORDER

# A single-axis listing rendering past this length asks for a second filter
# instead of falling back on the bot's `chunk_message` -- narrower than
# Discord's real 2000-char limit to leave headroom rather than cut it close.
_SAFE_LENGTH = 1900


class BuddyEntry(BaseModel):
    """One TB1 companion.

    Attributes:
        name: Display name, e.g. `"Healing Wand"` or `"Metal Minion Λ"` for an
            awakened form.
        rarity: Rarity grade, one of `RARITY_ORDER`.
        link: Wiki page for the companion.
        type_: Wiki type category (`Bow`/`Metal`/`Other`/`Shield`/`Spear`/
            `Staff`/`Sword`) -- every companion has exactly one. Aliased to
            `buddy.json`'s `"type"` key (`type` alone would shadow the builtin).
        attribute: Elemental wiki category, if any -- most companions have none.
        omicron: Whether this is a recoded (Omicron) tier variant.
        omicron_tier: `"Omicron I"`/`"Omicron II"`/`"Omicron III"` if `omicron`
            is set, derived from the name's `Ο`/`ΟⅡ`/`ΟⅢ` suffix; `None` otherwise.
    """

    name: str
    rarity: str
    link: str
    type_: str | None = Field(default=None, alias='type')
    attribute: str | None = None
    omicron: bool = False
    omicron_tier: str | None = None


def _omicron_tier(name: str) -> str:
    """Derive a companion's Omicron sub-tier from its own name.

    Args:
        name: An Omicron-flagged companion's display name, e.g. `"Bahl ΟⅡ"`.

    Returns:
        `"Omicron III"` or `"Omicron II"` if the name has that Roman-numeral
        suffix, else `"Omicron I"` for the plain `Ο`/`O` suffix.
    """
    if 'Ⅲ' in name:
        return 'Omicron III'
    if 'Ⅱ' in name:
        return 'Omicron II'
    return 'Omicron I'


class BuddyCatalog(_catalog.NameIndexedCatalog[BuddyEntry]):
    """Loads the TB1 companion catalog from `buddy.json`, keyed by display name."""

    def __init__(self, module_name: str | None = None,
                 modules_config: 'AppConfig | None' = None) -> None:
        """Load this module's companion data file.

        Args:
            module_name: Name of this module, used to look up its data folder.
            modules_config: Loaded application configuration.

        Raises:
            ValueError: If `module_name` or `modules_config` is missing.
        """
        if not modules_config or not module_name:
            raise ValueError(f"{self.__class__.__name__} -- Invalid module_name configuration file provided -- {module_name} : {modules_config}")

        data_path = pathlib.Path(modules_config.directories.data_directory) / module_name / 'buddy.json'
        raw: dict[str, dict[str, object]] = json.loads(data_path.read_text(encoding='utf-8'))

        self.buddies: list[BuddyEntry] = [BuddyEntry.model_validate({'name': name, **info})
                                          for name, info in raw.items()]
        super().__init__(self.buddies)

        self._by_rarity: dict[str, list[str]] = {}
        self._by_type: dict[str, list[str]] = {}
        self._type_labels: dict[str, str] = {}
        self._by_omicron_tier: dict[str, list[str]] = {}
        self._omicron_tier_labels: dict[str, str] = {}

        for entry in self.buddies:
            if entry.omicron:
                entry.omicron_tier = _omicron_tier(entry.name)
                key = _catalog.normalize(entry.omicron_tier)
                self._by_omicron_tier.setdefault(key, []).append(entry.name)
                self._omicron_tier_labels[key] = entry.omicron_tier
                # Omicron entries are excluded from the plain rarity/type
                # listings below -- see the module docstring for why.
                continue

            self._by_rarity.setdefault(entry.rarity, []).append(entry.name)
            if entry.type_:
                key = _catalog.normalize(entry.type_)
                self._by_type.setdefault(key, []).append(entry.name)
                self._type_labels[key] = entry.type_

        self.rarities_present: list[str] = [rarity for rarity in reversed(RARITY_ORDER) if rarity in self._by_rarity]
        # Declaration order (wiki's own, roughly weapon-shaped-first) reads
        # better here than an alphabetical sort would.
        self.types_present: list[str] = list(self._type_labels.values())
        self.omicron_tiers_present: list[str] = [self._omicron_tier_labels[key] for key in
                                                 ('omicroni', 'omicronii', 'omicroniii') if key in self._omicron_tier_labels]

    def find_rarity(self, query: str) -> str | None:
        """Resolve a user-typed rarity grade, case-insensitively.

        Args:
            query: Rarity grade as typed by the user (`d`, `D`, `ss`, ...).

        Returns:
            The matching grade from `RARITY_ORDER`, or `None` if `query` isn't
            one, or is one with no companions actually in it.
        """
        rarity = query.strip().upper()
        return rarity if rarity in self._by_rarity else None

    def find_type(self, query: str) -> str | None:
        """Resolve a user-typed wiki type, tolerant of casing/spacing.

        Args:
            query: Type as typed by the user (`sword`, `Staff`, ...).

        Returns:
            The matching type's canonical label, or `None` if `query` doesn't
            resolve to one.
        """
        return self._type_labels.get(_catalog.normalize(query))

    def find_omicron_tier(self, query: str) -> str | None:
        """Resolve a user-typed Omicron tier, tolerant of casing/spacing.

        Args:
            query: Tier as typed by the user (`OmicronII`, `omicron iii`, ...).

        Returns:
            The matching tier's canonical label (`"Omicron I"`/`"II"`/`"III"`),
            or `None` if `query` doesn't resolve to one.
        """
        return self._omicron_tier_labels.get(_catalog.normalize(query))

    def resolve_axis(self, query: str) -> tuple[str, str] | None:
        """Resolve a user-typed token against all 3 filterable axes.

        Args:
            query: A single token, tried in turn as a rarity, a wiki type,
                then an Omicron tier.

        Returns:
            `(axis, canonical_value)` where `axis` is one of `"rarity"`,
            `"type_"`, `"omicron_tier"` (matching `render_filtered`'s keyword
            names), or `None` if `query` matched none of the three.
        """
        rarity = self.find_rarity(query)
        if rarity is not None:
            return ('rarity', rarity)

        type_ = self.find_type(query)
        if type_ is not None:
            return ('type_', type_)

        tier = self.find_omicron_tier(query)
        if tier is not None:
            return ('omicron_tier', tier)

        return None

    def render_usage(self) -> str:
        """Render the `!tb1.buddy` usage hint shown when no query was given.

        Returns:
            Markdown-formatted usage text listing the rarities, types, and
            Omicron tiers in use.
        """
        rarities = ', '.join(f"`{rarity}`" for rarity in self.rarities_present)
        types = ', '.join(f"`{type_}`" for type_ in self.types_present)
        tiers = ', '.join(f"`{tier}`" for tier in self.omicron_tiers_present)
        return '\n'.join(["**Terra Battle Companions**",
                          "Specify a rarity grade, a wiki type, an Omicron tier, or a companion name:",
                          f"- `!tb1.buddy <rarity>` -- lists that tier, e.g. `!tb1.buddy Z` (grades in use: {rarities})",
                          f"- `!tb1.buddy <type>` -- lists that type, e.g. `!tb1.buddy Sword` (types in use: {types})",
                          f"- `!tb1.buddy <tier>` -- lists that Omicron tier, e.g. `!tb1.buddy OmicronII` (tiers in use: {tiers})",
                          "- `!tb1.buddy <rarity/type/tier> <rarity/type/tier>` -- combine two of the above to narrow further, e.g. `!tb1.buddy Z Sword`",
                          "- `!tb1.buddy <name>` -- looks up a companion's wiki page, e.g. `!tb1.buddy HealingWand` (spaces optional)",
                          "- `!tb1.buddy random` -- looks up a random companion"])

    def _render_or_require_filter(self, label: str, names: list[str]) -> str:
        """Render a single-axis listing, or ask for a second filter if it's too big.

        Whether a listing needs a second filter is measured against its actual
        rendered length, not a hardcoded axis name -- today only the "Other"
        wiki type crosses `_SAFE_LENGTH` (202 non-Omicron entries, ~2500
        characters), but this stays correct if the underlying data ever shifts
        which bucket is the biggest one instead of needing a matching code change.

        Args:
            label: The axis value being rendered, e.g. `"Z"` or `"Other"`.
            names: Companion names in that bucket.

        Returns:
            The rendered grid, or a message asking for a second filter.
        """
        grid = _catalog.render_grid(f"{label} ({len(names)})", names)
        if len(grid) <= _SAFE_LENGTH:
            return grid

        return '\n'.join([f"**{label}** has {len(names)} companions -- too many for one message on its own.",
                          f"Add a second rarity/type/Omicron-tier filter to narrow it down, e.g. `!tb1.buddy {label} <rarity/type/tier>`."])

    def render_tier(self, rarity: str) -> str:
        """Render one rarity tier's companions as a name grid.

        Args:
            rarity: A grade returned by `find_rarity` (i.e. known non-empty).

        Returns:
            Markdown-formatted tier listing, or a second-filter prompt if it's too big.
        """
        return self._render_or_require_filter(rarity, self._by_rarity[rarity])

    def render_type(self, type_: str) -> str:
        """Render one wiki type's companions as a name grid.

        Args:
            type_: A canonical label returned by `find_type`.

        Returns:
            Markdown-formatted type listing, or a second-filter prompt if it's too big.
        """
        return self._render_or_require_filter(type_, self._by_type[_catalog.normalize(type_)])

    def render_omicron_tier(self, tier: str) -> str:
        """Render one Omicron tier's companions as a name grid.

        Args:
            tier: A canonical label returned by `find_omicron_tier`.

        Returns:
            Markdown-formatted tier listing, or a second-filter prompt if it's too big.
        """
        return self._render_or_require_filter(tier, self._by_omicron_tier[_catalog.normalize(tier)])

    def render_filtered(self, rarity: str | None = None, type_: str | None = None,
                        omicron_tier: str | None = None) -> str:
        """Render companions matching every given axis (an AND filter across up to 3).

        Scans the full roster (unlike `render_tier`/`render_type`, which work
        off the Omicron-excluded listings) so an explicit combination like
        `rarity="Z", omicron_tier="Omicron I"` still finds its (small) matches.

        Args:
            rarity: A canonical grade from `find_rarity`, or `None` to not filter on it.
            type_: A canonical label from `find_type`, or `None` to not filter on it.
            omicron_tier: A canonical label from `find_omicron_tier`, or `None`
                to not filter on it.

        Returns:
            Markdown-formatted matching-companion grid, or a "no matches" message.
        """
        matches = [entry.name for entry in self.buddies
                   if (rarity is None or entry.rarity == rarity)
                   and (type_ is None or entry.type_ == type_)
                   and (omicron_tier is None or entry.omicron_tier == omicron_tier)]

        label = ' + '.join(part for part in (rarity, type_, omicron_tier) if part is not None)
        if not matches:
            return f"No companions match **{label}**."

        return _catalog.render_grid(f"{label} ({len(matches)})", matches)

    def render_entry(self, entry: BuddyEntry) -> str:
        """Render one companion's info card as markdown text.

        Args:
            entry: The entry to render.

        Returns:
            Markdown-formatted companion info: name, rarity, type, attribute
            (if any), Omicron flag (if set), and a wiki link left unmasked so
            Discord auto-embeds a preview of the page.
        """
        tags = [f"Rarity {entry.rarity}"]
        if entry.type_:
            tags.append(f"Type: {entry.type_}")
        if entry.attribute:
            tags.append(f"Attribute: {entry.attribute}")
        if entry.omicron:
            tags.append("Omicron")

        return '\n'.join([f"## **{entry.name}**",
                          f"-# {' | '.join(tags)}",
                          f"- [Wiki Content]({entry.link})"])
