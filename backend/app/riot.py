from datetime import UTC, datetime

import httpx
from pydantic import BaseModel


class AccountData(BaseModel):
    puuid: str
    game_name: str
    tag_line: str


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


class MatchSummary(BaseModel):
    match_id: str
    queue_id: int
    win: bool
    game_duration_seconds: int
    game_end_timestamp: int


class PlayerNotFoundError(Exception):
    pass


class RateLimitedError(Exception):
    pass


def _timestamp_seconds(value: datetime) -> int:
    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return int(value.timestamp())


def _check_response(response: httpx.Response) -> None:
    if response.status_code == 404:
        raise PlayerNotFoundError("Player not found")
    if response.status_code == 429:
        raise RateLimitedError("Riot API rate limit exceeded")
    response.raise_for_status()


async def get_account_by_riot_id(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    game_name: str,
    tag_line: str,
) -> AccountData:
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

    return AccountData(
        puuid=puuid,
        game_name=account_payload.get("gameName") or game_name,
        tag_line=account_payload.get("tagLine") or tag_line,
    )


async def get_rank(
    client: httpx.AsyncClient,
    base_url: str,
    region_url: str,
    api_key: str,
    game_name: str,
    tag_line: str,
) -> RankData:
    headers = {"X-Riot-Token": api_key}
    account = await get_account_by_riot_id(
        client=client,
        base_url=base_url,
        api_key=api_key,
        game_name=game_name,
        tag_line=tag_line,
    )
    puuid = account.puuid

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


async def get_recent_match_ids(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    puuid: str,
    *,
    start: int = 0,
    count: int = 20,
    start_time: datetime | None = None,
    queue: int | None = None,
    type: str | None = None,
) -> list[str]:
    headers = {"X-Riot-Token": api_key}
    params: dict[str, int | str] = {"start": start, "count": count}
    if start_time is not None:
        params["startTime"] = _timestamp_seconds(start_time)
    if queue is not None:
        params["queue"] = queue
    if type is not None:
        params["type"] = type

    response = await client.get(
        f"{base_url}/lol/match/v5/matches/by-puuid/{puuid}/ids",
        headers=headers,
        params=params,
    )
    _check_response(response)
    payload = response.json()
    return [str(match_id) for match_id in payload]


async def get_match_summary(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    puuid: str,
    match_id: str,
) -> MatchSummary:
    headers = {"X-Riot-Token": api_key}
    response = await client.get(
        f"{base_url}/lol/match/v5/matches/{match_id}",
        headers=headers,
    )
    _check_response(response)
    payload = response.json()
    metadata = payload.get("metadata") or {}
    info = payload.get("info") or {}
    participants = info.get("participants") or []

    participant = next(
        (item for item in participants if item.get("puuid") == puuid),
        None,
    )
    if participant is None:
        raise PlayerNotFoundError(f"No match participant data for {match_id}")

    duration = int(info.get("gameDuration") or info.get("gameDurationSeconds") or 0)
    end_timestamp = int(
        info.get("gameEndTimestamp") or participant.get("gameEndTimestamp") or 0
    )

    return MatchSummary(
        match_id=metadata.get("matchId") or match_id,
        queue_id=int(info.get("queueId") or 0),
        win=bool(participant.get("win", False)),
        game_duration_seconds=duration,
        game_end_timestamp=end_timestamp,
    )
