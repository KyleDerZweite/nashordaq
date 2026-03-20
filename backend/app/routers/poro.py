import asyncio
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentOnboardedUser
from app.config import settings
from app.database import get_session
from app.poro import (
    claim_poro_spawn,
    poro_state_notifier,
    poro_tier_level,
    resolve_poro_state,
)
from app.schemas import (
    PoroClaimRequest,
    PoroClaimResponse,
    PoroSpawnResponse,
    PoroStateResponse,
)

router = APIRouter(tags=["poro"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


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
        spawned_at=_normalize_datetime(spawn.spawned_at),
        expires_at=_normalize_datetime(spawn.expires_at),
        status=spawn.status,
    )


def _serialize_state(
    *,
    enabled: bool,
    server_time: datetime,
    next_roll_at: datetime | None,
    active_spawn,
) -> PoroStateResponse:
    return PoroStateResponse(
        enabled=enabled,
        server_time=_normalize_datetime(server_time) or server_time,
        next_roll_at=_normalize_datetime(next_roll_at),
        active_spawn=(
            _serialize_spawn(active_spawn) if active_spawn is not None else None
        ),
    )


def _encode_sse_event(payload: PoroStateResponse) -> str:
    return f"data: {payload.model_dump_json()}\n\n"


@router.get("/poro", response_model=PoroStateResponse)
async def get_poro_state(
    user: CurrentOnboardedUser,
    session: SessionDep,
) -> PoroStateResponse:
    now = datetime.now(UTC)
    if user.is_demo:
        return _serialize_state(
            enabled=False,
            server_time=now,
            next_roll_at=None,
            active_spawn=None,
        )
    if not settings.poro_enabled:
        return _serialize_state(
            enabled=False,
            server_time=now,
            next_roll_at=None,
            active_spawn=None,
        )

    summary = await resolve_poro_state(session, user, as_of=now)
    await session.commit()
    return _serialize_state(
        enabled=True,
        server_time=summary.server_time,
        next_roll_at=summary.next_roll_at,
        active_spawn=summary.active_spawn,
    )


@router.get("/poro/stream")
async def stream_poro_state(
    request: Request,
    user: CurrentOnboardedUser,
    session: SessionDep,
) -> StreamingResponse:
    if user.is_demo:

        async def _empty():
            return
            yield  # pragma: no cover

        return StreamingResponse(
            _empty(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    async def event_stream():
        stream_user_id = user.id
        listener = await poro_state_notifier.subscribe(stream_user_id)
        payload_json: str | None = None

        try:
            while True:
                if await request.is_disconnected():
                    break

                session.expire_all()
                stream_user = await session.get(type(user), stream_user_id)
                if stream_user is None or stream_user.linked_player_id is None:
                    break

                now = datetime.now(UTC)
                if not settings.poro_enabled:
                    payload = _serialize_state(
                        enabled=False,
                        server_time=now,
                        next_roll_at=None,
                        active_spawn=None,
                    )
                else:
                    summary = await resolve_poro_state(session, stream_user, as_of=now)
                    await session.commit()
                    payload = _serialize_state(
                        enabled=True,
                        server_time=summary.server_time,
                        next_roll_at=summary.next_roll_at,
                        active_spawn=summary.active_spawn,
                    )

                current_payload_json = payload.model_dump_json()
                if current_payload_json != payload_json:
                    payload_json = current_payload_json
                    yield _encode_sse_event(payload)

                if not settings.poro_enabled:
                    break

                listener.clear()
                try:
                    await asyncio.wait_for(listener.wait(), timeout=15)
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            await poro_state_notifier.unsubscribe(stream_user_id, listener)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/poro/claim", response_model=PoroClaimResponse)
async def post_poro_claim(
    body: PoroClaimRequest,
    user: CurrentOnboardedUser,
    session: SessionDep,
) -> PoroClaimResponse:
    if user.is_demo:
        raise HTTPException(status_code=403, detail="Not available in demo mode")
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
    await poro_state_notifier.notify(user.id)
    return PoroClaimResponse(
        spawn_id=spawn.public_id,
        tier=poro_tier_level(spawn.tier),
        reward_amount=spawn.reward_amount,
        claimed_at=_normalize_datetime(spawn.claimed_at) or now,
        balance=user.balance,
    )
