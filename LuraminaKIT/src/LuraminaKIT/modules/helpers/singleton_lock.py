#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prevents two `LuraminaKIT` instances from running against the same Discord
token at once.

Unlike a modulesKIT service (which binds a TCP port, so the OS itself refuses
a second instance), the Discord client only makes outbound connections -- nothing
stops a second process from logging in with the same token and receiving every
message a second time, each dispatching its own copy of every command. That
silent double-firing has actually happened (mismatched `.venv`/system-Python
launches left old processes running), and was only caught by manually inspecting
the process list -- this makes that failure loud instead of silent.

@author: Luraminaki
"""

import logging
import os
import pathlib
import subprocess
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _pid_is_running(pid: int) -> bool:
    """Check whether a process with `pid` currently exists.

    Args:
        pid: Process ID to check.

    Returns:
        `True` if a process with that PID is currently running.
    """
    if sys.platform == 'win32':
        # `os.kill(pid, 0)` isn't a reliable existence check on Windows (signal 0
        # isn't meaningfully supported there) -- shell out to `tasklist` instead.
        result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'],
                                capture_output=True, text=True, check=False)
        return str(pid) in result.stdout

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class SingleInstanceLock:
    """A PID-file lock held for the process's lifetime, released on `__exit__`.

    Usage:
        with SingleInstanceLock(path):
            main(...)

    Raises `SystemExit(1)` on `__enter__` if another live process already holds
    the lock, rather than letting two instances silently run side by side.
    """

    def __init__(self, path: pathlib.Path) -> None:
        """Prepare the lock, without acquiring it yet.

        Args:
            path: Where to keep the PID file. Its parent directory must already exist.
        """
        self.path: pathlib.Path = path

    def __enter__(self) -> 'SingleInstanceLock':
        """Acquire the lock, aborting the process if another instance holds it.

        Returns:
            `self`, so the lock can be used as a context manager.
        """
        if self.path.is_file():
            existing_pid_text = self.path.read_text(encoding='utf-8').strip()
            existing_pid = int(existing_pid_text) if existing_pid_text.isdigit() else None

            if existing_pid is not None and _pid_is_running(existing_pid):
                logger.error("Another instance is already running (PID %s, lock file %s) -- aborting",
                            existing_pid, self.path)
                sys.exit(1)

            logger.warning("Stale lock file %s (PID %s not running) -- reclaiming it", self.path, existing_pid_text)

        _= self.path.write_text(str(os.getpid()), encoding='utf-8')
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Release the lock by removing the PID file, if it's still ours."""
        try:
            if self.path.read_text(encoding='utf-8').strip() == str(os.getpid()):
                self.path.unlink()
        except OSError as err:
            logger.warning("Could not remove lock file %s -- %r", self.path, err)
