import logging
import re

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import database, main
from app.config import Settings
from app.database import get_session
from app.main import app


def test_fresh_configuration_needs_no_riot_key():
    config = Settings(_env_file=None, riot_api_key="", demo_mode_enabled=False)
    assert config.riot_api_key == ""


@pytest.fixture
async def local_instance(tmp_path, monkeypatch, caplog):
    from app.config import settings

    monkeypatch.setattr(settings, "riot_api_key", "")
    instance_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/instance.db")
    factory = async_sessionmaker(instance_engine, expire_on_commit=False)
    monkeypatch.setattr(database, "engine", instance_engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(main, "SessionLocal", factory)
    caplog.set_level(logging.INFO)
    await main.initialize_instance()

    startup_logs = "\n".join(
        record.getMessage() for record in caplog.get_records("setup")
    )

    async def sessions():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Nashordaq-CSRF": "1", "Origin": "http://test"},
    ) as client:
        yield client, startup_logs, factory
    app.dependency_overrides.clear()
    await instance_engine.dispose()


async def test_operator_setup_link_creates_admin_and_session(local_instance):
    client, logs, _ = local_instance
    link = re.search(r"/setup\?token=([A-Za-z0-9_-]+)", logs)
    assert link, "Fresh startup must deliver the setup link in the operator log"
    response = await client.post(
        "/api/auth/setup",
        json={
            "token": link[1],
            "username": "operator",
            "password": "a secure password",
        },
    )
    assert response.status_code == 201
    me = await client.get("/api/user/me")
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    assert me.json()["display_name"] == "operator"
    assert "password" not in response.text
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert "Max-Age=604800" in cookie


async def register_operator(client, logs):
    token = re.search(r"/setup\?token=([A-Za-z0-9_-]+)", logs)[1]
    response = await client.post(
        "/api/auth/setup",
        json={
            "token": token,
            "username": "operator",
            "password": "a secure password",
        },
    )
    assert response.status_code == 201
    return token


async def test_logout_revokes_cookie_and_credentials_issue_a_new_session(
    local_instance,
):
    client, logs, _ = local_instance
    await register_operator(client, logs)
    old_cookie = client.cookies.get("nashordaq_session")
    assert (await client.post("/api/auth/logout")).status_code == 200
    assert (
        await client.get(
            "/api/user/me", headers={"Cookie": f"nashordaq_session={old_cookie}"}
        )
    ).status_code == 401
    for username, password in [("operator", "wrong"), ("missing", "a secure password")]:
        assert (
            await client.post(
                "/api/auth/login", json={"username": username, "password": password}
            )
        ).status_code == 401
    assert (await client.get("/api/user/me")).status_code == 401
    assert (
        await client.post(
            "/api/auth/login",
            json={"username": "operator", "password": "a secure password"},
        )
    ).status_code == 200
    assert (await client.get("/api/auth/session")).json()["authenticated"] is True
    assert (await client.get("/api/user/me")).json()["role"] == "admin"


async def test_game_routes_ignore_forged_proxy_identity(local_instance):
    client, _, _ = local_instance
    routes = [
        "/api/market/players",
        "/api/market/players/1",
        "/api/leaderboard",
        "/api/leaderboard/1/portfolio",
        "/api/simulate/defaults",
        "/api/simulate/players/1/matches",
        "/api/system/status",
        "/api/user/me",
        "/api/orders",
        "/api/orders/recent",
        "/api/portfolio",
        "/api/admin/overview",
    ]
    for route in routes:
        response = await client.get(
            route,
            headers={
                "Remote-User": "admin",
                "Remote-Email": "admin@test",
                "Remote-Role": "admin",
            },
        )
        assert response.status_code == 401, (route, response.text)
    assert (await client.get("/api/auth/status")).json() == {
        "setup_required": True,
        "demo_mode_enabled": False,
    }


async def test_browser_changes_reject_cross_origin_and_simple_requests(local_instance):
    client, logs, _ = local_instance
    await register_operator(client, logs)
    for endpoint, payload in [
        ("/api/auth/login", {"username": "operator", "password": "a secure password"}),
        (
            "/api/auth/setup",
            {
                "token": "invalid",
                "username": "intruder",
                "password": "a secure password",
            },
        ),
        ("/api/auth/logout", {}),
        ("/api/user/onboarding", {"game_name": "x", "tag_line": "EUW"}),
        ("/api/simulate", {}),
    ]:
        response = await client.post(
            endpoint, json=payload, headers={"Origin": "https://evil.example"}
        )
        assert response.status_code == 403, endpoint
    assert (
        await client.post("/api/auth/logout", headers={"Origin": "null"})
    ).status_code == 403
    assert (
        await client.post("/api/auth/logout", headers={"Sec-Fetch-Site": "cross-site"})
    ).status_code == 403
    assert (
        await client.post("/api/auth/logout", headers={"X-Nashordaq-CSRF": ""})
    ).status_code == 403
    assert (await client.get("/api/user/me")).status_code == 200
    client.headers.pop("Origin")
    assert (await client.post("/api/auth/logout")).status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
        {"X-Nashordaq-CSRF": ""},
    ],
)
async def test_csrf_rejections_prevent_caching_and_referrer_disclosure(client, headers):
    response = await client.post(
        "/api/auth/login",
        json={"username": "member", "password": "a secure password"},
        headers={"X-Nashordaq-CSRF": "1", **headers},
    )
    assert response.status_code == 403
    assert response.headers.get("Cache-Control") == "no-store"
    assert response.headers.get("Referrer-Policy") == "no-referrer"


