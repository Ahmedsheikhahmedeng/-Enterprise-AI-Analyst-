"""Production Qdrant vector store provider implementation."""

import asyncio
import logging
import math
import time
import uuid
from collections.abc import Sequence
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
)
from qdrant_client.models import (
    SparseVector as QdrantSparseVector,
)

from app.vectorstore.collection import CollectionManager
from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.exceptions import (
    TenantIsolationError,
    VectorStoreConnectionError,
    VectorStoreValidationError,
)
from app.vectorstore.filters import TenantVectorFilterBuilder
from app.vectorstore.models import (
    IndexingBatchResult,
    SparseVector,
    VectorPoint,
    VectorSearchResult,
    VectorStoreStats,
)
from app.vectorstore.providers.base import VectorStore

logger = logging.getLogger(__name__)


class QdrantVectorStoreProvider(VectorStore):
    """Production VectorStore provider backed by Qdrant.

    Enforces:
    - Mandatory tenant isolation across all write, read, count, and delete operations.
    - Numerical validation on vectors (dimension checks, finite floats, non-empty).
    - Batching and concurrency backpressure using asyncio.Semaphore.
    - Exponential backoff on transient network and server errors.
    """

    def __init__(
        self,
        client: AsyncQdrantClient,
        config: VectorStoreConfig,
    ) -> None:
        self.client = client
        self.config = config

    async def ensure_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: str = "cosine",
        enable_sparse: bool = True,
    ) -> None:
        await CollectionManager.ensure_collection(
            client=self.client,
            collection_name=collection_name,
            vector_size=vector_size,
            distance=distance,
            enable_sparse=enable_sparse,
        )

    def _validate_point(self, point: VectorPoint, expected_dim: int | None = None) -> None:
        """Verify vector shape, numeric finiteness, and tenant payload presence."""
        if not point.vector:
            raise VectorStoreValidationError(f"Point '{point.id}' contains an empty vector.")
        if expected_dim is not None and len(point.vector) != expected_dim:
            raise VectorStoreValidationError(
                f"Point '{point.id}' vector dimension mismatch: expected {expected_dim}, "
                f"got {len(point.vector)}."
            )
        for idx, val in enumerate(point.vector):
            if not isinstance(val, (int, float)) or not math.isfinite(val):
                raise VectorStoreValidationError(
                    f"Non-finite value (NaN/Inf) at index {idx} in point '{point.id}'."
                )

        if not point.organization_id:
            raise TenantIsolationError(
                f"Point '{point.id}' is missing mandatory 'organization_id' in payload."
            )

    async def _upsert_single_batch(
        self,
        collection_name: str,
        batch_points: list[VectorPoint],
    ) -> None:
        """Execute a single batch upsert with exponential backoff on transient errors."""
        qdrant_points: list[PointStruct] = []
        for p in batch_points:
            vec: Any = p.vector
            if p.sparse_vector is not None:
                vec = {
                    "": p.vector,
                    "sparse": QdrantSparseVector(
                        indices=p.sparse_vector.indices,
                        values=p.sparse_vector.values,
                    ),
                }
            qdrant_points.append(
                PointStruct(
                    id=str(p.id),
                    vector=vec,
                    payload=p.payload,
                )
            )

        attempt = 0
        while attempt <= self.config.retry_count:
            try:
                await self.client.upsert(
                    collection_name=collection_name,
                    points=qdrant_points,
                )
                return
            except Exception as exc:
                err_str = str(exc).lower()
                # Check for transient errors
                is_transient = any(
                    k in err_str
                    for k in ("timeout", "timed out", "connection", "connect", "503", "502", "504")
                )
                if not is_transient or attempt == self.config.retry_count:
                    logger.error(
                        "Qdrant batch upsert failed on collection '%s': %s",
                        collection_name,
                        exc,
                    )
                    raise VectorStoreConnectionError(
                        f"Failed to upsert batch into Qdrant collection '{collection_name}': {exc}"
                    ) from exc

                sleep_time = self.config.retry_backoff * (2**attempt)
                logger.warning(
                    "Transient Qdrant error on upsert. Retrying in %.2fs (attempt %d/%d): %s",
                    sleep_time,
                    attempt + 1,
                    self.config.retry_count,
                    exc,
                )
                await asyncio.sleep(sleep_time)
                attempt += 1

    async def upsert(
        self,
        collection_name: str,
        points: Sequence[VectorPoint],
    ) -> IndexingBatchResult:
        if not points:
            return IndexingBatchResult(
                collection_name=collection_name,
                total_points=0,
                successful_points=0,
                failed_points=0,
                batch_count=0,
                status="success",
            )

        start_time = time.perf_counter()
        expected_dim = self.config.vector_size

        # 1. Validation & Tenant Consistency Check
        first_org_id = points[0].organization_id
        for p in points:
            self._validate_point(p, expected_dim=expected_dim)
            if p.organization_id != first_org_id:
                raise TenantIsolationError(
                    f"Mixed-tenant batch rejected: point '{p.id}' tenant '{p.organization_id}' "
                    f"does not match batch tenant '{first_org_id}'."
                )

        # 2. Partition into batches
        batch_size = self.config.upsert_batch_size
        batches = [list(points[i : i + batch_size]) for i in range(0, len(points), batch_size)]

        # 3. Concurrent batch execution with Semaphore
        semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        successful_points = 0
        failed_points = 0
        failed_chunk_ids: list[uuid.UUID] = []

        async def _worker(b: list[VectorPoint]) -> tuple[bool, list[VectorPoint]]:
            async with semaphore:
                try:
                    await self._upsert_single_batch(collection_name, b)
                    return True, b
                except Exception:
                    return False, b

        tasks = [_worker(b) for b in batches]
        results = await asyncio.gather(*tasks)

        for ok, b in results:
            if ok:
                successful_points += len(b)
            else:
                failed_points += len(b)
                for p in b:
                    chunk_id_str = p.payload.get("chunk_id")
                    if chunk_id_str:
                        failed_chunk_ids.append(uuid.UUID(chunk_id_str))

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        if failed_points == 0:
            status = "success"
        elif successful_points == 0:
            status = "failure"
        else:
            status = "partial"

        return IndexingBatchResult(
            collection_name=collection_name,
            total_points=len(points),
            successful_points=successful_points,
            failed_points=failed_points,
            failed_chunk_ids=failed_chunk_ids,
            batch_count=len(batches),
            latency_ms=latency_ms,
            status=status,
        )

    async def delete_by_document(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> int:
        doc_filter = TenantVectorFilterBuilder.build_document_filter(
            organization_id=organization_id,
            document_id=document_id,
        )
        before_count = await self.count_points(
            collection_name=collection_name,
            organization_id=organization_id,
            document_id=document_id,
        )
        await self.client.delete(
            collection_name=collection_name,
            points_selector=FilterSelector(filter=doc_filter),
        )
        return before_count

    async def delete_by_chunk(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        chunk_id: uuid.UUID,
    ) -> int:
        chunk_filter = TenantVectorFilterBuilder.build_chunk_filter(
            organization_id=organization_id,
            chunk_id=chunk_id,
        )
        await self.client.delete(
            collection_name=collection_name,
            points_selector=FilterSelector(filter=chunk_filter),
        )
        return 1

    async def delete_by_organization(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
    ) -> int:
        org_filter = TenantVectorFilterBuilder.build_organization_filter(organization_id)
        before_count = await self.count_points(
            collection_name=collection_name,
            organization_id=organization_id,
        )
        await self.client.delete(
            collection_name=collection_name,
            points_selector=FilterSelector(filter=org_filter),
        )
        return before_count

    async def get_points(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        point_ids: Sequence[uuid.UUID],
    ) -> list[VectorPoint]:
        if not point_ids:
            return []

        string_ids = [str(pid) for pid in point_ids]
        raw_records = await self.client.retrieve(
            collection_name=collection_name,
            ids=string_ids,
            with_payload=True,
            with_vectors=True,
        )

        results: list[VectorPoint] = []
        expected_org_str = str(organization_id)
        for rec in raw_records:
            payload = dict(rec.payload or {})
            # Strict multi-tenant defense: drop point if organization_id does not match
            if payload.get("organization_id") != expected_org_str:
                logger.warning(
                    "Tenant isolation triggered: dropped retrieved point '%s'.",
                    rec.id,
                )
                continue

            vector_data = rec.vector
            vec: list[float] = (
                [float(x) for x in vector_data if isinstance(x, (int, float))]
                if isinstance(vector_data, list)
                else []
            )

            results.append(
                VectorPoint(
                    id=uuid.UUID(str(rec.id)),
                    vector=vec,
                    payload=payload,
                )
            )
        return results

    async def count_points(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        document_id: uuid.UUID | None = None,
    ) -> int:
        if document_id is not None:
            count_filter = TenantVectorFilterBuilder.build_document_filter(
                organization_id=organization_id,
                document_id=document_id,
            )
        else:
            count_filter = TenantVectorFilterBuilder.build_organization_filter(organization_id)

        try:
            res = await self.client.count(
                collection_name=collection_name,
                count_filter=count_filter,
                exact=True,
            )
            return res.count
        except Exception as exc:
            logger.warning("Error counting points in collection '%s': %s", collection_name, exc)
            return 0

    async def get_collection_stats(
        self,
        collection_name: str,
    ) -> VectorStoreStats:
        return await CollectionManager.get_collection_stats(self.client, collection_name)

    async def search(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        vector: Sequence[float],
        *,
        limit: int,
        score_threshold: float | None = None,
        filter_conditions: Any | None = None,
    ) -> list[VectorSearchResult]:
        if not vector:
            raise VectorStoreValidationError("Query vector cannot be empty.")
        if not organization_id:
            raise TenantIsolationError("organization_id is mandatory for vector search.")

        # Ensure filter_conditions includes tenant isolation
        org_str = str(organization_id)
        if filter_conditions is None:
            qdrant_filter = TenantVectorFilterBuilder.build_organization_filter(organization_id)
        elif isinstance(filter_conditions, Filter):
            has_org = any(
                getattr(c, "key", None) == "organization_id"
                and getattr(getattr(c, "match", None), "value", None) == org_str
                for c in (filter_conditions.must or [])
            )
            if not has_org:
                must: list[Any] = list(filter_conditions.must or [])
                must.append(
                    FieldCondition(
                        key="organization_id",
                        match=MatchValue(value=org_str),
                    )
                )
                qdrant_filter = Filter(
                    must=must,
                    should=filter_conditions.should,
                    must_not=filter_conditions.must_not,
                )
            else:
                qdrant_filter = filter_conditions
        else:
            qdrant_filter = filter_conditions

        attempt = 0
        while attempt <= self.config.retry_count:
            try:
                response = await self.client.query_points(
                    collection_name=collection_name,
                    query=list(vector),
                    query_filter=qdrant_filter,
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=True,
                    with_vectors=False,
                )
                break
            except Exception as exc:
                err_str = str(exc).lower()
                if "not found" in err_str or "doesn't exist" in err_str:
                    logger.info(
                        "Collection '%s' does not exist yet; returning empty search results.",
                        collection_name,
                    )
                    return []
                is_transient = any(
                    k in err_str
                    for k in ("timeout", "timed out", "connection", "connect", "503", "502", "504")
                )
                if not is_transient or attempt == self.config.retry_count:
                    logger.error(
                        "Qdrant search failed on collection '%s': %s",
                        collection_name,
                        exc,
                    )
                    raise VectorStoreConnectionError(
                        f"Failed to execute vector search on Qdrant "
                        f"collection '{collection_name}': {exc}"
                    ) from exc

                sleep_time = self.config.retry_backoff * (2**attempt)
                logger.warning(
                    "Transient Qdrant error on search. Retrying in %.2fs (attempt %d/%d): %s",
                    sleep_time,
                    attempt + 1,
                    self.config.retry_count,
                    exc,
                )
                await asyncio.sleep(sleep_time)
                attempt += 1

        results: list[VectorSearchResult] = []
        for pt in response.points:
            payload = dict(pt.payload or {})
            if payload.get("organization_id") != org_str:
                logger.warning(
                    "Tenant isolation defense triggered: dropped point '%s' "
                    "with org '%s' (expected '%s')",
                    pt.id,
                    payload.get("organization_id"),
                    org_str,
                )
                continue
            results.append(
                VectorSearchResult(
                    id=uuid.UUID(str(pt.id)),
                    score=float(pt.score),
                    payload=payload,
                    vector=None,
                )
            )
        return results

    async def search_sparse(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        sparse_vector: SparseVector,
        *,
        limit: int,
        score_threshold: float | None = None,
        filter_conditions: Any | None = None,
    ) -> list[VectorSearchResult]:
        if not sparse_vector.indices:
            raise VectorStoreValidationError("Sparse vector indices cannot be empty.")
        if not organization_id:
            raise TenantIsolationError("organization_id is mandatory for vector search.")

        org_str = str(organization_id)
        if filter_conditions is None:
            qdrant_filter = TenantVectorFilterBuilder.build_organization_filter(organization_id)
        elif isinstance(filter_conditions, Filter):
            has_org = any(
                getattr(c, "key", None) == "organization_id"
                and getattr(getattr(c, "match", None), "value", None) == org_str
                for c in (filter_conditions.must or [])
            )
            if not has_org:
                must: list[Any] = list(filter_conditions.must or [])
                must.append(
                    FieldCondition(
                        key="organization_id",
                        match=MatchValue(value=org_str),
                    )
                )
                qdrant_filter = Filter(
                    must=must,
                    should=filter_conditions.should,
                    must_not=filter_conditions.must_not,
                )
            else:
                qdrant_filter = filter_conditions
        else:
            qdrant_filter = filter_conditions

        q_sparse = QdrantSparseVector(
            indices=sparse_vector.indices,
            values=sparse_vector.values,
        )

        attempt = 0
        while attempt <= self.config.retry_count:
            try:
                response = await self.client.query_points(
                    collection_name=collection_name,
                    query=q_sparse,
                    using="sparse",
                    query_filter=qdrant_filter,
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=True,
                    with_vectors=False,
                )
                break
            except Exception as exc:
                err_str = str(exc).lower()
                if "not found" in err_str or "doesn't exist" in err_str:
                    logger.info(
                        "Collection '%s' does not exist yet; returning empty sparse results.",
                        collection_name,
                    )
                    return []
                is_transient = any(
                    k in err_str
                    for k in ("timeout", "timed out", "connection", "connect", "503", "502", "504")
                )
                if not is_transient or attempt == self.config.retry_count:
                    logger.error(
                        "Qdrant sparse search failed on collection '%s': %s",
                        collection_name,
                        exc,
                    )
                    raise VectorStoreConnectionError(
                        f"Failed to execute sparse vector search on Qdrant "
                        f"collection '{collection_name}': {exc}"
                    ) from exc

                sleep_time = self.config.retry_backoff * (2**attempt)
                logger.warning(
                    "Transient Qdrant error on sparse search. Retrying in %.2fs "
                    "(attempt %d/%d): %s",
                    sleep_time,
                    attempt + 1,
                    self.config.retry_count,
                    exc,
                )
                await asyncio.sleep(sleep_time)
                attempt += 1

        results: list[VectorSearchResult] = []
        for pt in response.points:
            payload = dict(pt.payload or {})
            if payload.get("organization_id") != org_str:
                logger.warning(
                    "Tenant isolation defense triggered: dropped point '%s' "
                    "with org '%s' (expected '%s')",
                    pt.id,
                    payload.get("organization_id"),
                    org_str,
                )
                continue
            results.append(
                VectorSearchResult(
                    id=uuid.UUID(str(pt.id)),
                    score=float(pt.score),
                    payload=payload,
                    vector=None,
                    sparse_score=float(pt.score),
                    sparse_vector=None,
                )
            )
        return results

    async def health_check(self) -> bool:
        try:
            await self.client.get_collections()
            return True
        except Exception:
            return False
