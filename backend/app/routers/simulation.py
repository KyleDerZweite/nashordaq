from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models import PlayerMatch, TrackedPlayer
from app.schemas import (
    SimulationDefaultsResponse,
    SimulationMatch,
    SimulationParameterSet,
    SimulationPlayerMatchResponse,
    SimulationRequest,
    SimulationResponse,
    SimulationStep,
    SimulationTrajectory,
)

router = APIRouter(prefix="/simulate", tags=["simulation"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

BETA = 0.1
PRICE_FLOOR = 1.0

_PARAM_KEYS = [
    "pricing_alpha",
    "pricing_loss_move_multiplier",
    "pricing_max_effective_streak",
    "pricing_positive_lp_soft_cap",
    "pricing_negative_lp_soft_cap",
    "pricing_positive_lp_excess_efficiency",
    "pricing_negative_lp_excess_efficiency",
    "pricing_win_streak_lp_ratio_default",
]


def _resolve_params(override: SimulationParameterSet) -> dict[str, float | int]:
    defaults = {k: getattr(settings, k) for k in _PARAM_KEYS}
    for key in _PARAM_KEYS:
        value = getattr(override, key, None)
        if value is not None:
            defaults[key] = value
    return defaults


def _lp_efficiency(delta_lp: int, params: dict[str, float | int]) -> float:
    if delta_lp > 0:
        cap = int(params["pricing_positive_lp_soft_cap"])
        eff = float(params["pricing_positive_lp_excess_efficiency"])
        return min(delta_lp, cap) + max(0, delta_lp - cap) * eff
    if delta_lp < 0:
        cap = int(params["pricing_negative_lp_soft_cap"])
        eff = float(params["pricing_negative_lp_excess_efficiency"])
        return max(delta_lp, -cap) + min(0, delta_lp + cap) * eff
    return 0


def _update_streak(old: int, delta_lp: int, max_streak: int) -> int:
    if delta_lp > 0:
        return min((old + 1) if old >= 0 else 1, max_streak)
    if delta_lp < 0:
        return max((old - 1) if old <= 0 else -1, -max_streak)
    return 0


def _compute_step(
    price: float,
    streak: int,
    delta_lp: int,
    params: dict[str, float | int],
) -> tuple[float, float, float, float]:
    """Returns (new_price, effective_delta_lp, streak_multiplier, price_move)."""
    if delta_lp == 0:
        return price, 0.0, 1.0, 0.0

    eff_lp = _lp_efficiency(delta_lp, params)

    if eff_lp > 0:
        eff_lp *= float(params["pricing_win_streak_lp_ratio_default"])

    max_streak = max(1, int(params["pricing_max_effective_streak"]))
    eff_streak = min(max(0, streak), max_streak)
    streak_mult = 1 + (BETA * eff_streak)

    move = eff_lp * float(params["pricing_alpha"]) * streak_mult
    if eff_lp < 0:
        move *= float(params["pricing_loss_move_multiplier"])

    new_price = max(price + move, PRICE_FLOOR)
    return new_price, eff_lp, streak_mult, new_price - price


def _run_trajectory(
    matches: list[SimulationMatch],
    starting_price: float,
    starting_streak: int,
    param_set: SimulationParameterSet,
) -> SimulationTrajectory:
    params = _resolve_params(param_set)
    max_streak = max(1, int(params["pricing_max_effective_streak"]))
    price = starting_price
    streak = starting_streak
    steps: list[SimulationStep] = []

    for i, match in enumerate(matches):
        streak_after = _update_streak(streak, match.delta_lp, max_streak)
        new_price, eff_lp, streak_mult, move = _compute_step(
            price, streak_after, match.delta_lp, params
        )
        steps.append(
            SimulationStep(
                match_index=i,
                delta_lp=match.delta_lp,
                win=match.win,
                streak_before=streak,
                streak_after=streak_after,
                price_before=round(price, 4),
                price_after=round(new_price, 4),
                effective_delta_lp=round(eff_lp, 4),
                streak_multiplier=round(streak_mult, 4),
                price_move=round(move, 4),
            )
        )
        streak = streak_after
        price = new_price

    return SimulationTrajectory(
        label=param_set.label,
        parameters=params,
        steps=steps,
    )


@router.get("/defaults", response_model=SimulationDefaultsResponse)
async def get_defaults() -> SimulationDefaultsResponse:
    return SimulationDefaultsResponse(**{k: getattr(settings, k) for k in _PARAM_KEYS})


@router.get(
    "/players/{player_id}/matches",
    response_model=list[SimulationPlayerMatchResponse],
)
async def get_player_matches(
    player_id: int,
    session: SessionDep,
) -> list[SimulationPlayerMatchResponse]:
    player = await session.get(TrackedPlayer, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")

    result = await session.execute(
        select(PlayerMatch)
        .where(PlayerMatch.player_id == player_id)
        .order_by(PlayerMatch.completed_at.asc())
    )
    matches = result.scalars().all()

    return [
        SimulationPlayerMatchResponse(
            match_id=m.match_id,
            win=m.win,
            lp_delta=m.lp_delta,
            streak_before=m.streak_before,
            streak_after=m.streak_after,
            price_before=m.price_before,
            price_after=m.price_after,
            completed_at=m.completed_at,
        )
        for m in matches
    ]


@router.post("", response_model=SimulationResponse)
async def run_simulation(
    body: SimulationRequest,
    session: SessionDep,
) -> SimulationResponse:
    if body.matches is not None and body.player_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Provide either matches or player_id, not both",
        )

    matches: list[SimulationMatch]
    starting_price = body.starting_price
    starting_streak = body.starting_streak

    if body.player_id is not None:
        player = await session.get(TrackedPlayer, body.player_id)
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")

        result = await session.execute(
            select(PlayerMatch)
            .where(PlayerMatch.player_id == body.player_id)
            .order_by(PlayerMatch.completed_at.asc())
        )
        player_matches = result.scalars().all()
        if not player_matches:
            raise HTTPException(
                status_code=400, detail="No match history for this player"
            )

        starting_price = player_matches[0].price_before
        starting_streak = player_matches[0].streak_before
        matches = [
            SimulationMatch(delta_lp=m.lp_delta, win=m.win) for m in player_matches
        ]
    elif body.matches is not None:
        matches = body.matches
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either matches or player_id",
        )

    if len(matches) > 500:
        raise HTTPException(
            status_code=400, detail="Maximum 500 matches per simulation"
        )

    results = [
        _run_trajectory(matches, starting_price, starting_streak, ps)
        for ps in body.parameter_sets
    ]

    return SimulationResponse(results=results)
