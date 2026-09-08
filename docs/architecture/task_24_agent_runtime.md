# TASK 24 — Enterprise Agent Runtime & Typed Tool Orchestration Architecture

## Executive Summary

TASK 24 advances the platform from a unified AI Analyst to a **Controlled Enterprise Agent Runtime**. The runtime operates on an uncompromising security and engineering foundation:

> **The LLM is not the security boundary.**  
> The model proposes actions, plans, and parameters; the server enforces policies, validates schemas, verifies RBAC, scopes tenancy, monitors budgets, and arbitrates execution.

This platform implements a **bounded, tool-constrained, observable, auditable, and cancellable** runtime. It strictly prohibits autonomous infinite loops, arbitrary code execution, raw database queries bypassing security layers, and unvetted external side-effects.

---

## 1. Architectural Flow

Every agent session proceeds strictly through an 8-stage pipeline:

```text
User Goal
    ↓
Agent Profile & Policy
    ↓
Plan Generation (Deterministic / Structured LLM)
    ↓
Plan Validation (Max Steps, Known Tools, Budget Feasibility)
    ↓
Step Loop:
    [ Approval Gate Check ] (Awaiting human approval if sensitive)
        ↓
    [ Loop & Duplicate Detector ] (Idempotent cache / Loop detection)
        ↓
    [ Pre-Flight Security Gate ] (State, Tenant, RBAC, Profile, Schema, Budget, Timeout)
        ↓
    [ Tool Execution ] (Existing application service adapters)
        ↓
    [ Post-Flight Updates ] (Budget consumption, Evidence recording, Checkpoint snapshot)
    ↓
Evidence-Grounded Final Answer Synthesis (No Evidence → No Claim)
```

---

## 2. Domain Model & Entities

The agent runtime is backed by five persistent relational entities (managed under Alembic revision `fb758e565435`):

1. **`AgentSession`** (`agent_sessions`):
   - Represents the lifecycle of an agent invocation.
   - Fields: `id`, `organization_id`, `created_by`, `status`, `agent_type`, `goal`, `created_at`, `started_at`, `completed_at`, `cancelled_at`, `trace_id`, `request_id`, `plan_id`, `current_step`, `max_steps`, `error_details`.
2. **`AgentPlan`** (`agent_plans`):
   - Represents the validated, structured sequence of steps to fulfill the goal.
   - Fields: `id`, `session_id`, `organization_id`, `goal`, `steps` (JSONB array of `AgentStepSchema`), `estimated_cost`, `estimated_tokens`, `estimated_duration`, `requires_approval`.
3. **`AgentStep`** (`agent_steps`):
   - Individual tool execution step within a session.
   - Fields: `id`, `session_id`, `organization_id`, `sequence`, `tool_name`, `tool_input` (JSONB), `reason` (concise rationale, strictly no chain-of-thought), `status`, `output_data` (JSONB), `error_message`, `cost_usd`, `tokens`, `duration_ms`, `requires_approval`.
4. **`AgentCheckpoint`** (`agent_checkpoints`):
   - Point-in-time snapshot persisted after every successful step.
   - Fields: `id`, `session_id`, `step_id`, `organization_id`, `status`, `tool_name`, `tool_input_hash` (SHA-256), `tool_result_reference`, `evidence_ids` (JSONB array), `state_snapshot` (JSONB).
5. **`ApprovalRequest`** (`approval_requests`):
   - Operator approval request for sensitive tool actions.
   - Fields: `id`, `session_id`, `step_id`, `organization_id`, `requested_by`, `approved_by`, `status` (`pending`, `approved`, `rejected`, `expired`), `reason`, `resolution_notes`, `created_at`, `resolved_at`.

---

## 3. Deterministic State Machine

The runtime governs session progression through a 10-state deterministic finite state machine (`AgentStateMachine`):

* **States**:
  1. `created`: Session initialized, pending plan.
  2. `planning`: Planner actively formulating sequence.
  3. `planned`: Plan generated, validated, and ready to execute.
  4. `awaiting_approval`: Paused waiting for human sign-off on a sensitive step.
  5. `executing`: Active step execution underway.
  6. `paused`: Temporarily halted by policy or manual intervention.
  7. `completed`: Successfully synthesized final grounded answer (Terminal).
  8. `failed`: Execution halted due to non-retryable error (Terminal).
  9. `cancelled`: Terminated by operator or job supervisor (Terminal).
  10. `budget_exceeded`: Halted due to token, cost, step, or time exhaustion (Terminal).

* **State Constraints**:
  - Direct transitions from terminal states (`completed`, `failed`, `cancelled`, `budget_exceeded`) back to `executing` or `planning` are strictly forbidden.
  - Resumption is only permissible from `paused` or `awaiting_approval` upon resolution.

