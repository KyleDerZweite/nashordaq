from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.scheduler as scheduler_module
from app.config import settings
from app.models import (
    GambaPosition,
    GambaStatus,
    Order,
    OrderSource,
    TrackedPlayer,
    User,
)
from app.riot import RankData


async def test_create_gamba_returns_404_when_disabled(
    auth_client,
    tradable_player,
    monkeypatch,
):
    monkeypatch.setattr(settings, "gamba_enabled", False)

    resp = await auth_client.post("/api/gamba", json={"cash_amount": 100})
    assert resp.status_code == 404

    me_resp = await auth_client.get("/api/user/me")
    assert me_resp.json()["balance"] == pytest.approx(settings.starting_balance)


async def test_list_gamba_returns_404_when_disabled(
    auth_client,
    tradable_player,
    monkeypatch,
):
    monkeypatch.setattr(settings, "gamba_enabled", False)

    resp = await auth_client.get("/api/gamba")
    assert resp.status_code == 404


async def test_create_gamba_position_creates_recent_order(
    auth_client,
    tradable_player,
    monkeypatch,
):
    monkeypatch.setattr("app.routers.gamba.random.choice", lambda players: players[0])
    monkeypatch.setattr("app.routers.gamba.random.uniform", lambda a, b: 24.0)

    resp = await auth_client.post("/api/gamba", json={"cash_amount": 100})

    assert resp.status_code == 201
    data = resp.json()
    assert data["player_name"] == tradable_player.display_name
    assert data["player_game_name"] == tradable_player.game_name
    assert data["cash_amount"] == 100
    assert data["quantity"] == pytest.approx(4.0)
    assert data["status"] == "ACTIVE"

    me_resp = await auth_client.get("/api/user/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["balance"] == pytest.approx(settings.starting_balance - 100)

    positions_resp = await auth_client.get("/api/gamba")
    assert positions_resp.status_code == 200
    assert len(positions_resp.json()) == 1

    recent_orders_resp = await auth_client.get("/api/orders/recent")
    assert recent_orders_resp.status_code == 200
    recent_order = recent_orders_resp.json()[0]
    assert recent_order["source"] == "GAMBA"
    assert recent_order["side"] == "BUY"
    assert recent_order["quantity"] == pytest.approx(4.0)


async def test_create_gamba_position_allows_multiple_active_positions(
    auth_client,
    tradable_player,
    monkeypatch,
):
    monkeypatch.setattr("app.routers.gamba.random.choice", lambda players: players[0])
    monkeypatch.setattr("app.routers.gamba.random.uniform", lambda a, b: 24.0)

    first_resp = await auth_client.post("/api/gamba", json={"cash_amount": 100})
    assert first_resp.status_code == 201

    second_resp = await auth_client.post("/api/gamba", json={"cash_amount": 100})
    assert second_resp.status_code == 201

    positions_resp = await auth_client.get("/api/gamba")
    assert positions_resp.status_code == 200
    assert len(positions_resp.json()) == 2

    me_resp = await auth_client.get("/api/user/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["balance"] == pytest.approx(settings.starting_balance - 200)


@pytest.mark.asyncio
async def test_market_update_job_settles_due_gamba_position(db_engine, monkeypatch):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    # Use a recent due_time so inactivity decay does not trigger.
    due_time = datetime.now(UTC) - timedelta(hours=1)

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="GambaTarget",
            tag_line="EUW",
            display_name="Gamba Target",
            puuid="gamba-puuid",
            summoner_id="gamba-summoner",
            current_price=30.0,
            lp_abs=1500,
            previous_lp_abs=1500,
            streak=0,
            last_updated=due_time,
        )
        user = User(username="gamba-user", balance=900.0)
        session.add_all([player, user])
        await session.flush()

        buy_order = Order(
            user_id=user.id,
            player_id=player.id,
            side="BUY",
            quantity=0,
            quantity_value=4.0,
            status="EXECUTED",
            source=OrderSource.GAMBA,
            execution_price=25.0,
            executed_at=due_time,
        )
        session.add(buy_order)
        await session.flush()

        position = GambaPosition(
            user_id=user.id,
            player_id=player.id,
            buy_order_id=buy_order.id,
            cash_amount=100.0,
            quantity=4.0,
            entry_price=25.0,
            scheduled_settlement_at=due_time,
            settlement_multiplier=2.5,
            status=GambaStatus.ACTIVE,
        )
        session.add(position)
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="gamba-puuid",
            summoner_id="gamba-summoner",
            tier="GOLD",
            rank="I",
            league_points=0,
            wins=10,
            losses=10,
            hot_streak=False,
            inactive=True,
        )

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)
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
        user = await session.scalar(select(User).where(User.username == "gamba-user"))
        position = await session.scalar(select(GambaPosition))
        sell_order = await session.scalar(
            select(Order)
            .where(Order.source == OrderSource.GAMBA)
            .where(Order.side == "SELL")
        )

    assert user is not None
    assert position is not None
    assert sell_order is not None
    assert user.balance == pytest.approx(1050.0)
    assert position.status == GambaStatus.SETTLED
    assert position.raw_pnl == pytest.approx(20.0)
    assert position.settled_pnl == pytest.approx(50.0)
    assert sell_order.quantity_value == pytest.approx(4.0)
    assert sell_order.execution_price == pytest.approx(37.5)
