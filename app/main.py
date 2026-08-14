from __future__ import annotations

import os
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.cline import ClineCliConfig, ClineCliTransport
from app.core import CodingAgent, Supervisor, TaskState, ToolRouter


app = FastAPI(title="AI Lab Agent OS", version="0.1.0")


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_supervisor() -> Supervisor:
    if not _env_flag("AI_LAB_CLINE_ENABLED"):
        return Supervisor()

    transport = ClineCliTransport(
        ClineCliConfig(
            executable=os.environ.get("AI_LAB_CLINE_EXECUTABLE", "cline"),
            timeout_seconds=int(os.environ.get("AI_LAB_CLINE_TIMEOUT", "900")),
            auto_approve=_env_flag("AI_LAB_CLINE_AUTO_APPROVE"),
            thinking=os.environ.get("AI_LAB_CLINE_THINKING") or None,
        )
    )
    return Supervisor(router=ToolRouter(coding_agent=CodingAgent(transport)))


supervisor = build_supervisor()


class TaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1)
    max_retries: int = Field(default=2, ge=0, le=5)
    repository_path: str | None = None
    tests: tuple[str, ...] = ()
    approved: bool = False


class TaskResponse(BaseModel):
    task_id: str
    goal: str
    status: str
    assigned_agent: str | None
    current_step: int
    retry_count: int
    result: str | None
    history: list[str]
    steps: list[dict[str, str]]


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "version": "0.1.0",
        "cline_enabled": _env_flag("AI_LAB_CLINE_ENABLED"),
    }


@app.post("/tasks", response_model=TaskResponse)
def create_task(request: TaskRequest) -> TaskResponse:
    task = TaskState(
        task_id=str(uuid4()),
        goal=request.goal,
        max_retries=request.max_retries,
        repository_path=request.repository_path,
        tests=request.tests,
        approved=request.approved,
    )

    try:
        finished = supervisor.execute(task)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"task execution failed: {exc}") from exc

    return TaskResponse(
        task_id=finished.task_id,
        goal=finished.goal,
        status=finished.status.value,
        assigned_agent=finished.assigned_agent,
        current_step=finished.current_step,
        retry_count=finished.retry_count,
        result=finished.result,
        history=finished.history,
        steps=[
            {"name": step.name, "status": step.status.value, "message": step.message}
            for step in finished.steps
        ],
    )
