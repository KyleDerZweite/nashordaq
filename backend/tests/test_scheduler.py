from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.scheduler as scheduler_module
from app.models import (
    BankLedgerEntry,
    PlayerMatch,
    PlayerMatchLpSource,
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
            inactive=True,
        )

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)

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

    due_time = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=1)

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
            inactive=True,
        )

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)

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
async def test_market_update_job_learns_win_lp_average_and_passes_to_pricing(
    db_engine, monkeypatch
):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="AvgWinPlayer",
            tag_line="EUW",
            display_name="Avg Win Player",
            puuid="avg-win-puuid",
            summoner_id="avg-win-summoner",
            current_price=25.0,
            lp_abs=1500,
            previous_lp_abs=1500,
            streak=0,
            ranked_wins_snapshot=10,
            ranked_losses_snapshot=10,
        )
        session.add(player)
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="avg-win-puuid",
            summoner_id="avg-win-summoner",
            tier="GOLD",
            rank="I",
            league_points=60,
            wins=12,
            losses=10,
            hot_streak=False,
            inactive=False,
        )

    captured_kwargs: dict[str, float | None] = {}

    def fake_calculate_new_price(
        old_price: float,
        delta_lp: int,
        streak: int,
        *,
        avg_lp_loss_on_loss: float | None,
        avg_lp_gain_on_win: float | None,
    ) -> float:
        del delta_lp, streak
        captured_kwargs["avg_lp_loss_on_loss"] = avg_lp_loss_on_loss
        captured_kwargs["avg_lp_gain_on_win"] = avg_lp_gain_on_win
        return old_price + 5.0

    async def fake_get_recent_match_ids(**_: object) -> list[str]:
        return []

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)
    monkeypatch.setattr(
        scheduler_module,
        "get_recent_match_ids",
        fake_get_recent_match_ids,
    )
    monkeypatch.setattr(
        scheduler_module, "calculate_new_price", fake_calculate_new_price
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
            select(TrackedPlayer).where(TrackedPlayer.game_name == "AvgWinPlayer")
        )

    assert player is not None
    assert player.avg_lp_gain_on_win == pytest.approx(30.0)
    assert player.avg_lp_loss_on_loss is None
    assert player.ranked_wins_snapshot == 12
    assert player.ranked_losses_snapshot == 10
    assert captured_kwargs["avg_lp_gain_on_win"] == pytest.approx(30.0)
    assert captured_kwargs["avg_lp_loss_on_loss"] is None


@pytest.mark.asyncio
async def test_market_update_job_learns_loss_lp_average_with_ema(
    db_engine, monkeypatch
):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="AvgLossPlayer",
            tag_line="EUW",
            display_name="Avg Loss Player",
            puuid="avg-loss-puuid",
            summoner_id="avg-loss-summoner",
            current_price=25.0,
            lp_abs=1500,
            previous_lp_abs=1500,
            streak=0,
            ranked_wins_snapshot=12,
            ranked_losses_snapshot=10,
            avg_lp_gain_on_win=28.0,
            avg_lp_loss_on_loss=20.0,
        )
        session.add(player)
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="avg-loss-puuid",
            summoner_id="avg-loss-summoner",
            tier="GOLD",
            rank="I",
            league_points=-10,
            wins=12,
            losses=11,
            hot_streak=False,
            inactive=False,
        )

    captured_kwargs: dict[str, float | None] = {}

    def fake_calculate_new_price(
        old_price: float,
        delta_lp: int,
        streak: int,
        *,
        avg_lp_loss_on_loss: float | None,
        avg_lp_gain_on_win: float | None,
    ) -> float:
        del delta_lp, streak
        captured_kwargs["avg_lp_loss_on_loss"] = avg_lp_loss_on_loss
        captured_kwargs["avg_lp_gain_on_win"] = avg_lp_gain_on_win
        return old_price - 2.0

    async def fake_get_recent_match_ids(**_: object) -> list[str]:
        return []

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)
    monkeypatch.setattr(
        scheduler_module,
        "get_recent_match_ids",
        fake_get_recent_match_ids,
    )
    monkeypatch.setattr(
        scheduler_module, "calculate_new_price", fake_calculate_new_price
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
            select(TrackedPlayer).where(TrackedPlayer.game_name == "AvgLossPlayer")
        )

    # EMA update: 20.0 -> (1 - 0.35) * 20 + 0.35 * 10 = 16.5
    assert player is not None
    assert player.avg_lp_gain_on_win == pytest.approx(28.0)
    assert player.avg_lp_loss_on_loss == pytest.approx(16.5)
    assert player.ranked_wins_snapshot == 12
    assert player.ranked_losses_snapshot == 11
    assert captured_kwargs["avg_lp_gain_on_win"] == pytest.approx(28.0)
    assert captured_kwargs["avg_lp_loss_on_loss"] == pytest.approx(16.5)


