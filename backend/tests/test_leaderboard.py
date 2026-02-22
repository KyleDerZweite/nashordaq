async def test_leaderboard_single_user(auth_client):
    await auth_client.get("/api/user/me")
    resp = await auth_client.get("/api/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["username"] == "testuser"
    assert data[0]["total_value"] == 10000.0
    assert data[0]["rank"] == 1
