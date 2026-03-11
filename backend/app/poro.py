import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.banking import record_user_wealth_snapshot, round_currency
from app.config import settings
from app.models import (
    PoroSpawn,
    PoroSpawnStatus,
    PoroTier,
    User,
    UserPoroState,
    UserWealthSnapshotSource,
)


@dataclass(slots=True)
class PoroStateSummary:
    active_spawn: PoroSpawn | None
    next_roll_at: datetime | None
    server_time: datetime


TIER_ORDER = (
    PoroTier.TIER_1,
    PoroTier.TIER_2,
    PoroTier.TIER_3,
    PoroTier.TIER_4,
    PoroTier.TIER_5,
    PoroTier.TIER_6,
)

TIER_REWARDS = {
    PoroTier.TIER_1: 2.0,
    PoroTier.TIER_2: 4.0,
    PoroTier.TIER_3: 7.0,
    PoroTier.TIER_4: 12.0,
    PoroTier.TIER_5: 18.0,
    PoroTier.TIER_6: 30.0,
}

TIER_ASSET_KEYS = {
    PoroTier.TIER_1: "tier-1",
    PoroTier.TIER_2: "tier-2",
    PoroTier.TIER_3: "tier-3",
    PoroTier.TIER_4: "tier-4",
    PoroTier.TIER_5: "tier-5",
    PoroTier.TIER_6: "tier-6",
}

SPAWN_WEIGHTS = (
    (None, 55.0),
    (PoroTier.TIER_1, 26.0),
    (PoroTier.TIER_2, 11.0),
    (PoroTier.TIER_3, 4.5),
    (PoroTier.TIER_4, 2.2),
    (PoroTier.TIER_5, 1.0),
    (PoroTier.TIER_6, 0.3),
)


def poro_tier_level(tier: PoroTier) -> int:
    return TIER_ORDER.index(tier) + 1


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _roll_interval_seconds() -> int:
    minimum = settings.poro_min_interval_minutes * 60
    maximum = settings.poro_max_interval_minutes * 60
    mode = minimum + ((maximum - minimum) * 0.65)
    return max(minimum, min(maximum, int(random.triangular(minimum, maximum, mode))))


def _schedule_next_roll(from_time: datetime) -> datetime:
    return from_time + timedelta(seconds=_roll_interval_seconds())


def _roll_tier() -> PoroTier | None:
    draw = random.uniform(0.0, 100.0)
    cumulative = 0.0
    for tier, weight in SPAWN_WEIGHTS:
        cumulative += weight
        if draw <= cumulative:
            return tier
    return None


def _edge_point(edge: str) -> tuple[float, float]:
    inset_min = 0.12
    inset_max = 0.88
    overscan = 0.16
    if edge == "left":
        return (-overscan, random.uniform(inset_min, inset_max))
    if edge == "right":
        return (1.0 + overscan, random.uniform(inset_min, inset_max))
    if edge == "top":
        return (random.uniform(inset_min, inset_max), -overscan)
    return (random.uniform(inset_min, inset_max), 1.0 + overscan)


def _roll_path() -> tuple[float, float, float, float, int]:
    start_edge = random.choice(("left", "right", "top", "bottom"))
    candidate_edges = tuple(
        edge for edge in ("left", "right", "top", "bottom") if edge != start_edge
    )
    end_edge = random.choice(candidate_edges)
    start_x, start_y = _edge_point(start_edge)
    end_x, end_y = _edge_point(end_edge)
    distance = math.dist((start_x, start_y), (end_x, end_y))
    speed = random.uniform(0.09, 0.18)
    raw_duration = max(
        settings.poro_spawn_min_duration_seconds,
        min(settings.poro_spawn_max_duration_seconds, distance / speed),
    )
    return start_x, start_y, end_x, end_y, int(raw_duration * 1000)


async def _get_or_create_state(
    session: AsyncSession,
    user: User,
    *,
    as_of: datetime,
) -> UserPoroState:
    result = await session.execute(
        select(UserPoroState).where(UserPoroState.user_id == user.id)
    )
    state = result.scalar_one_or_none()
    if state is not None:
        return state

    state = UserPoroState(
        user_id=user.id,
        next_roll_at=_schedule_next_roll(as_of),
        active_spawn_id=None,
    )
    session.add(state)
    await session.flush()
    return state


async def _load_active_spawn(
    session: AsyncSession,
    state: UserPoroState,
) -> PoroSpawn | None:
    if state.active_spawn_id is None:
        return None
    return await session.get(PoroSpawn, state.active_spawn_id)