async def test_expiry_ends_access_after_seven_days(local_instance, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from app import auth

    client, logs, _ = local_instance
    now = datetime(2026, 10, 13, tzinfo=UTC)
    monkeypatch.setattr(auth, "utc_now", lambda: now)
    await register_operator(client, logs)
    now += timedelta(days=7, seconds=-1)
    assert (await client.get("/api/user/me")).status_code == 200
    now += timedelta(seconds=1)
    assert (await client.get("/api/user/me")).status_code == 401


async def test_concurrent_setup_replay_and_restart_keep_one_admin(
    local_instance, caplog
):
    import asyncio

    client, logs, _ = local_instance
    token = re.search(r"/setup\?token=([A-Za-z0-9_-]+)", logs)[1]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Nashordaq-CSRF": "1"},
    ) as other:
        responses = await asyncio.gather(
            *[
                browser.post(
                    "/api/auth/setup",
                    json={
                        "token": token,
                        "username": name,
                        "password": "a secure password",
                    },
                )
                for browser, name in [(client, "first"), (other, "second")]
            ]
        )
        assert sorted(response.status_code for response in responses) == [201, 400]
        winner = client if responses[0].status_code == 201 else other
        assert len((await winner.get("/api/admin/users")).json()) == 1
        caplog.clear()
        await database.engine.dispose()
        await main.initialize_instance()
        assert "Initial administrator setup" not in caplog.text
        assert (await winner.get("/api/user/me")).status_code == 200
        assert (await winner.get("/api/auth/status")).json()["setup_required"] is False
        assert (
            await winner.post(
                "/api/auth/setup",
                json={
                    "token": token,
                    "username": "replay",
                    "password": "a secure password",
                },
            )
        ).status_code == 400


async def test_legacy_database_rejected_without_any_mutation(tmp_path, monkeypatch):
    import sqlite3

    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as legacy:
        legacy.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
        legacy.execute("INSERT INTO users VALUES (1, 'proxy-user')")
    before = db_path.read_bytes()
    legacy_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setattr(database, "engine", legacy_engine)
    with pytest.raises(RuntimeError, match="Legacy proxy database.*separate empty"):
        await database.init_db()
    await legacy_engine.dispose()
    assert db_path.read_bytes() == before
    assert not (tmp_path / "legacy.db-wal").exists()


async def test_password_validation_never_echoes_submitted_secret(local_instance):
    client, logs, _ = local_instance
    token = re.search(r"/setup\?token=([A-Za-z0-9_-]+)", logs)[1]
    response = await client.post(
        "/api/auth/setup",
        json={"token": token, "username": "operator", "password": "private"},
    )
    assert response.status_code == 422
    assert "private" not in response.text
    assert token not in response.text


async def test_open_game_stream_stops_when_its_session_expires(
    auth_client, seeded_player, monkeypatch
):
    import asyncio
    from datetime import UTC, datetime, timedelta

    from app import auth

    now = datetime.now(UTC)
    reads = 0

    def progressing_clock():
        nonlocal reads
        reads += 1
        return now if reads <= 2 else now + timedelta(days=7)

    monkeypatch.setattr(auth, "utc_now", progressing_clock)
    response = await asyncio.wait_for(auth_client.get("/api/poro/stream"), timeout=20)
    assert response.status_code == 200
    assert response.text.count("data:") == 1


async def test_cookie_security_follows_operator_https_config(
    local_instance, monkeypatch
):
    from app.config import settings

    client, logs, _ = local_instance
    monkeypatch.setattr(settings, "public_url", "https://market.example")
    response = await client.post(
        "/api/auth/setup",
        json={
            "token": re.search(r"/setup\?token=([A-Za-z0-9_-]+)", logs)[1],
            "username": "operator",
            "password": "a secure password",
        },
        headers={"Origin": "https://market.example", "X-Forwarded-Proto": "http"},
    )
    assert response.status_code == 201
    assert "Secure" in response.headers["set-cookie"]
    monkeypatch.setattr(settings, "public_url", "http://test")
    response = await client.post(
        "/api/auth/login",
        json={"username": "operator", "password": "a secure password"},
        headers={"X-Forwarded-Proto": "https"},
    )
    assert response.status_code == 200
    assert "Secure" not in response.headers["set-cookie"]


async def test_open_game_stream_closes_after_logout(auth_client, seeded_player):
    import asyncio

    first_event = asyncio.Event()

    async def observe_http_events(scope, receive, send):
        async def observe_send(message):
            if message["type"] == "http.response.body" and b"data:" in message.get(
                "body", b""
            ):
                first_event.set()
            await send(message)

        await app(scope, receive, observe_send)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=observe_http_events),
        base_url="http://test",
        cookies={"nashordaq_session": auth_client.cookies.get("nashordaq_session")},
    ) as streaming_browser:
        stream = asyncio.create_task(streaming_browser.get("/api/poro/stream"))
        try:
            await asyncio.wait_for(first_event.wait(), timeout=2)
            assert (await auth_client.post("/api/auth/logout")).status_code == 200
            response = await asyncio.wait_for(stream, timeout=20)
            assert response.status_code == 200
            assert response.text.count("data:") == 1
        finally:
            stream.cancel()
            await asyncio.gather(stream, return_exceptions=True)


