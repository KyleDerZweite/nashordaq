from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.database import get_session
from app.models import Holding, Order, OrderSide, OrderStatus, TrackedPlayer
from app.schemas import OrderCreate, OrderResponse

router = APIRouter(tags=["orders"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _order_response(order: Order, player_name: str) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        player_id=order.player_id,
        player_name=player_name,
        side=order.side,
        quantity=order.quantity,
        status=order.status,
        execution_price=order.execution_price,
        created_at=order.created_at,
        executed_at=order.executed_at,
    )


@router.post("/orders", response_model=OrderResponse, status_code=201)
async def place_order(
    body: OrderCreate,
    user: CurrentUser,
    session: SessionDep,
) -> OrderResponse:
    result = await session.execute(
        select(TrackedPlayer).where(TrackedPlayer.id == body.player_id)
    )
    player = result.scalar_one_or_none()
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    if body.side == OrderSide.BUY:
        estimated_cost = player.current_price * body.quantity
        if user.balance < estimated_cost:
            raise HTTPException(status_code=400, detail="Insufficient balance")
    else:
        result = await session.execute(
            select(Holding).where(
                Holding.user_id == user.id,
                Holding.player_id == body.player_id,
            )
        )
        holding = result.scalar_one_or_none()
        owned = holding.quantity if holding else 0

        pending_sells = await session.execute(
            select(Order).where(
                Order.user_id == user.id,
                Order.player_id == body.player_id,
                Order.side == OrderSide.SELL,
                Order.status == OrderStatus.PENDING,
            )
        )
        reserved = sum(o.quantity for o in pending_sells.scalars())
        available = owned - reserved

        if body.quantity > available:
            raise HTTPException(status_code=400, detail="Insufficient shares")

    order = Order(
        user_id=user.id,
        player_id=body.player_id,
        side=body.side,
        quantity=body.quantity,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)

    return _order_response(order, player.display_name)


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(
    user: CurrentUser,
    session: SessionDep,
    status: OrderStatus | None = Query(default=None),  # noqa: B008
) -> list[OrderResponse]:
    stmt = select(Order).where(Order.user_id == user.id)
    if status is not None:
        stmt = stmt.where(Order.status == status)
    stmt = stmt.order_by(Order.created_at.desc())

    result = await session.execute(stmt)
    orders = result.scalars().all()

    player_ids = {o.player_id for o in orders}
    players_result = await session.execute(
        select(TrackedPlayer).where(TrackedPlayer.id.in_(player_ids))
    )
    player_map = {p.id: p.display_name for p in players_result.scalars()}

    return [_order_response(o, player_map.get(o.player_id, "")) for o in orders]


@router.delete("/orders/{order_id}", response_model=OrderResponse)
async def cancel_order(
    order_id: int,
    user: CurrentUser,
    session: SessionDep,
) -> OrderResponse:
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=400, detail="Order cannot be cancelled")

    order.status = OrderStatus.CANCELLED
    await session.commit()
    await session.refresh(order)

    player_result = await session.execute(
        select(TrackedPlayer).where(TrackedPlayer.id == order.player_id)
    )
    player = player_result.scalar_one()

    return _order_response(order, player.display_name)
