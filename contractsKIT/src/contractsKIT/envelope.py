#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standard response envelope shared by every modulesKIT module and consumed by LuraminaKIT."""

import enum

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar('T')


class StatusFunction(str, enum.Enum):
    """Outcome of a modulesKIT API call, shared across every module and LuraminaKIT."""

    SUCCESS = 'SUCCESS'
    FAIL = 'FAIL'
    ONGOING = 'ONGOING'
    DONE = 'DONE'
    ERROR = 'ERROR'
    WARNING = 'WARNING'


class StandardResponse(BaseModel, Generic[T]):
    """Standard envelope every modulesKIT route returns and LuraminaKIT parses.

    Attributes:
        status: Outcome of the call.
        data: Payload on success, `None` otherwise.
        error: Error description, empty on success.
    """

    status: StatusFunction
    data: T | None = None
    error: str = ''

    @classmethod
    def ok(cls, data: T) -> 'StandardResponse[T]':
        """Build a successful response wrapping `data`.

        Args:
            data: Payload to wrap.

        Returns:
            A `StandardResponse` with `status=SUCCESS`.
        """
        return cls(status=StatusFunction.SUCCESS, data=data, error='')

    @classmethod
    def fail(cls, error: str) -> 'StandardResponse[T]':
        """Build a failed response carrying `error`.

        Args:
            error: Human-readable error description.

        Returns:
            A `StandardResponse` with `status=ERROR` and no data.
        """
        return cls(status=StatusFunction.ERROR, data=None, error=error)
