"""Base abstract renderer interface for all report output formats."""

from abc import ABC, abstractmethod
from typing import Any

from app.reports.models import ReportDocument


class BaseReportRenderer(ABC):
    """Abstract interface implemented by Markdown, HTML, and PDF renderers."""

    @abstractmethod
    def render(self, doc: ReportDocument, **kwargs: Any) -> str | bytes:
        """Render the structured ReportDocument into its target output format."""
        raise NotImplementedError
