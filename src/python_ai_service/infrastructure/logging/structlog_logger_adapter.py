"""Structlog-backed implementation of the application logging port."""

import structlog

from python_ai_service.application.ports.logging_port import LoggingPort


class StructlogLoggerAdapter(LoggingPort):
    """Adapt structlog bound loggers to the application logging contract."""

    def __init__(self, *, name: str) -> None:
        self._name = name
        self._logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)

    def bind(self, **context: object) -> LoggingPort:
        bound = StructlogLoggerAdapter(name=self._name)
        bound._logger = self._logger.bind(**context)
        return bound

    def debug(self, event: str, **context: object) -> None:
        self._logger.debug(event, **context)

    def info(self, event: str, **context: object) -> None:
        self._logger.info(event, **context)

    def warning(self, event: str, **context: object) -> None:
        self._logger.warning(event, **context)

    def error(self, event: str, **context: object) -> None:
        self._logger.error(event, **context)

    def exception(self, event: str, **context: object) -> None:
        self._logger.exception(event, **context)
