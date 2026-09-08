"""Infrastructure tests validating Docker Compose production specifications and security policies."""

from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
COMPOSE_PROD_PATH = REPO_ROOT / "infra" / "compose" / "docker-compose.prod.yml"


@pytest.fixture
def prod_compose_data() -> dict[str, Any]:
    """Load and parse docker-compose.prod.yml."""
    assert COMPOSE_PROD_PATH.is_file(), f"Missing production compose file: {COMPOSE_PROD_PATH}"
    with open(COMPOSE_PROD_PATH, encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f)
    return data


def test_compose_services_presence(prod_compose_data: dict[str, Any]) -> None:
    """Verify that all 6 required services exist in production compose."""
    services = prod_compose_data.get("services", {})
    required_services = {"frontend", "backend", "worker", "postgres", "redis", "qdrant"}
    assert required_services.issubset(set(services.keys()))


def test_network_segmentation_rules(prod_compose_data: dict[str, Any]) -> None:
    """Verify that networks are segmented and data_net is completely internal."""
    networks = prod_compose_data.get("networks", {})
    assert "frontend_net" in networks
    assert "backend_net" in networks
    assert "data_net" in networks
    assert networks["data_net"].get("internal") is True

    services = prod_compose_data.get("services", {})
    # Data services must strictly be isolated to data_net
    assert services["postgres"]["networks"] == ["data_net"]
    assert services["redis"]["networks"] == ["data_net"]
    assert services["qdrant"]["networks"] == ["data_net"]

    # Frontend must not have access to data_net
    assert "data_net" not in services["frontend"]["networks"]


def test_no_public_database_ports(prod_compose_data: dict[str, Any]) -> None:
    """Verify that postgres, redis, and qdrant do NOT expose ports to host in production."""
    services = prod_compose_data.get("services", {})
    for service_name in ["postgres", "redis", "qdrant"]:
        ports = services[service_name].get("ports")
        assert not ports, (
            f"Security violation: Service '{service_name}' exposes host ports in production compose!"
        )


def test_container_security_hardening(prod_compose_data: dict[str, Any]) -> None:
    """Verify that application containers have no-new-privileges and drop capabilities."""
    services = prod_compose_data.get("services", {})
    for app_svc in ["frontend", "backend", "worker"]:
        svc_cfg = services[app_svc]
        sec_opt = svc_cfg.get("security_opt", [])
        assert "no-new-privileges:true" in sec_opt, f"Service {app_svc} missing no-new-privileges"
        cap_drop = svc_cfg.get("cap_drop", [])
        assert "ALL" in cap_drop, f"Service {app_svc} must drop ALL capabilities"


def test_resource_limits_enforced(prod_compose_data: dict[str, Any]) -> None:
    """Verify that all services declare explicit CPU, memory, and PID limits."""
    services = prod_compose_data.get("services", {})
    for svc_name, svc_cfg in services.items():
        deploy = svc_cfg.get("deploy", {})
        resources = deploy.get("resources", {})
        limits = resources.get("limits", {})
        assert "cpus" in limits, f"Service {svc_name} missing CPU limit"
        assert "memory" in limits, f"Service {svc_name} missing Memory limit"
        assert "pids" in limits, f"Service {svc_name} missing PIDs limit"


def test_pinned_backing_image_versions(prod_compose_data: dict[str, Any]) -> None:
    """Verify that database images are pinned to specific versions rather than 'latest'."""
    services = prod_compose_data.get("services", {})
    for svc_name in ["postgres", "redis", "qdrant"]:
        image = services[svc_name].get("image", "")
        assert image, f"Service {svc_name} must specify a pinned image"
        assert not image.endswith(":latest"), f"Service {svc_name} must not use ':latest' tag"
