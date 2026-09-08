"""Unit tests for the Task 9 document chunking subsystem.

Validates:
- Structure-aware chunking (page -> section -> headings -> lists -> tables -> paragraphs)
- Heading path tracking and context preservation
- Parent / Child chunk hierarchies
- Table chunking with header replication across row slices
- List preservation
- Huge block fallback splitting
- Multilingual token counting and sentence splitting (Arabic, Turkish, English, mixed)
- Deterministic chunk IDs and SHA-256 content hashing
- Conservative deduplication
- Chunk quality validation and metrics calculation
"""

import uuid

import pytest

from app.chunking.boundaries import HeadingPathTracker, SentenceSplitter
from app.chunking.config import ChunkingConfig
from app.chunking.exceptions import ChunkingValidationError
from app.chunking.hashing import (
    compute_content_hash,
    generate_deterministic_chunk_id,
    normalize_chunk_text,
)
from app.chunking.models import ChunkType, IntermediateChunk
from app.chunking.parent_child import ParentChildGenerator
from app.chunking.service import ChunkingService
from app.chunking.strategies import (
    HugeBlockFallbackStrategy,
    ListChunkingStrategy,
    RawChunkItem,
    TableChunkingStrategy,
)
from app.chunking.tokenizer import MultilingualTokenCounter
from app.chunking.validators import validate_chunks
from app.ingestion.models import (
    BlockType,
    ParsedBlock,
    ParsedDocument,
    ParsedSection,
    ParsedTable,
)


@pytest.fixture
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def doc_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def token_counter() -> MultilingualTokenCounter:
    return MultilingualTokenCounter()


@pytest.fixture
def chunking_service() -> ChunkingService:
    return ChunkingService()


# ---------------------------------------------------------------------------
# 1. Heading Path Tracker Tests
# ---------------------------------------------------------------------------


def test_heading_path_tracker_hierarchy() -> None:
    tracker = HeadingPathTracker()
    assert tracker.heading_path == []
    assert tracker.heading_context == ""

    # Add Chapter 1
    tracker.update(level=1, title="Chapter 1: Overview")
    assert tracker.heading_path == ["Chapter 1: Overview"]
    assert tracker.heading_context == "Chapter 1: Overview"

    # Add Section 1.1
    tracker.update(level=2, title="Section 1.1: Financials")
    assert tracker.heading_path == ["Chapter 1: Overview", "Section 1.1: Financials"]
    assert tracker.heading_context == "Chapter 1: Overview > Section 1.1: Financials"

    # Add Subsection 1.1.1
    tracker.update(level=3, title="Subsection 1.1.1: Revenue")
    assert len(tracker.heading_path) == 3
    assert (
        tracker.heading_context
        == "Chapter 1: Overview > Section 1.1: Financials > Subsection 1.1.1: Revenue"
    )

    # Step back up to Section 1.2 (level 2) - should pop level 2 and level 3
    tracker.update(level=2, title="Section 1.2: Operations")
    assert tracker.heading_path == ["Chapter 1: Overview", "Section 1.2: Operations"]
    assert tracker.heading_context == "Chapter 1: Overview > Section 1.2: Operations"

    # Step up to Chapter 2 (level 1) - should pop everything
    tracker.update(level=1, title="Chapter 2: Strategy")
    assert tracker.heading_path == ["Chapter 2: Strategy"]
    assert tracker.heading_context == "Chapter 2: Strategy"


# ---------------------------------------------------------------------------
# 2. Multilingual Token Counter & Sentence Splitter Tests
# ---------------------------------------------------------------------------


