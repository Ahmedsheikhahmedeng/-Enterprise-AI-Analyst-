"""Metric registry and deterministic composite quality scoring for continuous evaluation."""

from app.continuous_evaluation.domain.enums import MetricDirection
from app.continuous_evaluation.domain.models import MetricDefinition, QualityScore


class MetricRegistry:
    """Registry maintaining metadata, directionality, and weights for evaluation metrics."""

    DEFAULT_WEIGHTS: dict[str, float] = {
        "grounding": 0.20,
        "citation": 0.15,
        "retrieval": 0.15,
        "sql": 0.15,
        "semantic": 0.10,
        "graph": 0.10,
        "latency": 0.05,
        "cost": 0.05,
        "answer_quality": 0.05,
    }

    def __init__(self) -> None:
        self._metrics: dict[str, MetricDefinition] = {}
        self._weights: dict[str, float] = dict(self.DEFAULT_WEIGHTS)
        self._register_defaults()

    def _register_defaults(self) -> None:
        defaults = [
            # Grounding
            MetricDefinition(
                "groundedness", "grounding", MetricDirection.HIGHER_IS_BETTER, 0.90, 0.12
            ),
            MetricDefinition(
                "supported_claims_ratio", "grounding", MetricDirection.HIGHER_IS_BETTER, 0.85, 0.08
            ),
            # Citation
            MetricDefinition(
                "citation_precision", "citation", MetricDirection.HIGHER_IS_BETTER, 0.90, 0.08
            ),
            MetricDefinition(
                "citation_coverage", "citation", MetricDirection.HIGHER_IS_BETTER, 0.85, 0.07
            ),
            # Retrieval
            MetricDefinition("recall@5", "retrieval", MetricDirection.HIGHER_IS_BETTER, 0.85, 0.08),
            MetricDefinition("mrr", "retrieval", MetricDirection.HIGHER_IS_BETTER, 0.80, 0.04),
            MetricDefinition("ndcg@5", "retrieval", MetricDirection.HIGHER_IS_BETTER, 0.80, 0.03),
            # SQL
            MetricDefinition("sql_validity", "sql", MetricDirection.HIGHER_IS_BETTER, 0.98, 0.05),
            MetricDefinition("sql_safety", "sql", MetricDirection.HIGHER_IS_BETTER, 1.00, 0.05),
            MetricDefinition(
                "result_correctness", "sql", MetricDirection.HIGHER_IS_BETTER, 0.95, 0.05
            ),
            # Semantic
            MetricDefinition(
                "metric_resolution_accuracy",
                "semantic",
                MetricDirection.HIGHER_IS_BETTER,
                0.90,
                0.05,
            ),
            MetricDefinition(
                "dimension_resolution_accuracy",
                "semantic",
                MetricDirection.HIGHER_IS_BETTER,
                0.90,
                0.05,
            ),
            # Graph
            MetricDefinition(
                "path_precision", "graph", MetricDirection.HIGHER_IS_BETTER, 0.85, 0.05
            ),
            MetricDefinition(
                "multi_hop_correctness", "graph", MetricDirection.HIGHER_IS_BETTER, 0.85, 0.05
            ),
            # Agent & Orchestration
            MetricDefinition(
                "tool_selection_accuracy", "agent", MetricDirection.HIGHER_IS_BETTER, 0.90, 0.04
            ),
            MetricDefinition(
                "plan_correctness", "agent", MetricDirection.HIGHER_IS_BETTER, 0.90, 0.03
            ),
            MetricDefinition(
                "loop_avoidance", "agent", MetricDirection.HIGHER_IS_BETTER, 1.00, 0.03
            ),
            MetricDefinition(
                "route_accuracy", "orchestration", MetricDirection.HIGHER_IS_BETTER, 0.95, 0.05
            ),
            # Answer Quality
            MetricDefinition(
                "faithfulness", "answer_quality", MetricDirection.HIGHER_IS_BETTER, 0.90, 0.03
            ),
            MetricDefinition(
                "answer_relevance", "answer_quality", MetricDirection.HIGHER_IS_BETTER, 0.90, 0.02
            ),
            # Latency & Cost
            MetricDefinition(
                "latency_p95", "latency", MetricDirection.LOWER_IS_BETTER, 3000.0, 0.05
            ),
            MetricDefinition("cost_per_query", "cost", MetricDirection.LOWER_IS_BETTER, 0.05, 0.05),
        ]
        for d in defaults:
            self._metrics[d.metric_name] = d

    def register_metric(self, definition: MetricDefinition) -> None:
        """Registers or overrides a metric definition."""
        self._metrics[definition.metric_name] = definition

    def get_metric(self, name: str) -> MetricDefinition | None:
        """Retrieves registered definition for a given metric."""
        return self._metrics.get(name)

    def list_metrics(self, category: str | None = None) -> list[MetricDefinition]:
        """Lists all registered metrics optionally filtered by category."""
        if category:
            return [m for m in self._metrics.values() if m.category == category]
        return list(self._metrics.values())

    def update_category_weights(self, weights: dict[str, float]) -> dict[str, float]:
        """Updates and normalizes dimension weights."""
        if sum(weights.values()) <= 0:
            raise ValueError("Total weights must be strictly positive")
        for k, v in weights.items():
            if v < 0:
                raise ValueError("Weights must be non-negative")
            self._weights[k] = v
        total = sum(self._weights.values())
        self._weights = {k: v / total for k, v in self._weights.items()}
        return dict(self._weights)

    def get_category_weights(self) -> dict[str, float]:
        """Returns the current category weights."""
        return dict(self._weights)

    def compute_composite_score(
        self,
        metrics: dict[str, float],
        custom_weights: dict[str, float] | None = None,
    ) -> QualityScore:
        """Computes weighted QualityScore across categories without LLM involvement."""
        weights = dict(self._weights)
        if custom_weights:
            total = sum(custom_weights.values())
            if total > 0:
                weights.update({k: v / total for k, v in custom_weights.items()})

        # Calculate category scores
        cat_retrieval = metrics.get(
            "retrieval_recall@5", metrics.get("recall@5", metrics.get("retrieval_score", 1.0))
        )
        cat_grounding = metrics.get("groundedness", metrics.get("grounding_score", 1.0))
        cat_citation = metrics.get("citation_precision", metrics.get("citation_score", 1.0))
        cat_semantic = metrics.get(
            "semantic_accuracy",
            metrics.get("metric_resolution_accuracy", metrics.get("semantic_score", 1.0)),
        )
        cat_sql = metrics.get(
            "sql_accuracy", metrics.get("result_correctness", metrics.get("sql_score", 1.0))
        )
        cat_graph = metrics.get(
            "graph_grounding", metrics.get("multi_hop_correctness", metrics.get("graph_score", 1.0))
        )
        cat_agent = metrics.get("agent_score", metrics.get("plan_correctness", 1.0))

        # Latency normalized score [0, 1]: assuming <= 1000ms is 1.0, >= 5000ms is 0.0
        raw_latency = metrics.get("latency_p95", metrics.get("p95_ms", 1500.0))
        cat_latency = max(0.0, min(1.0, 1.0 - (max(0.0, raw_latency - 500.0) / 4500.0)))

        # Cost normalized score [0, 1]: assuming <= $0.01 is 1.0, >= $0.10 is 0.0
        raw_cost = metrics.get("cost_per_query", metrics.get("cost_per_query_usd", 0.02))
        cat_cost = max(0.0, min(1.0, 1.0 - (max(0.0, raw_cost - 0.005) / 0.095)))

        cat_answer_quality = metrics.get("faithfulness", metrics.get("answer_quality_score", 1.0))

        breakdown = {
            "grounding": round(float(cat_grounding), 4),
            "citation": round(float(cat_citation), 4),
            "retrieval": round(float(cat_retrieval), 4),
            "sql": round(float(cat_sql), 4),
            "semantic": round(float(cat_semantic), 4),
            "graph": round(float(cat_graph), 4),
            "latency": round(float(cat_latency), 4),
            "cost": round(float(cat_cost), 4),
            "answer_quality": round(float(cat_answer_quality), 4),
        }

        overall = (
            weights.get("grounding", 0.20) * cat_grounding
            + weights.get("citation", 0.15) * cat_citation
            + weights.get("retrieval", 0.15) * cat_retrieval
            + weights.get("sql", 0.15) * cat_sql
            + weights.get("semantic", 0.10) * cat_semantic
            + weights.get("graph", 0.10) * cat_graph
            + weights.get("latency", 0.05) * cat_latency
            + weights.get("cost", 0.05) * cat_cost
            + weights.get("answer_quality", 0.05) * cat_answer_quality
        )

        return QualityScore(
            retrieval_score=cat_retrieval,
            grounding_score=cat_grounding,
            citation_score=cat_citation,
            semantic_score=cat_semantic,
            sql_score=cat_sql,
            graph_score=cat_graph,
            agent_score=cat_agent,
            latency_score=cat_latency,
            cost_score=cat_cost,
            answer_quality_score=cat_answer_quality,
            overall_score=round(max(0.0, min(1.0, overall)), 4),
            weights=weights,
            breakdown=breakdown,
        )
