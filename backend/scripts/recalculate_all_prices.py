#!/usr/bin/env python3
"""One-off full price recalculation for all tracked players.

This script exists because the pricing formulas changed significantly and
prices computed under the old formulas need to be thrown away and replayed
from scratch. It is NOT a recurring seasonal tool (use reset_season.py for
that). After running this once, it can be deleted or kept for reference.

What it does:
  1. Backs up the target SQLite DB file.
  2. For each tracked player, fetches the full ranked match history from
     the Riot API since NASHORDAQ_PLAYING_INCOME_START_DATE.
  3. Merges API matches with any already-recorded player_matches rows.
     Existing rows keep their OBSERVED LP deltas; new (backfilled) rows
     use estimated LP deltas derived from the player's avg_lp_gain_on_win
     / avg_lp_loss_on_loss if available, otherwise the --lp-win/--lp-loss
     CLI defaults.
  4. Replays every match chronologically through the current
     calculate_new_price / update_streak formulas, computing playing
     income per match for linked users.
  5. Resets user balances to 1000 + total playing income earned, clears
     holdings/orders/debt/poro state, and re-inserts all replayed data
     (player_matches, price_history, playing_income_entries,
     wealth_snapshots).

Requirements:
  - .env (or env vars) must provide NASHORDAQ_RIOT_API_KEY and other
    required settings, since the script imports app.pricing and app.riot.
  - Run from the backend/ directory so the app package is importable.

Usage:
    uv run python scripts/recalculate_all_prices.py \
        --db-path ../data/nashordaq.db

Options:
    --lp-win   Fallback LP gain per win when no per-player avg (default 21)
    --lp-loss  Fallback LP loss per loss when no per-player avg (default 19)
    --backup-dir  Where to save the pre-run backup (default ./backups)
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

STARTING_BALANCE = 1000.0
RANKED_SOLO_QUEUE_ID = 420
DEFAULT_LP_WIN = 21
DEFAULT_LP_LOSS = 19
API_STAGGER_SECONDS = 2.0
RATE_LIMIT_BACKOFF_SECONDS = 30.0

TABLES_TO_CLEAR = [
    "user_poro_states",
    "poro_spawns",
    "playing_income_entries",
    "user_wealth_snapshots",
    "bank_ledger_entries",
    "gamba_positions",
    "holding_lots",
    "transactions",
    "orders",
    "holdings",
    "price_history",
    "player_matches",
]


# ---------------------------------------------------------------------------
# App imports
# ---------------------------------------------------------------------------


@dataclass
class Implementations:
    settings: Any
    calculate_ipo_price: Any
    calculate_lp_abs: Any
    calculate_new_price: Any
    calculate_win_rate: Any
    update_streak: Any
    get_rank: Any
    get_recent_match_ids: Any
    get_match_summary: Any
    player_not_found_error: type[Exception]
    rate_limited_error: type[Exception]
    # Playing income helpers
    get_playing_income_base_payout: Any
    get_playing_income_daily_multiplier: Any
    get_playing_income_outcome_multiplier: Any
    calculate_playing_income_amount: Any
    round_currency: Any
    start_of_utc_day: Any


def _load_implementations() -> Implementations:
    backend_dir = Path(__file__).resolve().parents[1]
    backend_dir_str = str(backend_dir)
    if backend_dir_str not in sys.path:
        sys.path.insert(0, backend_dir_str)

    from app.banking import (
        calculate_playing_income_amount,
        get_playing_income_base_payout,
        get_playing_income_daily_multiplier,
        get_playing_income_outcome_multiplier,
        round_currency,
        start_of_utc_day,
    )
    from app.config import settings
    from app.pricing import (
        calculate_ipo_price,
        calculate_lp_abs,
        calculate_new_price,
        calculate_win_rate,
        update_streak,
    )
    from app.riot import (
        PlayerNotFoundError,
        RateLimitedError,
        get_match_summary,
        get_rank,
        get_recent_match_ids,
    )

    return Implementations(
        settings=settings,
        calculate_ipo_price=calculate_ipo_price,
        calculate_lp_abs=calculate_lp_abs,
        calculate_new_price=calculate_new_price,
        calculate_win_rate=calculate_win_rate,
        update_streak=update_streak,
        get_rank=get_rank,
        get_recent_match_ids=get_recent_match_ids,
        get_match_summary=get_match_summary,
        player_not_found_error=PlayerNotFoundError,
        rate_limited_error=RateLimitedError,
        get_playing_income_base_payout=get_playing_income_base_payout,
        get_playing_income_daily_multiplier=get_playing_income_daily_multiplier,
        get_playing_income_outcome_multiplier=get_playing_income_outcome_multiplier,
        calculate_playing_income_amount=calculate_playing_income_amount,
        round_currency=round_currency,
        start_of_utc_day=start_of_utc_day,
    )


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ResolvedMatch:
    """A match ready for price replay."""

    match_id: str
    win: bool
    lp_delta: int
    lp_delta_source: str  # "OBSERVED" or "ESTIMATED"
    game_duration_seconds: int
    completed_at: datetime


@dataclass
class ReplayedMatch:
    """A match after price replay - has all snapshot fields."""

    match: ResolvedMatch
    player_id: int
    lp_before: int
    lp_after: int
    streak_before: int
    streak_after: int
    price_before: float
    price_after: float


@dataclass
class PlayingIncomeRecord:
    """A playing income entry to insert."""

    user_id: int
    player_id: int
    match_id: str
    match_result: str  # "WIN" or "LOSS"
    match_duration_seconds: int
    match_completed_at: datetime
    share_price: float
    base_rate: float
    outcome_multiplier: float
    amount: float


@dataclass
class PlayerReplayResult:
    player_id: int
    game_name: str
    tag_line: str
    puuid: str | None
    old_price: float
    new_price: float
    new_streak: int
    new_lp_abs: int
    start_lp: int
    win_rate: float
    match_count: int
    backfilled_count: int
    lp_win_used: int
    lp_loss_used: int
    replayed_matches: list[ReplayedMatch] = field(default_factory=list)
    last_match_completed_at: datetime | None = None


# ---------------------------------------------------------------------------
# Riot API helpers (with stagger + rate-limit backoff)
# ---------------------------------------------------------------------------


def _match_timestamp(summary: Any) -> datetime:
    ts = summary.game_end_timestamp
    if ts > 10_000_000_000:
        ts = ts / 1000
    return datetime.fromtimestamp(ts, tz=UTC)


async def _fetch_all_match_ids(
    impl: Implementations,
    client: httpx.AsyncClient,
    puuid: str,
    start_time: datetime,
) -> list[str]:
    """Page through all ranked match IDs since start_time."""
    page_size = 100
    start = 0
    all_ids: list[str] = []
    use_start_time = True
    use_filters = True

    while True:
        try:
            ids = await impl.get_recent_match_ids(
                client=client,
                base_url=impl.settings.riot_api_base_url,
                api_key=impl.settings.riot_api_key,
                puuid=puuid,
                start=start,
                count=page_size,
                start_time=start_time if use_start_time else None,
                queue=RANKED_SOLO_QUEUE_ID if use_filters else None,
                type="ranked" if use_filters else None,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 400:
                if use_start_time:
                    print(
                        "    Riot rejected filtered startTime; "
                        "falling back to unfiltered paging"
                    )
                    use_start_time = False
                    use_filters = False
                    start = 0
                    all_ids.clear()
                    continue
                print(f"    Riot 400 (unfiltered): {exc.response.text}")
            elif exc.response.status_code in (401, 403):
                print(
                    f"    Riot {exc.response.status_code}: "
                    f"{exc.response.text}\n"
                    "    -> Check NASHORDAQ_RIOT_API_KEY "
                    "(dev keys expire every 24h)"
                )
            raise
        except impl.rate_limited_error:
            backoff = RATE_LIMIT_BACKOFF_SECONDS
            print(f"    Rate limited on match IDs, waiting {backoff}s...")
            await asyncio.sleep(RATE_LIMIT_BACKOFF_SECONDS)
            continue
        if not ids:
            break
        all_ids.extend(ids)
        await asyncio.sleep(API_STAGGER_SECONDS)
        if len(ids) < page_size:
            break
        start += len(ids)

    return all_ids


async def _fetch_match_summaries(
    impl: Implementations,
    client: httpx.AsyncClient,
    puuid: str,
    match_ids: list[str],
    min_duration: int,
) -> list[Any]:
    """Fetch individual match summaries, one at a time with stagger."""
    summaries = []
    for match_id in match_ids:
        try:
            summary = await impl.get_match_summary(
                client=client,
                base_url=impl.settings.riot_api_base_url,
                api_key=impl.settings.riot_api_key,
                puuid=puuid,
                match_id=match_id,
            )
        except impl.player_not_found_error:
            continue
        except impl.rate_limited_error:
            backoff = RATE_LIMIT_BACKOFF_SECONDS
            print(f"    Rate limited, waiting {backoff}s...")
            await asyncio.sleep(RATE_LIMIT_BACKOFF_SECONDS)
            try:
                summary = await impl.get_match_summary(
                    client=client,
                    base_url=impl.settings.riot_api_base_url,
                    api_key=impl.settings.riot_api_key,
                    puuid=puuid,
                    match_id=match_id,
                )
            except (impl.player_not_found_error, impl.rate_limited_error):
                continue

        if summary.queue_id != RANKED_SOLO_QUEUE_ID:
            continue
        if summary.game_duration_seconds < min_duration:
            continue
        summaries.append(summary)
        await asyncio.sleep(API_STAGGER_SECONDS)

    summaries.sort(key=lambda s: s.game_end_timestamp)
    return summaries


# ---------------------------------------------------------------------------
# Per-player LP estimation
# ---------------------------------------------------------------------------
#
# Priority:
#   1. Both DB learned averages available   -> use directly
#   2. One DB average + W+L=40 constraint   -> derive the missing one
#   3. Constraint equation from known LP window (even a short one)
#   4. CLI fallback defaults
#

LP_SUM_CONSTRAINT = 40
LP_ESTIMATE_MIN = 10
LP_ESTIMATE_MAX = 30


def _clamp_lp(value: float) -> int:
    return round(max(LP_ESTIMATE_MIN, min(LP_ESTIMATE_MAX, value)))


def _estimate_lp_from_constraint(
    current_lp: int,
    window_start_lp: int,
    observed_delta: int,
    window_backfill_wins: int,
    window_backfill_losses: int,
) -> tuple[int, int] | None:
    """Estimate per-game LP win/loss using the constraint equation.

    Only uses backfilled matches that fall WITHIN the known LP window
    (from the first DB match to now). The LP change in this window is:

      window_delta = current_lp - window_start_lp
      remaining   = window_delta - observed_delta

    With the constraint W + L = 40:
      W = (remaining + 40 * B) / (A + B)
      L = 40 - W

    Returns (lp_win, lp_loss) or None if unsolvable.
    """
    total = window_backfill_wins + window_backfill_losses
    if total == 0:
        return None

    remaining = (current_lp - window_start_lp) - observed_delta

    w_est = (remaining + LP_SUM_CONSTRAINT * window_backfill_losses) / total
    l_est = LP_SUM_CONSTRAINT - w_est

    return _clamp_lp(w_est), _clamp_lp(l_est)


def _estimate_lp_for_player(
    player: Any,
    db_matches: list[Any],
    new_summaries: list[Any],
    current_lp_abs: int,
    fallback_lp_win: int,
    fallback_lp_loss: int,
) -> tuple[int, int, str]:
    """Determine (lp_win, lp_loss, method) for a player.

    Returns the estimation method name for logging.
    """
    avg_w = player.avg_lp_gain_on_win
    avg_l = player.avg_lp_loss_on_loss
    has_w = avg_w is not None and avg_w > 0
    has_l = avg_l is not None and avg_l > 0

    # Priority 1: both DB averages
    if has_w and has_l:
        return (
            _clamp_lp(avg_w),
            _clamp_lp(avg_l),
            f"DB averages (raw +{avg_w:.1f}/-{avg_l:.1f})",
        )

    # Priority 2: one DB average + constraint
    if has_w and not has_l:
        w_est = _clamp_lp(avg_w)
        l_est = _clamp_lp(LP_SUM_CONSTRAINT - avg_w)
        return w_est, l_est, f"DB avg_win={avg_w:.1f}, derived loss via W+L=40"

    if has_l and not has_w:
        l_est = _clamp_lp(avg_l)
        w_est = _clamp_lp(LP_SUM_CONSTRAINT - avg_l)
        return w_est, l_est, f"DB avg_loss={avg_l:.1f}, derived win via W+L=40"

    # Priority 3: constraint equation from known LP window
    if db_matches and new_summaries:
        window_start_lp = db_matches[0].lp_before
        window_start_at = db_matches[0].completed_at
        if window_start_at.tzinfo is None:
            window_start_at = window_start_at.replace(tzinfo=UTC)

        observed_delta = sum(m.lp_delta for m in db_matches)

        # Only count backfilled matches within the known window
        in_window_wins = 0
        in_window_losses = 0
        for s in new_summaries:
            ts = _match_timestamp(s)
            if ts >= window_start_at:
                if s.win:
                    in_window_wins += 1
                else:
                    in_window_losses += 1

        estimated = _estimate_lp_from_constraint(
            current_lp=current_lp_abs,
            window_start_lp=window_start_lp,
            observed_delta=observed_delta,
            window_backfill_wins=in_window_wins,
            window_backfill_losses=in_window_losses,
        )
        if estimated is not None:
            total_in_window = in_window_wins + in_window_losses
            total_backfill = len(new_summaries)
            return (
                *estimated,
                f"constraint eq ({total_in_window}/{total_backfill} "
                f"in window, LP {window_start_lp}->{current_lp_abs})",
            )

    # Priority 4: CLI fallback
    return (
        fallback_lp_win,
        fallback_lp_loss,
        "fallback defaults",
    )


# ---------------------------------------------------------------------------
# Backfill + merge + replay
# ---------------------------------------------------------------------------


async def _fetch_new_match_summaries(
    impl: Implementations,
    client: httpx.AsyncClient,
    player: Any,
    existing_match_ids: set[str],
) -> list[Any]:
    """Fetch match summaries from API for matches not in DB."""
    if not player.puuid:
        print(f"    {player.game_name}#{player.tag_line}: no puuid, skipping API fetch")
        return []

    start_time = impl.settings.playing_income_start_date
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=UTC)

    min_duration = impl.settings.playing_income_min_match_duration_seconds

    all_ids = await _fetch_all_match_ids(impl, client, player.puuid, start_time)
    new_ids = [mid for mid in all_ids if mid not in existing_match_ids]

    if not new_ids:
        return []

    print(
        f"    {player.game_name}#{player.tag_line}: "
        f"found {len(new_ids)} new matches to backfill"
    )

    return await _fetch_match_summaries(
        impl, client, player.puuid, new_ids, min_duration
    )


def _build_backfilled_matches(
    summaries: list[Any],
    lp_win: int,
    lp_loss: int,
) -> list[ResolvedMatch]:
    """Convert API match summaries to ResolvedMatch with LP deltas."""
    backfilled: list[ResolvedMatch] = []
    for summary in summaries:
        delta = lp_win if summary.win else -lp_loss
        backfilled.append(
            ResolvedMatch(
                match_id=summary.match_id,
                win=summary.win,
                lp_delta=delta,
                lp_delta_source="ESTIMATED",
                game_duration_seconds=summary.game_duration_seconds,
                completed_at=_match_timestamp(summary),
            )
        )
    return backfilled


async def _read_db_data(
    impl: Implementations,
) -> tuple[list[Any], dict[int, list[Any]]]:
    """Read players and existing match history from DB."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from app.models import PlayerMatch, TrackedPlayer

    engine = create_async_engine(impl.settings.database_url, echo=False)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        players = (await session.execute(select(TrackedPlayer))).scalars().all()
        all_matches = (
            (
                await session.execute(
                    select(PlayerMatch).order_by(PlayerMatch.completed_at.asc())
                )
            )
            .scalars()
            .all()
        )

    await engine.dispose()

    matches_by_player: dict[int, list[Any]] = {}
    for m in all_matches:
        matches_by_player.setdefault(m.player_id, []).append(m)

    return players, matches_by_player


