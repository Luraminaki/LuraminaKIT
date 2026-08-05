#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 21 13:47:01 2025

@author: Luraminaki
"""

import logging

from typing import TYPE_CHECKING

from contractsKIT import StandardResponse
from modulesKIT.modules.helpers import generic_api_views
from modulesKIT.modules.anyquotes import anyquotes

if TYPE_CHECKING:
    from modulesKIT.modules.helpers.generic_config import AppConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class QuotesView(generic_api_views.GenericViews):
    """Exposes the `/quote` route backed by `anyquotes.AnyQuotes`."""

    def __init__(self, modules_config: 'AppConfig | None' = None, *args, **kwargs) -> None:
        """Load the module's quote files and register the `/quote` route.

        Args:
            modules_config: Loaded application configuration.
            *args: Forwarded to `GenericViews`.
            **kwargs: Forwarded to `GenericViews`.
        """
        super().__init__(*args, modules_config=modules_config, **kwargs)

        self.aq: anyquotes.AnyQuotes = anyquotes.AnyQuotes(self.module_name, modules_config)
        self.add_route("/quote",
                       self.quote,
                       methods=['GET'],
                       response_model=StandardResponse[str],
                       description=f"Picks a random quote from the {', '.join(file.stem for file in self.aq.q_data)} file(s) available")

    async def quote(self) -> StandardResponse[str]:
        """Return a random quote.

        Returns:
            A `StandardResponse` wrapping the rendered quote, or an error if none
            could be picked.
        """
        try:
            if not (res := self.aq.get_random_quote_from_csv()):
                return StandardResponse[str].fail('')

        except Exception as err:
            logger.error("%r", err)
            return StandardResponse[str].fail(repr(err))

        return StandardResponse[str].ok(res)
