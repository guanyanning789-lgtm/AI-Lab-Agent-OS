from __future__ import annotations

import argparse
import json
import shutil
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
        help="Delete/recreate the target as the minimal broken calculator fixture before running.",
    )
    return parser.parse_args()


def reset_calculator_fixture(repository: Path) -> None:
    if repository.exists():
        shutil.rmtree(repository)
    repository.mkdir(parents=True)
    (repository / "calculator.py").write_text(
        "def add(a, b):\n    return a - b\n",
        encoding="utf-8",
    )
    (repository / "test_calculator.py").write_text(
        "from calculator import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repository, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=repository, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.name=AI Lab E2E", "-c", "user.email=ai-lab-e2e@local", "commit", "-m", "test: create broken calculator fixture"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
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