@pytest.mark.asyncio
async def test_market_update_job_uses_rescue_interest_rate_at_five_hundred_debt(
    db_engine, monkeypatch
):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    due_time = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=1)

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
            inactive=True,
        )

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)

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
            inactive=False,
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
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)
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
    assert user.balance == pytest.approx(1001.50)
    assert [entry.match_id for entry in entries] == ["EUW1_100", "EUW1_101", "EUW1_102"]
    assert entries[1].match_result == PlayingIncomeMatchResult.LOSS
    assert entries[1].amount == pytest.approx(0.50)
    assert entries[1].base_rate == pytest.approx(0.01)
    assert entries[2].match_result == PlayingIncomeMatchResult.WIN
    assert entries[2].amount == pytest.approx(1.00)
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
            inactive=False,
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
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)
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
    assert user.balance == pytest.approx(1002.50)
    assert [entry.match_id for entry in entries] == ["EUW1_300", "EUW1_301", "EUW1_302"]
    assert [entry.amount for entry in entries] == pytest.approx([1.00, 0.50, 1.00])
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
            inactive=False,
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
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)
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
    assert user.balance == pytest.approx(1000.29)
    assert entry.amount == pytest.approx(0.29)


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
            inactive=False,
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
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)
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

    assert user.balance == pytest.approx(1001.24)
    assert [entry.match_id for entry in entries[-2:]] == ["EUW1_704", "EUW1_705"]
    assert entries[-2].amount == pytest.approx(0.83)
    assert entries[-1].amount == pytest.approx(0.41)


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
            inactive=False,
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
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)
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
    assert user.balance == pytest.approx(1001.05)
    assert [entry.match_id for entry in entries] == ["EUW1_949", "EUW1_950"]
    assert [entry.amount for entry in entries] == pytest.approx([0.35, 0.70])
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
            inactive=False,
        )

    request_puuids: list[str] = []

    async def fake_get_recent_match_ids(**kwargs: object) -> list[str]:
        request_puuids.append(str(kwargs["puuid"]))
        return []

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)
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
async def test_market_update_job_falls_back_on_400_puuid_error(db_engine, monkeypatch):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="StalePuuidPlayer",
            tag_line="EUW",
            display_name="Stale Puuid Player",
            puuid="stale-puuid-400",
            summoner_id="old-summoner",
            current_price=20.0,
            lp_abs=1500,
            previous_lp_abs=1500,
            streak=0,
            last_updated=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
        )
        session.add(player)
        await session.flush()
        session.add(
            User(
                username="stale-puuid-user",
                balance=1000.0,
                linked_player_id=player.id,
            )
        )
        await session.commit()

    call_sequence: list[str] = []

    async def fake_get_rank_by_puuid(**kwargs: object) -> RankData:
        call_sequence.append("get_rank_by_puuid")
        request = httpx.Request(
            "GET", "https://euw1.api.riotgames.com/lol/league/v4/entries/by-puuid/stale"
        )
        response = httpx.Response(400, request=request)
        raise httpx.HTTPStatusError(
            "Client error '400 Bad Request'",
            request=request,
            response=response,
        )

    async def fake_get_rank(**kwargs: object) -> RankData:
        call_sequence.append("get_rank")
        return RankData(
            puuid="resolved-puuid",
            summoner_id="resolved-summoner",
            tier="GOLD",
            rank="I",
            league_points=0,
            wins=10,
            losses=10,
            hot_streak=False,
            inactive=False,
        )

    async def fake_get_recent_match_ids(**kwargs: object) -> list[str]:
        return []

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank_by_puuid)
    monkeypatch.setattr(scheduler_module, "get_rank", fake_get_rank)
    monkeypatch.setattr(
        scheduler_module, "get_recent_match_ids", fake_get_recent_match_ids
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

    assert call_sequence == ["get_rank_by_puuid", "get_rank"]

    async with session_factory() as session:
        player = await session.scalar(
            select(TrackedPlayer).where(TrackedPlayer.game_name == "StalePuuidPlayer")
        )

    assert player is not None
    assert player.puuid == "resolved-puuid"
    assert player.summoner_id == "resolved-summoner"


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
            inactive=False,
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
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)
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
    assert user.balance == pytest.approx(1001.05)
    assert [entry.match_id for entry in entries] == ["EUW1_1000", "EUW1_1002"]
    assert [entry.amount for entry in entries] == pytest.approx([0.35, 0.70])


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
            inactive=False,
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
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)
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
            inactive=False,
        )

    async def fake_get_recent_match_ids(**_: object) -> list[str]:
        return []

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)
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


