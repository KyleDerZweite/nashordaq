import re
from datetime import datetime

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.models import Base, User


@pytest.fixture(autouse=True)
def stub_initial_player_refresh():
    """Exercise real onboarding instead of the inherited no-op fixture."""
    return None


@pytest.fixture
def accepted_riot(httpx_mock):
    httpx_mock.add_response(
        url=re.compile(
            f"{settings.riot_api_base_url}/riot/account/v1/accounts/by-riot-id/.*"
        ),
        json={"puuid": "operator-riot"},
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=f"{settings.riot_api_region_url}/lol/league/v4/entries/by-puuid/operator-riot",
        json=[
            {
                "queueType": "RANKED_SOLO_5x5",
                "tier": "GOLD",
                "rank": "IV",
                "leaguePoints": 20,
                "wins": 10,
                "losses": 10,
            }
        ],
        is_reusable=True,
    )


@pytest.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/activity.db")

    @event.listens_for(engine.sync_engine, "connect")
    def sqlite_constraints(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=15000")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


async def test_admin_participates_under_normal_onboarding_and_economy_rules(
    admin_client, tradable_player, db_session, accepted_riot
):
    before = await admin_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 2},
    )
    assert before.status_code == 403
    assert before.json()["detail"] == "Complete onboarding first"
    onboarding = await admin_client.post(
        "/api/user/onboarding", json={"game_name": "OperatorRiot", "tag_line": "EUW"}
    )
    assert onboarding.status_code == 200
    own_player = onboarding.json()["linked_player_id"]
    own_buy = await admin_client.post(
        "/api/orders", json={"player_id": own_player, "side": "BUY", "quantity": 1}
    )
    assert own_buy.status_code == 400
    buy = await admin_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "BUY", "quantity": 2},
    )
    assert buy.status_code == 201
    assert buy.json()["execution_price"] == 25.025
    orders = await admin_client.get("/api/orders")
    assert [order["id"] for order in orders.json()] == [buy.json()["id"]]
    portfolio = await admin_client.get("/api/portfolio")
    assert portfolio.status_code == 200
    assert portfolio.json()["balance"] == 949.95
    sell = await admin_client.post(
        "/api/orders",
        json={"player_id": tradable_player.id, "side": "SELL", "quantity": 2},
    )
    assert sell.status_code == 400
    revert = await admin_client.delete(f"/api/orders/{buy.json()['id']}")
    assert revert.status_code == 200
    assert (await admin_client.get("/api/portfolio")).json()["balance"] == 1000
    assert (await admin_client.get("/api/bank")).status_code == 200
    administrator = await db_session.get(User, onboarding.json()["id"])
    administrator.balance = 0
    await db_session.commit()
    borrowed = await admin_client.post("/api/bank/borrow", json={"amount": 750})
    assert borrowed.status_code == 200
    assert borrowed.json()["cash_balance"] == 750
    assert borrowed.json()["debt_outstanding"] == 765
    repaid = await admin_client.post("/api/bank/repay", json={"amount": 15})
    assert repaid.status_code == 200
    assert repaid.json()["debt_accrued_interest"] == 0
    assert repaid.json()["debt_principal"] == 750
    assert (await admin_client.get("/api/activity")).json() == []


async def test_rescue_restoration_records_member_visible_concrete_change(
    auth_client, admin_client, db_session
):
    member = (await auth_client.get("/api/user/me")).json()
    operator = (await admin_client.get("/api/user/me")).json()
    user = await db_session.get(User, member["id"])
    user.rescue_loan_uses_remaining = 0
    await db_session.commit()
    restored = await admin_client.post(f"/api/admin/users/{user.id}/rescue-unlock")
    assert restored.status_code == 200
    activity = await auth_client.get("/api/activity")
    assert activity.status_code == 200
    event = activity.json()[0]
    assert event["actor"]["user_id"] == operator["id"]
    assert event["actor"]["username"] == "operator"
    assert event["affected"]["user_id"] == member["id"]
    assert event["affected"]["username"] == "testuser"
    assert event["kind"] == "rescue_access_restored"
    assert event["previous_uses"] == 0
    assert event["new_uses"] == 1
    assert datetime.fromisoformat(event["created_at"]).tzinfo is not None
    assert set(event) == {
        "id",
        "actor",
        "affected",
        "kind",
        "previous_uses",
        "new_uses",
        "created_at",
    }


async def test_activity_permissions_and_failed_interventions_leave_no_events(
    auth_client, admin_client, client
):
    member_id = (await auth_client.get("/api/user/me")).json()["id"]
    assert (await client.get("/api/activity")).status_code == 401
    denied = await auth_client.post(f"/api/admin/users/{member_id}/rescue-unlock")
    assert denied.status_code == 403
    missing = await admin_client.post("/api/admin/users/999999/rescue-unlock")
    assert missing.status_code == 404
    unchanged = await admin_client.post(f"/api/admin/users/{member_id}/rescue-unlock")
    assert unchanged.status_code == 409
    await admin_client.get("/api/admin/overview")
    await admin_client.get("/api/admin/users")
    await admin_client.get(f"/api/admin/users/{member_id}/portfolio")
    await admin_client.post("/api/auth/invites")
    assert (await auth_client.get("/api/activity")).json() == []


