import asyncio
import math
import random
from collections import defaultdict
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


class PoroStateNotifier:
    def __init__(self) -> None:
        self._listeners: dict[int, set[asyncio.Event]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, user_id: int) -> asyncio.Event:
        listener = asyncio.Event()
        async with self._lock:
            self._listeners[user_id].add(listener)
        return listener

    async def unsubscribe(self, user_id: int, listener: asyncio.Event) -> None:
        async with self._lock:
            listeners = self._listeners.get(user_id)
            if listeners is None:
                return
            listeners.discard(listener)
            if not listeners:
                self._listeners.pop(user_id, None)

    async def notify(self, user_id: int) -> None:
        async with self._lock:
            listeners = tuple(self._listeners.get(user_id, ()))

        for listener in listeners:
            listener.set()


poro_state_notifier = PoroStateNotifier()


TIER_ORDER = (
    PoroTier.TIER_1,
    PoroTier.TIER_2,
    PoroTier.TIER_3,
    PoroTier.TIER_4,
    PoroTier.TIER_5,
    PoroTier.TIER_6,
)

TIER_REWARDS = {
    PoroTier.TIER_1: 8.0,
    PoroTier.TIER_2: 13.0,
    PoroTier.TIER_3: 21.0,
    PoroTier.TIER_4: 34.0,
    PoroTier.TIER_5: 55.0,
    PoroTier.TIER_6: 89.0,
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
    (None, 69.1628),
    (PoroTier.TIER_1, 12.5),
    (PoroTier.TIER_2, 7.6923),
    (PoroTier.TIER_3, 4.7619),
    (PoroTier.TIER_4, 2.9412),
    (PoroTier.TIER_5, 1.8182),
    (PoroTier.TIER_6, 1.1236),
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
    minimum = settings.poro_min_interval_seconds_override
    maximum = settings.poro_max_interval_seconds_override

    if minimum is None or maximum is None:
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


def _adjacent_edges(edge: str) -> tuple[str, str]:
    if edge in {"left", "right"}:
        return ("top", "bottom")
    return ("left", "right")


def _roll_path() -> tuple[float, float, float, float, int]:
    start_edge = random.choice(("left", "right", "top", "bottom"))
    candidate_edges = _adjacent_edges(start_edge)
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


async def _sync_poro_state(
    session: AsyncSession,
    user: User,
    state: UserPoroState,
    *,
    as_of: datetime,
) -> tuple[PoroStateSummary, bool]:
    now = _normalize_datetime(as_of) or datetime.now(UTC)
    active_spawn = await _load_active_spawn(session, state)
    next_roll_at = _normalize_datetime(state.next_roll_at)
    changed = False

    if active_spawn is not None:
        active_expires_at = _normalize_datetime(active_spawn.expires_at)
        if active_spawn.status != PoroSpawnStatus.ACTIVE or (
            active_expires_at is not None and active_expires_at <= now
        ):
            _expire_spawn(state, active_spawn, as_of=now)
            active_spawn = None
            next_roll_at = _normalize_datetime(state.next_roll_at)
            changed = True
        else:
            return (
                PoroStateSummary(
                    active_spawn=active_spawn,
                    next_roll_at=next_roll_at,
                    server_time=now,
                ),
                changed,
            )

    if next_roll_at is None:
        next_roll_at = _schedule_next_roll(now)
        state.next_roll_at = next_roll_at
        state.updated_at = now
        changed = True

    if next_roll_at > now:
        return (
            PoroStateSummary(
                active_spawn=None,
                next_roll_at=next_roll_at,
                server_time=now,
            ),
            changed,
        )

    tier = _roll_tier()
    if tier is None:
        state.next_roll_at = _schedule_next_roll(now)
        state.updated_at = now
        return (
            PoroStateSummary(
                active_spawn=None,
                next_roll_at=state.next_roll_at,
                server_time=now,
            ),
            True,
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
    return (
        PoroStateSummary(
            active_spawn=spawn,
            next_roll_at=state.next_roll_at,
            server_time=now,
        ),
        True,
    )


async def resolve_poro_state(
    session: AsyncSession,
    user: User,
    *,
    as_of: datetime | None = None,
) -> PoroStateSummary:
    now = _normalize_datetime(as_of) or datetime.now(UTC)
    state = await _get_or_create_state(session, user, as_of=now)
    summary, _ = await _sync_poro_state(session, user, state, as_of=now)
    return summary


# Fingerprint cache used by maintain_poro_states to detect external DB changes
# (e.g. spawns created by the priming script that bypass the notifier).
_maintenance_state_cache: dict[int, tuple[int | None, str | None]] = {}


def _state_fingerprint(
    state: UserPoroState,
) -> tuple[int | None, str | None]:
    updated = str(state.updated_at) if state.updated_at is not None else None
    return (state.active_spawn_id, updated)


async def maintain_poro_states(
    session: AsyncSession,
    *,
    as_of: datetime | None = None,
) -> set[int]:
    now = _normalize_datetime(as_of) or datetime.now(UTC)
    result = await session.execute(
        select(User).where(User.linked_player_id.is_not(None))
    )
    users = result.scalars().all()
    changed_user_ids: set[int] = set()

    for user in users:
        state = await _get_or_create_state(session, user, as_of=now)
        _, changed = await _sync_poro_state(session, user, state, as_of=now)

        fingerprint = _state_fingerprint(state)
        if _maintenance_state_cache.get(user.id) != fingerprint:
            changed = True
        _maintenance_state_cache[user.id] = fingerprint

        if changed:
            changed_user_ids.add(user.id)

    return changed_user_ids


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
