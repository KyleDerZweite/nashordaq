from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.scheduler as scheduler_module
from app.models import (
    BankLedgerEntry,
    PlayingIncomeEntry,
    PlayingIncomeMatchResult,
    PriceHistory,
    TrackedPlayer,
    User,
    UserWealthSnapshot,
)
from app.riot import MatchSummary, PlayerNotFoundError, RankData


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

    async def fake_get_recent_match_ids(**_: object) -> list[str]:
        return []

    monkeypatch.setattr(
        scheduler_module,
        "get_recent_match_ids",
        fake_get_recent_match_ids,
    )
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


@pytest.mark.asyncio
async def test_market_update_job_accrues_due_bank_interest(db_engine, monkeypatch):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    due_time = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="DebtPlayer",
            tag_line="EUW",
            display_name="Debt Player",
            puuid="debt-puuid",
            summoner_id="debt-summoner",
            current_price=25.0,
            lp_abs=1500,
            previous_lp_abs=1500,
            streak=0,
            gamma_factor=1.0,
            last_updated=due_time,
        )
        user = User(
            username="debt-user",
            balance=1250.0,
            debt_principal=250.0,
            debt_accrued_interest=0.0,
            debt_last_accrued_at=due_time - timedelta(hours=120),
            debt_next_accrual_at=due_time,
        )
        session.add_all([player, user])
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="debt-puuid",
            summoner_id="debt-summoner",
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

    async def fake_get_recent_match_ids(**_: object) -> list[str]:
        return []

    monkeypatch.setattr(
        scheduler_module,
        "get_recent_match_ids",
        fake_get_recent_match_ids,
    )
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
        user = await session.scalar(select(User).where(User.username == "debt-user"))
        entry = await session.scalar(select(BankLedgerEntry))

    assert user is not None
    assert entry is not None
    assert user.debt_principal == pytest.approx(250.0)
    assert user.debt_accrued_interest == pytest.approx(5.0)
    assert entry.amount == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_market_update_job_uses_rescue_interest_rate_at_five_hundred_debt(
    db_engine, monkeypatch
):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    due_time = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="TierDebtPlayer",
            tag_line="EUW",
            display_name="Tier Debt Player",
            puuid="tier-debt-puuid",
            summoner_id="tier-debt-summoner",
            current_price=25.0,
            lp_abs=1500,
            previous_lp_abs=1500,
            streak=0,
            gamma_factor=1.0,
            last_updated=due_time,
        )
        user = User(
            username="tier-debt-user",
            balance=1250.0,
            debt_principal=500.0,
            debt_accrued_interest=0.0,
            debt_last_accrued_at=due_time - timedelta(hours=120),
            debt_next_accrual_at=due_time,
        )
        session.add_all([player, user])
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="tier-debt-puuid",
            summoner_id="tier-debt-summoner",
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

    async def fake_get_recent_match_ids(**_: object) -> list[str]:
        return []

    monkeypatch.setattr(
        scheduler_module,
        "get_recent_match_ids",
        fake_get_recent_match_ids,
    )
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
        user = await session.scalar(
            select(User).where(User.username == "tier-debt-user")
        )
        entry = await session.scalar(select(BankLedgerEntry))

    assert user is not None
    assert entry is not None
    assert user.debt_principal == pytest.approx(500.0)
    assert user.debt_accrued_interest == pytest.approx(10.0)
    assert entry.amount == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_market_update_job_applies_playing_income_once_per_new_match(
    db_engine, monkeypatch
):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="IncomePlayer",
            tag_line="EUW",
            display_name="Income Player",
            puuid="income-puuid",
            summoner_id="income-summoner",
            current_price=50.0,
            lp_abs=1500,
            previous_lp_abs=1500,
            streak=0,
            gamma_factor=1.0,
            last_updated=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
            last_playing_income_match_id="EUW1_100",
        )
        session.add(player)
        await session.flush()
        user = User(
            username="income-user",
            balance=1000.0,
            linked_player_id=player.id,
        )
        session.add(user)
        await session.flush()
        session.add(
            PlayingIncomeEntry(
                user_id=user.id,
                player_id=player.id,
                match_id="EUW1_100",
                match_result=PlayingIncomeMatchResult.WIN,
                match_duration_seconds=1800,
                match_completed_at=datetime(2024, 3, 9, 16, 0, tzinfo=UTC),
                share_price=50.0,
                base_rate=0.01,
                outcome_multiplier=1.0,
                amount=0.5,
            )
        )
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="income-puuid",
            summoner_id="income-summoner",
            tier="GOLD",
            rank="I",
            league_points=0,
            wins=10,
            losses=10,
            hot_streak=False,
            veteran=False,
            inactive=False,
            fresh_blood=False,
        )

    async def fake_get_recent_match_ids(**_: object) -> list[str]:
        return ["EUW1_102", "EUW1_101", "EUW1_100"]

    async def fake_get_match_summary(**kwargs: object) -> MatchSummary:
        match_id = str(kwargs["match_id"])
        summaries = {
            "EUW1_101": MatchSummary(
                match_id="EUW1_101",
                queue_id=420,
                win=False,
                game_duration_seconds=1800,
                game_end_timestamp=1_710_000_100_000,
            ),
            "EUW1_102": MatchSummary(
                match_id="EUW1_102",
                queue_id=420,
                win=True,
                game_duration_seconds=2100,
                game_end_timestamp=1_710_000_200_000,
            ),
        }
        return summaries[match_id]

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank", fake_get_rank)
    monkeypatch.setattr(
        scheduler_module.settings,
        "playing_income_start_date",
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    monkeypatch.setattr(
        scheduler_module,
        "get_recent_match_ids",
        fake_get_recent_match_ids,
    )
    monkeypatch.setattr(
        scheduler_module,
        "get_match_summary",
        fake_get_match_summary,
    )
    monkeypatch.setattr(
        scheduler_module,
        "_app",
        SimpleNamespace(state=SimpleNamespace(http_client=http_client)),
    )
    monkeypatch.setattr(scheduler_module, "_last_market_update_at", None)

    try:
        await scheduler_module.market_update_job()
        monkeypatch.setattr(scheduler_module, "_last_market_update_at", None)
        await scheduler_module.market_update_job()
    finally:
        await http_client.aclose()

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.username == "income-user"))
        entries = (
            (
                await session.execute(
                    select(PlayingIncomeEntry).order_by(
                        PlayingIncomeEntry.match_completed_at.asc()
                    )
                )
            )
            .scalars()
            .all()
        )
        player = await session.scalar(
            select(TrackedPlayer).where(TrackedPlayer.game_name == "IncomePlayer")
        )

    assert user is not None
    assert player is not None
    assert user.balance == pytest.approx(1000.75)
    assert [entry.match_id for entry in entries] == ["EUW1_100", "EUW1_101", "EUW1_102"]
    assert entries[1].match_result == PlayingIncomeMatchResult.LOSS
    assert entries[1].amount == pytest.approx(0.25)
    assert entries[1].base_rate == pytest.approx(0.0125)
    assert entries[2].match_result == PlayingIncomeMatchResult.WIN
    assert entries[2].amount == pytest.approx(0.5)
    assert entries[2].share_price == pytest.approx(50.0)
    assert player.last_playing_income_match_id == "EUW1_102"


