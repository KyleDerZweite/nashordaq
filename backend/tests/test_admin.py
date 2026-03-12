from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.models import User


async def test_admin_overview_requires_admin(auth_client):
    resp = await auth_client.get("/api/admin/overview")

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


async def test_admin_can_view_overview_users_and_orders(
    auth_client, tradable_player, monkeypatch
):
    await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 1},
    )
    monkeypatch.setattr(settings, "admin_remote_users", "testuser")

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Remote-User": "seconduser"},
    ) as second_user_client:
        onboarding_resp = await second_user_client.post(
            "/api/user/onboarding",
            json={
                "game_name": "secondadmin",
                "tag_line": "EUW",
                "display_name": "Second Admin",
            },
        )
        assert onboarding_resp.status_code == 200

    overview_resp = await auth_client.get("/api/admin/overview")
    users_resp = await auth_client.get("/api/admin/users")
    orders_resp = await auth_client.get("/api/admin/orders")
    status_resp = await auth_client.get("/api/admin/system/status")

    assert overview_resp.status_code == 200
    assert overview_resp.json()["admin_users"] == 1
    assert overview_resp.json()["total_users"] >= 2
    assert overview_resp.json()["total_orders"] >= 1

    assert users_resp.status_code == 200
    users = users_resp.json()
    assert users[0]["role"] == "admin"
    assert {user["username"] for user in users} >= {"testuser", "seconduser"}

    assert orders_resp.status_code == 200
    assert len(orders_resp.json()) >= 1
    assert orders_resp.json()[0]["user_name"] == "Test Player"

    assert status_resp.status_code == 200
    assert status_resp.json()["service_status"] == "ok"


async def test_admin_can_view_user_portfolio(auth_client, tradable_player, monkeypatch):
    buy_resp = await auth_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 2},
    )
    assert buy_resp.status_code == 201

    me_resp = await auth_client.get("/api/user/me")
    assert me_resp.status_code == 200
    user_id = me_resp.json()["id"]

    monkeypatch.setattr(settings, "admin_remote_users", "testuser")

    resp = await auth_client.get(f"/api/admin/users/{user_id}/portfolio")

    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "admin"
    assert data["portfolio"]["holdings"][0]["player_name"] == "Tradable Player"
    assert data["portfolio"]["holdings"][0]["quantity"] == 2


async def test_admin_can_restore_a_spent_rescue_use(
    auth_client,
    db_session,
    monkeypatch,
):
    await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "bank-admin",
            "tag_line": "EUW",
            "display_name": "Bank Admin",
        },
    )

    me_resp = await auth_client.get("/api/user/me")
    assert me_resp.status_code == 200
    user_id = me_resp.json()["id"]

    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 0.0
    await db_session.commit()

    borrow_resp = await auth_client.post("/api/bank/borrow", json={"amount": 750})
    assert borrow_resp.status_code == 200

    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 900.0
    await db_session.commit()

    repay_resp = await auth_client.post("/api/bank/repay", json={"amount": 765})
    assert repay_resp.status_code == 200
    assert repay_resp.json()["rescue_loan_uses_remaining"] == 0

    monkeypatch.setattr(settings, "admin_remote_users", "testuser")

    unlock_resp = await auth_client.post(f"/api/admin/users/{user_id}/rescue-unlock")

    assert unlock_resp.status_code == 200
    data = unlock_resp.json()
    assert data["rescue_loan_uses_remaining"] == 1
    assert data["rescue_loan_available"] is True
    assert data["rescue_loan_block_reason"] is None
