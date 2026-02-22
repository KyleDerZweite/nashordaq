from app.models import Holding


async def test_empty_portfolio(auth_client):
    resp = await auth_client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert data["balance"] == 10000.0
    assert data["holdings"] == []
    assert data["total_value"] == 10000.0


async def test_portfolio_with_holdings(auth_client, seeded_player, db_session):
    await auth_client.get("/api/user/me")

    user_resp = await auth_client.get("/api/user/me")
    user_id = user_resp.json()["id"]

    holding = Holding(user_id=user_id, player_id=seeded_player.id, quantity=10)
    db_session.add(holding)
    await db_session.commit()

    resp = await auth_client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["holdings"]) == 1
    assert data["holdings"][0]["quantity"] == 10
    assert data["holdings"][0]["current_price"] == 25.0
    assert data["holdings"][0]["market_value"] == 250.0
    assert data["total_value"] == 10250.0
