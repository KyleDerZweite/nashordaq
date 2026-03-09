from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.scheduler as scheduler_module
from app.models import PriceHistory, TrackedPlayer
from app.riot import RankData


@pytest.mark.asyncio
async def test_market_update_job_skips_persistence_without_lp_change(
    db_engine, monkeypatch
):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    original_last_updated = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="IdlePlayer",
            tag_line="EUW",
            display_name="Idle Player",
            puuid="idle-puuid",
            summoner_id="idle-summoner",
            current_price=25.0,
            lp_abs=1500,
            previous_lp_abs=1400,
            streak=3,
            gamma_factor=1.02,
            last_updated=original_last_updated,
        )
        session.add(player)
        await session.flush()
        session.add(
            PriceHistory(
                player_id=player.id,
                price=player.current_price,
                lp_abs=player.lp_abs,
                recorded_at=original_last_updated,
            )
        )
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="idle-puuid",
            summoner_id="idle-summoner",
            tier="GOLD",
            rank="I",
            league_points=0,
            wins=10,
            losses=10,
            hot_streak=False,
            veteran=True,
            inactive=True,
            fresh_blood=True,
        )

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank", fake_get_rank)
    monkeypatch.setattr(
        scheduler_module,
        "_app",
        SimpleNamespace(state=SimpleNamespace(http_client=http_client)),
    )
    monkeypatch.setattr(scheduler_module, "_last_market_update_at", None)

    try:
        await scheduler_module.market_update_job()
    finally:
        await http_client.aclose()

    async with session_factory() as session:
        player_result = await session.execute(
            select(TrackedPlayer).where(TrackedPlayer.game_name == "IdlePlayer")
        )
        player = player_result.scalar_one()
        history_count = await session.scalar(
            select(func.count()).select_from(PriceHistory)
        )

    assert player.current_price == 25.0
    assert player.lp_abs == 1500
    assert player.previous_lp_abs == 1400
    assert player.streak == 3
    assert player.last_updated == original_last_updated.replace(tzinfo=None)
    assert history_count == 1
