import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.banking import (
    apply_due_interest,
    calculate_playing_income_amount,
    get_playing_income_daily_multiplier,
    get_playing_income_minimum_amount,
    get_playing_income_outcome_multiplier,
    record_user_wealth_snapshot,
    start_of_utc_day,
)
from app.config import settings
from app.database import SessionLocal
from app.models import (
    GambaPosition,
    GambaStatus,
    Holding,
    Order,
    OrderSide,
    OrderSource,
    OrderStatus,
    PlayingIncomeEntry,
    PlayingIncomeMatchResult,
    PriceHistory,
    TrackedPlayer,
    Transaction,
    User,
    UserWealthSnapshotSource,
)
from app.poro import maintain_poro_states, poro_state_notifier
from app.pricing import (
    calculate_ipo_price,
    calculate_lp_abs,
    calculate_new_price,
    calculate_win_rate,
    generate_gamma_base,
    update_streak,
)
from app.riot import (
    MatchSummary,
    PlayerNotFoundError,
    RateLimitedError,
    get_match_summary,
    get_rank,
    get_recent_match_ids,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
_app: FastAPI | None = None
_last_market_update_at: datetime | None = None
MARKET_UPDATE_JOB_INTERVAL_SECONDS = 30
PORO_MAINTENANCE_JOB_INTERVAL_SECONDS = 5
MARKET_STATUS_GRACE_SECONDS = 90
RANKED_SOLO_QUEUE_ID = 420


def get_last_market_update_at() -> datetime | None:
    return _last_market_update_at


def is_scheduler_running() -> bool:
    return scheduler.running


def get_required_market_update_interval(player_count: int) -> timedelta:
    return timedelta(minutes=max(1, player_count))


def classify_market_status(
    *,
    now: datetime,
    last_market_update_at: datetime | None,
    tracked_player_count: int,
    scheduler_running: bool,
) -> str:
    if tracked_player_count == 0 or last_market_update_at is None:
        return "idle"

    if not scheduler_running:
        return "degraded"

    freshness_window = get_required_market_update_interval(
        tracked_player_count
    ) + timedelta(seconds=MARKET_STATUS_GRACE_SECONDS)
    if now - last_market_update_at <= freshness_window:
        return "healthy"

    return "degraded"


async def _get_or_create_holding(
    session: AsyncSession,
    user_id: int,
    player_id: int,
) -> Holding:
    result = await session.execute(
        select(Holding).where(
            Holding.user_id == user_id,
            Holding.player_id == player_id,
        )
    )
    holding = result.scalar_one_or_none()
    if holding is None:
        holding = Holding(user_id=user_id, player_id=player_id, quantity=0)
        session.add(holding)
        await session.flush()
    return holding


def _match_completed_at(summary: MatchSummary) -> datetime:
    timestamp = summary.game_end_timestamp
    if timestamp > 10_000_000_000:
        timestamp = timestamp / 1000
    return datetime.fromtimestamp(timestamp, tz=UTC)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _ema(previous: float | None, sample: float, alpha: float) -> float:
    if previous is None:
        return sample
    return ((1 - alpha) * previous) + (alpha * sample)


def _learn_player_lp_averages(
    player: TrackedPlayer,
    *,
    wins: int,
    losses: int,
    delta_lp: int,
) -> None:
    prev_wins = player.ranked_wins_snapshot
    prev_losses = player.ranked_losses_snapshot

    # Bootstrap snapshots before learning to avoid fabricating early samples.
    if prev_wins is None or prev_losses is None:
        player.ranked_wins_snapshot = wins
        player.ranked_losses_snapshot = losses
        return

    win_delta = wins - prev_wins
    loss_delta = losses - prev_losses

    # Seasonal resets or profile corrections can move counters backward.
    if win_delta < 0 or loss_delta < 0:
        player.ranked_wins_snapshot = wins
        player.ranked_losses_snapshot = losses
        return

    alpha = min(max(settings.pricing_lp_average_ema_alpha, 0.0), 1.0)

    # Learn per-win LP only from pure win-side updates.
    if win_delta > 0 and loss_delta == 0 and delta_lp > 0:
        sample_gain = delta_lp / win_delta
        if sample_gain > 0:
            player.avg_lp_gain_on_win = _ema(
                player.avg_lp_gain_on_win,
                sample_gain,
                alpha,
            )

    # Learn per-loss LP only from pure loss-side updates.
    if loss_delta > 0 and win_delta == 0 and delta_lp < 0:
        sample_loss = abs(delta_lp) / loss_delta
        if sample_loss > 0:
            player.avg_lp_loss_on_loss = _ema(
                player.avg_lp_loss_on_loss,
                sample_loss,
                alpha,
            )

    player.ranked_wins_snapshot = wins
    player.ranked_losses_snapshot = losses


async def _get_playing_income_history_start(
    session: AsyncSession,
    player: TrackedPlayer,
) -> datetime:
    configured_start = _normalize_datetime(settings.playing_income_start_date)
    latest_recorded_completed_at = await session.scalar(
        select(func.max(PlayingIncomeEntry.match_completed_at)).where(
            PlayingIncomeEntry.player_id == player.id
        )
    )
    if latest_recorded_completed_at is None:
        return configured_start

    latest_recorded_completed_at = _normalize_datetime(latest_recorded_completed_at)
    return max(
        configured_start,
        latest_recorded_completed_at + timedelta(seconds=1),
    )


async def _get_match_ids_since(
    player: TrackedPlayer,
    http_client,
    *,
    start_time: datetime,
) -> list[str]:
    puuid = player.puuid
    if puuid is None:
        return []

    page_size = max(1, settings.playing_income_recent_match_count)
    start = 0
    match_ids: list[str] = []
    use_start_time = True
    use_filters = True

    while True:
        try:
            page = await get_recent_match_ids(
                client=http_client,
                base_url=settings.riot_api_base_url,
                api_key=settings.riot_api_key,
                puuid=puuid,
                start=start,
                count=page_size,
                start_time=start_time if use_start_time else None,
                queue=RANKED_SOLO_QUEUE_ID if use_filters else None,
                type="ranked" if use_filters else None,
            )
        except httpx.HTTPStatusError as exc:
            if use_start_time and exc.response.status_code == 400:
                logger.warning(
                    (
                        "Riot Match-V5 rejected filtered startTime history for "
                        "%s#%s; falling back to unfiltered paging"
                    ),
                    player.game_name,
                    player.tag_line,
                )
                use_start_time = False
                use_filters = False
                start = 0
                match_ids.clear()
                continue
            raise

        if not page:
            break

        match_ids.extend(page)
        if len(page) < page_size:
            break

        start += len(page)

    return match_ids


async def _get_match_summary_if_available(
    player: TrackedPlayer,
    http_client,
    *,
    match_id: str,
) -> MatchSummary | None:
    try:
        return await get_match_summary(
            client=http_client,
            base_url=settings.riot_api_base_url,
            api_key=settings.riot_api_key,
            puuid=player.puuid,
            match_id=match_id,
        )
    except PlayerNotFoundError:
        logger.warning(
            "Skipping match %s for %s#%s because Riot returned no participant data",
            match_id,
            player.game_name,
            player.tag_line,
        )
        return None


async def _get_unprocessed_match_summaries(
    session: AsyncSession,
    player: TrackedPlayer,
    http_client,
) -> tuple[list[MatchSummary], MatchSummary | None]:
    if player.puuid is None:
        return [], None

    history_start = await _get_playing_income_history_start(session, player)
    match_ids = await _get_match_ids_since(
        player,
        http_client,
        start_time=history_start,
    )
    if not match_ids:
        return [], None

    recorded_ids_result = await session.execute(
        select(PlayingIncomeEntry.match_id).where(
            PlayingIncomeEntry.player_id == player.id,
        )
    )
    recorded_ids = set(recorded_ids_result.scalars().all())
    unseen_ids = [match_id for match_id in match_ids if match_id not in recorded_ids]

    newest_summary: MatchSummary | None = None
    if unseen_ids and unseen_ids[0] == match_ids[0]:
        candidate_newest_summary = await _get_match_summary_if_available(
            player,
            http_client,
            match_id=match_ids[0],
        )
        if (
            candidate_newest_summary is not None
            and _match_completed_at(candidate_newest_summary) >= history_start
        ):
            newest_summary = candidate_newest_summary

    summaries = [newest_summary] if newest_summary is not None else []
    for match_id in unseen_ids[len(summaries) :]:
        summary = await _get_match_summary_if_available(
            player,
            http_client,
            match_id=match_id,
        )
        if summary is None:
            continue
        if _match_completed_at(summary) < history_start:
            continue
        summaries.append(summary)

    if newest_summary is None:
        newest_summary = await _get_match_summary_if_available(
            player,
            http_client,
            match_id=match_ids[0],
        )

    summaries.sort(key=lambda summary: summary.game_end_timestamp)
    return summaries, newest_summary


async def _apply_playing_income_for_player(
    session: AsyncSession,
    player: TrackedPlayer,
    http_client,
) -> None:
    summaries, newest_summary = await _get_unprocessed_match_summaries(
        session, player, http_client
    )

    if not summaries:
        if newest_summary is not None:
            player.last_playing_income_match_id = newest_summary.match_id
            player.last_playing_income_match_end_at = _match_completed_at(
                newest_summary
            )
        return

    user_result = await session.execute(
        select(User).where(User.linked_player_id == player.id)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        latest_summary = newest_summary or summaries[-1]
        player.last_playing_income_match_id = latest_summary.match_id
        player.last_playing_income_match_end_at = _match_completed_at(latest_summary)
        return

    daily_rewarded_match_counts: dict[datetime, int] = {}

    for summary in summaries:
        completed_at = _match_completed_at(summary)
        day_start = start_of_utc_day(completed_at)

        if summary.queue_id != RANKED_SOLO_QUEUE_ID:
            continue
        if (
            summary.game_duration_seconds
            < settings.playing_income_min_match_duration_seconds
        ):
            continue

        if day_start not in daily_rewarded_match_counts:
            day_end = day_start + timedelta(days=1)
            rewarded_count_result = await session.scalar(
                select(func.count(PlayingIncomeEntry.id)).where(
                    PlayingIncomeEntry.user_id == user.id,
                    PlayingIncomeEntry.match_completed_at >= day_start,
                    PlayingIncomeEntry.match_completed_at < day_end,
                )
            )
            daily_rewarded_match_counts[day_start] = int(rewarded_count_result or 0)

        match_number_for_day = daily_rewarded_match_counts[day_start] + 1
        daily_multiplier = get_playing_income_daily_multiplier(match_number_for_day)
        outcome_multiplier = get_playing_income_outcome_multiplier(
            summary.win,
            match_number_for_day,
        )
        amount = calculate_playing_income_amount(
            player.current_price,
            outcome_multiplier,
            minimum_amount=get_playing_income_minimum_amount(summary.win),
            daily_multiplier=daily_multiplier,
        )
        if amount <= 0:
            continue

        user.balance += amount
        daily_rewarded_match_counts[day_start] = match_number_for_day
        session.add(
            PlayingIncomeEntry(
                user_id=user.id,
                player_id=player.id,
                match_id=summary.match_id,
                match_result=(
                    PlayingIncomeMatchResult.WIN
                    if summary.win
                    else PlayingIncomeMatchResult.LOSS
                ),
                match_duration_seconds=summary.game_duration_seconds,
                match_completed_at=completed_at,
                share_price=player.current_price,
                base_rate=settings.playing_income_base_rate,
                outcome_multiplier=outcome_multiplier,
                amount=amount,
            )
        )
        logger.info(
            "Applied playing income for %s#%s match %s: %.2f",
            player.game_name,
            player.tag_line,
            summary.match_id,
            amount,
        )

    latest_summary = newest_summary or summaries[-1]
    player.last_playing_income_match_id = latest_summary.match_id
    player.last_playing_income_match_end_at = _match_completed_at(latest_summary)


async def market_update_job() -> None:
    global _last_market_update_at

    assert _app is not None
    http_client = _app.state.http_client

    async with SessionLocal() as session:
        result = await session.execute(select(TrackedPlayer))
        players = result.scalars().all()
        successful_player_refreshes = 0

        if not players:
            logger.info("Skipping market update; no tracked players exist yet")
            return

        required_interval = get_required_market_update_interval(len(players))
        now = datetime.now(UTC)
        if (
            _last_market_update_at is not None
            and now - _last_market_update_at < required_interval
        ):
            logger.info(
                "Skipping market update; next run in %.1f min",
                (required_interval - (now - _last_market_update_at)).total_seconds()
                / 60,
            )
            return

        for player in players:
            try:
                rank_data = await get_rank(
                    client=http_client,
                    base_url=settings.riot_api_base_url,
                    region_url=settings.riot_api_region_url,
                    api_key=settings.riot_api_key,
                    game_name=player.game_name,
                    tag_line=player.tag_line,
                )
            except PlayerNotFoundError:
                logger.warning(
                    "Player not found: %s#%s", player.game_name, player.tag_line
                )
                continue
            except RateLimitedError:
                logger.warning("Rate limited, skipping remaining players")
                break
            except Exception:
                logger.exception(
                    "Error fetching data for %s#%s",
                    player.game_name,
                    player.tag_line,
                )
                continue

            if player.puuid != rank_data.puuid:
                player.puuid = rank_data.puuid
            if player.summoner_id != rank_data.summoner_id:
                player.summoner_id = rank_data.summoner_id

            successful_player_refreshes += 1

            new_lp_abs = calculate_lp_abs(
                rank_data.tier, rank_data.rank, rank_data.league_points
            )
            win_rate = calculate_win_rate(rank_data.wins, rank_data.losses)
            should_record_market_update = False

            if player.lp_abs == 0 and player.current_price <= 10.0:
                player.current_price = calculate_ipo_price(
                    new_lp_abs,
                    win_rate,
                )
                player.lp_abs = new_lp_abs
                player.previous_lp_abs = new_lp_abs
                player.gamma_factor = generate_gamma_base(hash(player.puuid) % 10000)
                player.ranked_wins_snapshot = rank_data.wins
                player.ranked_losses_snapshot = rank_data.losses
                should_record_market_update = True
                logger.info(
                    "Initialized price for %s#%s at %.2f",
                    player.game_name,
                    player.tag_line,
                    player.current_price,
                )
            else:
                delta_lp = new_lp_abs - player.lp_abs
                _learn_player_lp_averages(
                    player,
                    wins=rank_data.wins,
                    losses=rank_data.losses,
                    delta_lp=delta_lp,
                )

                if delta_lp == 0:
                    logger.info(
                        "No LP change for %s#%s; preserving market state",
                        player.game_name,
                        player.tag_line,
                    )
                else:
                    player.previous_lp_abs = player.lp_abs
                    player.lp_abs = new_lp_abs
                    player.streak = update_streak(player.streak, delta_lp)
                    player.current_price = calculate_new_price(
                        player.current_price,
                        delta_lp,
                        player.streak,
                        player.gamma_factor,
                        win_rate=win_rate,
                        avg_lp_loss_on_loss=player.avg_lp_loss_on_loss,
                        avg_lp_gain_on_win=player.avg_lp_gain_on_win,
                        inactive=rank_data.inactive,
                    )
                    should_record_market_update = True
                    logger.info(
                        "Updated price for %s#%s to %.2f (delta_lp=%d, win_rate=%.3f)",
                        player.game_name,
                        player.tag_line,
                        player.current_price,
                        delta_lp,
                        win_rate,
                    )

            if should_record_market_update:
                player.last_updated = datetime.now(UTC)
                session.add(
                    PriceHistory(
                        player_id=player.id,
                        price=player.current_price,
                        lp_abs=player.lp_abs,
                    )
                )

            try:
                await _apply_playing_income_for_player(session, player, http_client)
            except PlayerNotFoundError:
                logger.warning(
                    "Missing match data for %s#%s; skipping playing income",
                    player.game_name,
                    player.tag_line,
                )
            except RateLimitedError:
                logger.warning(
                    "Rate limited while fetching matches for %s#%s",
                    player.game_name,
                    player.tag_line,
                )
                break
            except Exception:
                logger.exception(
                    "Error applying playing income for %s#%s",
                    player.game_name,
                    player.tag_line,
                )

            await asyncio.sleep(0.1)

        # Execute pending orders
        pending_result = await session.execute(
            select(Order)
            .where(Order.status == OrderStatus.PENDING)
            .order_by(Order.created_at)
        )
        pending_orders = pending_result.scalars().all()

        for order in pending_orders:
            player = await session.get(TrackedPlayer, order.player_id)
            user = await session.get(User, order.user_id)
            if player is None or user is None:
                order.status = OrderStatus.CANCELLED
                continue

            execution_price = player.current_price
            total_cost = execution_price * order.quantity
            now = datetime.now(UTC)

            if order.side == OrderSide.BUY:
                if user.balance < total_cost:
                    order.status = OrderStatus.CANCELLED
                    logger.info("Cancelled order %d: insufficient balance", order.id)
                    continue
                user.balance -= total_cost
                holding = await _get_or_create_holding(session, user.id, player.id)
                holding.quantity += order.quantity

            elif order.side == OrderSide.SELL:
                holding = await _get_or_create_holding(session, user.id, player.id)
                if holding.quantity < order.quantity:
                    order.status = OrderStatus.CANCELLED
                    logger.info("Cancelled order %d: insufficient shares", order.id)
                    continue
                holding.quantity -= order.quantity
                user.balance += total_cost

            order.status = OrderStatus.EXECUTED
            order.execution_price = execution_price
            order.executed_at = now

            session.add(
                Transaction(
                    user_id=user.id,
                    player_id=player.id,
                    order_id=order.id,
                    side=order.side,
                    quantity=order.quantity,
                    price=execution_price,
                    total=total_cost,
                )
            )

        due_gamba_result = await session.execute(
            select(GambaPosition)
            .where(GambaPosition.status == GambaStatus.ACTIVE)
            .where(GambaPosition.scheduled_settlement_at <= datetime.now(UTC))
            .order_by(GambaPosition.scheduled_settlement_at.asc())
        )
        due_positions = due_gamba_result.scalars().all()

        for position in due_positions:
            player = await session.get(TrackedPlayer, position.player_id)
            user = await session.get(User, position.user_id)
            if player is None or user is None:
                continue

            now = datetime.now(UTC)
            exit_price = player.current_price
            gross_exit_value = position.quantity * exit_price
            raw_pnl = gross_exit_value - position.cash_amount
            payout_total = max(
                0.0,
                position.cash_amount + (raw_pnl * position.settlement_multiplier),
            )
            settled_pnl = payout_total - position.cash_amount

            user.balance += payout_total
            position.exit_price = exit_price
            position.settled_at = now
            position.raw_pnl = raw_pnl
            position.settled_pnl = settled_pnl
            position.status = GambaStatus.SETTLED

            sell_order = Order(
                user_id=user.id,
                player_id=player.id,
                side=OrderSide.SELL,
                quantity=0,
                quantity_value=position.quantity,
                status=OrderStatus.EXECUTED,
                source=OrderSource.GAMBA,
                gross_execution_price=exit_price,
                gross_total_value=gross_exit_value,
                entry_total_value=position.cash_amount,
                adjustment_value=payout_total - gross_exit_value,
                adjustment_reason="GAMBA_MULTIPLIER",
                execution_price=(payout_total / position.quantity)
                if position.quantity > 0
                else 0.0,
                executed_at=now,
            )
            session.add(sell_order)
            await session.flush()
            position.sell_order_id = sell_order.id

        indebted_users_result = await session.execute(
            select(User).where(
                (User.debt_principal > 0) | (User.debt_accrued_interest > 0)
            )
        )
        indebted_users = indebted_users_result.scalars().all()
        for user in indebted_users:
            await apply_due_interest(session, user, as_of=datetime.now(UTC))

        all_users_result = await session.execute(select(User))
        all_users = all_users_result.scalars().all()
        snapshot_time = datetime.now(UTC)
        for user in all_users:
            await record_user_wealth_snapshot(
                session,
                user,
                source=UserWealthSnapshotSource.MARKET_UPDATE,
                as_of=snapshot_time,
            )

        await session.commit()
        if successful_player_refreshes > 0:
            _last_market_update_at = datetime.now(UTC)
            logger.info(
                "Market update completed (%d players refreshed)",
                successful_player_refreshes,
            )
        else:
            logger.warning(
                "Market cycle completed, but every tracked player refresh failed"
            )


async def poro_maintenance_job() -> None:
    if not settings.poro_enabled:
        return

    async with SessionLocal() as session:
        changed_user_ids = await maintain_poro_states(session, as_of=datetime.now(UTC))
        await session.commit()

    for user_id in changed_user_ids:
        await poro_state_notifier.notify(user_id)


def start_scheduler(app: FastAPI) -> None:
    global _app, _last_market_update_at

    _app = app
    _last_market_update_at = None
    scheduler.add_job(
        market_update_job,
        IntervalTrigger(seconds=MARKET_UPDATE_JOB_INTERVAL_SECONDS),
        id="market_update",
        replace_existing=True,
        max_instances=1,
        next_run_time=datetime.now(UTC),
    )
    scheduler.add_job(
        poro_maintenance_job,
        IntervalTrigger(seconds=PORO_MAINTENANCE_JOB_INTERVAL_SECONDS),
        id="poro_maintenance",
        replace_existing=True,
        max_instances=1,
        next_run_time=datetime.now(UTC),
    )
    scheduler.start()
    logger.info("Scheduler started (dynamic interval: tracked_player_count minutes)")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
