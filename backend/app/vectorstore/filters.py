"""Tenant-enforcing filter builders for Qdrant operations."""

import uuid
from typing import Any

from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.vectorstore.exceptions import TenantIsolationError


class TenantVectorFilterBuilder:
    """Builds mandatory tenant-partitioned filters for Qdrant operations.

    Strictly prevents un-scoped cross-tenant queries, deletions, or retrievals.
    """

    @classmethod
    def build_organization_filter(cls, organization_id: uuid.UUID) -> Filter:
        """Construct a mandatory filter restricted strictly to an organization."""
        if not organization_id:
            raise TenantIsolationError("organization_id is required to construct tenant filter.")
        return Filter(
            must=[
                FieldCondition(
                    key="organization_id",
                    match=MatchValue(value=str(organization_id)),
                )
            ]
        )

    @classmethod
    def build_document_filter(
        cls,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> Filter:
        """Construct a tenant-partitioned filter restricted to a specific document."""
        if not organization_id or not document_id:
            raise TenantIsolationError("Both organization_id and document_id are required.")
        return Filter(
            must=[
                FieldCondition(
                    key="organization_id",
                    match=MatchValue(value=str(organization_id)),
                ),
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=str(document_id)),
                ),
            ]
        )

    @classmethod
    def build_chunk_filter(
        cls,
        organization_id: uuid.UUID,
        chunk_id: uuid.UUID,
    ) -> Filter:
        """Construct a tenant-partitioned filter restricted to a specific chunk."""
        if not organization_id or not chunk_id:
            raise TenantIsolationError("Both organization_id and chunk_id are required.")
        return Filter(
            must=[
                FieldCondition(
                    key="organization_id",
                    match=MatchValue(value=str(organization_id)),
                ),
                FieldCondition(
                    key="chunk_id",
                    match=MatchValue(value=str(chunk_id)),
                ),
            ]
        )

    @classmethod
    def build_search_filter(
        cls,
        organization_id: uuid.UUID,
        document_id: uuid.UUID | None = None,
        chunk_type: str | None = None,
        page_number: int | None = None,
        section: str | None = None,
        additional_conditions: list[FieldCondition] | None = None,
    ) -> Filter:
        """Construct a tenant-partitioned filter for vector search with metadata constraints."""
        if not organization_id:
            raise TenantIsolationError("organization_id is required to construct search filter.")

        must_conditions: list[Any] = [
            FieldCondition(
                key="organization_id",
                match=MatchValue(value=str(organization_id)),
            )
        ]

        if document_id is not None:
            must_conditions.append(
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=str(document_id)),
                )
            )
        if chunk_type is not None:
            must_conditions.append(
                FieldCondition(
                    key="chunk_type",
                    match=MatchValue(value=str(chunk_type)),
                )
            )
        if page_number is not None:
            must_conditions.append(
                FieldCondition(
                    key="page_number",
                    match=MatchValue(value=int(page_number)),
                )
            )
        if section is not None:
            must_conditions.append(
                FieldCondition(
                    key="section",
                    match=MatchValue(value=str(section)),
                )
            )
        if additional_conditions:
            must_conditions.extend(additional_conditions)

        return Filter(must=must_conditions)

    @classmethod
    def validate_tenant_consistency(
        cls,
        expected_organization_id: uuid.UUID,
        *target_organization_ids: Any,
    ) -> None:
        """Ensure all provided target entity tenant IDs match the expected organization ID.

        Raises:
            TenantIsolationError: If any target ID fails to match the expected tenant ID.
        """
        expected_str = str(expected_organization_id)
        for idx, tid in enumerate(target_organization_ids):
            if tid is None or str(tid) != expected_str:
                raise TenantIsolationError(
                    f"Cross-tenant write rejected: expected organization '{expected_str}', "
                    f"but entity at index {idx} belongs to organization '{tid}'."
                )
