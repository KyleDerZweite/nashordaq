from app.config import settings


async def test_leaderboard_single_user(auth_client):
    await auth_client.get("/api/user/me")
    onboard_resp = await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "boardUser",
            "tag_line": "EUW",
            "display_name": "Board User",
        },
    )
    assert onboard_resp.status_code == 200

    resp = await auth_client.get("/api/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["display_name"] == "Board User"
    assert data[0]["total_value"] == settings.starting_balance
    assert data[0]["rank"] == 1
