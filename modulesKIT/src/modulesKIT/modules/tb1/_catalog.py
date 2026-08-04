#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared name-normalization, grid-rendering, and name-lookup helpers for tb1's
catalogs (`characters`/`monsters`/`items`/`buddy`).

Each catalog was originally written independently and carried its own copy of
these three pieces, byte-for-byte identical (`items.py`'s `_normalize` was the
one exception -- it skipped the `Λ`-handling since no item name needs it, but
applying that same handling there is harmless: it's simply a no-op for every
item name). That duplication had a real cost, not just a stylistic one: the
block-chunking fix for oversized listings (splitting a listing into multiple
complete fenced blocks so Discord's message chunker never cuts through a code
fence) had to be discovered once and then hand-applied three more times to catch
up the other three files. Extracting the identical parts here means a future
fix like that only has to happen once.

What's deliberately *not* here: rarity/type/category-indexing logic
(`find_rarity`, `_by_rarity`, ...). Those look similar across catalogs at a
glance, but `buddy.py`'s rarity index excludes Omicron-flagged entries while
`characters.py`/`monsters.py`'s don't, and `items.py` doesn't have a rarity axis
at all -- forcing those into a shared shape would trade a small amount of
duplication for a genuinely confusing abstraction. Only the parts that were
truly identical got moved.

@author: Luraminaki
"""

import re

from typing import Generic, Protocol, TypeVar

LAMBDA = 'Λ'

# Rarity grades, lowest to highest. Playable adventurers only span B-Z in
# practice (D/C are generic recruitable mobs' territory), but the full scale is
# kept here so sorting/rendering doesn't silently break if that ever changes.
RARITY_ORDER: tuple[str, ...] = ('D', 'C', 'B', 'A', 'S', 'SS', 'Z')

# Target character width for each tier/category's name grid -- picked to stay
# readable in Discord's mobile code-block view (which doesn't wrap, only
# scrolls) while still fitting 2-4 names per row instead of one unbroken
# comma-separated line.
GRID_WIDTH = 42

# Keeps any single fenced block comfortably under Discord's 2000-character
# message limit even at GRID_WIDTH's widest row -- see `render_grid`.
MAX_ROWS_PER_BLOCK = 40


def normalize(text: str) -> str:
    """Fold a name/query down to a bare lowercase alnum key for lookup.

    LuraminaKIT's command dispatcher splits arguments on whitespace and matches
    them positionally, so a user typing a multi-word name (or an awakened `Λ`
    form) would only ever have the first word arrive as a single-word param.
    Stripping every non-alphanumeric character sidesteps that entirely --
    `JadeDragon` and `Jade Dragon` fold to the same key -- and `Λ` is spelled
    out as `lambda` first so it survives that same stripping instead of being
    dropped, keeping an awakened form distinguishable from its base one
    (`bahl` vs `bahllambda`). Typing the literal `Λ` still works too, whether
    or not it's glued onto the previous word, since it folds to the same
    `lambda` text.

    Args:
        text: A stored name/category or a user-typed query.

    Returns:
        The normalized lookup key.
    """
    return re.sub(r'[^a-z0-9]', '', text.strip().lower().replace(LAMBDA.lower(), 'lambda'))


def render_grid(header: str, names: list[str]) -> str:
    """Render a header plus one or more monospaced name grids.

    A single comma-separated line reads fine for a handful of names, but some
    of these catalogs have well over a hundred entries in one bucket -- an
    unbroken wall of text at that size. A fixed-width grid (column count picked
    from the longest name in this particular listing, so one with a few long
    names doesn't force sparse columns onto every other listing) keeps it
    scannable, and capping each fenced block at `MAX_ROWS_PER_BLOCK` rows keeps
    every block comfortably under Discord's 2000-character message limit --
    a single unbroken block that size would risk the bot's own `chunk_message`
    slicing mid-block, leaving a dangling ` ``` ` in one message and an orphaned
    one in the next.

    Args:
        header: Header line, e.g. `"Z (168)"` or `"Tickets (3)"`.
        names: Entry names, any order.

    Returns:
        A bold header line followed by one or more fenced code block grids.
    """
    ordered = sorted(names, key=str.casefold)
    col_width = max(len(name) for name in ordered) + 2
    num_cols = max(1, GRID_WIDTH // col_width)

    rows = [''.join(name.ljust(col_width) for name in ordered[i:i + num_cols]).rstrip()
            for i in range(0, len(ordered), num_cols)]

    blocks = ['\n'.join(rows[i:i + MAX_ROWS_PER_BLOCK]) for i in range(0, len(rows), MAX_ROWS_PER_BLOCK)]
    fenced = '\n'.join(f"```\n{block}\n```" for block in blocks)

    return f"**{header}**\n{fenced}"


class _Named(Protocol):
    """Structural type for any catalog entry with a `.name` -- see `NameIndexedCatalog`."""

    name: str


EntryT = TypeVar('EntryT', bound=_Named)


class NameIndexedCatalog(Generic[EntryT]):
    """Base class providing name-keyed lookup, shared by every tb1 catalog.

    Subclasses call `super().__init__(entries)` after building their own
    entry list, then keep whatever axis-specific indexing (`_by_rarity`,
    `_by_category`, ...) they each need on top of this.
    """

    def __init__(self, entries: list[EntryT]) -> None:
        """Build the name -> entry index.

        Args:
            entries: Every entry in this catalog.
        """
        self._by_key: dict[str, EntryT] = {normalize(entry.name): entry for entry in entries}

    def find(self, query: str) -> EntryT | None:
        """Resolve a user-typed name to its catalog entry.

        Args:
            query: Name as typed by the user, in any casing/spacing (see `normalize`).

        Returns:
            The matching entry, or `None` if `query` doesn't resolve to one.
        """
        return self._by_key.get(normalize(query))