@pytest.mark.asyncio
async def test_market_update_job_creates_player_match_for_single_game(
    db_engine, monkeypatch
):
    """When a single match is detected between LP polls, a PlayerMatch row is
    created with lp_delta_source=OBSERVED, and per-match pricing is applied."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="PerMatchPlayer",
            tag_line="EUW",
            display_name="Per Match Player",
            puuid="permatch-puuid",
            summoner_id="permatch-summoner",
            current_price=30.0,
            lp_abs=1500,
            previous_lp_abs=1480,
            streak=2,
            ranked_wins_snapshot=15,
            ranked_losses_snapshot=10,
            avg_lp_gain_on_win=22.0,
            avg_lp_loss_on_loss=18.0,
        )
        session.add(player)
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="permatch-puuid",
            summoner_id="permatch-summoner",
            tier="GOLD",
            rank="I",
            league_points=20,
            wins=16,
            losses=10,
            hot_streak=False,
            inactive=False,
        )

    async def fake_get_recent_match_ids(**_: object) -> list[str]:
        return ["EUW1_PM1"]

    async def fake_get_match_summary(**kwargs: object) -> MatchSummary:
        return MatchSummary(
            match_id="EUW1_PM1",
            queue_id=420,
            win=True,
            game_duration_seconds=1800,
            game_end_timestamp=1_710_000_100_000,
        )

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)
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
    finally:
        await http_client.aclose()

    async with session_factory() as session:
        player = await session.scalar(
            select(TrackedPlayer).where(TrackedPlayer.game_name == "PerMatchPlayer")
        )
        pm = await session.scalar(
            select(PlayerMatch).where(PlayerMatch.match_id == "EUW1_PM1")
        )
        price_history_count = await session.scalar(
            select(func.count()).select_from(PriceHistory)
        )

    assert player is not None
    assert pm is not None

    # LP delta: 1520 - 1500 = 20, single match -> OBSERVED
    assert pm.lp_delta == 20
    assert pm.lp_delta_source == PlayerMatchLpSource.OBSERVED
    assert pm.win is True
    assert pm.lp_before == 1500
    assert pm.lp_after == 1520
    assert pm.streak_before == 2
    assert pm.streak_after == 3
    assert pm.price_before == 30.0

    # Per-match pricing was applied
    assert player.current_price == pm.price_after
    assert player.lp_abs == 1520
    assert player.streak == 3
    assert price_history_count == 1


@pytest.mark.asyncio
async def test_market_update_job_creates_multiple_player_matches_for_multi_game(
    db_engine, monkeypatch
):
    """When two matches are detected, LP is split between them and two
    PlayerMatch rows are created with lp_delta_source=ESTIMATED."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="MultiMatchPlayer",
            tag_line="EUW",
            display_name="Multi Match Player",
            puuid="multimatch-puuid",
            summoner_id="multimatch-summoner",
            current_price=30.0,
            lp_abs=1500,
            previous_lp_abs=1460,
            streak=1,
            ranked_wins_snapshot=15,
            ranked_losses_snapshot=10,
        )
        session.add(player)
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="multimatch-puuid",
            summoner_id="multimatch-summoner",
            tier="GOLD",
            rank="I",
            league_points=40,
            wins=17,
            losses=10,
            hot_streak=False,
            inactive=False,
        )

    async def fake_get_recent_match_ids(**_: object) -> list[str]:
        return ["EUW1_MM2", "EUW1_MM1"]

    async def fake_get_match_summary(**kwargs: object) -> MatchSummary:
        match_id = str(kwargs["match_id"])
        summaries = {
            "EUW1_MM1": MatchSummary(
                match_id="EUW1_MM1",
                queue_id=420,
                win=True,
                game_duration_seconds=1800,
                game_end_timestamp=1_710_000_100_000,
            ),
            "EUW1_MM2": MatchSummary(
                match_id="EUW1_MM2",
                queue_id=420,
                win=True,
                game_duration_seconds=2000,
                game_end_timestamp=1_710_000_200_000,
            ),
        }
        return summaries[match_id]

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)
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
    finally:
        await http_client.aclose()

    async with session_factory() as session:
        player = await session.scalar(
            select(TrackedPlayer).where(TrackedPlayer.game_name == "MultiMatchPlayer")
        )
        matches = (
            (
                await session.execute(
                    select(PlayerMatch)
                    .where(PlayerMatch.player_id == player.id)
                    .order_by(PlayerMatch.completed_at.asc())
                )
            )
            .scalars()
            .all()
        )

    assert player is not None
    assert len(matches) == 2

    # Both wins, LP delta 40, split evenly: 20 each
    assert matches[0].match_id == "EUW1_MM1"
    assert matches[0].lp_delta == 20
    assert matches[0].lp_delta_source == PlayerMatchLpSource.ESTIMATED
    assert matches[0].win is True

    assert matches[1].match_id == "EUW1_MM2"
    assert matches[1].lp_delta == 20
    assert matches[1].lp_delta_source == PlayerMatchLpSource.ESTIMATED
    assert matches[1].win is True

    # Sequential pricing: second match builds on first
    assert matches[1].price_before == matches[0].price_after
    assert player.current_price == matches[1].price_after
    assert player.lp_abs == 1540