def _merge_matches(
    db_matches: list[Any],
    backfilled: list[ResolvedMatch],
) -> list[ResolvedMatch]:
    """Merge DB matches (OBSERVED LP) with backfilled API matches (ESTIMATED).

    DB matches take priority - if a match_id exists in both, the DB version
    with its observed LP delta is kept.
    """
    resolved: dict[str, ResolvedMatch] = {}
    for m in db_matches:
        completed_at = m.completed_at
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=UTC)
        resolved[m.match_id] = ResolvedMatch(
            match_id=m.match_id,
            win=m.win,
            lp_delta=m.lp_delta,
            lp_delta_source=m.lp_delta_source,
            game_duration_seconds=m.game_duration_seconds,
            completed_at=completed_at,
        )

    for m in backfilled:
        if m.match_id not in resolved:
            resolved[m.match_id] = m

    return sorted(resolved.values(), key=lambda m: m.completed_at)


def _replay_player(
    impl: Implementations,
    player: Any,
    matches: list[ResolvedMatch],
    current_lp_abs: int,
    win_rate: float,
    lp_win: int,
    lp_loss: int,
) -> PlayerReplayResult:
    """Replay all matches through current pricing formulas.

    Uses a single pass that produces both the final price AND the
    per-match snapshot data (lp, streak, price before/after).
    """
    backfilled_count = sum(1 for m in matches if m.lp_delta_source == "ESTIMATED")

    if not matches:
        new_price = impl.calculate_ipo_price(current_lp_abs, win_rate)
        return PlayerReplayResult(
            player_id=player.id,
            game_name=player.game_name,
            tag_line=player.tag_line,
            puuid=player.puuid,
            old_price=player.current_price,
            new_price=new_price,
            new_streak=0,
            new_lp_abs=current_lp_abs,
            start_lp=current_lp_abs,
            win_rate=win_rate,
            match_count=0,
            backfilled_count=0,
            lp_win_used=lp_win,
            lp_loss_used=lp_loss,
        )

    # Reconstruct starting LP by reversing net match deltas
    net_delta = sum(m.lp_delta for m in matches)
    start_lp = max(0, current_lp_abs - net_delta)

    price = impl.calculate_ipo_price(start_lp, win_rate)
    streak = 0
    running_lp = start_lp
    replayed: list[ReplayedMatch] = []

    for match in matches:
        lp_before = running_lp
        price_before = price
        streak_before = streak

        running_lp += match.lp_delta
        streak = impl.update_streak(streak, match.lp_delta)
        price = impl.calculate_new_price(price, match.lp_delta, streak)

        replayed.append(
            ReplayedMatch(
                match=match,
                player_id=player.id,
                lp_before=lp_before,
                lp_after=running_lp,
                streak_before=streak_before,
                streak_after=streak,
                price_before=price_before,
                price_after=price,
            )
        )

    return PlayerReplayResult(
        player_id=player.id,
        game_name=player.game_name,
        tag_line=player.tag_line,
        puuid=player.puuid,
        old_price=player.current_price,
        new_price=price,
        new_streak=streak,
        new_lp_abs=running_lp,
        start_lp=start_lp,
        win_rate=win_rate,
        match_count=len(matches),
        backfilled_count=backfilled_count,
        lp_win_used=lp_win,
        lp_loss_used=lp_loss,
        replayed_matches=replayed,
        last_match_completed_at=matches[-1].completed_at if matches else None,
    )


