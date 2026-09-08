"""In-memory fake vector store implementation for unit testing."""

import math
import uuid
from collections.abc import Sequence
from typing import Any

from app.vectorstore.exceptions import (
    CollectionMismatchError,
    TenantIsolationError,
    VectorStoreValidationError,
)
from app.vectorstore.models import (
    IndexingBatchResult,
    SparseVector,
    VectorPoint,
    VectorSearchResult,
    VectorStoreStats,
)
from app.vectorstore.providers.base import VectorStore


class FakeVectorStoreProvider(VectorStore):
    """In-memory simulated vector store strictly adhering to VectorStore protocol."""

    def __init__(self) -> None:
        self._collections: dict[str, dict[str, Any]] = {}

    @property
    def collections(self) -> dict[str, dict[str, Any]]:
        return self._collections

    async def ensure_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: str = "cosine",
        enable_sparse: bool = True,
    ) -> None:
        if collection_name in self._collections:
            meta = self._collections[collection_name]
            if meta["vector_size"] != vector_size or meta["distance"] != distance:
                raise CollectionMismatchError(
                    collection_name=collection_name,
                    expected_size=vector_size,
                    actual_size=meta["vector_size"],
                    expected_distance=distance,
                    actual_distance=meta["distance"],
                )
            return

        self._collections[collection_name] = {
            "vector_size": vector_size,
            "distance": distance,
            "enable_sparse": enable_sparse,
            "points": {},  # UUID: VectorPoint
        }

    async def upsert(
        self,
        collection_name: str,
        points: Sequence[VectorPoint],
    ) -> IndexingBatchResult:
        meta = self._collections[collection_name]
        expected_dim = meta["vector_size"]

        for point in points:
            if not point.vector:
                raise VectorStoreValidationError(f"Point '{point.id}' contains an empty vector.")
            if len(point.vector) != expected_dim:
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

        target = meta["points"]
        for p in points:
            target[p.id] = p

        return IndexingBatchResult(
            collection_name=collection_name,
            total_points=len(points),
            successful_points=len(points),
            failed_points=0,
            batch_count=1,
            status="success",
        )

    async def delete_by_document(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> int:
        if collection_name not in self._collections:
            return 0

        target = self._collections[collection_name]["points"]
        to_delete = [
            pid
            for pid, p in target.items()
            if p.payload.get("organization_id") == str(organization_id)
            and p.payload.get("document_id") == str(document_id)
        ]
        for pid in to_delete:
            del target[pid]
        return len(to_delete)

    async def delete_by_chunk(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        chunk_id: uuid.UUID,
    ) -> int:
        if collection_name not in self._collections:
            return 0

        target = self._collections[collection_name]["points"]
        to_delete = [
            pid
            for pid, p in target.items()
            if p.payload.get("organization_id") == str(organization_id)
            and p.payload.get("chunk_id") == str(chunk_id)
        ]
        for pid in to_delete:
            del target[pid]
        return len(to_delete)

    async def delete_by_organization(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
    ) -> int:
        if collection_name not in self._collections:
            return 0

        target = self._collections[collection_name]["points"]
        to_delete = [
            pid
            for pid, p in target.items()
            if p.payload.get("organization_id") == str(organization_id)
        ]
        for pid in to_delete:
            del target[pid]
        return len(to_delete)

    async def get_points(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        point_ids: Sequence[uuid.UUID],
    ) -> list[VectorPoint]:
        if collection_name not in self._collections:
            return []

        target = self._collections[collection_name]["points"]
        results: list[VectorPoint] = []
        for pid in point_ids:
            p = target.get(pid)
            if p and p.payload.get("organization_id") == str(organization_id):
                results.append(p)
        return results

    async def count_points(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        document_id: uuid.UUID | None = None,
    ) -> int:
        if collection_name not in self._collections:
            return 0

        target = self._collections[collection_name]["points"]
        count = 0
        for p in target.values():
            if p.payload.get("organization_id") == str(organization_id) and (
                document_id is None or p.payload.get("document_id") == str(document_id)
            ):
                count += 1
        return count

    async def get_collection_stats(
        self,
        collection_name: str,
    ) -> VectorStoreStats:
        if collection_name not in self._collections:
            raise KeyError(f"Collection '{collection_name}' does not exist.")

        meta = self._collections[collection_name]
        cnt = len(meta["points"])
        return VectorStoreStats(
            collection_name=collection_name,
            points_count=cnt,
            indexed_vectors_count=cnt,
            vector_size=meta["vector_size"],
            distance=meta["distance"],
            status="green",
        )

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
        if collection_name not in self._collections:
            return []

        target = self._collections[collection_name]["points"]
        org_str = str(organization_id)

        q_norm = math.sqrt(sum(x * x for x in vector))
        if q_norm == 0.0:
            return []

        scored_points: list[tuple[float, VectorPoint]] = []

        for p in target.values():
            if p.payload.get("organization_id") != org_str:
                continue

            if filter_conditions is not None:
                if isinstance(filter_conditions, dict):
                    match = True
                    for k, v in filter_conditions.items():
                        if p.payload.get(k) != v:
                            match = False
                            break
                    if not match:
                        continue
                elif hasattr(filter_conditions, "must") and filter_conditions.must:
                    match = True
                    for cond in filter_conditions.must:
                        key = getattr(cond, "key", None)
                        val_obj = getattr(cond, "match", None)
                        val = getattr(val_obj, "value", None) if val_obj else None
                        if key and val is not None and str(p.payload.get(key, "")) != str(val):
                            match = False
                            break
                    if not match:
                        continue

            p_vec = p.vector
            if len(p_vec) != len(vector):
                continue
            dot = sum(a * b for a, b in zip(vector, p_vec, strict=False))
            p_norm = math.sqrt(sum(x * x for x in p_vec))
            score = (dot / (q_norm * p_norm)) if p_norm > 0.0 else 0.0

            if score_threshold is not None and score < score_threshold:
                continue

            scored_points.append((score, p))

        scored_points.sort(key=lambda item: item[0], reverse=True)

        results: list[VectorSearchResult] = []
        for score, pt in scored_points[:limit]:
            results.append(
                VectorSearchResult(
                    id=pt.id,
                    score=score,
                    payload=pt.payload,
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
        if collection_name not in self._collections:
            return []

        target = self._collections[collection_name]["points"]
        org_str = str(organization_id)

        if not sparse_vector.indices:
            return []

        q_dict = dict(zip(sparse_vector.indices, sparse_vector.values, strict=False))
        scored_points: list[tuple[float, VectorPoint]] = []

        for p in target.values():
            if p.payload.get("organization_id") != org_str:
                continue

            if filter_conditions is not None:
                if isinstance(filter_conditions, dict):
                    match = True
                    for k, v in filter_conditions.items():
                        if p.payload.get(k) != v:
                            match = False
                            break
                    if not match:
                        continue
                elif hasattr(filter_conditions, "must") and filter_conditions.must:
                    match = True
                    for cond in filter_conditions.must:
                        key = getattr(cond, "key", None)
                        val_obj = getattr(cond, "match", None)
                        val = getattr(val_obj, "value", None) if val_obj else None
                        if key and val is not None and str(p.payload.get(key, "")) != str(val):
                            match = False
                            break
                    if not match:
                        continue

            if not p.sparse_vector or not p.sparse_vector.indices:
                continue

            p_dict = dict(zip(p.sparse_vector.indices, p.sparse_vector.values, strict=False))
            # Compute dot product over matching token indices
            dot_product = sum(q_dict[idx] * p_dict[idx] for idx in p_dict if idx in q_dict)

            if dot_product <= 0.0:
                continue

            if score_threshold is not None and dot_product < score_threshold:
                continue

            scored_points.append((dot_product, p))

        scored_points.sort(key=lambda item: item[0], reverse=True)

        results: list[VectorSearchResult] = []
        for score, pt in scored_points[:limit]:
            results.append(
                VectorSearchResult(
                    id=pt.id,
                    score=score,
                    payload=pt.payload,
                    vector=None,
                    sparse_score=score,
                    sparse_vector=pt.sparse_vector,
                )
            )
        return results

    async def health_check(self) -> bool:
        return True
