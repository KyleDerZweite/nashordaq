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

        result = await conn.execute(text("PRAGMA table_info(holding_lots)"))
        columns = {row[1] for row in result.fetchall()}
        if "buy_order_id" not in columns:
            await conn.execute(
                text("ALTER TABLE holding_lots ADD COLUMN buy_order_id INTEGER")
            )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
