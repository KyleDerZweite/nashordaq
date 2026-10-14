"""Permanent League aliases assigned by persistence, never by presentation."""

import json
from pathlib import Path

from sqlalchemy import event, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models import IdentityAlias, TrackedPlayer, User

_names = json.loads(Path(__file__).with_name("alias_names.json").read_text())
CHAMPION_NAMES: tuple[str, ...] = tuple(_names["champions"])
ALIAS_NAMES: tuple[str, ...] = CHAMPION_NAMES + tuple(_names["extensions"])


class AliasPoolExhausted(RuntimeError):
    pass


def _assign_aliases(
    session: Session, connection: Connection, targets: list[User | TrackedPlayer]
) -> None:
    if not targets:
        return
    # Acquire the SQLite writer lock before reading the allocation pool. Concurrent
    # creation waits here rather than choosing the same available champion name.
    connection.execute(text("UPDATE identity_aliases SET id=id WHERE 0"))
    rows = connection.execute(select(IdentityAlias.__table__)).mappings().all()
    used = {row["alias"] for row in rows}
    user_ids = {row["user_id"] for row in rows if row["user_id"] is not None}
    player_ids = {row["player_id"] for row in rows if row["player_id"] is not None}
    for row in session.new:
        if isinstance(row, IdentityAlias):
            used.add(row.alias)
    available = iter(name for name in ALIAS_NAMES if name not in used)
    for target in targets:
        if target.id is not None and target.id in (
            user_ids if isinstance(target, User) else player_ids
        ):
            continue
        try:
            name = next(available)
        except StopIteration:
            raise AliasPoolExhausted(
                "All League streamer aliases are in use. "
                "Ask the operator to extend the League name pool."
            ) from None
        session.add(
            IdentityAlias(user=target, alias=name)
            if isinstance(target, User)
            else IdentityAlias(player=target, alias=name)
        )


@event.listens_for(Session, "before_flush")
def assign_created_identity_aliases(session: Session, _context, _instances) -> None:
    targets = [row for row in session.new if isinstance(row, (User, TrackedPlayer))]
    if targets:
        _assign_aliases(session, session.connection(), targets)


async def backfill_aliases(session: AsyncSession) -> None:
    """Populate existing standalone instances without altering user data."""
    # Lock before reading targets so no concurrent registration can intervene.
    await session.execute(text("UPDATE identity_aliases SET id=id WHERE 0"))
    users = list(await session.scalars(select(User).order_by(User.id)))
    players = list(
        await session.scalars(select(TrackedPlayer).order_by(TrackedPlayer.id))
    )
    await session.run_sync(
        lambda sync_session: _assign_aliases(
            sync_session, sync_session.connection(), [*users, *players]
        )
    )