def test_token_counter_multilingual(token_counter: MultilingualTokenCounter) -> None:
    # Empty
    assert token_counter.count_tokens("") == 0
    assert token_counter.count_tokens("   \n\t  ") == 0

    # English
    en_text = "The quick brown fox jumps over the lazy dog."
    en_tokens = token_counter.count_tokens(en_text)
    assert 8 <= en_tokens <= 12

    # Turkish with special characters (ç, ğ, ı, ö, ş, ü, İ)
    tr_text = "Şirketimizin üçüncü çeyrek net kârı geçen yıla göre yüzde kırk beş arttı."
    tr_tokens = token_counter.count_tokens(tr_text)
    assert 10 <= tr_tokens <= 16

    # Arabic with diacritics (tashkeel)
    ar_text = "سَجَّلَتِ الشَّرِكَةُ أَرْبَاحًا قِيَاسِيَّةً فِي الرُّبْعِ الأَخِيرِ."
    ar_tokens = token_counter.count_tokens(ar_text)
    assert 6 <= ar_tokens <= 14

    # Mixed text
    mixed_text = "Q3 Results: Şirket kârı %15 arttı وبلغت الإيرادات 50 مليون دولار."
    mixed_tokens = token_counter.count_tokens(mixed_text)
    assert 10 <= mixed_tokens <= 20


def test_sentence_splitter_multilingual() -> None:
    splitter = SentenceSplitter()

    # English with abbreviations
    en_text = (
        "Dr. Smith met with Mr. Brown at 3.14 PM. The meeting went well. They signed the contract."
    )
    sentences = splitter.split(en_text)
    assert len(sentences) == 3
    assert sentences[0].startswith("Dr. Smith met with Mr. Brown")
    assert sentences[1] == "The meeting went well."
    assert sentences[2] == "They signed the contract."

    # Turkish with abbreviations (vb., Dr., Prof.)
    tr_text = (
        "Prof. Dr. Kaya konferansta konuştu. Raporlar, tablolar vb. incelendi. "
        "Yeni hedefler belirlendi."
    )
    tr_sentences = splitter.split(tr_text)
    assert len(tr_sentences) == 3
    assert tr_sentences[0].startswith("Prof. Dr. Kaya")
    assert "vb." in tr_sentences[1]
    assert tr_sentences[2] == "Yeni hedefler belirlendi."

    # Arabic with Arabic question mark (؟) and period (.)
    ar_text = (
        "هل حققت الشركة أهدافها السنوية؟ نعم، لقد تجاوزت كل التوقعات. وسيتم توزيع الأرباح قريباً."
    )
    ar_sentences = splitter.split(ar_text)
    assert len(ar_sentences) == 3
    assert ar_sentences[0].endswith("؟")
    assert ar_sentences[1].endswith(".")
    assert ar_sentences[2].endswith(".")


# ---------------------------------------------------------------------------
# 3. Deterministic Hashing & UUID Generation Tests
# ---------------------------------------------------------------------------


def test_deterministic_chunk_identity(doc_id: uuid.UUID) -> None:
    text = "  Quarterly   revenue increased   by 15% in EMEA.  \n"
    norm = normalize_chunk_text(text)
    assert norm == "Quarterly revenue increased by 15% in EMEA."

    hash1 = compute_content_hash(text)
    hash2 = compute_content_hash(norm)
    assert hash1 == hash2
    assert len(hash1) == 64

    # Deterministic UUID5
    id1 = generate_deterministic_chunk_id(
        document_id=doc_id,
        chunk_index=0,
        chunker_version="1.0.0",
        content_hash=hash1,
    )
    id2 = generate_deterministic_chunk_id(
        document_id=doc_id,
        chunk_index=0,
        chunker_version="1.0.0",
        content_hash=hash1,
    )
    assert id1 == id2
    assert isinstance(id1, uuid.UUID)

    # Different index produces different ID
    id_other_index = generate_deterministic_chunk_id(
        document_id=doc_id,
        chunk_index=1,
        chunker_version="1.0.0",
        content_hash=hash1,
    )
    assert id1 != id_other_index


# ---------------------------------------------------------------------------
# 4. Table Chunking Strategy Tests
# ---------------------------------------------------------------------------