async def test_admin_creates_invitation_and_member_joins_without_riot(local_instance):
    client, logs, _ = local_instance
    await register_operator(client, logs)
    response = await client.post("/api/auth/invites")
    assert response.status_code == 201
    invitation = response.json()
    assert invitation["status"] == "active"
    token = re.search(r"/invite\?token=([A-Za-z0-9_-]+)", invitation["url"])[1]
    lifecycle = (await client.get("/api/auth/invites")).json()
    assert lifecycle[0]["id"] == invitation["id"]
    assert token not in str(lifecycle)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Nashordaq-CSRF": "1"},
    ) as member:
        joined = await member.post(
            "/api/auth/register",
            json={
                "token": token,
                "username": "friend",
                "password": "my own secure password",
            },
        )
        assert joined.status_code == 201
        me = (await member.get("/api/user/me")).json()
        assert me["display_name"] == "friend"
        assert me["role"] == "player"
        assert me["onboarding_complete"] is False
        assert (await member.get("/api/market/players")).json() == []
        assert (await member.post("/api/auth/logout")).status_code == 200
        assert (
            await member.post(
                "/api/auth/login",
                json={"username": "friend", "password": "my own secure password"},
            )
        ).status_code == 200
    assert (await client.get("/api/auth/invites")).json()[0]["status"] == "consumed"


async def test_administrator_revokes_unused_invitation_and_replay_creates_no_account(
    local_instance,
):
    client, logs, _ = local_instance
    await register_operator(client, logs)
    invitation = (await client.post("/api/auth/invites")).json()
    assert (
        await client.delete(f"/api/auth/invites/{invitation['id']}")
    ).status_code == 200
    assert (await client.get("/api/auth/invites")).json()[0]["status"] == "revoked"
    token = re.search(r"/invite\?token=([A-Za-z0-9_-]+)", invitation["url"])[1]
    rejected = await client.post(
        "/api/auth/register",
        json={
            "token": token,
            "username": "blocked",
            "password": "my own secure password",
        },
    )
    assert rejected.status_code == 400
    assert len((await client.get("/api/admin/users")).json()) == 1
    assert (
        await client.delete(f"/api/auth/invites/{invitation['id']}")
    ).status_code == 409
    assert (await client.delete("/api/auth/invites/9999")).status_code == 409


async def test_invitation_controls_reject_members_and_anonymous_visitors(
    local_instance,
):
    client, logs, _ = local_instance
    await register_operator(client, logs)
    invitation = (await client.post("/api/auth/invites")).json()
    token = re.search(r"/invite\?token=([A-Za-z0-9_-]+)", invitation["url"])[1]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Nashordaq-CSRF": "1"},
    ) as member:
        for method, path in [
            ("GET", "/api/auth/invites"),
            ("POST", "/api/auth/invites"),
            ("DELETE", f"/api/auth/invites/{invitation['id']}"),
        ]:
            assert (await member.request(method, path)).status_code == 401
        assert (
            await member.post(
                "/api/auth/register",
                json={
                    "token": token,
                    "username": "friend",
                    "password": "my own secure password",
                },
            )
        ).status_code == 201
        for method, path in [
            ("GET", "/api/auth/invites"),
            ("POST", "/api/auth/invites"),
            ("DELETE", f"/api/auth/invites/{invitation['id']}"),
        ]:
            assert (
                await member.request(method, path, headers={"Remote-Role": "admin"})
            ).status_code == 403
    assert (
        await client.delete(f"/api/auth/invites/{invitation['id']}")
    ).status_code == 409


