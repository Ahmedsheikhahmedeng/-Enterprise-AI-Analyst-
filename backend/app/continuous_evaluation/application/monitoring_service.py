"""Continuous production quality monitoring, privacy-safe sampling, and human evaluation tracking."""

import re
import uuid
from datetime import UTC, datetime, timedelta

from app.continuous_evaluation.domain.enums import EvaluationSource, SamplingStrategy
from app.continuous_evaluation.domain.models import (
    HumanEvaluation,
    JudgeMonitoringReport,
    ProductionSample,
)
from app.continuous_evaluation.domain.protocols import ContinuousEvaluationRepositoryProtocol
from app.observability.instrumentation.continuous_evaluation import (
    ContinuousEvaluationInstrumentation,
)


class PrivacySanitizer:
    """Detects and redacts sensitive PII and secrets prior to evaluation storage."""

    PII_PATTERNS = [
        # Email addresses
        (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[REDACTED_EMAIL]"),
        # Credit card numbers
        (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[REDACTED_CC]"),
        # Social security numbers
        (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
        # Bearer tokens / API keys
        (
            re.compile(
                r"(?:bearer\s+|api_key[\s:=]+['\"]?)[a-zA-Z0-9_\-\.]{16,}['\"]?", re.IGNORECASE
            ),
            "[REDACTED_SECRET]",
        ),
        # Passwords in query
        (
            re.compile(r"(?:password|passwd)[\s:=]+[^\s&]+", re.IGNORECASE),
            "password=[REDACTED_CRED]",
        ),
    ]

    @classmethod
    def sanitize(cls, text: str) -> tuple[str, bool]:
        """Scrubs sensitive strings and returns sanitized text with redaction flag."""
        redacted = False
        result = text
        for pattern, replacement in cls.PII_PATTERNS:
            if pattern.search(result):
                result = pattern.sub(replacement, result)
                redacted = True
        return result, redacted


class MonitoringService:
    """Orchestrates production workload sampling, privacy sanitization, and human annotations."""

    def __init__(
        self,
        repository: ContinuousEvaluationRepositoryProtocol,
        instrumentation: ContinuousEvaluationInstrumentation | None = None,
        default_retention_days: int = 30,
    ) -> None:
        self.repository = repository
        self.instrumentation = instrumentation
        self.default_retention_days = default_retention_days

    async def capture_production_sample(
        self,
        *,
        organization_id: uuid.UUID,
        query: str,
        response: str,
        strategy: SamplingStrategy = SamplingStrategy.RANDOM,
        data_sensitivity: str = "INTERNAL",
        retention_days: int | None = None,
        source_execution_id: str | None = None,
    ) -> ProductionSample:
        """Sanitizes PII and securely persists production execution sample with explicit retention limits."""
        # Sanitize query and response
        clean_query, redacted_q = PrivacySanitizer.sanitize(query)
        clean_response, redacted_r = PrivacySanitizer.sanitize(response)
        was_redacted = redacted_q or redacted_r

        days = retention_days if retention_days is not None else self.default_retention_days
        expires_at = datetime.now(UTC) + timedelta(days=days)

        sample = ProductionSample(
            id=uuid.uuid4(),
            organization_id=organization_id,
            source_execution_id=source_execution_id,
            query=clean_query,
            response=clean_response,
            sampling_strategy=strategy,
            data_sensitivity=data_sensitivity,
            redacted=was_redacted,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
        )

        persisted = await self.repository.record_production_sample(sample)
        return persisted

    async def purge_expired_samples(self) -> int:
        """Deletes production evaluation samples past their retention threshold."""
        return await self.repository.delete_expired_samples()

    async def record_human_review(
        self,
        *,
        organization_id: uuid.UUID,
        evaluator_id: uuid.UUID,
        accuracy_score: float,
        helpfulness_score: float,
        grounding_score: float,
        clarity_score: float,
        sample_id: uuid.UUID | None = None,
        case_result_id: uuid.UUID | None = None,
        comments: str | None = None,
    ) -> HumanEvaluation:
        """Records qualitative review from human annotator without altering the underlying raw execution."""
        # Score validation (1.0 to 5.0)
        for name, sc in [
            ("accuracy_score", accuracy_score),
            ("helpfulness_score", helpfulness_score),
            ("grounding_score", grounding_score),
            ("clarity_score", clarity_score),
        ]:
            if not (1.0 <= sc <= 5.0):
                raise ValueError(f"{name} must be strictly between 1.0 and 5.0, got {sc}")

        human_eval = HumanEvaluation(
            id=uuid.uuid4(),
            organization_id=organization_id,
            evaluator_id=evaluator_id,
            sample_id=sample_id,
            case_result_id=case_result_id,
            accuracy_score=accuracy_score,
            helpfulness_score=helpfulness_score,
            grounding_score=grounding_score,
            clarity_score=clarity_score,
            comments=comments,
            created_at=datetime.now(UTC),
            evaluation_source=EvaluationSource.HUMAN,
        )

        persisted = await self.repository.record_human_evaluation(human_eval)
        return persisted

    def analyze_judge_bias(
        self,
        human_evaluations: list[HumanEvaluation],
        llm_judge_scores: list[float],  # normalized [0.0, 1.0]
    ) -> JudgeMonitoringReport:
        """Quantifies alignment and drift between human ground truth and LLM Judge evaluations."""
        n = min(len(human_evaluations), len(llm_judge_scores))
        if n == 0:
            return JudgeMonitoringReport(
                total_samples=0,
                agreement_rate=1.0,
                drift_score=0.0,
                disagreement_count=0,
                mean_judge_score=0.0,
                mean_human_score=0.0,
            )

        human_norm_scores = [h.normalized_score() for h in human_evaluations[:n]]
        judge_norm_scores = llm_judge_scores[:n]

        disagreements = 0
        score_diffs = []

        for h_sc, j_sc in zip(human_norm_scores, judge_norm_scores, strict=False):
            diff = abs(h_sc - j_sc)
            score_diffs.append(diff)
            # A difference > 0.25 on a 0-1 scale constitutes significant disagreement
            if diff > 0.25:
                disagreements += 1

        agreement_rate = 1.0 - (disagreements / n)
        drift_score = sum(score_diffs) / n

        mean_judge = sum(judge_norm_scores) / n
        mean_human = sum(human_norm_scores) / n

        if self.instrumentation and disagreements > 0:
            self.instrumentation.record_judge_disagreement("llm_judge_vs_human")

        return JudgeMonitoringReport(
            total_samples=n,
            agreement_rate=agreement_rate,
            drift_score=drift_score,
            disagreement_count=disagreements,
            mean_judge_score=mean_judge,
            mean_human_score=mean_human,
        )
