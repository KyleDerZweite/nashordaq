from datetime import UTC, datetime
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import TrackedPlayer
from app.riot import integration_status
from app.scheduler import (
    classify_market_status,
    get_last_market_update_at,
    get_required_market_update_interval,
    is_scheduler_running,
)
from app.schemas import SystemStatusResponse


async def observe_system_status(session: AsyncSession) -> SystemStatusResponse:
    total_player_count = (
        await session.scalar(select(func.count()).select_from(TrackedPlayer)) or 0
    )
    trackable_player_count = (
        await session.scalar(
            select(func.count())
            .select_from(TrackedPlayer)
            .where(TrackedPlayer.lp_abs > 0)
        )
        or 0
    )
    interval = get_required_market_update_interval(trackable_player_count)
    last_market_update_at = get_last_market_update_at()
    scheduler_running = is_scheduler_running()
    riot_status, riot_status_detail = integration_status(
        settings.riot_api_key, settings.demo_mode_enabled
    )

    return SystemStatusResponse(
        riot_status=riot_status,
        riot_status_detail=riot_status_detail,
        service_status="ok",
        scheduler_running=scheduler_running,
        market_status=classify_market_status(
            now=datetime.now(UTC),
            last_market_update_at=last_market_update_at,
            tracked_player_count=total_player_count,
            scheduler_running=scheduler_running,
            expected_interval=interval,
        ),
        tracked_player_count=total_player_count,
        expected_update_interval_minutes=max(1, ceil(interval.total_seconds() / 60)),
        last_market_update_at=last_market_update_at,
        gamba_enabled=settings.gamba_enabled,
        demo_mode_enabled=settings.demo_mode_enabled,
    )
