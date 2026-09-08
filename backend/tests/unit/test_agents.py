"""Unit tests for Enterprise Agent Runtime core components."""

import uuid

import pytest
from pydantic import ValidationError

from app.agents.budgets import AgentBudgetManager, StepBudget, TimeBudget, TokenBudget
from app.agents.checkpoints import CheckpointManager
from app.agents.exceptions import (
    AgentStateTransitionError,
    BudgetExceededError,
    LoopDetectedError,
    PlanValidationError,
    ToolAuthorizationError,
    ToolExecutionError,
    ToolNotFoundError,
)
from app.agents.executor import LoopDetector
from app.agents.plan import AgentPlanValidator
from app.agents.policies import AgentToolPolicy
from app.agents.profiles import get_agent_profile
from app.agents.registry import ToolRegistry, get_tool_registry
from app.agents.schemas import (
    AgentStatus,
    AgentStepSchema,
    AgentType,
    ToolRiskLevel,
)
from app.agents.state import AgentStateMachine
from app.agents.tools.analyst import AnalystTool
from app.agents.tools.schemas import (
    AnalystQueryInput,
    EvaluationRunInput,
    RAGRetrieveInput,
    ReportCreateInput,
    SQLQueryInput,
)


def test_state_machine_valid_transitions() -> None:
    AgentStateMachine.validate_transition(AgentStatus.CREATED, AgentStatus.PLANNING)
    AgentStateMachine.validate_transition(AgentStatus.PLANNING, AgentStatus.PLANNED)
    AgentStateMachine.validate_transition(AgentStatus.PLANNED, AgentStatus.EXECUTING)
    AgentStateMachine.validate_transition(AgentStatus.EXECUTING, AgentStatus.COMPLETED)
    AgentStateMachine.validate_transition(AgentStatus.EXECUTING, AgentStatus.AWAITING_APPROVAL)
    AgentStateMachine.validate_transition(AgentStatus.AWAITING_APPROVAL, AgentStatus.EXECUTING)
    AgentStateMachine.validate_transition(AgentStatus.EXECUTING, AgentStatus.PAUSED)
    AgentStateMachine.validate_transition(AgentStatus.PAUSED, AgentStatus.EXECUTING)


def test_state_machine_invalid_terminal_transitions() -> None:
    with pytest.raises(AgentStateTransitionError):
        AgentStateMachine.validate_transition(AgentStatus.COMPLETED, AgentStatus.EXECUTING)

    with pytest.raises(AgentStateTransitionError):
        AgentStateMachine.validate_transition(AgentStatus.CANCELLED, AgentStatus.EXECUTING)

    with pytest.raises(AgentStateTransitionError):
        AgentStateMachine.validate_transition(AgentStatus.BUDGET_EXCEEDED, AgentStatus.EXECUTING)

    assert AgentStateMachine.is_terminal(AgentStatus.COMPLETED)
    assert AgentStateMachine.is_terminal(AgentStatus.CANCELLED)
    assert AgentStateMachine.is_terminal(AgentStatus.BUDGET_EXCEEDED)
    assert not AgentStateMachine.is_terminal(AgentStatus.EXECUTING)


def test_budget_manager_step_and_tool_caps() -> None:
    step_budget = StepBudget(max_steps=2, max_tool_calls=2)
    step_budget.check_step()
    step_budget.check_tool_call()

    step_budget.consume_step()
    step_budget.consume_tool_call()
    assert step_budget.executed_steps == 1

    step_budget.consume_step()
    with pytest.raises(BudgetExceededError):
        step_budget.check_step()

    with pytest.raises(BudgetExceededError):
        step_budget.consume_step()


def test_budget_manager_token_and_cost_caps() -> None:
    mgr = AgentBudgetManager(max_tokens=1000, max_cost_usd=0.05)
    mgr.token_budget.consume(500)
    mgr.cost_budget.consume(0.02)
    mgr.pre_flight_check()

    with pytest.raises(BudgetExceededError):
        mgr.token_budget.consume(600)

    with pytest.raises(BudgetExceededError):
        mgr.cost_budget.consume(0.05)


