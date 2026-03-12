from __future__ import annotations

import argparse
import asyncio
import random
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

RANKED_SOLO_QUEUE_ID = 420
DEFAULT_GAME_NAME = "W2B Luchacho"
DEFAULT_TAG_LINE = "W2BLZ"


@dataclass
class ReplayResult:
    start_lp_abs: int
    end_lp_abs: int
    reconstructed_price: float
    reconstructed_streak: int
    considered_matches: list[Any]
    net_lp_delta_from_matches: int


@dataclass
class Implementations:
    settings: Any
    calculate_ipo_price: Any
    calculate_lp_abs: Any
    calculate_new_price: Any
    calculate_win_rate: Any
    generate_gamma_base: Any
    update_streak: Any
    get_match_summary: Any
    get_rank: Any
    get_recent_match_ids: Any
    player_not_found_error: type[Exception]


def _load_implementations() -> Implementations:
    backend_dir = Path(__file__).resolve().parents[1]
    backend_dir_str = str(backend_dir)
    if backend_dir_str not in sys.path:
        sys.path.insert(0, backend_dir_str)

    from app.config import settings
    from app.pricing import (
        calculate_ipo_price,
        calculate_lp_abs,
        calculate_new_price,
        calculate_win_rate,
        generate_gamma_base,
        update_streak,
    )
    from app.riot import (
        PlayerNotFoundError,
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
        generate_gamma_base=generate_gamma_base,
        update_streak=update_streak,
        get_match_summary=get_match_summary,
        get_rank=get_rank,
        get_recent_match_ids=get_recent_match_ids,
        player_not_found_error=PlayerNotFoundError,
    )


def _parse_args(*, min_duration_default: int) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recalculate a player's current price by replaying ranked match "
            "outcomes since NASHORDAQ_PLAYING_INCOME_START_DATE."
        )
    )
    parser.add_argument("--game-name", default=DEFAULT_GAME_NAME)
    parser.add_argument("--tag-line", default=DEFAULT_TAG_LINE)
    parser.add_argument(
        "--lp-win",
        type=int,
        default=20,
        help="Assumed LP gain per win during replay (default: 20).",
    )
    parser.add_argument(
        "--lp-loss",
        type=int,
        default=20,
        help="Assumed LP loss per defeat during replay (default: 20).",
    )
    parser.add_argument(
        "--min-duration-seconds",
        type=int,
        default=min_duration_default,
        help=(
            "Ignore matches shorter than this duration (default follows playing income "
            "minimum duration)."
        ),
    )
    parser.add_argument(
        "--current-price",
        type=float,
        default=None,
        help="Optional currently stored price for comparison output.",
    )
    parser.add_argument(
        "--current-streak",
        type=int,
        default=None,
        help="Optional currently stored streak for comparison output.",
    )
    parser.add_argument(
        "--gamma-factor",
        type=float,
        default=None,
        help="Optional gamma_factor override. Defaults to generated value from puuid.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1337,
        help="Seed for random epsilon used by calculate_new_price (default: 1337).",
    )
    return parser.parse_args()


def _match_timestamp(summary: Any) -> datetime:
    timestamp = summary.game_end_timestamp
    if timestamp > 10_000_000_000:
        timestamp = timestamp / 1000
    return datetime.fromtimestamp(timestamp, tz=UTC)


async def _fetch_match_summaries(
    impl: Implementations,
    client: httpx.AsyncClient,
    puuid: str,
    *,
    start_time: datetime,
    min_duration_seconds: int,
) -> list[Any]:
    page_size = 100
    start = 0
    match_ids: list[str] = []

    while True:
        page = await impl.get_recent_match_ids(
            client=client,
            base_url=impl.settings.riot_api_base_url,
            api_key=impl.settings.riot_api_key,
            puuid=puuid,
            start=start,
            count=page_size,
            start_time=start_time,
            queue=RANKED_SOLO_QUEUE_ID,
            type="ranked",
        )
        if not page:
            break
        match_ids.extend(page)
        if len(page) < page_size:
            break
        start += len(page)

    summaries: list[Any] = []
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
            # Some match payloads can omit/lose the expected participant entry.
            continue
        if summary.queue_id != RANKED_SOLO_QUEUE_ID:
            continue
        if summary.game_duration_seconds < min_duration_seconds:
            continue
        if _match_timestamp(summary) < start_time:
            continue
        summaries.append(summary)

    summaries.sort(key=lambda item: item.game_end_timestamp)
    return summaries


