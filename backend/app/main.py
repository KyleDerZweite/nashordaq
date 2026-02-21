from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from app.config import settings
from app.riot import PlayerNotFoundError, RateLimitedError, get_rank


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient()
    yield
    await app.state.http_client.aclose()


app = FastAPI(title="Nashordaq", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/market/quote")
async def quote(
    gameName: str = Query(...),
    tagLine: str = Query(...),
) -> dict[str, Any]:
    try:
        rank_data = await get_rank(
            client=app.state.http_client,
            base_url=settings.riot_api_base_url,
            region_url=settings.riot_api_region_url,
            api_key=settings.riot_api_key,
            game_name=gameName,
            tag_line=tagLine,
        )
    except PlayerNotFoundError as e:
        return JSONResponse(status_code=404, content={"detail": str(e)})
    except RateLimitedError as e:
        return JSONResponse(status_code=429, content={"detail": str(e)})

    return {
        "gameName": gameName,
        "tagLine": tagLine,
        "tier": rank_data.tier,
        "rank": rank_data.rank,
        "leaguePoints": rank_data.league_points,
    }
