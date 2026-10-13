import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime

os.environ.setdefault("NASHORDAQ_RIOT_API_KEY", "test-api-key")
os.environ.setdefault("NASHORDAQ_RIOT_API_BASE_URL", "https://europe.api.riotgames.com")
os.environ.setdefault("NASHORDAQ_RIOT_API_REGION_URL", "https://euw1.api.riotgames.com")

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import hash_password
from app.config import settings
from app.database import get_session
from app.main import app
from app.models import Base, TrackedPlayer, User
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


@pytest.fixture
async def client():
    app.state.http_client = httpx.AsyncClient()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await app.state.http_client.aclose()


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


TEST_PASSWORD = "fixture password for tests"
TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)


@pytest.fixture
async def account_client(db_engine):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.state.http_client = httpx.AsyncClient()

    @asynccontextmanager
    async def logged_in(
        username="testuser", *, is_admin=False, display_name="Test User"
    ):
        async with session_factory() as session:
            user = await session.scalar(select(User).where(User.username == username))
            if user is None:
                user = User(
                    username=username,
                    email=f"{username}@test.dev",
                    display_name=display_name,
                    balance=settings.starting_balance,
                    is_admin=is_admin,
                )
                session.add(user)
            user.password_hash = TEST_PASSWORD_HASH
            await session.commit()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Nashordaq-CSRF": "1", "Origin": "http://test"},
        ) as client:
            response = await client.post(
                "/api/auth/login",
                json={"username": username, "password": TEST_PASSWORD},
            )
            assert response.status_code == 200, response.text
            yield client

    yield logged_in
    await app.state.http_client.aclose()
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_client(account_client):
    async with account_client() as client:
        yield client


@pytest.fixture
async def admin_client(account_client):
    async with account_client(
        "operator", is_admin=True, display_name="Operator"
    ) as client:
        yield client


@pytest.fixture
async def second_client(account_client):
    async with account_client("seconduser", display_name="Second User") as client:
        yield client


@pytest.fixture
async def seeded_player(db_session):
    player = TrackedPlayer(
        game_name="TestPlayer",
        tag_line="EUW",
        display_name="Test Player",
        current_price=25.0,
        lp_abs=1500,
        previous_lp_abs=1400,
        last_updated=datetime.now(UTC),
    )
    db_session.add(player)
    await db_session.commit()
    await db_session.refresh(player)

    user_result = await db_session.execute(
        select(User).where(User.username == "testuser")
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        user = User(
            username="testuser",
            email="testuser@test.dev",
            display_name="Test User",
            balance=settings.starting_balance,
            linked_player_id=player.id,
        )
        db_session.add(user)
    else:
        user.linked_player_id = player.id
    await db_session.commit()

    return player


@pytest.fixture
async def tradable_player(db_session, seeded_player):
    del seeded_player

    player = TrackedPlayer(
        game_name="TradablePlayer",
        tag_line="EUW",
        display_name="Tradable Player",
        current_price=25.0,
        lp_abs=1500,
        previous_lp_abs=1400,
        last_updated=datetime.now(UTC),
    )
    db_session.add(player)
    await db_session.commit()
    await db_session.refresh(player)
    return player
