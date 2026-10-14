"""Server-side maintenance commands for an explicitly selected standalone database."""

import argparse
import asyncio
import getpass
import sqlite3
import sys
import warnings
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import URL, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth import NewPassword, hash_password, is_admin_user, replace_password
from app.config import settings
from app.database import validate_existing_database
from app.models import User
from app.persistence import backup_database, require_absolute, restore_database


def read_password(from_stdin: bool) -> str:
    if from_stdin:
        if sys.stdin.isatty():
            raise RuntimeError(
                "Redirect protected stdin, or omit --password-stdin for hidden input."
            )
        password = sys.stdin.read(1026)
        if password.endswith("\n"):
            password = password[:-1]
        if "\n" in password or "\r" in password:
            raise RuntimeError(
                "Provide exactly one password line through protected stdin."
            )
    else:
        if not sys.stdin.isatty():
            raise RuntimeError("Use a terminal or explicitly pass --password-stdin.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("New administrator password: ")
            if password != getpass.getpass("Confirm new password: "):
                raise RuntimeError("Passwords do not match. Nothing was changed.")
    try:
        return NewPassword(new_password=password).new_password
    except ValidationError:
        raise RuntimeError("Password must contain 12 to 1024 characters.") from None


async def recover_admin(path: Path, password: str) -> None:
    validate_existing_database(path)
    if settings.demo_mode_enabled:
        raise RuntimeError("Administrator recovery is unavailable in demo mode.")
    engine = create_async_engine(
        URL.create("sqlite+aiosqlite", database=str(path.resolve())),
        connect_args={"timeout": 15},
    )
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            administrators = list(
                await session.scalars(select(User).where(User.is_admin))
            )
            if len(administrators) != 1 or not is_admin_user(administrators[0]):
                raise RuntimeError(
                    "Recovery requires the existing sole non-demo administrator."
                )
            administrator = administrators[0]
            verifier = await asyncio.to_thread(hash_password, password)
            changed = await replace_password(
                session,
                administrator.id,
                verifier,
                expected_hash=administrator.password_hash,
            )
            if not changed:
                raise RuntimeError("Administrator access changed. Retry recovery.")
            await session.commit()
    finally:
        await engine.dispose()


class OperatorParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's default error can echo values supplied in unsupported arguments.
        self.print_usage(sys.stderr)
        self.exit(2, "Invalid command arguments. Run with --help.\n")


def main() -> int:
    parser = OperatorParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    recover = commands.add_parser(
        "recover-admin", help="Recover the existing administrator"
    )
    recover.add_argument(
        "--database", required=True, type=Path, help="Existing SQLite file"
    )
    recover.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read one password line from protected stdin instead of getpass",
    )
    backup = commands.add_parser(
        "backup", help="Create a consistent live SQLite snapshot"
    )
    backup.add_argument(
        "--database", required=True, type=Path, help="Absolute source SQLite path"
    )
    backup.add_argument(
        "--output", required=True, type=Path, help="Absolute new snapshot path"
    )
    restore = commands.add_parser(
        "restore", help="Restore into a fresh stopped installation"
    )
    restore.add_argument(
        "--backup", required=True, type=Path, help="Absolute supported backup path"
    )
    restore.add_argument(
        "--database", required=True, type=Path, help="Absolute new database path"
    )
    preflight = commands.add_parser(
        "check-update", help="Check this code's supported schema without changing data"
    )
    preflight.add_argument(
        "--database", required=True, type=Path, help="Absolute existing SQLite path"
    )
    args = parser.parse_args()
    if args.command == "check-update":
        try:
            require_absolute(args.database)
            validate_existing_database(args.database)
        except RuntimeError as error:
            print(str(error), file=sys.stderr)
            return 1
        except (OSError, sqlite3.Error):
            print(
                "Cannot inspect a supported standalone database. "
                "Preserve it and use the matching code revision and a healthy backup.",
                file=sys.stderr,
            )
            return 1
        print(
            "Compatible standalone schema version 1. No database changes made. "
            "Keep the old code and its matching backup before updating."
        )
        return 0
    if args.command in {"backup", "restore"}:
        try:
            if args.command == "backup":
                backup_database(args.database, args.output)
            else:
                restore_database(args.backup, args.database)
        except RuntimeError as error:
            print(str(error), file=sys.stderr)
            return 1
        except (OSError, sqlite3.Error):
            print(
                "Cannot create snapshot. Check source compatibility, "
                "directory permissions, "
                "free space and hard-link support; retry with a fresh destination.",
                file=sys.stderr,
            )
            return 1
        except KeyboardInterrupt:
            print(
                "Snapshot interrupted. Inspect the destination before retrying.",
                file=sys.stderr,
            )
            return 1
        if args.command == "backup":
            print(f"Backup created: {args.output}")
        else:
            print(
                f"Restore completed: {args.database}. "
                "Start the installation and verify login and game state."
            )
        return 0
    try:
        validate_existing_database(args.database)
        password = read_password(args.password_stdin)
        asyncio.run(recover_admin(args.database, password))
    except (EOFError, KeyboardInterrupt):
        print("Recovery cancelled. Nothing was changed.", file=sys.stderr)
        return 1
    except (RuntimeError, getpass.GetPassWarning) as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error, SQLAlchemyError):
        print(
            "Cannot access a supported standalone database. Nothing was committed.",
            file=sys.stderr,
        )
        return 1
    print(
        "Administrator password replaced. All old administrator sessions are revoked."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
