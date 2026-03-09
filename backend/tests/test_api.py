from datetime import datetime
from unittest.mock import AsyncMock, patch

from app.riot import PlayerNotFoundError, RankData


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    datetime.strptime(data["update"], "%Y-%m-%d %H:%M")


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
