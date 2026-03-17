from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_wal(dbapi_conn: Any, _connection_record: Any) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
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


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
