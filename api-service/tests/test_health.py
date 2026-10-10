"""The liveness check the frontend and compose rely on."""

from fastapi.testclient import TestClient

from main import app


def test_health_returns_ok():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
