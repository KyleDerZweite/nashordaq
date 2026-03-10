from app.config import settings
from app.models import Holding


async def test_empty_portfolio(auth_client):
    onboard = await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "portfolio-user",
            "tag_line": "EUW",
            "display_name": "Portfolio User",
        },
    )
    assert onboard.status_code == 200

    resp = await auth_client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.json()
    assert data["balance"] == settings.starting_balance
    assert data["holdings_value"] == 0.0
    assert data["active_gamba_value"] == 0.0
    assert data["debt_outstanding"] == 0.0
    assert data["holdings"] == []
    assert data["total_value"] == settings.starting_balance


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
    assert data["holdings"][0]["average_buy_price"] == 0.0
    assert data["holdings"][0]["current_price"] == 25.0
    assert data["holdings"][0]["cost_basis"] == 0.0
    assert data["holdings"][0]["market_value"] == 250.0
    assert data["holdings"][0]["unrealized_pnl"] == 250.0
    assert data["holdings"][0]["unrealized_pnl_pct"] == 0.0
    assert data["holdings_value"] == 250.0
    assert data["active_gamba_value"] == 0.0
    assert data["debt_outstanding"] == 0.0
    assert data["total_value"] == settings.starting_balance + 250.0


async def test_portfolio_shows_buy_price_vs_current(
    auth_client, tradable_player, db_session
):
    buy_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 2},
    )
    assert buy_resp.status_code == 201

    tradable_player.current_price = 30.0
    await db_session.commit()

    resp = await auth_client.get("/api/portfolio")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["holdings"]) == 1
    assert data["holdings"][0]["average_buy_price"] == 25.0
    assert data["holdings"][0]["current_price"] == 30.0
    assert data["holdings"][0]["cost_basis"] == 50.0
    assert data["holdings"][0]["market_value"] == 60.0
    assert data["holdings"][0]["unrealized_pnl"] == 10.0
    assert data["holdings"][0]["unrealized_pnl_pct"] == 20.0
    assert data["holdings_value"] == 60.0
