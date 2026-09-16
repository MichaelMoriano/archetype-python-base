"""Async-safe request identifier context shared across layers.

This module holds the request-id ContextVar in a neutral, stdlib-only place so
that cross-cutting consumers (logging configuration, API middleware, exception
handlers) can read it without depending on the API layer.
"""

from contextvars import ContextVar, Token

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_current_request_id() -> str:
    """Return the current request identifier, or an empty string outside a request."""
    value = _request_id_var.get()
    return value if value is not None else ""


def bind_request_id(request_id: str) -> Token[str | None]:
    """Bind a request identifier to the current context and return its reset token."""
    return _request_id_var.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the request identifier held before the matching bind call."""
    _request_id_var.reset(token)