# ---------------------------------------------------------------------------
# Playing income computation
# ---------------------------------------------------------------------------


def _compute_playing_income(
    impl: Implementations,
    results: list[PlayerReplayResult],
    user_player_links: dict[int, int],
) -> tuple[list[PlayingIncomeRecord], dict[int, float]]:
    """Compute playing income for all replayed matches.

    Args:
        results: replay results for all players
        user_player_links: mapping of player_id -> user_id for linked players

    Returns:
        (income_records, user_income_totals) where user_income_totals maps
        user_id -> total income earned.
    """
    income_records: list[PlayingIncomeRecord] = []
    user_income_totals: dict[int, float] = {}

    min_duration = impl.settings.playing_income_min_match_duration_seconds

    for result in results:
        user_id = user_player_links.get(result.player_id)
        if user_id is None:
            continue

        # Track daily match counts for diminishing returns
        daily_match_counts: dict[datetime, int] = {}

        for rm in result.replayed_matches:
            m = rm.match
            if m.game_duration_seconds < min_duration:
                continue

            day_start = impl.start_of_utc_day(m.completed_at)
            match_number = daily_match_counts.get(day_start, 0) + 1

            daily_multiplier = impl.get_playing_income_daily_multiplier(match_number)
            outcome_multiplier = impl.get_playing_income_outcome_multiplier(
                m.win, match_number
            )
            amount = impl.calculate_playing_income_amount(
                rm.price_after,
                outcome_multiplier,
                base_payout=impl.get_playing_income_base_payout(m.win),
                daily_multiplier=daily_multiplier,
            )
            if amount <= 0:
                continue

            daily_match_counts[day_start] = match_number
            user_income_totals[user_id] = user_income_totals.get(user_id, 0.0) + amount
            income_records.append(
                PlayingIncomeRecord(
                    user_id=user_id,
                    player_id=result.player_id,
                    match_id=m.match_id,
                    match_result="WIN" if m.win else "LOSS",
                    match_duration_seconds=m.game_duration_seconds,
                    match_completed_at=m.completed_at,
                    share_price=rm.price_after,
                    base_rate=impl.settings.playing_income_base_rate,
                    outcome_multiplier=outcome_multiplier,
                    amount=amount,
                )
            )

    return income_records, user_income_totals


