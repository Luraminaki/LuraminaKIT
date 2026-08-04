#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Typed configuration for LuraminaKIT.

Values come from two layers, merged together: environment variables / a `.env`
file (secrets such as the Discord token) as the base, overridden by a JSON config
file (bot behavior, module list).

@author: Luraminaki
"""

import json
import logging
import pathlib

from pydantic import BaseModel
from pydantic_settings import BaseSettings
import dotenv

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ModuleEntry(BaseModel):
    """A modulesKIT module LuraminaKIT should poll for commands.

    Attributes:
        name: Module name (matches its modulesKIT config key).
        port: TCP port the module's FastAPI app listens on.
        prefix: The module's API route prefix (e.g. `/api/anyquotes`).
    """

    name: str
    port: int
    prefix: str


class BotParams(BaseModel):
    """Discord bot behavior settings.

    Attributes:
        bot_name: Display name of the bot.
        activities: Configured presence activities.
        cmd_prefix: Prefix that triggers command dispatch (e.g. `"!"`).
        modules_base_route: Base URL (scheme + host) modules are reachable at.
        modules_api_routes: Path suffix appended to reach a module's `/url-list` route.
    """

    bot_name: str = ''
    activities: list[str] = []
    cmd_prefix: str = ''
    modules_base_route: str = ''
    modules_api_routes: str = ''


class Settings(BaseSettings):
    """Root configuration for LuraminaKIT.

    `discord_token` is meant to come from the environment (or a `.env` file loaded
    via `load_env_variables`) rather than the JSON config file, so it never has to
    sit in plaintext in a file that might get committed.

    Attributes:
        discord_token: Discord bot token. Sourced from the `DISCORD_TOKEN`
            environment variable.
        bot_params: Discord bot behavior settings.
        modules: modulesKIT modules to poll for commands.
    """

    discord_token: str = ''
    bot_params: BotParams = BotParams()
    modules: list[ModuleEntry] = []


def merge_configs(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    """Recursively merge `override` into `base`, with `override` taking precedence.

    Args:
        base: Base configuration mapping (e.g. environment-derived settings).
        override: Values that take precedence over `base` (e.g. a config file).

    Returns:
        A new merged mapping; neither input is mutated.
    """
    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = merge_configs(existing, value)
        else:
            merged[key] = value
    return merged


def load_env_variables(env_file: pathlib.Path) -> None:
    """Load environment variables from a `.env` file if it exists.

    Args:
        env_file: Path to the `.env` file to load. Callers should resolve this
            relative to their own `__file__`, not the process's current working
            directory.
    """
    if env_file.is_file():
        _ = dotenv.load_dotenv(env_file, override=False)
    else:
        logger.warning("No .env file found at %s -- Skipping loading environment variables", env_file)


def load_config_file(path: 'str | pathlib.Path') -> dict[str, object]:
    """Read and parse a JSON config-override file.

    Args:
        path: Filesystem path to a JSON object of `Settings` overrides.

    Returns:
        The parsed override mapping.

    Raises:
        FileNotFoundError: If the path does not point to a file.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    config_path = pathlib.Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    return json.loads(config_path.read_text(encoding='utf-8'))


def load_valid_config(custom_config: dict[str, object] | None = None) -> Settings:
    """Get a valid `Settings` instance, environment as the base, `custom_config` on top.

    A fresh `Settings()` is constructed here (rather than reused from a module-level
    singleton) so that any environment variables loaded by `load_env_variables` just
    beforehand are guaranteed to be picked up.

    Args:
        custom_config: Configuration overrides (typically loaded from a JSON config
            file via `load_config_file`), merged on top of the environment-derived
            defaults.

    Returns:
        Settings: A valid `Settings` instance.
    """
    base = Settings().model_dump()
    config = merge_configs(base, custom_config) if custom_config else base

    # Not strict: a config FILE supplies values as JSON (e.g. paths as strings,
    # ints where a float is expected), so we want Pydantic's normal coercion --
    # strict=True would reject a string for a Path field and defeat file overrides.
    return Settings.model_validate(config)
