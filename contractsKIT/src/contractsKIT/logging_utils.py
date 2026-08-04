#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared logging setup for modulesKIT/LuraminaKIT launcher scripts."""

import logging

from logging.handlers import RotatingFileHandler

import contractsKIT.logreset as logreset

_DEFAULT_MAX_BYTES = 5 * 1024 * 1024
_DEFAULT_BACKUP_COUNT = 5


def configure_launcher_logging(logger: logging.Logger, log_file_stem: str,
                               max_bytes: int = _DEFAULT_MAX_BYTES,
                               backup_count: int = _DEFAULT_BACKUP_COUNT) -> None:
    """Initialize logging consistently across launcher scripts.

    The log file rotates once it reaches `max_bytes`, keeping up to `backup_count`
    older files (`<log_file_stem>.log.1`, `.2`, ...) before the oldest is discarded.

    Args:
        logger: The logger instance to configure.
        log_file_stem: The stem for the log file name.
        max_bytes: Size in bytes a log file may reach before it rolls over.
            Defaults to 5 MiB.
        backup_count: Number of rotated log files to keep. Defaults to 5.
    """
    logreset.reset_logging()

    level = logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] [%(process)s] [%(name)s] [%(levelname)s]: %(funcName)s -- %(message)s",
        handlers=[
            RotatingFileHandler(f"{log_file_stem}.log", mode="a", maxBytes=max_bytes,
                               backupCount=backup_count, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    logger.setLevel(level)
