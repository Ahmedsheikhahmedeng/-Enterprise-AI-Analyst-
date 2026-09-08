"""Reset script to clean synthetic demo data while preserving platform configurations."""

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import text

from app.core.config import get_settings
from app.db.postgres import create_database_engine, create_session_factory, dispose_database_engine


async def reset() -> None:
    print("Resetting demo environment...")
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    demo_org_id = uuid.UUID("99999999-9999-9999-9999-999999999999")

    async with session_factory() as session:
        # Clean demo org safely if present
        await session.execute(
            text("DELETE FROM organizations WHERE id = :id"),
            {"id": demo_org_id},
        )
        await session.commit()
        print("  Demo organization cleaned.")

    await dispose_database_engine(engine)
    print("Demo environment reset complete.")


if __name__ == "__main__":
    asyncio.run(reset())
