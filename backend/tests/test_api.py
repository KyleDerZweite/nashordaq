from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import app.main as main_module
from app.models import (
    PoroSpawn,
    PoroSpawnStatus,
    PoroTier,
    TrackedPlayer,
    User,
    UserWealthSnapshot,
    UserWealthSnapshotSource,
)
from app.riot import AccountData, PlayerNotFoundError, RankData


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    datetime.strptime(data["update"], "%Y-%m-%d %H:%M")


async def test_system_status_is_idle_without_tracked_players(auth_client, monkeypatch):
    monkeypatch.setattr(main_module, "get_last_market_update_at", lambda: None)
    monkeypatch.setattr(main_module, "is_scheduler_running", lambda: False)

    resp = await auth_client.get("/api/system/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "service_status": "ok",
        "scheduler_running": False,
        "market_status": "idle",
        "tracked_player_count": 0,
        "expected_update_interval_minutes": 1,
        "last_market_update_at": None,
        "gamba_enabled": True,
        "demo_mode_enabled": False,
    }


async def test_system_status_is_healthy_after_recent_market_refresh(
    auth_client, db_session, monkeypatch
):
    db_session.add(
        TrackedPlayer(
            game_name="RecentPlayer",
            tag_line="EUW",
            display_name="Recent Player",
        )
    )
    await db_session.commit()

    last_market_update_at = datetime.now(UTC)
    monkeypatch.setattr(
        main_module,
        "get_last_market_update_at",
        lambda: last_market_update_at,
    )
    monkeypatch.setattr(main_module, "is_scheduler_running", lambda: True)

    resp = await auth_client.get("/api/system/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["scheduler_running"] is True
    assert data["market_status"] == "healthy"
    assert data["tracked_player_count"] == 1
    assert data["expected_update_interval_minutes"] == 1
    assert data["last_market_update_at"] is not None


async def test_system_status_is_degraded_when_market_refresh_is_stale(
    auth_client, db_session, monkeypatch
):
    db_session.add_all(
        [
            TrackedPlayer(
                game_name="PlayerOne",
                tag_line="EUW",
                display_name="Player One",
            ),
            TrackedPlayer(
                game_name="PlayerTwo",
                tag_line="EUW",
                display_name="Player Two",
            ),
        ]
    )
    await db_session.commit()

    stale_market_update_at = datetime.now(UTC) - timedelta(minutes=5)
    monkeypatch.setattr(
        main_module,
        "get_last_market_update_at",
        lambda: stale_market_update_at,
    )
    monkeypatch.setattr(main_module, "is_scheduler_running", lambda: True)

    resp = await auth_client.get("/api/system/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["scheduler_running"] is True
    assert data["market_status"] == "degraded"
    assert data["tracked_player_count"] == 2
    assert data["expected_update_interval_minutes"] == 1
    assert data["last_market_update_at"] is not None


async def test_quote_success(client):
    mock_rank = RankData(
        puuid="test-puuid",
        summoner_id="test-summoner",
        tier="GOLD",
        rank="II",
        league_points=75,
        wins=12,
        losses=8,
        hot_streak=True,
        inactive=False,
    )

    with patch("app.main.get_rank", new_callable=AsyncMock, return_value=mock_rank):
        resp = await client.get(
            "/api/market/quote", params={"gameName": "TestPlayer", "tagLine": "NA1"}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "GOLD"
    assert data["rank"] == "II"
    assert data["leaguePoints"] == 75
    assert data["wins"] == 12
    assert data["losses"] == 8
    assert data["hotStreak"] is True


async def test_quote_not_found(client):
    with patch(
        "app.main.get_rank",
        new_callable=AsyncMock,
        side_effect=PlayerNotFoundError("Not found"),
    ):
        resp = await client.get(
            "/api/market/quote", params={"gameName": "Nobody", "tagLine": "0000"}
        )

    assert resp.status_code == 404
    assert "Not found" in resp.json()["detail"]


async def test_market_account_success(client):
    mock_account = AccountData(
        puuid="test-puuid",
        game_name="TestPlayer",
        tag_line="NA1",
    )

    with patch(
        "app.main.get_account_by_riot_id",
        new_callable=AsyncMock,
        return_value=mock_account,
    ):
        resp = await client.get(
            "/api/market/account", params={"gameName": "TestPlayer", "tagLine": "NA1"}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "game_name": "TestPlayer",
        "tag_line": "NA1",
        "puuid": "test-puuid",
    }


async def test_market_account_not_found(client):
    with patch(
        "app.main.get_account_by_riot_id",
        new_callable=AsyncMock,
        side_effect=PlayerNotFoundError("Player not found"),
    ):
        resp = await client.get(
            "/api/market/account", params={"gameName": "Nobody", "tagLine": "0000"}
        )

    assert resp.status_code == 404
    assert "Player not found" in resp.json()["detail"]


async def test_balance_insights_returns_current_state_and_history(
    auth_client, db_session
):
    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 1200.0
    db_session.add_all(
        [
            UserWealthSnapshot(
                user_id=user.id,
                source=UserWealthSnapshotSource.ONBOARDING,
                cash_balance=1000.0,
                holdings_value=0.0,
                active_gamba_value=0.0,
                debt_outstanding=0.0,
                net_worth=1000.0,
                recorded_at=datetime.now(UTC) - timedelta(hours=3),
            ),
            UserWealthSnapshot(
                user_id=user.id,
                source=UserWealthSnapshotSource.CREDIT_ACTION,
                cash_balance=1200.0,
                holdings_value=50.0,
                active_gamba_value=25.0,
                debt_outstanding=10.0,
                net_worth=1265.0,
                recorded_at=datetime.now(UTC) - timedelta(hours=1),
            ),
        ]
    )
    await db_session.commit()

    resp = await auth_client.get("/api/user/balance-insights")

    assert resp.status_code == 200
    data = resp.json()
    assert data["cash_balance"] == 1200.0
    assert data["playing_income_last_24h"] == 0.0
    assert data["playing_income_lifetime_total"] == 0.0
    assert len(data["history"]) == 2
    assert data["history"][0]["source"] == "ONBOARDING"
    assert data["history"][1]["source"] == "CREDIT_ACTION"


async def test_balance_insights_includes_poro_rewards(auth_client, db_session):
    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None

    now = datetime.now(UTC)
    db_session.add_all(
        [
            PoroSpawn(
                public_id="poro-recent",
                user_id=user.id,
                tier=PoroTier.TIER_2,
                reward_amount=12.0,
                asset_key="tier-2",
                start_x=-0.16,
                start_y=0.25,
                end_x=0.5,
                end_y=-0.16,
                duration_ms=6000,
                spawned_at=now - timedelta(hours=2, seconds=6),
                expires_at=now - timedelta(hours=2),
                claimed_at=now - timedelta(hours=2),
                status=PoroSpawnStatus.CLAIMED,
            ),
            PoroSpawn(
                public_id="poro-older",
                user_id=user.id,
                tier=PoroTier.TIER_1,
                reward_amount=6.0,
                asset_key="tier-1",
                start_x=1.16,
                start_y=0.4,
                end_x=0.5,
                end_y=1.16,
                duration_ms=6000,
                spawned_at=now - timedelta(days=2, seconds=6),
                expires_at=now - timedelta(days=2),
                claimed_at=now - timedelta(days=2),
                status=PoroSpawnStatus.CLAIMED,
            ),
        ]
    )
    await db_session.commit()

    resp = await auth_client.get("/api/user/balance-insights")

    assert resp.status_code == 200
    data = resp.json()
    assert data["playing_income_last_24h"] == 12.0
    assert data["playing_income_lifetime_total"] == 18.0
