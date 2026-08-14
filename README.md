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

## Current vertical slice

```text
Natural-language goal
    -> Supervisor
    -> Task State
    -> Tool Router
    -> Coding Agent
    -> Cline transport (optional, explicit enable)
    -> Verification
    -> Retry / Repair with previous verification error
    -> Replan after retry budget is exhausted
    -> COMPLETE / FAILED
```

The runtime keeps a deterministic in-process Coding Agent fallback so orchestration can be tested in CI without Cline installed. When `AI_LAB_CLINE_ENABLED=1`, Coding Agent delegates through the real Cline CLI transport.

## Safety and approval handoff

Real Cline execution is **off by default**. AI Lab owns the outer approval boundary.

- `AI_LAB_CLINE_ENABLED=1` explicitly enables the real Cline-backed Coding Agent.
- `approved: true` is still required on every individual coding task before Cline is invoked.
- Once those outer gates pass, Cline tool auto-approval defaults to `true` because JSON/headless execution cannot pause for an interactive terminal approval prompt.
- `AI_LAB_CLINE_AUTO_APPROVE=0` can still disable inner Cline tool auto-approval for debugging/interactive approval workflows, but this is not suitable for unattended JSON/headless execution.
- Cline is instructed to stay inside the supplied repository and not commit, push, merge, or change branches.
- AI Lab Agent OS retains ownership of verification, retry, repair, replan and completion decisions.

The intended trust chain is:

```text
human/operator approval
 -> AI Lab task approval + repository scope
 -> Cline internal tool auto-approval inside that task
 -> independent AI Lab verification
 -> COMPLETE / Repair / Replan
```

## Quick start

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
uvicorn app.main:app --reload
```

### Deterministic runtime smoke test

```bash
curl -X POST http://127.0.0.1:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"goal":"Fix the coding task and verify it"}'
```

### Real Cline-backed coding task

On Windows PowerShell:

```powershell
$env:AI_LAB_CLINE_ENABLED = "1"
uvicorn app.main:app --reload
```

Then POST a task containing the local repository path, verification commands and explicit approval:

```json
{
  "goal": "Fix the failing parser test",
  "repository_path": "C:\\AI-Lab\\target-repo",
  "tests": ["python -m pytest -q"],
  "approved": true,
  "max_retries": 2
}
```

If the first Cline attempt fails verification, the Supervisor records the failure, increments the retry budget, switches the next Cline request to `repair` mode, and includes prior verification errors in the repair prompt.

### Local real-Cline acceptance harness

`scripts/local_cline_e2e.py` is deliberately an explicitly approved acceptance harness. It turns on Cline tool auto-approval for that scoped test task so the headless process can actually edit files and run tools without waiting for an impossible TTY approval.

## V0.1 acceptance target

V0.1 is accepted only after the real local end-to-end proof succeeds:

```text
user goal
 -> Supervisor
 -> Cline
 -> repository change
 -> tests
 -> verification
 -> automatic repair/replan if needed
 -> COMPLETE
```

A successful mock or deterministic-adapter test does **not** count as completion of this milestone.

## Design rule

Agents are intentionally few. Reliability, memory, routing, scheduling, verification and observability are shared runtime capabilities rather than separate chatty agents.
