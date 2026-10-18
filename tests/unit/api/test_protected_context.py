from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from python_ai_service.api.common.dependencies.request_context_dependency import get_request_context
from python_ai_service.bootstrap.main import create_app
from python_ai_service.domain.request_context import RequestContext
from tests.settings_helpers import build_test_settings


@dataclass(slots=True)
class FakeSecurityPort:
    calls: int = 0

    async def validate_jwt(
        self, *, origin_id: int, sub_origin_id: int, request_id: str, token: str
    ) -> None:
        assert origin_id == 26
        assert sub_origin_id == 105
        assert token == "token"
        assert request_id == "req-1"
        self.calls += 1


def _app() -> FastAPI:
    app = create_app(build_test_settings())

    @app.get("/probe")
    async def probe(
        context: Annotated[RequestContext, Depends(get_request_context)],
    ) -> dict[str, object]:
        return {
            "origin_id": context.origin_id,
            "sub_origin_id": context.sub_origin_id,
            "request_id": context.request_id,
        }

    return app


def test_protected_context_validates_security_and_builds_context() -> None:
    app = _app()
    fake = FakeSecurityPort()
    with TestClient(app) as client:
        app.state.container.security_validation_port = fake
        response = client.get(
            "/probe",
            headers={
                "Authorization": "Bearer token",
                "OriginId": "26",
                "SubOriginId": "105",
                "X-Request-Id": "req-1",
            },
        )
    assert response.status_code == 200
    assert response.json() == {
        "origin_id": 26,
        "sub_origin_id": 105,
        "request_id": "req-1",
    }
    assert fake.calls == 1


def test_protected_context_requires_bearer_token() -> None:
    app = _app()
    with TestClient(app) as client:
        response = client.get(
            "/probe",
            headers={"OriginId": "26", "SubOriginId": "105"},
        )
    assert response.status_code == 401
    assert response.json()["meta"]["code"] == "AUTH-401"


def test_protected_context_requires_institutional_headers() -> None:
    app = _app()
    with TestClient(app) as client:
        response = client.get(
            "/probe",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 422
