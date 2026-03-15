from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentAdminUser, get_user_role
from app.banking import build_account_snapshot, restore_rescue_loan_use
from app.config import settings
from app.database import get_session
from app.models import (
    GambaPosition,
    GambaStatus,
    Holding,
    Order,
    OrderStatus,
    PlayerMatch,
    PlayingIncomeEntry,
    PoroSpawn,
    PoroSpawnStatus,
    TrackedPlayer,
    User,
)
from app.pricing import BETA, calculate_win_rate
from app.routers.portfolio import build_portfolio_response
from app.scheduler import (
    classify_market_status,
    get_last_market_update_at,
    get_required_market_update_interval,
    is_scheduler_running,
)
from app.schemas import (
    AdminOverviewResponse,
    AdminPlayerInsightResponse,
    AdminPlayerMatchResponse,
    AdminPlayerPlayingIncomeEntryResponse,
    AdminPlayerPoroRewardResponse,
    AdminUserPortfolioResponse,
    AdminUserSummaryResponse,
    SystemStatusResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _linked_player_identity_map(
    session: AsyncSession,
) -> dict[int, tuple[str, str]]:
    result = await session.execute(
        select(TrackedPlayer.id, TrackedPlayer.display_name, TrackedPlayer.game_name)
    )
    return {
        player_id: (display_name, game_name)
        for player_id, display_name, game_name in result.all()
    }


async def _build_admin_user_portfolio_response(
    session: AsyncSession,
    user: User,
) -> AdminUserPortfolioResponse:
    linked_player_name = None
    linked_player_game_name = None
    if user.linked_player_id is not None:
        linked_player = await session.get(TrackedPlayer, user.linked_player_id)
        linked_player_name = linked_player.display_name if linked_player else None
        linked_player_game_name = linked_player.game_name if linked_player else None

    snapshot = await build_account_snapshot(session, user)

    return AdminUserPortfolioResponse(
        user_id=user.id,
        username=user.username,
        role=get_user_role(user.username),
        linked_player_id=user.linked_player_id,
        linked_player_name=linked_player_name,
        linked_player_game_name=linked_player_game_name,
        onboarding_complete=user.linked_player_id is not None,
        created_at=user.created_at,
        rescue_loan_uses_remaining=snapshot.rescue_loan_uses_remaining,
        rescue_loan_available=snapshot.rescue_loan_available,
        rescue_loan_block_reason=snapshot.rescue_loan_block_reason,
        portfolio=await build_portfolio_response(session, user),
    )


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _estimate_ratio_metrics(
    player: TrackedPlayer,
) -> tuple[float | None, float, int, float]:
    raw_ratio: float | None = None
    if (
        player.avg_lp_loss_on_loss is not None
        and player.avg_lp_gain_on_win is not None
        and player.avg_lp_loss_on_loss > 0
        and player.avg_lp_gain_on_win > 0
    ):
        raw_ratio = player.avg_lp_loss_on_loss / player.avg_lp_gain_on_win

    clamped_ratio = (
        settings.pricing_win_streak_lp_ratio_default
        if raw_ratio is None
        else _clamp(
            raw_ratio,
            settings.pricing_win_streak_lp_ratio_min,
            settings.pricing_win_streak_lp_ratio_max,
        )
    )
    effective_positive_streak = min(
        max(player.streak, 0),
        max(1, settings.pricing_max_effective_streak),
    )
    streak_multiplier = 1 + (BETA * effective_positive_streak)
    return raw_ratio, clamped_ratio, effective_positive_streak, streak_multiplier


def _estimate_win_rate(player: TrackedPlayer) -> float | None:
    if (
        player.ranked_wins_snapshot is None
        or player.ranked_losses_snapshot is None
        or player.ranked_wins_snapshot < 0
        or player.ranked_losses_snapshot < 0
    ):
        return None
    return calculate_win_rate(
        player.ranked_wins_snapshot,
        player.ranked_losses_snapshot,
    )


@router.get("/overview", response_model=AdminOverviewResponse)
async def get_admin_overview(
    admin_user: CurrentAdminUser,
    session: SessionDep,
) -> AdminOverviewResponse:
    del admin_user

    user_result = await session.execute(select(User))
    users = user_result.scalars().all()

    order_counts = await session.execute(
        select(
            func.count(Order.id),
            func.sum(case((Order.status == OrderStatus.PENDING, 1), else_=0)),
            func.sum(case((Order.status == OrderStatus.EXECUTED, 1), else_=0)),
            func.sum(case((Order.status == OrderStatus.REVERTED, 1), else_=0)),
            func.sum(case((Order.status == OrderStatus.CANCELLED, 1), else_=0)),
        )
    )
    (
        total_orders,
        pending_orders,
        executed_orders,
        reverted_orders,
        cancelled_orders,
    ) = order_counts.one()

    total_cash_balance = 0.0
    total_debt_outstanding = 0.0
    admin_users = 0
    onboarded_users = 0
    for user in users:
        snapshot = await build_account_snapshot(session, user)
        total_cash_balance += snapshot.cash_balance
        total_debt_outstanding += snapshot.debt_outstanding
        if user.linked_player_id is not None:
            onboarded_users += 1
        if get_user_role(user.username) == "admin":
            admin_users += 1

    tracked_players = await session.scalar(
        select(func.count()).select_from(TrackedPlayer)
    )

    return AdminOverviewResponse(
        total_users=len(users),
        onboarded_users=onboarded_users,
        admin_users=admin_users,
        tracked_players=tracked_players or 0,
        total_orders=total_orders or 0,
        pending_orders=pending_orders or 0,
        executed_orders=executed_orders or 0,
        reverted_orders=reverted_orders or 0,
        cancelled_orders=cancelled_orders or 0,
        total_cash_balance=round(total_cash_balance, 2),
        total_debt_outstanding=round(total_debt_outstanding, 2),
    )


@router.get("/users", response_model=list[AdminUserSummaryResponse])
async def list_admin_users(
    admin_user: CurrentAdminUser,
    session: SessionDep,
) -> list[AdminUserSummaryResponse]:
    del admin_user

    user_result = await session.execute(
        select(User).order_by(User.created_at.asc(), User.id.asc())
    )
    users = user_result.scalars().all()
    linked_player_identities = await _linked_player_identity_map(session)

    summaries: list[AdminUserSummaryResponse] = []
    for user in users:
        snapshot = await build_account_snapshot(session, user)
        summaries.append(
            AdminUserSummaryResponse(
                id=user.id,
                username=user.username,
                role=get_user_role(user.username),
                linked_player_id=user.linked_player_id,
                linked_player_name=(
                    linked_player_identities.get(user.linked_player_id, (None, None))[0]
                    if user.linked_player_id is not None
                    else None
                ),
                linked_player_game_name=(
                    linked_player_identities.get(user.linked_player_id, (None, None))[1]
                    if user.linked_player_id is not None
                    else None
                ),
                onboarding_complete=user.linked_player_id is not None,
                balance=snapshot.cash_balance,
                holdings_value=snapshot.holdings_value,
                active_gamba_value=snapshot.active_gamba_value,
                debt_outstanding=snapshot.debt_outstanding,
                total_value=snapshot.debt_adjusted_net_worth,
                created_at=user.created_at,
            )
        )

    return sorted(summaries, key=lambda summary: summary.total_value, reverse=True)


@router.get("/players/insights", response_model=list[AdminPlayerInsightResponse])
async def list_admin_player_insights(
    admin_user: CurrentAdminUser,
    session: SessionDep,
) -> list[AdminPlayerInsightResponse]:
    del admin_user

    players_result = await session.execute(
        select(TrackedPlayer).order_by(
            TrackedPlayer.current_price.desc(),
            TrackedPlayer.display_name.asc(),
        )
    )
    players = players_result.scalars().all()

    users_result = await session.execute(select(User))
    users = users_result.scalars().all()
    user_by_linked_player = {
        user.linked_player_id: user
        for user in users
        if user.linked_player_id is not None
    }

    shareholder_result = await session.execute(
        select(
            Holding.player_id,
            func.count(Holding.user_id.distinct()),
            func.coalesce(func.sum(Holding.quantity), 0),
        ).group_by(Holding.player_id)
    )
    shareholder_map = {
        player_id: (shareholder_count or 0, total_shares or 0)
        for player_id, shareholder_count, total_shares in shareholder_result.all()
    }

    gamba_result = await session.execute(
        select(
            GambaPosition.player_id,
            func.count(GambaPosition.id),
            func.coalesce(func.sum(GambaPosition.cash_amount), 0.0),
        )
        .where(GambaPosition.status == GambaStatus.ACTIVE)
        .group_by(GambaPosition.player_id)
    )
    gamba_map = {
        player_id: (active_positions or 0, active_cash or 0.0)
        for player_id, active_positions, active_cash in gamba_result.all()
    }

    now = datetime.now(UTC)
    last_24h = now.replace(tzinfo=UTC) - timedelta(hours=24)
    insights: list[AdminPlayerInsightResponse] = []

    for player in players:
        linked_user = user_by_linked_player.get(player.id)
        linked_snapshot = (
            await build_account_snapshot(session, linked_user)
            if linked_user is not None
            else None
        )

        shareholder_count, total_shares = shareholder_map.get(player.id, (0, 0))
        active_gamba_positions, active_gamba_cash = gamba_map.get(player.id, (0, 0.0))

        playing_income_entries_result = await session.execute(
            select(PlayingIncomeEntry)
            .where(PlayingIncomeEntry.player_id == player.id)
            .order_by(PlayingIncomeEntry.match_completed_at.desc())
        )
        playing_income_entries = playing_income_entries_result.scalars().all()
        playing_income_lifetime_total = round(
            sum(entry.amount for entry in playing_income_entries), 2
        )
        playing_income_game_count = len(playing_income_entries)
        playing_income_average_per_game = (
            round(playing_income_lifetime_total / playing_income_game_count, 2)
            if playing_income_game_count > 0
            else None
        )
        playing_income_last_24h = round(
            sum(
                entry.amount
                for entry in playing_income_entries
                if (
                    entry.match_completed_at.replace(tzinfo=UTC)
                    if entry.match_completed_at.tzinfo is None
                    else entry.match_completed_at.astimezone(UTC)
                )
                >= last_24h
            ),
            2,
        )

        poro_rewards: list[PoroSpawn] = []
        poro_rewards_total = 0.0
        poro_claim_count = 0
        if linked_user is not None:
            poro_rewards_result = await session.execute(
                select(PoroSpawn)
                .where(PoroSpawn.user_id == linked_user.id)
                .order_by(PoroSpawn.spawned_at.desc())
            )
            poro_rewards = poro_rewards_result.scalars().all()
            claimed_rewards = [
                spawn
                for spawn in poro_rewards
                if spawn.status == PoroSpawnStatus.CLAIMED
            ]
            poro_rewards_total = round(
                sum(spawn.reward_amount for spawn in claimed_rewards),
                2,
            )
            poro_claim_count = len(claimed_rewards)

        player_matches_result = await session.execute(
            select(PlayerMatch)
            .where(PlayerMatch.player_id == player.id)
            .order_by(PlayerMatch.completed_at.desc())
        )
        player_matches = player_matches_result.scalars().all()
        income_by_match_id = {
            entry.match_id: entry.amount for entry in playing_income_entries
        }

        raw_ratio, clamped_ratio, effective_positive_streak, streak_multiplier = (
            _estimate_ratio_metrics(player)
        )
        estimated_win_rate = _estimate_win_rate(player)

        insights.append(
            AdminPlayerInsightResponse(
                player_id=player.id,
                display_name=player.display_name,
                game_name=player.game_name,
                tag_line=player.tag_line,
                linked_user_id=linked_user.id if linked_user is not None else None,
                linked_username=(
                    linked_user.username if linked_user is not None else None
                ),
                linked_user_balance=(
                    linked_snapshot.cash_balance
                    if linked_snapshot is not None
                    else None
                ),
                linked_user_holdings_value=(
                    linked_snapshot.holdings_value
                    if linked_snapshot is not None
                    else None
                ),
                linked_user_active_gamba_value=(
                    linked_snapshot.active_gamba_value
                    if linked_snapshot is not None
                    else None
                ),
                linked_user_debt_outstanding=(
                    linked_snapshot.debt_outstanding
                    if linked_snapshot is not None
                    else None
                ),
                linked_user_net_worth=(
                    linked_snapshot.debt_adjusted_net_worth
                    if linked_snapshot is not None
                    else None
                ),
                current_price=player.current_price,
                lp_abs=player.lp_abs,
                previous_lp_abs=player.previous_lp_abs,
                lp_delta=player.lp_abs - player.previous_lp_abs,
                streak=player.streak,
                effective_positive_streak=effective_positive_streak,
                ranked_wins_snapshot=player.ranked_wins_snapshot,
                ranked_losses_snapshot=player.ranked_losses_snapshot,
                estimated_win_rate=estimated_win_rate,
                avg_lp_gain_on_win=player.avg_lp_gain_on_win,
                avg_lp_loss_on_loss=player.avg_lp_loss_on_loss,
                estimated_lp_ratio_raw=raw_ratio,
                estimated_lp_ratio_clamped=clamped_ratio,
                estimated_streak_multiplier=streak_multiplier,
                shareholder_count=shareholder_count,
                total_shares_held=total_shares,
                active_gamba_positions=active_gamba_positions,
                active_gamba_cash=round(active_gamba_cash, 2),
                playing_income_game_count=playing_income_game_count,
                playing_income_lifetime_total=playing_income_lifetime_total,
                playing_income_average_per_game=playing_income_average_per_game,
                playing_income_last_24h=playing_income_last_24h,
                poro_claim_count=poro_claim_count,
                poro_rewards_total=poro_rewards_total,
                recent_player_matches=[
                    AdminPlayerMatchResponse(
                        match_id=pm.match_id,
                        win=pm.win,
                        lp_delta=pm.lp_delta,
                        lp_delta_source=pm.lp_delta_source,
                        price_before=pm.price_before,
                        price_after=pm.price_after,
                        playing_income_amount=income_by_match_id.get(pm.match_id),
                        completed_at=pm.completed_at,
                    )
                    for pm in player_matches[:50]
                ],
                recent_playing_income_entries=[
                    AdminPlayerPlayingIncomeEntryResponse(
                        match_id=entry.match_id,
                        match_result=entry.match_result,
                        match_completed_at=entry.match_completed_at,
                        amount=entry.amount,
                        share_price=entry.share_price,
                        outcome_multiplier=entry.outcome_multiplier,
                    )
                    for entry in playing_income_entries[:50]
                ],
                recent_poro_rewards=[
                    AdminPlayerPoroRewardResponse(
                        spawn_id=spawn.public_id,
                        reward_amount=spawn.reward_amount,
                        spawned_at=spawn.spawned_at,
                        claimed_at=spawn.claimed_at,
                        status=spawn.status,
                    )
                    for spawn in poro_rewards[:50]
                ],
            )
        )

    return insights


@router.get("/users/{user_id}/portfolio", response_model=AdminUserPortfolioResponse)
async def get_admin_user_portfolio(
    user_id: int,
    admin_user: CurrentAdminUser,
    session: SessionDep,
) -> AdminUserPortfolioResponse:
    del admin_user

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return await _build_admin_user_portfolio_response(session, user)


@router.post(
    "/users/{user_id}/rescue-unlock",
    response_model=AdminUserPortfolioResponse,
)
async def restore_admin_user_rescue_unlock(
    user_id: int,
    admin_user: CurrentAdminUser,
    session: SessionDep,
) -> AdminUserPortfolioResponse:
    del admin_user

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    restore_rescue_loan_use(user)
    await session.commit()
    await session.refresh(user)
    return await _build_admin_user_portfolio_response(session, user)


@router.get("/system/status", response_model=SystemStatusResponse)
async def get_admin_system_status(
    admin_user: CurrentAdminUser,
    session: SessionDep,
) -> SystemStatusResponse:
    del admin_user

    tracked_player_count = await session.scalar(
        select(func.count()).select_from(TrackedPlayer)
    )
    player_count = tracked_player_count or 0
    expected_update_interval_minutes = int(
        get_required_market_update_interval(player_count).total_seconds() // 60
    )
    last_market_update_at = get_last_market_update_at()
    scheduler_running = is_scheduler_running()

    return SystemStatusResponse(
        service_status="ok",
        scheduler_running=scheduler_running,
        market_status=classify_market_status(
            now=datetime.now(UTC),
            last_market_update_at=last_market_update_at,
            tracked_player_count=player_count,
            scheduler_running=scheduler_running,
        ),
        tracked_player_count=player_count,
        expected_update_interval_minutes=max(1, expected_update_interval_minutes),
        last_market_update_at=last_market_update_at,
    )
