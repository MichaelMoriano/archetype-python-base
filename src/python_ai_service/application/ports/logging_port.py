"""Outbound structured logging contract required by application code.

This port intentionally depends on the standard library only. Keeping it free of
framework and vendor imports is what allows the application layer to stay
independent from the concrete logging technology used by infrastructure.
"""

from typing import Protocol


class LoggingPort(Protocol):
    def bind(self, **context: object) -> "LoggingPort":
        """Return a new logger carrying the given context on every emitted event."""
        ...

    def debug(self, event: str, **context: object) -> None:
        """Emit a debug event with optional structured context."""
        ...

    def info(self, event: str, **context: object) -> None:
        """Emit an informational event with optional structured context."""
        ...

    def warning(self, event: str, **context: object) -> None:
        """Emit a warning event with optional structured context."""
        ...

    def error(self, event: str, **context: object) -> None:
        """Emit an error event with optional structured context."""
        ...

    def exception(self, event: str, **context: object) -> None:
        """Emit an error event including the active exception traceback."""
        ...
