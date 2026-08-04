#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TB1 daily-quest rotation forecast.

The 41-day rotation, its epoch, and the quest-name mapping below are ported from
a reverse-engineered analysis of the game's own daily-quest computation, not
from hisobot's own copy, so forecasts match the game's actual rotation logic
exactly.

@author: Luraminaki
"""

import logging

from datetime import date, datetime, timedelta, UTC

from pydantic import BaseModel

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DAILY_EPOCH = date(2015, 1, 1)
ROTATION_LENGTH = 41

MIN_FORECAST_DAYS = 1
MAX_FORECAST_DAYS = 7
DEFAULT_FORECAST_DAYS = 3

# Daily-quest 41-day rotation, two slots per day ("chapterId-sectionNo"). Ported
# verbatim from the reverse-engineered rotation table (day 1 at index 0).
DAILY_ROTATION: list[tuple[str, str]] = [
    ("6004-1", "6000-1"),
    ("6005-1", "6003-1"),
    ("6011-2", "6006-1"),
    ("6010-1", "6011-1"),
    ("6002-1", "6009-1"),
    ("6005-1", "6012-1"),
    ("6008-1", "6010-1"),
    ("6004-1", "6003-1"),
    ("6000-1", "6011-2"),
    ("6007-1", "6006-1"),
    ("6005-1", "6009-1"),
    ("6000-1", "6001-1"),
    ("6010-1", "6006-1"),
    ("6003-1", "6004-1"),
    ("6007-1", "6011-2"),
    ("6002-1", "6012-1"),
    ("6010-1", "6011-1"),
    ("6009-1", "6006-1"),
    ("6001-1", "6007-1"),
    ("6008-1", "6002-1"),
    ("6012-1", "6004-1"),
    ("6000-1", "6005-1"),
    ("6003-1", "6011-2"),
    ("6006-1", "6010-1"),
    ("6011-1", "6002-1"),
    ("6009-1", "6005-1"),
    ("6012-1", "6008-1"),
    ("6010-1", "6004-1"),
    ("6003-1", "6000-1"),
    ("6011-2", "6007-1"),
    ("6006-1", "6005-1"),
    ("6009-1", "6000-1"),
    ("6001-1", "6010-1"),
    ("6006-1", "6003-1"),
    ("6004-1", "6007-1"),
    ("6011-2", "6002-1"),
    ("6012-1", "6010-1"),
    ("6011-1", "6009-1"),
    ("6006-1", "6001-1"),
    ("6007-1", "6008-1"),
    ("6002-1", "6012-1"),
]

# Confirmed chapter-id -> quest name mapping (tested 2026-05-30).
# NOTE: 6004 is marked uncertain ("Particle Hoarder Horde?") in the upstream
# source comment -- carried over here rather than presented as confirmed.
DAILY_QUEST_NAMES: dict[str, str] = {
    "6000-1": "Metal Runner Rampage",
    "6001-1": "Puppet Pandemonium",
    "6002-1": "Crystal Roundelay",
    "6003-1": "Hedgehog Hullabaloo",
    "6004-1": "Particle Hoarder Horde?",
    "6005-1": "Rarity Rumble",
    "6006-1": "Sweet Temptation",
    "6007-1": "Tropical Haze",
    "6008-1": "Tearjerker Time",
    "6009-1": "Hidden Stars",
    "6010-1": "Lucky Orbling",
    "6011-1": "Yamamoto's Puzzle Quest",
    "6011-2": "Yamamoto's Puzzle Quest II",
    "6012-1": "The Hunt for Joker",
}


class DailyQuestForecastEntry(BaseModel):
    """One forecasted day's daily-quest slots.

    Attributes:
        label: Display label for the day (`"Today"`, `"Tomorrow"`, or an ISO date).
        quest_1: Name of the first daily-quest slot.
        quest_2: Name of the second daily-quest slot.
    """

    label: str
    quest_1: str
    quest_2: str


class DailyQuestSchedule:
    """Computes TB1's 41-day daily-quest rotation and forecasts it forward."""

    def rotation_day_index(self, on_date: date) -> int:
        """Return `on_date`'s 0-based index into `DAILY_ROTATION`.

        Args:
            on_date: The date to resolve.

        Returns:
            The rotation day index, 0-40.
        """
        return (on_date - DAILY_EPOCH).days % ROTATION_LENGTH

    def quests_for(self, on_date: date) -> tuple[str, str]:
        """Return the two daily-quest names active on `on_date`.

        Args:
            on_date: The date to resolve.

        Returns:
            `(quest_1_name, quest_2_name)`.
        """
        dq1_id, dq2_id = DAILY_ROTATION[self.rotation_day_index(on_date)]
        return DAILY_QUEST_NAMES.get(dq1_id, dq1_id), DAILY_QUEST_NAMES.get(dq2_id, dq2_id)

    def forecast(self, days: int = DEFAULT_FORECAST_DAYS) -> list[DailyQuestForecastEntry]:
        """Forecast the daily quests for the next `days` days, starting today (UTC).

        Args:
            days: Number of days to forecast, 1-7.

        Returns:
            One `DailyQuestForecastEntry` per forecasted day, starting with today.

        Raises:
            ValueError: If `days` is out of range.
        """
        if not MIN_FORECAST_DAYS <= days <= MAX_FORECAST_DAYS:
            raise ValueError(f"days must be between {MIN_FORECAST_DAYS} and {MAX_FORECAST_DAYS}, got {days}")

        today = datetime.now(UTC).date()
        entries: list[DailyQuestForecastEntry] = []

        for offset in range(days):
            target = today + timedelta(days=offset)
            label = "Today" if offset == 0 else "Tomorrow" if offset == 1 else target.isoformat()
            quest_1, quest_2 = self.quests_for(target)
            entries.append(DailyQuestForecastEntry(label=label, quest_1=quest_1, quest_2=quest_2))

        return entries

    def render(self, entries: list[DailyQuestForecastEntry]) -> str:
        """Render a forecast as markdown text.

        Args:
            entries: Output of `forecast`.

        Returns:
            Markdown-formatted forecast, one line per day.
        """
        lines = [f"**{entry.label}**: {entry.quest_1} / {entry.quest_2}" for entry in entries]
        return '\n'.join(["**TB1 Daily Quest Forecast (UTC)**", *lines])
