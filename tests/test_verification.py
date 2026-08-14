import subprocess

from app.core import AgentResult, CodingAgent, Supervisor, TaskState, ToolRouter, Verifier
from app.cline import ClineResponse
from app.verification import TestCommandVerifier


def test_verifier_runs_allowed_command_and_returns_evidence(tmp_path):
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, stdout="7 passed in 0.12s", stderr="")

    verifier = TestCommandVerifier(runner=runner)
    result = verifier.run(
        repository_path=str(tmp_path),
        commands=("python -m pytest -q",),
    )

    assert result.passed is True
    assert "7 passed" in result.message
    assert calls[0][0][:3] == ["python", "-m", "pytest"]
    assert calls[0][1]["cwd"] == str(tmp_path)
    assert calls[0][1]["check"] is False


def test_verifier_rejects_arbitrary_shell_program(tmp_path):
    result = TestCommandVerifier().run(
        repository_path=str(tmp_path),
        commands=("git reset --hard",),
    )

    assert result.passed is False
    assert "not allowed" in result.message


def test_failed_test_output_becomes_repair_prompt(tmp_path):
    class Transport:
        def __init__(self):
            self.requests = []

        def send(self, request):
            self.requests.append(request)
            return ClineResponse(True, "cline completed")

    outcomes = [
        subprocess.CompletedProcess(["python"], 1, stdout="FAILED test_parser.py::test_parse", stderr=""),
        subprocess.CompletedProcess(["python"], 0, stdout="1 passed", stderr=""),
    ]

    def runner(args, **kwargs):
        return outcomes.pop(0)

    transport = Transport()
    supervisor = Supervisor(
        router=ToolRouter(coding_agent=CodingAgent(transport)),
        verifier=Verifier(test_verifier=TestCommandVerifier(runner=runner)),
    )
    task = TaskState(
        task_id="verify-repair",
        goal="fix parser code and run tests",
        repository_path=str(tmp_path),
        tests=("python -m pytest -q",),
        approved=True,
        max_retries=2,
    )

    finished = supervisor.execute(task)

    assert finished.status.value == "COMPLETE"
    assert finished.retry_count == 1
    assert len(transport.requests) == 2
    assert transport.requests[1].mode == "repair"
    assert any("FAILED test_parser.py::test_parse" in item for item in transport.requests[1].verification_errors)
    assert "1 passed" in finished.steps[3].message
