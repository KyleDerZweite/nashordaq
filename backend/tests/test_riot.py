import httpx
import pytest

from app.riot import PlayerNotFoundError, get_rank

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
