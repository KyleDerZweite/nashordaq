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
