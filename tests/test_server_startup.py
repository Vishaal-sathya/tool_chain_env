from starlette.testclient import TestClient
from app import app

client = TestClient(app)

def test_server_health_check():
    """
    A simple test to ensure the server starts and the health check endpoint is available.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