def _replay_price(
    impl: Implementations,
    *,
    current_lp_abs: int,
    win_rate: float,
    gamma_factor: float,
    matches: list[Any],
    lp_win: int,
    lp_loss: int,
) -> ReplayResult:
    lp_deltas = [lp_win if match.win else -lp_loss for match in matches]
    net_delta = sum(lp_deltas)

    # Reconstruct LP at the configured start date by reversing the match outcome deltas.
    start_lp_abs = max(0, current_lp_abs - net_delta)
    reconstructed_lp_abs = start_lp_abs
    reconstructed_streak = 0
    reconstructed_price = impl.calculate_ipo_price(start_lp_abs, win_rate)

    for delta_lp in lp_deltas:
        reconstructed_lp_abs += delta_lp
        reconstructed_streak = impl.update_streak(reconstructed_streak, delta_lp)
        reconstructed_price = impl.calculate_new_price(
            reconstructed_price,
            delta_lp,
            reconstructed_streak,
            gamma_factor,
            win_rate=win_rate,
            inactive=False,
        )

    return ReplayResult(
        start_lp_abs=start_lp_abs,
        end_lp_abs=reconstructed_lp_abs,
        reconstructed_price=reconstructed_price,
        reconstructed_streak=reconstructed_streak,
        considered_matches=matches,
        net_lp_delta_from_matches=net_delta,
    )


async def _run() -> None:
    impl = _load_implementations()
    args = _parse_args(
        min_duration_default=impl.settings.playing_income_min_match_duration_seconds
    )
    random.seed(args.seed)

    start_time = impl.settings.playing_income_start_date
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=UTC)
    else:
        start_time = start_time.astimezone(UTC)

    timeout = httpx.Timeout(
        timeout=impl.settings.http_timeout_seconds,
        connect=impl.settings.http_connect_timeout_seconds,
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        rank_data = await impl.get_rank(
            client=client,
            base_url=impl.settings.riot_api_base_url,
            region_url=impl.settings.riot_api_region_url,
            api_key=impl.settings.riot_api_key,
            game_name=args.game_name,
            tag_line=args.tag_line,
        )

        current_lp_abs = impl.calculate_lp_abs(
            rank_data.tier,
            rank_data.rank,
            rank_data.league_points,
        )
        win_rate = impl.calculate_win_rate(rank_data.wins, rank_data.losses)

        match_summaries = await _fetch_match_summaries(
            impl,
            client,
            rank_data.puuid,
            start_time=start_time,
            min_duration_seconds=args.min_duration_seconds,
        )

    gamma_factor = (
        args.gamma_factor
        if args.gamma_factor is not None
        else impl.generate_gamma_base(hash(rank_data.puuid) % 10000)
    )

    replay = _replay_price(
        impl,
        current_lp_abs=current_lp_abs,
        win_rate=win_rate,
        gamma_factor=gamma_factor,
        matches=match_summaries,
        lp_win=args.lp_win,
        lp_loss=args.lp_loss,
    )

    print("=== Nashordaq Price Recalculation (Standalone) ===")
    print(f"Player: {args.game_name}#{args.tag_line}")
    print(f"Configured start: {start_time.isoformat()}")
    print(
        "Assumed LP deltas: "
        f"win=+{args.lp_win}, loss=-{args.lp_loss}, "
        f"min_duration={args.min_duration_seconds}s"
    )
    print(f"Random seed: {args.seed}")
    print(f"Gamma factor used: {gamma_factor:.6f}")
    print(f"Matches considered: {len(replay.considered_matches)}")
    print(f"Current Riot LP_abs: {current_lp_abs}")
    print(f"Reconstructed LP_abs at start: {replay.start_lp_abs}")
    print(
        f"Net LP delta from considered matches: {replay.net_lp_delta_from_matches:+d}"
    )
    print(f"Replay end LP_abs: {replay.end_lp_abs}")
    print(f"Reconstructed current price: {replay.reconstructed_price:.4f}")
    print(f"Reconstructed streak: {replay.reconstructed_streak}")

    if args.current_price is not None:
        print(f"Provided current price: {args.current_price:.4f}")
        print(
            "Price delta (reconstructed - provided): "
            f"{replay.reconstructed_price - args.current_price:+.4f}"
        )

    if args.current_streak is not None:
        print(f"Provided current streak: {args.current_streak}")
        print(
            "Streak delta (reconstructed - provided): "
            f"{replay.reconstructed_streak - args.current_streak:+d}"
        )

    if replay.considered_matches:
        first_match_at = _match_timestamp(replay.considered_matches[0]).isoformat()
        last_match_at = _match_timestamp(replay.considered_matches[-1]).isoformat()
        print(f"Match window: {first_match_at} -> {last_match_at}")

    if replay.end_lp_abs != current_lp_abs:
        print(
            "WARNING: Replayed end LP_abs does not match current Riot LP_abs. "
            "Adjust --lp-win/--lp-loss assumptions."
        )


if __name__ == "__main__":
    asyncio.run(_run())
