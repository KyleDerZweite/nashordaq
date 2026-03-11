from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app import poro as poro_service
from app.models import (
    PoroSpawn,
    PoroSpawnStatus,
    User,
    UserPoroState,
    UserWealthSnapshot,
)


async def _onboard_poro_user(auth_client):
    onboard_resp = await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "poro-user",
            "tag_line": "EUW",
            "display_name": "Poro User",
        },
    )
    assert onboard_resp.status_code == 200


@pytest.fixture
def force_spawn_roll(monkeypatch):
    monkeypatch.setattr(poro_service, "_roll_interval_seconds", lambda: 1800)
    monkeypatch.setattr(
        poro_service,
        "_roll_tier",
        lambda: poro_service.PoroTier.TIER_3,
    )
    monkeypatch.setattr(
        poro_service,
        "_roll_path",
        lambda: (-0.16, 0.25, 1.16, 0.75, 12000),
    )


async def test_poro_state_waits_until_next_roll(auth_client):
    await _onboard_poro_user(auth_client)

    first_resp = await auth_client.get("/api/poro")
    assert first_resp.status_code == 200
    first_body = first_resp.json()
    assert first_body["enabled"] is True
    assert first_body["active_spawn"] is None
    assert first_body["next_roll_at"] is not None


async def test_poro_state_creates_spawn_when_roll_is_due(
    auth_client,
    db_session,
    force_spawn_roll,
):
    await _onboard_poro_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    state_result = await db_session.execute(
        select(UserPoroState).where(UserPoroState.user_id == user_id)
    )
    state = state_result.scalar_one_or_none()
    if state is None:
        state = UserPoroState(
            user_id=user_id,
            next_roll_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        db_session.add(state)
    else:
        state.next_roll_at = datetime.now(UTC) - timedelta(seconds=1)
        state.active_spawn_id = None
    await db_session.commit()

    resp = await auth_client.get("/api/poro")
    assert resp.status_code == 200
    body = resp.json()
    spawn = body["active_spawn"]
    assert spawn is not None
    assert spawn["tier"] == 3
    assert spawn["reward_amount"] == pytest.approx(7.0)
    assert spawn["duration_ms"] == 12000
    assert body["next_roll_at"] is None


async def test_poro_claim_increases_balance_and_records_snapshot(
    auth_client,
    db_session,
    force_spawn_roll,
):
    await _onboard_poro_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    state_result = await db_session.execute(
        select(UserPoroState).where(UserPoroState.user_id == user_id)
    )
    state = state_result.scalar_one_or_none()
    if state is None:
        state = UserPoroState(
            user_id=user_id,
            next_roll_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        db_session.add(state)
    else:
        state.next_roll_at = datetime.now(UTC) - timedelta(seconds=1)
        state.active_spawn_id = None
    await db_session.commit()

    spawn_resp = await auth_client.get("/api/poro")
    spawn_id = spawn_resp.json()["active_spawn"]["spawn_id"]

    user = await db_session.get(User, user_id)
    assert user is not None
    starting_balance = user.balance

    claim_resp = await auth_client.post("/api/poro/claim", json={"spawn_id": spawn_id})
    assert claim_resp.status_code == 200
    claim_body = claim_resp.json()
    assert claim_body["reward_amount"] == pytest.approx(7.0)
    assert claim_body["balance"] == pytest.approx(starting_balance + 7.0)

    spawn_result = await db_session.execute(
        select(PoroSpawn).where(PoroSpawn.public_id == spawn_id)
    )
    spawn = spawn_result.scalar_one()
    assert spawn.status == PoroSpawnStatus.CLAIMED
    assert spawn.claimed_at is not None

    snapshot_result = await db_session.execute(
        select(UserWealthSnapshot).where(UserWealthSnapshot.user_id == user_id)
    )
    snapshots = snapshot_result.scalars().all()
    assert len(snapshots) >= 1


async def test_poro_claim_rejects_duplicate_claims(
    auth_client,
    db_session,
    force_spawn_roll,
):
    await _onboard_poro_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    state = UserPoroState(
        user_id=user_id,
        next_roll_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    db_session.add(state)
    await db_session.commit()

    spawn_resp = await auth_client.get("/api/poro")
    spawn_id = spawn_resp.json()["active_spawn"]["spawn_id"]

    first_claim = await auth_client.post("/api/poro/claim", json={"spawn_id": spawn_id})
    assert first_claim.status_code == 200

    second_claim = await auth_client.post(
        "/api/poro/claim",
        json={"spawn_id": spawn_id},
    )
    assert second_claim.status_code == 409
    assert second_claim.json()["detail"] == "Poro already claimed"


async def test_poro_claim_rejects_expired_spawns(
    auth_client,
    db_session,
):
    await _onboard_poro_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    spawn = PoroSpawn(
        public_id="expired-poro",
        user_id=user_id,
        tier=poro_service.PoroTier.TIER_2,
        reward_amount=4.0,
        asset_key="tier-2",
        start_x=-0.16,
        start_y=0.25,
        end_x=1.16,
        end_y=0.75,
        duration_ms=12000,
        spawned_at=datetime.now(UTC) - timedelta(seconds=20),
        expires_at=datetime.now(UTC) - timedelta(seconds=5),
        status=PoroSpawnStatus.ACTIVE,
    )
    db_session.add(spawn)
    await db_session.flush()
    db_session.add(
        UserPoroState(
            user_id=user_id,
            active_spawn_id=spawn.id,
            next_roll_at=None,
        )
    )
    await db_session.commit()

    claim_resp = await auth_client.post(
        "/api/poro/claim",
        json={"spawn_id": "expired-poro"},
    )
    assert claim_resp.status_code == 409
    assert claim_resp.json()["detail"] == "Poro already expired"


async def test_poro_requires_onboarding(auth_client):
    resp = await auth_client.get(
        "/api/poro",
        headers={"Remote-User": "fresh-user"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Complete onboarding first"
