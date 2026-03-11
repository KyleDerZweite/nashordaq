import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_user_role, is_admin_user
from app.banking import build_balance_insights_summary, record_user_wealth_snapshot
from app.config import settings
from app.database import get_session
from app.models import PriceHistory, TrackedPlayer, User, UserWealthSnapshotSource
from app.pricing import (
    calculate_ipo_price,
    calculate_lp_abs,
    calculate_win_rate,
    generate_gamma_base,
)
from app.riot import PlayerNotFoundError, RateLimitedError, get_rank
from app.schemas import (
    BalanceInsightsResponse,
    UserOnboardingCreate,
    UserProfileUpdate,
    UserResponse,
    UserWealthSnapshotResponse,
)

router = APIRouter(tags=["user"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
logger = logging.getLogger(__name__)


def _normalize_player_identity(
    game_name: str,
    tag_line: str,
    display_name: str,
) -> tuple[str, str, str]:
    normalized_game_name = game_name.strip()
    normalized_tag_line = tag_line.strip().lstrip("#")
    normalized_display_name = display_name.strip()

    if (
        not normalized_game_name
        or not normalized_tag_line
        or not normalized_display_name
    ):
        raise HTTPException(status_code=400, detail="All fields are required")

    return normalized_game_name, normalized_tag_line, normalized_display_name


async def _initialize_player_market_state(
    request: Request,
    session: AsyncSession,
    player: TrackedPlayer,
) -> None:
    try:
        rank_data = await get_rank(
            client=request.app.state.http_client,
            base_url=settings.riot_api_base_url,
            region_url=settings.riot_api_region_url,
            api_key=settings.riot_api_key,
            game_name=player.game_name,
            tag_line=player.tag_line,
        )
    except PlayerNotFoundError:
        logger.warning(
            "Onboarding completed without initial price refresh for %s#%s: "
            "no ranked Riot data",
            player.game_name,
            player.tag_line,
        )
        return
    except RateLimitedError:
        logger.warning(
            "Onboarding completed without initial price refresh for %s#%s: "
            "Riot API rate limited",
            player.game_name,
            player.tag_line,
        )
        return
    except Exception:
        logger.exception(
            "Onboarding completed without initial price refresh for %s#%s",
            player.game_name,
            player.tag_line,
        )
        return

    player.puuid = rank_data.puuid
    player.summoner_id = rank_data.summoner_id

    new_lp_abs = calculate_lp_abs(
        rank_data.tier,
        rank_data.rank,
        rank_data.league_points,
    )
    win_rate = calculate_win_rate(rank_data.wins, rank_data.losses)
    player.current_price = calculate_ipo_price(
        new_lp_abs,
        win_rate,
        veteran=rank_data.veteran,
        fresh_blood=rank_data.fresh_blood,
    )
    player.lp_abs = new_lp_abs
    player.previous_lp_abs = new_lp_abs
    player.gamma_factor = generate_gamma_base(hash(player.puuid) % 10000)
    player.last_updated = datetime.now(UTC)

    session.add(
        PriceHistory(
            player_id=player.id,
            price=player.current_price,
            lp_abs=player.lp_abs,
        )
    )

    logger.info(
        "Initialized market price for %s#%s at %.2f",
        player.game_name,
        player.tag_line,
        player.current_price,
    )


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        role=get_user_role(user.username),
        balance=user.balance,
        linked_player_id=user.linked_player_id,
        onboarding_complete=user.linked_player_id is not None,
        created_at=user.created_at,
    )


@router.get("/user/me", response_model=UserResponse)
async def get_me(user: CurrentUser) -> UserResponse:
    return _to_user_response(user)


@router.get("/user/balance-insights", response_model=BalanceInsightsResponse)
async def get_balance_insights(
    user: CurrentUser,
    session: SessionDep,
) -> BalanceInsightsResponse:
    summary = await build_balance_insights_summary(
        session, user, as_of=datetime.now(UTC)
    )

    return BalanceInsightsResponse(
        cash_balance=summary.snapshot.cash_balance,
        holdings_value=summary.snapshot.holdings_value,
        active_gamba_value=summary.snapshot.active_gamba_value,
        debt_outstanding=summary.snapshot.debt_outstanding,
        net_worth=summary.snapshot.debt_adjusted_net_worth,
        playing_income_last_24h=summary.playing_income.playing_income_last_24h,
        playing_income_lifetime_total=summary.playing_income.playing_income_lifetime_total,
        history=[
            UserWealthSnapshotResponse(
                id=entry.id,
                source=entry.source,
                cash_balance=entry.cash_balance,
                holdings_value=entry.holdings_value,
                active_gamba_value=entry.active_gamba_value,
                debt_outstanding=entry.debt_outstanding,
                net_worth=entry.net_worth,
                recorded_at=entry.recorded_at,
            )
            for entry in summary.history
        ],
    )


@router.post("/user/onboarding", response_model=UserResponse)
async def complete_onboarding(
    body: UserOnboardingCreate,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
) -> UserResponse:
    if is_admin_user(user):
        raise HTTPException(status_code=403, detail="Admin users cannot onboard")

    if user.linked_player_id is not None:
        raise HTTPException(status_code=409, detail="Onboarding already completed")

    game_name, tag_line, display_name = _normalize_player_identity(
        body.game_name,
        body.tag_line,
        body.display_name,
    )

    existing_result = await session.execute(
        select(TrackedPlayer).where(
            TrackedPlayer.game_name == game_name,
            TrackedPlayer.tag_line == tag_line,
        )
    )
    existing_player = existing_result.scalar_one_or_none()
    if existing_player is not None:
        raise HTTPException(status_code=409, detail="Player is already tracked")

    player = TrackedPlayer(
        game_name=game_name,
        tag_line=tag_line,
        display_name=display_name,
    )
    session.add(player)
    await session.flush()

    linked_result = await session.execute(
        select(User).where(User.linked_player_id == player.id)
    )
    already_linked = linked_result.scalar_one_or_none()
    if already_linked is not None:
        raise HTTPException(status_code=409, detail="Player is already linked")

    user.linked_player_id = player.id
    await _initialize_player_market_state(request, session, player)
    await record_user_wealth_snapshot(
        session,
        user,
        source=UserWealthSnapshotSource.ONBOARDING,
        as_of=datetime.now(UTC),
    )
    await session.commit()
    await session.refresh(user)
    return _to_user_response(user)


@router.put("/user/profile", response_model=UserResponse)
async def update_profile(
    body: UserProfileUpdate,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
) -> UserResponse:
    if is_admin_user(user):
        raise HTTPException(
            status_code=403,
            detail="Admin users cannot edit their profile",
        )

    if user.linked_player_id is None:
        raise HTTPException(status_code=403, detail="Complete onboarding first")

    player = await session.get(TrackedPlayer, user.linked_player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Linked player not found")

    game_name, tag_line, display_name = _normalize_player_identity(
        body.game_name,
        body.tag_line,
        body.display_name,
    )

    existing_result = await session.execute(
        select(TrackedPlayer).where(
            TrackedPlayer.game_name == game_name,
            TrackedPlayer.tag_line == tag_line,
            TrackedPlayer.id != player.id,
        )
    )
    existing_player = existing_result.scalar_one_or_none()
    if existing_player is not None:
        raise HTTPException(status_code=409, detail="Player is already tracked")

    player.game_name = game_name
    player.tag_line = tag_line
    player.display_name = display_name

    await _initialize_player_market_state(request, session, player)
    await record_user_wealth_snapshot(
        session,
        user,
        source=UserWealthSnapshotSource.ONBOARDING,
        as_of=datetime.now(UTC),
    )
    await session.commit()
    await session.refresh(user)
    return _to_user_response(user)
