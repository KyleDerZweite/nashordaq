"""Observe the operator CLI against real SQLite files, including active WAL writes."""

import itertools
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.models import Base


def run_operator(*arguments: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "app.operator", *map(str, arguments)],
        capture_output=True,
        text=True,
        timeout=90,
    )


def create_instance(path: Path) -> sqlite3.Connection:
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    connection = sqlite3.connect(path)
    connection.execute("INSERT INTO instance_metadata VALUES (1, 1)")
    connection.commit()
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA wal_autocheckpoint=0")
    return connection


def test_live_backup_includes_committed_wal_and_keeps_transactions_coherent(tmp_path):
    source = tmp_path / "live.db"
    snapshot = tmp_path / "snapshot.db"
    keeper = create_instance(source)
    keeper.executescript(
        "CREATE TABLE future_balance (id INTEGER PRIMARY KEY, balance INTEGER);"
        "INSERT INTO future_balance VALUES (1, 1000);"
        "CREATE TABLE future_history (id INTEGER PRIMARY KEY, amount INTEGER);"
        "INSERT INTO future_history VALUES (1, 7);"
        "UPDATE future_balance SET balance=993;"
    )
    assert Path(str(source) + "-wal").stat().st_size > 0
    with sqlite3.connect(source.as_uri() + "?immutable=1", uri=True) as main_only:
        assert (
            main_only.execute(
                "SELECT name FROM sqlite_master WHERE name='future_history'"
            ).fetchone()
            is None
        )
    stop = threading.Event()
    started = threading.Event()
    failures = []

    def active_writer():
        try:
            with sqlite3.connect(source, timeout=15) as writer:
                writer.execute("PRAGMA wal_autocheckpoint=0")
                for number in itertools.count(2):
                    if stop.is_set():
                        break
                    with writer:
                        writer.execute(
                            "INSERT INTO future_history VALUES (?, 1)", (number,)
                        )
                        writer.execute("UPDATE future_balance SET balance=balance-1")
                    started.set()
                    stop.wait(0.001)
        except Exception as error:
            failures.append(error)

    thread = threading.Thread(target=active_writer)
    thread.start()
    try:
        assert started.wait(5)
        result = run_operator("backup", "--database", source, "--output", snapshot)
        assert result.returncode == 0, result.stderr
        assert thread.is_alive(), (
            "Writes must continue through the entire backup command"
        )
        assert "Backup created" in result.stdout
        with sqlite3.connect(snapshot) as saved:
            balance = saved.execute("SELECT balance FROM future_balance").fetchone()[0]
            total, count = saved.execute(
                "SELECT sum(amount), count(*) FROM future_history"
            ).fetchone()
            assert balance + total == 1000
            assert count >= 2
            assert saved.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert saved.execute("PRAGMA journal_mode").fetchone() == ("delete",)
        assert snapshot.stat().st_mode & 0o777 == 0o600
        assert not Path(str(snapshot) + "-wal").exists()
        assert not Path(str(snapshot) + "-shm").exists()
    finally:
        stop.set()
        thread.join(timeout=20)
        keeper.close()
    assert not thread.is_alive()
    assert not failures


