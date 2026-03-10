from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import engine, get_session, init_db
from app.models import TrackedPlayer
from app.riot import PlayerNotFoundError, RateLimitedError, get_rank
from app.routers import leaderboard, market, orders, portfolio, user
from app.scheduler import (
    classify_market_status,
    get_last_market_update_at,
    get_required_market_update_interval,
    is_scheduler_running,
    start_scheduler,
    stop_scheduler,
)
from app.schemas import SystemStatusResponse

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(
            settings.http_timeout_seconds,
            connect=settings.http_connect_timeout_seconds,
        )
    )
    await init_db()
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
    allow_headers=[
        "Content-Type",
        settings.auth_header,
        "Remote-Email",
        "Remote-Name",
    ],
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


@app.get("/api/system/status", response_model=SystemStatusResponse)
async def system_status(session: SessionDep) -> SystemStatusResponse:
    tracked_player_count = await session.scalar(
        select(func.count()).select_from(TrackedPlayer)
    )
    player_count = tracked_player_count or 0
    expected_update_interval_minutes = int(
        get_required_market_update_interval(player_count).total_seconds() // 60
    )
    last_market_update_at = get_last_market_update_at()
    scheduler_running = is_scheduler_running()

    return SystemStatusResponse(
        service_status="ok",
        scheduler_running=scheduler_running,
        market_status=classify_market_status(
            now=datetime.now(UTC),
            last_market_update_at=last_market_update_at,
            tracked_player_count=player_count,
            scheduler_running=scheduler_running,
        ),
        tracked_player_count=player_count,
        expected_update_interval_minutes=max(1, expected_update_interval_minutes),
        last_market_update_at=last_market_update_at,
    )


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
        "wins": rank_data.wins,
        "losses": rank_data.losses,
        "hotStreak": rank_data.hot_streak,
        "veteran": rank_data.veteran,
        "inactive": rank_data.inactive,
        "freshBlood": rank_data.fresh_blood,
    }