# ---------------------------------------------------------------------------
# Orchestration: fetch from API, replay, collect results
# ---------------------------------------------------------------------------


async def _backfill_and_replay(
    impl: Implementations,
    lp_win_fallback: int,
    lp_loss_fallback: int,
) -> list[PlayerReplayResult]:
    """Backfill from API and replay all players."""
    players, matches_by_player = await _read_db_data(impl)

    timeout = httpx.Timeout(
        timeout=impl.settings.http_timeout_seconds,
        connect=impl.settings.http_connect_timeout_seconds,
    )

    results: list[PlayerReplayResult] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        for player in players:
            db_matches = matches_by_player.get(player.id, [])
            existing_ids = {m.match_id for m in db_matches}

            # Fetch current rank for accurate win_rate + LP.
            # We MUST get a fresh puuid (old ones break if API key
            # rotated), so retry on rate limit instead of skipping.
            current_lp_abs = player.lp_abs
            win_rate = 0.5
            rank_ok = False
            print(f"  [{player.game_name}#{player.tag_line}] Fetching rank...")
            for _rank_attempt in range(3):
                try:
                    rank_data = await impl.get_rank(
                        client=client,
                        base_url=impl.settings.riot_api_base_url,
                        region_url=impl.settings.riot_api_region_url,
                        api_key=impl.settings.riot_api_key,
                        game_name=player.game_name,
                        tag_line=player.tag_line,
                    )
                    current_lp_abs = impl.calculate_lp_abs(
                        rank_data.tier,
                        rank_data.rank,
                        rank_data.league_points,
                    )
                    win_rate = impl.calculate_win_rate(rank_data.wins, rank_data.losses)
                    if player.puuid != rank_data.puuid:
                        print(
                            f"    Refreshed puuid: "
                            f"{(player.puuid or 'None')[:12]}... "
                            f"-> {rank_data.puuid[:12]}..."
                        )
                        player.puuid = rank_data.puuid
                    print(
                        f"    Rank OK: {rank_data.tier} {rank_data.rank} "
                        f"{rank_data.league_points}LP -> "
                        f"lp_abs={current_lp_abs}, wr={win_rate:.2%}"
                    )
                    rank_ok = True
                    await asyncio.sleep(API_STAGGER_SECONDS)
                    break
                except impl.player_not_found_error:
                    print(f"    rank not found, using stored LP={current_lp_abs}")
                    break
                except impl.rate_limited_error:
                    print(
                        f"    Rate limited on rank, waiting "
                        f"{RATE_LIMIT_BACKOFF_SECONDS}s..."
                    )
                    await asyncio.sleep(RATE_LIMIT_BACKOFF_SECONDS)

            # Fetch new match summaries from API (skip if puuid
            # couldn't be refreshed - stale puuids cause 400s)
            if rank_ok:
                new_summaries = await _fetch_new_match_summaries(
                    impl, client, player, existing_ids
                )
            else:
                print("    Skipping match fetch (no fresh puuid)")
                new_summaries = []

            # Estimate LP deltas for backfilled matches
            lp_win, lp_loss, method = _estimate_lp_for_player(
                player=player,
                db_matches=db_matches,
                new_summaries=new_summaries,
                current_lp_abs=current_lp_abs,
                fallback_lp_win=lp_win_fallback,
                fallback_lp_loss=lp_loss_fallback,
            )
            if new_summaries:
                print(
                    f"    {player.game_name}#{player.tag_line}: "
                    f"LP +{lp_win}/-{lp_loss} ({method})"
                )

            backfilled = _build_backfilled_matches(new_summaries, lp_win, lp_loss)

            # Merge DB + backfilled, replay through pricing formulas
            all_matches = _merge_matches(db_matches, backfilled)
            result = _replay_player(
                impl,
                player,
                all_matches,
                current_lp_abs,
                win_rate,
                lp_win,
                lp_loss,
            )
            results.append(result)

    return results


