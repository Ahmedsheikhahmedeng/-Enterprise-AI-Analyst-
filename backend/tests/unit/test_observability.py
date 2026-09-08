"""Unit tests for Production Observability, Distributed Tracing & Monitoring components."""

import pytest

from app.observability.config import ObservabilityConfig
from app.observability.context import (
    ObservabilityContext,
    bind_observability_context,
    format_w3c_traceparent,
    get_current_context,
    parse_w3c_traceparent,
    reset_observability_context,
    sanitize_correlation_id,
)
from app.observability.exceptions import HighCardinalityViolationError
from app.observability.exporters.logging import LoggingExporter
from app.observability.exporters.otel import OpenTelemetryExporter
from app.observability.exporters.prometheus import PrometheusExporter
from app.observability.metrics import MetricsRegistry
from app.observability.models import SpanStatus
from app.observability.redaction import TelemetryRedactor
from app.observability.slo import SLOEvaluator
from app.observability.tracing import TraceManager, TraceSampler


class TestObservabilityContext:
    """Test suite for ContextVars propagation, W3C traceparent formatting and parsing."""

    def test_sanitize_correlation_id_valid(self) -> None:
        valid_id = "req-12345_abc.XYZ"
        assert sanitize_correlation_id(valid_id) == valid_id

    def test_sanitize_correlation_id_invalid_generates_uuid(self) -> None:
        malicious_id = "malicious<script>alert(1)</script>" + "A" * 100
        clean = sanitize_correlation_id(malicious_id)
        assert clean != malicious_id
        assert len(clean) == 32  # uuid4 hex length

    def test_w3c_traceparent_roundtrip(self) -> None:
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        span_id = "00f067aa0ba902b7"
        header = format_w3c_traceparent(trace_id, span_id, sampled=True)
        assert header == f"00-{trace_id}-{span_id}-01"

        parsed = parse_w3c_traceparent(header)
        assert parsed is not None
        p_trace, p_span, p_sampled = parsed
        assert p_trace == trace_id
        assert p_span == span_id
        assert p_sampled is True

    def test_context_binding_and_derivation(self) -> None:
        ctx = ObservabilityContext(
            request_id="req-1",
            trace_id="trace-1",
            span_id="span-root",
            route="/test",
        )
        token = bind_observability_context(ctx)
        try:
            current = get_current_context()
            assert current is not None
            assert current.request_id == "req-1"
            assert current.span_id == "span-root"

            child = current.with_span("span-child")
            assert child.parent_span_id == "span-root"
            assert child.span_id == "span-child"
            assert child.trace_id == "trace-1"
        finally:
            reset_observability_context(token)

        assert get_current_context() is None


class TestTelemetryRedactor:
    """Test suite ensuring zero sensitive data leaks into telemetry attributes or logs."""

    def setup_method(self) -> None:
        self.redactor = TelemetryRedactor()

    def test_redact_bearer_token(self) -> None:
        raw = "Error sending to upstream: Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz"
        redacted = self.redactor.redact_text(raw)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
        assert "Bearer [REDACTED]" in redacted

    def test_redact_database_url_password(self) -> None:
        raw = "Failed connecting to postgresql://admin:SuperSecretPass123@db.internal:5432/production_db"
        redacted = self.redactor.redact_text(raw)
        assert "SuperSecretPass123" not in redacted
        assert "postgresql://admin:[REDACTED]@db.internal:5432/production_db" in redacted

    def test_redact_nested_dict_sensitive_keys(self) -> None:
        payload = {
            "user_email": "analyst@enterprise.com",
            "api_key": "sk-1234567890abcdef",
            "db_password": "p@ssword!",
            "nested": {
                "auth_token": "secret-token-val",
                "normal_val": 42,
            },
        }
        clean = self.redactor.redact_data(payload)
        assert clean["api_key"] == "[REDACTED]"
        assert clean["db_password"] == "[REDACTED]"
        assert clean["nested"]["auth_token"] == "[REDACTED]"
        assert clean["nested"]["normal_val"] == 42


class TestMetricsRegistryAndCardinality:
    """Test suite for high-cardinality protection, Counters, Gauges, and Histograms."""

    def setup_method(self) -> None:
        self.registry = MetricsRegistry()

    def test_forbidden_labels_raise_high_cardinality_error(self) -> None:
        with pytest.raises(HighCardinalityViolationError):
            self.registry.increment("test_counter", labels={"user_id": "usr-123"})

        with pytest.raises(HighCardinalityViolationError):
            self.registry.increment("test_counter", labels={"request_id": "req-123"})

        with pytest.raises(HighCardinalityViolationError):
            self.registry.increment("test_counter", labels={"query": "SELECT * FROM sales"})

        with pytest.raises(HighCardinalityViolationError):
            self.registry.increment("test_counter", labels={"prompt": "Summarize this data"})

    def test_counter_and_gauge_operations(self) -> None:
        self.registry.increment(
            "requests_total", value=1.0, labels={"route": "/ask", "status": "ok"}
        )
        self.registry.increment(
            "requests_total", value=2.0, labels={"route": "/ask", "status": "ok"}
        )
        val = self.registry.get_counter_value(
            "requests_total", labels={"route": "/ask", "status": "ok"}
        )
        assert val == 3.0

        self.registry.gauge("in_flight", value=5.0, labels={"method": "POST"})
        assert self.registry.get_gauge_value("in_flight", labels={"method": "POST"}) == 5.0

    def test_histogram_observations_and_buckets(self) -> None:
        self.registry.observe("latency_ms", value=15.0, labels={"route": "/ask"})
        self.registry.observe("latency_ms", value=120.0, labels={"route": "/ask"})
        self.registry.observe("latency_ms", value=450.0, labels={"route": "/ask"})

        data = self.registry.get_all_metrics()
        hist = data["histograms"]["latency_ms"][0]
        assert hist["count"] == 3
        assert hist["sum"] == 585.0


