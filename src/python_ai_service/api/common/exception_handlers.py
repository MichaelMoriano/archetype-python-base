"""Central controlled HTTP exception mapping."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from python_ai_service.api.common.middleware.request_id_middleware import get_current_request_id
from python_ai_service.domain.exceptions import (
    AuthenticationException,
    AuthorizationException,
    ExternalServiceException,
    ExternalServiceTimeoutException,
    NotFoundException,
    ValidationException,
)


def _payload(code: str, message: str) -> dict[str, object]:
    return {
        "meta": {
            "code": code,
            "message": message,
            "request_id": get_current_request_id(),
        }
    }


def register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(AuthenticationException)
    async def authentication_handler(_: Request, __: AuthenticationException) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=_payload("AUTH-401", "Authentication failed."),
        )

    @application.exception_handler(AuthorizationException)
    async def authorization_handler(_: Request, __: AuthorizationException) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_payload("AUTH-403", "Operation is not allowed."),
        )

    @application.exception_handler(ValidationException)
    async def validation_handler(_: Request, error: ValidationException) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_payload("REQ-400", str(error)),
        )

    @application.exception_handler(NotFoundException)
    async def not_found_handler(_: Request, __: NotFoundException) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_payload("REQ-404", "Resource was not found."),
        )

    @application.exception_handler(ExternalServiceTimeoutException)
    async def timeout_handler(_: Request, __: ExternalServiceTimeoutException) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content=_payload("EXT-504", "An external dependency timed out."),
        )

    @application.exception_handler(ExternalServiceException)
    async def external_handler(_: Request, __: ExternalServiceException) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_payload("EXT-503", "An external dependency is unavailable."),
        )
