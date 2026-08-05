#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module self-description: what a modulesKIT module advertises at its `/url-list` route."""

from pydantic import BaseModel, Field


class ParamDescriptor(BaseModel):
    """Description of a single query parameter accepted by a route.

    Attributes:
        name: Query parameter name.
        required: Whether the parameter must be provided.
        type_: Name of the expected value type (e.g. `"str"`).
        hint: Human-readable explanation of what this parameter means/does,
            shown alongside its usage line. Empty means no explanation was
            provided -- see `modules.helpers.command_help` for how a module
            can supply one without touching its route-registration code.
    """

    name: str
    required: bool
    type_: str = 'str'
    hint: str = ''


class RouteDescriptor(BaseModel):
    """Self-description of a single route, advertised at a module's `/url-list`.

    Attributes:
        path: Full route path, including the `/api/<module_name>` prefix.
        name: Route/endpoint function name.
        description: Human-readable description of what the route does.
        methods: HTTP methods the route accepts.
        query_params: Query parameters the route accepts.
        response_model: `repr` of the route's pydantic response model, if any.
        aliases: Extra command names LuraminaKIT should dispatch to this route,
            alongside `name`.
        attachment_paths: Where this command's companion files can each be fetched
            as raw bytes, if it has any -- unlike `path`, these are relative to the
            module's `/api/<module_name>` prefix, not already absolutized, since
            callers need to prepend that themselves (see
            `command_dispatch.fetch_attachments`). Empty means no attachments --
            LuraminaKIT sends the command's text response only.
        timeout: Seconds LuraminaKIT should wait for this route to respond
            before giving up. Every route defaults to a fast 5s -- a route that
            genuinely needs longer (e.g. an LLM completion) can advertise its
            own higher value via `add_route(..., timeout=...)` without raising
            the timeout for every other, normally-fast command too. Capped at
            120s so a misconfigured module can't hang a command indefinitely.
    """

    path: str
    name: str
    description: str = ''
    methods: list[str] = []
    query_params: list[ParamDescriptor] = []
    response_model: str | None = None
    aliases: list[str] = []
    attachment_paths: list[str] = []
    timeout: float = Field(default=5.0, gt=0, le=120)


class CategoryHelp(BaseModel):
    """Explanation of one dotted category prefix (e.g. `"tb1.special"`).

    Attributes:
        summary: Full explanation, shown when a user drills all the way into
            this category (`/help path:tb1.special`).
        short: A short phrase for the category's own line in a parent listing
            (`/help path:tb1`), where there isn't room for the full
            explanation. Falls back to `summary` when empty -- see
            `modules.helpers.command_help` for how a module supplies these.
    """

    summary: str = ''
    short: str = ''


class ModuleManifest(BaseModel):
    """Full self-description of a modulesKIT module, returned by its `/url-list` route.

    Attributes:
        module_name: Name of the module (matches its config key).
        description: Human-readable description of the module as a whole
            (from its `config.json` entry), shown by `/help` above its
            commands -- distinct from `RouteDescriptor.description`, which
            describes one route at a time.
        routes: Every route the module advertises, excluding `/url-list` itself.
        category_help: Dotted category prefix (e.g. `"tb1.special"`) -> its
            explanation, shown by `/help`. Empty means no category
            explanations were provided -- see `modules.helpers.command_help`.
    """

    module_name: str
    description: str = ''
    routes: list[RouteDescriptor]
    category_help: dict[str, CategoryHelp] = {}
