from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.config import settings
from app.main import app
from app.models import HoldingLot, Order, OrderStatus, TrackedPlayer


async def test_place_buy_order(auth_client, tradable_player):
    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 2},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["side"] == "BUY"
    assert data["quantity"] == 2
    assert data["status"] == "EXECUTED"
    assert data["player_name"] == "Tradable Player"
    assert data["execution_price"] == 25.0

    me_resp = await auth_client.get("/api/user/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["balance"] == settings.starting_balance - 50.0


async def test_place_buy_insufficient_balance(auth_client, tradable_player):
    # Price is 25.0, balance is 10000.0, so 401 shares = 10025.0 > 10000.0
    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 401},
    )
    assert resp.status_code == 400
    assert "Insufficient balance" in resp.json()["detail"]


async def test_place_buy_requires_first_market_update(
    auth_client, seeded_player, db_session
):
    player = TrackedPlayer(
        game_name="FreshPlayer",
        tag_line="EUW",
        display_name="Fresh Player",
        current_price=10.0,
        lp_abs=0,
        previous_lp_abs=0,
        last_updated=None,
    )
    db_session.add(player)
    await db_session.commit()
    await db_session.refresh(player)

    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": player.id, "side": "BUY", "quantity": 1},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Player has not received a first market update yet"


async def test_place_buy_rejects_own_stock(auth_client, seeded_player, db_session):
    rival_player = TrackedPlayer(
        game_name="RivalPlayer",
        tag_line="EUW",
        display_name="Rival Player",
        current_price=20.0,
        lp_abs=1400,
        previous_lp_abs=1350,
        last_updated=datetime.now(UTC),
    )
    db_session.add(rival_player)
    await db_session.commit()
    await db_session.refresh(rival_player)

    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": seeded_player.id, "side": "BUY", "quantity": 1},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "You cannot buy your own stock"

    allowed_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": rival_player.id, "side": "BUY", "quantity": 1},
    )
    assert allowed_resp.status_code == 201


async def test_place_sell_no_shares(auth_client, seeded_player):
    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": seeded_player.id, "side": "SELL", "quantity": 1},
    )
    assert resp.status_code == 400
    assert "Insufficient shares" in resp.json()["detail"]


async def test_place_order_invalid_player(auth_client):
    onboard = await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "invalid-user",
            "tag_line": "EUW",
            "display_name": "Invalid User",
        },
    )
    assert onboard.status_code == 200

    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": 999, "side": "BUY", "quantity": 1},
    )
    assert resp.status_code == 404


async def test_place_order_invalid_quantity(auth_client, seeded_player):
    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": seeded_player.id, "side": "BUY", "quantity": 0},
    )
    assert resp.status_code == 422


async def test_cancel_order(auth_client, tradable_player):
    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 1},
    )
    order_id = resp.json()["id"]

    resp = await auth_client.delete(f"/api/orders/{order_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "REVERTED"

    me_resp = await auth_client.get("/api/user/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["balance"] == settings.starting_balance


async def test_cancel_nonexistent_order(auth_client):
    onboard = await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "cancel-user",
            "tag_line": "EUW",
            "display_name": "Cancel User",
        },
    )
    assert onboard.status_code == 200

    resp = await auth_client.delete("/api/orders/999")
    assert resp.status_code == 404


async def test_cancel_already_cancelled(auth_client, tradable_player):
    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 1},
    )
    order_id = resp.json()["id"]
    resp = await auth_client.delete(f"/api/orders/{order_id}")
    assert resp.status_code == 200

    resp = await auth_client.delete(f"/api/orders/{order_id}")
    assert resp.status_code == 400
    assert "Order cannot be cancelled" in resp.json()["detail"]


async def test_cancel_order_expired_grace_window(
    auth_client, tradable_player, db_session
):
    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 1},
    )
    assert resp.status_code == 201
    order_id = resp.json()["id"]

    order_result = await db_session.execute(select(Order).where(Order.id == order_id))
    order = order_result.scalar_one()
    assert order.executed_at is not None
    order.executed_at = datetime.now(UTC) - timedelta(
        seconds=settings.buy_revert_grace_seconds + 1
    )
    await db_session.commit()

    cancel_resp = await auth_client.delete(f"/api/orders/{order_id}")
    assert cancel_resp.status_code == 400
    assert "Revert window expired" in cancel_resp.json()["detail"]


