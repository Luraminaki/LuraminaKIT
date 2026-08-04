#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 21 13:47:01 2025

@author: Luraminaki
"""

import sys
import time
import json
import pathlib
import argparse
import logging

from importlib.metadata import version as pkg_version
from typing import Callable, cast, TYPE_CHECKING
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from contractsKIT import configure_launcher_logging
from modulesKIT.modules.helpers.generic_config import AppConfig

if TYPE_CHECKING:
    from modulesKIT.modules.helpers.generic_api_views import GenericViews

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def generic_create_app(config: AppConfig, module_views: 'GenericViews | None' = None) -> FastAPI:
    """Build the FastAPI app for a module, wiring in its router and CORS middleware.

    Args:
        config: Loaded application configuration.
        module_views: The module's view/router object.

    Returns:
        The configured `FastAPI` application.

    Raises:
        ValueError: If `module_views` is `None`.
    """
    if module_views is None:
        raise ValueError("module_views is None")

    webapp = FastAPI(title=module_views.module_name,
                     description=config.modules[module_views.module_name].description,
                     version=config.version)

    # These services are meant to be called by LuraminaKIT over loopback, not by
    # browser JS -- "*" + allow_credentials is a CORS misconfiguration (Starlette
    # falls back to reflecting the request's actual Origin, so it's effectively
    # "any origin, with credentials" rather than the literal wildcard). Restricted
    # to loopback origins; widen this only if/when a real browser-facing client
    # (e.g. an admin dashboard) needs to call these routes directly.
    webapp.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1", "http://localhost"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # MUST be in that specific order, else it doesn't work
    webapp.include_router(module_views.api_router)

    return webapp


def generic_main(default_config_file: pathlib.Path, main: Callable[[AppConfig], int] | None = None,
                 version: str = '') -> None:
    """Parse CLI args, load `config.json` into an `AppConfig`, and run `main`.

    Args:
        default_config_file: Config file to use when `-c`/`--configuration` isn't
            passed on the command line. Callers should resolve this relative to
            their own `__file__`, not the process's current working directory.
        main: Entry point to run with the loaded config; receives the `AppConfig`
            and returns the process exit code.
        version: Application version, stamped onto the loaded config.

    Raises:
        SystemExit: Always, with `main`'s return value (or `1` on setup failure).
    """
    m_tic = time.perf_counter()

    parser = argparse.ArgumentParser()
    _ = parser.add_argument('-c', '--configuration', help='Configuration file location', required=False)
    args = vars(parser.parse_args())

    config_file = args.get('configuration', None)
    config_file = pathlib.Path(config_file) if config_file is not None else default_config_file

    if not config_file.is_file():
        logger.error("%s does not exist -- Aborting", config_file)
        sys.exit(1)

    try:
        with config_file.open('r', encoding='utf-8') as f:
            raw_conf: dict[str, object] = json.load(f)
            raw_conf['version'] = version

            # Resolve relative directories (e.g. "./data/") against the config file's own
            # location instead of the process's CWD, so behavior never depends on where
            # the script was launched from. `directories` is the same dict object stored
            # inside raw_conf (`.get` doesn't copy it), so mutating it in place here still
            # updates raw_conf itself.
            directories = cast(dict[str, object], raw_conf.get('directories', {}))
            data_directory = directories.get('data_directory')
            if data_directory is not None:
                directories['data_directory'] = str((config_file.parent / cast(str, data_directory)).resolve())

            conf = AppConfig.model_validate(raw_conf)

    except Exception as err:
        logger.error("Loading %s failed -- %r", config_file, err)
        sys.exit(1)

    logger.info("Current time is: %s", time.asctime(time.localtime()))
    logger.info("%s acquired", config_file)

    if main is None:
        logger.error("'main' function is 'None' -- Aborting")
        sys.exit(1)

    ret_val: int = main(conf)

    m_tac = time.perf_counter() - m_tic
    logger.info("Ellapsed time: %s", round(m_tac, 3))

    sys.exit(ret_val)


def generic_launcher(script_file: str, view_class: type['GenericViews']) -> None:
    """Full launcher for a modulesKIT module: logging, config, app creation, and serving.

    Every `main_*.py` used to repeat the same ~80 lines (`create_app`/`main`/
    `__main__` boilerplate, differing only in which view class gets instantiated)
    by hand. This collapses that down to one call, taking just the one thing that
    actually varies per module.

    Also fixes a gap the hand-written version had: `uvicorn.run()` doesn't raise
    on a bind failure (e.g. the port already being in use) -- it logs the error
    itself and calls `sys.exit(uvicorn.server.STARTUP_FAILURE)` directly from deep
    inside its own startup path. `SystemExit` isn't an `Exception` subclass, so a
    plain `except Exception` never sees it: the process still exits (so it can't
    linger as a broken duplicate), but silently, without this module's own crash
    logging and with an exit code that doesn't match `main`'s documented `0`/`1`
    contract. Catching `SystemExit` alongside `Exception` here routes that failure
    through the same logging/return-code path as any other crash.

    Args:
        script_file: The calling script's own `__file__` -- used to derive the
            app name (`main_tb1.py` -> `tb1`), its directory (for `config.json`/
            `logs/`), and the log file stem.
        view_class: The module's `GenericViews` subclass to instantiate and serve.
    """
    script_path = pathlib.Path(script_file).resolve()
    script_dir = script_path.parent
    app_name = script_path.stem.replace('main_', '')
    app_version = pkg_version('modulesKIT')

    launcher_logger = logging.getLogger(app_name)
    launcher_logger.setLevel(logging.INFO)

    def create_app(config: AppConfig, name: str) -> FastAPI:
        return generic_create_app(config, view_class(module_name=name, modules_config=config))

    def main(conf: AppConfig) -> int:
        try:
            launcher_logger.info("Creating APP: %s", app_name)
            app = create_app(conf, app_name)
            uvicorn.run(app,
                       port=conf.modules[app_name].port,
                       # `None` tells uvicorn to keep the root logging config set up
                       # below instead of installing its own dictConfig.
                       log_config=None)
            return 0

        except SystemExit as err:
            launcher_logger.error("App failed to start at %s -- uvicorn exited with code %s",
                                  time.asctime(time.localtime()), err.code)
            return 1

        except Exception as err:
            launcher_logger.error("App chrashed at %s -- %r", time.asctime(time.localtime()), err)
            return 1

    configure_launcher_logging(launcher_logger, str(script_dir / 'logs' / script_path.stem))
    launcher_logger.info("Version %s", app_version)

    generic_main(default_config_file=script_dir / 'config.json', main=main, version=app_version)
