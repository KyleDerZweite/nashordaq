from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import HoldingLot, PriceHistory, TrackedPlayer
from app.pricing import calculate_market_impact

# --- Unit tests for calculate_market_impact ---


def test_buy_impact_basic():
    avg, new = calculate_market_impact(100.0, 10, "BUY", liquidity_depth=1000)
    # impact = 10/1000 = 0.01
    assert avg == pytest.approx(100.0 * 1.005)
    assert new == pytest.approx(100.0 * 1.01)


def test_sell_impact_basic():
    avg, new = calculate_market_impact(100.0, 10, "SELL", liquidity_depth=1000)
    assert avg == pytest.approx(100.0 * 0.995)
    assert new == pytest.approx(100.0 * 0.99)


def test_large_buy_impact():
    avg, new = calculate_market_impact(20.0, 300, "BUY", liquidity_depth=1000)
    # impact = 0.3
    assert avg == pytest.approx(20.0 * 1.15)
    assert new == pytest.approx(20.0 * 1.3)


def test_round_trip_always_loses():
    """A buy then sell of the same quantity always loses money."""
    price = 50.0
    qty = 100
    depth = 1000

    buy_avg, price_after_buy = calculate_market_impact(
        price, qty, "BUY", liquidity_depth=depth
    )
    sell_avg, _ = calculate_market_impact(
        price_after_buy, qty, "SELL", liquidity_depth=depth
    )

    buy_cost = buy_avg * qty
    sell_proceeds = sell_avg * qty
    assert sell_proceeds < buy_cost


def test_sell_floor():
    """Sell impact cannot push price below 1.0."""
    avg, new = calculate_market_impact(2.0, 900, "SELL", liquidity_depth=1000)
    assert new == 1.0
    assert avg >= 1.0


def test_zero_quantity_no_impact():
    avg, new = calculate_market_impact(25.0, 0, "BUY", liquidity_depth=1000)
    assert avg == 25.0
    assert new == 25.0


def test_zero_depth_no_impact():
    avg, new = calculate_market_impact(25.0, 10, "BUY", liquidity_depth=0)
    assert avg == 25.0
    assert new == 25.0


def test_small_trade_negligible_impact():
    avg, new = calculate_market_impact(30.0, 1, "BUY", liquidity_depth=1000)
    # 1 share: 0.1% impact, 0.05% slippage
    assert abs(avg - 30.0) < 0.02
    assert abs(new - 30.0) < 0.04


# --- Integration tests for order flow ---


async def test_buy_moves_price_up(auth_client, tradable_player, db_session):
    original_price = tradable_player.current_price

    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 10},
    )
    assert resp.status_code == 201

    await db_session.refresh(tradable_player)
    # 10/1000 = 1% impact
    assert tradable_player.current_price == pytest.approx(original_price * 1.01)


async def test_sell_moves_price_down(auth_client, tradable_player, db_session):
    # First buy shares (small enough to afford)
    buy_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 10},
    )
    assert buy_resp.status_code == 201

    await db_session.refresh(tradable_player)
    price_after_buy = tradable_player.current_price

    # Unlock holding period
    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    lots_result = await db_session.execute(
        select(HoldingLot).where(
            HoldingLot.user_id == user_id,
            HoldingLot.player_id == tradable_player.id,
        )
    )
    lot = lots_result.scalar_one()
    lot.acquired_at = datetime.now(UTC) - timedelta(hours=5)
    await db_session.commit()

    # Sell
    sell_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "SELL", "quantity": 10},
    )
    assert sell_resp.status_code == 201

    await db_session.refresh(tradable_player)
    assert tradable_player.current_price < price_after_buy


async def test_buy_records_price_history(auth_client, tradable_player, db_session):
    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 10},
    )
    assert resp.status_code == 201

    history = await db_session.execute(
        select(PriceHistory).where(
            PriceHistory.player_id == tradable_player.id,
        )
    )
    rows = history.scalars().all()
    assert len(rows) == 1
    await db_session.refresh(tradable_player)
    assert rows[0].price == pytest.approx(tradable_player.current_price)


async def test_revert_reverses_price_impact(auth_client, tradable_player, db_session):
    original_price = tradable_player.current_price

    buy_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 10},
    )
    assert buy_resp.status_code == 201

    await db_session.refresh(tradable_player)
    assert tradable_player.current_price != original_price

    # Revert
    revert_resp = await auth_client.delete(f"/api/orders/{buy_resp.json()['id']}")
    assert revert_resp.status_code == 200

    await db_session.refresh(tradable_player)
    # Price should be approximately back to original
    assert tradable_player.current_price == pytest.approx(original_price, rel=0.01)


async def test_order_response_includes_impact_fields(auth_client, tradable_player):
    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 20},
    )
    assert resp.status_code == 201
    data = resp.json()

    assert data["market_impact_pct"] is not None
    assert data["market_impact_pct"] > 0  # Buy should be positive
    assert data["price_after_impact"] is not None
    assert data["price_after_impact"] > data["execution_price"]


async def test_gamba_does_not_move_price(
    auth_client, tradable_player, seeded_player, db_session, monkeypatch
):
    """Gamba orders should NOT apply market impact."""
    import random

    from app.config import settings

    monkeypatch.setattr(random, "choice", lambda _: tradable_player)
    monkeypatch.setattr(random, "uniform", lambda a, b: a)
    monkeypatch.setattr(settings, "gamba_max_active_positions_per_user", 5)

    original_price = tradable_player.current_price

    resp = await auth_client.post(
        "/api/gamba",
        json={"cash_amount": 100.0},
    )
    assert resp.status_code == 201

    await db_session.refresh(tradable_player)
    assert tradable_player.current_price == original_price


async def test_impact_scales_with_order_size(auth_client, tradable_player, db_session):
    """Larger orders should have proportionally larger impact."""
    player2 = TrackedPlayer(
        game_name="ImpactB",
        tag_line="EUW",
        display_name="Impact B",
        current_price=25.0,
        lp_abs=1500,
        previous_lp_abs=1400,
        last_updated=datetime.now(UTC),
    )
    db_session.add(player2)
    await db_session.commit()
    await db_session.refresh(player2)

    # Small order on tradable_player (price 25)
    resp1 = await auth_client.post(
        "/api/orders",
        json={
            "player_id": tradable_player.id,
            "side": "BUY",
            "quantity": 5,
        },
    )
    # Larger order on player2 (also price 25)
    resp2 = await auth_client.post(
        "/api/orders",
        json={"player_id": player2.id, "side": "BUY", "quantity": 30},
    )
    assert resp1.status_code == 201
    assert resp2.status_code == 201

    await db_session.refresh(tradable_player)
    await db_session.refresh(player2)

    small_impact = (tradable_player.current_price - 25.0) / 25.0
    large_impact = (player2.current_price - 25.0) / 25.0
    assert large_impact > small_impact * 3
