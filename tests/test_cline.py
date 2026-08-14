import subprocess

from app.cline import ClineCliConfig, ClineCliTransport, ClineRequest, ClineResponse
from app.core import CodingAgent, Supervisor, TaskState, ToolRouter


def _request(tmp_path, **overrides):
    values = {
        "task": "Fix the failing parser test",
        "repository_path": str(tmp_path),
        "tests": ("python -m pytest -q",),
        "mode": "delegate",
        "verification_errors": (),
        "allowed_paths": (),
    }
    values.update(overrides)
    return ClineRequest(**values)


def test_command_uses_safe_defaults(tmp_path):
    transport = ClineCliTransport(ClineCliConfig(executable="cline"))
    command = transport._build_command(_request(tmp_path))

    assert command[0] == "cline"
    assert "--json" in command
    assert command[command.index("--auto-approve") + 1] == "false"
    assert command[command.index("--cwd") + 1] == str(tmp_path)
    assert "--thinking" not in command


def test_prompt_contains_strict_allowed_paths(tmp_path):
    prompt = ClineCliTransport._build_prompt(
        _request(tmp_path, allowed_paths=("calculator.py",))
    )

    assert "STRICT CHANGE SCOPE" in prompt
    assert "- calculator.py" in prompt
    assert "Do not create, modify, rename, or delete any other file." in prompt


def test_windows_ps1_launcher_uses_powershell(tmp_path):
    transport = ClineCliTransport(
        resolver=lambda executable: r"C:\Users\PC\AppData\Roaming\npm\cline.ps1",
        platform_name="nt",
    )
    command = transport._build_launch_command(_request(tmp_path))

    assert command[:4] == ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass"]
    assert command[command.index("-File") + 1].endswith("cline.ps1")


def test_successful_cli_result_is_accepted(tmp_path):
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"type":"message","text":"Implemented fix"}\n',
            stderr="",
        )

    result = ClineCliTransport(
        runner=runner,
        resolver=lambda executable: "/usr/local/bin/cline",
        platform_name="posix",
    ).send(_request(tmp_path))

    assert result.accepted is True
    assert result.message == "Implemented fix"
    assert calls[0][1]["cwd"] == str(tmp_path)


def test_nonzero_exit_is_rejected(tmp_path):
    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 2, stdout="", stderr="authentication required")

    result = ClineCliTransport(
        runner=runner,
        resolver=lambda executable: "/usr/local/bin/cline",
        platform_name="posix",
    ).send(_request(tmp_path))

    assert result.accepted is False
    assert "authentication required" in result.message


def test_missing_repository_is_rejected(tmp_path):
    result = ClineCliTransport().send(_request(tmp_path / "missing"))
    assert result.accepted is False
    assert "does not exist" in result.message.lower()


def test_coding_agent_requires_approval(tmp_path):
    class Transport:
        def send(self, request):
            raise AssertionError("transport must not run without approval")

    task = TaskState(
        task_id="t1",
        goal="fix code",
        repository_path=str(tmp_path),
        approved=False,
        max_retries=0,
    )
    result = CodingAgent(Transport()).run(task)

    assert result.success is False
    assert "approval" in result.message.lower()


def test_supervisor_retries_as_repair_with_verification_error(tmp_path):
    class FlakyTransport:
        def __init__(self):
            self.requests = []

        def send(self, request):
            self.requests.append(request)
            if len(self.requests) == 1:
                return ClineResponse(False, "2 tests failed")
            return ClineResponse(True, "repair completed")

    transport = FlakyTransport()
    supervisor = Supervisor(router=ToolRouter(coding_agent=CodingAgent(transport)))
    task = TaskState(
        task_id="t2",
        goal="fix the failing code tests",
        repository_path=str(tmp_path),
        tests=(),
        approved=True,
        allowed_paths=("calculator.py",),
        max_retries=2,
    )

    finished = supervisor.execute(task)

    assert finished.status.value == "COMPLETE"
    assert finished.retry_count == 1
    assert len(transport.requests) == 2
    assert transport.requests[0].mode == "delegate"
    assert transport.requests[0].allowed_paths == ("calculator.py",)
    assert transport.requests[1].mode == "repair"
    assert "2 tests failed" in transport.requests[1].verification_errors