class TestDistributedTracing:
    """Test suite for hierarchical spans, async/sync context managers, and sampling."""

    def setup_method(self) -> None:
        self.trace_manager = TraceManager()
        self.trace_manager.clear()

    @pytest.mark.asyncio
    async def test_async_nested_spans(self) -> None:
        async with self.trace_manager.start_span_async("parent.span") as parent:
            assert parent.name == "parent.span"
            async with self.trace_manager.start_span_async("child.span") as child:
                assert child.parent_span_id == parent.span_id
                assert child.trace_id == parent.trace_id

        spans = self.trace_manager.get_trace_spans(parent.trace_id)
        assert len(spans) == 2
        span_names = [s.name for s in spans]
        assert "child.span" in span_names
        assert "parent.span" in span_names

    def test_sync_span_exception_recording(self) -> None:
        with (
            pytest.raises(ValueError, match="synthetic test error"),
            self.trace_manager.start_span_sync("failing.span") as span,
        ):
            trace_id = span.trace_id
            raise ValueError("synthetic test error")

        spans = self.trace_manager.get_trace_spans(trace_id)
        assert len(spans) == 1
        assert spans[0].status == SpanStatus.ERROR
        assert spans[0].attributes["error.type"] == "ValueError"
        assert spans[0].error_message is not None
        assert "synthetic test error" in spans[0].error_message

    def test_trace_sampler_error_always(self) -> None:
        cfg = ObservabilityConfig(trace_sample_rate=0.0, enable_error_always_sampling=True)
        sampler = TraceSampler(cfg)
        assert sampler.should_sample(is_error=False) is False
        assert sampler.should_sample(is_error=True) is True


class TestSLOAndErrorBudget:
    """Test suite for Service Level Objectives accounting and error budgets."""

    def setup_method(self) -> None:
        self.registry = MetricsRegistry()
        self.evaluator = SLOEvaluator(self.registry)

    def test_error_budget_greater_than_target(self) -> None:
        # Target 99% (0.99), Observed 99.5% (0.995)
        # Allowed bad ratio = 0.01. Actual bad ratio = 0.005
        # Remaining budget = 1.0 - (0.005 / 0.01) = 0.5 (50% remaining)
        budget = self.evaluator.calculate_error_budget(target=0.99, observed=0.995, comparison=">=")
        assert budget.status == "MET"
        assert pytest.approx(budget.budget_remaining, 0.01) == 0.5

    def test_error_budget_breached(self) -> None:
        # Target 99% (0.99), Observed 98% (0.98)
        # Allowed bad ratio = 0.01. Actual bad ratio = 0.02
        # Remaining budget = 1.0 - (0.02 / 0.01) = -1.0 (breached)
        budget = self.evaluator.calculate_error_budget(target=0.99, observed=0.98, comparison=">=")
        assert budget.status == "BREACHED"
        assert budget.budget_remaining < 0.0

    def test_slo_evaluation_with_recorded_metrics(self) -> None:
        # 100% success -> MET (100% budget remaining)
        self.registry.increment(
            "enterprise_ai_analyst_requests_total", value=100.0, labels={"route": "hybrid"}
        )
        self.registry.increment(
            "enterprise_ai_analyst_success_total", value=100.0, labels={"route": "hybrid"}
        )

        results = self.evaluator.evaluate_slos()
        analyst_avail = next(r for r in results if r.name == "analyst_availability")
        assert analyst_avail.observed == 1.0
        assert analyst_avail.status == "MET"


class TestExporters:
    """Test suite for Logging, Prometheus exposition, and OpenTelemetry abstractions."""

    def setup_method(self) -> None:
        self.registry = MetricsRegistry()
        self.registry.increment(
            "http_requests_total",
            value=42.0,
            labels={"method": "GET", "status_code": "200"},
            description="Total HTTP requests processed",
        )
        self.registry.observe(
            "http_request_duration_ms",
            value=25.0,
            labels={"method": "GET"},
            description="HTTP duration histogram",
        )

    def test_prometheus_exposition_format(self) -> None:
        exporter = PrometheusExporter(self.registry)
        output = exporter.export()
        assert "# TYPE http_requests_total counter" in output
        assert 'http_requests_total{method="GET",status_code="200"} 42.0' in output
        assert "# TYPE http_request_duration_ms histogram" in output

    def test_logging_exporter(self) -> None:
        exporter = LoggingExporter(self.registry)
        snapshot = exporter.export()
        assert isinstance(snapshot, dict)
        assert len(snapshot["counters"]) > 0

    def test_opentelemetry_exporter(self) -> None:
        exporter = OpenTelemetryExporter(self.registry)
        exported = exporter.export()
        assert "resourceMetrics" in exported
        scope_metrics = exported["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]
        metric_names = [m["name"] for m in scope_metrics]
        assert "http_requests_total" in metric_names
