"""Unit tests for Dataset Normalization, Profiling, Quality, Deduplication, Lineage, and RAG Adapter."""

import uuid
from typing import Any

from app.ingestion.application.deduplication_service import DeduplicationService
from app.ingestion.application.lineage_service import LineageService
from app.ingestion.application.normalization_service import NormalizationService
from app.ingestion.application.profiling_service import ProfilingService
from app.ingestion.application.rag_adapter import DatasetRAGAdapter
from app.ingestion.domain.enums import (
    ColumnDataType,
    DataClassification,
    DeduplicationStrategy,
    IngestionMode,
    PIIClassification,
)
from app.ingestion.infrastructure.profiler.pii_detector import PIIDetector


def test_identifier_normalization_multilingual() -> None:
    """Verify identifier normalization across Arabic, Turkish, English, and reserved keywords."""
    norm = NormalizationService()

    # English standard & whitespace
    assert norm.normalize_identifier("Customer Name") == "Customer_Name"
    assert norm.normalize_identifier("  total_amount   ") == "total_amount"
    assert norm.normalize_identifier("user-id!@#$") == "user_id"

    # Reserved SQL keywords
    assert norm.normalize_identifier("select") == "select_col"
    assert norm.normalize_identifier("WHERE") == "WHERE_col"
    assert norm.normalize_identifier("order") == "order_col"

    # Leading numbers
    assert norm.normalize_identifier("123_revenue") == "col_123_revenue"

    # Arabic identifiers
    arabic_res = norm.normalize_identifier("اسم العميل")
    assert arabic_res == "اسم_العميل"
    assert norm.normalize_identifier("قيمة_الفاتورة") == "قيمة_الفاتورة"

    # Turkish identifiers
    assert norm.normalize_identifier("müşteri_adı") == "müşteri_adı"
    assert norm.normalize_identifier("toplam_tutar") == "toplam_tutar"

    # Empty fallback
    assert norm.normalize_identifier("") == "unnamed_column"
    assert norm.normalize_identifier("   ") == "unnamed_column"


def test_schema_normalization_duplicate_disambiguation() -> None:
    """Verify duplicate column names are deterministically disambiguated."""
    norm = NormalizationService()
    raw_headers = ["revenue", "cost", "revenue", "REVENUE", "cost"]
    defs = norm.normalize_schema(raw_headers)

    assert len(defs) == 5
    norm_names = [d.normalized_name for d in defs]
    assert norm_names[0] == "revenue"
    assert norm_names[1] == "cost"
    assert norm_names[2] == "revenue_1"
    assert norm_names[3] == "REVENUE_2"
    assert norm_names[4] == "cost_1"

    # Verify original names preserved
    assert defs[0].original_name == "revenue"
    assert defs[3].original_name == "REVENUE"


def test_pii_detector_patterns() -> None:
    """Verify deterministic regex matching for emails, phones, credit cards, and IDs."""
    detector = PIIDetector()

    # Email
    emails = ["john.doe@enterprise.corp", "user123@domain.org", "invalid-email"]
    assert detector.detect_column_pii("contact", emails) == PIIClassification.EMAIL

    # Credit card
    cards = ["4532-1234-5678-9012", "5412 3456 7890 1234"]
    assert detector.detect_column_pii("payment", cards) == PIIClassification.CREDIT_CARD

    # Phone
    phones = ["+1 (555) 234-5678", "0532 123 4567"]
    assert detector.detect_column_pii("telephone", phones) == PIIClassification.PHONE

    # National ID
    ids = ["123-45-6789", "12345678901"]
    assert detector.detect_column_pii("ssn", ids) == PIIClassification.NATIONAL_ID

    # Non-PII
    cities = ["New York", "London", "Tokyo", "Istanbul"]
    assert detector.detect_column_pii("city", cities) == PIIClassification.NONE


def test_dataset_classification_derivation() -> None:
    """Verify dataset sensitivity classification derived from column PII types."""
    detector = PIIDetector()

    # Sensitive if credit card or national id present
    assert (
        detector.determine_dataset_classification(
            {"id": PIIClassification.NONE, "card": PIIClassification.CREDIT_CARD}
        )
        == DataClassification.SENSITIVE
    )

    # Internal if email or phone present without high-risk PII
    assert (
        detector.determine_dataset_classification(
            {"id": PIIClassification.NONE, "email": PIIClassification.EMAIL}
        )
        == DataClassification.INTERNAL
    )

    # Public if no PII present
    assert (
        detector.determine_dataset_classification(
            {"id": PIIClassification.NONE, "item": PIIClassification.NONE}
        )
        == DataClassification.PUBLIC
    )


