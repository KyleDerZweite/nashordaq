"""Supported update and rejection observed through startup and operator commands."""

import sqlite3

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import database


async def test_startup_rejects_incomplete_standalone_before_creating_or_changing_data(
    tmp_path, monkeypatch
):
    path = tmp_path / "incomplete.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE instance_metadata "
            "(id INTEGER PRIMARY KEY, schema_version INTEGER)"
        )
        connection.execute("INSERT INTO instance_metadata VALUES (1, 1)")
    original = path.read_bytes()
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", async_sessionmaker(engine))
    try:
        with pytest.raises(RuntimeError, match="matching code revision"):
            await database.init_db()
    finally:
        await engine.dispose()
    assert path.read_bytes() == original
    assert set(tmp_path.iterdir()) == {path}


async def test_startup_refuses_missing_sole_administrator_protection(
    tmp_path, monkeypatch
):
    from sqlalchemy import create_engine

    from app.models import Base

    path = tmp_path / "unprotected.db"
    setup = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(setup)
    setup.dispose()
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO instance_metadata VALUES (1, 1)")
        connection.execute("DROP INDEX sole_administrator")
    original = path.read_bytes()
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", async_sessionmaker(engine))
    try:
        with pytest.raises(RuntimeError, match="matching code revision"):
            await database.init_db()
    finally:
        await engine.dispose()
    assert path.read_bytes() == original
    assert set(tmp_path.iterdir()) == {path}


def test_candidate_update_preflight_preserves_complete_supported_database(tmp_path):
    import subprocess
    import sys

    from sqlalchemy import create_engine

    from app.models import Base

    path = tmp_path / "supported.db"
    setup = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(setup)
    setup.dispose()
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO instance_metadata VALUES (1, 1)")
        connection.execute("CREATE TABLE operator_extension (notes TEXT)")
        connection.execute(
            "INSERT INTO operator_extension VALUES ('retain additive state')"
        )
    original = path.read_bytes()
    result = subprocess.run(
        [sys.executable, "-m", "app.operator", "check-update", "--database", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "schema version 1" in result.stdout
    assert path.read_bytes() == original
    assert set(tmp_path.iterdir()) == {path}


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE instance_metadata SET schema_version=999",
        "INSERT INTO instance_metadata VALUES (2, 1)",
        "ALTER TABLE users RENAME COLUMN password_hash TO old_password_hash",
        "DROP INDEX ix_users_username",
        "CREATE UNIQUE INDEX unexpected_admin ON users(is_admin)",
        "INSERT INTO auth_sessions VALUES ('orphan', 987, '2030-01-01', '2026-01-01')",
    ],
)
async def test_rejected_candidate_never_repairs_or_discards_existing_state(
    tmp_path, monkeypatch, mutation
):
    from sqlalchemy import create_engine

    from app.models import Base

    path = tmp_path / "synthetic-invalid.db"
    setup = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(setup)
    setup.dispose()
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO instance_metadata VALUES (1, 1)")
        connection.execute(mutation)
    original = path.read_bytes()
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", async_sessionmaker(engine))
    try:
        with pytest.raises(RuntimeError):
            await database.init_db()
    finally:
        await engine.dispose()
    assert path.read_bytes() == original
    assert set(tmp_path.iterdir()) == {path}


async def test_existing_member_without_administrator_cannot_reopen_setup(
    tmp_path, monkeypatch
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.models import Base, InstanceMetadata, User

    path = tmp_path / "synthetic-lost-administrator.db"
    setup = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(setup)
    with Session(setup) as session:
        session.add(InstanceMetadata(id=1, schema_version=1))
        session.add(
            User(username="retained-member", password_hash="unusable fixture verifier")
        )
        session.commit()
    setup.dispose()
    original = path.read_bytes()
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", async_sessionmaker(engine))
    try:
        with pytest.raises(RuntimeError, match="administrator"):
            await database.init_db()
    finally:
        await engine.dispose()
    assert path.read_bytes() == original
    assert set(tmp_path.iterdir()) == {path}
