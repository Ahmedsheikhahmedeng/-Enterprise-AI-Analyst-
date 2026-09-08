"""Unit tests for Semantic Catalog, Business Glossary, Metrics, and Normalization."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.semantic import BusinessTerm, SemanticMetric
from app.semantic.application.conflict_detector import SemanticConflictDetector
from app.semantic.application.metric_compiler import MetricCompiler
from app.semantic.application.normalizer import SemanticTextNormalizer
from app.semantic.domain.errors import InvalidMetricFormulaError
from app.semantic.infrastructure.repository import SemanticRepository


def test_multilingual_normalizer_arabic() -> None:
    """Verify Arabic diacritic stripping and alef/teh-marbuta normalization."""
    raw = "إِجْمَالِيُّ الإِيْرَادَاتِ المُكْتَمِلَةِ"
    norm = SemanticTextNormalizer.normalize(raw)
    assert "اجمالي" in norm
    assert "الايرادات" in norm
    assert "المكتمله" in norm

    lang = SemanticTextNormalizer.detect_language(raw)
    assert lang == "ar"


def test_multilingual_normalizer_turkish() -> None:
    """Verify Turkish dotted/dotless I handling and language detection."""
    raw = "İSTANBUL SATIŞ GELİRİ"
    norm = SemanticTextNormalizer.normalize(raw)
    assert "istanbul" in norm
    assert "satış" in norm
    assert "geliri" in norm

    lang = SemanticTextNormalizer.detect_language(raw)
    assert lang == "tr"


def test_multilingual_normalizer_english_and_punctuation() -> None:
    """Verify English casing and punctuation removal."""
    raw = "Total Revenue ($USD) - 2026!!!"
    norm = SemanticTextNormalizer.normalize(raw)
    assert norm == "total revenue usd 2026"


def test_metric_compiler_safe_expression() -> None:
    """Verify compilation of valid arithmetic and aggregation expressions."""
    sql = MetricCompiler.compile_metric(
        metric_name="total_rev",
        formula="SUM(total_amount)",
        aggregation="SUM",
        table_name="orders",
        column_mapping={"total_amount": "total_amount"},
        filters=["orders.status = 'completed'"],
    )
    assert (
        sql
        == 'SELECT SUM("total_amount") AS "total_rev" FROM "orders" WHERE orders.status = \'completed\''
    )


def test_metric_compiler_rejects_sql_injection() -> None:
    """Verify MetricCompiler strictly rejects semicolons and DDL/DML injection."""
    with pytest.raises(InvalidMetricFormulaError, match="prohibited SQL"):
        MetricCompiler.compile_metric(
            metric_name="malicious",
            formula="SUM(amount); DROP TABLE orders; --",
            aggregation="SUM",
            table_name="orders",
            column_mapping={},
        )

    with pytest.raises(InvalidMetricFormulaError, match="Unbalanced"):
        MetricCompiler.compile_metric(
            metric_name="unbalanced",
            formula="SUM(amount",
            aggregation="SUM",
            table_name="orders",
            column_mapping={},
        )


@pytest.mark.asyncio
async def test_glossary_term_versioning() -> None:
    """Verify updating a business term definition creates an immutable version."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    term_id = uuid.uuid4()

    mock_session = AsyncMock()
    repo = SemanticRepository(mock_session)

    # Initial term
    existing_term = BusinessTerm(
        id=term_id,
        organization_id=org_id,
        name="Revenue",
        normalized_name="revenue",
        definition="Initial definition",
        version=1,
        status="draft",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo.get_term = AsyncMock(return_value=existing_term)  # type: ignore

    updated = await repo.update_term(
        term_id=term_id,
        organization_id=org_id,
        definition="Updated enterprise revenue definition",
        updated_by=user_id,
    )

    assert updated.version == 2
    assert updated.definition == "Updated enterprise revenue definition"
    assert mock_session.add.called


@pytest.mark.asyncio
async def test_conflict_detection_different_formulas() -> None:
    """Verify SemanticConflictDetector discovers contradictory formulas with the same concept name."""
    org_id = uuid.uuid4()
    mock_session = AsyncMock()

    m1 = SemanticMetric(
        id=uuid.uuid4(),
        organization_id=org_id,
        name="Gross Margin",
        normalized_name="gross margin",
        definition="Sales minus COGS",
        formula="SUM(revenue - cogs)",
        aggregation="SUM",
        status="published",
    )
    m2 = SemanticMetric(
        id=uuid.uuid4(),
        organization_id=org_id,
        name="Gross Margin",
        normalized_name="gross margin",
        definition="Revenue ratio",
        formula="AVG(margin_pct)",
        aggregation="AVG",
        status="published",
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [m1, m2]
    mock_session.execute.return_value = mock_result

    detector = SemanticConflictDetector(mock_session)
    detector.repo.create_conflict = AsyncMock()  # type: ignore

    await detector.detect_metric_conflicts(org_id)
    assert detector.repo.create_conflict.called
