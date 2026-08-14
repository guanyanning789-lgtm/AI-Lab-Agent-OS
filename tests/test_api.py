from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_coding_task() -> None:
    response = client.post(
        "/tasks",
        json={"goal": "Fix the Cline bug and run tests"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETE"
    assert body["assigned_agent"] == "coding"
    assert body["steps"][-1]["status"] == "COMPLETE"


def test_rejects_unknown_request_fields() -> None:
    response = client.post(
        "/tasks",
        json={"goal": "Fix code", "unexpected": True},
    )
    assert response.status_code == 422
