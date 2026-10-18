"""Public HTTP behavior when the external security validator fails."""

import httpx
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from python_ai_service.api.common.dependencies.security_dependency import require_valid_jwt
from python_ai_service.bootstrap.main import create_app
from python_ai_service.infrastructure.security.gen_security_adapter import GenSecurityAdapter
from tests.settings_helpers import build_test_settings


@pytest.mark.asyncio
@pytest.mark.parametrize("scheme", ["basic", "jwt"])
@pytest.mark.parametrize(
    ("failure", "status", "code", "message"),
    [
        ("timeout", 504, "EXT-504", "An external dependency timed out."),
        ("connection", 503, "EXT-503", "An external dependency is unavailable."),
        ("invalid_json", 503, "EXT-503", "An external dependency is unavailable."),
        ("inconsistent", 503, "EXT-503", "An external dependency is unavailable."),
        ("internal", 503, "EXT-503", "An external dependency is unavailable."),
    ],
)
async def test_validator_failures_are_controlled_and_do_not_expose_details(
    scheme: str, failure: str, status: int, code: str, message: str
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private upstream details", request=request)
        if failure == "connection":
            raise httpx.ConnectError("private upstream details", request=request)
        if failure == "invalid_json":
            return httpx.Response(200, text="private upstream details")
        if failure == "inconsistent":
            return httpx.Response(500, json={"returnCode": "000", "returnDescription": "private"})
        return httpx.Response(200, json={"returnCode": "003", "returnDescription": "private"})

    settings = build_test_settings()
    app = create_app(settings)

    @app.get("/jwt-probe", dependencies=[Depends(require_valid_jwt)])
    async def jwt_probe() -> dict[str, bool]:
        return {"authenticated": True}

    path = "/api/v1/auth/basic/health" if scheme == "basic" else "/jwt-probe"
    authorization = "Basic dXNlcjpwYXNz" if scheme == "basic" else "Bearer test-token"
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as external:
        with TestClient(app) as client:
            app.state.container.security_validation_port = GenSecurityAdapter(
                client=external, settings=settings
            )
            response = client.get(
                path,
                headers={
                    "Authorization": authorization,
                    "OriginId": "26",
                    "SubOriginId": "105",
                    "X-Request-Id": "failure-test",
                },
            )
    assert len(requests) == 1
    assert response.status_code == status
    assert response.headers["X-Request-Id"] == "failure-test"
    assert response.json() == {
        "meta": {"code": code, "message": message, "request_id": "failure-test"}
    }
    assert "private" not in response.text
    assert authorization not in response.text
