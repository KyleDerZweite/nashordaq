from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentOnboardedUser
from app.database import get_session
from app.models import Holding, HoldingLot, Order, TrackedPlayer
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

    player_ids = [player.id for _, player in rows]
    lots_result = await session.execute(
        select(HoldingLot).where(
            HoldingLot.user_id == user.id,
            HoldingLot.player_id.in_(player_ids),
            HoldingLot.quantity > 0,
        )
    )
    lots = lots_result.scalars().all()

    order_ids = [lot.buy_order_id for lot in lots if lot.buy_order_id is not None]
    orders_result = await session.execute(select(Order).where(Order.id.in_(order_ids)))
    order_price_map = {
        order.id: (order.execution_price or 0.0) for order in orders_result.scalars()
    }

    cost_basis_by_player: dict[int, float] = {}
    for lot in lots:
        if lot.buy_order_id is None:
            continue
        lot_cost = lot.quantity * order_price_map.get(lot.buy_order_id, 0.0)
        cost_basis_by_player[lot.player_id] = (
            cost_basis_by_player.get(lot.player_id, 0.0) + lot_cost
        )

    holdings = []
    total_holdings_value = 0.0
    for holding, player in rows:
        cost_basis = cost_basis_by_player.get(player.id, 0.0)
        average_buy_price = (
            cost_basis / holding.quantity if holding.quantity > 0 else 0.0
        )
        market_value = holding.quantity * player.current_price
        unrealized_pnl = market_value - cost_basis
        unrealized_pnl_pct = (
            (unrealized_pnl / cost_basis) * 100 if cost_basis > 0 else 0.0
        )
        total_holdings_value += market_value
        holdings.append(
            HoldingResponse(
                player_id=player.id,
                player_name=player.display_name,
                quantity=holding.quantity,
                average_buy_price=average_buy_price,
                current_price=player.current_price,
                cost_basis=cost_basis,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct,
            )
        )

    return PortfolioResponse(
        balance=user.balance,
        holdings=holdings,
        total_value=user.balance + total_holdings_value,
    )
