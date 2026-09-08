"""Thread-safe ConnectorRegistry mapping connector types to connector factories."""

import threading
from collections.abc import Callable

from app.connectors.domain.enums import ConnectorType
from app.connectors.domain.errors import InvalidConfigurationError
from app.connectors.domain.protocols import DataConnector
from app.connectors.infrastructure.csv.connector import CSVConnector
from app.connectors.infrastructure.excel.connector import ExcelConnector
from app.connectors.infrastructure.postgres.connector import PostgreSQLConnector


class ConnectorRegistry:
    """Thread-safe registry of data connector implementations."""

    def __init__(self, register_defaults: bool = True) -> None:
        self._lock = threading.Lock()
        self._factories: dict[str, Callable[[], DataConnector]] = {}
        if register_defaults:
            from app.connectors.infrastructure.csv.connector import CSVConnector
            from app.connectors.infrastructure.excel.connector import ExcelConnector
            from app.connectors.infrastructure.postgres.connector import PostgreSQLConnector

            self.register(ConnectorType.POSTGRESQL, PostgreSQLConnector)
            self.register(ConnectorType.CSV, CSVConnector)
            self.register(ConnectorType.EXCEL, ExcelConnector)

    def register(
        self,
        connector_type: str | ConnectorType,
        factory: Callable[[], DataConnector] | type[DataConnector],
    ) -> None:
        """Register a connector implementation or factory callable."""
        key = str(
            connector_type.value if hasattr(connector_type, "value") else connector_type
        ).lower()
        callable_factory: Callable[[], DataConnector] = factory

        with self._lock:
            self._factories[key] = callable_factory

    def get(self, connector_type: str | ConnectorType) -> DataConnector:
        """Instantiate and return connector for requested type; raises InvalidConfigurationError if unknown."""
        key = str(
            connector_type.value if hasattr(connector_type, "value") else connector_type
        ).lower()
        with self._lock:
            factory = self._factories.get(key)
        if not factory:
            supported = ", ".join(self.list_types())
            raise InvalidConfigurationError(
                key, f"Unknown connector type '{key}'. Supported types are: {supported}"
            )
        return factory()

    def has(self, connector_type: str | ConnectorType) -> bool:
        """Check if connector type is registered."""
        key = str(
            connector_type.value if hasattr(connector_type, "value") else connector_type
        ).lower()
        with self._lock:
            return key in self._factories

    def list_types(self) -> list[str]:
        """Return list of all registered connector types."""
        with self._lock:
            return sorted(self._factories.keys())


_global_connector_registry: ConnectorRegistry | None = None
_registry_lock = threading.Lock()


def get_connector_registry() -> ConnectorRegistry:
    """Singleton getter returning initialized ConnectorRegistry with production connectors."""
    global _global_connector_registry
    if _global_connector_registry is None:
        with _registry_lock:
            if _global_connector_registry is None:
                registry = ConnectorRegistry()
                registry.register(ConnectorType.POSTGRESQL, PostgreSQLConnector)
                registry.register(ConnectorType.CSV, CSVConnector)
                registry.register(ConnectorType.EXCEL, ExcelConnector)
                _global_connector_registry = registry
    return _global_connector_registry
