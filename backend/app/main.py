from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import SessionLocal, engine, init_db
from app.riot import PlayerNotFoundError, RateLimitedError, get_rank
from app.routers import leaderboard, market, orders, portfolio, user
from app.scheduler import get_last_market_update_at, start_scheduler, stop_scheduler
from app.seed import sync_tracked_players


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(
            settings.http_timeout_seconds,
            connect=settings.http_connect_timeout_seconds,
        )
    )
    await init_db()
    async with SessionLocal() as session:
        await sync_tracked_players(session)
    start_scheduler(app)
    yield
    stop_scheduler()
    await app.state.http_client.aclose()
    await engine.dispose()


app = FastAPI(title="Nashordaq", lifespan=lifespan)

allowed_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", settings.auth_header, "Remote-Email", "Remote-Name"],
)

app.include_router(user.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(leaderboard.router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    last_update = get_last_market_update_at() or datetime.now(UTC)
    return {
        "status": "ok",
        "update": last_update.strftime("%Y-%m-%d %H:%M"),
    }


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
