# AI Lab Agent OS

AI Lab Agent OS is a local-first autonomous agent runtime designed around one outcome:

> A user states a natural-language goal; the system plans, routes work to specialist agents, executes tools, verifies results, automatically retries/repairs/replans when needed, and returns a final report.

## Target architecture

- Supervisor
- Agent Runtime: Task State, Tool Router, Context Manager, Scheduler / Queue
- Specialist Agents: Coding, Research, Computer
- Reliability: Safety, Approval, Verification, Retry, Repair, Replan
- Intelligence: Memory, Model Router, Resource Manager
- Observability: Logging, Trace, Metrics, Audit

## Current Coding vertical slice

```text
Natural-language goal
 -> Supervisor
 -> Task State
 -> Tool Router
 -> Coding Agent
 -> Cline CLI
 -> Scope Guard
 -> independent pytest verification
 -> Retry / Repair with real failure evidence
 -> Replan after retry budget is exhausted
 -> COMPLETE / FAILED
```

## Safety, approval and change scope

Real Cline execution is off by default. AI Lab owns the outer approval boundary.

- `AI_LAB_CLINE_ENABLED=1` enables the real Cline-backed Coding Agent.
- `approved: true` is required on every individual coding task.
- Headless Cline tool auto-approval is enabled only after those outer gates pass.
- `allowed_paths` can restrict a task to explicit repository-relative files.
- The same scope is written into Cline's prompt and independently checked after execution using Git status.
- Unexpected source-file changes cause verification failure instead of being silently accepted.
- Generated Python caches such as `__pycache__` and `.pytest_cache` are ignored by the source scope check.
- AI Lab independently runs verification and owns Retry / Repair / Replan / COMPLETE.

Trust chain:

```text
human/operator approval
 -> AI Lab task approval + repository + allowed file scope
 -> Cline internal tool auto-approval
 -> AI Lab Scope Guard
 -> AI Lab test verification
 -> COMPLETE / Repair / Replan
```

## Quick start

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
uvicorn app.main:app --reload
```

### Real Cline-backed API task

```json
{
  "goal": "Fix the broken add function in calculator.py",
  "repository_path": "C:\\AI-Lab\\target-repo",
  "tests": ["python -m pytest -q"],
  "allowed_paths": ["calculator.py"],
  "approved": true,
  "max_retries": 2
}
```

## Local real-Cline acceptance harness

The acceptance harness can now rebuild the disposable calculator repository itself, so stale files from previous experiments cannot contaminate the result.

```powershell
python .\scripts\local_cline_e2e.py `
  "C:\AI-Lab\Agent-OS-E2E-Test" `
  "Fix the broken add function in calculator.py so the existing test passes. Make the smallest correct code change." `
  --reset-calculator-fixture `
  --allow-path "calculator.py" `
  --test "python -m pytest -q" `
  --max-retries 2
```

The harness deletes and recreates only the disposable target path passed to it, initializes a two-file Git repository, inserts the intentionally broken subtraction implementation, and then starts the approved Cline task.

## V0.1 acceptance target

V0.1 is accepted only after the real Windows end-to-end proof succeeds:

```text
user goal
 -> Supervisor
 -> Cline
 -> only calculator.py changes
 -> pytest passes
 -> AI Lab verification passes
 -> COMPLETE
```

A successful mock or deterministic-adapter test does not count as completion of this milestone.

## Design rule

Agents are intentionally few. Reliability, memory, routing, scheduling, verification and observability are shared runtime capabilities rather than separate chatty agents.
