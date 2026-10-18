import httpx
import pytest
from fastapi.testclient import TestClient

from python_ai_service.bootstrap.main import create_app
from python_ai_service.infrastructure.security.gen_security_adapter import GenSecurityAdapter
from tests.settings_helpers import build_test_settings


@pytest.mark.parametrize(
    ("authorization", "return_code", "expected_status", "expected_calls"),
    [
        ("Basic dXNlcjpwYXNz", "000", 200, 1),
        ("Basic dXNlcjpwYXNz", "044", 401, 1),
        ("Basic !!!", "000", 401, 0),
        ("Bearer token", "000", 401, 0),
        (None, "000", 401, 0),
    ],
)
@pytest.mark.asyncio
async def test_basic_health_uses_external_validator(
    authorization: str | None, return_code: str, expected_status: int, expected_calls: int
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"returnCode": return_code, "returnDescription": "test"})

    settings = build_test_settings()
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as external:
        with TestClient(app) as client:
            app.state.container.security_validation_port = GenSecurityAdapter(
                client=external, settings=settings
            )
            headers = {"OriginId": "26", "SubOriginId": "105", "X-Request-Id": "basic-probe"}
            if authorization is not None:
                headers["Authorization"] = authorization
            response = client.get("/api/v1/auth/basic/health", headers=headers)
    assert response.status_code == expected_status
    assert response.headers["X-Request-Id"] == "basic-probe"
    assert len(requests) == expected_calls
    assert "dXNlcjpwYXNz" not in response.text
    if expected_status == 200:
        assert response.json() == {
            "status": "ok",
            "origin": "26",
            "sub_origin": "105",
            "correlation_id": "basic-probe",
        }
    else:
        assert response.json()["meta"] == {
            "code": "AUTH-401",
            "message": "Authentication failed.",
            "request_id": "basic-probe",
        }
    if requests:
        assert str(requests[0].url) == settings.gen_security_basic_auth_url
        assert requests[0].headers["Authorization"] == authorization
        assert requests[0].headers["OriginId"] == "26"
        assert requests[0].headers["SubOriginId"] == "105"
        assert requests[0].headers["X-Request-Id"] == "basic-probe"
