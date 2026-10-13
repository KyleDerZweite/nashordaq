from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import auth, database, main, scheduler
from app.config import settings
from app.database import get_session
from app.main import app


async def test_demo_requires_explicit_login_and_rejects_normal_sessions(
    admin_client, client, monkeypatch
):
    monkeypatch.setattr(settings, "demo_mode_enabled", True)
    for headers in [
        {},
        {"Remote-User": "administrator", "Remote-Role": "admin"},
        {"Cookie": "nashordaq_demo_session=old-demo-token"},
    ]:
        response = await client.get("/api/user/me", headers=headers)
        assert response.status_code == 401
    assert (await admin_client.get("/api/market/players")).status_code == 401
    for username, password in [
        ("demo", "wrong"),
        ("operator", "fixture password for tests"),
    ]:
        response = await admin_client.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
        assert response.status_code == 401
    response = await admin_client.post(
        "/api/auth/login", json={"username": "demo", "password": "demo"}
    )
    assert response.status_code == 200
    me = (await admin_client.get("/api/user/me")).json()
    assert me["is_demo"] is True
    assert me["role"] == "player"
    assert me["balance"] == 1000
    assert me["onboarding_complete"] is True
    assert (await client.get("/api/auth/status")).json() == {
        "setup_required": False,
        "demo_mode_enabled": True,
    }


async def test_demo_market_tick_updates_shared_prices_and_creates_history(
    demo_instance,
):
    async with demo_instance() as client:
        await demo_login(client)
        before = (await client.get("/api/market/players")).json()
        player_id = before[0]["id"]
        history_before = (await client.get(f"/api/market/players/{player_id}")).json()
        await scheduler.demo_market_tick_job()
        after = (await client.get("/api/market/players")).json()
        assert any(
            a["current_price"] != b["current_price"]
            for a, b in zip(before, after, strict=True)
        )
        history_after = (await client.get(f"/api/market/players/{player_id}")).json()
        assert (
            len(history_after["price_history"])
            == len(history_before["price_history"]) + 1
        )
        assert history_after["price_history"][0]["price"] == after[0]["current_price"]


