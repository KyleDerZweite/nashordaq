from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.banking import build_account_snapshot
from app.database import get_session
from app.models import TrackedPlayer, User
from app.schemas import LeaderboardEntry

router = APIRouter(tags=["leaderboard"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard(session: SessionDep) -> list[LeaderboardEntry]:
    users_result = await session.execute(
        select(User, TrackedPlayer)
        .join(TrackedPlayer, User.linked_player_id == TrackedPlayer.id)
        .where(User.linked_player_id.is_not(None))
    )
    users = users_result.all()

    entries: list[tuple[str, float]] = []
    for user, tracked_player in users:
        snapshot = await build_account_snapshot(session, user)
        entries.append((tracked_player.display_name, snapshot.debt_adjusted_net_worth))

    entries.sort(key=lambda e: e[1], reverse=True)

    return [
        LeaderboardEntry(display_name=display_name, total_value=total, rank=i + 1)
        for i, (display_name, total) in enumerate(entries)
    ]
