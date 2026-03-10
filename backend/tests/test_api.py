from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import app.main as main_module
from app.models import TrackedPlayer
from app.riot import PlayerNotFoundError, RankData


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
    assert data["expected_update_interval_minutes"] == 2
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
        veteran=False,
        inactive=False,
        fresh_blood=True,
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
