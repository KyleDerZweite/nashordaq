from app.config import settings


async def test_auto_provision_new_user(auth_client):
    resp = await auth_client.get("/api/user/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testuser"
    assert data["balance"] == settings.starting_balance


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
