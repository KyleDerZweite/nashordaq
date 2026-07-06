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
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=15000")
    cursor.close()


SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    from app.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        user_cols_result = await conn.execute(text("PRAGMA table_info(users)"))
        user_columns = {row[1] for row in user_cols_result.fetchall()}
        if "email" not in user_columns:
            await conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255)"))
            # Backfill email from username for existing rows
            await conn.execute(text("UPDATE users SET email = username"))
        if "display_name" not in user_columns:
            await conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN display_name VARCHAR(255) DEFAULT ''"
                )
            )
            # Backfill display_name from username for existing rows
            await conn.execute(text("UPDATE users SET display_name = username"))
        if "linked_player_id" not in user_columns:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN linked_player_id INTEGER")
            )
        if "debt_principal" not in user_columns:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN debt_principal FLOAT DEFAULT 0.0")
            )
        if "debt_accrued_interest" not in user_columns:
            await conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN debt_accrued_interest "
                    "FLOAT DEFAULT 0.0"
                )
            )
        if "debt_last_accrued_at" not in user_columns:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN debt_last_accrued_at DATETIME")
            )
        if "debt_next_accrual_at" not in user_columns:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN debt_next_accrual_at DATETIME")
            )
        if "rescue_loan_uses_remaining" not in user_columns:
            await conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN rescue_loan_uses_remaining "
                    "INTEGER DEFAULT 1"
                )
            )
            await conn.execute(
                text(
                    "UPDATE users SET rescue_loan_uses_remaining = CASE "
                    "WHEN EXISTS ("
                    "SELECT 1 FROM bank_ledger_entries "
                    "WHERE bank_ledger_entries.user_id = users.id "
                    "AND bank_ledger_entries.entry_type = 'BORROW'"
                    ") THEN 0 ELSE 1 END"
                )
            )
        if "is_demo" not in user_columns:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN is_demo BOOLEAN DEFAULT 0")
            )

        tracked_player_cols_result = await conn.execute(
            text("PRAGMA table_info(tracked_players)")
        )
        tracked_player_columns = {
            row[1] for row in tracked_player_cols_result.fetchall()
        }
        if "last_playing_income_match_id" not in tracked_player_columns:
            await conn.execute(
                text(
                    "ALTER TABLE tracked_players "
                    "ADD COLUMN last_playing_income_match_id VARCHAR(64)"
                )
            )
        if "last_playing_income_match_end_at" not in tracked_player_columns:
            await conn.execute(
                text(
                    "ALTER TABLE tracked_players "
                    "ADD COLUMN last_playing_income_match_end_at DATETIME"
                )
            )
        if "ranked_wins_snapshot" not in tracked_player_columns:
            await conn.execute(
                text(
                    "ALTER TABLE tracked_players "
                    "ADD COLUMN ranked_wins_snapshot INTEGER"
                )
            )
        if "ranked_losses_snapshot" not in tracked_player_columns:
            await conn.execute(
                text(
                    "ALTER TABLE tracked_players "
                    "ADD COLUMN ranked_losses_snapshot INTEGER"
                )
            )
        if "avg_lp_gain_on_win" not in tracked_player_columns:
            await conn.execute(
                text("ALTER TABLE tracked_players ADD COLUMN avg_lp_gain_on_win FLOAT")
            )
        if "avg_lp_loss_on_loss" not in tracked_player_columns:
            await conn.execute(
                text("ALTER TABLE tracked_players ADD COLUMN avg_lp_loss_on_loss FLOAT")
            )
        if "last_match_pricing_at" not in tracked_player_columns:
            await conn.execute(
                text(
                    "ALTER TABLE tracked_players "
                    "ADD COLUMN last_match_pricing_at DATETIME"
                )
            )

        result = await conn.execute(text("PRAGMA table_info(holding_lots)"))
        columns = {row[1] for row in result.fetchall()}
        if "buy_order_id" not in columns:
            await conn.execute(
                text("ALTER TABLE holding_lots ADD COLUMN buy_order_id INTEGER")
            )

        order_cols_result = await conn.execute(text("PRAGMA table_info(orders)"))
        order_columns = {row[1] for row in order_cols_result.fetchall()}
        if "quantity_value" not in order_columns:
            await conn.execute(
                text("ALTER TABLE orders ADD COLUMN quantity_value FLOAT")
            )
        if "source" not in order_columns:
            await conn.execute(
                text(
                    "ALTER TABLE orders ADD COLUMN source VARCHAR(10) DEFAULT 'MANUAL'"
                )
            )
        if "gross_execution_price" not in order_columns:
            await conn.execute(
                text("ALTER TABLE orders ADD COLUMN gross_execution_price FLOAT")
            )
        if "gross_total_value" not in order_columns:
            await conn.execute(
                text("ALTER TABLE orders ADD COLUMN gross_total_value FLOAT")
            )
        if "entry_total_value" not in order_columns:
            await conn.execute(
                text("ALTER TABLE orders ADD COLUMN entry_total_value FLOAT")
            )
        if "adjustment_value" not in order_columns:
            await conn.execute(
                text("ALTER TABLE orders ADD COLUMN adjustment_value FLOAT")
            )
        if "adjustment_reason" not in order_columns:
            await conn.execute(
                text("ALTER TABLE orders ADD COLUMN adjustment_reason VARCHAR(32)")
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
