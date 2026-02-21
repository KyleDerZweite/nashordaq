import os

os.environ.setdefault("NASHORDAQ_RIOT_API_KEY", "test-api-key")
os.environ.setdefault("NASHORDAQ_RIOT_API_BASE_URL", "https://europe.api.riotgames.com")
os.environ.setdefault("NASHORDAQ_RIOT_API_REGION_URL", "https://euw1.api.riotgames.com")

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    app.state.http_client = httpx.AsyncClient()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await app.state.http_client.aclose()
