"""Configuration parameters for report generation, versioning, and export."""

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class ReportConfig:
    """Settings governing report construction, rendering limits, and formatting."""

    max_findings: int = 10
    max_metrics: int = 20
    max_table_rows: int = 100
    default_template: str = "executive"
    generator_version: str = "1.0.0"
    prompt_version: str = "1.0.0"
    template_version: str = "1.0.0"
    pdf_page_size: str = "A4"


@lru_cache(maxsize=1)
def get_report_config() -> ReportConfig:
    """Return cached singleton ReportConfig."""
    return ReportConfig()
