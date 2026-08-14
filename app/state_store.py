from __future__ import annotations

import json
from pathlib import Path

from app.core import TaskState, TaskStatus, TaskStep


class JsonTaskStore:
    """Minimal durable task-state store for the V0.1 runtime.

    Files are written atomically enough for a single-process local runtime:
    write a temporary JSON file, then replace the destination.
    """

    def __init__(self, root: str | Path = ".ai-lab/tasks") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, task_id: str) -> Path:
        safe = "".join(ch for ch in task_id if ch.isalnum() or ch in {"-", "_"})
        if not safe or safe != task_id:
            raise ValueError("invalid task_id")
        return self.root / f"{safe}.json"

    @staticmethod
    def _to_dict(task: TaskState) -> dict:
        return {
            "task_id": task.task_id,
            "goal": task.goal,
            "status": task.status.value,
            "current_step": task.current_step,
            "retry_count": task.retry_count,
            "max_retries": task.max_retries,
            "assigned_agent": task.assigned_agent,
            "repository_path": task.repository_path,
            "tests": list(task.tests),
            "approved": task.approved,
            "verification_errors": list(task.verification_errors),
            "steps": [
                {
                    "name": step.name,
                    "status": step.status.value,
                    "message": step.message,
                }
                for step in task.steps
            ],
            "history": list(task.history),
            "result": task.result,
        }

    @staticmethod
    def _from_dict(payload: dict) -> TaskState:
        return TaskState(
            task_id=str(payload["task_id"]),
            goal=str(payload["goal"]),
            status=TaskStatus(payload.get("status", "PENDING")),
            current_step=int(payload.get("current_step", 0)),
            retry_count=int(payload.get("retry_count", 0)),
            max_retries=int(payload.get("max_retries", 2)),
            assigned_agent=payload.get("assigned_agent"),
            repository_path=payload.get("repository_path"),
            tests=tuple(payload.get("tests", ())),
            approved=bool(payload.get("approved", False)),
            verification_errors=tuple(payload.get("verification_errors", ())),
            steps=[
                TaskStep(
                    name=str(step["name"]),
                    status=TaskStatus(step.get("status", "PENDING")),
                    message=str(step.get("message", "")),
                )
                for step in payload.get("steps", [])
            ],
            history=[str(item) for item in payload.get("history", [])],
            result=payload.get("result"),
        )

    def save(self, task: TaskState) -> Path:
        destination = self._path(task.task_id)
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self._to_dict(task), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(destination)
        return destination

    def load(self, task_id: str) -> TaskState | None:
        path = self._path(task_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return self._from_dict(payload)
