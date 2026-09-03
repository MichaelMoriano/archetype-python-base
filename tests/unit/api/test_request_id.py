from fastapi.testclient import TestClient

from python_ai_service.bootstrap.main import create_app
from tests.settings_helpers import build_test_settings


def test_request_id_is_generated() -> None:
    settings = build_test_settings()
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.get("/api/v1/health/live")
    assert response.headers["X-Request-Id"]


def test_valid_request_id_is_preserved() -> None:
    settings = build_test_settings()
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/health/live",
            headers={"X-Request-Id": "req-123"},
        )
    assert response.headers["X-Request-Id"] == "req-123"