@pytest.mark.asyncio
async def test_market_update_job_backfills_playing_income_from_start_date(
    db_engine, monkeypatch
):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    configured_start = datetime(2024, 3, 1, tzinfo=UTC)

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="BackfillPlayer",
            tag_line="EUW",
            display_name="Backfill Player",
            puuid="backfill-puuid",
            summoner_id="backfill-summoner",
            current_price=50.0,
            lp_abs=1500,
            previous_lp_abs=1500,
            streak=0,
            gamma_factor=1.0,
            last_updated=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
            last_playing_income_match_id="EUW1_299",
        )
        session.add(player)
        await session.flush()
        session.add(
            User(
                username="backfill-user",
                balance=1000.0,
                linked_player_id=player.id,
            )
        )
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="backfill-puuid",
            summoner_id="backfill-summoner",
            tier="GOLD",
            rank="I",
            league_points=0,
            wins=10,
            losses=10,
            hot_streak=False,
            veteran=False,
            inactive=False,
            fresh_blood=False,
        )

    match_id_calls: list[dict[str, object]] = []

    async def fake_get_recent_match_ids(**kwargs: object) -> list[str]:
        match_id_calls.append(dict(kwargs))
        assert kwargs["start_time"] == configured_start
        if kwargs["start"] == 0:
            return ["EUW1_302", "EUW1_301"]
        if kwargs["start"] == 2:
            return ["EUW1_300"]
        return []

    async def fake_get_match_summary(**kwargs: object) -> MatchSummary:
        match_id = str(kwargs["match_id"])
        summaries = {
            "EUW1_300": MatchSummary(
                match_id="EUW1_300",
                queue_id=420,
                win=True,
                game_duration_seconds=2200,
                game_end_timestamp=1_710_000_100_000,
            ),
            "EUW1_301": MatchSummary(
                match_id="EUW1_301",
                queue_id=420,
                win=False,
                game_duration_seconds=1800,
                game_end_timestamp=1_710_000_200_000,
            ),
            "EUW1_302": MatchSummary(
                match_id="EUW1_302",
                queue_id=420,
                win=True,
                game_duration_seconds=2400,
                game_end_timestamp=1_710_000_300_000,
            ),
        }
        return summaries[match_id]

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank", fake_get_rank)
    monkeypatch.setattr(
        scheduler_module.settings,
        "playing_income_start_date",
        configured_start,
    )
    monkeypatch.setattr(
        scheduler_module.settings,
        "playing_income_recent_match_count",
        2,
    )
    monkeypatch.setattr(
        scheduler_module,
        "get_recent_match_ids",
        fake_get_recent_match_ids,
    )
    monkeypatch.setattr(
        scheduler_module,
        "get_match_summary",
        fake_get_match_summary,
    )
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
        user = await session.scalar(
            select(User).where(User.username == "backfill-user")
        )
        entries = (
            (
                await session.execute(
                    select(PlayingIncomeEntry).order_by(
                        PlayingIncomeEntry.match_completed_at.asc()
                    )
                )
            )
            .scalars()
            .all()
        )
        player = await session.scalar(
            select(TrackedPlayer).where(TrackedPlayer.game_name == "BackfillPlayer")
        )

    assert user is not None
    assert player is not None
    assert user.balance == pytest.approx(1001.25)
    assert [entry.match_id for entry in entries] == ["EUW1_300", "EUW1_301", "EUW1_302"]
    assert [entry.amount for entry in entries] == pytest.approx([0.5, 0.25, 0.5])
    assert player.last_playing_income_match_id == "EUW1_302"
    assert [call["start"] for call in match_id_calls] == [0, 2]


