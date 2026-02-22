import httpx
from pydantic import BaseModel


class RankData(BaseModel):
    puuid: str
    summoner_id: str
    tier: str
    rank: str
    league_points: int


class PlayerNotFoundError(Exception):
    pass


class RateLimitedError(Exception):
    pass


def _check_response(response: httpx.Response) -> None:
    if response.status_code == 404:
        raise PlayerNotFoundError("Player not found")
    if response.status_code == 429:
        raise RateLimitedError("Riot API rate limit exceeded")
    response.raise_for_status()


async def get_rank(
    client: httpx.AsyncClient,
    base_url: str,
    region_url: str,
    api_key: str,
    game_name: str,
    tag_line: str,
) -> RankData:
    headers = {"X-Riot-Token": api_key}

    account_resp = await client.get(
        f"{base_url}/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}",
        headers=headers,
    )
    _check_response(account_resp)
    puuid: str = account_resp.json()["puuid"]

    summoner_resp = await client.get(
        f"{region_url}/lol/summoner/v4/summoners/by-puuid/{puuid}",
        headers=headers,
    )
    _check_response(summoner_resp)
    summoner_id: str = summoner_resp.json()["id"]

    league_resp = await client.get(
        f"{region_url}/lol/league/v4/entries/by-summoner/{summoner_id}",
        headers=headers,
    )
    _check_response(league_resp)

    entries: list[dict] = league_resp.json()
    solo_queue = next(
        (e for e in entries if e["queueType"] == "RANKED_SOLO_5x5"),
        None,
    )
    if solo_queue is None:
        raise PlayerNotFoundError(f"No Solo Queue data for {game_name}#{tag_line}")

    return RankData(
        puuid=puuid,
        summoner_id=summoner_id,
        tier=solo_queue["tier"],
        rank=solo_queue["rank"],
        league_points=solo_queue["leaguePoints"],
    )