async def test_expired_invitation_does_not_create_account(local_instance, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from app import auth

    client, logs, _ = local_instance
    now = datetime(2026, 10, 13, tzinfo=UTC)
    monkeypatch.setattr(auth, "utc_now", lambda: now)
    await register_operator(client, logs)
    invitation = (await client.post("/api/auth/invites")).json()
    assert invitation["expires_at"] == "2026-10-20T00:00:00Z"
    token = re.search(r"/invite\?token=([A-Za-z0-9_-]+)", invitation["url"])[1]
    now += timedelta(days=7)
    assert (
        await client.post(
            "/api/auth/register",
            json={
                "token": token,
                "username": "late",
                "password": "my own secure password",
            },
        )
    ).status_code == 400
    assert (
        await client.post(
            "/api/auth/login",
            json={"username": "operator", "password": "a secure password"},
        )
    ).status_code == 200
    assert (await client.get("/api/auth/invites")).json()[0]["status"] == "expired"
    assert len((await client.get("/api/admin/users")).json()) == 1
    assert (
        await client.delete(f"/api/auth/invites/{invitation['id']}")
    ).status_code == 409


async def test_bad_credentials_leave_invitation_usable(local_instance):
    client, logs, _ = local_instance
    await register_operator(client, logs)
    invitation = (await client.post("/api/auth/invites")).json()
    token = re.search(r"/invite\?token=([A-Za-z0-9_-]+)", invitation["url"])[1]
    for username, password, status in [
        ("", "my own secure password", 422),
        ("friend", "private", 422),
        ("\n\x01", "my own secure password", 422),
        (" operator ", "my own secure password", 409),
    ]:
        rejected = await client.post(
            "/api/auth/register",
            json={"token": token, "username": username, "password": password},
        )
        assert rejected.status_code == status
        assert token not in rejected.text
        assert password not in rejected.text
        assert (await client.get("/api/auth/invites")).json()[0]["status"] == "active"
        assert len((await client.get("/api/admin/users")).json()) == 1
    assert (
        await client.post(
            "/api/auth/register",
            json={
                "token": token,
                "username": " friend ",
                "password": "my own secure password",
            },
        )
    ).status_code == 201
    assert (await client.get("/api/user/me")).json()["display_name"] == "friend"


async def test_concurrent_invitation_redemption_has_one_member_and_survives_restart(
    local_instance,
):
    import asyncio

    client, logs, _ = local_instance
    setup_token = await register_operator(client, logs)
    invitation = (await client.post("/api/auth/invites")).json()
    token = re.search(r"/invite\?token=([A-Za-z0-9_-]+)", invitation["url"])[1]
    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Nashordaq-CSRF": "1"},
        ) as first,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Nashordaq-CSRF": "1"},
        ) as second,
    ):
        responses = await asyncio.gather(
            *[
                browser.post(
                    "/api/auth/register",
                    json={
                        "token": token,
                        "username": name,
                        "password": "my own secure password",
                    },
                )
                for browser, name in [(first, "first"), (second, "second")]
            ]
        )
        assert sorted(response.status_code for response in responses) == [201, 400]
        winner, loser = (
            (first, second) if responses[0].status_code == 201 else (second, first)
        )
        assert (await loser.get("/api/auth/session")).status_code == 401
        assert len((await client.get("/api/admin/users")).json()) == 2
        await database.engine.dispose()
        await main.initialize_instance()
        assert (await winner.get("/api/user/me")).json()["role"] == "player"
        assert (await client.get("/api/auth/invites")).json()[0]["status"] == "consumed"
        for invalid_token in [token, setup_token, "unknown"]:
            assert (
                await loser.post(
                    "/api/auth/register",
                    json={
                        "token": invalid_token,
                        "username": "replay",
                        "password": "my own secure password",
                    },
                )
            ).status_code == 400
        assert len((await client.get("/api/admin/users")).json()) == 2
        assert (
            await loser.post(
                "/api/auth/register",
                json={"username": "open", "password": "my own secure password"},
            )
        ).status_code == 422


async def test_invitation_mutations_enforce_csrf_and_do_not_log_tokens(
    local_instance, caplog
):
    client, logs, _ = local_instance
    await register_operator(client, logs)
    caplog.clear()
    invitation = (await client.post("/api/auth/invites")).json()
    token = re.search(r"/invite\?token=([A-Za-z0-9_-]+)", invitation["url"])[1]
    assert token not in caplog.text
    for method, path, body in [
        ("POST", "/api/auth/invites", None),
        ("DELETE", f"/api/auth/invites/{invitation['id']}", None),
        (
            "POST",
            "/api/auth/register",
            {
                "token": token,
                "username": "blocked",
                "password": "my own secure password",
            },
        ),
    ]:
        assert (
            await client.request(
                method, path, json=body, headers={"Origin": "https://evil.example"}
            )
        ).status_code == 403
        assert (
            await client.request(
                method, path, json=body, headers={"X-Nashordaq-CSRF": ""}
            )
        ).status_code == 403
    assert (await client.get("/api/auth/invites")).json()[0]["status"] == "active"
    assert len((await client.get("/api/admin/users")).json()) == 1


async def test_password_change_verifies_current_credential_and_ends_all_own_sessions(
    local_instance,
):
    client, logs, _ = local_instance
    await register_operator(client, logs)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Nashordaq-CSRF": "1"},
    ) as second:
        assert (
            await second.post(
                "/api/auth/login",
                json={
                    "username": "operator",
                    "password": "a secure password",
                },
            )
        ).status_code == 200
        rejected = await client.post(
            "/api/auth/password",
            json={
                "current_password": "wrong",
                "new_password": "a replacement password",
            },
        )
        assert rejected.status_code == 403
        assert (await second.get("/api/auth/session")).status_code == 200
        changed = await client.post(
            "/api/auth/password",
            json={
                "current_password": "a secure password",
                "new_password": "a replacement password",
                "user_id": 999,
            },
        )
        assert changed.status_code == 200
        assert (await client.get("/api/auth/session")).status_code == 401
        assert (await second.get("/api/auth/session")).status_code == 401
        assert (
            await second.post(
                "/api/auth/login",
                json={
                    "username": "operator",
                    "password": "a secure password",
                },
            )
        ).status_code == 401
        assert (
            await second.post(
                "/api/auth/login",
                json={
                    "username": "operator",
                    "password": "a replacement password",
                },
            )
        ).status_code == 200


async def join_member(administrator, member, username="friend"):
    invitation = (await administrator.post("/api/auth/invites")).json()
    token = re.search(r"/invite\?token=([A-Za-z0-9_-]+)", invitation["url"])[1]
    assert (
        await member.post(
            "/api/auth/register",
            json={
                "token": token,
                "username": username,
                "password": "my own secure password",
            },
        )
    ).status_code == 201
    return (await member.get("/api/user/me")).json()["id"]


