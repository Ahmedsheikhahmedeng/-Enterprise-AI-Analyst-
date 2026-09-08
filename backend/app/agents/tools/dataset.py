"""Typed adapter tools wrapping Dataset metadata, profiling, and quality for Agent Runtime."""

import time
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agents.context import AgentExecutionContext
from app.agents.exceptions import ToolInputValidationError
from app.agents.schemas import ToolRiskLevel
from app.agents.tools.base import ToolOutput
from app.agents.tools.schemas import (
    DatasetGetInput,
    DatasetListInput,
    DatasetProfileInput,
    DatasetQualityInput,
    DatasetVersionsInput,
)
from app.models.dataset import Dataset, DatasetVersion
from app.rbac.catalog import (
    PERM_DATASET_PROFILE,
    PERM_DATASET_READ,
    PERM_DATASET_VERSIONS,
)


class DatasetListTool:
    """Tool listing available datasets for the active tenant."""

    name: str = "dataset.list"
    version: str = "v1.0"
    description: str = "Lists all materialized tabular datasets available in tenant."
    input_schema: type[BaseModel] = DatasetListInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_DATASET_READ
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> DatasetListInput:
        try:
            return DatasetListInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        return {
            "action": "list_datasets",
            "organization_id": str(context.organization_id),
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, DatasetListInput)
            else DatasetListInput.model_validate(validated_input)
        )
        t0 = time.perf_counter()

        stmt = (
            select(Dataset)
            .where(Dataset.organization_id == context.organization_id)
            .order_by(Dataset.created_at.desc())
            .offset(inp.offset)
            .limit(inp.limit)
        )
        res = await context.db_session.execute(stmt)
        datasets = res.scalars().all()

        data = [
            {
                "id": str(d.id),
                "name": d.name,
                "description": d.description,
                "source_type": d.source_type,
                "status": d.status,
                "current_version": d.current_version,
                "row_count": d.row_count,
                "quality_score": d.quality_score,
                "classification": d.classification,
            }
            for d in datasets
        ]

        return ToolOutput(
            success=True,
            data={"datasets": data, "count": len(data)},
            duration_ms=(time.perf_counter() - t0) * 1000,
        )


