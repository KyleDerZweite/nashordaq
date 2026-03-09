import httpx
from pydantic import BaseModel


class RankData(BaseModel):
    puuid: str
    summoner_id: str
    tier: str
    rank: str
    league_points: int
    wins: int
    losses: int
    hot_streak: bool
    veteran: bool
    inactive: bool
    fresh_blood: bool


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
    account_payload = account_resp.json()
    puuid = account_payload.get("puuid")
    if not puuid:
        raise PlayerNotFoundError(f"No account data for {game_name}#{tag_line}")

    summoner_resp = await client.get(
        f"{region_url}/lol/summoner/v4/summoners/by-puuid/{puuid}",
        headers=headers,
    )
    _check_response(summoner_resp)
    summoner_payload = summoner_resp.json()
    summoner_id = summoner_payload.get("id") or summoner_payload.get("summonerId")

    league_url = (
        f"{region_url}/lol/league/v4/entries/by-summoner/{summoner_id}"
        if summoner_id
        else f"{region_url}/lol/league/v4/entries/by-puuid/{puuid}"
    )
    league_resp = await client.get(league_url, headers=headers)
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
        summoner_id=summoner_id or puuid,
        tier=solo_queue["tier"],
        rank=solo_queue["rank"],
        league_points=solo_queue["leaguePoints"],
        wins=solo_queue.get("wins", 0),
        losses=solo_queue.get("losses", 0),
        hot_streak=solo_queue.get("hotStreak", False),
        veteran=solo_queue.get("veteran", False),
        inactive=solo_queue.get("inactive", False),
        fresh_blood=solo_queue.get("freshBlood", False),
    )
