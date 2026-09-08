"""Unit tests for the Vector Store layer."""

import uuid
from typing import Any

import pytest
from qdrant_client.models import Distance

from app.chunking.models import ChunkType
from app.models.document import DocumentChunk, DocumentChunkEmbedding
from app.vectorstore.collection import build_collection_name, parse_distance
from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.exceptions import (
    TenantIsolationError,
    VectorStoreConfigurationError,
    VectorStoreValidationError,
)
from app.vectorstore.filters import TenantVectorFilterBuilder
from app.vectorstore.hashing import compute_vector_point_id
from app.vectorstore.models import VectorPoint
from app.vectorstore.payload import PayloadBuilder
from app.vectorstore.providers.fake import FakeVectorStoreProvider
from app.vectorstore.service import VectorStoreService


class TestCollectionNamingAndConfig:
    def test_build_collection_name_deterministic(self) -> None:
        name1 = build_collection_name(
            prefix="test_chunks",
            provider="openai",
            model="text-embedding-3-small",
            dimensions=1536,
            version="v1.0",
        )
        name2 = build_collection_name(
            prefix="test_chunks",
            provider="openai",
            model="text-embedding-3-small",
            dimensions=1536,
            version="v1.0",
        )
        assert name1 == name2
        assert name1 == "test_chunks__openai__text_embedding_3_small__1536__v1_0"

    def test_build_collection_name_sanitizes_special_characters(self) -> None:
        name = build_collection_name(
            prefix="chunks-prefix",
            provider="cohere/multilingual",
            model="embed:english-v3.0",
            dimensions=1024,
            version="2024-01-01",
        )
        assert "/" not in name
        assert ":" not in name
        assert "." not in name
        assert name == "chunks_prefix__cohere_multilingual__embed_english_v3_0__1024__2024_01_01"

    def test_parse_distance(self) -> None:
        assert parse_distance("cosine") == Distance.COSINE
        assert parse_distance("dot") == Distance.DOT
        assert parse_distance("euclid") == Distance.EUCLID
        assert parse_distance("euclidean") == Distance.EUCLID

        with pytest.raises(VectorStoreConfigurationError, match="Unsupported distance metric"):
            parse_distance("manhattan")


class TestDeterministicPointId:
    def test_same_inputs_produce_same_id(self) -> None:
        org_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        emb_hash = "sha256:abcdef1234567890"

        id1 = compute_vector_point_id(org_id, chunk_id, emb_hash)
        id2 = compute_vector_point_id(org_id, chunk_id, emb_hash)

        assert id1 == id2
        assert isinstance(id1, uuid.UUID)

    def test_different_inputs_produce_different_id(self) -> None:
        org_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        emb_hash_1 = "hash1"
        emb_hash_2 = "hash2"

        id1 = compute_vector_point_id(org_id, chunk_id, emb_hash_1)
        id2 = compute_vector_point_id(org_id, chunk_id, emb_hash_2)
        assert id1 != id2

        # Different tenant produces different point ID even if chunk and hash match
        org_id_2 = uuid.uuid4()
        id3 = compute_vector_point_id(org_id_2, chunk_id, emb_hash_1)
        assert id1 != id3