@pytest.mark.asyncio
async def test_market_update_job_falls_back_to_aggregate_when_no_matches(
    db_engine, monkeypatch
):
    """When LP changes but no ranked matches are detected (e.g., promotion
    adjustment), aggregate pricing is used as fallback."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        player = TrackedPlayer(
            game_name="AggregatePlayer",
            tag_line="EUW",
            display_name="Aggregate Player",
            puuid="aggregate-puuid",
            summoner_id="aggregate-summoner",
            current_price=30.0,
            lp_abs=1500,
            previous_lp_abs=1480,
            streak=2,
            ranked_wins_snapshot=15,
            ranked_losses_snapshot=10,
        )
        session.add(player)
        await session.commit()

    async def fake_get_rank(**_: object) -> RankData:
        return RankData(
            puuid="aggregate-puuid",
            summoner_id="aggregate-summoner",
            tier="GOLD",
            rank="II",
            league_points=0,
            wins=15,
            losses=10,
            hot_streak=False,
            inactive=False,
        )

    async def fake_get_recent_match_ids(**_: object) -> list[str]:
        return []

    http_client = httpx.AsyncClient()
    monkeypatch.setattr(scheduler_module, "SessionLocal", session_factory)
    monkeypatch.setattr(scheduler_module, "get_rank_by_puuid", fake_get_rank)
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
            select(TrackedPlayer).where(TrackedPlayer.game_name == "AggregatePlayer")
        )
        pm_count = await session.scalar(select(func.count()).select_from(PlayerMatch))
        price_history_count = await session.scalar(
            select(func.count()).select_from(PriceHistory)
        )

    assert player is not None
    # No matches -> no PlayerMatch rows, but aggregate pricing applied
    assert pm_count == 0
    # LP delta: Gold II 0 LP = (3*400)+(2*100)+0 = 1400, was 1500, delta = -100
    assert player.lp_abs == 1400
    assert player.current_price != 30.0  # price changed
    assert price_history_count == 1