def _expire_spawn(
    state: UserPoroState,
    spawn: PoroSpawn,
    *,
    as_of: datetime,
) -> None:
    spawn.status = PoroSpawnStatus.EXPIRED
    state.active_spawn_id = None
    state.next_roll_at = _schedule_next_roll(as_of)
    state.updated_at = as_of


async def resolve_poro_state(
    session: AsyncSession,
    user: User,
    *,
    as_of: datetime | None = None,
) -> PoroStateSummary:
    now = _normalize_datetime(as_of) or datetime.now(UTC)
    state = await _get_or_create_state(session, user, as_of=now)
    active_spawn = await _load_active_spawn(session, state)
    next_roll_at = _normalize_datetime(state.next_roll_at)

    if active_spawn is not None:
        active_expires_at = _normalize_datetime(active_spawn.expires_at)
        if active_spawn.status != PoroSpawnStatus.ACTIVE or (
            active_expires_at is not None and active_expires_at <= now
        ):
            _expire_spawn(state, active_spawn, as_of=now)
            active_spawn = None
        else:
            state.updated_at = now
            return PoroStateSummary(
                active_spawn=active_spawn,
                next_roll_at=next_roll_at,
                server_time=now,
            )

    if next_roll_at is None:
        next_roll_at = _schedule_next_roll(now)
        state.next_roll_at = next_roll_at

    if next_roll_at > now:
        state.updated_at = now
        return PoroStateSummary(
            active_spawn=None,
            next_roll_at=next_roll_at,
            server_time=now,
        )

    tier = _roll_tier()
    if tier is None:
        state.next_roll_at = _schedule_next_roll(now)
        state.updated_at = now
        return PoroStateSummary(
            active_spawn=None,
            next_roll_at=state.next_roll_at,
            server_time=now,
        )

    start_x, start_y, end_x, end_y, duration_ms = _roll_path()
    spawn = PoroSpawn(
        public_id=uuid4().hex,
        user_id=user.id,
        tier=tier,
        reward_amount=TIER_REWARDS[tier],
        asset_key=TIER_ASSET_KEYS[tier],
        start_x=start_x,
        start_y=start_y,
        end_x=end_x,
        end_y=end_y,
        duration_ms=duration_ms,
        spawned_at=now,
        expires_at=now + timedelta(milliseconds=duration_ms),
        status=PoroSpawnStatus.ACTIVE,
    )
    session.add(spawn)
    await session.flush()

    state.active_spawn_id = spawn.id
    state.next_roll_at = None
    state.updated_at = now
    return PoroStateSummary(
        active_spawn=spawn,
        next_roll_at=state.next_roll_at,
        server_time=now,
    )


async def claim_poro_spawn(
    session: AsyncSession,
    user: User,
    spawn_public_id: str,
    *,
    as_of: datetime | None = None,
) -> PoroSpawn:
    now = _normalize_datetime(as_of) or datetime.now(UTC)
    spawn_result = await session.execute(
        select(PoroSpawn).where(
            PoroSpawn.public_id == spawn_public_id,
            PoroSpawn.user_id == user.id,
        )
    )
    spawn = spawn_result.scalar_one_or_none()
    if spawn is None:
        raise ValueError("Poro not found")

    state = await _get_or_create_state(session, user, as_of=now)
    spawn_expires_at = _normalize_datetime(spawn.expires_at)

    if spawn.status == PoroSpawnStatus.CLAIMED or spawn.claimed_at is not None:
        raise RuntimeError("Poro already claimed")

    if spawn.status != PoroSpawnStatus.ACTIVE or (
        spawn_expires_at is not None and spawn_expires_at <= now
    ):
        if spawn.status == PoroSpawnStatus.ACTIVE and (
            spawn_expires_at is not None and spawn_expires_at <= now
        ):
            _expire_spawn(state, spawn, as_of=now)
        raise RuntimeError("Poro already expired")

    user.balance = round_currency(user.balance + spawn.reward_amount)
    spawn.claimed_at = now
    spawn.status = PoroSpawnStatus.CLAIMED
    if state.active_spawn_id == spawn.id:
        state.active_spawn_id = None
    state.next_roll_at = _schedule_next_roll(now)
    state.updated_at = now
    await record_user_wealth_snapshot(
        session,
        user,
        source=UserWealthSnapshotSource.CREDIT_ACTION,
        as_of=now,
    )
    return spawn