class TestPayloadBuilderAndSecurity:
    def _create_dummy_chunk_and_emb(
        self,
        org_id: uuid.UUID,
        doc_id: uuid.UUID,
        chunk_id: uuid.UUID,
    ) -> tuple[DocumentChunk, DocumentChunkEmbedding]:
        chunk = DocumentChunk(
            id=chunk_id,
            document_id=doc_id,
            organization_id=org_id,
            chunk_index=0,
            content="This is financial quarterly revenue report content.",
            content_hash="hash_content_123",
            token_count=10,
            character_count=52,
            chunk_type=ChunkType.TEXT,
            heading_path=["Financials", "Q3"],
            heading_context="Financials > Q3",
            page_number=3,
            section="Executive Summary",
            chunker_version="1.0.0",
        )
        emb = DocumentChunkEmbedding(
            id=uuid.uuid4(),
            organization_id=org_id,
            chunk_id=chunk_id,
            provider="openai",
            model="text-embedding-3-small",
            version="1.0.0",
            dimensions=1536,
            embedding_input_hash="hash_input_456",
            normalization=True,
        )
        return chunk, emb

    def test_build_payload_success(self) -> None:
        org_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        chunk, emb = self._create_dummy_chunk_and_emb(org_id, doc_id, chunk_id)

        payload = PayloadBuilder.build_chunk_payload(
            chunk=chunk,
            embedding=emb,
            content=chunk.content,
        )

        assert payload["organization_id"] == str(org_id)
        assert payload["document_id"] == str(doc_id)
        assert payload["chunk_id"] == str(chunk_id)
        assert payload["chunk_index"] == 0
        assert payload["chunk_type"] == "text"
        assert payload["page_number"] == 3
        assert payload["heading_path"] == ["Financials", "Q3"]
        assert payload["heading_context"] == "Financials > Q3"
        assert payload["section"] == "Executive Summary"
        assert payload["content_hash"] == "hash_content_123"
        assert payload["embedding_input_hash"] == "hash_input_456"
        assert payload["embedding_provider"] == "openai"
        assert payload["embedding_model"] == "text-embedding-3-small"
        assert payload["embedding_dimensions"] == 1536
        assert payload["normalization"] in ("True", "l2", "none")
        assert payload["content"] == "This is financial quarterly revenue report content."

    def test_forbidden_credentials_rejected(self) -> None:
        forbidden_payload: dict[str, Any] = {
            "organization_id": str(uuid.uuid4()),
            "api_key": "sk-1234567890",
        }
        with pytest.raises(VectorStoreValidationError, match="Forbidden secret"):
            PayloadBuilder.validate_payload_security(forbidden_payload)

        auth_payload: dict[str, Any] = {
            "organization_id": str(uuid.uuid4()),
            "access_token": "bearer xyz",
        }
        with pytest.raises(VectorStoreValidationError, match="Forbidden secret"):
            PayloadBuilder.validate_payload_security(auth_payload)


class TestTenantVectorFilters:
    def test_build_organization_filter(self) -> None:
        org_id = uuid.uuid4()
        f = TenantVectorFilterBuilder.build_organization_filter(org_id)
        assert isinstance(f.must, list)
        assert len(f.must) == 1
        cond: Any = f.must[0]
        assert cond.key == "organization_id"
        assert cond.match.value == str(org_id)

    def test_build_document_filter(self) -> None:
        org_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        f = TenantVectorFilterBuilder.build_document_filter(org_id, doc_id)
        assert isinstance(f.must, list)
        assert len(f.must) == 2
        keys = [getattr(c, "key", None) for c in f.must]
        assert "organization_id" in keys
        assert "document_id" in keys

    def test_validate_tenant_consistency(self) -> None:
        org_id = uuid.uuid4()
        other_org_id = uuid.uuid4()

        # Consistent
        TenantVectorFilterBuilder.validate_tenant_consistency(org_id, str(org_id), org_id)

        # Inconsistent
        with pytest.raises(TenantIsolationError, match="Cross-tenant write rejected"):
            TenantVectorFilterBuilder.validate_tenant_consistency(org_id, other_org_id)

        with pytest.raises(TenantIsolationError, match="Cross-tenant write rejected"):
            TenantVectorFilterBuilder.validate_tenant_consistency(org_id, None)


