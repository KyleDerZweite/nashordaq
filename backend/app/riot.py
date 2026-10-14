from datetime import UTC, datetime
from typing import Annotated, Literal

import httpx
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, TypeAdapter

NonemptyString = Annotated[str, Field(min_length=1)]


class _RiotPayload(BaseModel):
    model_config = ConfigDict(strict=True)


class _AccountPayload(_RiotPayload):
    puuid: NonemptyString
    gameName: NonemptyString | None = None
    tagLine: NonemptyString | None = None


class _LeagueEntry(_RiotPayload):
    queueType: NonemptyString
    summonerId: NonemptyString | None = None
    tier: Literal[
        "IRON",
        "BRONZE",
        "SILVER",
        "GOLD",
        "PLATINUM",
        "EMERALD",
        "DIAMOND",
        "MASTER",
        "GRANDMASTER",
        "CHALLENGER",
    ]
    rank: Literal["I", "II", "III", "IV"]
    leaguePoints: int
    wins: int = Field(default=0, ge=0)
    losses: int = Field(default=0, ge=0)
    hotStreak: bool = False
    inactive: bool = False


class _MatchParticipant(_RiotPayload):
    puuid: NonemptyString
    win: bool
    gameEndTimestamp: int | None = Field(default=None, gt=0)


class _MatchInfo(_RiotPayload):
    queueId: int = Field(ge=0)
    gameDuration: int = Field(
        ge=0, validation_alias=AliasChoices("gameDuration", "gameDurationSeconds")
    )
    gameEndTimestamp: int | None = Field(default=None, gt=0)
    participants: list[_MatchParticipant] = Field(min_length=1)


class _MatchMetadata(_RiotPayload):
    matchId: NonemptyString | None = None


class _MatchPayload(_RiotPayload):
    metadata: _MatchMetadata = Field(default_factory=_MatchMetadata)
    info: _MatchInfo


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
    inactive: bool


class MatchSummary(BaseModel):
    match_id: str
    queue_id: int
    win: bool
    game_duration_seconds: int
    game_end_timestamp: int


class PlayerNotFoundError(Exception):
    pass


RiotStatus = Literal[
    "missing_key",
    "unchecked",
    "available",
    "invalid_key",
    "unavailable",
    "rate_limited",
    "demo",
]


class RiotIntegrationError(Exception):
    def __init__(self, status: RiotStatus, detail: str, http_status: int = 503):
        super().__init__(detail)
        self.status = status
        self.http_status = http_status


class RateLimitedError(RiotIntegrationError):
    def __init__(self, detail: str = "Riot is rate limited. Wait a moment and retry."):
        super().__init__("rate_limited", detail, 429)


_last_failure: RiotIntegrationError | None = None
_verified = False


def _invalid_response() -> RiotIntegrationError:
    global _last_failure, _verified
    _last_failure = RiotIntegrationError(
        "unavailable",
        "Riot returned an invalid response. Retry later. "
        "Local account access remains available.",
        502,
    )
    _verified = False
    return _last_failure


def integration_status(api_key: str, demo: bool = False) -> tuple[RiotStatus, str]:
    if demo:
        return "demo", "Demo uses a simulated market and does not require Riot."
    if not api_key.strip():
        return (
            "missing_key",
            "Riot is not configured. Ask the operator to set "
            "NASHORDAQ_RIOT_API_KEY in the protected environment configuration "
            "and recreate the full Compose stack. "
            "Local account access remains available.",
        )
    if _last_failure is not None:
        return _last_failure.status, str(_last_failure)
    if _verified:
        return "available", "The last Riot request succeeded."
    return "unchecked", "Riot is configured but has not been verified yet."


async def _request[T](
    client: httpx.AsyncClient,
    url: str,
    api_key: str,
    *,
    payload_type: TypeAdapter[T],
    params: dict[str, int | str] | None = None,
) -> T:
    global _last_failure, _verified
    try:
        if not api_key.strip():
            raise RiotIntegrationError("missing_key", integration_status(api_key)[1])
        response = await client.get(
            url, headers={"X-Riot-Token": api_key}, params=params
        )
        _check_response(response)
        try:
            payload = payload_type.validate_json(response.content)
        except ValueError:
            raise _invalid_response() from None
    except RiotIntegrationError as error:
        _last_failure = error
        raise
    except httpx.RequestError:
        error = RiotIntegrationError(
            "unavailable",
            "Riot is unavailable. Retry later. Local account access remains available.",
            502,
        )
        _last_failure = error
        raise error from None
    _last_failure = None
    _verified = True
    return payload


def _timestamp_seconds(value: datetime) -> int:
    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return int(value.timestamp())


