import asyncio
import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import SessionLocal
from app.models import (
    Holding,
    Order,
    OrderSide,
    OrderStatus,
    PriceHistory,
    TrackedPlayer,
    Transaction,
    User,
)
from app.pricing import (
    calculate_ipo_price,
    calculate_lp_abs,
    calculate_new_price,
    calculate_win_rate,
    generate_gamma_base,
    update_streak,
)
from app.riot import PlayerNotFoundError, RateLimitedError, get_rank

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
_app: FastAPI | None = None
_last_market_update_at: datetime | None = None


def get_last_market_update_at() -> datetime | None:
    return _last_market_update_at


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


async def market_update_job() -> None:
    global _last_market_update_at

    assert _app is not None
    http_client = _app.state.http_client

    async with SessionLocal() as session:
        result = await session.execute(select(TrackedPlayer))
        players = result.scalars().all()
        successful_player_updates = 0

        if not players:
            logger.info("Skipping market update; no tracked players exist yet")
            return

        required_interval_minutes = max(1, len(players))
        now = datetime.now(UTC)
        if (
            _last_market_update_at is not None
            and now - _last_market_update_at
            < timedelta(minutes=required_interval_minutes)
        ):
            logger.info(
                "Skipping market update; next run in %.1f min",
                (
                    timedelta(minutes=required_interval_minutes)
                    - (now - _last_market_update_at)
                ).total_seconds()
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

            if player.puuid is None:
                player.puuid = rank_data.puuid
                player.summoner_id = rank_data.summoner_id

            new_lp_abs = calculate_lp_abs(
                rank_data.tier, rank_data.rank, rank_data.league_points
            )
            win_rate = calculate_win_rate(rank_data.wins, rank_data.losses)

            if player.lp_abs == 0 and player.current_price <= 10.0:
                player.current_price = calculate_ipo_price(
                    new_lp_abs,
                    win_rate,
                    veteran=rank_data.veteran,
                    fresh_blood=rank_data.fresh_blood,
                )
                player.lp_abs = new_lp_abs
                player.previous_lp_abs = new_lp_abs
                player.gamma_factor = generate_gamma_base(hash(player.puuid) % 10000)
                logger.info(
                    "Initialized price for %s#%s at %.2f",
                    player.game_name,
                    player.tag_line,
                    player.current_price,
                )
            else:
                delta_lp = new_lp_abs - player.lp_abs
                player.previous_lp_abs = player.lp_abs
                player.lp_abs = new_lp_abs
                player.streak = update_streak(player.streak, delta_lp)
                player.current_price = calculate_new_price(
                    player.current_price,
                    delta_lp,
                    player.streak,
                    player.gamma_factor,
                    win_rate=win_rate,
                    hot_streak=rank_data.hot_streak,
                    veteran=rank_data.veteran,
                    inactive=rank_data.inactive,
                    fresh_blood=rank_data.fresh_blood,
                )
                logger.info(
                    "Updated price for %s#%s to %.2f (delta_lp=%d, win_rate=%.3f)",
                    player.game_name,
                    player.tag_line,
                    player.current_price,
                    delta_lp,
                    win_rate,
                )

            player.last_updated = datetime.now(UTC)

            session.add(
                PriceHistory(
                    player_id=player.id,
                    price=player.current_price,
                    lp_abs=player.lp_abs,
                )
            )
            successful_player_updates += 1

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

        await session.commit()
        if successful_player_updates > 0:
            _last_market_update_at = datetime.now(UTC)
            logger.info(
                "Market update completed (%d players)",
                successful_player_updates,
            )
        else:
            logger.warning(
                "Market cycle completed, but every tracked player refresh failed"
            )


def start_scheduler(app: FastAPI) -> None:
    global _app, _last_market_update_at

    _app = app
    _last_market_update_at = None
    scheduler.add_job(
        market_update_job,
        IntervalTrigger(seconds=30),
        id="market_update",
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
