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
