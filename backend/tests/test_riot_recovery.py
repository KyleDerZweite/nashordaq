"""Riot failure journeys through authenticated HTTP and the real external adapter."""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.scheduler as scheduler_module
from app.config import settings
from app.main import app
from app.models import TrackedPlayer


@pytest.fixture(autouse=True)
def stub_initial_player_refresh():
    """Override the legacy no-op fixture and exercise real onboarding."""
    return None


async def test_missing_riot_key_explained_without_affecting_local_access(
    admin_client, monkeypatch
):
    monkeypatch.setattr(settings, "riot_api_key", "")
    status = await admin_client.get("/api/system/status")
    assert status.json()["riot_status"] == "missing_key"
    assert "restart" in status.json()["riot_status_detail"]
    lookup = await admin_client.get("/api/market/account?gameName=Player&tagLine=EUW")
    assert lookup.status_code == 503
    assert "NASHORDAQ_RIOT_API_KEY" in lookup.json()["detail"]
    assert (await admin_client.get("/api/auth/session")).status_code == 200
    assert (await admin_client.get("/api/admin/system/status")).status_code == 200


@pytest.mark.parametrize("upstream_status", [401, 403])
async def test_rejected_riot_key_keeps_account_unlinked(
    auth_client, monkeypatch, httpx_mock, upstream_status
):
    monkeypatch.setattr(settings, "riot_api_key", "controlled-rejected-secret")
    httpx_mock.add_response(status_code=upstream_status)
    result = await auth_client.post(
        "/api/user/onboarding", json={"game_name": "Player", "tag_line": "EUW"}
    )
    assert result.status_code == 503
    assert "replace NASHORDAQ_RIOT_API_KEY" in result.json()["detail"]
    assert "controlled-rejected-secret" not in result.text
    me = await auth_client.get("/api/user/me")
    assert me.json()["linked_player_id"] is None
    assert (await auth_client.get("/api/market/players")).json() == []
    assert (await auth_client.get("/api/auth/session")).status_code == 200
    assert (await auth_client.get("/api/system/status")).json()[
        "riot_status"
    ] == "invalid_key"


@pytest.mark.parametrize(
    "upstream_status, expected_status",
    [
        (401, "invalid_key"),
        (403, "invalid_key"),
        (429, "rate_limited"),
        (503, "unavailable"),
        ("network", "unavailable"),
    ],
)
async def test_later_upstream_failure_rolls_back_entire_refresh(
    auth_client,
    db_session,
    db_engine,
    monkeypatch,
    httpx_mock,
    upstream_status,
    expected_status,
):
    db_session.add_all(
        [
            TrackedPlayer(
                game_name="First",
                tag_line="EUW",
                display_name="First",
                puuid="first",
                current_price=10,
                lp_abs=0,
            ),
            TrackedPlayer(
                game_name="Second",
                tag_line="EUW",
                display_name="Second",
                puuid="second",
                current_price=25,
                lp_abs=1500,
            ),
        ]
    )
    await db_session.commit()
    before = (await auth_client.get("/api/market/players")).json()
    before_details = [
        (await auth_client.get(f"/api/market/players/{player['id']}")).json()
        for player in before
    ]
    httpx_mock.add_response(
        url=f"{settings.riot_api_region_url}/lol/league/v4/entries/by-puuid/first",
        json=[
            {
                "queueType": "RANKED_SOLO_5x5",
                "tier": "GOLD",
                "rank": "I",
                "leaguePoints": 50,
            }
        ],
    )
    second_url = f"{settings.riot_api_region_url}/lol/league/v4/entries/by-puuid/second"
    if upstream_status == "network":
        httpx_mock.add_exception(
            httpx.ReadTimeout("controlled diagnostic"), url=second_url
        )
    else:
        httpx_mock.add_response(url=second_url, status_code=upstream_status)
    monkeypatch.setattr(
        scheduler_module,
        "SessionLocal",
        async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False),
    )
    monkeypatch.setattr(scheduler_module, "_app", app)
    monkeypatch.setattr(scheduler_module, "_last_market_update_at", None)
    monkeypatch.setattr(settings, "riot_request_stagger_seconds", 0)
    await scheduler_module.market_update_job()
    after = (await auth_client.get("/api/market/players")).json()
    assert after == before
    assert [
        (await auth_client.get(f"/api/market/players/{player['id']}")).json()
        for player in after
    ] == before_details
    assert (await auth_client.get("/api/system/status")).json()[
        "last_market_update_at"
    ] is None
    assert (await auth_client.get("/api/system/status")).json()[
        "riot_status"
    ] == expected_status


