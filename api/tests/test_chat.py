import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_create_session():
    response = client.post("/api/v1/chat/sessions")
    assert response.status_code == 200
    assert "session_id" in response.json()


@pytest.mark.asyncio
async def test_send_message():
    # Create session
    session_response = client.post("/api/v1/chat/sessions")
    session_id = session_response.json()["session_id"]

    # Send message
    response = client.post(
        "/api/v1/chat/messages", json={"message": "Hello, how are you?", "session_id": session_id}
    )

    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["tokens_used"] > 0
