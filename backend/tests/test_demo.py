import os
import random
from datetime import UTC, datetime

os.environ.setdefault("NASHORDAQ_RIOT_API_KEY", "test-api-key")
os.environ.setdefault("NASHORDAQ_RIOT_API_BASE_URL", "https://europe.api.riotgames.com")
os.environ.setdefault("NASHORDAQ_RIOT_API_REGION_URL", "https://euw1.api.riotgames.com")

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, settings
from app.database import get_session
from app.main import app
from app.models import Base, PriceHistory, TrackedPlayer, User
from app.routers import user as user_router


@pytest.fixture(autouse=True)
def stub_initial_player_refresh(monkeypatch):
    async def _noop_initialize_player_market_state(request, session, player):
        return None

    monkeypatch.setattr(
        user_router,
        "_initialize_player_market_state",
        _noop_initialize_player_market_state,
    )


# -- Config validation tests --------------------------------------------------


def test_config_requires_riot_key_when_demo_disabled():
    with pytest.raises(ValueError, match="NASHORDAQ_RIOT_API_KEY is required"):
        Settings(
            demo_mode_enabled=False,
            riot_api_key="",
            riot_api_base_url="https://europe.api.riotgames.com",
            riot_api_region_url="https://euw1.api.riotgames.com",
        )


def test_config_allows_empty_riot_key_when_demo_enabled():
    s = Settings(
        demo_mode_enabled=True,
        riot_api_key="",
        riot_api_base_url="https://europe.api.riotgames.com",
        riot_api_region_url="https://euw1.api.riotgames.com",
    )
    assert s.demo_mode_enabled is True
    assert s.riot_api_key == ""


# -- Fixtures ------------------------------------------------------------------


@pytest.fixture
async def demo_db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def demo_session_factory(demo_db_engine):
    return async_sessionmaker(
        demo_db_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest.fixture
async def demo_client(demo_db_engine, demo_session_factory, monkeypatch):
    """Client with demo mode enabled and NO auth headers."""
    monkeypatch.setattr(settings, "demo_mode_enabled", True)

    async def override_get_session():
        async with demo_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.state.http_client = httpx.AsyncClient()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await app.state.http_client.aclose()
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_client_with_demo(demo_db_engine, demo_session_factory, monkeypatch):
    """Client with demo mode enabled AND proxy auth headers (non-demo user)."""
    monkeypatch.setattr(settings, "demo_mode_enabled", True)

    async def override_get_session():
        async with demo_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.state.http_client = httpx.AsyncClient()
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={
            "Remote-User": "realuser",
            "Remote-Email": "realuser@test.dev",
            "Remote-Name": "Real User",
        },
    ) as ac:
        yield ac
    await app.state.http_client.aclose()
    app.dependency_overrides.clear()


@pytest.fixture
async def demo_tradable_player(demo_session_factory):
    """Create a tradable player in the demo DB."""
    async with demo_session_factory() as session:
        player = TrackedPlayer(
            game_name="DemoPlayer",
            tag_line="EUW",
            display_name="Demo Player",
            current_price=25.0,
            lp_abs=1500,
            previous_lp_abs=1400,
            last_updated=datetime.now(UTC),
        )
        session.add(player)
        await session.commit()
        await session.refresh(player)
        return player


# -- Demo user creation and resume tests --------------------------------------


async def test_demo_user_created_when_no_auth_headers(demo_client):
    resp = await demo_client.get("/api/user/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_demo"] is True
    assert data["onboarding_complete"] is True
    assert data["balance"] == settings.starting_balance


async def test_demo_user_resume_via_cookie(demo_client, demo_session_factory):
    # First request creates the demo user
    resp1 = await demo_client.get("/api/user/me")
    assert resp1.status_code == 200
    user_id_1 = resp1.json()["id"]

    # Find the demo user's token from the DB
    async with demo_session_factory() as session:
        result = await session.execute(select(User).where(User.id == user_id_1))
        user = result.scalar_one()
        # username is "demo_{token}"
        token = user.username.removeprefix("demo_")

    # Second request with the cookie should return same user
    demo_client.cookies.set("nashordaq_demo_session", token)
    resp2 = await demo_client.get("/api/user/me")
    assert resp2.status_code == 200
    assert resp2.json()["id"] == user_id_1


