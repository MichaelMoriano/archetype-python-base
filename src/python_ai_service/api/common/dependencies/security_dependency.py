"""FastAPI security dependency. JWT interpretation remains owned by GEN-SECURITY."""

from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from python_ai_service.api.common.dependencies.headers_dependency import (
    InstitutionalHeaders,
    get_institutional_headers,
)
from python_ai_service.application.ports.security_validation_port import SecurityValidationPort
from python_ai_service.domain.exceptions import AuthenticationException

_bearer = HTTPBearer(auto_error=False)


def get_security_validation_port(request: Request) -> SecurityValidationPort:
    return cast(SecurityValidationPort, request.app.state.container.security_validation_port)


async def require_valid_jwt(
    headers: Annotated[InstitutionalHeaders, Depends(get_institutional_headers)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    security_port: Annotated[SecurityValidationPort, Depends(get_security_validation_port)],
) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationException("Bearer authentication is required.")
    await security_port.validate_jwt(
        origin_id=headers.origin_id,
        sub_origin_id=headers.sub_origin_id,
        token=credentials.credentials,
    )
