"""Integration tests for Dataset Ingestion, Materialization, Versions, Background Jobs, and Agent Tools."""

import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import openpyxl
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context import AgentExecutionContext
from app.agents.tools.dataset import (
    DatasetGetTool,
    DatasetListTool,
    DatasetProfileTool,
    DatasetQualityTool,
    DatasetVersionsTool,
)
from app.connectors.domain.enums import ConnectorType
from app.ingestion.application.ingestion_service import IngestionService
from app.ingestion.domain.enums import DatasetStatus, DeduplicationStrategy, IngestionMode
from app.ingestion.domain.models import IngestionConfig
from app.jobs.context import JobContext
from app.jobs.tasks.dataset_ingestion import DatasetIngestionTask
from app.models.data_source import DataSource
from app.models.dataset import Dataset, DatasetColumn, DatasetVersion


@pytest.mark.asyncio
async def test_csv_to_dataset_full_flow(tmp_path: Path) -> None:
    """End-to-end integration test: CSV file -> DataSource -> Dataset ingestion & materialization."""
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text(
        "order_id,customer_name,total_amount,status\n"
        "1001,Acme Corp,1500.50,completed\n"
        "1002,Globex Inc,2750.00,completed\n"
        "1003,Initech,890.25,pending\n"
    )

    org_id = uuid.uuid4()
    ds_id = uuid.uuid4()
    dataset_id = uuid.uuid4()

    mock_ds = DataSource(
        id=ds_id,
        organization_id=org_id,
        name="Sales CSV Source",
        type=ConnectorType.CSV.value,
        status="active",
        configuration={"file_path": str(csv_file)},
    )

    mock_dataset = Dataset(
        id=dataset_id,
        organization_id=org_id,
        name="Quarterly Sales",
        source_type=ConnectorType.CSV.value,
        source_datasource_id=ds_id,
        status=DatasetStatus.CREATED.value,
        current_version=1,
    )

    mock_session = AsyncMock(spec=AsyncSession)

    # Handlers for select queries: Dataset then DataSource
    async def mock_execute(stmt: Any) -> Any:
        sql_str = str(stmt).lower()
        res = MagicMock()
        if "from datasets" in sql_str:
            res.scalars.return_value.first.return_value = mock_dataset
        elif "from data_sources" in sql_str:
            res.scalars.return_value.first.return_value = mock_ds
        elif "from dataset_versions" in sql_str:
            res.scalars.return_value.first.return_value = None
            res.scalars.return_value.all.return_value = []
        elif "from dataset_columns" in sql_str:
            res.scalars.return_value.all.return_value = []
        else:
            res.scalars.return_value.first.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_session.execute.side_effect = mock_execute

    ingestion_service = IngestionService()
    config = IngestionConfig(
        batch_size=100,
        deduplication_strategy=DeduplicationStrategy.EXACT_ROW_HASH,
        ingestion_mode=IngestionMode.STRUCTURED_ONLY,
    )

    result = await ingestion_service.ingest_dataset(
        db_session=mock_session,
        organization_id=org_id,
        dataset_id=dataset_id,
        config=config,
    )

    # Verify materialization outcome
    assert result.version == 1
    assert result.row_count == 3
    assert result.quality_report.score >= 0.8
    assert result.profile.column_count == 4
    assert result.storage_path is not None
    assert Path(result.storage_path).exists()