def test_profiling_and_quality_score() -> None:
    """Verify statistical profiling and data quality scorecard calculation."""
    profiler = ProfilingService()
    norm = NormalizationService()

    columns = norm.normalize_schema(
        ["id", "amount", "notes"],
        {
            "id": ColumnDataType.INTEGER,
            "amount": ColumnDataType.FLOAT,
            "notes": ColumnDataType.STRING,
        },
    )

    rows: list[dict[str, Any]] = [
        {"id": 1, "amount": 100.0, "notes": "first record"},
        {"id": 2, "amount": 200.0, "notes": "second record"},
        {"id": 3, "amount": 300.0, "notes": None},
        {"id": 4, "amount": None, "notes": "fourth record"},
    ]

    org_id = uuid.uuid4()
    dataset_id = uuid.uuid4()

    profile, quality = profiler.profile_dataset(
        organization_id=org_id,
        dataset_id=dataset_id,
        columns=columns,
        rows=rows,
        duplicate_count=1,
    )

    # Assert profile statistics
    assert profile.row_count == 4
    assert profile.column_count == 3
    amt_prof = profile.columns["amount"]
    assert amt_prof.null_count == 1
    assert amt_prof.null_ratio == 0.25
    assert amt_prof.min_value == 100.0
    assert amt_prof.max_value == 300.0
    assert amt_prof.mean_value == 200.0
    assert amt_prof.median_value == 200.0

    notes_prof = profile.columns["notes"]
    assert notes_prof.min_length == 12  # "first record"
    assert notes_prof.max_length == 13  # "second record"

    # Assert quality report
    assert 0.0 <= quality.score <= 1.0
    assert quality.null_ratio > 0.0
    assert quality.duplicate_ratio > 0.0


def test_deduplication_strategies() -> None:
    """Verify deduplication under EXACT_ROW_HASH, PRIMARY_KEY, and NONE."""
    dedup = DeduplicationService()

    rows = [
        {"id": 1, "name": "Alpha", "val": 10},
        {"id": 1, "name": "Alpha", "val": 10},  # Exact duplicate
        {"id": 1, "name": "Beta", "val": 20},  # Same PK, different values
        {"id": 2, "name": "Gamma", "val": 30},
    ]

    # 1. EXACT_ROW_HASH: only identical rows removed
    res_exact, count_exact = dedup.deduplicate_rows(rows, DeduplicationStrategy.EXACT_ROW_HASH)
    assert len(res_exact) == 3
    assert count_exact == 1

    # 2. PRIMARY_KEY: removes all rows with duplicate key
    res_pk, count_pk = dedup.deduplicate_rows(rows, DeduplicationStrategy.PRIMARY_KEY, keys=["id"])
    assert len(res_pk) == 2
    assert count_pk == 2

    # 3. NONE: preserves all rows
    res_none, count_none = dedup.deduplicate_rows(rows, DeduplicationStrategy.NONE)
    assert len(res_none) == 4
    assert count_none == 0


def test_lineage_and_idempotency_fingerprints() -> None:
    """Verify deterministic fingerprints produce identical hashes for identical inputs."""
    lineage_svc = LineageService()
    norm = NormalizationService()
    dedup = DeduplicationService()

    org_id = uuid.uuid4()
    ds_id = uuid.uuid4()
    dataset_id = uuid.uuid4()

    cols = norm.normalize_schema(["id", "name", "email"])
    rows = [{"id": 1, "name": "Acme", "email": "info@acme.com"}]
    row_hashes = [dedup.compute_row_hash(r) for r in rows]

    lineage1 = lineage_svc.create_lineage(
        dataset_id=dataset_id,
        organization_id=org_id,
        source_datasource_id=ds_id,
        columns=cols,
        row_hashes=row_hashes,
        source_target="customers",
    )

    lineage2 = lineage_svc.create_lineage(
        dataset_id=dataset_id,
        organization_id=org_id,
        source_datasource_id=ds_id,
        columns=cols,
        row_hashes=row_hashes,
        source_target="customers",
    )

    # Identical inputs must yield identical fingerprints
    assert lineage1.source_fingerprint == lineage2.source_fingerprint
    assert lineage1.schema_fingerprint == lineage2.schema_fingerprint
    assert lineage1.content_fingerprint == lineage2.content_fingerprint


def test_rag_adapter_row_formatting() -> None:
    """Verify DatasetRAGAdapter formats rows into key-value cards and respects IngestionMode."""
    adapter = DatasetRAGAdapter()
    dataset_id = uuid.uuid4()

    row = {"customer_id": 101, "customer_name": "Globex", "country": "Turkey"}

    card = adapter.format_row_as_document(row, "Customers", 0)
    assert "Customer Id: 101" in card
    assert "Customer Name: Globex" in card
    assert "Country: Turkey" in card

    # STRUCTURED_ONLY generates 0 RAG documents
    empty_docs = adapter.convert_dataset_to_rag_documents(
        dataset_id, "Customers", [row], IngestionMode.STRUCTURED_ONLY
    )
    assert len(empty_docs) == 0

    # RAG_ENABLED generates retrievable document cards
    rag_docs = adapter.convert_dataset_to_rag_documents(
        dataset_id, "Customers", [row], IngestionMode.RAG_ENABLED
    )
    assert len(rag_docs) == 1
    assert "Globex" in rag_docs[0]["content"]
    assert rag_docs[0]["metadata"]["dataset_id"] == str(dataset_id)
