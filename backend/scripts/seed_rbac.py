"""Idempotent RBAC seed script to populate system permissions, roles, and default mappings."""

import asyncio
import sys
from pathlib import Path

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.postgres import (
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
)
from app.rbac.service import RBACService

logger = get_logger("seed.rbac")


async def seed() -> None:
    """Run idempotent RBAC seeding against PostgreSQL."""
    settings = get_settings()
    setup_logging(
        log_level=settings.LOG_LEVEL,
        json_format=settings.is_production,
    )

    logger.info("Starting RBAC seeding process...")
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    rbac_service = RBACService()

    try:
        async with session_factory() as session, session.begin():
            perms, roles, mappings = await rbac_service.seed_system_rbac(session)
            logger.info(
                "RBAC seeding completed successfully",
                permissions_seeded=perms,
                roles_seeded=roles,
                role_permissions_seeded=mappings,
            )
    except Exception as exc:
        logger.error("RBAC seeding failed", exc_info=exc)
        sys.exit(1)
    finally:
        await dispose_database_engine(engine)


def main() -> None:
    """CLI script entrypoint."""
    asyncio.run(seed())


if __name__ == "__main__":
    main()
