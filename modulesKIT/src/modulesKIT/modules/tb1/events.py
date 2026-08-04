#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Info cards for TB1's special quests/events, loaded from `data/tb1/events.json`.

`vh` and `arachnobot` were ported from hisobot's `vh.js`/`arachnobot.js` (both
Discord Rich Embeds with no dynamic data -- hardcoded title/link/image, so there
was no scheduling to port, only the content itself). Every other entry, including
`dosa`, has no hisobot precedent: `pact.json` and `tb1roll.js`'s own usage
examples treat "Death of Shay and Arionne" as a first-class special pact alongside
`vh`/`arachnobot`, but hisobot never shipped a matching info command for it, and a
wider wiki audit turned up the rest. Content for all of these is sourced directly
from the Terra Battle Wiki.

Kept as a JSON data file rather than a hardcoded dict because there are dozens of
entries -- matches this repo's existing convention of data living in `data/` and
code staying thin (see `pact.json`, `anyquotes`'s CSVs).

@author: Luraminaki
"""

import json
import logging
import pathlib

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from modulesKIT.modules.helpers.generic_config import AppConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class EventInfo(BaseModel):
    """Info card for a single TB1 special quest/event.

    Attributes:
        title: Event title.
        credit: Attribution for the linked chart/image, or a short factual
            description when no dedicated chart exists for this event.
        link: Wiki (or forum) page for the event.
        image_url: Chart/banner image, if a genuine event-specific one exists.
        note: Short footer note.
        aliases: Extra command names that should also resolve to this event.
        flowchart_file: Filename of a local flowchart image archived under
            `data/tb1/events/<key>/`, if this event has one. Unlike `image_url`
            (always a live external link), a flowchart is meant to be sent as a
            real Discord attachment -- see `EventCatalog.flowchart_path`.
    """

    title: str
    credit: str
    link: str
    image_url: str = ''
    note: str = "Limited time event"
    aliases: list[str] = []
    flowchart_file: str = ''


class EventCatalog:
    """Loads every TB1 event's info card from `events.json`, keyed by command name."""

    def __init__(self, module_name: str | None = None,
                 modules_config: 'AppConfig | None' = None) -> None:
        """Load this module's event data file.

        Args:
            module_name: Name of this module, used to look up its data folder.
            modules_config: Loaded application configuration.

        Raises:
            ValueError: If `module_name` or `modules_config` is missing.
        """
        if not modules_config or not module_name:
            raise ValueError(f"{self.__class__.__name__} -- Invalid module_name configuration file provided -- {module_name} : {modules_config}")

        module_data_dir = pathlib.Path(modules_config.directories.data_directory) / module_name
        data_path = module_data_dir / 'events.json'
        raw: dict[str, dict[str, object]] = json.loads(data_path.read_text(encoding='utf-8'))

        self.events: dict[str, EventInfo] = {key: EventInfo.model_validate(value) for key, value in raw.items()}
        self._events_dir: pathlib.Path = module_data_dir / 'events'

    def flowchart_path(self, key: str) -> pathlib.Path | None:
        """The local flowchart image path for `key`, if it has one and it exists on disk.

        Args:
            key: Key into `self.events`.

        Returns:
            The resolved path, or `None` if this event has no `flowchart_file` set
            or the file is missing.
        """
        info = self.events[key]
        if not info.flowchart_file:
            return None

        path = self._events_dir / key / info.flowchart_file
        return path if path.is_file() else None

    def render(self, key: str) -> str:
        """Render one event's info card as markdown text.

        Args:
            key: Key into `self.events`.

        Returns:
            Markdown-formatted event info: title, credit/description, a masked
            `[Banner](...)` link if a chart image exists (left free to auto-embed,
            so the actual picture shows), and a masked `[Wiki Content](...)` link
            to the wiki/forum page with its own preview suppressed via `<...>` --
            without that, Discord's link-preview embed for the wiki page (built
            from that page's own `og:image`) duplicates the same banner picture
            a second time.
        """
        info = self.events[key]
        lines = [f"## **{info.title}**", f"-# {info.credit}"]

        if info.image_url:
            lines.append(f"- [Banner](<{info.image_url}>)")

        lines.append(f"- [Wiki Content]({info.link})")
        lines.append(f"*{info.note}*")

        return '\n'.join(lines)
