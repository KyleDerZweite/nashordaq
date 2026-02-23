from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app


async def test_auto_provision_new_user(auth_client):
    resp = await auth_client.get("/api/user/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testuser"
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
