#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TB1 pact-roll simulator, ported from hisobot's `tb1roll.js`.

Rates and unit pools come from `data/tb1/pact.json` (community-estimated,
copied from hisobot as-is). Unlike the original JS command, which mutated the
loaded pact data in place on every call (so special-pact units kept piling up
across repeated rolls until the process restarted), `_build_pool` works on a
fresh copy every time.

`pact.json`'s three special-pact overlays (`"Arachnobot's Tale"`,
`"Vengeful Heart"`, `"Death of Shay and Arionne"`) each added a few guest units
to the pool during their own limited-time banner, back when the game was live.
hisobot let you opt into any subset of them via a `specials` argument -- but by
the time the game was discontinued, all three banners had run concurrently, so
no combination other than "all three" ever reflected a real, live pool state.
`_build_pool` merges all three in unconditionally instead of taking a selection.

@author: Luraminaki
"""

import json
import logging
import pathlib
import random

from collections import Counter
from typing import cast, ClassVar, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from modulesKIT.modules.helpers.generic_config import AppConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BASE_TIERS = ("B", "A", "S", "SS", "Z")
POF_KEY = "Pact of Fellowship"

MIN_PULLS = 1
MAX_PULLS = 100


class PactPool(BaseModel):
    """Parsed contents of `pact.json`.

    Attributes:
        rarities: Rarity tiers, lowest to highest (e.g. `["B","A","S","SS","Z"]`).
        rates: Floor rarity -> {rarity: percentage chance}, sums to 100 per floor.
        base_units: Rarity -> unit names always in the pool.
        pact_of_fellowship: Rarity -> unit names removed once PoF is completed.
        specials: Special pact name -> {rarity: unit names}, all unconditionally merged into every roll's pool.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    rarities: list[str]
    rates: dict[str, dict[str, float]]
    base_units: dict[str, list[str]]
    pact_of_fellowship: dict[str, list[str]]
    specials: dict[str, dict[str, list[str]]]

    @classmethod
    def from_file(cls, path: pathlib.Path) -> 'PactPool':
        """Load and reshape `pact.json` into a `PactPool`.

        `units` in the source file mixes the 5 base rarity tiers with the PoF and
        special-pact overlays under the same dict; this splits them apart.

        Args:
            path: Path to the pact data file.

        Returns:
            The parsed pact pool.
        """
        # `units` mixes two shapes: base tiers map straight to a name list, while
        # the PoF/special-pact overlays nest one level deeper (rarity -> names) --
        # a real heterogeneous dict, not just an under-annotated uniform one, so
        # each access below is cast to the shape that key is actually known to have.
        raw: dict[str, object] = json.loads(path.read_text(encoding='utf-8'))
        units_raw = cast(dict[str, 'list[str] | dict[str, list[str]]'], raw['units'])
        overlay_keys = [key for key in units_raw if key not in BASE_TIERS and key != POF_KEY]

        return cls(rarities=cast(list[str], raw['rarities']),
                   rates=cast(dict[str, dict[str, float]], raw['rates']),
                   base_units={tier: cast(list[str], units_raw[tier]) for tier in BASE_TIERS},
                   pact_of_fellowship=cast(dict[str, list[str]], units_raw[POF_KEY]),
                   specials={key: cast(dict[str, list[str]], units_raw[key]) for key in overlay_keys})


class PulledUnit(BaseModel):
    """A unit pulled one or more times within the same rarity tier.

    Attributes:
        name: Unit name.
        count: Number of times it was pulled.
    """

    name: str
    count: int


class RollResult(BaseModel):
    """Roll results for a single rarity tier.

    Attributes:
        rarity: The rarity tier.
        units: Units pulled at this tier, each with its pull count.
    """

    rarity: str
    units: list[PulledUnit]

    @property
    def total(self) -> int:
        """Total number of pulls landed at this tier."""
        return sum(unit.count for unit in self.units)


