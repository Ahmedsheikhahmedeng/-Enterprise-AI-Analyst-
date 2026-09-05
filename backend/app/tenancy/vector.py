"""Qdrant vector retrieval tenant isolation contracts and filter builders."""

import uuid
from typing import Any


def build_qdrant_tenant_filter(organization_id: uuid.UUID) -> dict[str, Any]:
    """Construct a mandatory Qdrant payload filter enforcing tenant boundary.

    Guarantees that all vector searches and nearest neighbor queries are partitioned
    strictly by organization_id, preventing cross-tenant vector leakages.
    """
    return {
        "must": [
            {
                "key": "organization_id",
                "match": {
                    "value": str(organization_id),
                },
            }
        ]
    }