# ---------------------------------------------------------------------------
# DB mutations (synchronous sqlite3)
# ---------------------------------------------------------------------------


def _backup(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"nashordaq-{timestamp}.db"
    shutil.copy2(db_path, dest)
    print(f"Backup saved to {dest}")
    return dest


def _apply_reset(
    impl: Implementations,
    db_path: Path,
    results: list[PlayerReplayResult],
) -> None:
    """Write all changes to the DB."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    now = datetime.now(UTC).isoformat()

    # -- Read user-player links --
    user_player_links: dict[int, int] = {}  # player_id -> user_id
    for row in conn.execute(
        "SELECT id, linked_player_id FROM users WHERE linked_player_id IS NOT NULL"
    ).fetchall():
        user_player_links[row[1]] = row[0]

    # -- Compute playing income from replayed matches --
    income_records, user_income_totals = _compute_playing_income(
        impl, results, user_player_links
    )

    # -- Reset users (balance = 1000 + playing income earned) --
    conn.execute(
        """
        UPDATE users SET
            balance = ?,
            debt_principal = 0.0,
            debt_accrued_interest = 0.0,
            debt_last_accrued_at = NULL,
            debt_next_accrual_at = NULL,
            rescue_loan_uses_remaining = 1
        """,
        (STARTING_BALANCE,),
    )
    for user_id, income_total in user_income_totals.items():
        final_balance = impl.round_currency(STARTING_BALANCE + income_total)
        conn.execute(
            "UPDATE users SET balance = ? WHERE id = ?",
            (final_balance, user_id),
        )
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    print(f"Reset {user_count} user(s) to base balance {STARTING_BALANCE}")
    for user_id, income_total in sorted(user_income_totals.items()):
        username = conn.execute(
            "SELECT username FROM users WHERE id = ?", (user_id,)
        ).fetchone()[0]
        print(
            f"  {username}: +{income_total:.2f} playing income "
            f"-> {impl.round_currency(STARTING_BALANCE + income_total):.2f}"
        )

    # -- Update tracked players with replayed prices --
    for r in results:
        last_match_at = (
            r.last_match_completed_at.isoformat() if r.last_match_completed_at else None
        )
        # Find the last match_id for playing income tracking
        last_income_match_id = None
        last_income_match_end_at = None
        for ir in reversed(income_records):
            if ir.player_id == r.player_id:
                last_income_match_id = ir.match_id
                last_income_match_end_at = ir.match_completed_at.isoformat()
                break

        conn.execute(
            """
            UPDATE tracked_players SET
                current_price = ?,
                streak = ?,
                lp_abs = ?,
                previous_lp_abs = ?,
                puuid = ?,
                ranked_wins_snapshot = NULL,
                ranked_losses_snapshot = NULL,
                avg_lp_gain_on_win = NULL,
                avg_lp_loss_on_loss = NULL,
                last_updated = ?,
                last_match_pricing_at = ?,
                last_playing_income_match_id = ?,
                last_playing_income_match_end_at = ?
            WHERE id = ?
            """,
            (
                r.new_price,
                r.new_streak,
                r.new_lp_abs,
                r.new_lp_abs,  # previous_lp_abs = lp_abs (no pending delta)
                r.puuid,  # refreshed puuid from API
                now,  # last_updated = now so scheduler knows we're fresh
                last_match_at,
                last_income_match_id,
                last_income_match_end_at,
                r.player_id,
            ),
        )
        if r.match_count == 0:
            label = "IPO"
        else:
            parts = []
            observed = r.match_count - r.backfilled_count
            if observed:
                parts.append(f"{observed} observed")
            if r.backfilled_count:
                parts.append(f"{r.backfilled_count} backfilled")
            label = (
                f"{r.match_count} matches ({', '.join(parts)}), "
                f"lp +{r.lp_win_used}/-{r.lp_loss_used}"
            )
        print(
            f"  {r.game_name}#{r.tag_line}: "
            f"LP_start={r.start_lp}, "
            f"{r.old_price:.2f} -> {r.new_price:.2f}, "
            f"streak={r.new_streak} ({label})"
        )

    # -- Clear transactional tables (player_matches too; we re-insert) --
    for table in TABLES_TO_CLEAR:
        deleted = conn.execute(  # noqa: S608
            f"DELETE FROM {table}"
        ).rowcount
        if deleted:
            print(f"  Cleared {table}: {deleted} row(s)")

    # -- Re-insert all player_matches with correct snapshots --
    total_matches = 0
    for r in results:
        for rm in r.replayed_matches:
            m = rm.match
            conn.execute(
                """
                INSERT INTO player_matches
                    (player_id, match_id, win, lp_before, lp_after,
                     lp_delta, lp_delta_source,
                     streak_before, streak_after,
                     price_before, price_after,
                     game_duration_seconds,
                     completed_at, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r.player_id,
                    m.match_id,
                    m.win,
                    rm.lp_before,
                    rm.lp_after,
                    m.lp_delta,
                    m.lp_delta_source,
                    rm.streak_before,
                    rm.streak_after,
                    rm.price_before,
                    rm.price_after,
                    m.game_duration_seconds,
                    m.completed_at.isoformat(),
                    now,
                ),
            )
            total_matches += 1

    # -- Insert full price_history (one entry per match + IPO seed) --
    total_price_history = 0
    for r in results:
        # Seed: IPO price at start
        ipo_price = impl.calculate_ipo_price(r.start_lp, r.win_rate)
        if r.replayed_matches:
            seed_time = r.replayed_matches[0].match.completed_at - timedelta(seconds=1)
        else:
            seed_time = datetime.now(UTC)
        conn.execute(
            """
            INSERT INTO price_history
                (player_id, price, lp_abs, recorded_at)
            VALUES (?, ?, ?, ?)
            """,
            (r.player_id, ipo_price, r.start_lp, seed_time.isoformat()),
        )
        total_price_history += 1

        # One price_history entry per match
        for rm in r.replayed_matches:
            conn.execute(
                """
                INSERT INTO price_history
                    (player_id, price, lp_abs, recorded_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    r.player_id,
                    rm.price_after,
                    rm.lp_after,
                    rm.match.completed_at.isoformat(),
                ),
            )
            total_price_history += 1

    # -- Insert playing income entries --
    for ir in income_records:
        conn.execute(
            """
            INSERT INTO playing_income_entries
                (user_id, player_id, match_id, match_result,
                 match_duration_seconds, match_completed_at,
                 share_price, base_rate, outcome_multiplier,
                 amount, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ir.user_id,
                ir.player_id,
                ir.match_id,
                ir.match_result,
                ir.match_duration_seconds,
                ir.match_completed_at.isoformat(),
                ir.share_price,
                ir.base_rate,
                ir.outcome_multiplier,
                ir.amount,
                now,
            ),
        )

    # -- Seed one wealth snapshot per user (with playing income included) --
    user_rows = conn.execute("SELECT id FROM users").fetchall()
    for (user_id,) in user_rows:
        balance = conn.execute(
            "SELECT balance FROM users WHERE id = ?", (user_id,)
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO user_wealth_snapshots
                (user_id, source, cash_balance, holdings_value,
                 active_gamba_value, debt_outstanding,
                 net_worth, recorded_at)
            VALUES (?, 'ONBOARDING', ?, 0.0, 0.0, 0.0, ?, ?)
            """,
            (user_id, balance, balance, now),
        )

    conn.commit()
    conn.close()

    print(
        f"\nRecalculation complete: {len(user_rows)} user(s), "
        f"{len(results)} player(s) re-priced, "
        f"{total_matches} match record(s), "
        f"{total_price_history} price_history record(s), "
        f"{len(income_records)} playing_income record(s)."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _run(
    db_path: Path,
    backup_dir: Path,
    lp_win: int,
    lp_loss: int,
) -> None:
    impl = _load_implementations()

    abs_path = db_path.resolve()
    impl.settings.database_url = f"sqlite+aiosqlite:///{abs_path}"

    _backup(db_path, backup_dir)

    print("Fetching match history from Riot API and replaying prices...\n")
    results = asyncio.run(_backfill_and_replay(impl, lp_win, lp_loss))

    _apply_reset(impl, db_path, results)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "One-off full price recalculation: backfill matches "
            "from Riot API and replay through current pricing "
            "formulas. Resets balances and clears trading history."
        )
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        required=True,
        help="Path to the SQLite DB file to recalculate",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path("./backups"),
        help="Where to save pre-run backup (default: ./backups)",
    )
    parser.add_argument(
        "--lp-win",
        type=int,
        default=DEFAULT_LP_WIN,
        help=(
            "Fallback LP gain per win when player has no "
            f"learned average (default: {DEFAULT_LP_WIN})"
        ),
    )
    parser.add_argument(
        "--lp-loss",
        type=int,
        default=DEFAULT_LP_LOSS,
        help=(
            "Fallback LP loss per defeat when player has no "
            f"learned average (default: {DEFAULT_LP_LOSS})"
        ),
    )
    args = parser.parse_args()

    if not args.db_path.exists():
        parser.error(f"DB file not found: {args.db_path}")

    _run(args.db_path, args.backup_dir, args.lp_win, args.lp_loss)


if __name__ == "__main__":
    main()
