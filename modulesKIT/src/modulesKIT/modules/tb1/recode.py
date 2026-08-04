#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TB1 recode (base -> Λ awakened form) pairs, derived from already-loaded
`characters.CharacterCatalog`/`monsters.MonsterCatalog` -- no separate data file.

A recoded Λ form is always named `"<base name> Λ"` (confirmed against
`chrdb_full.json`'s `rebirth_from`/`ancestor` fields, which link a Λ entry back
to its base by ID -- but since both ends of that link are already present as
plain names in one roster or the other, deriving pairs by name is simpler and
avoids needing chr_id at all). Its base is usually another character, but the
wiki's own Monsters page notes "Recoded monsters turn into Adventurers" -- e.g.
`Lich Λ`/`Marilith Λ`/`Seiryu Λ` are characters whose base form is a monster --
so a Λ form with no match in the character roster falls back to the monster
roster before being treated as unresolved.

@author: Luraminaki
"""

import logging

from pydantic import BaseModel

from modulesKIT.modules.tb1 import _catalog, characters, monsters

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_LAMBDA_SUFFIX = f" {_catalog.LAMBDA}"


class RecodePair(BaseModel):
    """One base character and its recoded (Λ) form.

    Attributes:
        base: Base character's display name.
        recoded: Recoded (Λ) form's display name.
        base_link: Base character's wiki page.
        recoded_link: Recoded form's wiki page.
    """

    base: str
    recoded: str
    base_link: str
    recoded_link: str


def _derive_pairs(catalog: characters.CharacterCatalog,
                   monster_catalog: monsters.MonsterCatalog | None = None) -> list[RecodePair]:
    """Find every roster entry with a resolvable base and pair them up.

    Args:
        catalog: An already-loaded character roster.
        monster_catalog: An already-loaded monster roster, checked as a
            fallback for a Λ form whose base isn't a character (a recoded
            monster that graduated to Adventurer status). `None` skips that
            fallback entirely.

    Returns:
        Recode pairs, sorted by base name.
    """
    pairs: list[RecodePair] = []

    for entry in catalog.characters:
        if not entry.name.endswith(_LAMBDA_SUFFIX):
            continue

        base_name = entry.name[:-len(_LAMBDA_SUFFIX)]
        base_entry = catalog.find(base_name)
        if base_entry is None and monster_catalog is not None:
            base_entry = monster_catalog.find(base_name)
        if base_entry is None:
            logger.warning("Recode form %r has no matching base entry in either roster -- skipped", entry.name)
            continue

        pairs.append(RecodePair(base=base_entry.name, recoded=entry.name,
                                base_link=base_entry.link, recoded_link=entry.link))

    return sorted(pairs, key=lambda pair: pair.base.casefold())


class RecodeCatalog:
    """Recode (base -> Λ) pairs, numbered for `!tb1.recode <ID>` lookup."""

    def __init__(self, catalog: characters.CharacterCatalog,
                 monster_catalog: monsters.MonsterCatalog | None = None) -> None:
        """Derive every recode pair from `catalog` (and, as a fallback, `monster_catalog`).

        Args:
            catalog: An already-loaded character roster.
            monster_catalog: An already-loaded monster roster, see `_derive_pairs`.
        """
        self.pairs: list[RecodePair] = _derive_pairs(catalog, monster_catalog)

    def render_list(self) -> str:
        """Render every recode pair as a numbered `ID: base -> recoded` list.

        Returns:
            Markdown-formatted list, one pair per line, plus a hint for looking
            up a single pair's wiki links.
        """
        lines = [f"{pair_id}: {pair.base} -> {pair.recoded}" for pair_id, pair in enumerate(self.pairs, start=1)]
        return '\n'.join(["**TB1 Recode Pairs**",
                          "```", *lines, "```",
                          "`!tb1.recode <ID>` for a specific pair's wiki links."])

    def render_pair(self, pair_id: int) -> str | None:
        """Render one recode pair's info card, with both wiki links.

        Args:
            pair_id: 1-based index, as shown by `render_list`.

        Returns:
            Markdown-formatted card, or `None` if `pair_id` is out of range.
        """
        if not 1 <= pair_id <= len(self.pairs):
            return None

        pair = self.pairs[pair_id - 1]
        return '\n'.join([f"## **{pair.base} -> {pair.recoded}**",
                          f"- [{pair.base}]({pair.base_link})",
                          f"- [{pair.recoded}]({pair.recoded_link})"])