async def test_admin_reset_delivers_once_and_revokes_only_target_sessions(
    local_instance,
):
    client, logs, _ = local_instance
    await register_operator(client, logs)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Nashordaq-CSRF": "1"},
    ) as member:
        user_id = await join_member(client, member)
        response = await client.post("/api/auth/resets", json={"user_id": user_id})
        assert response.status_code == 201
        reset = response.json()
        token = re.search(r"/reset\?token=([A-Za-z0-9_-]+)", reset["url"])[1]
        lifecycle = (await client.get("/api/auth/resets")).json()
        assert lifecycle[0]["user_id"] == user_id
        assert token not in str(lifecycle)
        assert (
            await member.post(
                "/api/auth/reset",
                json={
                    "token": token,
                    "new_password": "the recovered password",
                },
            )
        ).status_code == 200
        assert (await member.get("/api/auth/session")).status_code == 401
        assert (await client.get("/api/auth/session")).status_code == 200
        assert (await client.get("/api/auth/resets")).json()[0]["status"] == "consumed"
        assert (
            await member.post(
                "/api/auth/login",
                json={
                    "username": "friend",
                    "password": "the recovered password",
                },
            )
        ).status_code == 200
        assert (
            await member.post(
                "/api/auth/reset",
                json={
                    "token": token,
                    "new_password": "replayed replacement password",
                },
            )
        ).status_code == 400
        assert (await member.get("/api/auth/session")).status_code == 200


@pytest.mark.parametrize("failure", ["expired", "revoked", "invalid", "validation"])
async def test_unusable_reset_changes_neither_credentials_nor_sessions(
    local_instance,
    monkeypatch,
    failure,
):
    from datetime import UTC, datetime, timedelta

    from app import auth

    client, logs, _ = local_instance
    now = datetime(2026, 10, 14, tzinfo=UTC)
    monkeypatch.setattr(auth, "utc_now", lambda: now)
    await register_operator(client, logs)
    user_id = (await client.get("/api/user/me")).json()["id"]
    reset = (await client.post("/api/auth/resets", json={"user_id": user_id})).json()
    assert reset["expires_at"] == "2026-10-14T01:00:00Z"
    token = re.search(r"/reset\?token=([A-Za-z0-9_-]+)", reset["url"])[1]
    password = "a rejected replacement"
    status = 400
    if failure == "expired":
        now += timedelta(hours=1)
    elif failure == "revoked":
        assert (
            await client.delete(f"/api/auth/resets/{reset['id']}")
        ).status_code == 200
    elif failure == "invalid":
        token = "unknown"
    else:
        password = "secret"
        status = 422
    response = await client.post(
        "/api/auth/reset",
        json={
            "token": token,
            "new_password": password,
        },
    )
    assert response.status_code == status
    assert token not in response.text and password not in response.text
    assert (await client.get("/api/auth/session")).status_code == 200
    assert (
        await client.post(
            "/api/auth/login",
            json={
                "username": "operator",
                "password": "a secure password",
            },
        )
    ).status_code == 200
    if failure in {"expired", "revoked"}:
        assert (
            await client.delete(f"/api/auth/resets/{reset['id']}")
        ).status_code == 409
    else:
        assert (await client.get("/api/auth/resets")).json()[0]["status"] == "active"


async def test_reset_controls_require_admin_and_all_mutations_enforce_csrf(
    local_instance,
):
    client, logs, _ = local_instance
    await register_operator(client, logs)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Nashordaq-CSRF": "1"},
    ) as member:
        paths = [
            ("GET", "/api/auth/resets", None),
            ("POST", "/api/auth/resets", {"user_id": 1}),
            ("DELETE", "/api/auth/resets/1", None),
            (
                "POST",
                "/api/auth/password",
                {
                    "current_password": "old",
                    "new_password": "a secure password",
                },
            ),
        ]
        for method, path, body in paths:
            assert (await member.request(method, path, json=body)).status_code == 401
        user_id = await join_member(client, member)
        for method, path, body in paths[:3]:
            assert (await member.request(method, path, json=body)).status_code == 403
        assert (
            await client.post("/api/auth/resets", json={"user_id": 9999})
        ).status_code == 404
        reset = (
            await client.post("/api/auth/resets", json={"user_id": user_id})
        ).json()
        token = re.search(r"/reset\?token=([A-Za-z0-9_-]+)", reset["url"])[1]
        for method, path, body in paths + [
            (
                "POST",
                "/api/auth/reset",
                {
                    "token": token,
                    "new_password": "a secure password",
                },
            )
        ]:
            for headers in [
                {"X-Nashordaq-CSRF": ""},
                {"Origin": "https://evil.example"},
            ]:
                assert (
                    await client.request(method, path, json=body, headers=headers)
                ).status_code == (200 if method == "GET" else 403)
        assert (await member.get("/api/auth/session")).status_code == 200
        assert (await client.get("/api/auth/resets")).json()[0]["status"] == "active"


