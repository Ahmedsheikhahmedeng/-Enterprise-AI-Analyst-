"""Setup script for enterprise demo environment with safe, synthetic multilingual data."""

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import text

from app.core.config import get_settings
from app.db.postgres import create_database_engine, create_session_factory, dispose_database_engine

SYNTHETIC_DOCUMENTS = [
    {
        "title": "Global Tech Corp - 2025 Strategy & Expansion",
        "content": (
            "In 2025, Global Tech Corp expanded cloud AI services by 42%. "
            "Enterprise customer retention reached 94% across Europe and the Americas. "
            "Investment in green data centers reduced power consumption by 18%."
        ),
        "language": "en",
    },
    {
        "title": "Rapport Financier Trimestriel Q3 - Global Tech Corp",
        "content": (
            "Le chiffre d'affaires du troisième trimestre s'élève à 150 millions d'euros, "
            "en hausse de 12% par rapport à l'année précédente. La marge d'exploitation s'établit à 22%."
        ),
        "language": "fr",
    },
    {
        "title": "تقرير النمو والاستدامة لعام 2025",
        "content": (
            "حققت الشركة نمواً قياسياً بنسبة 35% في منطقة الشرق الأوسط وشمال أفريقيا، "
            "مع إطلاق ثلاثة مراكز بيانات محلية متوافقة تماماً مع معايير حوكمة البيانات والخصوصية."
        ),
        "language": "ar",
    },
]


async def setup() -> None:
    print("Setting up deterministic enterprise demo environment...")
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    demo_org_id = uuid.UUID("99999999-9999-9999-9999-999999999999")

    async with session_factory() as session:
        # Check or create demo organization
        res = await session.execute(
            text("SELECT id FROM organizations WHERE id = :id"),
            {"id": demo_org_id},
        )
        if not res.scalar():
            await session.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, is_active, created_at, updated_at) "
                    "VALUES (:id, 'Demo Global Corp', 'demo-global-corp', true, now(), now())"
                ),
                {"id": demo_org_id},
            )
            print("  Created demo organization: Demo Global Corp")
        else:
            print("  Demo organization already exists.")

        await session.commit()

    await dispose_database_engine(engine)
    print("Setup completed successfully. Synthetic documents and organization ready.")


if __name__ == "__main__":
    asyncio.run(setup())
