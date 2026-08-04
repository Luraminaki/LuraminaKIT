#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr 13 12:05:32 2025

@author: Luraminaki
"""

import sys
import time
import pathlib
import argparse
import logging

from importlib.metadata import version

import discord

from contractsKIT import configure_launcher_logging
from LuraminaKIT.modules.clients.discord_client import DiscordClient
from LuraminaKIT.modules.helpers.settings import Settings, load_config_file, load_env_variables, load_valid_config
from LuraminaKIT.modules.helpers.singleton_lock import SingleInstanceLock

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
__version__ = version('LuraminaKIT')


def main(config: Settings) -> None:
    """Start the Discord client and block until it disconnects.

    Args:
        config: Loaded application configuration.
    """
    # `default()` already covers everything non-privileged, including `voice_states`
    # (voice-channel join/leave -- needed for a future voice/music module). The two
    # privileged intents below must also be toggled on for this bot application in
    # the Discord Developer Portal, under Bot > Privileged Gateway Intents.
    intents = discord.Intents.default()
    intents.message_content = True  # read message text/attachments: commands, future LLM & file-reading
    intents.members = True  # enumerate/track guild members: future server-management commands
    client = DiscordClient(intents=intents, custom_config=config)
    client.run(config.discord_token)


if __name__ == "__main__":
    m_tic = time.perf_counter()

    configure_launcher_logging(logger, str(SCRIPT_DIR / 'logs' / pathlib.Path(__file__).stem))

    logger.info("Version %s", __version__)

    load_env_variables(SCRIPT_DIR / ".env")

    parser = argparse.ArgumentParser()
    _ = parser.add_argument('-c', '--configuration', help='Configuration file location', required=False)
    args = vars(parser.parse_args())

    config_file = args.get('configuration', None)
    config_file = pathlib.Path(config_file) if config_file is not None else SCRIPT_DIR / "config.json"

    if not config_file.is_file():
        logger.error("%s does not exist -- Aborting", config_file)
        sys.exit(1)

    try:
        conf: Settings = load_valid_config(load_config_file(config_file))
    except Exception as err:
        logger.error("Loading %s failed -- %r", config_file, err)
        sys.exit(1)

    logger.info("Current time is: %s", time.asctime(time.localtime()))
    logger.info("%s acquired", config_file)
    crash = False

    lock_dir = SCRIPT_DIR / 'logs'
    lock_dir.mkdir(parents=True, exist_ok=True)

    try:
        with SingleInstanceLock(lock_dir / 'lurainakit.lock'):
            main(config=conf)
    except Exception as err:
        crash = True
        logger.error("App chrashed at %s -- %r", time.asctime(time.localtime()), err)

    m_tac = time.perf_counter() - m_tic
    logger.info("Ellapsed time: %s", round(m_tac, 3))

    if crash:
        sys.exit(1)

    sys.exit(0)
