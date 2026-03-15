import random
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentOnboardedUser, CurrentUser, is_admin_user
from app.config import settings
from app.database import get_session
from app.models import (
    GambaPosition,
    GambaStatus,
    Order,
    OrderSide,
    OrderSource,
    OrderStatus,
    TrackedPlayer,
)
from app.schemas import GambaCreate, GambaPositionResponse

router = APIRouter(tags=["gamba"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _position_response(
    position: GambaPosition,
    player_name: str,
    player_game_name: str,
) -> GambaPositionResponse:
    return GambaPositionResponse(
        id=position.id,
        player_id=position.player_id,
        player_name=player_name,
        player_game_name=player_game_name,
        cash_amount=position.cash_amount,
        quantity=position.quantity,
        entry_price=position.entry_price,
        scheduled_settlement_at=position.scheduled_settlement_at,
        settlement_multiplier=position.settlement_multiplier,
        status=position.status,
        exit_price=position.exit_price,
        settled_at=position.settled_at,
        raw_pnl=position.raw_pnl,
        settled_pnl=position.settled_pnl,
        created_at=position.created_at,
    )


async def _get_random_eligible_player(
    session: AsyncSession,
    user_player_id: int | None,
) -> TrackedPlayer:
    result = await session.execute(
        select(TrackedPlayer).where(TrackedPlayer.last_updated.is_not(None))
    )
    players = [
        player for player in result.scalars().all() if player.id != user_player_id
    ]
    if not players:
        raise HTTPException(
            status_code=400,
            detail="No eligible Gamba players available",
        )
    return random.choice(players)


@router.post("/gamba", response_model=GambaPositionResponse, status_code=201)
async def create_gamba_position(
    body: GambaCreate,
    user: CurrentOnboardedUser,
    session: SessionDep,
) -> GambaPositionResponse:
    if body.cash_amount > user.balance:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    player = await _get_random_eligible_player(session, user.linked_player_id)
    if player.current_price <= 0:
        raise HTTPException(status_code=400, detail="Selected player is not tradable")

    now = datetime.now(UTC)
    hold_hours = random.uniform(
        settings.gamba_min_hold_hours,
        settings.gamba_max_hold_hours,
    )
    quantity = body.cash_amount / player.current_price

    # Scale settlement multiplier linearly with hold duration:
    # shorter holds get a lower multiplier, longer holds get a higher one.
    hold_range = settings.gamba_max_hold_hours - settings.gamba_min_hold_hours
    if hold_range > 0:
        hold_fraction = (hold_hours - settings.gamba_min_hold_hours) / hold_range
    else:
        hold_fraction = 0.5
    settlement_multiplier = settings.gamba_settlement_multiplier_min + hold_fraction * (
        settings.gamba_settlement_multiplier_max
        - settings.gamba_settlement_multiplier_min
    )

    user.balance -= body.cash_amount

    buy_order = Order(
        user_id=user.id,
        player_id=player.id,
        side=OrderSide.BUY,
        quantity=0,
        quantity_value=quantity,
        status=OrderStatus.EXECUTED,
        source=OrderSource.GAMBA,
        execution_price=player.current_price,
        executed_at=now,
    )
    session.add(buy_order)
    await session.flush()

    position = GambaPosition(
        user_id=user.id,
        player_id=player.id,
        buy_order_id=buy_order.id,
        cash_amount=body.cash_amount,
        quantity=quantity,
        entry_price=player.current_price,
        scheduled_settlement_at=now + timedelta(hours=hold_hours),
        settlement_multiplier=settlement_multiplier,
        status=GambaStatus.ACTIVE,
    )
    session.add(position)

    await session.commit()
    await session.refresh(position)

    return _position_response(position, player.display_name, player.game_name)


@router.get("/gamba", response_model=list[GambaPositionResponse])
async def list_gamba_positions(
    user: CurrentUser,
    session: SessionDep,
) -> list[GambaPositionResponse]:
    if is_admin_user(user) or user.linked_player_id is None:
        return []

    result = await session.execute(
        select(GambaPosition, TrackedPlayer)
        .join(TrackedPlayer, TrackedPlayer.id == GambaPosition.player_id)
        .where(GambaPosition.user_id == user.id)
        .order_by(GambaPosition.created_at.desc())
    )
    rows = result.all()
    return [
        _position_response(position, player.display_name, player.game_name)
        for position, player in rows
    ]
