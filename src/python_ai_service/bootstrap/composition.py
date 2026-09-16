"""Composition root: map application ports to concrete infrastructure adapters."""

from dataclasses import dataclass

import httpx

from python_ai_service.application.ports.logging_port import LoggingPort
from python_ai_service.application.ports.security_validation_port import SecurityValidationPort
from python_ai_service.config.settings import Settings
from python_ai_service.infrastructure.logging.structlog_logger_adapter import StructlogLoggerAdapter
from python_ai_service.infrastructure.security.gen_security_adapter import GenSecurityAdapter


@dataclass(slots=True)
class ApplicationContainer:
    logging_port: LoggingPort
    security_validation_port: SecurityValidationPort


def build_container(
    *,
    settings: Settings,
    security_client: httpx.AsyncClient,
) -> ApplicationContainer:
    return ApplicationContainer(
        logging_port=StructlogLoggerAdapter(name=settings.app_name),
        security_validation_port=GenSecurityAdapter(client=security_client, settings=settings),
    )
