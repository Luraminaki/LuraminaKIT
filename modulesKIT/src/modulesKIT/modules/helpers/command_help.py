#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional per-command help text, loaded from a module's own
`data/<module>/command_help.json` if present.

Lets a command's description and per-parameter hints be edited without
touching source code -- `GenericViews.add_route` merges a matching entry's
`summary`/`params` into the `RouteDescriptor`/`ParamDescriptor` it builds,
falling back to the `description=`/`params=` passed in code when no JSON
entry exists for that command (or the file doesn't exist at all -- entirely
optional per module).

@author: Luraminaki
"""

import logging
import pathlib

from pydantic import BaseModel, TypeAdapter

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class CommandHelpEntry(BaseModel):
    """Optional help text for one command, keyed by its full dispatch name.

    Attributes:
        summary: Overrides that command's `description=` when non-empty. For a
            category-prefix entry (key doesn't match a real command name),
            this is the full explanation shown when drilled all the way in.
        params: Param name -> human-readable hint, overlaid onto that param's
            `ParamDescriptor.hint` when present. Unused for category entries.
        short: Category entries only -- a short phrase for the category's own
            line in a parent listing, where there isn't room for `summary` in
            full. Falls back to `summary` when empty. Ignored for command entries.
    """

    summary: str = ''
    params: dict[str, str] = {}
    short: str = ''


_COMMAND_HELP_ADAPTER = TypeAdapter(dict[str, CommandHelpEntry])


def load_command_help(module_name: str, data_directory: str) -> dict[str, CommandHelpEntry]:
    """Load `<data_directory>/<module_name>/command_help.json`, if it exists.

    Args:
        module_name: Name of the module, used to locate its data folder.
        data_directory: Root directory holding each module's data files.

    Returns:
        Command name -> its help entry. Empty if the file doesn't exist or
        fails to parse -- a module without one just gets no hints, not an error.
    """
    path = pathlib.Path(data_directory) / module_name / 'command_help.json'
    if not path.is_file():
        return {}

    try:
        return _COMMAND_HELP_ADAPTER.validate_json(path.read_text(encoding='utf-8'))
    except Exception as err:
        logger.error("Failed to load %s -- %r", path, err)
        return {}