def test_table_chunking_preserves_headers_across_slices(doc_id: uuid.UUID) -> None:
    headers = ["Department", "Q1", "Q2", "Q3", "Q4", "Total"]
    # 50 rows to trigger chunking slice
    rows = [
        [f"Dept_{i}", f"{i * 10}", f"{i * 12}", f"{i * 15}", f"{i * 20}", f"{i * 57}"]
        for i in range(50)
    ]

    table = ParsedTable(
        headers=headers,
        rows=rows,
        page_number=1,
        sheet_name="Financial Summary",
    )

    # Use config with small target tokens to force slicing
    config = ChunkingConfig(
        TARGET_CHUNK_TOKENS=100,
        MAX_TABLE_ROWS_PER_SLICE=15,
    )
    strategy = TableChunkingStrategy(config=config)

    chunks = strategy.chunk_table(
        table=table,
        document_id=doc_id,
        heading_path=["Financial Statements"],
        heading_context="Financial Statements",
    )

    assert len(chunks) >= 3  # Sliced into multiple parts
    for chunk in chunks:
        assert chunk.chunk_type == ChunkType.TABLE
        # EVERY slice must contain markdown table header
        assert "| Department | Q1 | Q2 | Q3 | Q4 | Total |" in chunk.content
        assert "| --- | --- | --- | --- | --- | --- |" in chunk.content
        # Source locator checks
        assert chunk.source_locator is not None
        assert chunk.source_locator.sheet_name == "Financial Summary"
        assert chunk.metadata["sheet_name"] == "Financial Summary"
        assert chunk.metadata["row_start"] < chunk.metadata["row_end"]


# ---------------------------------------------------------------------------
# 5. List Chunking Strategy Tests
# ---------------------------------------------------------------------------


def test_list_chunking_cohesion(doc_id: uuid.UUID) -> None:
    list_text = "\n".join(
        [f"- Strategic Initiative {i}: Detail description of task {i}" for i in range(30)]
    )
    block = ParsedBlock(type=BlockType.LIST, text=list_text)

    config = ChunkingConfig(TARGET_CHUNK_TOKENS=80)
    strategy = ListChunkingStrategy(config=config)

    chunks = strategy.chunk_list(
        block=block,
        document_id=doc_id,
        heading_path=["Strategy"],
        heading_context="Strategy",
        page_number=2,
    )

    assert len(chunks) > 1
    for ch in chunks:
        assert ch.chunk_type == ChunkType.LIST
        assert ch.page_number == 2
        # Lines should be full items
        for line in ch.content.split("\n"):
            assert line.startswith("- Strategic Initiative")


# ---------------------------------------------------------------------------
# 6. Huge Block Fallback Strategy Tests
# ---------------------------------------------------------------------------


def test_huge_block_fallback(doc_id: uuid.UUID) -> None:
    # 5,000 words without newlines to simulate giant continuous paragraph
    huge_paragraph = (
        ". ".join(
            [f"This is sentence number {i} with valuable corporate information" for i in range(250)]
        )
        + "."
    )
    strategy = HugeBlockFallbackStrategy(config=ChunkingConfig(TARGET_CHUNK_TOKENS=100))

    chunks = strategy.chunk_block(
        text=huge_paragraph,
        chunk_type=ChunkType.PARAGRAPH,
        document_id=doc_id,
        heading_path=["General"],
        page_number=1,
    )

    assert len(chunks) >= 5
    for ch in chunks:
        assert len(ch.content) <= 4000
        assert ch.chunk_type == ChunkType.PARAGRAPH


def test_giant_unbroken_text_fallback(doc_id: uuid.UUID) -> None:
    # 20,000 characters with no periods at all
    unbroken_text = "A" * 20000
    strategy = HugeBlockFallbackStrategy(
        config=ChunkingConfig(TARGET_CHUNK_TOKENS=200, MAX_CHUNK_CHARACTERS=2000)
    )

    chunks = strategy.chunk_block(
        text=unbroken_text,
        chunk_type=ChunkType.TEXT,
        document_id=doc_id,
        heading_path=["Test"],
    )

    assert len(chunks) >= 10
    for ch in chunks:
        assert len(ch.content) <= 2000


