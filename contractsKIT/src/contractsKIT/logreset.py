#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@description: Helper function to reset logging configuration. This can be useful in case of multiple processes or modules that configure logging differently, to avoid conflicts and ensure a consistent logging configuration across the project.

Created on Tue Apr 14 14:52:00 2026

@author: Luraminaki
"""

import logging
import logging.config


def reset_logging(conf: dict[str, object] | None = None) -> None:
    """Reset logging.

    Removes any configured handlers and filters.
    Sets new configuration (if provided).

    Args:
        conf: `logging.config.dictConfig`-style configuration to apply afterwards,
            if any. Defaults to `None` (leaves logging unconfigured).
    """
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    for log_filter in root.filters[:]:
        root.removeFilter(log_filter)

    if conf is not None:
        logging.config.dictConfig(conf)
