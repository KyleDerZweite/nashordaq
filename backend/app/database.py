import json
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

logger = logging.getLogger(__name__)
DEMO_SEED_PATH = (
    Path(__file__).resolve().parent.parent.parent / "demo" / "demo_seed.json"
)

engine = create_async_engine(settings.database_url, echo=False)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_conn: Any, _connection_record: Any) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=15000")
    cursor.close()


SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    from app.models import Base

    async with engine.begin() as conn:
        tables = set(
            (
                await conn.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name NOT LIKE 'sqlite_%'"
                    )
                )
            ).scalars()
        )
        if tables and "instance_metadata" not in tables:
            raise RuntimeError(
                "Legacy proxy database detected. Stop Nashordaq, preserve "
                "the old database "
                "and its WAL/SHM files as a backup, then configure a separate empty "
                "data directory for standalone setup. Existing data is "
                "not migrated or deleted."
            )
        if "instance_metadata" in tables:
            version = await conn.scalar(
                text("SELECT schema_version FROM instance_metadata WHERE id=1")
            )
            if version != 1:
                raise RuntimeError(
                    "Unsupported standalone database version; "
                    "use the matching release and backup."
                )
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.run_sync(Base.metadata.create_all)
        if not tables:
            await conn.execute(
                text("INSERT INTO instance_metadata (id, schema_version) VALUES (1, 1)")
            )

    if settings.demo_mode_enabled:
        await _seed_demo_data()


async def _seed_demo_data() -> None:
    if not DEMO_SEED_PATH.exists():
        logger.warning(
            "Demo seed file not found at %s; skipping seed import",
            DEMO_SEED_PATH,
        )
        return

    async with SessionLocal() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM tracked_players"))
        count = result.scalar()
        if count and count > 0:
            return

        seed = json.loads(DEMO_SEED_PATH.read_text())
        now = datetime.now(UTC).isoformat()

        for player in seed.get("players", []):
            await session.execute(
                text(
                    "INSERT INTO tracked_players "
                    "(id, game_name, tag_line, display_name, puuid, summoner_id, "
                    "current_price, lp_abs, previous_lp_abs, streak, "
                    "ranked_wins_snapshot, ranked_losses_snapshot, "
                    "avg_lp_gain_on_win, avg_lp_loss_on_loss, last_updated) "
                    "VALUES (:id, :game_name, :tag_line, :display_name, :puuid, "
                    ":summoner_id, :current_price, :lp_abs, :previous_lp_abs, "
                    ":streak, :ranked_wins_snapshot, :ranked_losses_snapshot, "
                    ":avg_lp_gain_on_win, :avg_lp_loss_on_loss, :last_updated)"
                ),
                {**player, "last_updated": now},
            )

        for ph in seed.get("price_history", []):
            await session.execute(
                text(
                    "INSERT INTO price_history (player_id, price, lp_abs, recorded_at) "
                    "VALUES (:player_id, :price, :lp_abs, :recorded_at)"
                ),
                ph,
            )

        await session.commit()
        logger.info(
            "Seeded demo data: %d players, %d price history entries",
            len(seed.get("players", [])),
            len(seed.get("price_history", [])),
        )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