# ---------------------------------------------------------------------------
# 7. Parent / Child Hierarchy Tests
# ---------------------------------------------------------------------------


def test_parent_child_generator(doc_id: uuid.UUID, org_id: uuid.UUID) -> None:
    items = [
        RawChunkItem(
            content="Revenue reached $100M in North America.",
            chunk_type=ChunkType.PARAGRAPH,
            heading_path=["Financials", "Revenue"],
            heading_context="Financials > Revenue",
            section="Financial Performance",
            page_number=1,
        ),
        RawChunkItem(
            content="European revenue reached €85M.",
            chunk_type=ChunkType.PARAGRAPH,
            heading_path=["Financials", "Revenue"],
            heading_context="Financials > Revenue",
            section="Financial Performance",
            page_number=1,
        ),
        RawChunkItem(
            content="Operating margin improved by 320 bps.",
            chunk_type=ChunkType.PARAGRAPH,
            heading_path=["Financials", "Margins"],
            heading_context="Financials > Margins",
            section="Financial Performance",
            page_number=2,
        ),
    ]

    generator = ParentChildGenerator()
    chunks = generator.build_hierarchy(
        raw_items=items,
        document_id=doc_id,
        organization_id=org_id,
    )

    # 1 Parent + 3 Children = 4 chunks
    assert len(chunks) == 4
    parent = chunks[0]
    children = chunks[1:]

    assert parent.chunk_type == ChunkType.PARENT
    assert parent.parent_chunk_id is None
    assert parent.metadata["is_parent"] is True
    assert parent.metadata["child_count"] == 3
    assert "Revenue reached $100M" in parent.content
    assert "Operating margin improved" in parent.content

    for child in children:
        assert child.parent_chunk_id == parent.id
        assert child.document_id == doc_id
        assert child.organization_id == org_id
        assert child.chunk_type == ChunkType.PARAGRAPH


# ---------------------------------------------------------------------------
# 8. End-to-End Service Tests (Structured & Paginated Documents)
# ---------------------------------------------------------------------------


def test_chunking_service_structured_document(
    chunking_service: ChunkingService,
    doc_id: uuid.UUID,
    org_id: uuid.UUID,
) -> None:
    parsed_doc = ParsedDocument(
        document_id=doc_id,
        title="Annual Report 2025",
        source_type="docx",
        parser_name="docx_parser",
        parser_version="1.0.0",
        sections=[
            ParsedSection(
                title="Executive Summary",
                level=1,
                blocks=[
                    ParsedBlock(
                        type=BlockType.PARAGRAPH,
                        text=(
                            "This annual report summarizes corporate progress "
                            "during fiscal year 2025."
                        ),
                    ),
                    ParsedBlock(
                        type=BlockType.LIST,
                        text=(
                            "- Revenue grew by 22%\n"
                            "- Operating costs decreased by 5%\n"
                            "- Customer retention was 94%"
                        ),
                    ),
                ],
            ),
            ParsedSection(
                title="Financial Statements",
                level=1,
                blocks=[
                    ParsedBlock(
                        type=BlockType.HEADING,
                        text="Balance Sheet Highlights",
                        metadata={"level": 2},
                    ),
                    ParsedBlock(
                        type=BlockType.PARAGRAPH,
                        text=(
                            "Total assets reached $1.2B compared to $950M "
                            "in the previous fiscal year."
                        ),
                    ),
                ],
            ),
        ],
        tables=[
            ParsedTable(
                headers=["Metric", "2024", "2025"],
                rows=[
                    ["Gross Revenue", "$100M", "$122M"],
                    ["Net Income", "$20M", "$28M"],
                ],
                sheet_name="Summary Table",
            )
        ],
    )

    chunks, summary = chunking_service.chunk_document(parsed_doc=parsed_doc, organization_id=org_id)

    assert len(chunks) > 0
    assert summary.total_chunks == len(chunks)
    assert summary.parent_chunks >= 1
    assert summary.child_chunks >= 1
    assert summary.table_chunks >= 1
    assert summary.list_chunks >= 1
    assert summary.text_chunks >= 1
    assert summary.empty_chunks == 0
    assert summary.oversized_chunks == 0
    assert summary.document_id == doc_id
    assert summary.organization_id == org_id


