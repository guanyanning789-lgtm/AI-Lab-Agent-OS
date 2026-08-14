from fastapi.testclient import TestClient

from app.main import app, build_supervisor


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


def test_real_cline_transport_defaults_to_inner_auto_approval_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("AI_LAB_CLINE_ENABLED", "1")
    monkeypatch.delenv("AI_LAB_CLINE_AUTO_APPROVE", raising=False)

    supervisor = build_supervisor()
    coding_agent = supervisor.router.get_agent("coding")

    assert coding_agent._transport is not None
    assert coding_agent._transport._config.auto_approve is True


def test_inner_auto_approval_can_be_explicitly_disabled(monkeypatch) -> None:
    monkeypatch.setenv("AI_LAB_CLINE_ENABLED", "1")
    monkeypatch.setenv("AI_LAB_CLINE_AUTO_APPROVE", "0")

    supervisor = build_supervisor()
    coding_agent = supervisor.router.get_agent("coding")

    assert coding_agent._transport is not None
    assert coding_agent._transport._config.auto_approve is False
