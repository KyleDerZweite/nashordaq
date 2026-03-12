from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentAdminUser, get_user_role
from app.banking import build_account_snapshot, restore_rescue_loan_use
from app.database import get_session
from app.models import Order, OrderStatus, TrackedPlayer, User
from app.routers.orders import build_order_responses
from app.routers.portfolio import build_portfolio_response
from app.scheduler import (
    classify_market_status,
    get_last_market_update_at,
    get_required_market_update_interval,
    is_scheduler_running,
)
from app.schemas import (
    AdminOverviewResponse,
    AdminUserPortfolioResponse,
    AdminUserSummaryResponse,
    OrderResponse,
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


@router.get("/orders", response_model=list[OrderResponse])
async def list_admin_orders(
    admin_user: CurrentAdminUser,
    session: SessionDep,
    status: OrderStatus | None = Query(default=None),  # noqa: B008
    user_id: int | None = Query(default=None, ge=1),  # noqa: B008
    limit: int = Query(default=200, ge=1, le=500),  # noqa: B008
) -> list[OrderResponse]:
    del admin_user

    stmt = select(Order)
    if status is not None:
        stmt = stmt.where(Order.status == status)
    if user_id is not None:
        stmt = stmt.where(Order.user_id == user_id)
    stmt = stmt.order_by(Order.created_at.desc()).limit(limit)

    result = await session.execute(stmt)
    orders = result.scalars().all()
    return await build_order_responses(session, orders)


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
