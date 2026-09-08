"""Evaluation Case creation, validation, and storage management."""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.exceptions import (
    EvaluationAuthorizationError,
    EvaluationCaseNotFoundError,
    EvaluationValidationError,
)
from app.models.evaluation import EvaluationCase, EvaluationDataset


class CaseManager:
    """Handles benchmark test case definitions and assertions."""

    ALLOWED_ROUTES = {"rag", "sql", "hybrid", "none"}

    async def add_case(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        dataset_id: UUID,
        query: str,
        route_expected: str,
        language: str = "en",
        datasource_id: UUID | None = None,
        expected_answer: str | None = None,
        expected_citations: list[str] | None = None,
        expected_documents: list[str] | None = None,
        expected_sql_semantics: str | None = None,
        expected_metrics: dict[str, Any] | None = None,
        expected_rows: list[dict[str, Any]] | None = None,
        relevant_chunks: list[str] | None = None,
        tags: list[str] | None = None,
        difficulty: str = "medium",
        enabled: bool = True,
    ) -> EvaluationCase:
        """Create and validate a new test case in an evaluation dataset."""
        # 1. Validate route
        clean_route = route_expected.strip().lower()
        if clean_route not in self.ALLOWED_ROUTES:
            raise EvaluationValidationError(
                message=f"Invalid route_expected '{route_expected}'. Must be one of: {sorted(self.ALLOWED_ROUTES)}",
                details={"route_expected": route_expected},
            )

        # 2. Verify dataset ownership
        dataset = await session.get(EvaluationDataset, dataset_id)
        if not dataset:
            raise EvaluationValidationError(
                message=f"Dataset '{dataset_id}' does not exist.",
                details={"dataset_id": str(dataset_id)},
            )
        if dataset.organization_id != organization_id:
            raise EvaluationAuthorizationError(
                message="Cannot add cases to another organization's dataset.",
                details={"dataset_id": str(dataset_id)},
            )

        case = EvaluationCase(
            dataset_id=dataset_id,
            organization_id=organization_id,
            version=dataset.version,
            query=query.strip(),
            language=language,
            route_expected=clean_route,
            datasource_id=datasource_id,
            expected_answer=expected_answer.strip() if expected_answer else None,
            expected_citations=expected_citations or [],
            expected_documents=expected_documents or [],
            expected_sql_semantics=expected_sql_semantics.strip()
            if expected_sql_semantics
            else None,
            expected_metrics=expected_metrics or {},
            expected_rows=expected_rows or [],
            relevant_chunks=relevant_chunks or [],
            tags=tags or [],
            difficulty=difficulty,
            enabled=enabled,
        )
        session.add(case)
        await session.commit()
        await session.refresh(case)
        return case

    async def get_case(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        case_id: UUID,
    ) -> EvaluationCase:
        """Fetch a specific evaluation case enforcing tenant isolation."""
        stmt = select(EvaluationCase).where(EvaluationCase.id == case_id)
        res = await session.execute(stmt)
        case = res.scalars().first()

        if not case:
            raise EvaluationCaseNotFoundError(
                message=f"Evaluation case '{case_id}' not found.",
                details={"case_id": str(case_id)},
            )

        if case.organization_id != organization_id:
            raise EvaluationAuthorizationError(
                message="Cannot access evaluation case belonging to another organization.",
                details={"case_id": str(case_id)},
            )

        return case

    async def list_cases(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        dataset_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[EvaluationCase], int]:
        """List cases for a dataset."""
        count_stmt = select(func.count(EvaluationCase.id)).where(
            EvaluationCase.dataset_id == dataset_id,
            EvaluationCase.organization_id == organization_id,
        )
        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(EvaluationCase)
            .where(
                EvaluationCase.dataset_id == dataset_id,
                EvaluationCase.organization_id == organization_id,
            )
            .order_by(EvaluationCase.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        cases = list((await session.execute(stmt)).scalars().all())
        return cases, total
