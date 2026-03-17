from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.models import (
    PlayingIncomeEntry,
    PlayingIncomeMatchResult,
    PoroSpawn,
    PoroSpawnStatus,
    PoroTier,
    TrackedPlayer,
    User,
)


async def test_admin_overview_requires_admin(auth_client):
    resp = await auth_client.get("/api/admin/overview")

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


async def test_admin_can_view_overview_users_and_orders(
    auth_client, tradable_player, monkeypatch
):
    await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 1},
    )
    monkeypatch.setattr(settings, "admin_remote_users", "testuser@test.dev")

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={
            "Remote-User": "seconduser",
            "Remote-Email": "seconduser@test.dev",
            "Remote-Name": "Second User",
        },
    ) as second_user_client:
        onboarding_resp = await second_user_client.post(
            "/api/user/onboarding",
            json={
                "game_name": "secondadmin",
                "tag_line": "EUW",
            },
        )
        assert onboarding_resp.status_code == 200

    overview_resp = await auth_client.get("/api/admin/overview")
    users_resp = await auth_client.get("/api/admin/users")
    status_resp = await auth_client.get("/api/admin/system/status")

    assert overview_resp.status_code == 200
    assert overview_resp.json()["admin_users"] == 1
    assert overview_resp.json()["total_users"] >= 2
    assert overview_resp.json()["total_orders"] >= 1

    assert users_resp.status_code == 200
    users = users_resp.json()
    assert users[0]["role"] == "admin"
    assert {user["email"] for user in users} >= {
        "testuser@test.dev",
        "seconduser@test.dev",
    }

    assert status_resp.status_code == 200
    assert status_resp.json()["service_status"] == "ok"


async def test_admin_can_view_user_portfolio(auth_client, tradable_player, monkeypatch):
    buy_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 2},
    )
    assert buy_resp.status_code == 201

    me_resp = await auth_client.get("/api/user/me")
    assert me_resp.status_code == 200
    user_id = me_resp.json()["id"]

    monkeypatch.setattr(settings, "admin_remote_users", "testuser@test.dev")

    resp = await auth_client.get(f"/api/admin/users/{user_id}/portfolio")

    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "admin"
    assert data["linked_player_game_name"] == "TestPlayer"
    assert data["portfolio"]["holdings"][0]["player_name"] == "Tradable Player"
    assert data["portfolio"]["holdings"][0]["player_game_name"] == "TradablePlayer"
    assert data["portfolio"]["holdings"][0]["quantity"] == 2


async def test_admin_can_restore_a_spent_rescue_use(
    auth_client,
    db_session,
    monkeypatch,
):
    await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "bank-admin",
            "tag_line": "EUW",
        },
    )

    me_resp = await auth_client.get("/api/user/me")
    assert me_resp.status_code == 200
    user_id = me_resp.json()["id"]

    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 0.0
    await db_session.commit()

    borrow_resp = await auth_client.post("/api/bank/borrow", json={"amount": 750})
    assert borrow_resp.status_code == 200

    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 900.0
    await db_session.commit()

    repay_resp = await auth_client.post("/api/bank/repay", json={"amount": 765})
    assert repay_resp.status_code == 200
    assert repay_resp.json()["rescue_loan_uses_remaining"] == 0

    monkeypatch.setattr(settings, "admin_remote_users", "testuser@test.dev")

    unlock_resp = await auth_client.post(f"/api/admin/users/{user_id}/rescue-unlock")

    assert unlock_resp.status_code == 200
    data = unlock_resp.json()
    assert data["rescue_loan_uses_remaining"] == 1
    assert data["rescue_loan_available"] is True
    assert data["rescue_loan_block_reason"] is None


async def test_admin_can_view_player_insights(auth_client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "admin_remote_users", "testuser@test.dev")

    me_resp = await auth_client.get("/api/user/me")
    assert me_resp.status_code == 200
    user_id = me_resp.json()["id"]

    user = await db_session.get(User, user_id)
    assert user is not None
    player = TrackedPlayer(
        game_name="insight-admin",
        tag_line="EUW",
        display_name="Insight Admin",
        current_price=25.0,
        lp_abs=1500,
        previous_lp_abs=1470,
    )
    db_session.add(player)
    await db_session.flush()
    user.linked_player_id = player.id

    player.avg_lp_gain_on_win = 30.0
    player.avg_lp_loss_on_loss = 10.0
    player.ranked_wins_snapshot = 12
    player.ranked_losses_snapshot = 6
    player.streak = 4

    db_session.add(
        PlayingIncomeEntry(
            user_id=user.id,
            player_id=player.id,
            match_id="EUW1_123",
            match_result=PlayingIncomeMatchResult.WIN,
            match_duration_seconds=1800,
            match_completed_at=datetime(2026, 3, 13, 10, 0, tzinfo=UTC),
            share_price=25.0,
            base_rate=0.0125,
            outcome_multiplier=1.0,
            amount=0.36,
        )
    )
    db_session.add(
        PoroSpawn(
            public_id="poro123",
            user_id=user.id,
            tier=PoroTier.TIER_2,
            reward_amount=8.0,
            asset_key="poro2",
            start_x=0.0,
            start_y=0.0,
            end_x=1.0,
            end_y=1.0,
            duration_ms=6000,
            spawned_at=datetime(2026, 3, 13, 9, 0, tzinfo=UTC),
            expires_at=datetime(2026, 3, 13, 9, 10, tzinfo=UTC),
            claimed_at=datetime(2026, 3, 13, 9, 1, tzinfo=UTC),
            status=PoroSpawnStatus.CLAIMED,
        )
    )
    await db_session.commit()

    resp = await auth_client.get("/api/admin/players/insights")

    assert resp.status_code == 200
    data = resp.json()
    tracked = next(item for item in data if item["player_id"] == player.id)
    assert tracked["linked_user_display_name"] == "Test User"
    assert tracked["avg_lp_gain_on_win"] == 30.0
    assert tracked["avg_lp_loss_on_loss"] == 10.0
    assert tracked["estimated_lp_ratio_clamped"] == 0.3333333333333333
    assert tracked["effective_positive_streak"] == 4
    assert tracked["playing_income_lifetime_total"] == 0.36
    assert tracked["poro_rewards_total"] == 8.0
    assert tracked["recent_playing_income_entries"][0]["match_id"] == "EUW1_123"
    assert tracked["recent_poro_rewards"][0]["spawn_id"] == "poro123"
