from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentOnboardedUser
from app.database import get_session
from app.models import Holding, TrackedPlayer
from app.schemas import HoldingResponse, PortfolioResponse

router = APIRouter(tags=["portfolio"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(
    user: CurrentOnboardedUser,
    session: SessionDep,
) -> PortfolioResponse:
    result = await session.execute(
        select(Holding, TrackedPlayer)
        .join(TrackedPlayer, Holding.player_id == TrackedPlayer.id)
        .where(Holding.user_id == user.id, Holding.quantity > 0)
    )
    rows = result.all()

    holdings = []
    total_holdings_value = 0.0
    for holding, player in rows:
        market_value = holding.quantity * player.current_price
        total_holdings_value += market_value
        holdings.append(
            HoldingResponse(
                player_id=player.id,
                player_name=player.display_name,
                quantity=holding.quantity,
                current_price=player.current_price,
                market_value=market_value,
            )
        )

    return PortfolioResponse(
        balance=user.balance,
        holdings=holdings,
        total_value=user.balance + total_holdings_value,
    )