async def test_concurrent_reset_has_one_winner_and_revokes_other_reset_links(
    local_instance,
):
    import asyncio

    client, logs, _ = local_instance
    await register_operator(client, logs)
    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Nashordaq-CSRF": "1"},
        ) as first,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Nashordaq-CSRF": "1"},
        ) as second,
    ):
        user_id = await join_member(client, first)
        assert (
            await second.post(
                "/api/auth/login",
                json={
                    "username": "friend",
                    "password": "my own secure password",
                },
            )
        ).status_code == 200
        reset = (
            await client.post("/api/auth/resets", json={"user_id": user_id})
        ).json()
        other_reset = (
            await client.post("/api/auth/resets", json={"user_id": user_id})
        ).json()
        token = re.search(r"/reset\?token=([A-Za-z0-9_-]+)", reset["url"])[1]
        responses = await asyncio.gather(
            *[
                browser.post(
                    "/api/auth/reset", json={"token": token, "new_password": password}
                )
                for browser, password in [
                    (first, "the first replacement"),
                    (second, "the second replacement"),
                ]
            ]
        )
        assert sorted(response.status_code for response in responses) == [200, 400]
        assert (await first.get("/api/auth/session")).status_code == 401
        assert (await second.get("/api/auth/session")).status_code == 401
        assert (await client.get("/api/auth/session")).status_code == 200
        winner_password = (
            "the first replacement"
            if responses[0].status_code == 200
            else "the second replacement"
        )
        assert (
            await first.post(
                "/api/auth/login",
                json={
                    "username": "friend",
                    "password": winner_password,
                },
            )
        ).status_code == 200
        other_token = re.search(r"/reset\?token=([A-Za-z0-9_-]+)", other_reset["url"])[
            1
        ]
        assert (
            await second.post(
                "/api/auth/reset",
                json={
                    "token": other_token,
                    "new_password": "stale replacement password",
                },
            )
        ).status_code == 400
        assert (await first.get("/api/auth/session")).status_code == 200
        await database.engine.dispose()
        await main.initialize_instance()
        assert (await first.get("/api/auth/session")).status_code == 200
        assert {
            item["status"] for item in (await client.get("/api/auth/resets")).json()
        } == {"consumed", "revoked"}


async def test_password_change_revokes_unused_reset_and_preserves_other_member(
    local_instance,
):
    client, logs, _ = local_instance
    await register_operator(client, logs)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Nashordaq-CSRF": "1"},
    ) as member:
        await join_member(client, member)
        user_id = (await client.get("/api/user/me")).json()["id"]
        reset = (
            await client.post("/api/auth/resets", json={"user_id": user_id})
        ).json()
        assert (
            await client.post(
                "/api/auth/password",
                json={
                    "current_password": "a secure password",
                    "new_password": "a replacement password",
                },
            )
        ).status_code == 200
        assert (await member.get("/api/auth/session")).status_code == 200
        token = re.search(r"/reset\?token=([A-Za-z0-9_-]+)", reset["url"])[1]
        assert (
            await member.post(
                "/api/auth/reset",
                json={
                    "token": token,
                    "new_password": "a stale replacement",
                },
            )
        ).status_code == 400
        assert (
            await client.post(
                "/api/auth/login",
                json={
                    "username": "operator",
                    "password": "a replacement password",
                },
            )
        ).status_code == 200


async def operator_command(
    database_path,
    *arguments,
    password=None,
    demo_mode=False,
    terminal_stdin=False,
):
    import asyncio
    import os
    import sys

    terminal_fds = os.openpty() if terminal_stdin else None
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.operator",
        "recover-admin",
        "--database",
        str(database_path),
        *arguments,
        stdin=terminal_fds[1] if terminal_fds else asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={
            **os.environ,
            "NASHORDAQ_RIOT_API_KEY": "",
            "NASHORDAQ_DEMO_MODE_ENABLED": str(demo_mode).lower(),
        },
    )
    try:
        communication = process.communicate(
            None if terminal_fds else password.encode() if password is not None else b""
        )
        stdout, stderr = (
            await asyncio.wait_for(communication, timeout=10)
            if terminal_fds
            else await communication
        )
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        if terminal_fds:
            for fd in terminal_fds:
                os.close(fd)
    return process.returncode, (stdout + stderr).decode()


async def test_operator_recovers_same_sole_admin_and_revokes_its_sessions(
    local_instance,
    tmp_path,
):
    client, logs, _ = local_instance
    await register_operator(client, logs)
    before = (await client.get("/api/user/me")).json()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Nashordaq-CSRF": "1"},
    ) as member:
        await join_member(client, member)
        reset = (
            await client.post("/api/auth/resets", json={"user_id": before["id"]})
        ).json()
        password = "an operator recovered password"
        code, output = await operator_command(
            tmp_path / "instance.db",
            "--password-stdin",
            password=password + "\n",
        )
        assert code == 0, output
        assert password not in output
        assert (await client.get("/api/auth/session")).status_code == 401
        assert (await member.get("/api/auth/session")).status_code == 200
        assert (
            await client.post(
                "/api/auth/login",
                json={
                    "username": "operator",
                    "password": password,
                },
            )
        ).status_code == 200
        after = (await client.get("/api/user/me")).json()
        assert after == before
        assert len((await client.get("/api/admin/users")).json()) == 2
        token = re.search(r"/reset\?token=([A-Za-z0-9_-]+)", reset["url"])[1]
        assert (
            await member.post(
                "/api/auth/reset",
                json={
                    "token": token,
                    "new_password": "a stale recovered password",
                },
            )
        ).status_code == 400