@pytest.mark.asyncio
class TestFakeVectorStoreProvider:
    async def test_ensure_and_upsert_lifecycle(self) -> None:
        provider = FakeVectorStoreProvider()
        config = VectorStoreConfig(vector_size=4)
        service = VectorStoreService(config=config, provider=provider)

        coll_name = await service.ensure_collection(
            embedding_provider="mock",
            embedding_model="unit-test",
            dimensions=4,
            version="1.0",
        )
        assert coll_name in provider.collections

        org_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        point_id = uuid.uuid4()
        point = VectorPoint(
            id=point_id,
            vector=[0.1, 0.2, 0.3, 0.4],
            payload={
                "organization_id": str(org_id),
                "document_id": str(doc_id),
                "chunk_id": str(uuid.uuid4()),
                "content": "Test mock chunk",
            },
        )

        res = await provider.upsert(coll_name, [point])
        assert res.total_points == 1
        assert res.successful_points == 1
        assert res.status == "success"

        # Count
        count = await provider.count_points(coll_name, org_id)
        assert count == 1

        # Retrieval
        retrieved = await provider.get_points(coll_name, org_id, [point_id])
        assert len(retrieved) == 1
        assert retrieved[0].id == point_id

        # Cross-tenant retrieve blocked
        wrong_org = uuid.uuid4()
        cross_tenant_retrieved = await provider.get_points(coll_name, wrong_org, [point_id])
        assert len(cross_tenant_retrieved) == 0

        # Stats
        stats = await provider.get_collection_stats(coll_name)
        assert stats.points_count == 1
        assert stats.vector_dimensions == 4

        # Delete by document
        deleted = await provider.delete_by_document(coll_name, org_id, doc_id)
        assert deleted == 1
        assert await provider.count_points(coll_name, org_id) == 0

    async def test_upsert_validation_failures(self) -> None:
        provider = FakeVectorStoreProvider()
        coll = "test_val_coll"
        await provider.ensure_collection(coll, 4, "cosine")

        # Missing organization_id
        bad_point = VectorPoint(
            id=uuid.uuid4(),
            vector=[1.0, 2.0, 3.0, 4.0],
            payload={},
        )
        with pytest.raises(TenantIsolationError):
            await provider.upsert(coll, [bad_point])

        # Dimension mismatch
        dim_mismatch_point = VectorPoint(
            id=uuid.uuid4(),
            vector=[1.0, 2.0],
            payload={"organization_id": str(uuid.uuid4())},
        )
        with pytest.raises(VectorStoreValidationError, match="dimension mismatch"):
            await provider.upsert(coll, [dim_mismatch_point])

        # NaN / Inf in vector
        nan_point = VectorPoint(
            id=uuid.uuid4(),
            vector=[1.0, float("nan"), 3.0, 4.0],
            payload={"organization_id": str(uuid.uuid4())},
        )
        with pytest.raises(VectorStoreValidationError, match="Non-finite"):
            await provider.upsert(coll, [nan_point])


@pytest.mark.asyncio
class TestVectorStoreService:
    async def test_index_chunks_end_to_end(self) -> None:
        provider = FakeVectorStoreProvider()
        config = VectorStoreConfig(vector_size=4)
        service = VectorStoreService(config=config, provider=provider)

        org_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()

        chunk = DocumentChunk(
            id=chunk_id,
            document_id=doc_id,
            organization_id=org_id,
            chunk_index=0,
            content="Sample text content for vector indexing.",
            content_hash="content_hash_1",
            token_count=7,
            character_count=40,
            chunk_type=ChunkType.TEXT,
            heading_path=[],
            chunker_version="1.0.0",
        )
        emb = DocumentChunkEmbedding(
            id=uuid.uuid4(),
            organization_id=org_id,
            chunk_id=chunk_id,
            provider="test-prov",
            model="test-model",
            version="1.0.0",
            dimensions=4,
            embedding_input_hash="emb_input_hash_1",
        )
        vectors = [[0.1, 0.2, 0.3, 0.4]]

        res = await service.index_chunks(
            organization_id=org_id,
            chunks=[chunk],
            embeddings=[emb],
            vectors=vectors,
        )

        assert res.status == "success"
        assert res.total_points == 1
        assert res.successful_points == 1

        # Count verified
        count = await service.count_points(
            collection_name=res.collection_name,
            organization_id=org_id,
        )
        assert count == 1