@pytest.mark.asyncio
async def test_market_update_job_applies_minimum_playing_income_amount(
    db_engine, monkeypatch
):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="MinimumIncomePlayer",
            tag_line="EUW",
            display_name="Minimum Income Player",
            puuid="minimum-puuid",
            summoner_id="minimum-summoner",
            current_price=8.0,
            lp_abs=1500,
            previous_lp_abs=1500,
            streak=0,
            gamma_factor=1.0,
            last_updated=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
        )
        session.add(player)
        await session.flush()
        session.add(
            User(
                username="minimum-income-user",
                balance=1000.0,
                linked_player_id=player.id,
            )
        )
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="minimum-puuid",
            summoner_id="minimum-summoner",
            tier="GOLD",
            rank="I",
            league_points=0,
            wins=10,
            losses=10,
            hot_streak=False,
            veteran=False,
            inactive=False,
            fresh_blood=False,
        )

    async def fake_get_recent_match_ids(**_: object) -> list[str]:
        return ["EUW1_900"]

    async def fake_get_match_summary(**_: object) -> MatchSummary:
        return MatchSummary(
            match_id="EUW1_900",
            queue_id=420,
            win=False,
            game_duration_seconds=1800,
            game_end_timestamp=1_773_187_200_000,
        )

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank", fake_get_rank)
    monkeypatch.setattr(
        scheduler_module.settings,
        "playing_income_start_date",
        datetime(2026, 3, 1, tzinfo=UTC),
    )
    monkeypatch.setattr(
        scheduler_module,
        "get_recent_match_ids",
        fake_get_recent_match_ids,
    )
    monkeypatch.setattr(
        scheduler_module,
        "get_match_summary",
        fake_get_match_summary,
    )
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
        user = await session.scalar(
            select(User).where(User.username == "minimum-income-user")
        )
        entry = await session.scalar(
            select(PlayingIncomeEntry).where(PlayingIncomeEntry.match_id == "EUW1_900")
        )

    assert user is not None
    assert entry is not None
    assert user.balance == pytest.approx(1000.12)
    assert entry.amount == pytest.approx(0.12)


