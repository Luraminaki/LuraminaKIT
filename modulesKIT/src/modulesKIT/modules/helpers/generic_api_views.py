#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 21 13:47:01 2025

@author: Luraminaki
"""

import logging

from typing import Callable, TYPE_CHECKING

from fastapi import APIRouter
from pydantic import BaseModel

from contractsKIT import StandardResponse, ParamDescriptor, RouteDescriptor, ModuleManifest, CategoryHelp
from modulesKIT.modules.helpers import command_help

if TYPE_CHECKING:
    from modulesKIT.modules.helpers.generic_config import AppConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class GenericViews:
    """Base class for a module's FastAPI views: owns its router and route manifest."""

    def __init__(self, module_name: str, modules_config: 'AppConfig | None' = None, *args, **kwargs) -> None:
        """Initialize the router and register the `/url-list` manifest route.

        Args:
            module_name: Name of the module, used as the router's URL prefix.
            modules_config: Loaded application configuration. Subclasses that
                already take this as their own kwarg should forward it here too
                (`super().__init__(modules_config=modules_config, ...)`) so
                `self.tokens` is populated -- otherwise it's just `{}`.
            *args: Forwarded to subclasses.
            **kwargs: Forwarded to subclasses.
        """
        self.module_name: str = module_name
        self.tokens: dict[str, str] = modules_config.tokens if modules_config else {}
        self.module_description: str = (modules_config.modules[module_name].description
                                        if modules_config and module_name in modules_config.modules else '')
        self.command_help: dict[str, command_help.CommandHelpEntry] = (
            command_help.load_command_help(module_name, modules_config.directories.data_directory)
            if modules_config else {})
        self._routes: list[RouteDescriptor] = []

        self.api_router: APIRouter = APIRouter(prefix=f"/api/{module_name}", tags=["API"])
        self.api_router.add_api_route("/url-list", self.get_all_urls, methods=['GET'])

    def add_route(self, path: str, endpoint: Callable[..., object], methods: list[str],
                  description: str = '', response_model: type[BaseModel] | None = None,
                  params: list[ParamDescriptor] | None = None,
                  aliases: list[str] | None = None, name: str | None = None,
                  attachment_paths: list[str] | None = None, timeout: float = 5.0) -> None:
        """Register a route on the module's router and record it for `/url-list` advertisement.

        Kept as an explicit declaration (rather than introspecting FastAPI's route/dependant
        internals) so the advertised manifest doesn't depend on FastAPI's private attributes.

        Args:
            path: Route path, relative to the module's `/api/<module_name>` prefix.
            endpoint: Coroutine function handling the route.
            methods: HTTP methods the route accepts.
            description: Human-readable description of what the route does.
            response_model: Pydantic model FastAPI should validate the response against.
            params: Query parameters the route accepts, for advertisement purposes.
                Each one's `hint` may be overridden by a matching entry in this
                module's `command_help.json`, if it has one -- see
                `modules.helpers.command_help`.
            aliases: Extra command names LuraminaKIT should dispatch to this route,
                alongside the endpoint's own name.
            name: Command name LuraminaKIT should dispatch to this route. Defaults to
                the endpoint's own `__name__`; pass this explicitly when the desired
                command name (e.g. one containing dots) isn't a valid Python identifier
                and so can't be the endpoint's real function name.
            attachment_paths: Paths (relative to this module's own `/api/<module_name>`
                prefix) where this command's companion files can each be fetched as
                raw bytes, if it has any. This method doesn't register those routes
                itself (raw bytes don't fit `StandardResponse[T]`) -- register them
                separately on `self.api_router` and pass their paths here so
                LuraminaKIT knows to fetch and attach them.
            timeout: Seconds LuraminaKIT should wait for this route to respond
                before giving up. Defaults to a fast 5s; raise it for a route
                that's genuinely slow by nature (e.g. an LLM completion) rather
                than making every other, normally-fast command wait as long.

        Raises:
            ValueError: If a dotted command name/alias doesn't start with this
                module's own name -- LuraminaKIT's `!lurahelp` groups commands by
                splitting them on `.`, so a command that doesn't self-namespace
                this way would show up filed under a different module's listing.
            ValueError: If a command name/alias was already claimed by an earlier
                `add_route` call on this same view -- catches the mistake right
                where it was made (a copy-pasted route registration, usually)
                instead of only surfacing downstream as a logged-and-skipped
                collision when LuraminaKIT builds its command table.
        """
        resolved_name = name or getattr(endpoint, '__name__', path)
        for command_name in (resolved_name, *(aliases or [])):
            if '.' in command_name and not command_name.startswith(f"{self.module_name}."):
                raise ValueError(f"{self.__class__.__name__} -- command name/alias {command_name!r} contains a "
                                 + f"dot but doesn't start with '{self.module_name}.' -- dotted commands must be "
                                 + "namespaced under their own module's name")

        already_claimed = {claimed for route in self._routes for claimed in (route.name, *route.aliases)}
        for command_name in (resolved_name, *(aliases or [])):
            if command_name in already_claimed:
                raise ValueError(f"{self.__class__.__name__} -- command name/alias {command_name!r} is already "
                                 + "registered by another route on this view -- add_route was called twice with "
                                 + "the same name/alias")

        help_entry = self.command_help.get(resolved_name)
        final_description = help_entry.summary if help_entry and help_entry.summary else description

        final_params = params or []
        if help_entry and help_entry.params:
            final_params = [param.model_copy(update={'hint': help_entry.params.get(param.name, param.hint)})
                            for param in final_params]

        self.api_router.add_api_route(path, endpoint, methods=methods,
                                      description=final_description, response_model=response_model)

        self._routes.append(RouteDescriptor(path=f"/api/{self.module_name}{path}",
                                            name=name or getattr(endpoint, '__name__', path),
                                            description=final_description,
                                            methods=methods,
                                            query_params=final_params,
                                            response_model=str(response_model) if response_model else None,
                                            aliases=aliases or [],
                                            attachment_paths=attachment_paths or [],
                                            timeout=timeout))

    async def get_all_urls(self) -> StandardResponse[ModuleManifest]:
        """Advertise every route registered via `add_route`.

        Returns:
            A `StandardResponse` wrapping this module's `ModuleManifest`.
        """
        try:
            # command_help.json entries whose key isn't an actual route/alias name
            # aren't a command at all -- they're a category-prefix explanation
            # (e.g. "tb1.special"), advertised separately from the per-route hints
            # `add_route` already merged in.
            claimed_names = {claimed for route in self._routes for claimed in (route.name, *route.aliases)}
            category_help = {key: CategoryHelp(summary=entry.summary, short=entry.short)
                             for key, entry in self.command_help.items()
                             if key not in claimed_names and (entry.summary or entry.short)}

            manifest = ModuleManifest(module_name=self.module_name, description=self.module_description,
                                      routes=self._routes, category_help=category_help)
        except Exception as err:
            logger.error("%r", err)
            return StandardResponse[ModuleManifest].fail(repr(err))

        return StandardResponse[ModuleManifest].ok(manifest)
