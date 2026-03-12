import random

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

ALPHA = 0.15
BETA = 0.1
PRICE_FLOOR = 1.0
WIN_RATE_NEUTRAL = 0.5
WIN_RATE_IPO_WEIGHT = 0.4
WIN_RATE_PRICE_WEIGHT = 0.25
HOT_STREAK_BONUS = 0.15
VETERAN_BONUS = 0.01
FRESH_BLOOD_BONUS = 0.02


def _max_effective_streak() -> int:
    return max(1, settings.pricing_max_effective_streak)


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
    *,
    veteran: bool = False,
    fresh_blood: bool = False,
) -> float:
    base_price = (lp_abs / 100) + 10
    win_rate_premium = max(0.0, win_rate - WIN_RATE_NEUTRAL) * WIN_RATE_IPO_WEIGHT
    status_premium = 0.0
    if veteran:
        status_premium += VETERAN_BONUS
    if fresh_blood:
        status_premium += FRESH_BLOOD_BONUS

    return max(base_price * (1 + win_rate_premium + status_premium), PRICE_FLOOR)


def generate_gamma_base(account_identifier: int) -> float:
    return 1 + ((account_identifier % 100) / 1000)


def generate_epsilon() -> float:
    return random.uniform(-0.03, 0.03)


def calculate_new_price(
    old_price: float,
    delta_lp: int,
    streak: int,
    gamma_base: float,
    *,
    win_rate: float = WIN_RATE_NEUTRAL,
    hot_streak: bool = False,
    veteran: bool = False,
    inactive: bool = False,
    fresh_blood: bool = False,
) -> float:
    if delta_lp == 0:
        return max(old_price, PRICE_FLOOR)

    epsilon = generate_epsilon()
    gamma = gamma_base + epsilon
    effective_streak = min(abs(streak), _max_effective_streak())
    streak_multiplier = 1 + BETA * effective_streak
    if hot_streak:
        streak_multiplier += HOT_STREAK_BONUS

    win_rate_multiplier = 1 + ((win_rate - WIN_RATE_NEUTRAL) * WIN_RATE_PRICE_WEIGHT)
    status_multiplier = 1.0
    if veteran:
        status_multiplier += VETERAN_BONUS
    if fresh_blood:
        status_multiplier += FRESH_BLOOD_BONUS

    new_price = (
        old_price + (delta_lp * ALPHA * streak_multiplier) * gamma * win_rate_multiplier
    ) * status_multiplier

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
