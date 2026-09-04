from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Schema for basic service health check response."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(
        default="ok",
        description="Health status indicator",
        examples=["ok"],
    )
    service: str = Field(
        default="enterprise-ai-analyst",
        description="Standardized name of the service",
        examples=["enterprise-ai-analyst"],
    )
    version: str = Field(
        default="0.1.0",
        description="Active application release version",
        examples=["0.1.0"],
    )


class LivenessResponse(BaseModel):
    """Schema for Kubernetes / container process liveness check."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"] = Field(
        default="ok",
        description="Process liveness state",
        examples=["ok"],
    )
    service: str = Field(
        default="enterprise-ai-analyst",
        description="Standardized name of the service",
        examples=["enterprise-ai-analyst"],
    )


class DependencyStatus(BaseModel):
    """Reachability status for external backing infrastructure services."""

    model_config = ConfigDict(frozen=True)

    postgresql: Literal["ok", "unavailable"] = Field(
        ...,
        description="PostgreSQL relational database connectivity status",
        examples=["ok"],
    )
    redis: Literal["ok", "unavailable"] = Field(
        ...,
        description="Redis in-memory caching and message broker connectivity status",
        examples=["ok"],
    )
    qdrant: Literal["ok", "unavailable"] = Field(
        ...,
        description="Qdrant vector engine connectivity status",
        examples=["ok"],
    )


class ReadinessResponse(BaseModel):
    """Schema for service readiness check evaluating required infrastructure."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "unhealthy"] = Field(
        ...,
        description="Overall service readiness state",
        examples=["ok"],
    )
    service: str = Field(
        default="enterprise-ai-analyst",
        description="Standardized name of the service",
        examples=["enterprise-ai-analyst"],
    )
    dependencies: DependencyStatus = Field(
        ...,
        description="Granular health states of downstream backing infrastructure",
    )