async def test_fresh_restore_recovers_credentials_sessions_setup_and_trade_history(
    tmp_path, monkeypatch, caplog
):
    import logging
    import re
    from datetime import UTC, datetime

    import httpx
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app import database, main
    from app.config import settings
    from app.database import get_session
    from app.main import app
    from app.models import TrackedPlayer, User

    source = tmp_path / "live.db"
    snapshot = tmp_path / "snapshot.db"
    restored = tmp_path / "restored.db"
    keeper = create_instance(source)
    instance_engine = create_async_engine(f"sqlite+aiosqlite:///{source}")
    factory = async_sessionmaker(instance_engine, expire_on_commit=False)
    monkeypatch.setattr(settings, "demo_mode_enabled", False)
    monkeypatch.setattr(database, "engine", instance_engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(main, "SessionLocal", factory)
    caplog.set_level(logging.INFO)
    await main.initialize_instance()
    token = re.search(r"/setup\?token=([A-Za-z0-9_-]+)", caplog.text)[1]

    async def sessions():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    transport = httpx.ASGITransport(app=app)
    options = {
        "transport": transport,
        "base_url": "http://test",
        "headers": {"X-Nashordaq-CSRF": "1"},
    }
    try:
        async with (
            httpx.AsyncClient(**options) as admin,
            httpx.AsyncClient(**options) as member,
        ):
            setup = await admin.post(
                "/api/auth/setup",
                json={
                    "token": token,
                    "username": "operator",
                    "password": "operator secure password",
                },
            )
            assert setup.status_code == 201
            invite = (await admin.post("/api/auth/invites")).json()
            invite_token = re.search(r"/invite\?token=([A-Za-z0-9_-]+)", invite["url"])[
                1
            ]
            joined = await member.post(
                "/api/auth/register",
                json={
                    "token": invite_token,
                    "username": "friend",
                    "password": "member secure password",
                },
            )
            assert joined.status_code == 201
            member_id = (await member.get("/api/user/me")).json()["id"]
            # Explicit market fixture substitutes no live Riot provider.
            async with factory() as session:
                own = TrackedPlayer(
                    game_name="Own",
                    tag_line="EUW",
                    display_name="Own",
                    current_price=10,
                    lp_abs=1200,
                    last_updated=datetime.now(UTC),
                )
                tradable = TrackedPlayer(
                    game_name="Tradable",
                    tag_line="EUW",
                    display_name="Tradable",
                    current_price=25,
                    lp_abs=1500,
                    last_updated=datetime.now(UTC),
                )
                session.add_all([own, tradable])
                await session.flush()
                (await session.get(User, member_id)).linked_player_id = own.id
                await session.commit()
                player_id = tradable.id
            order = await member.post(
                "/api/orders",
                json={"player_id": player_id, "side": "BUY", "quantity": 2},
            )
            assert order.status_code == 201
            expected_me = (await member.get("/api/user/me")).json()
            expected_portfolio = (await member.get("/api/portfolio")).json()
            expected_orders = (await member.get("/api/orders")).json()
            expected_market = (
                await member.get(f"/api/market/players/{player_id}")
            ).json()
            expected_invites = (await admin.get("/api/auth/invites")).json()
            saved_admin_id = (await admin.get("/api/user/me")).json()["id"]
            assert Path(str(source) + "-wal").stat().st_size > 0
            result = run_operator("backup", "--database", source, "--output", snapshot)
            assert result.returncode == 0, result.stderr
            assert (
                await member.post(
                    "/api/orders",
                    json={"player_id": player_id, "side": "BUY", "quantity": 1},
                )
            ).status_code == 201
            assert len((await member.get("/api/orders")).json()) == 2
            snapshot_bytes = snapshot.read_bytes()
            result = run_operator(
                "restore", "--backup", snapshot, "--database", restored
            )
            assert result.returncode == 0, result.stderr
            assert "Restore completed" in result.stdout
            assert snapshot.read_bytes() == snapshot_bytes
            await instance_engine.dispose()
            instance_engine = create_async_engine(f"sqlite+aiosqlite:///{restored}")
            factory = async_sessionmaker(instance_engine, expire_on_commit=False)
            monkeypatch.setattr(database, "engine", instance_engine)
            monkeypatch.setattr(database, "SessionLocal", factory)
            monkeypatch.setattr(main, "SessionLocal", factory)
            caplog.clear()
            await main.initialize_instance()
            assert "Initial administrator setup" not in caplog.text
            assert (await admin.get("/api/auth/status")).json()[
                "setup_required"
            ] is False
            assert (await admin.get("/api/user/me")).json()["id"] == saved_admin_id
            assert (await admin.get("/api/user/me")).json()["role"] == "admin"
            assert (await admin.get("/api/auth/invites")).json() == expected_invites
            assert (await member.get("/api/user/me")).json() == expected_me
            assert (await member.get("/api/portfolio")).json() == expected_portfolio
            assert (await member.get("/api/orders")).json() == expected_orders
            assert (
                await member.get(f"/api/market/players/{player_id}")
            ).json() == expected_market
            for browser, username, password in [
                (admin, "operator", "operator secure password"),
                (member, "friend", "member secure password"),
            ]:
                browser.cookies.clear()
                assert (
                    await browser.post(
                        "/api/auth/login",
                        json={"username": username, "password": password},
                    )
                ).status_code == 200
            assert (
                await admin.post(
                    "/api/auth/setup",
                    json={
                        "token": token,
                        "username": "second-admin",
                        "password": "operator secure password",
                    },
                )
            ).status_code == 400
    finally:
        app.dependency_overrides.clear()
        await instance_engine.dispose()
        keeper.close()


def test_restore_refuses_incomplete_schema_without_publishing_or_changing_backup(
    tmp_path,
):
    source = tmp_path / "incomplete.db"
    destination = tmp_path / "fresh.db"
    with sqlite3.connect(source) as incomplete:
        incomplete.execute(
            "CREATE TABLE instance_metadata "
            "(id INTEGER PRIMARY KEY, schema_version INTEGER)"
        )
        incomplete.execute("INSERT INTO instance_metadata VALUES (1, 1)")
    before = source.read_bytes()
    result = run_operator("restore", "--backup", source, "--database", destination)
    assert result.returncode == 1
    assert "matching code revision" in result.stderr
    assert source.read_bytes() == before
    assert set(tmp_path.iterdir()) == {source}


@pytest.mark.parametrize("command", ["backup", "restore"])
@pytest.mark.parametrize(
    "obstacle",
    ["file", "-wal", "-shm", "-journal", "symlink", "dangling-symlink", "directory"],
)
def test_operator_preserves_existing_destination_and_unrelated_data(
    tmp_path, command, obstacle
):
    source = tmp_path / "source.db"
    keeper = create_instance(source)
    keeper.close()
    before = source.read_bytes()
    destination = tmp_path / "destination.db"
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_bytes(b"Keep this unrelated installation intact.")
    if obstacle == "directory":
        destination.mkdir()
    elif obstacle in {"symlink", "dangling-symlink"}:
        destination.symlink_to(
            unrelated if obstacle == "symlink" else tmp_path / "absent.db"
        )
    else:
        Path(
            str(destination) + (obstacle if obstacle.startswith("-") else "")
        ).write_bytes(b"Existing state")
    source_flag, target_flag = (
        ("--database", "--output")
        if command == "backup"
        else ("--backup", "--database")
    )
    result = run_operator(command, source_flag, source, target_flag, destination)
    assert result.returncode == 1
    assert "already exists" in result.stderr
    assert source.read_bytes() == before
    assert unrelated.read_bytes() == b"Keep this unrelated installation intact."
    if obstacle == "directory":
        assert destination.is_dir()
    elif obstacle in {"symlink", "dangling-symlink"}:
        assert destination.is_symlink()
    else:
        assert (
            Path(
                str(destination) + (obstacle if obstacle.startswith("-") else "")
            ).read_bytes()
            == b"Existing state"
        )


@pytest.mark.parametrize(
    "failure", ["missing", "legacy", "version", "corrupt", "foreign-key"]
)
def test_backup_rejects_unusable_sources_without_changing_source_or_publishing(
    tmp_path, failure
):
    source = tmp_path / "source.db"
    destination = tmp_path / "snapshot.db"
    if failure == "legacy":
        with sqlite3.connect(source) as legacy:
            legacy.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
    elif failure == "corrupt":
        source.write_bytes(b"This is not a SQLite database.")
    elif failure != "missing":
        keeper = create_instance(source)
        if failure == "version":
            keeper.execute("UPDATE instance_metadata SET schema_version=999")
        else:
            keeper.execute(
                "INSERT INTO auth_sessions "
                "(token_hash, user_id, expires_at, created_at) "
                "VALUES ('orphan', 999, '2099-01-01', '2026-10-14')"
            )
        keeper.commit()
        keeper.close()
    before = source.read_bytes() if source.exists() else None
    result = run_operator("backup", "--database", source, "--output", destination)
    assert result.returncode == 1
    assert result.stderr.strip()
    assert "Traceback" not in result.stderr
    assert not destination.exists()
    assert (source.read_bytes() if source.exists() else None) == before
    assert set(tmp_path.iterdir()).issubset(
        {source, Path(str(source) + "-wal"), Path(str(source) + "-shm")}
    )


@pytest.mark.parametrize("command", ["backup", "restore"])
def test_operator_requires_absolute_paths_and_an_existing_destination_directory(
    tmp_path, command
):
    source = tmp_path / "source.db"
    create_instance(source).close()
    source_flag, target_flag = (
        ("--database", "--output")
        if command == "backup"
        else ("--backup", "--database")
    )
    result = run_operator(command, source_flag, source, target_flag, "relative.db")
    assert result.returncode == 1
    assert "absolute paths" in result.stderr
    result = run_operator(
        command, source_flag, source, target_flag, tmp_path / "absent" / "new.db"
    )
    assert result.returncode == 1
    assert "destination directory" in result.stderr
    assert set(tmp_path.iterdir()) == {source}


def test_competing_backups_publish_only_one_complete_destination(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    source = tmp_path / "source.db"
    destination = tmp_path / "snapshot.db"
    keeper = create_instance(source)
    keeper.execute("CREATE TABLE future_payload (value BLOB)")
    keeper.execute("INSERT INTO future_payload VALUES (zeroblob(4000000))")
    keeper.commit()
    keeper.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: run_operator(
                    "backup", "--database", source, "--output", destination
                ),
                range(2),
            )
        )
    assert sorted(result.returncode for result in results) == [0, 1]
    with sqlite3.connect(destination) as snapshot:
        assert snapshot.execute(
            "SELECT length(value) FROM future_payload"
        ).fetchone() == (4000000,)
        assert snapshot.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert set(tmp_path.iterdir()).issubset(
        {source, destination, Path(str(source) + "-wal"), Path(str(source) + "-shm")}
    )
