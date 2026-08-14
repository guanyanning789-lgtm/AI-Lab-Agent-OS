# AI Lab Agent OS

AI Lab Agent OS is a local-first autonomous agent runtime designed around one outcome:

> A user states a natural-language goal; the system plans, routes work to specialist agents, executes tools, verifies results, automatically retries/repairs/replans when needed, and returns a final report.

## Target architecture

- Supervisor
- Agent Runtime
  - Task State
  - Tool Router
  - Context Manager
  - Scheduler / Queue
- Specialist Agents
  - Coding Agent
  - Research Agent
  - Computer Agent
- Reliability Layer
  - Safety
  - Approval
  - Verification
  - Retry
  - Repair
  - Replan
- Intelligence Layer
  - Memory
  - Model Router
  - Resource Manager
- Observability Layer
  - Logging
  - Trace
  - Metrics
  - Audit

## V0.1 acceptance target

The first executable vertical slice is:

```text
Natural-language goal
    -> Supervisor
    -> Task State
    -> Tool Router
    -> Coding Agent
    -> Verification
    -> Retry / Repair / Replan on failure
    -> COMPLETE
```

V0.1 uses an in-process deterministic coding-agent adapter so the orchestration loop can be tested without requiring Cline to be installed in CI. A real Cline transport is the next integration target.

## Quick start

```bash
python -m pip install -e .[dev]
pytest
uvicorn app.main:app --reload
```

Then submit a task:

```bash
curl -X POST http://127.0.0.1:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"goal":"Fix the coding task and verify it"}'
```

## Design rule

Agents are intentionally few. Reliability, memory, routing, scheduling, verification and observability are shared runtime capabilities rather than separate chatty agents.
