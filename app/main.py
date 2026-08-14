from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.core import Supervisor, TaskState


app = FastAPI(title="AI Lab Agent OS", version="0.1.0")
supervisor = Supervisor()


class TaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1)
    max_retries: int = Field(default=2, ge=0, le=5)


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
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@app.post("/tasks", response_model=TaskResponse)
def create_task(request: TaskRequest) -> TaskResponse:
    task = TaskState(
        task_id=str(uuid4()),
        goal=request.goal,
        max_retries=request.max_retries,
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