def test_token_budget_granular_tracking() -> None:
    tb = TokenBudget(max_tokens=1000, max_input_tokens=800, max_output_tokens=200)
    tb.consume(0, input_tokens=300, output_tokens=100)
    assert tb.consumed_input_tokens == 300
    assert tb.consumed_output_tokens == 100
    assert tb.consumed_total_tokens == 400

    # Input cap exceed
    with pytest.raises(BudgetExceededError):
        tb.consume(0, input_tokens=600, output_tokens=10)


def test_time_budget() -> None:
    tb = TimeBudget(max_duration_seconds=0.01)
    import time

    time.sleep(0.02)
    with pytest.raises(BudgetExceededError):
        tb.check()


def test_loop_detector() -> None:
    detector = LoopDetector(threshold=3)
    detector.record_and_check("sql.query", "hash_abc")
    detector.record_and_check("sql.query", "hash_abc")
    with pytest.raises(LoopDetectedError):
        detector.record_and_check("sql.query", "hash_abc")


def test_plan_validator() -> None:
    validator = AgentPlanValidator(registered_tools={"sql.query", "rag.retrieve"}, max_steps=5)

    valid_steps = [
        AgentStepSchema(
            step_id=str(uuid.uuid4()),
            sequence=1,
            tool_name="sql.query",
            tool_input={"query": "test"},
            reason="Fetch revenue metrics before report generation.",
        )
    ]
    validator.validate(valid_steps)

    # Empty plan
    with pytest.raises(PlanValidationError):
        validator.validate([])

    # Unknown tool
    invalid_tool = [
        AgentStepSchema(
            step_id=str(uuid.uuid4()),
            sequence=1,
            tool_name="unknown.tool",
            tool_input={},
            reason="Illegal action",
        )
    ]
    with pytest.raises(PlanValidationError):
        validator.validate(invalid_tool)

    # Missing rationale
    no_reason = [
        AgentStepSchema(
            step_id=str(uuid.uuid4()),
            sequence=1,
            tool_name="sql.query",
            tool_input={},
            reason="",
        )
    ]
    with pytest.raises(PlanValidationError):
        validator.validate(no_reason)

    # Verbose rationale (CoT guard enforced at schema level)
    with pytest.raises(ValidationError):
        AgentStepSchema(
            step_id=str(uuid.uuid4()),
            sequence=1,
            tool_name="sql.query",
            tool_input={},
            reason="A" * 600,
        )


def test_tool_registry() -> None:
    registry = ToolRegistry()
    analyst_tool = AnalystTool()
    registry.register(analyst_tool)

    assert registry.get("analyst.query").name == "analyst.query"
    assert "analyst.query" in registry.tool_names()
    assert len(registry.list_tools()) == 1

    with pytest.raises(ToolNotFoundError):
        registry.get("nonexistent.tool")


def test_default_tool_registry_contains_all_initial_tools() -> None:
    reg = get_tool_registry()
    names = reg.tool_names()
    assert "analyst.query" in names
    assert "sql.query" in names
    assert "rag.retrieve" in names
    assert "report.create" in names
    assert "evaluation.run" in names