@pytest.mark.parametrize(
    "failure", ["missing_key", "outage", "network", "rate_limited"]
)
async def test_unavailable_riot_onboarding_can_retry_without_duplicate_player(
    auth_client, monkeypatch, httpx_mock, failure
):
    if failure == "missing_key":
        monkeypatch.setattr(settings, "riot_api_key", "")
        expected_code = 503
    elif failure == "network":
        httpx_mock.add_exception(httpx.ConnectError("controlled private diagnostics"))
        expected_code = 502
    else:
        httpx_mock.add_response(status_code=429 if failure == "rate_limited" else 503)
        expected_code = 429 if failure == "rate_limited" else 502
    payload = {"game_name": "RetryPlayer", "tag_line": "EUW"}
    result = await auth_client.post("/api/user/onboarding", json=payload)
    assert result.status_code == expected_code
    assert "controlled private diagnostics" not in result.text
    assert (await auth_client.get("/api/user/me")).json()["linked_player_id"] is None
    assert (await auth_client.get("/api/market/players")).json() == []

    # Replaced environment/restart is operator-owned. A controlled accepted response
    # here proves retry atomicity, not that an actual Riot credential is valid.
    monkeypatch.setattr(settings, "riot_api_key", "controlled-accepted-key")
    httpx_mock.add_response(json={"puuid": "retry-player"})
    httpx_mock.add_response(
        json=[
            {
                "queueType": "RANKED_SOLO_5x5",
                "tier": "GOLD",
                "rank": "I",
                "leaguePoints": 50,
                "wins": 10,
                "losses": 10,
            }
        ]
    )
    recovered = await auth_client.post("/api/user/onboarding", json=payload)
    assert recovered.status_code == 200
    assert recovered.json()["onboarding_complete"] is True
    players = (await auth_client.get("/api/market/players")).json()
    assert len(players) == 1
    assert players[0]["current_price"] == 25.5
    assert (await auth_client.get("/api/system/status")).json()[
        "riot_status"
    ] == "available"


async def test_match_outage_preserves_existing_price_and_history(
    auth_client, seeded_player, db_engine, monkeypatch, httpx_mock
):
    before = (await auth_client.get(f"/api/market/players/{seeded_player.id}")).json()
    httpx_mock.add_response(json={"puuid": "test-player"})
    httpx_mock.add_response(
        json=[
            {
                "queueType": "RANKED_SOLO_5x5",
                "tier": "GOLD",
                "rank": "I",
                "leaguePoints": 75,
            }
        ]
    )
    httpx_mock.add_response(status_code=502)
    monkeypatch.setattr(
        scheduler_module,
        "SessionLocal",
        async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False),
    )
    monkeypatch.setattr(scheduler_module, "_app", app)
    monkeypatch.setattr(scheduler_module, "_last_market_update_at", None)
    await scheduler_module.market_update_job()
    assert (
        await auth_client.get(f"/api/market/players/{seeded_player.id}")
    ).json() == before


async def test_missing_key_preserves_existing_market(
    auth_client, seeded_player, db_engine, monkeypatch
):
    before = (await auth_client.get(f"/api/market/players/{seeded_player.id}")).json()
    monkeypatch.setattr(settings, "riot_api_key", "")
    monkeypatch.setattr(
        scheduler_module,
        "SessionLocal",
        async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False),
    )
    monkeypatch.setattr(scheduler_module, "_app", app)
    monkeypatch.setattr(scheduler_module, "_last_market_update_at", None)
    await scheduler_module.market_update_job()
    assert (
        await auth_client.get(f"/api/market/players/{seeded_player.id}")
    ).json() == before
    assert (await auth_client.get("/api/auth/session")).status_code == 200


async def test_profile_failure_keeps_existing_link_and_identity(
    auth_client, seeded_player, httpx_mock
):
    before = (await auth_client.get(f"/api/market/players/{seeded_player.id}")).json()
    httpx_mock.add_response(status_code=403)
    changed = await auth_client.put(
        "/api/user/profile", json={"game_name": "Replacement", "tag_line": "EUW"}
    )
    assert changed.status_code == 503
    assert (
        await auth_client.get(f"/api/market/players/{seeded_player.id}")
    ).json() == before
    assert (await auth_client.get("/api/user/me")).json()[
        "linked_player_id"
    ] == seeded_player.id