async def test_activity_and_rescue_access_roll_back_on_sqlite_record_failure(
    auth_client, admin_client, db_session, db_engine
):
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text

    from app.main import app

    member_id = (await auth_client.get("/api/user/me")).json()["id"]
    member = await db_session.get(User, member_id)
    member.rescue_loan_uses_remaining = 0
    await db_session.commit()
    async with db_engine.begin() as connection:
        await connection.execute(
            text(
                "CREATE TRIGGER reject_intervention "
                "BEFORE INSERT ON game_interventions "
                "BEGIN SELECT RAISE(ABORT, 'test record failure'); END"
            )
        )
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        cookies=admin_client.cookies,
        headers={"X-Nashordaq-CSRF": "1"},
    ) as failure_client:
        failed = await failure_client.post(
            f"/api/admin/users/{member_id}/rescue-unlock"
        )
    assert failed.status_code == 500
    assert (await auth_client.get("/api/activity")).json() == []
    portfolio = await admin_client.get(f"/api/admin/users/{member_id}/portfolio")
    assert portfolio.json()["rescue_loan_uses_remaining"] == 0
    async with db_engine.begin() as connection:
        await connection.execute(text("DROP TRIGGER reject_intervention"))
    retried = await admin_client.post(f"/api/admin/users/{member_id}/rescue-unlock")
    assert retried.status_code == 200
    assert len((await auth_client.get("/api/activity")).json()) == 1
    repeated = await admin_client.post(f"/api/admin/users/{member_id}/rescue-unlock")
    assert repeated.status_code == 409
    assert len((await auth_client.get("/api/activity")).json()) == 1


async def test_simultaneous_restoration_creates_exactly_one_activity_event(
    auth_client, admin_client, db_session
):
    import asyncio

    member_id = (await auth_client.get("/api/user/me")).json()["id"]
    member = await db_session.get(User, member_id)
    member.rescue_loan_uses_remaining = 0
    await db_session.commit()
    results = await asyncio.gather(
        admin_client.post(f"/api/admin/users/{member_id}/rescue-unlock"),
        admin_client.post(f"/api/admin/users/{member_id}/rescue-unlock"),
    )
    assert sorted(response.status_code for response in results) == [200, 409]
    events = (await auth_client.get("/api/activity")).json()
    assert len(events) == 1
    assert events[0]["affected"]["user_id"] == member_id
    assert (await admin_client.get(f"/api/admin/users/{member_id}/portfolio")).json()[
        "rescue_loan_uses_remaining"
    ] == 1


async def test_admin_user_role_and_onboarding_allowed(admin_client, accepted_riot):

    me_resp = await admin_client.get("/api/user/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "admin"

    onboarding_resp = await admin_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "viewer",
            "tag_line": "EUW",
        },
    )
    assert onboarding_resp.status_code == 200
    assert onboarding_resp.json()["onboarding_complete"] is True
    assert onboarding_resp.json()["role"] == "admin"


async def test_admin_user_profile_update_requires_onboarding_then_succeeds(
    admin_client,
    accepted_riot,
):

    update_resp = await admin_client.put(
        "/api/user/profile",
        json={
            "game_name": "viewer",
            "tag_line": "EUW",
        },
    )
    assert update_resp.status_code == 403
    assert update_resp.json()["detail"] == "Complete onboarding first"
    assert (
        await admin_client.post(
            "/api/user/onboarding", json={"game_name": "viewer", "tag_line": "EUW"}
        )
    ).status_code == 200
    updated = await admin_client.put(
        "/api/user/profile", json={"game_name": "renamed", "tag_line": "EUW"}
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "admin"


async def test_demo_visitor_cannot_read_existing_normal_game_interventions(
    auth_client, admin_client, db_session, client, monkeypatch
):
    member_id = (await auth_client.get("/api/user/me")).json()["id"]
    member = await db_session.get(User, member_id)
    member.rescue_loan_uses_remaining = 0
    await db_session.commit()
    assert (
        await admin_client.post(f"/api/admin/users/{member_id}/rescue-unlock")
    ).status_code == 200
    assert len((await auth_client.get("/api/activity")).json()) == 1
    monkeypatch.setattr(settings, "demo_mode_enabled", True)
    login = await client.post(
        "/api/auth/login",
        json={"username": "demo", "password": "demo"},
        headers={"X-Nashordaq-CSRF": "1"},
    )
    assert login.status_code == 200
    assert (await client.get("/api/activity")).json() == []
