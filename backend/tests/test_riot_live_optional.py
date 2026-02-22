import os
from pathlib import Path
from urllib.parse import quote

import httpx
import pytest

PLACEHOLDER_KEYS = {
    "",
    "test-api-key",
    "RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
}


def _read_dotenv() -> dict[str, str]:
    project_root = Path(__file__).resolve().parents[2]
    env_path = project_root / ".env"
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _resolve_riot_key(dotenv_values: dict[str, str]) -> str | None:
    env_key = os.getenv("NASHORDAQ_RIOT_API_KEY", "").strip()
    if env_key and env_key not in PLACEHOLDER_KEYS:
        return env_key

    dotenv_key = dotenv_values.get("NASHORDAQ_RIOT_API_KEY", "").strip()
    if dotenv_key and dotenv_key not in PLACEHOLDER_KEYS:
        return dotenv_key

    return None


async def test_live_riot_three_call_chain_optional():
    dotenv_values = _read_dotenv()
    riot_api_key = _resolve_riot_key(dotenv_values)

    if riot_api_key is None:
        pytest.skip(
            "No real Riot API key in env/.env; skipping optional live Riot test"
        )

    base_url = (
        os.getenv("NASHORDAQ_RIOT_API_BASE_URL")
        or dotenv_values.get("NASHORDAQ_RIOT_API_BASE_URL")
        or "https://europe.api.riotgames.com"
    )
    region_url = (
        os.getenv("NASHORDAQ_RIOT_API_REGION_URL")
        or dotenv_values.get("NASHORDAQ_RIOT_API_REGION_URL")
        or "https://euw1.api.riotgames.com"
    )

    game_name = (
        os.getenv("NASHORDAQ_LIVE_TEST_GAME_NAME")
        or dotenv_values.get("NASHORDAQ_LIVE_TEST_GAME_NAME")
        or "Azzapp"
    )
    tag_line = (
        os.getenv("NASHORDAQ_LIVE_TEST_TAG_LINE")
        or dotenv_values.get("NASHORDAQ_LIVE_TEST_TAG_LINE")
        or "31415"
    )

    headers = {"X-Riot-Token": riot_api_key}
    game_name_encoded = quote(game_name, safe="")
    tag_line_encoded = quote(tag_line, safe="")

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        account_resp = await client.get(
            f"{base_url}/riot/account/v1/accounts/by-riot-id/"
            f"{game_name_encoded}/{tag_line_encoded}",
            headers=headers,
        )
        if account_resp.status_code == 429:
            pytest.skip("Riot API rate limited during optional live test")
        assert account_resp.status_code == 200, account_resp.text

        account_data = account_resp.json()
        puuid = account_data.get("puuid")
        assert puuid, account_data

        summoner_resp = await client.get(
            f"{region_url}/lol/summoner/v4/summoners/by-puuid/{puuid}",
            headers=headers,
        )
        if summoner_resp.status_code == 429:
            pytest.skip("Riot API rate limited during optional live test")
        assert summoner_resp.status_code == 200, summoner_resp.text

        summoner_data = summoner_resp.json()
        summoner_id = summoner_data.get("id") or summoner_data.get("summonerId")

        if summoner_id:
            league_url = f"{region_url}/lol/league/v4/entries/by-summoner/{summoner_id}"
        else:
            league_url = f"{region_url}/lol/league/v4/entries/by-puuid/{puuid}"

        league_resp = await client.get(league_url, headers=headers)
        if league_resp.status_code == 429:
            pytest.skip("Riot API rate limited during optional live test")
        assert league_resp.status_code == 200, league_resp.text

        entries = league_resp.json()
        assert isinstance(entries, list)
        assert any(entry.get("queueType") == "RANKED_SOLO_5x5" for entry in entries)
