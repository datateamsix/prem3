"""Fail-closed Identity Graph errors. Not people-identity errors."""

from __future__ import annotations


class IdentityGraphError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code