def test_chunking_determinism(
    chunking_service: ChunkingService,
    doc_id: uuid.UUID,
    org_id: uuid.UUID,
) -> None:
    parsed_doc = ParsedDocument(
        document_id=doc_id,
        title="Determinism Test Doc",
        source_type="txt",
        parser_name="text_parser",
        parser_version="1.0.0",
        sections=[
            ParsedSection(
                title="Main",
                level=1,
                blocks=[
                    ParsedBlock(type=BlockType.PARAGRAPH, text="Paragraph A with static content."),
                    ParsedBlock(
                        type=BlockType.PARAGRAPH, text="Paragraph B with subsequent content."
                    ),
                ],
            )
        ],
    )

    chunks_run1, summary1 = chunking_service.chunk_document(parsed_doc, org_id)
    chunks_run2, summary2 = chunking_service.chunk_document(parsed_doc, org_id)

    assert len(chunks_run1) == len(chunks_run2)
    for c1, c2 in zip(chunks_run1, chunks_run2, strict=True):
        assert c1.id == c2.id
        assert c1.content_hash == c2.content_hash
        assert c1.chunk_index == c2.chunk_index
        assert c1.token_count == c2.token_count
        assert c1.parent_chunk_id == c2.parent_chunk_id


# ---------------------------------------------------------------------------
# 9. Chunk Quality Validation Tests
# ---------------------------------------------------------------------------


def test_validation_detects_empty_content(doc_id: uuid.UUID, org_id: uuid.UUID) -> None:
    bad_chunk = IntermediateChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        organization_id=org_id,
        chunk_index=0,
        chunk_type=ChunkType.TEXT,
        content="   ",
        token_count=0,
        character_count=3,
        content_hash="hash",
    )
    with pytest.raises(ChunkingValidationError, match="empty or whitespace-only"):
        validate_chunks([bad_chunk], expected_document_id=doc_id, expected_organization_id=org_id)


def test_validation_detects_circular_parent(doc_id: uuid.UUID, org_id: uuid.UUID) -> None:
    chunk_id = uuid.uuid4()
    bad_chunk = IntermediateChunk(
        id=chunk_id,
        document_id=doc_id,
        organization_id=org_id,
        parent_chunk_id=chunk_id,  # Points to itself
        chunk_index=0,
        chunk_type=ChunkType.PARENT,
        content="Self referencing",
        token_count=2,
        character_count=16,
        content_hash="hash",
    )
    with pytest.raises(ChunkingValidationError, match="Circular parent reference"):
        validate_chunks([bad_chunk], expected_document_id=doc_id, expected_organization_id=org_id)


def test_validation_detects_orphan_child(doc_id: uuid.UUID, org_id: uuid.UUID) -> None:
    orphan_child = IntermediateChunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        organization_id=org_id,
        parent_chunk_id=uuid.uuid4(),  # Missing parent
        chunk_index=0,
        chunk_type=ChunkType.PARAGRAPH,
        content="Orphan child",
        token_count=2,
        character_count=12,
        content_hash="hash",
    )
    with pytest.raises(ChunkingValidationError, match="Orphan child chunk"):
        validate_chunks(
            [orphan_child], expected_document_id=doc_id, expected_organization_id=org_id
        )
