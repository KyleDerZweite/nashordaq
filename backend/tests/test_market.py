from datetime import UTC, datetime, timedelta

from app.models import PriceHistory


async def test_list_players(auth_client, seeded_player):
    resp = await auth_client.get("/api/market/players")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["display_name"] == "Test Player"
    assert data[0]["current_price"] == 25.0
    assert data[0]["trend"] == "up"


async def test_get_player_detail(auth_client, seeded_player):
    resp = await auth_client.get(f"/api/market/players/{seeded_player.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "Test Player"
    assert data["lp_abs"] == 1500
    assert data["trend"] == "up"
    assert data["price_history"] == []


async def test_get_player_not_found(auth_client):
    resp = await auth_client.get("/api/market/players/999")
    assert resp.status_code == 404


async def test_get_player_detail_returns_full_history_by_default(
    auth_client, db_session, seeded_player
):
    history_entries = [
        PriceHistory(
            player_id=seeded_player.id,
            price=10.0,
            lp_abs=1000,
            recorded_at=datetime.now(UTC) - timedelta(days=3),
        ),
        PriceHistory(
            player_id=seeded_player.id,
            price=12.5,
            lp_abs=1200,
            recorded_at=datetime.now(UTC) - timedelta(days=2),
        ),
        PriceHistory(
            player_id=seeded_player.id,
            price=15.0,
            lp_abs=1500,
            recorded_at=datetime.now(UTC) - timedelta(days=1),
        ),
    ]
    db_session.add_all(history_entries)
    await db_session.commit()

    full_resp = await auth_client.get(f"/api/market/players/{seeded_player.id}")
    assert full_resp.status_code == 200
    full_data = full_resp.json()
    assert len(full_data["price_history"]) == 3
    assert full_data["price_history"][0]["price"] == 15.0

    limited_resp = await auth_client.get(
        f"/api/market/players/{seeded_player.id}?limit=2"
    )
    assert limited_resp.status_code == 200
    limited_data = limited_resp.json()
    assert len(limited_data["price_history"]) == 2
    assert limited_data["price_history"][0]["price"] == 15.0
    assert limited_data["price_history"][1]["price"] == 12.5


async def test_trend_uses_recent_ten_history_points(
    auth_client, db_session, seeded_player
):
    history_entries = [
        PriceHistory(
            player_id=seeded_player.id,
            price=20.0 - index,
            lp_abs=2000 - (index * 10),
            recorded_at=datetime.now(UTC) - timedelta(days=10 - index),
        )
        for index in range(10)
    ]
    db_session.add_all(history_entries)
    await db_session.commit()

    list_resp = await auth_client.get("/api/market/players")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data[0]["trend"] == "down"

    detail_resp = await auth_client.get(f"/api/market/players/{seeded_player.id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["trend"] == "down"
