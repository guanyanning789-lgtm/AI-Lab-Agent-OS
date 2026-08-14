from __future__ import annotations

import os
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.cline import ClineCliConfig, ClineCliTransport
from app.core import CodingAgent, Supervisor, TaskState, ToolRouter
from app.state_store import JsonTaskStore


app = FastAPI(title="AI Lab Agent OS", version="0.1.0")


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_supervisor() -> Supervisor:
    if not _env_flag("AI_LAB_CLINE_ENABLED"):
        return Supervisor()

    # Cline's JSON/headless mode cannot pause for terminal approvals. Once the
    # operator has explicitly enabled the Cline transport, individual tasks
    # are still blocked by TaskState.approved. For an approved task we let
    # Cline execute its internal tools unattended, while AI Lab retains the
    # repository scope, verification and retry/repair authority.
    transport = ClineCliTransport(
        ClineCliConfig(
            executable=os.environ.get("AI_LAB_CLINE_EXECUTABLE", "cline"),
            timeout_seconds=int(os.environ.get("AI_LAB_CLINE_TIMEOUT", "900")),
            auto_approve=_env_flag("AI_LAB_CLINE_AUTO_APPROVE", default=True),
            thinking=os.environ.get("AI_LAB_CLINE_THINKING") or None,
        )
    )
    return Supervisor(router=ToolRouter(coding_agent=CodingAgent(transport)))


supervisor = build_supervisor()
task_store = JsonTaskStore(os.environ.get("AI_LAB_TASK_STORE", ".ai-lab/tasks"))


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


def _response(task: TaskState) -> TaskResponse:
    return TaskResponse(
        task_id=task.task_id,
        goal=task.goal,
        status=task.status.value,
        assigned_agent=task.assigned_agent,
        current_step=task.current_step,
        retry_count=task.retry_count,
        result=task.result,
        history=task.history,
        steps=[
            {"name": step.name, "status": step.status.value, "message": step.message}
            for step in task.steps
        ],
    )


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
    task_store.save(task)

    try:
        finished = supervisor.execute(task)
    except Exception as exc:
        task.result = f"task execution failed: {exc}"
        task_store.save(task)
        raise HTTPException(status_code=500, detail=task.result) from exc

    task_store.save(finished)
    return _response(finished)


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str) -> TaskResponse:
    try:
        task = task_store.load(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return _response(task)
