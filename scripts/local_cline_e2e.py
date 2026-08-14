from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from app.cline import ClineCliConfig, ClineCliTransport
from app.core import CodingAgent, Supervisor, TaskState, ToolRouter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the real local Cline acceptance loop for AI Lab Agent OS."
    )
    parser.add_argument("repository", help="Target repository Cline is allowed to modify")
    parser.add_argument("goal", help="Natural-language coding goal")
    parser.add_argument("--test", action="append", default=[], dest="tests")
    parser.add_argument("--allow-path", action="append", default=[], dest="allowed_paths")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument(
        "--reset-calculator-fixture",
        action="store_true",
        help="Reset/recreate the target as the minimal broken calculator fixture before running.",
    )
    return parser.parse_args()


def _run_git(repository: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repository),
        check=check,
        capture_output=True,
        text=True,
    )


def reset_calculator_fixture(repository: Path) -> None:
    """Create a deterministic minimal fixture without deleting the .git directory.

    On Windows, deleting an existing repository can fail because Git objects may
    be temporarily held open by Git, antivirus, indexing, or another process.
    Reusing the repository and cleaning the worktree avoids that failure mode.
    """
    repository.mkdir(parents=True, exist_ok=True)
    git_dir = repository / ".git"

    if git_dir.is_dir():
        # Restore tracked content and remove every untracked/ignored worktree
        # artifact while preserving .git itself.
        _run_git(repository, "reset", "--hard", "HEAD", check=False)
        _run_git(repository, "clean", "-fdx", check=True)
    else:
        # A pre-existing non-git directory is only used for this disposable
        # acceptance fixture. Remove its children without touching the root.
        for child in repository.iterdir():
            if child.is_dir():
                subprocess.run(
                    ["powershell.exe", "-NoProfile", "-Command", "Remove-Item -LiteralPath $args[0] -Recurse -Force", str(child)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            else:
                child.unlink()
        _run_git(repository, "init")

    (repository / "calculator.py").write_text(
        "def add(a, b):\n    return a - b\n",
        encoding="utf-8",
    )
    (repository / "test_calculator.py").write_text(
        "from calculator import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )

    # Ensure the fixture has exactly these two tracked source/test files, then
    # create a fresh baseline commit. If the repository already had history,
    # amend/resetting to a new baseline would preserve unrelated tracked files;
    # instead stage deletions too and commit the deterministic fixture state.
    _run_git(repository, "add", "-A")
    staged = _run_git(repository, "diff", "--cached", "--quiet", check=False)
    if staged.returncode != 0:
        _run_git(
            repository,
            "-c",
            "user.name=AI Lab E2E",
            "-c",
            "user.email=ai-lab-e2e@local",
            "commit",
            "-m",
            "test: reset broken calculator fixture",
        )

    # Abort if unrelated worktree files somehow survived the reset. This keeps
    # the E2E proof honest before Cline is allowed to run.
    expected = {"calculator.py", "test_calculator.py"}
    actual = {
        path.relative_to(repository).as_posix()
        for path in repository.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }
    unexpected = sorted(actual - expected)
    if unexpected:
        raise RuntimeError(
            "fixture reset left unexpected files: " + ", ".join(unexpected)
        )


def main() -> int:
    args = parse_args()
    repository = Path(args.repository).resolve()
    if args.reset_calculator_fixture:
        reset_calculator_fixture(repository)

    transport = ClineCliTransport(ClineCliConfig(auto_approve=True))
    supervisor = Supervisor(router=ToolRouter(coding_agent=CodingAgent(transport)))
    task = TaskState(
        task_id="local-cline-e2e",
        goal=args.goal,
        repository_path=str(repository),
        tests=tuple(args.tests),
        allowed_paths=tuple(args.allowed_paths),
        approved=True,
        max_retries=args.max_retries,
    )
    finished = supervisor.execute(task)

    payload = {
        "task_id": finished.task_id,
        "goal": finished.goal,
        "status": finished.status.value,
        "assigned_agent": finished.assigned_agent,
        "retry_count": finished.retry_count,
        "allowed_paths": list(finished.allowed_paths),
        "result": finished.result,
        "verification_errors": list(finished.verification_errors),
        "steps": [
            {"name": step.name, "status": step.status.value, "message": step.message}
            for step in finished.steps
        ],
        "history": finished.history,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if finished.status.value == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
