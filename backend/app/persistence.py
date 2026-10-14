"""Consistent SQLite snapshots for explicit operator backup and fresh restore."""

import os
import sqlite3
import tempfile
import time
from contextlib import closing
from pathlib import Path

from app.database import validate_existing_database, validate_standalone_schema

SQLITE_SIDECARS = ("-wal", "-shm", "-journal")


def require_absolute(path: Path) -> None:
    if not path.is_absolute():
        raise RuntimeError(
            "Use explicit absolute paths for the source and destination."
        )


def require_fresh_destination(path: Path) -> None:
    if not path.parent.is_dir():
        raise RuntimeError("Create the private destination directory before retrying.")
    if any(os.path.lexists(str(path) + suffix) for suffix in ("", *SQLITE_SIDECARS)):
        raise RuntimeError(
            "Destination database or SQLite sidecar already exists. "
            "Use a fresh path in a stopped installation; nothing was overwritten."
        )


def backup_database(source: Path, destination: Path) -> None:
    """Publish a verified, private snapshot without overwriting a destination."""
    require_absolute(source)
    require_absolute(destination)
    require_fresh_destination(destination)
    validate_existing_database(source)
    descriptor, name = tempfile.mkstemp(
        prefix=".nashordaq-snapshot-", suffix=".db", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(name)
    try:
        with (
            closing(
                sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
            ) as live,
            closing(sqlite3.connect(temporary)) as snapshot,
        ):
            deadline = time.monotonic() + 60

            def progress(_status: int, _remaining: int, _total: int) -> None:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        "Snapshot could not finish within 60 seconds. "
                        "Retry when database locks or load have cleared."
                    )

            # Pin one WAL read snapshot while other connections continue writing.
            live.execute("BEGIN")
            live.execute(
                "SELECT schema_version FROM instance_metadata WHERE id=1"
            ).fetchone()
            live.backup(snapshot, pages=256, progress=progress, sleep=0.1)
            snapshot.execute("PRAGMA journal_mode=DELETE")
            validate_standalone_schema(snapshot.execute)
        with temporary.open("rb") as file:
            os.fsync(file.fileno())
        require_fresh_destination(destination)
        # Publish exclusively even if another process creates the destination.
        os.link(temporary, destination)
        directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        for suffix in ("", *SQLITE_SIDECARS):
            Path(str(temporary) + suffix).unlink(missing_ok=True)


def restore_database(backup: Path, database: Path) -> None:
    """Restore all persisted state to an absent database in a stopped installation."""
    backup_database(backup, database)
