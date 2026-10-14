import json
import logging
import sqlite3
from collections.abc import AsyncGenerator, Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import CheckConstraint, UniqueConstraint, event, text
from sqlalchemy.dialects.sqlite import dialect
from sqlalchemy.exc import DBAPIError
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


def validate_schema_version(tables: set[str], version: int | None) -> None:
    if tables and "instance_metadata" not in tables:
        raise RuntimeError(
            "Legacy proxy database detected. Stop Nashordaq, preserve the old database "
            "and its WAL/SHM files as a backup, then configure a separate empty "
            "data directory for standalone setup. Existing data is "
            "not migrated or deleted."
        )
    if "instance_metadata" in tables and version != 1:
        raise RuntimeError(
            "Unsupported standalone database version; "
            "use the matching code revision and backup."
        )


def validate_standalone_schema(
    execute: Callable[[str], Iterable[Any]],
) -> bool:
    """Inspect the complete initial standalone schema without changing storage."""
    from app.models import Base

    try:
        tables = {
            row[0]
            for row in execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        }
        if not tables:
            return False
        versions = (
            list(execute("SELECT id, schema_version FROM instance_metadata"))
            if "instance_metadata" in tables
            else []
        )
        validate_schema_version(tables, versions[0][1] if len(versions) == 1 else None)
        if versions[0][0] != 1:
            raise RuntimeError(
                "Invalid standalone schema marker; "
                "use the matching code revision and backup."
            )

        def incompatible(detail: str) -> None:
            raise RuntimeError(
                f"Standalone schema is incomplete or malformed: {detail}. "
                "Preserve the database and use the matching code revision and backup."
            )

        sqlite_dialect = dialect()
        for table in Base.metadata.sorted_tables:
            columns = {
                row[1]: row for row in execute(f'PRAGMA table_info("{table.name}")')
            }
            for column in table.columns:
                actual = columns.get(column.name)
                if actual is None or (
                    actual[2].upper()
                    != column.type.compile(dialect=sqlite_dialect).upper()
                    or bool(actual[3]) != (not column.nullable)
                    or bool(actual[5]) != column.primary_key
                ):
                    incompatible(f"{table.name}.{column.name}")
            unique_columns = set()
            for index in execute(f'PRAGMA index_list("{table.name}")'):
                name = index[1].replace('"', '""')
                if index[2] and not index[4]:
                    unique_columns.add(
                        tuple(row[2] for row in execute(f'PRAGMA index_info("{name}")'))
                    )
            required_unique = {
                tuple(column.name for column in constraint.columns)
                for constraint in table.constraints
                if isinstance(constraint, UniqueConstraint)
            } | {
                tuple(column.name for column in index.columns)
                for index in table.indexes
                if index.unique and index.dialect_options["sqlite"]["where"] is None
            }
            allowed_unique = required_unique | {
                tuple(column.name for column in table.primary_key.columns)
            }
            known_columns = {column.name for column in table.columns}
            if not required_unique.issubset(unique_columns) or any(
                set(columns).issubset(known_columns) and columns not in allowed_unique
                for columns in unique_columns
            ):
                incompatible(f"{table.name} uniqueness protection")
            foreign_keys = {
                (row[3], row[2], row[4], row[6])
                for row in execute(f'PRAGMA foreign_key_list("{table.name}")')
            }
            for key in table.foreign_keys:
                if (
                    key.parent.name,
                    key.column.table.name,
                    key.column.name,
                    key.ondelete or "NO ACTION",
                ) not in foreign_keys:
                    incompatible(f"{table.name} reference protection")
            table_sql = next(
                iter(
                    execute(
                        "SELECT sql FROM sqlite_master WHERE type='table' "
                        f"AND name='{table.name}'"
                    )
                )
            )[0]
            normalized = "".join(table_sql.lower().split())
            for constraint in table.constraints:
                if isinstance(constraint, CheckConstraint) and (
                    "".join(str(constraint.sqltext).lower().split()) not in normalized
                ):
                    incompatible(f"{table.name} check protection")
        sole_index = list(
            execute(
                "SELECT sql FROM sqlite_master WHERE type='index' "
                "AND name='sole_administrator' AND tbl_name='users'"
            )
        )
        if not sole_index or "".join(sole_index[0][0].lower().split()) != (
            "createuniqueindexsole_administratoronusers(is_admin)whereis_admin=1"
        ):
            incompatible("sole administrator protection")
        if list(
            execute(
                "SELECT id FROM users WHERE is_admin NOT IN (0, 1) "
                "OR is_demo NOT IN (0, 1) OR (is_admin=1 AND is_demo=1) LIMIT 1"
            )
        ):
            incompatible("administrator account state")
        administrator_count = next(
            iter(execute("SELECT count(*) FROM users WHERE is_admin=1 AND is_demo=0"))
        )[0]
        normal_members = next(
            iter(execute("SELECT count(*) FROM users WHERE is_demo=0"))
        )[0]
        completed_setup = list(
            execute(
                "SELECT id FROM access_tokens WHERE kind='setup' "
                "AND consumed_at IS NOT NULL LIMIT 1"
            )
        )
        if (normal_members or completed_setup) and administrator_count != 1:
            incompatible("existing sole administrator is missing")
        if list(execute("PRAGMA integrity_check")) != [("ok",)]:
            raise RuntimeError(
                "Database integrity check failed. Preserve it and use a healthy backup."
            )
        if list(execute("PRAGMA foreign_key_check")):
            raise RuntimeError(
                "Database references are inconsistent. "
                "Preserve it and use a healthy backup."
            )
    except (sqlite3.DatabaseError, DBAPIError):
        raise RuntimeError(
            "Malformed standalone database. Preserve it and use the matching code "
            "revision and a healthy backup."
        ) from None
    return True


def validate_existing_database(path: Path) -> None:
    """Check an operator-selected SQLite file before opening it for mutation."""
    if not path.is_file():
        raise RuntimeError("Select an existing standalone SQLite database file.")
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        if not validate_standalone_schema(connection.execute):
            raise RuntimeError(
                "The database has no standalone installation to recover."
            )


async def init_db() -> None:
    from app.models import Base

    async with engine.begin() as conn:
        existing = await conn.run_sync(
            lambda connection: validate_standalone_schema(connection.exec_driver_sql)
        )
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.run_sync(Base.metadata.create_all)
        if not existing:
            await conn.execute(
                text("INSERT INTO instance_metadata (id, schema_version) VALUES (1, 1)")
            )

    if settings.demo_mode_enabled:
        await _seed_demo_data()

    from app.identities import backfill_aliases

    async with SessionLocal() as session:
        await backfill_aliases(session)
        await session.commit()


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