---

## 4. Typed Tool Registry & Initial Tool Adapters

All tools are registered in the singleton `ToolRegistry` and implement the `AgentTool` protocol:

```python
class AgentTool(Protocol):
    name: str
    version: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    required_permission: str
    risk_level: ToolRiskLevel
    supports_preview: bool
    supports_approval: bool
    idempotent: bool

    async def validate(self, tool_input: dict[str, Any]) -> BaseModel: ...
    async def preview(self, validated_input: BaseModel, context: AgentExecutionContext) -> dict[str, Any]: ...
    async def execute(self, validated_input: BaseModel, context: AgentExecutionContext) -> ToolOutput: ...
```

### Initial Tools (Adapters over Existing Services)

1. **`analyst.query`** (`AnalystTool`):
   - Adapter over `AIAnalystService.ask()`.
   - Handles SQL, RAG, or Hybrid routing under existing tenant boundaries and grounding guarantees.
   - Risk Level: `READ` | Permission: `analytics.execute`.
2. **`sql.query`** (`SQLTool`):
   - Adapter over `SQLAgentService.execute_question()`.
   - Strictly enforces read-only AST checks, tenant schema filters, and timeout limits (TASK 17/22).
   - Risk Level: `READ` | Permission: `sql.execute`.
3. **`rag.retrieve`** (`RAGTool`):
   - Adapter over `RAGService.answer()`.
   - Employs hybrid retrieval, BM25 + dense vector scoring, reciprocal rank fusion (RRF), and cross-encoder reranking.
   - Risk Level: `READ` | Permission: `retrieval.execute`.
4. **`report.create`** (`ReportTool`):
   - Adapter over `ReportService.create_report_from_analysis()`.
   - Generates and versions structured executive documents from verified analysis runs.
   - Risk Level: `SAFE_WRITE` (Sensitive) | Permission: `reports.create`.
5. **`evaluation.run`** (`EvaluationTool`):
   - Adapter over `BenchmarkRunner.run_benchmark()` / `EvaluationService`.
   - Executes offline validation benchmarks without modifying golden datasets.
   - Risk Level: `READ` | Permission: `evaluation.run`.

---

## 5. Security & Policy Enforcement

### 8-Point Pre-Flight Security Gate

Before any tool is executed, `StepExecutor` enforces eight consecutive validations:

1. **Session State Validation**: Session must be in `executing` state.
2. **Approval Gate Check**: If tool requires approval (`requires_approval=True` or `risk_level in (SENSITIVE, HIGH_RISK)`), verifies that an approved `ApprovalRequest` exists for the current step.
3. **Loop & Duplicate Protection**: Computes SHA-256 hash of normalized input parameters. If identical tool & hash already completed and is marked idempotent, reuses cached output from `AgentCheckpoint`. If called repeatedly without completion, `LoopDetector` halts execution.
4. **Tool Authorization**:
   - Tool exists in `ToolRegistry`.
   - Tool is in `AgentProfile.allowed_tools` allowlist.
   - User possesses `tool.required_permission` in their RBAC set.
   - Tenant isolation verified (`context.organization_id`).
5. **Strict Schema Validation**: Pydantic input validation with `model_config = ConfigDict(extra="forbid")`. Arbitrary/unknown JSON keys are rejected immediately with `ToolInputValidationError`.
6. **Budget Pre-Flight Check**: Checks step count, tool call count, elapsed time against deadlines, token consumption, and cost in USD.
7. **Timeout Safeguards**: Tool execution is bounded by an async timeout (`step_timeout_seconds`), respecting parent deadline hierarchy: `tool_timeout < step_timeout < session_deadline < job_deadline`.
8. **Untrusted Data Boundary**: Tool outputs (SQL rows, RAG chunks, reports) are treated as **untrusted data**. Prompt injections embedded in tool responses are recorded as evidence/data and never executed as runtime instructions.

---

## 6. Multi-Dimensional Budgets

Budget enforcement (`AgentBudgetManager`) tracks consumption and rejects overages before initiating expensive operations:

* **Step Budget** (`StepBudget`): Maximum allowed execution steps (default: 10, configurable up to 20).
* **Tool Call Budget**: Maximum total tool calls per session (enforces bounded steps).
* **Time Budget** (`TimeBudget`): Wall-clock deadline enforcement in seconds.
* **Token Budget** (`TokenBudget`): Granular tracking of `input_tokens`, `output_tokens`, and `total_tokens` against configurable ceilings.
* **Cost Budget** (`CostBudget`): Dollar-denominated expenditure limit calculated from provider usage metadata.

---

## 7. Approval Gates & Human Sign-Off