def test_tool_policy_authorization() -> None:
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    policy = AgentToolPolicy(allowed_tools={"analyst.query", "sql.query"})

    # Valid
    policy.authorize_tool(
        tool_name="sql.query",
        tool_risk_level=ToolRiskLevel.READ,
        required_permission="analytics.execute",
        user_permissions={"analytics.execute"},
        organization_id=org_a,
        target_org_id=org_a,
    )

    # Profile allowlist mismatch
    with pytest.raises(ToolAuthorizationError):
        policy.authorize_tool(
            tool_name="rag.retrieve",
            tool_risk_level=ToolRiskLevel.READ,
            required_permission="ai.chat",
            user_permissions={"ai.chat"},
            organization_id=org_a,
        )

    # Permission mismatch
    with pytest.raises(ToolAuthorizationError):
        policy.authorize_tool(
            tool_name="sql.query",
            tool_risk_level=ToolRiskLevel.READ,
            required_permission="analytics.execute",
            user_permissions={"viewer.read"},
            organization_id=org_a,
        )

    # Cross-tenant violation
    with pytest.raises(ToolAuthorizationError):
        policy.authorize_tool(
            tool_name="sql.query",
            tool_risk_level=ToolRiskLevel.READ,
            required_permission="analytics.execute",
            user_permissions={"analytics.execute"},
            organization_id=org_a,
            target_org_id=org_b,
        )

    # High risk rejection
    with pytest.raises(ToolAuthorizationError):
        policy.authorize_tool(
            tool_name="sql.query",
            tool_risk_level=ToolRiskLevel.HIGH_RISK,
            required_permission="analytics.execute",
            user_permissions={"analytics.execute"},
            organization_id=org_a,
        )


def test_input_schema_validation() -> None:
    # Valid Analyst
    inp = AnalystQueryInput(query="Show me Q3 revenue")
    assert inp.query == "Show me Q3 revenue"

    # Forbid extra fields on all tools
    with pytest.raises(ValidationError):
        AnalystQueryInput.model_validate({"query": "Valid", "extra_param": "forbidden"})

    with pytest.raises(ValidationError):
        SQLQueryInput.model_validate(
            {"question": "Q?", "datasource_id": str(uuid.uuid4()), "extra": 1}
        )

    with pytest.raises(ValidationError):
        RAGRetrieveInput.model_validate({"query": "Q?", "extra": 1})

    with pytest.raises(ValidationError):
        ReportCreateInput.model_validate(
            {
                "analysis_run_id": str(uuid.uuid4()),
                "title": "Title",
                "malicious": "injected",
            }
        )

    with pytest.raises(ValidationError):
        EvaluationRunInput.model_validate({"dataset_id": str(uuid.uuid4()), "extra": "field"})


def test_checkpoint_input_hash() -> None:
    h1 = CheckpointManager.compute_input_hash({"a": 1, "b": "hello"})
    h2 = CheckpointManager.compute_input_hash({"b": "hello", "a": 1})
    assert h1 == h2


def test_agent_profile_defaults() -> None:
    analyst_p = get_agent_profile(AgentType.ANALYST_AGENT)
    assert analyst_p.name == "analyst_agent"
    assert "analyst.query" in analyst_p.allowed_tools
    assert analyst_p.max_steps == 20
    assert analyst_p.max_cost == 2.0
    assert analyst_p.requires_approval

    research_p = get_agent_profile(AgentType.RESEARCH_AGENT)
    assert "web_search" not in research_p.allowed_tools
    assert research_p.allowed_tools == {
        "rag.retrieve",
        "sql.query",
        "datasource.list",
        "datasource.schema",
        "datasource.preview",
        "datasource.query",
        "dataset.list",
        "dataset.get",
        "dataset.profile",
        "dataset.versions",
        "dataset.quality",
        "semantic.search",
        "semantic.get_term",
        "semantic.resolve_metric",
        "semantic.resolve_dimension",
        "semantic.get_entity",
        "semantic.get_relationships",
        "semantic.get_query_plan",
        "graph.search",
        "graph.get_node",
        "graph.get_neighbors",
        "graph.find_path",
        "graph.query",
        "graph.get_lineage",
    }


def test_retry_classification() -> None:
    err_retryable = ToolExecutionError("sql.query", "connection timeout", retryable=True)
    assert err_retryable.retryable

    err_fatal = ToolExecutionError("sql.query", "unauthorized access", retryable=False)
    assert not err_fatal.retryable