async def test_login_racing_reset_cannot_keep_a_session_using_old_password(
    local_instance,
):
    import asyncio

    client, logs, _ = local_instance
    await register_operator(client, logs)
    user_id = (await client.get("/api/user/me")).json()["id"]
    reset = (await client.post("/api/auth/resets", json={"user_id": user_id})).json()
    token = re.search(r"/reset\?token=([A-Za-z0-9_-]+)", reset["url"])[1]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Nashordaq-CSRF": "1"},
    ) as old_login:
        login, reset_response = await asyncio.gather(
            old_login.post(
                "/api/auth/login",
                json={
                    "username": "operator",
                    "password": "a secure password",
                },
            ),
            client.post(
                "/api/auth/reset",
                json={
                    "token": token,
                    "new_password": "a recovered password",
                },
            ),
        )
        assert login.status_code in {200, 401}
        assert reset_response.status_code == 200
        assert (await old_login.get("/api/auth/session")).status_code == 401


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "empty",
        "legacy",
        "unsupported",
        "no_admin",
        "short",
        "multiple_lines",
        "no_stdin",
        "password_argv",
        "demo_mode",
        "terminal_stdin",
    ],
)
async def test_operator_recovery_failure_preserves_database_and_sessions(
    local_instance,
    tmp_path,
    failure,
):
    import sqlite3

    client, logs, _ = local_instance
    await register_operator(client, logs)
    target = tmp_path / "instance.db"
    arguments = ["--password-stdin"]
    password = "an operator recovered password\n"
    if failure in {"missing", "empty", "legacy", "unsupported", "no_admin"}:
        target = tmp_path / "other.db"
        if failure == "no_admin":
            fresh_engine = create_async_engine(f"sqlite+aiosqlite:///{target}")
            from app.models import Base

            async with fresh_engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            await fresh_engine.dispose()
            with sqlite3.connect(target) as connection:
                connection.execute("INSERT INTO instance_metadata VALUES (1, 1)")
        elif failure != "missing":
            with sqlite3.connect(target) as connection:
                if failure == "legacy":
                    connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
                elif failure in {"unsupported", "no_admin"}:
                    connection.execute(
                        "CREATE TABLE instance_metadata "
                        "(id INTEGER PRIMARY KEY, schema_version INTEGER)"
                    )
                    connection.execute(
                        "INSERT INTO instance_metadata VALUES (1, ?)",
                        (2 if failure == "unsupported" else 1,),
                    )
                    connection.execute(
                        "CREATE TABLE users (id INTEGER PRIMARY KEY, is_admin BOOLEAN)"
                    )
    elif failure == "short":
        password = "short\n"
    elif failure == "multiple_lines":
        password = "first password\nsecond password\n"
    elif failure == "no_stdin":
        arguments = []
    elif failure == "password_argv":
        arguments = ["--password", "a private argv password"]
        password = None
    before = target.read_bytes() if target.exists() else None
    code, output = await operator_command(
        target,
        *arguments,
        password=password,
        demo_mode=failure == "demo_mode",
        terminal_stdin=failure == "terminal_stdin",
    )
    assert code != 0
    if failure == "no_admin":
        assert "existing sole non-demo administrator" in output
    for secret in [
        "an operator recovered password",
        "a private argv password",
        "first password",
    ]:
        assert secret not in output
    assert (target.read_bytes() if target.exists() else None) == before
    assert (await client.get("/api/auth/session")).status_code == 200
    assert (
        await client.post(
            "/api/auth/login",
            json={
                "username": "operator",
                "password": "a secure password",
            },
        )
    ).status_code == 200


async def test_password_recovery_secrets_never_enter_logs_or_lifecycle_responses(
    local_instance,
    caplog,
):
    client, logs, _ = local_instance
    await register_operator(client, logs)
    user_id = (await client.get("/api/user/me")).json()["id"]
    caplog.clear()
    reset = (await client.post("/api/auth/resets", json={"user_id": user_id})).json()
    token = re.search(r"/reset\?token=([A-Za-z0-9_-]+)", reset["url"])[1]
    new_password = "a very private replacement"
    assert (
        await client.post(
            "/api/auth/reset",
            json={
                "token": token,
                "new_password": new_password,
            },
        )
    ).status_code == 200
    assert (
        await client.post(
            "/api/auth/login",
            json={
                "username": "operator",
                "password": new_password,
            },
        )
    ).status_code == 200
    for path in ["/api/auth/resets", "/api/user/me", "/api/admin/users"]:
        body = (await client.get(path)).text
        assert token not in body and new_password not in body
        assert "password_hash" not in body and "token_hash" not in body
    assert token not in caplog.text and new_password not in caplog.text


async def test_invitation_and_password_recovery_do_not_create_game_interventions(
    local_instance,
):
    client, logs, _ = local_instance
    await register_operator(client, logs)
    assert (await client.get("/api/activity")).json() == []
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Nashordaq-CSRF": "1"},
    ) as member:
        user_id = await join_member(client, member)
        invitation = (await client.post("/api/auth/invites")).json()
        assert (
            await client.delete(
                f"/api/auth/invites/{invitation['id']}",
            )
        ).status_code == 200
        reset = (
            await client.post("/api/auth/resets", json={"user_id": user_id})
        ).json()
        assert (
            await client.delete(f"/api/auth/resets/{reset['id']}")
        ).status_code == 200
        reset = (
            await client.post("/api/auth/resets", json={"user_id": user_id})
        ).json()
        token = re.search(r"/reset\?token=([A-Za-z0-9_-]+)", reset["url"])[1]
        assert (
            await member.post(
                "/api/auth/reset",
                json={
                    "token": token,
                    "new_password": "the recovered password",
                },
            )
        ).status_code == 200
        assert (
            await member.post(
                "/api/auth/login",
                json={
                    "username": "friend",
                    "password": "the recovered password",
                },
            )
        ).status_code == 200
        assert (await member.get("/api/activity")).json() == []
        assert (
            await member.post(
                "/api/auth/password",
                json={
                    "current_password": "the recovered password",
                    "new_password": "the final private password",
                },
            )
        ).status_code == 200
        assert (await client.get("/api/activity")).json() == []


