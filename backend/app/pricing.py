import random

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


def calculate_lp_abs(tier: str, rank: str, league_points: int) -> int:
    t = TIER_MAP.get(tier.upper(), 0)
    d = DIVISION_MAP.get(rank.upper(), 3) if t < 7 else 3
    return (t * 400) + (d * 100) + league_points


def calculate_ipo_price(lp_abs: int) -> float:
    return (lp_abs / 100) + 10


def generate_gamma_base(account_identifier: int) -> float:
    return 1 + ((account_identifier % 100) / 1000)


def generate_epsilon() -> float:
    return random.uniform(-0.03, 0.03)


def calculate_new_price(
    old_price: float,
    delta_lp: int,
    streak: int,
    gamma_base: float,
) -> float:
    epsilon = generate_epsilon()
    gamma = gamma_base + epsilon
    new_price = old_price + (delta_lp * ALPHA * (1 + BETA * abs(streak))) * gamma
    return max(new_price, PRICE_FLOOR)


def update_streak(old_streak: int, delta_lp: int) -> int:
    if delta_lp > 0:
        return (old_streak + 1) if old_streak >= 0 else 1
    elif delta_lp < 0:
        return (old_streak - 1) if old_streak <= 0 else -1
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
