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
