from datetime import UTC, datetime

import httpx
import pytest

from app.riot import (
    PlayerNotFoundError,
    get_match_summary,
    get_rank,
    get_recent_match_ids,
)

PUUID = "test-puuid-1234"
SUMMONER_ID = "test-summoner-id-5678"
BASE_URL = "https://europe.api.riotgames.com"
REGION_URL = "https://euw1.api.riotgames.com"
API_KEY = "test-api-key"


async def test_get_rank_success(httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE_URL}/riot/account/v1/accounts/by-riot-id/Faker/KR1",
        json={"puuid": PUUID, "gameName": "Faker", "tagLine": "KR1"},
    )
    httpx_mock.add_response(
        url=f"{REGION_URL}/lol/summoner/v4/summoners/by-puuid/{PUUID}",
        json={"id": SUMMONER_ID, "puuid": PUUID},
    )
    httpx_mock.add_response(
        url=f"{REGION_URL}/lol/league/v4/entries/by-summoner/{SUMMONER_ID}",
        json=[
            {
                "queueType": "RANKED_SOLO_5x5",
                "tier": "CHALLENGER",
                "rank": "I",
                "leaguePoints": 1200,
                "wins": 70,
                "losses": 30,
                "hotStreak": True,
                "inactive": False,
            },
            {
                "queueType": "RANKED_FLEX_SR",
                "tier": "DIAMOND",
                "rank": "II",
                "leaguePoints": 45,
            },
        ],
    )

    async with httpx.AsyncClient() as client:
        result = await get_rank(
            client=client,
            base_url=BASE_URL,
            region_url=REGION_URL,
            api_key=API_KEY,
            game_name="Faker",
            tag_line="KR1",
        )

    assert result.tier == "CHALLENGER"
    assert result.rank == "I"
    assert result.league_points == 1200
    assert result.puuid == PUUID
    assert result.summoner_id == SUMMONER_ID
    assert result.wins == 70
    assert result.losses == 30
    assert result.hot_streak is True
    assert result.inactive is False


async def test_get_rank_player_not_found(httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE_URL}/riot/account/v1/accounts/by-riot-id/Nobody/0000",
        status_code=404,
    )

    async with httpx.AsyncClient() as client:
        with pytest.raises(PlayerNotFoundError):
            await get_rank(
                client=client,
                base_url=BASE_URL,
                region_url=REGION_URL,
                api_key=API_KEY,
                game_name="Nobody",
                tag_line="0000",
            )


async def test_get_rank_fallback_to_by_puuid(httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE_URL}/riot/account/v1/accounts/by-riot-id/Faker/KR1",
        json={"puuid": PUUID, "gameName": "Faker", "tagLine": "KR1"},
    )
    httpx_mock.add_response(
        url=f"{REGION_URL}/lol/summoner/v4/summoners/by-puuid/{PUUID}",
        json={"puuid": PUUID},
    )
    httpx_mock.add_response(
        url=f"{REGION_URL}/lol/league/v4/entries/by-puuid/{PUUID}",
        json=[
            {
                "queueType": "RANKED_SOLO_5x5",
                "tier": "CHALLENGER",
                "rank": "I",
                "leaguePoints": 1200,
                "wins": 10,
                "losses": 5,
                "hotStreak": False,
                "inactive": False,
            }
        ],
    )

    async with httpx.AsyncClient() as client:
        result = await get_rank(
            client=client,
            base_url=BASE_URL,
            region_url=REGION_URL,
            api_key=API_KEY,
            game_name="Faker",
            tag_line="KR1",
        )

    assert result.tier == "CHALLENGER"
    assert result.rank == "I"
    assert result.league_points == 1200
    assert result.puuid == PUUID
    assert result.summoner_id == PUUID


async def test_get_recent_match_ids_success(httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE_URL}/lol/match/v5/matches/by-puuid/{PUUID}/ids?start=0&count=3&queue=420&type=ranked",
        json=["EUW1_1", "EUW1_2", "EUW1_3"],
    )

    async with httpx.AsyncClient() as client:
        result = await get_recent_match_ids(
            client=client,
            base_url=BASE_URL,
            api_key=API_KEY,
            puuid=PUUID,
            count=3,
            queue=420,
            type="ranked",
        )

    assert result == ["EUW1_1", "EUW1_2", "EUW1_3"]


async def test_get_recent_match_ids_supports_start_time(httpx_mock):
    httpx_mock.add_response(
        url=(
            f"{BASE_URL}/lol/match/v5/matches/by-puuid/{PUUID}/ids"
            "?start=0&count=2&startTime=1704067200&queue=420&type=ranked"
        ),
        json=["EUW1_10", "EUW1_11"],
    )

    async with httpx.AsyncClient() as client:
        result = await get_recent_match_ids(
            client=client,
            base_url=BASE_URL,
            api_key=API_KEY,
            puuid=PUUID,
            count=2,
            start_time=datetime(2024, 1, 1, tzinfo=UTC),
            queue=420,
            type="ranked",
        )

    assert result == ["EUW1_10", "EUW1_11"]


async def test_get_match_summary_success(httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE_URL}/lol/match/v5/matches/EUW1_42",
        json={
            "metadata": {"matchId": "EUW1_42"},
            "info": {
                "queueId": 420,
                "gameDuration": 1932,
                "gameEndTimestamp": 1_710_000_000_000,
                "participants": [
                    {"puuid": PUUID, "win": True},
                    {"puuid": "other", "win": False},
                ],
            },
        },
    )

    async with httpx.AsyncClient() as client:
        result = await get_match_summary(
            client=client,
            base_url=BASE_URL,
            api_key=API_KEY,
            puuid=PUUID,
            match_id="EUW1_42",
        )

    assert result.match_id == "EUW1_42"
    assert result.queue_id == 420
    assert result.win is True
    assert result.game_duration_seconds == 1932
    assert result.game_end_timestamp == 1_710_000_000_000
