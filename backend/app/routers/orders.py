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
    PriceHistory,
    TrackedPlayer,
    Transaction,
    User,
)
from app.pricing import calculate_market_impact
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
    player_game_name: str,
    user_name: str | None = None,
    user_game_name: str | None = None,
) -> OrderResponse:
    market_impact_pct: float | None = None
    price_after_impact: float | None = None
    if (
        order.source == OrderSource.MANUAL
        and order.gross_execution_price is not None
        and order.execution_price is not None
        and order.gross_execution_price > 0
    ):
        market_impact_pct = (
            order.execution_price - order.gross_execution_price
        ) / order.gross_execution_price
        # Reconstruct post-trade price: impact_pct = Q/D, we stored avg = P*(1±i/2),
        # so full impact is 2x the slippage direction.
        impact_pct_full = abs(market_impact_pct) * 2
        if order.side == OrderSide.BUY:
            price_after_impact = order.gross_execution_price * (1 + impact_pct_full)
        else:
            price_after_impact = max(
                order.gross_execution_price * (1 - impact_pct_full), 1.0
            )

    return OrderResponse(
        id=order.id,
        player_id=order.player_id,
        player_name=player_name,
        player_game_name=player_game_name,
        user_name=user_name,
        user_game_name=user_game_name,
        side=order.side,
        quantity=(
            order.quantity_value
            if order.quantity_value is not None
            else float(order.quantity)
        ),
        status=order.status,
        source=order.source,
        execution_price=order.execution_price,
        market_impact_pct=market_impact_pct,
        price_after_impact=price_after_impact,
        created_at=order.created_at,
        executed_at=order.executed_at,
    )