class PactRoller:
    """Simulates TB1 pact rolls against the community-estimated rates in `pact.json`."""

    def __init__(self, module_name: str | None = None,
                 modules_config: 'AppConfig | None' = None) -> None:
        """Load this module's pact data file.

        Args:
            module_name: Name of this module, used to look up its data folder.
            modules_config: Loaded application configuration.

        Raises:
            ValueError: If `module_name` or `modules_config` is missing.
        """
        if not modules_config or not module_name:
            raise ValueError(f"{self.__class__.__name__} -- Invalid module_name configuration file provided -- {module_name} : {modules_config}")

        data_path = pathlib.Path(modules_config.directories.data_directory) / module_name / 'pact.json'
        self.pact: PactPool = PactPool.from_file(data_path)

    def _build_pool(self, pof: bool) -> dict[str, list[str]]:
        """Build a per-call copy of the unit pool with PoF removal and all special-pact units merged in.

        Args:
            pof: Whether Pact of Fellowship has been completed.

        Returns:
            Rarity -> candidate unit names for this roll.
        """
        pool: dict[str, list[str]] = {tier: list(names) for tier, names in self.pact.base_units.items()}

        if pof:
            for tier, pof_units in self.pact.pact_of_fellowship.items():
                pool[tier] = [unit for unit in pool[tier] if unit not in pof_units]

        for special_units in self.pact.specials.values():
            for tier, units in special_units.items():
                pool.setdefault(tier, []).extend(units)

        return pool

    def _pull_once(self, rates: dict[str, float], pool: dict[str, list[str]]) -> tuple[str, str]:
        """Simulate a single pull: pick a rarity per `rates`, then a unit from `pool`.

        Args:
            rates: Rarity -> percentage chance table for the roll's floor rarity.
            pool: Rarity -> candidate unit names.

        Returns:
            `(rarity, unit_name)` of the pulled unit.

        Raises:
            ValueError: If `rates` doesn't sum to 100 (shouldn't happen with the
                shipped `pact.json`).
        """
        remaining = random.randrange(100)

        for rarity, chance in rates.items():
            if chance > remaining:
                return rarity, random.choice(pool[rarity])
            remaining -= chance

        raise ValueError(f"Rates table did not sum to 100: {rates}")

    def roll(self, pulls: int, pof: bool, base: str) -> list[RollResult]:
        """Simulate `pulls` pact rolls.

        Args:
            pulls: Number of rolls to simulate, 1-100.
            pof: Whether Pact of Fellowship has been completed (excludes its units).
            base: Lowest remaining rarity in the player's pool (`B`/`A`/`S`/`SS`/`Z`).

        Returns:
            One `RollResult` per rarity that was actually pulled, in `pact.rarities` order.

        Raises:
            ValueError: If `pulls` is out of range or `base` isn't a known rarity.
        """
        if not MIN_PULLS <= pulls <= MAX_PULLS:
            raise ValueError(f"pulls must be between {MIN_PULLS} and {MAX_PULLS}, got {pulls}")

        base = base.strip().upper()
        if base not in self.pact.rates:
            raise ValueError(f"Unknown base rarity: {base!r}, expected one of {self.pact.rarities}")

        pool = self._build_pool(pof)
        rates = self.pact.rates[base]

        tallies: dict[str, Counter[str]] = {}
        for _ in range(pulls):
            rarity, unit = self._pull_once(rates, pool)
            tallies.setdefault(rarity, Counter())[unit] += 1

        return [RollResult(rarity=rarity,
                           units=[PulledUnit(name=name, count=count) for name, count in tallies[rarity].items()])
                for rarity in self.pact.rarities if rarity in tallies]

    def render(self, results: list[RollResult]) -> str:
        """Render roll results as markdown text.

        Args:
            results: Output of `roll`.

        Returns:
            Markdown-formatted summary, one line per rarity that was pulled.
        """
        if not results:
            return "No pulls simulated."

        lines = [f"**{result.rarity} ({result.total})**: " +
                ', '.join(f"{unit.name} ({unit.count})" for unit in result.units)
                for result in results]

        return '\n'.join(["**Terra Battle Pact Simulation**",
                          *lines,
                          "*NOTE: These pulls are not binding or guaranteed!*"])