@pytest.fixture
async def demo_instance(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "demo_mode_enabled", True)
    monkeypatch.setattr(settings, "riot_api_key", "")
    instance_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/demo.db")

    @event.listens_for(instance_engine.sync_engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    factory = async_sessionmaker(instance_engine, expire_on_commit=False)
    monkeypatch.setattr(database, "engine", instance_engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(main, "SessionLocal", factory)
    monkeypatch.setattr(scheduler, "SessionLocal", factory)
    await main.initialize_instance()

    async def sessions():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = sessions

    @asynccontextmanager
    async def visitor():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Nashordaq-CSRF": "1", "Origin": "http://test"},
        ) as client:
            yield client

    yield visitor
    app.dependency_overrides.clear()
    await instance_engine.dispose()


async def demo_login(client):
    response = await client.post(
        "/api/auth/login", json={"username": "demo", "password": "demo"}
    )
    assert response.status_code == 200, response.text
    return (await client.get("/api/user/me")).json()


async def test_demo_visitors_trade_in_shared_market_with_private_personal_state(
    demo_instance,
):
    async with demo_instance() as first, demo_instance() as second:
        assert (await first.get("/api/market/players")).status_code == 401
        a = await demo_login(first)
        b = await demo_login(second)
        assert a["id"] != b["id"]
        market = (await first.get("/api/market/players")).json()
        assert len(market) > 0
        status = (await first.get("/api/system/status")).json()
        assert status["riot_status"] == "demo"
        assert status["demo_mode_enabled"] is True
        assert (await second.get("/api/market/players")).json() == market
        player = market[0]
        order = await first.post(
            "/api/orders",
            json={"player_id": player["id"], "side": "BUY", "quantity": 1},
        )
        assert order.status_code == 201, order.text
        order_id = order.json()["id"]
        assert (await second.get(f"/api/orders/{order_id}")).status_code == 404
        assert (await second.delete(f"/api/orders/{order_id}")).status_code in {
            403,
            404,
        }
        assert (await second.get("/api/orders")).json() == []
        assert (await second.get("/api/orders/recent")).json() == []
        assert (await second.get("/api/portfolio")).json()["holdings"] == []
        assert (await first.get("/api/portfolio")).json()["holdings"][0][
            "quantity"
        ] == 1
        assert (await second.get("/api/user/me")).json()["balance"] == 1000
        assert (await first.get("/api/user/me")).json()["balance"] < 1000
        assert (await first.get("/api/auth/session")).status_code == 200
        assert (await first.get("/api/user/me")).json()["id"] == a["id"]
        assert (
            await second.get(f"/api/leaderboard/{a['id']}/portfolio")
        ).status_code == 404
        assert (await first.get("/api/market/players")).json() == market


async def test_polling_expires_at_thirty_minutes_but_explicit_activity_renews(
    demo_instance, monkeypatch
):
    now = datetime(2026, 10, 14, tzinfo=UTC)
    monkeypatch.setattr(auth, "utc_now", lambda: now)
    async with demo_instance() as idle, demo_instance() as active:
        await demo_login(idle)
        await demo_login(active)
        now += timedelta(minutes=29)
        assert (await idle.get("/api/auth/session")).status_code == 200
        assert (await idle.get("/api/market/players")).status_code == 200
        assert (await idle.get("/api/orders")).status_code == 200
        assert (await idle.get("/api/poro/stream")).status_code == 200
        assert (
            await idle.post(
                "/api/auth/activity", headers={"Origin": "https://evil.example"}
            )
        ).status_code == 403
        assert (await active.post("/api/auth/activity")).status_code == 200
        now += timedelta(minutes=1)
        assert (await idle.get("/api/user/me")).status_code == 401
        assert (await idle.post("/api/auth/activity")).status_code == 401
        await scheduler.demo_cleanup_job()
        await scheduler.demo_cleanup_job()
        from app.models import User

        async with database.SessionLocal() as session:
            assert len((await session.scalars(select(User))).all()) == 1
        assert (await active.get("/api/user/me")).status_code == 200
        now += timedelta(minutes=29)
        assert (await active.get("/api/user/me")).status_code == 401


async def test_logout_deletes_personal_rows_and_cleanup_preserves_shared_market(
    demo_instance, monkeypatch
):
    from sqlalchemy import func

    from app.models import AuthSession, Holding, HoldingLot, Order, Transaction, User

    now = datetime(2026, 10, 14, tzinfo=UTC)
    monkeypatch.setattr(auth, "utc_now", lambda: now)
    async with demo_instance() as first, demo_instance() as second:
        await demo_login(first)
        await demo_login(second)
        market = (await first.get("/api/market/players")).json()
        response = await first.post(
            "/api/orders",
            json={"player_id": market[0]["id"], "side": "BUY", "quantity": 1},
        )
        assert response.status_code == 201
        old_cookie = first.cookies.get("nashordaq_session")
        assert (await first.post("/api/auth/logout")).status_code == 200
        assert (
            await first.get(
                "/api/user/me", headers={"Cookie": f"nashordaq_session={old_cookie}"}
            )
        ).status_code == 401
        # SQLite is the approved seam for physical cleanup.
        async with database.SessionLocal() as session:
            for model in [Holding, HoldingLot, Order, Transaction]:
                assert (
                    await session.scalar(select(func.count()).select_from(model)) == 0
                )
            assert await session.scalar(select(func.count()).select_from(User)) == 1
            assert (
                await session.scalar(select(func.count()).select_from(AuthSession)) == 1
            )
            regular = User(username="regular", display_name="regular", is_demo=False)
            session.add(regular)
            await session.flush()
            session.add(
                AuthSession(
                    token_hash="0" * 64,
                    user_id=regular.id,
                    expires_at=now + timedelta(days=7),
                )
            )
            await session.commit()
        now += timedelta(minutes=30)
        await scheduler.demo_cleanup_job()
        await scheduler.demo_cleanup_job()
        async with database.SessionLocal() as session:
            assert (await session.scalars(select(User.username))).all() == ["regular"]
            assert (
                await session.scalar(select(func.count()).select_from(AuthSession)) == 1
            )
        await demo_login(second)
        assert (await second.get("/api/market/players")).json() == market


async def test_demo_permissions_features_and_obsolete_nickname(
    demo_instance, monkeypatch
):
    monkeypatch.setattr(settings, "gamba_enabled", True)
    monkeypatch.setattr(settings, "poro_enabled", True)
    async with demo_instance() as client:
        await demo_login(client)
        assert (await client.get("/api/admin/overview")).status_code == 403
        assert (await client.get("/api/auth/invites")).status_code == 403
        assert (await client.post("/api/auth/invites")).status_code == 403
        assert (await client.delete("/api/auth/invites/1")).status_code == 403
        assert (
            await client.post(
                "/api/auth/register",
                json={
                    "token": "x",
                    "username": "member",
                    "password": "secure password",
                },
            )
        ).status_code == 403
        assert (
            await client.post(
                "/api/auth/setup",
                json={"token": "x", "username": "admin", "password": "secure password"},
            )
        ).status_code == 403
        assert (
            await client.post(
                "/api/user/onboarding", json={"game_name": "x", "tag_line": "EUW"}
            )
        ).status_code == 403
        assert (await client.get("/api/bank")).status_code == 403
        assert (
            await client.post("/api/gamba", json={"cash_amount": 50})
        ).status_code == 403
        assert (await client.get("/api/poro")).json()["enabled"] is False
        assert (
            await client.post("/api/user/demo-nickname", json={"display_name": "Other"})
        ).status_code == 404
        cookie = client.cookies.get("nashordaq_session")
        monkeypatch.setattr(settings, "demo_mode_enabled", False)
        assert (
            await client.get(
                "/api/user/me", headers={"Cookie": f"nashordaq_session={cookie}"}
            )
        ).status_code == 401
        assert (
            await client.post(
                "/api/auth/login", json={"username": "demo", "password": "demo"}
            )
        ).status_code == 401


async def test_demo_cannot_change_password_or_use_account_recovery(demo_instance):
    async with demo_instance() as client:
        await demo_login(client)
        user_id = (await client.get("/api/user/me")).json()["id"]
        for method, path, body in [
            (
                "POST",
                "/api/auth/password",
                {"current_password": "demo", "new_password": "a private new password"},
            ),
            (
                "POST",
                "/api/auth/reset",
                {"token": "unavailable", "new_password": "a private new password"},
            ),
            ("GET", "/api/auth/resets", None),
            ("POST", "/api/auth/resets", {"user_id": user_id}),
            ("DELETE", "/api/auth/resets/1", None),
        ]:
            assert (await client.request(method, path, json=body)).status_code == 403
            assert (await client.get("/api/auth/session")).status_code == 200
        assert (await client.get("/api/user/me")).json()["id"] == user_id


async def test_portfolio_and_recent_orders_enforce_mode_and_demo_owner_boundaries(
    demo_instance, monkeypatch
):
    from app.models import Holding, TrackedPlayer, User
    from tests.conftest import TEST_PASSWORD, TEST_PASSWORD_HASH

    async with database.SessionLocal() as session:
        players = (await session.scalars(select(TrackedPlayer))).all()
        regular = User(
            username="preserved-member",
            display_name="preserved-member",
            password_hash=TEST_PASSWORD_HASH,
            linked_player_id=players[0].id,
        )
        viewer = User(
            username="normal-viewer",
            display_name="normal-viewer",
            password_hash=TEST_PASSWORD_HASH,
            linked_player_id=players[4].id,
        )
        session.add_all([regular, viewer])
        await session.flush()
        regular_id = regular.id
        session.add(Holding(user_id=regular.id, player_id=players[1].id, quantity=3))
        await session.commit()

    async with demo_instance() as demo, demo_instance() as normal:
        me = await demo_login(demo)
        response = await demo.get(f"/api/leaderboard/{regular_id}/portfolio")
        assert response.status_code == 404
        assert (await demo.get("/api/leaderboard")).json() == []
        # Exercise the authorization rule independently of today's unlinked demo model.
        async with database.SessionLocal() as session:
            demo_user = await session.get(User, me["id"])
            demo_user.linked_player_id = players[2].id
            session.add(
                Holding(user_id=demo_user.id, player_id=players[1].id, quantity=1)
            )
            await session.commit()
        own = await demo.get(f"/api/leaderboard/{me['id']}/portfolio")
        assert own.status_code == 200
        assert own.json()["holdings"][0]["quantity"] == 1
        assert [
            entry["user_id"] for entry in (await demo.get("/api/leaderboard")).json()
        ] == [me["id"]]
        demo_order = await demo.post(
            "/api/orders",
            json={"player_id": players[3].id, "side": "BUY", "quantity": 1},
        )
        assert demo_order.status_code == 201
        demo_order_id = demo_order.json()["id"]
        assert (await demo.get("/api/orders/recent")).json()[0]["id"] == demo_order_id
        assert (await demo.get(f"/api/orders/{demo_order_id}")).status_code == 200

        monkeypatch.setattr(settings, "demo_mode_enabled", False)
        response = await normal.post(
            "/api/auth/login",
            json={"username": "normal-viewer", "password": TEST_PASSWORD},
        )
        assert response.status_code == 200
        preserved = await normal.get(f"/api/leaderboard/{regular_id}/portfolio")
        assert preserved.status_code == 200
        assert preserved.json()["holdings"][0]["quantity"] == 3
        normal_id = (await normal.get("/api/user/me")).json()["id"]
        normal_leaderboard = (await normal.get("/api/leaderboard")).json()
        assert {entry["user_id"] for entry in normal_leaderboard} == {
            regular_id,
            normal_id,
        }
        normal_order = await normal.post(
            "/api/orders",
            json={"player_id": players[5].id, "side": "BUY", "quantity": 1},
        )
        assert normal_order.status_code == 201
        recent_ids = [
            order["id"] for order in (await normal.get("/api/orders/recent")).json()
        ]
        assert normal_order.json()["id"] in recent_ids
        assert demo_order_id not in recent_ids
        assert (await normal.get(f"/api/orders/{demo_order_id}")).status_code == 404
        assert (
            await normal.get(f"/api/leaderboard/{me['id']}/portfolio")
        ).status_code == 404


async def test_identity_directory_preserves_mode_and_demo_owner_privacy(
    demo_instance, monkeypatch
):
    from app.models import TrackedPlayer, User
    from tests.conftest import TEST_PASSWORD, TEST_PASSWORD_HASH

    async with database.SessionLocal() as session:
        player = TrackedPlayer(
            game_name="PreservedRiotSecret",
            tag_line="HIDDENTAG",
            display_name="PreservedLabel",
        )
        session.add(player)
        await session.flush()
        session.add(
            User(
                username="PreservedUsername",
                password_hash=TEST_PASSWORD_HASH,
                linked_player_id=player.id,
            )
        )
        await session.commit()
    async with demo_instance() as first, demo_instance() as second:
        await demo_login(first)
        await demo_login(second)
        first_id = (await first.get("/api/user/me")).json()["id"]
        second_id = (await second.get("/api/user/me")).json()["id"]
        directory = await first.get("/api/identities")
        assert directory.status_code == 200
        assert {member["user_id"] for member in directory.json()["users"]} == {first_id}
        assert "PreservedUsername" not in directory.text
        assert "PreservedRiotSecret" not in directory.text
        assert "HIDDENTAG" not in directory.text
        assert second_id != first_id
        first_alias = directory.json()["users"][0]["streamer_alias"]
        second_alias = (await second.get("/api/identities")).json()["users"][0][
            "streamer_alias"
        ]
        assert first_alias != second_alias
        assert (await first.get("/api/identities")).json()["users"][0][
            "streamer_alias"
        ] == first_alias
        monkeypatch.setattr(settings, "demo_mode_enabled", False)
        assert (
            await first.post(
                "/api/auth/login",
                json={"username": "PreservedUsername", "password": TEST_PASSWORD},
            )
        ).status_code == 200
        normal = (await first.get("/api/identities")).json()
        assert [member["username"] for member in normal["users"]] == [
            "PreservedUsername"
        ]
        assert normal["users"][0]["game_name"] == "PreservedRiotSecret"
