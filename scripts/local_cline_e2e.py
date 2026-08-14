from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.cline import ClineCliTransport
from app.core import CodingAgent, Supervisor, TaskState, ToolRouter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the real local Cline acceptance loop for AI Lab Agent OS."
    )
    parser.add_argument("repository", help="Target repository Cline is allowed to modify")
    parser.add_argument("goal", help="Natural-language coding goal")
    parser.add_argument(
        "--test",
        action="append",
        default=[],
        dest="tests",
        help="Verification command; repeat for multiple commands",
    )
    parser.add_argument("--max-retries", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repository = Path(args.repository).resolve()

    supervisor = Supervisor(
        router=ToolRouter(coding_agent=CodingAgent(ClineCliTransport()))
    )
    task = TaskState(
        task_id="local-cline-e2e",
        goal=args.goal,
        repository_path=str(repository),
        tests=tuple(args.tests),
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
        "result": finished.result,
        "verification_errors": list(finished.verification_errors),
        "steps": [
            {
                "name": step.name,
                "status": step.status.value,
                "message": step.message,
            }
            for step in finished.steps
        ],
        "history": finished.history,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if finished.status.value == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