@pytest.mark.asyncio
async def test_market_update_job_reduces_playing_income_after_three_games_in_day(
    db_engine, monkeypatch
):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    match_day = datetime(2026, 3, 9, 0, 0, tzinfo=UTC)

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="DailyIncomePlayer",
            tag_line="EUW",
            display_name="Daily Income Player",
            puuid="daily-income-puuid",
            summoner_id="daily-income-summoner",
            current_price=50.0,
            lp_abs=1500,
            previous_lp_abs=1500,
            streak=0,
            gamma_factor=1.0,
            last_updated=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
            last_playing_income_match_id="EUW1_703",
        )
        session.add(player)
        await session.flush()
        user = User(
            username="daily-income-user",
            balance=1000.0,
            linked_player_id=player.id,
        )
        session.add(user)
        await session.flush()
        session.add_all(
            [
                PlayingIncomeEntry(
                    user_id=user.id,
                    player_id=player.id,
                    match_id="EUW1_701",
                    match_result=PlayingIncomeMatchResult.WIN,
                    match_duration_seconds=1800,
                    match_completed_at=match_day + timedelta(hours=1),
                    share_price=50.0,
                    base_rate=0.0125,
                    outcome_multiplier=1.0,
                    amount=0.5,
                ),
                PlayingIncomeEntry(
                    user_id=user.id,
                    player_id=player.id,
                    match_id="EUW1_702",
                    match_result=PlayingIncomeMatchResult.WIN,
                    match_duration_seconds=1800,
                    match_completed_at=match_day + timedelta(hours=2),
                    share_price=50.0,
                    base_rate=0.0125,
                    outcome_multiplier=1.0,
                    amount=0.5,
                ),
                PlayingIncomeEntry(
                    user_id=user.id,
                    player_id=player.id,
                    match_id="EUW1_703",
                    match_result=PlayingIncomeMatchResult.WIN,
                    match_duration_seconds=1800,
                    match_completed_at=match_day + timedelta(hours=3),
                    share_price=50.0,
                    base_rate=0.0125,
                    outcome_multiplier=1.0,
                    amount=0.5,
                ),
            ]
        )
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="daily-income-puuid",
            summoner_id="daily-income-summoner",
            tier="GOLD",
            rank="I",
            league_points=0,
            wins=10,
            losses=10,
            hot_streak=False,
            veteran=False,
            inactive=False,
            fresh_blood=False,
        )

    async def fake_get_recent_match_ids(**_: object) -> list[str]:
        return ["EUW1_705", "EUW1_704", "EUW1_703"]

    async def fake_get_match_summary(**kwargs: object) -> MatchSummary:
        match_id = str(kwargs["match_id"])
        summaries = {
            "EUW1_704": MatchSummary(
                match_id="EUW1_704",
                queue_id=420,
                win=True,
                game_duration_seconds=1800,
                game_end_timestamp=1_773_082_800_000,
            ),
            "EUW1_705": MatchSummary(
                match_id="EUW1_705",
                queue_id=420,
                win=False,
                game_duration_seconds=1800,
                game_end_timestamp=1_773_086_400_000,
            ),
        }
        return summaries[match_id]

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank", fake_get_rank)
    monkeypatch.setattr(
        scheduler_module.settings,
        "playing_income_start_date",
        datetime(2026, 3, 1, tzinfo=UTC),
    )
    monkeypatch.setattr(
        scheduler_module,
        "get_recent_match_ids",
        fake_get_recent_match_ids,
    )
    monkeypatch.setattr(
        scheduler_module,
        "get_match_summary",
        fake_get_match_summary,
    )
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
        user = await session.scalar(
            select(User).where(User.username == "daily-income-user")
        )
        assert user is not None
        entries = (
            (
                await session.execute(
                    select(PlayingIncomeEntry)
                    .where(PlayingIncomeEntry.user_id == user.id)
                    .order_by(PlayingIncomeEntry.match_completed_at.asc())
                )
            )
            .scalars()
            .all()
        )

    assert user.balance == pytest.approx(1000.54)
    assert [entry.match_id for entry in entries[-2:]] == ["EUW1_704", "EUW1_705"]
    assert entries[-2].amount == pytest.approx(0.37)
    assert entries[-1].amount == pytest.approx(0.17)


