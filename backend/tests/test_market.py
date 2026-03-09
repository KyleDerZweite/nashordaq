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
