from app.config import settings

TIER_MAP: dict[str, int] = {
    "IRON": 0,
    "BRONZE": 1,
    "SILVER": 2,
    "GOLD": 3,
    "PLATINUM": 4,
    "EMERALD": 5,
    "DIAMOND": 6,
    "MASTER": 7,
    "GRANDMASTER": 7,
    "CHALLENGER": 7,
}

DIVISION_MAP: dict[str, int] = {
    "IV": 0,
    "III": 1,
    "II": 2,
    "I": 3,
}

BETA = 0.1
PRICE_FLOOR = 1.0
WIN_RATE_NEUTRAL = 0.5
WIN_RATE_IPO_WEIGHT = 0.4


def _max_effective_streak() -> int:
    return max(1, settings.pricing_max_effective_streak)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _lp_gain_dampener(
    avg_lp_loss_on_loss: float | None,
    avg_lp_gain_on_win: float | None,
) -> float:
    has_loss = avg_lp_loss_on_loss is not None and avg_lp_loss_on_loss > 0
    has_gain = avg_lp_gain_on_win is not None and avg_lp_gain_on_win > 0
    offset = settings.pricing_lp_ratio_bootstrap_offset

    if has_loss and has_gain:
        raw_ratio = avg_lp_loss_on_loss / avg_lp_gain_on_win
    elif has_gain and not has_loss:
        bootstrapped_loss = max(1.0, avg_lp_gain_on_win - offset)
        raw_ratio = bootstrapped_loss / avg_lp_gain_on_win
    elif has_loss and not has_gain:
        bootstrapped_gain = avg_lp_loss_on_loss + offset
        raw_ratio = avg_lp_loss_on_loss / bootstrapped_gain
    else:
        return settings.pricing_win_streak_lp_ratio_default

    return _clamp(
        raw_ratio,
        settings.pricing_win_streak_lp_ratio_min,
        settings.pricing_win_streak_lp_ratio_max,
    )


def _apply_lp_efficiency(delta_lp: int) -> float:
    if delta_lp > 0:
        capped_component = min(delta_lp, settings.pricing_positive_lp_soft_cap)
        excess_component = max(0, delta_lp - settings.pricing_positive_lp_soft_cap)
        return capped_component + (
            excess_component * settings.pricing_positive_lp_excess_efficiency
        )
    if delta_lp < 0:
        capped_component = max(delta_lp, -settings.pricing_negative_lp_soft_cap)
        excess_component = min(0, delta_lp + settings.pricing_negative_lp_soft_cap)
        return capped_component + (
            excess_component * settings.pricing_negative_lp_excess_efficiency
        )
    return 0


def calculate_lp_abs(tier: str, rank: str, league_points: int) -> int:
    t = TIER_MAP.get(tier.upper(), 0)
    d = DIVISION_MAP.get(rank.upper(), 3) if t < 7 else 3
    return (t * 400) + (d * 100) + league_points


def calculate_win_rate(wins: int, losses: int) -> float:
    total_games = max(0, wins) + max(0, losses)
    if total_games == 0:
        return WIN_RATE_NEUTRAL
    return max(0.0, min(1.0, wins / total_games))


def calculate_ipo_price(
    lp_abs: int,
    win_rate: float = WIN_RATE_NEUTRAL,
) -> float:
    base_price = (lp_abs / 100) + 10
    win_rate_premium = max(0.0, win_rate - WIN_RATE_NEUTRAL) * WIN_RATE_IPO_WEIGHT

    return max(base_price * (1 + win_rate_premium), PRICE_FLOOR)


def calculate_new_price(
    old_price: float,
    delta_lp: int,
    streak: int,
    *,
    avg_lp_loss_on_loss: float | None = None,
    avg_lp_gain_on_win: float | None = None,
) -> float:
    if delta_lp == 0:
        return max(old_price, PRICE_FLOOR)

    effective_delta_lp = _apply_lp_efficiency(delta_lp)

    if effective_delta_lp > 0:
        gain_dampener = _lp_gain_dampener(avg_lp_loss_on_loss, avg_lp_gain_on_win)
        effective_delta_lp *= gain_dampener

    effective_streak = min(max(0, streak), _max_effective_streak())
    streak_multiplier = 1 + (BETA * effective_streak)

    lp_move = effective_delta_lp * settings.pricing_alpha * streak_multiplier
    if effective_delta_lp < 0:
        lp_move *= settings.pricing_loss_move_multiplier

    new_price = old_price + lp_move

    return max(new_price, PRICE_FLOOR)


def update_streak(old_streak: int, delta_lp: int) -> int:
    max_effective_streak = _max_effective_streak()

    if delta_lp > 0:
        return min((old_streak + 1) if old_streak >= 0 else 1, max_effective_streak)
    elif delta_lp < 0:
        return max(
            (old_streak - 1) if old_streak <= 0 else -1,
            -max_effective_streak,
        )
    return 0


def calculate_sell_multiplier(
    held_hours: float,
    short_hold_fee_rate: float,
    short_hold_fee_window_hours: float,
    long_hold_bonus_rate: float,
    long_hold_bonus_start_hours: float,
) -> float:
    safe_held_hours = max(0.0, held_hours)

    if (
        short_hold_fee_window_hours > 0
        and safe_held_hours < short_hold_fee_window_hours
    ):
        remaining_ratio = 1 - (safe_held_hours / short_hold_fee_window_hours)
        return 1 - (short_hold_fee_rate * remaining_ratio)

    if safe_held_hours >= long_hold_bonus_start_hours:
        return 1 + long_hold_bonus_rate

    return 1.0