async def test_cancel_order_after_partial_sell(
    auth_client, tradable_player, db_session
):
    buy_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 3},
    )
    assert buy_resp.status_code == 201
    order_id = buy_resp.json()["id"]

    sell_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "SELL", "quantity": 1},
    )
    assert sell_resp.status_code == 201

    cancel_resp = await auth_client.delete(f"/api/orders/{order_id}")
    assert cancel_resp.status_code == 400
    assert (
        "Order cannot be reverted after shares were sold"
        in cancel_resp.json()["detail"]
    )


async def test_list_orders(auth_client, tradable_player):
    await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 1},
    )
    await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 2},
    )

    resp = await auth_client.get("/api/orders")
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert resp.json()[0]["user_name"] == "Test Player"


async def test_list_orders_filter_status(auth_client, tradable_player):
    await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 1},
    )
    await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 2},
    )

    resp = await auth_client.get("/api/orders", params={"status": "EXECUTED"})
    assert len(resp.json()) == 2


async def test_list_orders_filter_status_reverted(auth_client, tradable_player):
    buy_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 1},
    )
    assert buy_resp.status_code == 201

    revert_resp = await auth_client.delete(f"/api/orders/{buy_resp.json()['id']}")
    assert revert_resp.status_code == 200

    resp = await auth_client.get("/api/orders", params={"status": "REVERTED"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["status"] == "REVERTED"


async def test_list_recent_orders_includes_all_players(
    auth_client, seeded_player, tradable_player
):
    await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 1},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Remote-User": "seconduser"},
    ) as second_user_client:
        second_onboarding = await second_user_client.post(
            "/api/user/onboarding",
            json={
                "game_name": "secondrecent",
                "tag_line": "EUW",
                "display_name": "Second Recent",
            },
        )
        assert second_onboarding.status_code == 200

        recent_players_resp = await second_user_client.get("/api/market/players")
        recent_players = recent_players_resp.json()
        test_player = next(
            player
            for player in recent_players
            if player["display_name"] == "Test Player"
        )
        buy_resp = await second_user_client.post(
            "/api/orders",
            json={"player_id": test_player["id"], "side": "BUY", "quantity": 1},
        )
        assert buy_resp.status_code == 201

        recent_resp = await second_user_client.get("/api/orders/recent")

    assert recent_resp.status_code == 200
    data = recent_resp.json()
    assert len(data) >= 2
    assert {entry["user_name"] for entry in data[:2]} == {
        "Test Player",
        "Second Recent",
    }


async def test_sell_applies_short_hold_fee(auth_client, tradable_player, db_session):
    buy_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 10},
    )
    assert buy_resp.status_code == 201

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]

    lots_result = await db_session.execute(
        select(HoldingLot).where(
            HoldingLot.user_id == user_id,
            HoldingLot.player_id == tradable_player.id,
        )
    )
    lot = lots_result.scalar_one()
    lot.acquired_at = datetime.now(UTC)
    await db_session.commit()

    sell_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "SELL", "quantity": 10},
    )
    assert sell_resp.status_code == 201

    # Immediate sell gets max 2% reduction: 25.0 * 0.98
    assert sell_resp.json()["execution_price"] == pytest.approx(24.5)


async def test_sell_gets_long_hold_bonus(auth_client, tradable_player, db_session):
    buy_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 10},
    )
    assert buy_resp.status_code == 201

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]

    lots_result = await db_session.execute(
        select(HoldingLot).where(
            HoldingLot.user_id == user_id,
            HoldingLot.player_id == tradable_player.id,
        )
    )
    lot = lots_result.scalar_one()
    lot.acquired_at = datetime.now(UTC) - timedelta(hours=13)
    await db_session.commit()

    sell_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "SELL", "quantity": 10},
    )
    assert sell_resp.status_code == 201

    # >=12h hold gets +2% bonus: 25.0 * 1.02
    assert sell_resp.json()["execution_price"] == 25.5


async def test_buy_lot_links_to_order(auth_client, tradable_player, db_session):
    buy_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 2},
    )
    assert buy_resp.status_code == 201
    order_id = buy_resp.json()["id"]

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]

    lot_result = await db_session.execute(
        select(HoldingLot).where(
            HoldingLot.user_id == user_id,
            HoldingLot.player_id == tradable_player.id,
        )
    )
    lot = lot_result.scalar_one()
    assert lot.buy_order_id == order_id


async def test_revert_sets_order_status(auth_client, tradable_player, db_session):
    buy_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 1},
    )
    assert buy_resp.status_code == 201
    order_id = buy_resp.json()["id"]

    revert_resp = await auth_client.delete(f"/api/orders/{order_id}")
    assert revert_resp.status_code == 200

    order_result = await db_session.execute(select(Order).where(Order.id == order_id))
    order = order_result.scalar_one()
    assert order.status == OrderStatus.REVERTED
