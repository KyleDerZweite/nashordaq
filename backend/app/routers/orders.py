from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentOnboardedUser, CurrentUser, is_admin_user
from app.config import settings
from app.database import get_session
from app.models import (
    Holding,
    HoldingLot,
    Order,
    OrderSide,
    OrderSource,
    OrderStatus,
    TrackedPlayer,
    Transaction,
    User,
)
from app.pricing import calculate_sell_multiplier
from app.schemas import OrderCreate, OrderDetailResponse, OrderResponse

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


def _order_response(
    order: Order,
    player_name: str,
    user_name: str | None = None,
) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        player_id=order.player_id,
        player_name=player_name,
        user_name=user_name,
        side=order.side,
        quantity=(
            order.quantity_value
            if order.quantity_value is not None
            else float(order.quantity)
        ),
        status=order.status,
        source=order.source,
        execution_price=order.execution_price,
        created_at=order.created_at,
        executed_at=order.executed_at,
    )


def _order_detail_response(
    order: Order,
    player_name: str,
    user_name: str | None = None,
) -> OrderDetailResponse:
    quantity = (
        order.quantity_value
        if order.quantity_value is not None
        else float(order.quantity)
    )
    total_value = None
    if order.execution_price is not None:
        total_value = order.execution_price * quantity

    return OrderDetailResponse(
        id=order.id,
        player_id=order.player_id,
        player_name=player_name,
        user_name=user_name,
        side=order.side,
        quantity=quantity,
        status=order.status,
        source=order.source,
        execution_price=order.execution_price,
        created_at=order.created_at,
        executed_at=order.executed_at,
        total_value=total_value,
        gross_execution_price=order.gross_execution_price,
        gross_total_value=order.gross_total_value,
        entry_total_value=order.entry_total_value,
        adjustment_value=order.adjustment_value,
        adjustment_reason=order.adjustment_reason,
    )


async def build_order_responses(
    session: AsyncSession,
    orders: list[Order],
) -> list[OrderResponse]:
    if not orders:
        return []

    player_ids = {o.player_id for o in orders}
    user_ids = {o.user_id for o in orders}

    players_result = await session.execute(
        select(TrackedPlayer).where(TrackedPlayer.id.in_(player_ids))
    )
    player_map = {p.id: p.display_name for p in players_result.scalars()}

    users_result = await session.execute(select(User).where(User.id.in_(user_ids)))
    users = users_result.scalars().all()
    linked_player_ids = {
        user.linked_player_id for user in users if user.linked_player_id
    }
    linked_players_result = await session.execute(
        select(TrackedPlayer).where(TrackedPlayer.id.in_(linked_player_ids))
    )
    linked_player_name_map = {
        player.id: player.display_name for player in linked_players_result.scalars()
    }
    user_name_map = {
        user.id: (
            linked_player_name_map.get(user.linked_player_id, user.username)
            if user.linked_player_id is not None
            else user.username
        )
        for user in users
    }

    return [
        _order_response(
            order,
            player_map.get(order.player_id, ""),
            user_name_map.get(order.user_id),
        )
        for order in orders
    ]


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
        if user.linked_player_id == body.player_id:
            raise HTTPException(
                status_code=400,
                detail="You cannot buy your own stock",
            )

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
            quantity_value=float(body.quantity),
            status=OrderStatus.EXECUTED,
            source=OrderSource.MANUAL,
            execution_price=execution_price,
            gross_execution_price=execution_price,
            gross_total_value=total_cost,
            entry_total_value=total_cost,
            adjustment_value=0.0,
            adjustment_reason=None,
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
        gross_total = gross_price * body.quantity
        adjusted_total = 0.0
        entry_total_value = 0.0

        buy_order_ids = [
            lot.buy_order_id for lot in lots if lot.buy_order_id is not None
        ]
        buy_order_price_map: dict[int, float] = {}
        if buy_order_ids:
            buy_orders_result = await session.execute(
                select(Order).where(Order.id.in_(buy_order_ids))
            )
            buy_order_price_map = {
                buy_order.id: (buy_order.execution_price or 0.0)
                for buy_order in buy_orders_result.scalars()
            }

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
            if lot.buy_order_id is not None:
                entry_total_value += consumed * buy_order_price_map.get(
                    lot.buy_order_id,
                    0.0,
                )
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
            quantity_value=float(body.quantity),
            status=OrderStatus.EXECUTED,
            source=OrderSource.MANUAL,
            execution_price=effective_execution_price,
            gross_execution_price=gross_price,
            gross_total_value=gross_total,
            entry_total_value=entry_total_value,
            adjustment_value=adjusted_total - gross_total,
            adjustment_reason="HOLD_DURATION",
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
    user: CurrentUser,
    session: SessionDep,
    status: OrderStatus | None = Query(default=None),  # noqa: B008
) -> list[OrderResponse]:
    if is_admin_user(user):
        return []

    if user.linked_player_id is None:
        return []

    stmt = select(Order).where(Order.user_id == user.id)
    if status is not None:
        stmt = stmt.where(Order.status == status)
    stmt = stmt.order_by(Order.created_at.desc())

    result = await session.execute(stmt)
    orders = result.scalars().all()

    return await build_order_responses(session, orders)


@router.get("/orders/recent", response_model=list[OrderResponse])
async def list_recent_orders(
    user: CurrentUser,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),  # noqa: B008
) -> list[OrderResponse]:
    del user

    result = await session.execute(
        select(Order).order_by(Order.created_at.desc()).limit(limit)
    )
    orders = result.scalars().all()
    return await build_order_responses(session, orders)


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def get_order_detail(
    order_id: int,
    user: CurrentUser,
    session: SessionDep,
) -> OrderDetailResponse:
    del user

    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    player_result = await session.execute(
        select(TrackedPlayer).where(TrackedPlayer.id == order.player_id)
    )
    player = player_result.scalar_one_or_none()
    user_result = await session.execute(select(User).where(User.id == order.user_id))
    order_user = user_result.scalar_one_or_none()

    if player is None or order_user is None:
        raise HTTPException(status_code=404, detail="Order not found")

    user_name = order_user.username
    if order_user.linked_player_id is not None:
        linked_player_result = await session.execute(
            select(TrackedPlayer).where(TrackedPlayer.id == order_user.linked_player_id)
        )
        linked_player = linked_player_result.scalar_one_or_none()
        if linked_player is not None:
            user_name = linked_player.display_name

    return _order_detail_response(order, player.display_name, user_name)


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

    if order.source != OrderSource.MANUAL:
        raise HTTPException(status_code=400, detail="Order cannot be cancelled")

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
