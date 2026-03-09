from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Holding, TrackedPlayer, User
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

    players_result = await session.execute(select(TrackedPlayer))
    price_map = {p.id: p.current_price for p in players_result.scalars()}

    entries: list[tuple[str, float]] = []
    for user, tracked_player in users:
        holdings_result = await session.execute(
            select(Holding).where(Holding.user_id == user.id, Holding.quantity > 0)
        )
        holdings_value = sum(
            h.quantity * price_map.get(h.player_id, 0.0)
            for h in holdings_result.scalars()
        )
        entries.append((tracked_player.game_name, user.balance + holdings_value))

    entries.sort(key=lambda e: e[1], reverse=True)

    return [
        LeaderboardEntry(game_name=game_name, total_value=total, rank=i + 1)
        for i, (game_name, total) in enumerate(entries)
    ]
