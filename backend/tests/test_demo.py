import random
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models import PriceHistory, TrackedPlayer


async def test_demo_access_fails_closed_until_explicit_login_lands(
    auth_client, client, monkeypatch
):
    monkeypatch.setattr(settings, "demo_mode_enabled", True)
    for headers in [
        {},
        {"Remote-User": "administrator", "Remote-Role": "admin"},
        {"Cookie": "nashordaq_demo_session=old-demo-token"},
    ]:
        response = await client.get("/api/user/me", headers=headers)
        assert response.status_code == 401
    assert (await auth_client.get("/api/market/players")).status_code == 401
    response = await auth_client.post(
        "/api/auth/login", json={"username": "demo", "password": "demo"}
    )
    assert response.status_code == 403
    assert (await client.get("/api/auth/status")).json() == {
        "setup_required": False,
        "demo_mode_enabled": True,
    }


async def test_demo_market_tick_updates_prices_and_creates_history(
    db_engine, monkeypatch
):
    """Call demo_market_tick_job directly and verify it updates player prices."""
    from app.scheduler import demo_market_tick_job

    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    monkeypatch.setattr("app.scheduler.SessionLocal", session_factory)

    random.seed(42)

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="TickPlayer",
            tag_line="EUW",
            display_name="Tick Player",
            current_price=30.0,
            lp_abs=2000,
            previous_lp_abs=1900,
            last_updated=datetime.now(UTC),
            avg_lp_gain_on_win=22.0,
            avg_lp_loss_on_loss=18.0,
        )
        session.add(player)
        await session.commit()
        player_id = player.id

    await demo_market_tick_job()

    async with session_factory() as session:
        result = await session.execute(
            select(TrackedPlayer).where(TrackedPlayer.id == player_id)
        )
        updated_player = result.scalar_one()
        assert updated_player.last_updated is not None

        history_result = await session.execute(
            select(PriceHistory).where(PriceHistory.player_id == player_id)
        )
        history_entries = history_result.scalars().all()
        assert len(history_entries) == 1
        assert history_entries[0].price == updated_player.current_price
        assert updated_player.current_price != 30.0
