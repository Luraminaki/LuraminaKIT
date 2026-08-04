#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Starts every `auto_start`-enabled modulesKIT module in the background, then
runs the LuraminaKIT bot in the foreground so its logs stream to this terminal.

Modules are discovered from `modulesKIT/config.json` -- no hardcoded module
list here, adding a module to that config is enough to have it picked up.
Each module already logs to its own rotating file (`modulesKIT/logs/main_<name>.log`)
regardless of this script, so their own console output is redirected away to
keep this terminal free for the bot's.

Usage: `python run.py` from the repository root (or anywhere -- paths below are
resolved relative to this file, not the current working directory).

@author: Luraminaki
"""

import io
import pathlib
import subprocess
import sys
import time

from modulesKIT.modules.helpers.generic_config import AppConfig

# Redirected-to-file stdout (as opposed to a real console) is block-buffered by
# default -- without this, status lines below sit in the buffer and don't reach
# the terminal/log until the buffer fills or the process exits, which defeats
# the point of a script meant to be watched live. `reconfigure` is only declared
# on the concrete `TextIOWrapper`, not the more general `TextIO` type `sys.stdout`
# is statically typed as, hence the narrowing check.
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(line_buffering=True)

REPO_ROOT = pathlib.Path(__file__).resolve().parent
MODULES_DIR = REPO_ROOT / 'modulesKIT'
BOT_DIR = REPO_ROOT / 'LuraminaKIT'
MODULES_CONFIG_FILE = MODULES_DIR / 'config.json'

MODULE_STARTUP_DELAY_SECONDS = 3


def discover_auto_start_modules() -> list[str]:
    """Module names to launch, per `modulesKIT/config.json`'s `auto_start` flag.

    Returns:
        Names of every module whose config entry has `auto_start` unset or `true`.
    """
    config = AppConfig.model_validate_json(MODULES_CONFIG_FILE.read_text(encoding='utf-8'))
    return [name for name, entry in config.modules.items() if entry.auto_start]


def launch_module(name: str) -> subprocess.Popen[bytes]:
    """Start one modulesKIT module as a background subprocess.

    Args:
        name: Module name -- its launcher is expected at `main_<name>.py`.

    Returns:
        The started process handle.
    """
    script = MODULES_DIR / f'main_{name}.py'
    args = [sys.executable, str(script)]

    # Isolates the module from this console's Ctrl+C -- otherwise Windows
    # broadcasts CTRL_C_EVENT to the whole process tree, killing modules the
    # instant Ctrl+C is pressed instead of letting `shutdown_modules` below
    # shut them down in an orderly way once the bot has actually exited.
    # Passed as separate branches (not a kwargs dict) since the two platforms'
    # flags have unrelated types (`int` vs `bool`) that a single dict can't
    # express cleanly for a type checker.
    if sys.platform == 'win32':
        return subprocess.Popen(args, cwd=str(MODULES_DIR), stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

    return subprocess.Popen(args, cwd=str(MODULES_DIR), stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)


def shutdown_modules(processes: dict[str, subprocess.Popen[bytes]]) -> None:
    """Terminate every still-running module subprocess, killing stragglers.

    Args:
        processes: Module name -> its process handle.
    """
    for name, proc in processes.items():
        if proc.poll() is None:
            proc.terminate()

    for name, proc in processes.items():
        try:
            _ = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print(f"  {name} didn't stop in time -- killing it")
            proc.kill()
            _ = proc.wait()


def main() -> int:
    """Launch every auto-start module, then the bot in the foreground.

    Returns:
        The bot subprocess's own exit code.
    """
    module_names = discover_auto_start_modules()

    processes: dict[str, subprocess.Popen[bytes]] = {}
    for name in module_names:
        print(f"Starting module: {name}")
        processes[name] = launch_module(name)

    if not module_names:
        print("No modules have auto_start enabled -- starting the bot alone.")
    else:
        time.sleep(MODULE_STARTUP_DELAY_SECONDS)

        dead = [name for name, proc in processes.items() if proc.poll() is not None]
        for name in dead:
            print(f"  WARNING: module {name!r} already exited -- "
                  + f"check modulesKIT/logs/main_{name}.log")

    try:
        print("Starting LuraminaKIT bot (Ctrl+C to stop everything)...\n")
        result = subprocess.run([sys.executable, str(BOT_DIR / 'main.py')], cwd=str(BOT_DIR))
        return result.returncode
    finally:
        if processes:
            print("\nShutting down modules...")
            shutdown_modules(processes)


if __name__ == '__main__':
    sys.exit(main())