* Operations altering state or publishing artifacts (`report.create`, `evaluation.run`) trigger an `awaiting_approval` pause.
* An `ApprovalRequest` is generated with `pending` status.
* Operators with `agents.approve` permission review the request via REST API:
  - `POST /api/v1/agents/sessions/{session_id}/approvals/{approval_id}/approve`
  - `POST /api/v1/agents/sessions/{session_id}/approvals/{approval_id}/reject`
* Once approved, the session transitions to `executing` upon resume.

---

## 8. Checkpoints & Crash Resumption

* After each successful step, `CheckpointManager` records an immutable `AgentCheckpoint`.
* The checkpoint stores:
  - SHA-256 hash of canonicalized input JSON.
  - IDs of all produced evidence items.
  - State snapshot and artifact references.
* Resuming a session (`POST /api/v1/agents/sessions/{session_id}/resume`) restores state from the latest valid checkpoint, validates tenant and permissions, and continues execution from the subsequent step without re-running idempotent completed steps.

---

## 9. Provenance & Evidence-Grounded Final Answer

* Every tool execution records structured `EvidenceItem` objects with source type (`sql`, `rag`, `report`, `eval`) and unique citation identifiers (`S1`, `R1`, etc.).
* Final answer synthesis enforces **Grounding**:
  - The agent synthesizes answers strictly from recorded tool evidence.
  - Claims lacking citation or verified evidence refs return `"Insufficient evidence"`.
  - If a non-critical tool fails (e.g. SQL offline but RAG succeeds), the response is flagged as `degraded=True`.

---

## 10. Background Worker Integration

* Agent execution integrates directly with the TASK 23 asynchronous job worker architecture (`AgentExecutionTask` in `app/jobs/tasks/agent.py`).
* Job type: `agent_execution`.
* Worker inherits `JobContext`, preserving `organization_id`, `trace_id`, `created_by`, and cancellation handles.

---

## 11. Observability & Telemetry

Metrics are registered in the existing Prometheus collector:

| Metric Name | Type | Description | Labels |
|---|---|---|---|
| `agent_sessions_total` | Counter | Total agent sessions created | `agent_type`, `status` |
| `agent_steps_total` | Counter | Total agent execution steps | `agent_type`, `status` |
| `agent_tool_calls_total` | Counter | Total tool invocations | `tool_name`, `status` |
| `agent_budget_exceeded_total` | Counter | Budget threshold violations | `budget_type` |
| `agent_duration_seconds` | Histogram | End-to-end execution duration | `agent_type` |
| `agent_approval_wait_seconds` | Histogram | Duration spent waiting for approval | `agent_type` |

Audit logs record all security and operational events (`agent.session_created`, `agent.tool_called`, `agent.approval_granted`, etc.) without exposing credentials, tokens, or private prompts.

---

## 12. REST API Specification

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `POST` | `/api/v1/agents/sessions` | `agents.create` | Create a new agent session and plan |
| `GET` | `/api/v1/agents/sessions/{id}` | `agents.read` | Retrieve session status and metadata |
| `GET` | `/api/v1/agents/sessions/{id}/plan` | `agents.read` | Retrieve structured execution plan |
| `GET` | `/api/v1/agents/sessions/{id}/steps` | `agents.read` | List ordered execution steps |
| `POST` | `/api/v1/agents/sessions/{id}/start` | `agents.execute` | Start executing session |
| `POST` | `/api/v1/agents/sessions/{id}/cancel` | `agents.cancel` | Cancel active or pending session |
| `POST` | `/api/v1/agents/sessions/{id}/resume` | `agents.resume` | Resume paused/approved session |
| `GET` | `/api/v1/agents/sessions/{id}/approvals` | `agents.read` | List approval requests for session |
| `POST` | `/api/v1/agents/sessions/{id}/approvals/{aid}/approve` | `agents.approve` | Approve sensitive step |
| `POST` | `/api/v1/agents/sessions/{id}/approvals/{aid}/reject` | `agents.approve` | Reject sensitive step |

---

## 13. Known Limitations & Out-of-Scope Elements

The following capabilities are deliberately **prohibited and not implemented**:

- **Web Search & Scrapers**: Zero external unauthenticated web retrieval.
- **Browser Automation**: No Selenium, Playwright, or headless browser tooling.
- **Arbitrary Code Execution**: No `os.system`, `subprocess`, `exec()`, or arbitrary Python sandbox.
- **Unbounded Loops**: No autonomous self-directed infinite loops; bounded strictly by `max_steps` and `AgentBudgetManager`.
- **Long-Term Memory**: No cross-session autonomous associative memory stores.
- **Unapproved External Side-Effects**: No external webhooks, email, or Slack messaging without operator authorization.