class DatasetGetTool:
    """Tool retrieving schema and metadata for a specific dataset."""

    name: str = "dataset.get"
    version: str = "v1.0"
    description: str = "Gets dataset details, schema, and column definitions."
    input_schema: type[BaseModel] = DatasetGetInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_DATASET_READ
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> DatasetGetInput:
        try:
            return DatasetGetInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, DatasetGetInput)
            else DatasetGetInput.model_validate(validated_input)
        )
        return {
            "action": "get_dataset",
            "dataset_id": str(inp.dataset_id),
            "organization_id": str(context.organization_id),
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, DatasetGetInput)
            else DatasetGetInput.model_validate(validated_input)
        )
        t0 = time.perf_counter()

        stmt = (
            select(Dataset)
            .where(
                Dataset.id == inp.dataset_id,
                Dataset.organization_id == context.organization_id,
            )
            .options(selectinload(Dataset.columns))
        )
        res = await context.db_session.execute(stmt)
        dataset = res.scalars().first()

        if not dataset:
            return ToolOutput(
                success=False,
                error_message="Dataset not found for this organization",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        cols = [
            {
                "name": c.name,
                "normalized_name": c.normalized_name,
                "data_type": c.data_type,
                "nullable": c.nullable,
                "ordinal_position": c.ordinal_position,
                "pii_classification": c.pii_classification,
            }
            for c in dataset.columns
        ]

        return ToolOutput(
            success=True,
            data={
                "id": str(dataset.id),
                "name": dataset.name,
                "description": dataset.description,
                "status": dataset.status,
                "current_version": dataset.current_version,
                "row_count": dataset.row_count,
                "quality_score": dataset.quality_score,
                "classification": dataset.classification,
                "columns": cols,
            },
            duration_ms=(time.perf_counter() - t0) * 1000,
        )


class DatasetProfileTool:
    """Tool inspecting statistical profiling for a dataset."""

    name: str = "dataset.profile"
    version: str = "v1.0"
    description: str = "Retrieves statistical data profile and column distributions for a dataset."
    input_schema: type[BaseModel] = DatasetProfileInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_DATASET_PROFILE
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> DatasetProfileInput:
        try:
            return DatasetProfileInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, DatasetProfileInput)
            else DatasetProfileInput.model_validate(validated_input)
        )
        return {
            "action": "profile_dataset",
            "dataset_id": str(inp.dataset_id),
            "organization_id": str(context.organization_id),
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, DatasetProfileInput)
            else DatasetProfileInput.model_validate(validated_input)
        )
        t0 = time.perf_counter()

        stmt = select(Dataset).where(
            Dataset.id == inp.dataset_id,
            Dataset.organization_id == context.organization_id,
        )
        res = await context.db_session.execute(stmt)
        dataset = res.scalars().first()

        if not dataset:
            return ToolOutput(
                success=False,
                error_message="Dataset not found for this organization",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        return ToolOutput(
            success=True,
            data={
                "dataset_id": str(dataset.id),
                "name": dataset.name,
                "profile": dataset.profile_data or {},
            },
            duration_ms=(time.perf_counter() - t0) * 1000,
        )


class DatasetVersionsTool:
    """Tool retrieving historical materialization versions for a dataset."""

    name: str = "dataset.versions"
    version: str = "v1.0"
    description: str = "Lists all historical materialization versions of a dataset."
    input_schema: type[BaseModel] = DatasetVersionsInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_DATASET_VERSIONS
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> DatasetVersionsInput:
        try:
            return DatasetVersionsInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, DatasetVersionsInput)
            else DatasetVersionsInput.model_validate(validated_input)
        )
        return {
            "action": "list_dataset_versions",
            "dataset_id": str(inp.dataset_id),
            "organization_id": str(context.organization_id),
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, DatasetVersionsInput)
            else DatasetVersionsInput.model_validate(validated_input)
        )
        t0 = time.perf_counter()

        stmt = (
            select(DatasetVersion)
            .where(
                DatasetVersion.dataset_id == inp.dataset_id,
                DatasetVersion.organization_id == context.organization_id,
            )
            .order_by(DatasetVersion.version.desc())
        )
        res = await context.db_session.execute(stmt)
        versions = res.scalars().all()

        data = [
            {
                "id": str(v.id),
                "version": v.version,
                "status": v.status,
                "row_count": v.row_count,
                "content_hash": v.content_hash,
                "schema_hash": v.schema_hash,
                "created_at": v.created_at.isoformat() if v.created_at else "",
            }
            for v in versions
        ]

        return ToolOutput(
            success=True,
            data={"versions": data, "count": len(data)},
            duration_ms=(time.perf_counter() - t0) * 1000,
        )


class DatasetQualityTool:
    """Tool inspecting quality scorecard and metrics for a dataset."""

    name: str = "dataset.quality"
    version: str = "v1.0"
    description: str = "Retrieves evaluated data quality score and metrics for a dataset."
    input_schema: type[BaseModel] = DatasetQualityInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_DATASET_READ
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> DatasetQualityInput:
        try:
            return DatasetQualityInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, DatasetQualityInput)
            else DatasetQualityInput.model_validate(validated_input)
        )
        return {
            "action": "get_dataset_quality",
            "dataset_id": str(inp.dataset_id),
            "organization_id": str(context.organization_id),
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, DatasetQualityInput)
            else DatasetQualityInput.model_validate(validated_input)
        )
        t0 = time.perf_counter()

        stmt = select(Dataset).where(
            Dataset.id == inp.dataset_id,
            Dataset.organization_id == context.organization_id,
        )
        res = await context.db_session.execute(stmt)
        dataset = res.scalars().first()

        if not dataset:
            return ToolOutput(
                success=False,
                error_message="Dataset not found for this organization",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        return ToolOutput(
            success=True,
            data={
                "dataset_id": str(dataset.id),
                "name": dataset.name,
                "quality_score": dataset.quality_score,
                "quality_report": dataset.quality_report or {},
            },
            duration_ms=(time.perf_counter() - t0) * 1000,
        )
