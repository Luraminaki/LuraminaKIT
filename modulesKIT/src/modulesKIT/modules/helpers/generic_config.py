#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Typed configuration for modulesKIT, loaded once from config.json.

@author: Luraminaki
"""

from pydantic import BaseModel


class DirectoriesConfig(BaseModel):
    """Filesystem directories used by modulesKIT.

    Attributes:
        data_directory: Root directory holding each module's data files.
    """

    data_directory: str


class ModuleConfig(BaseModel):
    """Configuration for a single module, keyed by module name in `AppConfig.modules`.

    Attributes:
        port: TCP port the module's FastAPI app listens on.
        description: Human-readable description, used as the app's OpenAPI description.
        data: Free-form module-specific settings (e.g. a quote template string).
        auto_start: Whether the repo-root `run.py` launcher should start this
            module. Defaults to `True`; set to `False` for a module too heavy to
            want running by default (e.g. on weaker hardware). Only consulted by
            `run.py` -- starting a module directly via its own `main_<name>.py`
            always works regardless of this flag.
    """

    port: int
    description: str = ''
    data: dict[str, str] = {}
    auto_start: bool = True


class AppConfig(BaseModel):
    """Root configuration for a modulesKIT launcher, loaded once from `config.json`.

    Attributes:
        directories: Filesystem directories used by modulesKIT.
        tokens: Named secrets/tokens available to modules.
        modules: Per-module configuration, keyed by module name.
        version: Application version, injected at startup.
    """

    directories: DirectoriesConfig
    tokens: dict[str, str] = {}
    modules: dict[str, ModuleConfig]
    version: str = ''
