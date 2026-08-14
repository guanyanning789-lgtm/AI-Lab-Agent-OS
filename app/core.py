from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from app.cline import ClineRequest, ClineTransport
from app.verification import TestCommandVerifier


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    REPAIRING = "REPAIRING"
    REPLANNING = "REPLANNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


@dataclass(slots=True)
class TaskStep:
    name: str
    status: TaskStatus = TaskStatus.PENDING
    message: str = ""


@dataclass(slots=True)
class TaskState:
    task_id: str
    goal: str
    status: TaskStatus = TaskStatus.PENDING
    current_step: int = 0
    retry_count: int = 0
    max_retries: int = 2
    assigned_agent: str | None = None
    repository_path: str | None = None
    tests: tuple[str, ...] = ()
    approved: bool = False
    verification_errors: tuple[str, ...] = ()
    steps: list[TaskStep] = field(default_factory=list)
    history: list[str] = field(default_factory=list)
    result: str | None = None

    def record(self, event: str) -> None:
        self.history.append(event)


@dataclass(slots=True)
class AgentResult:
    success: bool
    message: str
    artifacts: list[str] = field(default_factory=list)


class Agent(Protocol):
    name: str

    def run(self, task: TaskState) -> AgentResult: ...


class CodingAgent:
    name = "coding"

    def __init__(self, transport: ClineTransport | None = None) -> None:
        self._transport = transport

    def run(self, task: TaskState) -> AgentResult:
        task.record("coding-agent: execution requested")

        if self._transport is None:
            return AgentResult(
                success=True,
                message=f"Coding task accepted by deterministic adapter: {task.goal}",
            )

        if not task.approved:
            return AgentResult(
                success=False,
                message="Human approval is required before delegating a coding task to Cline.",
            )
        if not task.repository_path:
            return AgentResult(
                success=False,
                message="repository_path is required for Cline coding tasks.",
            )

        mode = "repair" if task.verification_errors else "delegate"
        response = self._transport.send(
            ClineRequest(
                task=task.goal,
                repository_path=task.repository_path,
                tests=task.tests,
                mode=mode,
                verification_errors=task.verification_errors,
            )
        )
        return AgentResult(success=response.accepted, message=response.message)


class ResearchAgent:
    name = "research"

    def run(self, task: TaskState) -> AgentResult:
        task.record("research-agent: execution requested")
        return AgentResult(success=True, message=f"Research task accepted: {task.goal}")


class ComputerAgent:
    name = "computer"

    def run(self, task: TaskState) -> AgentResult:
        task.record("computer-agent: execution requested")
        return AgentResult(success=True, message=f"Computer task accepted: {task.goal}")


class ToolRouter:
    def __init__(self, *, coding_agent: Agent | None = None) -> None:
        self._agents: dict[str, Agent] = {
            "coding": coding_agent or CodingAgent(),
            "research": ResearchAgent(),
            "computer": ComputerAgent(),
        }

    def classify(self, goal: str) -> str:
        text = goal.lower()
        if any(word in text for word in ("code", "coding", "bug", "test", "pytest", "cline", "代码", "修复", "测试")):
            return "coding"
        if any(word in text for word in ("research", "search", "compare", "资料", "研究", "搜索")):
            return "research"
        return "computer"

    def get_agent(self, name: str) -> Agent:
        return self._agents[name]


class SafetyGate:
    blocked_terms = ("delete all", "format disk", "rm -rf /", "清空磁盘")

    def check(self, goal: str) -> tuple[bool, str]:
        normalized = goal.lower()
        if any(term in normalized for term in self.blocked_terms):
            return False, "Goal blocked by safety policy"
        return True, "safe"


class Verifier:
    def __init__(self, *, test_verifier: TestCommandVerifier | None = None) -> None:
        self._test_verifier = test_verifier or TestCommandVerifier()

    def verify(self, result: AgentResult, task: TaskState | None = None) -> tuple[bool, str]:
        if not result.success:
            return False, result.message or "verification failed"

        if (
            task is not None
            and task.assigned_agent == "coding"
            and task.repository_path
            and task.tests
        ):
            evidence = self._test_verifier.run(
                repository_path=task.repository_path,
                commands=task.tests,
            )
            return evidence.passed, evidence.message

        return True, "verification passed"


class RepairEngine:
    def repair(self, task: TaskState, failure: str) -> None:
        task.status = TaskStatus.REPAIRING
        task.retry_count += 1
        task.verification_errors = (*task.verification_errors, failure)
        task.record(f"repair: {failure}")


class ReplanEngine:
    def replan(self, task: TaskState, failure: str) -> None:
        task.status = TaskStatus.REPLANNING
        task.record(f"replan: {failure}")


class Supervisor:
    def __init__(
        self,
        *,
        router: ToolRouter | None = None,
        verifier: Verifier | None = None,
    ) -> None:
        self.router = router or ToolRouter()
        self.safety = SafetyGate()
        self.verifier = verifier or Verifier()
        self.repair = RepairEngine()
        self.replan = ReplanEngine()

    def plan(self, task: TaskState) -> None:
        task.steps = [
            TaskStep("understand_goal"),
            TaskStep("route_agent"),
            TaskStep("execute"),
            TaskStep("verify"),
            TaskStep("complete"),
        ]
        task.record("supervisor: plan created")

    def execute(self, task: TaskState) -> TaskState:
        safe, reason = self.safety.check(task.goal)
        if not safe:
            task.status = TaskStatus.FAILED
            task.result = reason
            task.record(f"safety: blocked ({reason})")
            return task

        self.plan(task)
        task.status = TaskStatus.RUNNING
        task.steps[0].status = TaskStatus.COMPLETE

        agent_name = self.router.classify(task.goal)
        task.assigned_agent = agent_name
        task.steps[1].status = TaskStatus.COMPLETE
        task.record(f"router: {agent_name}")

        agent = self.router.get_agent(agent_name)
        while True:
            task.current_step = 2
            task.steps[2].status = TaskStatus.RUNNING
            result = agent.run(task)
            task.steps[2].status = TaskStatus.COMPLETE if result.success else TaskStatus.FAILED

            task.status = TaskStatus.VERIFYING
            task.current_step = 3
            ok, verification_message = self.verifier.verify(result, task)
            task.steps[3].message = verification_message
            task.record(f"verification: {verification_message}")
            if ok:
                task.steps[3].status = TaskStatus.COMPLETE
                task.steps[4].status = TaskStatus.COMPLETE
                task.status = TaskStatus.COMPLETE
                task.current_step = 4
                task.result = result.message
                task.record("supervisor: complete")
                return task

            task.steps[3].status = TaskStatus.FAILED
            if task.retry_count < task.max_retries:
                self.repair.repair(task, verification_message)
                continue

            self.replan.replan(task, verification_message)
            task.status = TaskStatus.FAILED
            task.result = verification_message
            return task
