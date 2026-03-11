from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentOnboardedUser
from app.config import settings
from app.database import get_session
from app.poro import claim_poro_spawn, poro_tier_level, resolve_poro_state
from app.schemas import (
    PoroClaimRequest,
    PoroClaimResponse,
    PoroSpawnResponse,
    PoroStateResponse,
)

router = APIRouter(tags=["poro"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _serialize_spawn(spawn) -> PoroSpawnResponse:
    return PoroSpawnResponse(
        spawn_id=spawn.public_id,
        tier=poro_tier_level(spawn.tier),
        tier_label=spawn.tier.value,
        reward_amount=spawn.reward_amount,
        asset_key=spawn.asset_key,
        start_x=spawn.start_x,
        start_y=spawn.start_y,
        end_x=spawn.end_x,
        end_y=spawn.end_y,
        duration_ms=spawn.duration_ms,
        spawned_at=spawn.spawned_at,
        expires_at=spawn.expires_at,
        status=spawn.status,
    )


@router.get("/poro", response_model=PoroStateResponse)
async def get_poro_state(
    user: CurrentOnboardedUser,
    session: SessionDep,
) -> PoroStateResponse:
    now = datetime.now(UTC)
    if not settings.poro_enabled:
        return PoroStateResponse(
            enabled=False,
            server_time=now,
            next_roll_at=None,
            active_spawn=None,
        )

    summary = await resolve_poro_state(session, user, as_of=now)
    await session.commit()
    return PoroStateResponse(
        enabled=True,
        server_time=summary.server_time,
        next_roll_at=summary.next_roll_at,
        active_spawn=(
            _serialize_spawn(summary.active_spawn)
            if summary.active_spawn is not None
            else None
        ),
    )


@router.post("/poro/claim", response_model=PoroClaimResponse)
async def post_poro_claim(
    body: PoroClaimRequest,
    user: CurrentOnboardedUser,
    session: SessionDep,
) -> PoroClaimResponse:
    if not settings.poro_enabled:
        raise HTTPException(status_code=404, detail="Poro feature disabled")

    now = datetime.now(UTC)
    try:
        spawn = await claim_poro_spawn(session, user, body.spawn_id, as_of=now)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(user)
    return PoroClaimResponse(
        spawn_id=spawn.public_id,
        tier=poro_tier_level(spawn.tier),
        reward_amount=spawn.reward_amount,
        claimed_at=spawn.claimed_at or now,
        balance=user.balance,
    )
