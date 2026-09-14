from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings


def test_health_endpoint_status_code():
    """GET /health возвращает HTTP 200."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_payload():
    """GET /health возвращает status = 'ok' и наименование из настроек."""
    client = TestClient(app)
    response = client.get("/health")
    data = response.json()
    settings = get_settings()

    assert data["status"] == "ok"
    assert data["service"] == settings.app_name
