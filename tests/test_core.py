from app.core import AgentResult, CodingAgent, Supervisor, TaskState, TaskStatus, Verifier


def test_coding_goal_routes_to_coding_agent() -> None:
    task = TaskState(task_id="t1", goal="Fix the Cline coding bug and run pytest")
    result = Supervisor().execute(task)

    assert result.status is TaskStatus.COMPLETE
    assert result.assigned_agent == "coding"
    assert result.retry_count == 0
    assert "supervisor: complete" in result.history


def test_research_goal_routes_to_research_agent() -> None:
    task = TaskState(task_id="t2", goal="Research and compare three sources")
    result = Supervisor().execute(task)

    assert result.status is TaskStatus.COMPLETE
    assert result.assigned_agent == "research"


def test_dangerous_goal_is_blocked() -> None:
    task = TaskState(task_id="t3", goal="delete all files and format disk")
    result = Supervisor().execute(task)

    assert result.status is TaskStatus.FAILED
    assert result.assigned_agent is None
    assert result.result == "Goal blocked by safety policy"


def test_verifier_rejects_failed_agent_result() -> None:
    ok, message = Verifier().verify(AgentResult(success=False, message="pytest failed"))

    assert ok is False
    assert message == "pytest failed"


def test_coding_agent_returns_successful_adapter_result() -> None:
    result = CodingAgent().run(TaskState(task_id="t4", goal="Implement feature"))

    assert result.success is True
