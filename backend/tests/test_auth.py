from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.routers import user as user_router


async def test_auto_provision_new_user(auth_client):
    resp = await auth_client.get("/api/user/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testuser"
    assert data["role"] == "player"
    assert data["balance"] == settings.starting_balance
    assert data["linked_player_id"] is None
    assert data["onboarding_complete"] is False


async def test_existing_user_returned(auth_client):
    resp1 = await auth_client.get("/api/user/me")
    resp2 = await auth_client.get("/api/user/me")
    assert resp1.json()["id"] == resp2.json()["id"]


async def test_no_auth_header(client):
    resp = await client.get("/api/user/me")
    assert resp.status_code == 401


async def test_untrusted_proxy_rejected(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "enforce_trusted_proxy", True)
    monkeypatch.setattr(settings, "trusted_proxy_cidrs", "10.0.0.0/8")

    resp = await auth_client.get("/api/user/me")
    assert resp.status_code == 403


async def test_complete_onboarding(auth_client):
    resp = await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "mySummoner",
            "tag_line": "EUW",
            "display_name": "My Summoner",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["onboarding_complete"] is True
    assert data["linked_player_id"] is not None


async def test_complete_onboarding_duplicate_player(auth_client):
    first = await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "dupeName",
            "tag_line": "EUW",
            "display_name": "Dupe",
        },
    )
    assert first.status_code == 200

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Remote-User": "seconduser"},
    ) as second_user_client:
        second = await second_user_client.post(
            "/api/user/onboarding",
            json={
                "game_name": "dupeName",
                "tag_line": "EUW",
                "display_name": "Dupe 2",
            },
        )
    assert second.status_code == 409


async def test_onboarding_twice_rejected(auth_client):
    first = await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "onceonly",
            "tag_line": "EUW",
            "display_name": "Once",
        },
    )
    assert first.status_code == 200

    second = await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "another",
            "tag_line": "EUW",
            "display_name": "Another",
        },
    )
    assert second.status_code == 409


async def test_onboarding_tagline_with_hash_is_accepted(auth_client):
    resp = await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "hashuser",
            "tag_line": "#EUW",
            "display_name": "Hash User",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["onboarding_complete"] is True


async def test_admin_user_role_and_onboarding_blocked(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "admin_remote_users", "testuser")

    me_resp = await auth_client.get("/api/user/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "admin"

    onboarding_resp = await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "viewer",
            "tag_line": "EUW",
            "display_name": "Viewer",
        },
    )
    assert onboarding_resp.status_code == 403
    assert onboarding_resp.json()["detail"] == "Admin users cannot onboard"


async def test_onboarding_initializes_market_price(auth_client, monkeypatch):
    async def _initialize(request, session, player):
        player.current_price = 42.0
        player.lp_abs = 3200
        player.previous_lp_abs = 3200

    monkeypatch.setattr(
        user_router,
        "_initialize_player_market_state",
        _initialize,
    )

    resp = await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "priceduser",
            "tag_line": "EUW",
            "display_name": "Priced User",
        },
    )

    assert resp.status_code == 200

    players_resp = await auth_client.get("/api/market/players")
    assert players_resp.status_code == 200
    players = players_resp.json()
    assert players[0]["current_price"] == 42.0

    player_detail_resp = await auth_client.get(
        f"/api/market/players/{players[0]['id']}"
    )
    assert player_detail_resp.status_code == 200
    player_detail = player_detail_resp.json()
    assert player_detail["lp_abs"] == 3200


async def test_update_profile(auth_client):
    onboard_resp = await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "beforeupdate",
            "tag_line": "EUW",
            "display_name": "Before Update",
        },
    )
    assert onboard_resp.status_code == 200

    update_resp = await auth_client.put(
        "/api/user/profile",
        json={
            "game_name": "afterupdate",
            "tag_line": "EUW",
            "display_name": "After Update",
        },
    )
    assert update_resp.status_code == 200

    players_resp = await auth_client.get("/api/market/players")
    assert players_resp.status_code == 200
    players = players_resp.json()
    assert players[0]["game_name"] == "afterupdate"
    assert players[0]["display_name"] == "After Update"


async def test_update_profile_duplicate_player_rejected(auth_client):
    first = await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "firstplayer",
            "tag_line": "EUW",
            "display_name": "First Player",
        },
    )
    assert first.status_code == 200

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Remote-User": "seconduser"},
    ) as second_user_client:
        second = await second_user_client.post(
            "/api/user/onboarding",
            json={
                "game_name": "secondplayer",
                "tag_line": "EUW",
                "display_name": "Second Player",
            },
        )
        assert second.status_code == 200

        update_resp = await second_user_client.put(
            "/api/user/profile",
            json={
                "game_name": "firstplayer",
                "tag_line": "EUW",
                "display_name": "Collision",
            },
        )

    assert update_resp.status_code == 409


async def test_admin_user_profile_update_blocked(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "admin_remote_users", "testuser")

    update_resp = await auth_client.put(
        "/api/user/profile",
        json={
            "game_name": "viewer",
            "tag_line": "EUW",
            "display_name": "Viewer",
        },
    )
    assert update_resp.status_code == 403
    assert update_resp.json()["detail"] == "Admin users cannot edit their profile"
