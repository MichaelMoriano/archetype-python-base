from fastapi.testclient import TestClient

from python_ai_service.bootstrap.main import create_app
from tests.settings_helpers import build_test_settings


def test_health_is_public_and_versioned() -> None:
    settings = build_test_settings()
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"
