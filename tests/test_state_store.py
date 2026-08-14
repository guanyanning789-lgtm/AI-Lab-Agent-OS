from app.core import TaskState, TaskStatus, TaskStep
from app.state_store import JsonTaskStore


def test_task_state_round_trip(tmp_path):
    store = JsonTaskStore(tmp_path / "tasks")
    task = TaskState(
        task_id="task-1",
        goal="fix code",
        status=TaskStatus.REPAIRING,
        current_step=3,
        retry_count=1,
        max_retries=2,
        assigned_agent="coding",
        repository_path="C:/repo",
        tests=("python -m pytest -q",),
        approved=True,
        verification_errors=("1 failed",),
        allowed_paths=("calculator.py",),
        steps=[TaskStep("verify", status=TaskStatus.FAILED, message="1 failed")],
        history=["created", "repair: 1 failed"],
        result=None,
    )

    path = store.save(task)
    loaded = store.load("task-1")

    assert path.exists()
    assert loaded is not None
    assert loaded.task_id == task.task_id
    assert loaded.status is TaskStatus.REPAIRING
    assert loaded.retry_count == 1
    assert loaded.tests == ("python -m pytest -q",)
    assert loaded.verification_errors == ("1 failed",)
    assert loaded.allowed_paths == ("calculator.py",)
    assert loaded.steps[0].status is TaskStatus.FAILED


def test_missing_task_returns_none(tmp_path):
    store = JsonTaskStore(tmp_path / "tasks")
    assert store.load("missing") is None


def test_invalid_task_id_is_rejected(tmp_path):
    store = JsonTaskStore(tmp_path / "tasks")
    try:
        store.load("../escape")
    except ValueError as exc:
        assert "invalid task_id" in str(exc)
    else:
        raise AssertionError("expected invalid task id to be rejected")