@pytest.mark.asyncio
async def test_excel_to_dataset_full_flow(tmp_path: Path) -> None:
    """End-to-end integration test: Excel workbook -> DataSource -> Dataset ingestion."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Employees"
    ws.append(["emp_id", "full_name", "department", "salary"])
    ws.append([1, "Alice Smith", "Engineering", 120000])
    ws.append([2, "Bob Jones", "Product", 115000])

    excel_file = tmp_path / "company.xlsx"
    wb.save(str(excel_file))

    org_id = uuid.uuid4()
    ds_id = uuid.uuid4()
    dataset_id = uuid.uuid4()

    mock_ds = DataSource(
        id=ds_id,
        organization_id=org_id,
        name="HR Source",
        type=ConnectorType.EXCEL.value,
        status="active",
        configuration={"file_path": str(excel_file)},
    )

    mock_dataset = Dataset(
        id=dataset_id,
        organization_id=org_id,
        name="Employee Directory",
        source_type=ConnectorType.EXCEL.value,
        source_datasource_id=ds_id,
        status=DatasetStatus.CREATED.value,
        current_version=1,
    )

    mock_session = AsyncMock(spec=AsyncSession)

    async def mock_execute(stmt: Any) -> Any:
        sql_str = str(stmt).lower()
        res = MagicMock()
        if "from datasets" in sql_str:
            res.scalars.return_value.first.return_value = mock_dataset
        elif "from data_sources" in sql_str:
            res.scalars.return_value.first.return_value = mock_ds
        elif "from dataset_versions" in sql_str:
            res.scalars.return_value.first.return_value = None
            res.scalars.return_value.all.return_value = []
        elif "from dataset_columns" in sql_str:
            res.scalars.return_value.all.return_value = []
        else:
            res.scalars.return_value.first.return_value = None
            res.scalars.return_value.all.return_value = []
        return res

    mock_session.execute.side_effect = mock_execute

    ingestion_service = IngestionService()
    result = await ingestion_service.ingest_dataset(
        db_session=mock_session,
        organization_id=org_id,
        dataset_id=dataset_id,
        target_name="Employees",
    )

    assert result.version == 1
    assert result.row_count == 2
    assert "full_name" in result.profile.columns


@pytest.mark.asyncio
async def test_zero_downtime_version_lifecycle(tmp_path: Path) -> None:
    """Verify that while v2 is ingesting, v1 remains ready; on success v2 is ready and v1 is stale."""
    from app.ingestion.application.materialization_service import MaterializationService
    from app.ingestion.domain.models import (
        DataQualityReport,
        DatasetLineage,
        DatasetProfile,
    )

    mat_svc = MaterializationService()
    org_id = uuid.uuid4()
    dataset_id = uuid.uuid4()

    mock_dataset = Dataset(
        id=dataset_id,
        organization_id=org_id,
        name="Products",
        source_type="csv",
        status=DatasetStatus.READY.value,
        current_version=1,
    )

    v1 = DatasetVersion(
        id=uuid.uuid4(),
        dataset_id=dataset_id,
        organization_id=org_id,
        version=1,
        status=DatasetStatus.READY.value,
        row_count=100,
        content_hash="v1_hash",
        schema_hash="v1_schema",
    )

    mock_session = AsyncMock(spec=AsyncSession)

    # 1. Prepare v2: v2 is INGESTING, v1 remains READY
    mock_res_v1 = MagicMock()
    mock_res_v1.scalars.return_value.first.return_value = v1
    mock_session.execute.return_value = mock_res_v1

    v2 = await mat_svc.prepare_new_version(mock_session, mock_dataset)
    assert v2.version == 2
    assert v2.status == DatasetStatus.INGESTING.value
    assert v1.status == DatasetStatus.READY.value

    # 2. Promote v2 success: v2 becomes READY, update statement executed
    profile = DatasetProfile(dataset_id=dataset_id, organization_id=org_id, row_count=120)
    quality = DataQualityReport(score=0.95)
    lineage = DatasetLineage(dataset_id=dataset_id, organization_id=org_id)

    mock_session.execute.return_value = MagicMock()
    v2_promoted = await mat_svc.promote_version_success(
        db_session=mock_session,
        dataset=mock_dataset,
        version=v2,
        columns=[],
        profile=profile,
        quality_report=quality,
        lineage=lineage,
        storage_path="/tmp/v2",
        content_hash="v2_hash",
        schema_hash="v2_schema",
        row_count=120,
    )

    assert v2_promoted.status == DatasetStatus.READY.value
    assert v2_promoted.version == 2
    assert mock_dataset.current_version == 2

    # 3. If v3 fails midway: v3 is marked FAILED, older v2 remains active
    v3 = DatasetVersion(
        id=uuid.uuid4(),
        dataset_id=dataset_id,
        organization_id=org_id,
        version=3,
        status=DatasetStatus.INGESTING.value,
    )
    mock_ready_res = MagicMock()
    mock_ready_res.scalars.return_value.first.return_value = v2  # v2 is ready
    mock_session.execute.return_value = mock_ready_res

    await mat_svc.mark_version_failure(mock_session, mock_dataset, v3, "Disk full error")
    assert v3.status == DatasetStatus.FAILED.value
    assert mock_dataset.status == DatasetStatus.READY.value  # Did not crash dataset to FAILED


@pytest.mark.asyncio
async def test_background_job_dataset_ingestion_task() -> None:
    """Verify DatasetIngestionTask execution through background job interface."""
    org_id = uuid.uuid4()
    dataset_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_ingestion_service = AsyncMock()
    from app.ingestion.domain.models import (
        DataQualityReport,
        DatasetLineage,
        DatasetProfile,
        MaterializationResult,
    )

    mock_ingestion_service.ingest_dataset.return_value = MaterializationResult(
        dataset_id=dataset_id,
        version=1,
        row_count=500,
        content_hash="hash_500",
        schema_hash="schema_500",
        storage_path="/storage/data.jsonl",
        profile=DatasetProfile(dataset_id=dataset_id, organization_id=org_id, row_count=500),
        quality_report=DataQualityReport(score=0.92),
        lineage=DatasetLineage(dataset_id=dataset_id, organization_id=org_id),
    )

    mock_session = AsyncMock(spec=AsyncSession)
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_session_factory() -> AsyncIterator[AsyncSession]:
        yield mock_session

    task = DatasetIngestionTask(
        ingestion_service=mock_ingestion_service,
        session_factory=mock_session_factory,  # type: ignore[arg-type]
    )

    context = JobContext(
        job_id=job_id,
        organization_id=org_id,
        job_type="dataset_ingestion",
        attempt=1,
        max_attempts=3,
    )

    output = await task.run(
        payload={"dataset_id": str(dataset_id), "batch_size": 500},
        context=context,
    )

    assert output["status"] == "completed"
    assert output["row_count"] == 500
    assert output["version"] == 1


@pytest.mark.asyncio
async def test_agent_runtime_dataset_tools() -> None:
    """Verify typed Agent Tools: dataset.list, dataset.get, dataset.profile, dataset.versions, dataset.quality."""
    org_id = uuid.uuid4()
    dataset_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_dataset = Dataset(
        id=dataset_id,
        organization_id=org_id,
        name="Metrics Dataset",
        description="Daily KPIs",
        source_type="csv",
        status="ready",
        current_version=2,
        row_count=1500,
        quality_score=0.94,
        classification="INTERNAL",
        profile_data={"row_count": 1500, "column_count": 5},
        quality_report={"score": 0.94, "null_ratio": 0.01},
    )

    col1 = DatasetColumn(
        dataset_id=dataset_id,
        name="kpi_name",
        normalized_name="kpi_name",
        data_type="string",
        nullable=False,
        ordinal_position=1,
    )
    mock_dataset.columns = [col1]

    v1 = DatasetVersion(
        id=uuid.uuid4(),
        dataset_id=dataset_id,
        organization_id=org_id,
        version=1,
        status="stale",
        row_count=1000,
        content_hash="h1",
        schema_hash="s1",
    )
    v2 = DatasetVersion(
        id=uuid.uuid4(),
        dataset_id=dataset_id,
        organization_id=org_id,
        version=2,
        status="ready",
        row_count=1500,
        content_hash="h2",
        schema_hash="s2",
    )

    mock_res_list = MagicMock()
    mock_res_list.scalars.return_value.all.return_value = [mock_dataset]
    mock_res_list.scalars.return_value.first.return_value = mock_dataset

    mock_res_versions = MagicMock()
    mock_res_versions.scalars.return_value.all.return_value = [v2, v1]

    async def mock_execute(stmt: Any) -> Any:
        sql_str = str(stmt).lower()
        if "from dataset_versions" in sql_str:
            return mock_res_versions
        return mock_res_list

    mock_session.execute.side_effect = mock_execute

    context = AgentExecutionContext(
        organization_id=org_id,
        session_id=uuid.uuid4(),
        step_id=uuid.uuid4(),
        db_session=mock_session,
        user_id=user_id,
    )

    # 1. dataset.list
    list_tool = DatasetListTool()
    v_list = await list_tool.validate({"limit": 10, "offset": 0})
    res_list = await list_tool.execute(v_list, context)
    assert res_list.success is True
    assert res_list.data["count"] == 1

    # 2. dataset.get
    get_tool = DatasetGetTool()
    v_get = await get_tool.validate({"dataset_id": str(dataset_id)})
    res_get = await get_tool.execute(v_get, context)
    assert res_get.success is True
    assert res_get.data["current_version"] == 2
    assert len(res_get.data["columns"]) == 1

    # 3. dataset.profile
    prof_tool = DatasetProfileTool()
    v_prof = await prof_tool.validate({"dataset_id": str(dataset_id)})
    res_prof = await prof_tool.execute(v_prof, context)
    assert res_prof.success is True
    assert res_prof.data["profile"]["row_count"] == 1500

    # 4. dataset.versions
    ver_tool = DatasetVersionsTool()
    v_ver = await ver_tool.validate({"dataset_id": str(dataset_id)})
    res_ver = await ver_tool.execute(v_ver, context)
    assert res_ver.success is True
    assert res_ver.data["count"] == 2

    # 5. dataset.quality
    qual_tool = DatasetQualityTool()
    v_qual = await qual_tool.validate({"dataset_id": str(dataset_id)})
    res_qual = await qual_tool.execute(v_qual, context)
    assert res_qual.success is True
    assert res_qual.data["quality_score"] == 0.94
