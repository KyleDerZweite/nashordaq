async def test_place_buy_order(auth_client, seeded_player):
    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": seeded_player.id, "side": "BUY", "quantity": 2},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["side"] == "BUY"
    assert data["quantity"] == 2
    assert data["status"] == "PENDING"
    assert data["player_name"] == "Test Player"


async def test_place_buy_insufficient_balance(auth_client, seeded_player):
    # Price is 25.0, balance is 10000.0, so 401 shares = 10025.0 > 10000.0
    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": seeded_player.id, "side": "BUY", "quantity": 401},
    )
    assert resp.status_code == 400
    assert "Insufficient balance" in resp.json()["detail"]


async def test_place_sell_no_shares(auth_client, seeded_player):
    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": seeded_player.id, "side": "SELL", "quantity": 1},
    )
    assert resp.status_code == 400
    assert "Insufficient shares" in resp.json()["detail"]


async def test_place_order_invalid_player(auth_client):
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


async def test_cancel_order(auth_client, seeded_player):
    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": seeded_player.id, "side": "BUY", "quantity": 1},
    )
    order_id = resp.json()["id"]

    resp = await auth_client.delete(f"/api/orders/{order_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


async def test_cancel_nonexistent_order(auth_client):
    resp = await auth_client.delete("/api/orders/999")
    assert resp.status_code == 404


async def test_cancel_already_cancelled(auth_client, seeded_player):
    resp = await auth_client.post(
        "/api/orders",
        json={"player_id": seeded_player.id, "side": "BUY", "quantity": 1},
    )
    order_id = resp.json()["id"]
    await auth_client.delete(f"/api/orders/{order_id}")

    resp = await auth_client.delete(f"/api/orders/{order_id}")
    assert resp.status_code == 400


async def test_list_orders(auth_client, seeded_player):
    await auth_client.post(
        "/api/orders",
        json={"player_id": seeded_player.id, "side": "BUY", "quantity": 1},
    )
    await auth_client.post(
        "/api/orders",
        json={"player_id": seeded_player.id, "side": "BUY", "quantity": 2},
    )

    resp = await auth_client.get("/api/orders")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_list_orders_filter_status(auth_client, seeded_player):
    resp1 = await auth_client.post(
        "/api/orders",
        json={"player_id": seeded_player.id, "side": "BUY", "quantity": 1},
    )
    order_id = resp1.json()["id"]
    await auth_client.delete(f"/api/orders/{order_id}")

    await auth_client.post(
        "/api/orders",
        json={"player_id": seeded_player.id, "side": "BUY", "quantity": 2},
    )

    resp = await auth_client.get("/api/orders", params={"status": "PENDING"})
    assert len(resp.json()) == 1
    assert resp.json()[0]["quantity"] == 2
