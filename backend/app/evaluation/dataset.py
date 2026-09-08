"""Evaluation Dataset lifecycle and version management."""

import hashlib
import json
import uuid
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.exceptions import (
    EvaluationAuthorizationError,
    EvaluationDatasetNotFoundError,
)
from app.models.evaluation import EvaluationCase, EvaluationDataset, EvaluationDatasetVersion


class DatasetManager:
    """Manages benchmark datasets and transaction-safe versioned snapshots."""

    async def create_dataset(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        name: str,
        description: str | None = None,
        language: str = "en",
        user_id: UUID | None = None,
    ) -> EvaluationDataset:
        """Create a new evaluation dataset."""
        dataset = EvaluationDataset(
            organization_id=organization_id,
            name=name.strip(),
            description=description.strip() if description else None,
            language=language,
            version=1,
            status="active",
            created_by=user_id,
        )
        session.add(dataset)
        await session.flush()

        # Seed version 1 record
        initial_version = EvaluationDatasetVersion(
            dataset_id=dataset.id,
            organization_id=organization_id,
            version_number=1,
            cases_count=0,
            checksum=hashlib.sha256(b"empty_v1").hexdigest(),
            created_by=user_id,
        )
        session.add(initial_version)
        await session.commit()
        await session.refresh(dataset)
        return dataset

    async def get_dataset(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        dataset_id: UUID,
    ) -> EvaluationDataset:
        """Retrieve dataset enforcing strict tenant isolation."""
        stmt = select(EvaluationDataset).where(EvaluationDataset.id == dataset_id)
        res = await session.execute(stmt)
        dataset = res.scalars().first()

        if not dataset:
            raise EvaluationDatasetNotFoundError(
                message=f"Evaluation dataset '{dataset_id}' not found.",
                details={"dataset_id": str(dataset_id)},
            )

        if dataset.organization_id != organization_id:
            raise EvaluationAuthorizationError(
                message="Cannot access evaluation dataset belonging to another organization.",
                details={"dataset_id": str(dataset_id)},
            )

        return dataset

    async def list_datasets(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[EvaluationDataset], int]:
        """List datasets scoped to tenant."""
        offset = max(page - 1, 0) * page_size
        count_stmt = select(func.count(EvaluationDataset.id)).where(
            EvaluationDataset.organization_id == organization_id
        )
        total_res = await session.execute(count_stmt)
        total = total_res.scalar() or 0

        query = (
            select(EvaluationDataset)
            .where(EvaluationDataset.organization_id == organization_id)
            .order_by(EvaluationDataset.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        res = await session.execute(query)
        return list(res.scalars().all()), total

    async def snapshot_version(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        dataset_id: UUID,
        user_id: UUID | None = None,
    ) -> EvaluationDatasetVersion:
        """Increment version and record immutable snapshot of all current cases."""
        dataset = await self.get_dataset(
            session, organization_id=organization_id, dataset_id=dataset_id
        )

        # Fetch all enabled cases for this dataset
        stmt = (
            select(EvaluationCase)
            .where(
                EvaluationCase.dataset_id == dataset_id,
                EvaluationCase.enabled.is_(True),
            )
            .order_by(EvaluationCase.created_at.asc())
        )
        cases = list((await session.execute(stmt)).scalars().all())

        # Compute deterministic checksum
        cases_payload = [
            {
                "query": c.query,
                "route_expected": c.route_expected,
                "expected_answer": c.expected_answer,
                "expected_metrics": c.expected_metrics,
            }
            for c in cases
        ]
        serialized = json.dumps(cases_payload, sort_keys=True)
        checksum = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        new_version_num = dataset.version + 1
        dataset.version = new_version_num

        version_rec = EvaluationDatasetVersion(
            id=uuid.uuid4(),
            dataset_id=dataset.id,
            organization_id=organization_id,
            version_number=new_version_num,
            cases_count=len(cases),
            checksum=checksum,
            created_by=user_id,
        )
        session.add(version_rec)
        await session.commit()
        await session.refresh(version_rec)
        return version_rec