@pytest.mark.asyncio
async def test_market_update_job_falls_back_when_start_time_query_is_rejected(
    db_engine, monkeypatch
):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="FallbackIncomePlayer",
            tag_line="EUW",
            display_name="Fallback Income Player",
            puuid="fallback-puuid",
            summoner_id="fallback-summoner",
            current_price=20.0,
            lp_abs=1500,
            previous_lp_abs=1500,
            streak=0,
            gamma_factor=1.0,
            last_updated=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
        )
        session.add(player)
        await session.flush()
        session.add(
            User(
                username="fallback-income-user",
                balance=1000.0,
                linked_player_id=player.id,
            )
        )
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="fallback-puuid",
            summoner_id="fallback-summoner",
            tier="GOLD",
            rank="I",
            league_points=0,
            wins=10,
            losses=10,
            hot_streak=False,
            veteran=False,
            inactive=False,
            fresh_blood=False,
        )

    request_calls: list[dict[str, object]] = []

    async def fake_get_recent_match_ids(**kwargs: object) -> list[str]:
        request_calls.append(dict(kwargs))
        if kwargs["start_time"] is not None:
            request = httpx.Request("GET", "https://example.test/matches")
            response = httpx.Response(400, request=request)
            raise httpx.HTTPStatusError(
                "bad request",
                request=request,
                response=response,
            )
        if kwargs["start"] == 0:
            return ["EUW1_950", "EUW1_949"]
        return []

    async def fake_get_match_summary(**kwargs: object) -> MatchSummary:
        match_id = str(kwargs["match_id"])
        summaries = {
            "EUW1_949": MatchSummary(
                match_id="EUW1_949",
                queue_id=420,
                win=False,
                game_duration_seconds=1800,
                game_end_timestamp=1_773_187_200_000,
            ),
            "EUW1_950": MatchSummary(
                match_id="EUW1_950",
                queue_id=420,
                win=True,
                game_duration_seconds=1800,
                game_end_timestamp=1_773_190_800_000,
            ),
        }
        return summaries[match_id]

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank", fake_get_rank)
    monkeypatch.setattr(
        scheduler_module.settings,
        "playing_income_start_date",
        datetime(2026, 3, 10, tzinfo=UTC),
    )
    monkeypatch.setattr(
        scheduler_module,
        "get_recent_match_ids",
        fake_get_recent_match_ids,
    )
    monkeypatch.setattr(
        scheduler_module,
        "get_match_summary",
        fake_get_match_summary,
    )
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
        user = await session.scalar(
            select(User).where(User.username == "fallback-income-user")
        )
        entries = (
            (
                await session.execute(
                    select(PlayingIncomeEntry).order_by(
                        PlayingIncomeEntry.match_completed_at.asc()
                    )
                )
            )
            .scalars()
            .all()
        )

    assert user is not None
    assert user.balance == pytest.approx(1000.43)
    assert [entry.match_id for entry in entries] == ["EUW1_949", "EUW1_950"]
    assert [entry.amount for entry in entries] == pytest.approx([0.14, 0.29])
    assert request_calls[0]["start_time"] is not None
    assert request_calls[1]["start_time"] is None