# -- Demo trade does NOT change TrackedPlayer price ----------------------------


async def test_demo_buy_does_not_change_player_price(
    demo_client, demo_tradable_player, demo_session_factory
):
    me_resp = await demo_client.get("/api/user/me")
    assert me_resp.status_code == 200

    original_price = demo_tradable_player.current_price

    resp = await demo_client.post(
        "/api/orders",
        json={
            "player_id": demo_tradable_player.id,
            "side": "BUY",
            "quantity": 5,
        },
    )
    assert resp.status_code == 201

    async with demo_session_factory() as session:
        result = await session.execute(
            select(TrackedPlayer).where(TrackedPlayer.id == demo_tradable_player.id)
        )
        player = result.scalar_one()
        assert player.current_price == original_price


# -- Gamba returns 403 for demo users -----------------------------------------


async def test_gamba_returns_403_for_demo_user(
    demo_client, demo_tradable_player, monkeypatch
):
    monkeypatch.setattr(settings, "gamba_enabled", True)

    me_resp = await demo_client.get("/api/user/me")
    assert me_resp.status_code == 200

    resp = await demo_client.post(
        "/api/gamba",
        json={"cash_amount": 50.0},
    )
    assert resp.status_code == 403
    assert "demo" in resp.json()["detail"].lower()


# -- Bank returns 403 for demo users ------------------------------------------


async def test_bank_returns_403_for_demo_user(demo_client):
    me_resp = await demo_client.get("/api/user/me")
    assert me_resp.status_code == 200

    resp = await demo_client.get("/api/bank")
    assert resp.status_code == 403
    assert "demo" in resp.json()["detail"].lower()


# -- Poro returns disabled state for demo users --------------------------------


async def test_poro_returns_disabled_for_demo_user(demo_client, monkeypatch):
    monkeypatch.setattr(settings, "poro_enabled", True)

    me_resp = await demo_client.get("/api/user/me")
    assert me_resp.status_code == 200

    resp = await demo_client.get("/api/poro")
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is False


# -- Onboarding blocked for demo users ----------------------------------------


async def test_onboarding_blocked_for_demo_user(demo_client):
    me_resp = await demo_client.get("/api/user/me")
    assert me_resp.status_code == 200

    resp = await demo_client.post(
        "/api/user/onboarding",
        json={"game_name": "DemoSummoner", "tag_line": "EUW"},
    )
    assert resp.status_code == 403
    assert "demo" in resp.json()["detail"].lower()


# -- Demo nickname endpoint ----------------------------------------------------


async def test_demo_nickname_works_for_demo_user(demo_client):
    me_resp = await demo_client.get("/api/user/me")
    assert me_resp.status_code == 200

    resp = await demo_client.post(
        "/api/user/demo-nickname",
        json={"display_name": "CoolTrader"},
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "CoolTrader"


async def test_demo_nickname_fails_for_non_demo_user(auth_client_with_demo):
    me_resp = await auth_client_with_demo.get("/api/user/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["is_demo"] is False

    resp = await auth_client_with_demo.post(
        "/api/user/demo-nickname",
        json={"display_name": "CoolTrader"},
    )
    assert resp.status_code == 403
    assert "demo" in resp.json()["detail"].lower()


# -- Simulated market tick -----------------------------------------------------


async def test_demo_market_tick_updates_prices_and_creates_history(
    demo_db_engine, monkeypatch
):
    """Call demo_market_tick_job directly and verify it updates player prices."""
    from app.scheduler import demo_market_tick_job

    session_factory = async_sessionmaker(
        demo_db_engine, class_=AsyncSession, expire_on_commit=False
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
