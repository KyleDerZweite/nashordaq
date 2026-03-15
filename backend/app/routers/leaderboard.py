from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.banking import build_account_snapshot
from app.database import get_session
from app.models import TrackedPlayer, User
from app.routers.portfolio import build_portfolio_response
from app.schemas import LeaderboardEntry, LeaderboardPlayerPortfolioResponse

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

    entries: list[tuple[int, str, str, float]] = []
    for user, tracked_player in users:
        snapshot = await build_account_snapshot(session, user)
        entries.append(
            (
                user.id,
                tracked_player.display_name,
                tracked_player.game_name,
                snapshot.debt_adjusted_net_worth,
            )
        )

    entries.sort(key=lambda entry: entry[3], reverse=True)

    return [
        LeaderboardEntry(
            user_id=user_id,
            display_name=display_name,
            game_name=game_name,
            total_value=total,
            rank=i + 1,
        )
        for i, (user_id, display_name, game_name, total) in enumerate(entries)
    ]


@router.get(
    "/leaderboard/{user_id}/portfolio",
    response_model=LeaderboardPlayerPortfolioResponse,
)
async def get_leaderboard_player_portfolio(
    user_id: int,
    session: SessionDep,
) -> LeaderboardPlayerPortfolioResponse:
    user_result = await session.execute(
        select(User, TrackedPlayer)
        .join(TrackedPlayer, User.linked_player_id == TrackedPlayer.id)
        .where(User.id == user_id, User.linked_player_id.is_not(None))
    )
    row = user_result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Player not found")

    user, tracked_player = row
    portfolio = await build_portfolio_response(session, user)

    return LeaderboardPlayerPortfolioResponse(
        display_name=tracked_player.display_name,
        game_name=tracked_player.game_name,
        total_value=portfolio.total_value,
        holdings=portfolio.holdings,
    )