@pytest.mark.asyncio
async def test_market_update_job_refreshes_stale_puuid_before_match_history(
    db_engine, monkeypatch
):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="RefreshPuuidPlayer",
            tag_line="EUW",
            display_name="Refresh Puuid Player",
            puuid="stale-puuid",
            summoner_id="stale-summoner",
            current_price=20.0,
            lp_abs=1500,
            previous_lp_abs=1500,
            streak=0,
            gamma_factor=1.0,
            last_updated=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
        )
        session.add(player)
        await session.flush()
        session.add(
            User(
                username="refresh-puuid-user",
                balance=1000.0,
                linked_player_id=player.id,
            )
        )
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="fresh-puuid",
            summoner_id="fresh-summoner",
            tier="GOLD",
            rank="I",
            league_points=0,
            wins=10,
            losses=10,
            hot_streak=False,
            veteran=False,
            inactive=False,
            fresh_blood=False,
        )

    request_puuids: list[str] = []

    async def fake_get_recent_match_ids(**kwargs: object) -> list[str]:
        request_puuids.append(str(kwargs["puuid"]))
        return []

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank", fake_get_rank)
    monkeypatch.setattr(
        scheduler_module,
        "get_recent_match_ids",
        fake_get_recent_match_ids,
    )
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
        player = await session.scalar(
            select(TrackedPlayer).where(TrackedPlayer.game_name == "RefreshPuuidPlayer")
        )

    assert player is not None
    assert player.puuid == "fresh-puuid"
    assert player.summoner_id == "fresh-summoner"
    assert request_puuids == ["fresh-puuid"]


@pytest.mark.asyncio
async def test_market_update_job_skips_malformed_match_summary_and_continues(
    db_engine, monkeypatch
):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="SkipBrokenMatchPlayer",
            tag_line="EUW",
            display_name="Skip Broken Match Player",
            puuid="skip-broken-puuid",
            summoner_id="skip-broken-summoner",
            current_price=20.0,
            lp_abs=1500,
            previous_lp_abs=1500,
            streak=0,
            gamma_factor=1.0,
            last_updated=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
        )
        session.add(player)
        await session.flush()
        session.add(
            User(
                username="skip-broken-user",
                balance=1000.0,
                linked_player_id=player.id,
            )
        )
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="skip-broken-puuid",
            summoner_id="skip-broken-summoner",
            tier="GOLD",
            rank="I",
            league_points=0,
            wins=10,
            losses=10,
            hot_streak=False,
            veteran=False,
            inactive=False,
            fresh_blood=False,
        )

    async def fake_get_recent_match_ids(**_: object) -> list[str]:
        return ["EUW1_1002", "EUW1_1001", "EUW1_1000"]

    async def fake_get_match_summary(**kwargs: object) -> MatchSummary:
        match_id = str(kwargs["match_id"])
        if match_id == "EUW1_1001":
            raise PlayerNotFoundError("missing participant")
        summaries = {
            "EUW1_1000": MatchSummary(
                match_id="EUW1_1000",
                queue_id=420,
                win=False,
                game_duration_seconds=1800,
                game_end_timestamp=1_773_187_200_000,
            ),
            "EUW1_1002": MatchSummary(
                match_id="EUW1_1002",
                queue_id=420,
                win=True,
                game_duration_seconds=1800,
                game_end_timestamp=1_773_194_400_000,
            ),
        }
        return summaries[match_id]

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank", fake_get_rank)
    monkeypatch.setattr(
        scheduler_module.settings,
        "playing_income_start_date",
        datetime(2026, 3, 10, tzinfo=UTC),
    )
    monkeypatch.setattr(
        scheduler_module,
        "get_recent_match_ids",
        fake_get_recent_match_ids,
    )
    monkeypatch.setattr(
        scheduler_module,
        "get_match_summary",
        fake_get_match_summary,
    )
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
        user = await session.scalar(
            select(User).where(User.username == "skip-broken-user")
        )
        entries = (
            (
                await session.execute(
                    select(PlayingIncomeEntry).order_by(
                        PlayingIncomeEntry.match_completed_at.asc()
                    )
                )
            )
            .scalars()
            .all()
        )

    assert user is not None
    assert user.balance == pytest.approx(1000.43)
    assert [entry.match_id for entry in entries] == ["EUW1_1000", "EUW1_1002"]
    assert [entry.amount for entry in entries] == pytest.approx([0.14, 0.29])