def _order_detail_response(
    order: Order,
    player_name: str,
    player_game_name: str,
    user_name: str | None = None,
    user_game_name: str | None = None,
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
        player_game_name=player_game_name,
        user_name=user_name,
        user_game_name=user_game_name,
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
    player_map = {
        player.id: (player.display_name, player.game_name)
        for player in players_result.scalars()
    }

    users_result = await session.execute(select(User).where(User.id.in_(user_ids)))
    users = users_result.scalars().all()
    linked_player_ids = {
        user.linked_player_id for user in users if user.linked_player_id
    }
    linked_players_result = await session.execute(
        select(TrackedPlayer).where(TrackedPlayer.id.in_(linked_player_ids))
    )
    linked_player_identity_map = {
        player.id: (player.display_name, player.game_name)
        for player in linked_players_result.scalars()
    }
    user_name_map = {
        user.id: (
            linked_player_identity_map.get(
                user.linked_player_id,
                (
                    user.display_name or user.email or user.username,
                    user.display_name or user.email or user.username,
                ),
            )[0]
            if user.linked_player_id is not None
            else user.display_name or user.email or user.username
        )
        for user in users
    }
    user_game_name_map = {
        user.id: (
            linked_player_identity_map.get(
                user.linked_player_id,
                (
                    user.display_name or user.email or user.username,
                    user.display_name or user.email or user.username,
                ),
            )[1]
            if user.linked_player_id is not None
            else user.display_name or user.email or user.username
        )
        for user in users
    }

    return [
        _order_response(
            order,
            player_map.get(order.player_id, ("", ""))[0],
            player_map.get(order.player_id, ("", ""))[1],
            user_name_map.get(order.user_id),
            user_game_name_map.get(order.user_id),
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
        if not user.is_demo and user.linked_player_id == body.player_id:
            raise HTTPException(
                status_code=400,
                detail="You cannot buy your own stock",
            )

        if player.last_updated is None:
            raise HTTPException(
                status_code=400,
                detail="Player has not received a first market update yet",
            )

        market_price = player.current_price
        avg_fill, new_market_price = calculate_market_impact(
            market_price, body.quantity, "BUY"
        )
        execution_price = avg_fill
        total_cost = execution_price * body.quantity
        if user.balance < total_cost:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        user.balance -= total_cost
        if not user.is_demo:
            player.current_price = new_market_price

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
            gross_execution_price=market_price,
            gross_total_value=market_price * body.quantity,
            entry_total_value=total_cost,
            adjustment_value=total_cost - (market_price * body.quantity),
            adjustment_reason="Market Impact",
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

        if not user.is_demo:
            session.add(
                PriceHistory(
                    player_id=body.player_id,
                    price=new_market_price,
                    lp_abs=player.lp_abs,
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

        min_hold_deadline = now - timedelta(hours=settings.min_hold_period_hours)
        remaining = body.quantity
        market_price = player.current_price
        avg_fill, new_market_price = calculate_market_impact(
            market_price, body.quantity, "SELL"
        )
        execution_price = avg_fill
        total_value = execution_price * body.quantity
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

            if not user.is_demo:
                acquired_at = (
                    lot.acquired_at
                    if lot.acquired_at.tzinfo is not None
                    else lot.acquired_at.replace(tzinfo=UTC)
                )
                if acquired_at > min_hold_deadline:
                    continue

            consumed = min(remaining, lot.quantity)
            if lot.buy_order_id is not None:
                entry_total_value += consumed * buy_order_price_map.get(
                    lot.buy_order_id,
                    0.0,
                )
            lot.quantity -= consumed
            remaining -= consumed

        if remaining > 0:
            raise HTTPException(
                status_code=400,
                detail="Shares are still within the minimum holding period",
            )

        holding.quantity -= body.quantity
        user.balance += total_value
        if not user.is_demo:
            player.current_price = new_market_price

        order = Order(
            user_id=user.id,
            player_id=body.player_id,
            side=body.side,
            quantity=body.quantity,
            quantity_value=float(body.quantity),
            status=OrderStatus.EXECUTED,
            source=OrderSource.MANUAL,
            execution_price=execution_price,
            gross_execution_price=market_price,
            gross_total_value=market_price * body.quantity,
            entry_total_value=entry_total_value,
            adjustment_value=total_value - (market_price * body.quantity),
            adjustment_reason="Market Impact",
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
                price=execution_price,
                total=total_value,
            )
        )

        if not user.is_demo:
            session.add(
                PriceHistory(
                    player_id=body.player_id,
                    price=new_market_price,
                    lp_abs=player.lp_abs,
                )
            )

    await session.commit()
    await session.refresh(order)

    return _order_response(order, player.display_name, player.game_name)


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(
    user: CurrentUser,
    session: SessionDep,
    status: OrderStatus | None = Query(default=None),  # noqa: B008
) -> list[OrderResponse]:
    if is_admin_user(user):
        return []

    if user.linked_player_id is None and not user.is_demo:
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

    stmt = select(Order)
    if settings.demo_mode_enabled:
        stmt = stmt.join(User, User.id == Order.user_id).where(
            User.is_demo == False  # noqa: E712
        )
    result = await session.execute(stmt.order_by(Order.created_at.desc()).limit(limit))
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

    user_name = order_user.display_name or order_user.email or order_user.username
    user_game_name = user_name
    if order_user.linked_player_id is not None:
        linked_player_result = await session.execute(
            select(TrackedPlayer).where(TrackedPlayer.id == order_user.linked_player_id)
        )
        linked_player = linked_player_result.scalar_one_or_none()
        if linked_player is not None:
            user_name = linked_player.display_name
            user_game_name = linked_player.game_name

    return _order_detail_response(
        order,
        player.display_name,
        player.game_name,
        user_name,
        user_game_name,
    )


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
        return _order_response(order, player.display_name, player.game_name)

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

    # Reverse the market impact: the original BUY pushed price up, so we
    # apply a reverse SELL impact of the same size to undo it.
    _, reverted_price = calculate_market_impact(
        player.current_price, order.quantity, "SELL"
    )
    player.current_price = reverted_price

    session.add(
        PriceHistory(
            player_id=order.player_id,
            price=reverted_price,
            lp_abs=player.lp_abs,
        )
    )

    await session.commit()
    await session.refresh(order)

    return _order_response(order, player.display_name, player.game_name)