async def test_registered_alias_survives_restart_and_riot_name_changes(local_instance):
    from sqlalchemy import select

    from app.models import TrackedPlayer, User

    client, logs, factory = local_instance
    assert (await client.get("/api/identities")).status_code == 401
    await register_operator(client, logs)
    first = (await client.get("/api/identities")).json()
    assert first["users"][0]["username"] == "operator"
    assert first["users"][0]["streamer_alias"] == "Aatrox"
    async with factory() as session:
        operator = await session.scalar(select(User).where(User.username == "operator"))
        player = TrackedPlayer(
            game_name="Recognizable Name",
            tag_line="SECRET",
            display_name="Private Name",
        )
        session.add(player)
        await session.flush()
        operator.linked_player_id = player.id
        await session.commit()
    linked = (await client.get("/api/identities")).json()
    assert linked["players"][0]["streamer_alias"] == "Aatrox"
    async with factory() as session:
        player = await session.scalar(select(TrackedPlayer))
        player.game_name = "Changed Name"
        await session.commit()
    await database.engine.dispose()
    await main.initialize_instance()
    restarted = (await client.get("/api/identities")).json()
    assert restarted["users"][0]["streamer_alias"] == "Aatrox"
    assert restarted["players"][0]["streamer_alias"] == "Aatrox"
    assert restarted["users"][0]["game_name"] == "Changed Name"


async def test_registration_extends_champions_with_league_items(local_instance):
    from app.models import User

    client, logs, factory = local_instance
    await register_operator(client, logs)
    async with factory() as session:
        # Occupy the remaining 172 champion identities through normal persistence
        # creation. No cryptographic login is required for fixture population.
        session.add_all([User(username=f"existing-{i}") for i in range(172)])
        await session.commit()
    invitation = (await client.post("/api/auth/invites")).json()
    token = re.search(r"/invite\?token=([A-Za-z0-9_-]+)", invitation["url"])[1]
    response = await client.post(
        "/api/auth/register",
        json={
            "token": token,
            "username": "beyond-champions",
            "password": "my secure password",
        },
    )
    assert response.status_code == 201
    directory = (await client.get("/api/identities")).json()
    aliases = {
        member["username"]: member["streamer_alias"] for member in directory["users"]
    }
    assert aliases["operator"] == "Aatrox"
    assert aliases["beyond-champions"] == "Infinity Edge"
    assert len(set(aliases.values())) == 174


async def test_full_alias_exhaustion_preserves_invitation_and_accounts(local_instance):
    from app.models import User

    client, logs, factory = local_instance
    await register_operator(client, logs)
    async with factory() as session:
        # The pinned pool contains 173 champions and 20 item/ability names.
        session.add_all([User(username=f"occupied-{i}") for i in range(192)])
        await session.commit()
    invitation = (await client.post("/api/auth/invites")).json()
    token = re.search(r"/invite\?token=([A-Za-z0-9_-]+)", invitation["url"])[1]
    response = await client.post(
        "/api/auth/register",
        json={"token": token, "username": "no-alias", "password": "my secure password"},
    )
    assert response.status_code == 503
    assert "All League streamer aliases are in use" in response.json()["detail"]
    assert (await client.get("/api/auth/invites")).json()[0]["status"] == "active"
    directory = (await client.get("/api/identities")).json()
    assert len(directory["users"]) == 193
    assert "no-alias" not in [member["username"] for member in directory["users"]]


async def test_concurrent_registration_assigns_distinct_permanent_aliases(
    local_instance,
):
    import asyncio

    client, logs, _ = local_instance
    await register_operator(client, logs)
    invitations = [(await client.post("/api/auth/invites")).json() for _ in range(2)]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Nashordaq-CSRF": "1"},
    ) as other:
        responses = await asyncio.gather(
            *[
                browser.post(
                    "/api/auth/register",
                    json={
                        "token": re.search(
                            r"/invite\?token=([A-Za-z0-9_-]+)", invitation["url"]
                        )[1],
                        "username": username,
                        "password": "my secure password",
                    },
                )
                for browser, invitation, username in [
                    (client, invitations[0], "member-one"),
                    (other, invitations[1], "member-two"),
                ]
            ]
        )
        assert [response.status_code for response in responses] == [201, 201]
        directory = (await client.get("/api/identities")).json()
        members = {
            member["username"]: member["streamer_alias"]
            for member in directory["users"]
        }
        assert members["operator"] == "Aatrox"
        assert {members["member-one"], members["member-two"]} == {"Ahri", "Akali"}
        assert (await other.get("/api/identities")).json() == directory


async def test_existing_standalone_data_receives_aliases_without_account_changes(
    local_instance,
):
    from sqlalchemy import text

    from app.models import TrackedPlayer

    client, logs, factory = local_instance
    await register_operator(client, logs)
    async with factory() as session:
        session.add(
            TrackedPlayer(
                game_name="Unlinked Private",
                tag_line="TOPSECRET",
                display_name="Private",
            )
        )
        await session.commit()
    before = (await client.get("/api/user/me")).json()
    # Empty alias assignments in the complete current schema exercise backfill.
    async with database.engine.begin() as connection:
        await connection.execute(text("DELETE FROM identity_aliases"))
    await database.engine.dispose()
    await main.initialize_instance()
    assert (await client.get("/api/user/me")).json() == before
    directory = (await client.get("/api/identities")).json()
    assert directory["users"][0]["streamer_alias"] == "Aatrox"
    assert directory["players"][0]["streamer_alias"] == "Ahri"
    assert directory["players"][0]["username"] is None
    await main.initialize_instance()
    assert (await client.get("/api/identities")).json() == directory
