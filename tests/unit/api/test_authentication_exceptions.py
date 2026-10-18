import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python_ai_service.api.common.exception_handlers import register_exception_handlers
from python_ai_service.domain.exceptions import (
    AuthenticationException,
    MalformedCredentialsException,
    MissingCredentialsException,
    UnsupportedAuthenticationSchemeException,
)


@pytest.mark.parametrize(
    "exception_type",
    [
        AuthenticationException,
        MissingCredentialsException,
        MalformedCredentialsException,
        UnsupportedAuthenticationSchemeException,
    ],
)
def test_authentication_exceptions_return_401_without_internal_details(
    exception_type: type[AuthenticationException],
) -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/protected")
    async def protected() -> None:
        raise exception_type("Internal authentication details must not be exposed.")

    with TestClient(app) as client:
        response = client.get("/protected")

    assert response.status_code == 401
    assert response.json() == {
        "meta": {
            "code": "AUTH-401",
            "message": "Authentication failed.",
            "request_id": "",
        }
    }