def _check_response(response: httpx.Response) -> None:
    if response.status_code == 404:
        raise PlayerNotFoundError("Player not found")
    if response.status_code == 429:
        raise RateLimitedError()
    if response.status_code in {401, 403}:
        raise RiotIntegrationError(
            "invalid_key",
            "Riot rejected the API key. Ask the operator to replace "
            "NASHORDAQ_RIOT_API_KEY in the protected environment configuration "
            "and recreate the full Compose stack. "
            "Local account access remains available.",
        )
    if response.status_code >= 500:
        raise RiotIntegrationError(
            "unavailable",
            "Riot is unavailable. Retry later. Local account access remains available.",
            502,
        )
    response.raise_for_status()


async def get_account_by_riot_id(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    game_name: str,
    tag_line: str,
) -> AccountData:
    account = await _request(
        client,
        f"{base_url}/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}",
        api_key=api_key,
        payload_type=TypeAdapter(_AccountPayload),
    )
    return AccountData(
        puuid=account.puuid,
        game_name=account.gameName or game_name,
        tag_line=account.tagLine or tag_line,
    )


def _extract_solo_queue_rank(
    puuid: str,
    entries: list[_LeagueEntry],
    display_hint: str = "",
) -> RankData:
    solo_queue = next(
        (e for e in entries if e.queueType == "RANKED_SOLO_5x5"),
        None,
    )
    if solo_queue is None:
        hint = display_hint or f"puuid {puuid}"
        raise PlayerNotFoundError(f"No Solo Queue data for {hint}")

    return RankData(
        puuid=puuid,
        summoner_id=solo_queue.summonerId or puuid,
        tier=solo_queue.tier,
        rank=solo_queue.rank,
        league_points=solo_queue.leaguePoints,
        wins=solo_queue.wins,
        losses=solo_queue.losses,
        hot_streak=solo_queue.hotStreak,
        inactive=solo_queue.inactive,
    )


async def _fetch_league_entries(
    client: httpx.AsyncClient,
    region_url: str,
    api_key: str,
    puuid: str,
) -> list[_LeagueEntry]:
    return await _request(
        client,
        f"{region_url}/lol/league/v4/entries/by-puuid/{puuid}",
        api_key=api_key,
        payload_type=TypeAdapter(list[_LeagueEntry]),
    )


async def get_rank_by_puuid(
    client: httpx.AsyncClient,
    region_url: str,
    api_key: str,
    puuid: str,
) -> RankData:
    """Fast rank refresh: single league-v4/entries/by-puuid call (20000 req/10s)."""
    entries = await _fetch_league_entries(client, region_url, api_key, puuid)
    return _extract_solo_queue_rank(puuid, entries)


async def get_rank(
    client: httpx.AsyncClient,
    base_url: str,
    region_url: str,
    api_key: str,
    game_name: str,
    tag_line: str,
) -> RankData:
    """Full rank lookup from Riot ID: account-v1 + league-v4 (2 API calls)."""
    account = await get_account_by_riot_id(
        client=client,
        base_url=base_url,
        api_key=api_key,
        game_name=game_name,
        tag_line=tag_line,
    )
    entries = await _fetch_league_entries(client, region_url, api_key, account.puuid)
    return _extract_solo_queue_rank(account.puuid, entries, f"{game_name}#{tag_line}")


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
    params: dict[str, int | str] = {"start": start, "count": count}
    if start_time is not None:
        params["startTime"] = _timestamp_seconds(start_time)
    if queue is not None:
        params["queue"] = queue
    if type is not None:
        params["type"] = type

    return await _request(
        client,
        f"{base_url}/lol/match/v5/matches/by-puuid/{puuid}/ids",
        api_key=api_key,
        payload_type=TypeAdapter(list[NonemptyString]),
        params=params,
    )


async def get_match_summary(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    puuid: str,
    match_id: str,
) -> MatchSummary:
    payload = await _request(
        client,
        f"{base_url}/lol/match/v5/matches/{match_id}",
        api_key=api_key,
        payload_type=TypeAdapter(_MatchPayload),
    )
    info = payload.info

    participant = next(
        (item for item in info.participants if item.puuid == puuid),
        None,
    )
    if participant is None:
        raise _invalid_response()
    end_timestamp = info.gameEndTimestamp or participant.gameEndTimestamp
    if end_timestamp is None:
        raise _invalid_response()

    return MatchSummary(
        match_id=payload.metadata.matchId or match_id,
        queue_id=info.queueId,
        win=participant.win,
        game_duration_seconds=info.gameDuration,
        game_end_timestamp=end_timestamp,
    )
