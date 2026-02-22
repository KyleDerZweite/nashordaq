from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import TrackedPlayer
from app.schemas import PlayerDetail, PlayerSummary, PriceHistoryEntry

router = APIRouter(tags=["market"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/market/players", response_model=list[PlayerSummary])
async def list_players(session: SessionDep) -> list[PlayerSummary]:
    result = await session.execute(select(TrackedPlayer))
    players = result.scalars().all()
    return [
        PlayerSummary(
            id=p.id,
            display_name=p.display_name,
            game_name=p.game_name,
            tag_line=p.tag_line,
            current_price=p.current_price,
            last_updated=p.last_updated,
        )
        for p in players
    ]


@router.get("/market/players/{player_id}", response_model=PlayerDetail)
async def get_player(
    player_id: int,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=1000),  # noqa: B008
) -> PlayerDetail:
    result = await session.execute(
        select(TrackedPlayer)
        .where(TrackedPlayer.id == player_id)
        .options(selectinload(TrackedPlayer.price_history))
    )
    player = result.scalar_one_or_none()
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    history = sorted(player.price_history, key=lambda h: h.recorded_at, reverse=True)[
        :limit
    ]

    return PlayerDetail(
        id=player.id,
        display_name=player.display_name,
        game_name=player.game_name,
        tag_line=player.tag_line,
        current_price=player.current_price,
        last_updated=player.last_updated,
        previous_lp_abs=player.previous_lp_abs,
        lp_abs=player.lp_abs,
        streak=player.streak,
        price_history=[
            PriceHistoryEntry(
                price=h.price,
                lp_abs=h.lp_abs,
                recorded_at=h.recorded_at,
            )
            for h in history
        ],
    )
