from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentOnboardedUser
from app.config import settings
from app.database import get_session
from app.models import (
    Holding,
    HoldingLot,
    Order,
    OrderSide,
    OrderStatus,
    TrackedPlayer,
    Transaction,
)
from app.pricing import calculate_sell_multiplier
from app.schemas import OrderCreate, OrderResponse

router = APIRouter(tags=["orders"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _get_or_create_holding(
    session: AsyncSession,
    user_id: int,
    player_id: int,
) -> Holding:
    result = await session.execute(
        select(Holding).where(
            Holding.user_id == user_id,
            Holding.player_id == player_id,
        )
    )
    holding = result.scalar_one_or_none()
    if holding is None:
        holding = Holding(user_id=user_id, player_id=player_id, quantity=0)
        session.add(holding)
        await session.flush()
    return holding


def _pending_sells_query(user_id: int, player_id: int) -> Select[tuple[Order]]:
    return select(Order).where(
        Order.user_id == user_id,
        Order.player_id == player_id,
        Order.side == OrderSide.SELL,
        Order.status == OrderStatus.PENDING,
    )


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
    user: CurrentOnboardedUser,
    session: SessionDep,
) -> OrderResponse:
    result = await session.execute(
        select(TrackedPlayer).where(TrackedPlayer.id == body.player_id)
    )
    player = result.scalar_one_or_none()
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    now = datetime.now(UTC)

    if body.side == OrderSide.BUY:
        if player.last_updated is None:
            raise HTTPException(
                status_code=400,
                detail="Player has not received a first market update yet",
            )

        execution_price = player.current_price
        total_cost = execution_price * body.quantity
        if user.balance < total_cost:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        user.balance -= total_cost

        holding = await _get_or_create_holding(session, user.id, body.player_id)
        holding.quantity += body.quantity

        order = Order(
            user_id=user.id,
            player_id=body.player_id,
            side=body.side,
            quantity=body.quantity,
            status=OrderStatus.EXECUTED,
            execution_price=execution_price,
            executed_at=now,
        )
        session.add(order)
        await session.flush()

        session.add(
            HoldingLot(
                user_id=user.id,
                player_id=body.player_id,
                buy_order_id=order.id,
                quantity=body.quantity,
                acquired_at=now,
            )
        )

        session.add(
            Transaction(
                user_id=user.id,
                player_id=body.player_id,
                order_id=order.id,
                side=body.side,
                quantity=body.quantity,
                price=execution_price,
                total=total_cost,
            )
        )
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
            _pending_sells_query(user.id, body.player_id)
        )
        reserved = sum(o.quantity for o in pending_sells.scalars())
        available = owned - reserved

        if body.quantity > available:
            raise HTTPException(status_code=400, detail="Insufficient shares")

        lots_result = await session.execute(
            select(HoldingLot)
            .where(
                HoldingLot.user_id == user.id,
                HoldingLot.player_id == body.player_id,
                HoldingLot.quantity > 0,
            )
            .order_by(HoldingLot.acquired_at.asc(), HoldingLot.id.asc())
        )
        lots = lots_result.scalars().all()

        remaining = body.quantity
        gross_price = player.current_price
        adjusted_total = 0.0

        for lot in lots:
            if remaining <= 0:
                break

            consumed = min(remaining, lot.quantity)
            acquired_at = (
                lot.acquired_at
                if lot.acquired_at.tzinfo is not None
                else lot.acquired_at.replace(tzinfo=UTC)
            )
            held_duration = now - acquired_at
            held_hours = held_duration.total_seconds() / 3600
            multiplier = calculate_sell_multiplier(
                held_hours=held_hours,
                short_hold_fee_rate=settings.short_hold_fee_rate,
                short_hold_fee_window_hours=settings.short_hold_fee_window_hours,
                long_hold_bonus_rate=settings.long_hold_bonus_rate,
                long_hold_bonus_start_hours=settings.long_hold_bonus_start_hours,
            )

            adjusted_total += consumed * gross_price * multiplier
            lot.quantity -= consumed
            remaining -= consumed

        if remaining > 0:
            raise HTTPException(status_code=400, detail="Insufficient shares")

        effective_execution_price = adjusted_total / body.quantity
        holding.quantity -= body.quantity
        user.balance += adjusted_total

        order = Order(
            user_id=user.id,
            player_id=body.player_id,
            side=body.side,
            quantity=body.quantity,
            status=OrderStatus.EXECUTED,
            execution_price=effective_execution_price,
            executed_at=now,
        )
        session.add(order)
        await session.flush()

        session.add(
            Transaction(
                user_id=user.id,
                player_id=body.player_id,
                order_id=order.id,
                side=body.side,
                quantity=body.quantity,
                price=effective_execution_price,
                total=adjusted_total,
            )
        )

    await session.commit()
    await session.refresh(order)

    return _order_response(order, player.display_name)


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(
    user: CurrentOnboardedUser,
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
    user: CurrentOnboardedUser,
    session: SessionDep,
) -> OrderResponse:
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    player_result = await session.execute(
        select(TrackedPlayer).where(TrackedPlayer.id == order.player_id)
    )
    player = player_result.scalar_one()

    if order.status == OrderStatus.PENDING:
        order.status = OrderStatus.CANCELLED
        await session.commit()
        await session.refresh(order)
        return _order_response(order, player.display_name)

    if order.status != OrderStatus.EXECUTED or order.side != OrderSide.BUY:
        raise HTTPException(status_code=400, detail="Order cannot be cancelled")

    if order.executed_at is None:
        raise HTTPException(status_code=400, detail="Order cannot be cancelled")

    now = datetime.now(UTC)
    executed_at = (
        order.executed_at
        if order.executed_at.tzinfo is not None
        else order.executed_at.replace(tzinfo=UTC)
    )
    grace_deadline = executed_at + timedelta(seconds=settings.buy_revert_grace_seconds)
    if now > grace_deadline:
        raise HTTPException(status_code=400, detail="Revert window expired")

    holding = await _get_or_create_holding(session, user.id, order.player_id)
    if holding.quantity < order.quantity:
        raise HTTPException(
            status_code=400,
            detail="Order cannot be reverted after shares were sold",
        )

    lot_result = await session.execute(
        select(HoldingLot).where(
            HoldingLot.buy_order_id == order.id,
            HoldingLot.user_id == user.id,
            HoldingLot.player_id == order.player_id,
        )
    )
    lot = lot_result.scalar_one_or_none()
    if lot is None or lot.quantity < order.quantity:
        raise HTTPException(
            status_code=400,
            detail="Order cannot be reverted after shares were sold",
        )

    execution_price = order.execution_price
    if execution_price is None:
        raise HTTPException(status_code=400, detail="Order cannot be cancelled")

    refund_total = execution_price * order.quantity
    lot.quantity -= order.quantity
    holding.quantity -= order.quantity
    user.balance += refund_total
    order.status = OrderStatus.REVERTED

    await session.commit()
    await session.refresh(order)

    return _order_response(order, player.display_name)