@pytest.mark.asyncio
async def test_market_update_job_skips_short_match_playing_income(
    db_engine, monkeypatch
):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="ShortMatchPlayer",
            tag_line="EUW",
            display_name="Short Match Player",
            puuid="short-puuid",
            summoner_id="short-summoner",
            current_price=40.0,
            lp_abs=1500,
            previous_lp_abs=1500,
            streak=0,
            gamma_factor=1.0,
            last_updated=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
            last_playing_income_match_id="EUW1_200",
        )
        session.add(player)
        await session.flush()
        session.add(
            User(
                username="short-user",
                balance=1000.0,
                linked_player_id=player.id,
            )
        )
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="short-puuid",
            summoner_id="short-summoner",
            tier="GOLD",
            rank="I",
            league_points=0,
            wins=10,
            losses=10,
            hot_streak=False,
            veteran=False,
            inactive=False,
            fresh_blood=False,
        )

    async def fake_get_recent_match_ids(**_: object) -> list[str]:
        return ["EUW1_201", "EUW1_200"]

    async def fake_get_match_summary(**_: object) -> MatchSummary:
        return MatchSummary(
            match_id="EUW1_201",
            queue_id=420,
            win=True,
            game_duration_seconds=600,
            game_end_timestamp=1_710_000_300_000,
        )

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank", fake_get_rank)
    monkeypatch.setattr(
        scheduler_module,
        "get_recent_match_ids",
        fake_get_recent_match_ids,
    )
    monkeypatch.setattr(
        scheduler_module,
        "get_match_summary",
        fake_get_match_summary,
    )
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
        user = await session.scalar(select(User).where(User.username == "short-user"))
        entry_count = await session.scalar(
            select(func.count()).select_from(PlayingIncomeEntry)
        )
        player = await session.scalar(
            select(TrackedPlayer).where(TrackedPlayer.game_name == "ShortMatchPlayer")
        )

    assert user is not None
    assert player is not None
    assert user.balance == pytest.approx(1000.0)
    assert entry_count == 0
    assert player.last_playing_income_match_id == "EUW1_201"


@pytest.mark.asyncio
async def test_market_update_job_records_wealth_snapshots(db_engine, monkeypatch):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="SnapshotPlayer",
            tag_line="EUW",
            display_name="Snapshot Player",
            puuid="snapshot-puuid",
            summoner_id="snapshot-summoner",
            current_price=25.0,
            lp_abs=1500,
            previous_lp_abs=1500,
            streak=0,
            gamma_factor=1.0,
            last_updated=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
        )
        session.add(player)
        await session.flush()
        session.add(
            User(
                username="snapshot-user",
                balance=900.0,
                linked_player_id=player.id,
            )
        )
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="snapshot-puuid",
            summoner_id="snapshot-summoner",
            tier="GOLD",
            rank="I",
            league_points=0,
            wins=10,
            losses=10,
            hot_streak=False,
            veteran=False,
            inactive=False,
            fresh_blood=False,
        )

    async def fake_get_recent_match_ids(**_: object) -> list[str]:
        return []

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank", fake_get_rank)
    monkeypatch.setattr(
        scheduler_module,
        "get_recent_match_ids",
        fake_get_recent_match_ids,
    )
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
        snapshot_count = await session.scalar(
            select(func.count()).select_from(UserWealthSnapshot)
        )

    assert snapshot_count == 1
