from unittest.mock import patch

import pytest

from app.pricing import (
    calculate_ipo_price,
    calculate_lp_abs,
    calculate_new_price,
    calculate_sell_multiplier,
    calculate_win_rate,
    generate_gamma_base,
    update_streak,
)


def test_lp_abs_iron_iv_0():
    assert calculate_lp_abs("IRON", "IV", 0) == 0


def test_lp_abs_gold_ii_75():
    # T=3, D=2 -> 3*400 + 2*100 + 75 = 1475
    assert calculate_lp_abs("GOLD", "II", 75) == 1475


def test_lp_abs_diamond_i_99():
    # T=6, D=3 -> 6*400 + 3*100 + 99 = 2799
    assert calculate_lp_abs("DIAMOND", "I", 99) == 2799


def test_lp_abs_master_plus():
    # Master+ all map to T=7, D=3 -> 7*400 + 3*100 + LP
    assert calculate_lp_abs("MASTER", "I", 0) == 3100
    assert calculate_lp_abs("GRANDMASTER", "I", 500) == 3600
    assert calculate_lp_abs("CHALLENGER", "I", 1200) == 4300


def test_lp_abs_case_insensitive():
    assert calculate_lp_abs("gold", "ii", 50) == calculate_lp_abs("GOLD", "II", 50)


def test_ipo_price():
    assert calculate_ipo_price(0) == 10.0
    assert calculate_ipo_price(1000) == 20.0
    assert calculate_ipo_price(3100) == 41.0


def test_win_rate():
    assert calculate_win_rate(0, 0) == 0.5
    assert calculate_win_rate(7, 3) == 0.7


def test_ipo_price_with_win_rate_bonus():
    price = calculate_ipo_price(1000, 0.7)
    assert price == pytest.approx(21.6)


def test_gamma_base():
    assert generate_gamma_base(0) == 1.0
    assert generate_gamma_base(50) == 1.05
    assert generate_gamma_base(99) == 1.099
    assert generate_gamma_base(100) == 1.0  # wraps at 100


def test_new_price_positive_delta():
    with patch("app.pricing.generate_epsilon", return_value=0.0):
        price = calculate_new_price(
            old_price=20.0, delta_lp=100, streak=0, gamma_base=1.0
        )
    # First +20 LP are full strength; the remaining +80 LP apply at 25% efficiency.
    assert price == pytest.approx(24.8)


def test_new_price_negative_delta():
    with patch("app.pricing.generate_epsilon", return_value=0.0):
        price = calculate_new_price(
            old_price=20.0, delta_lp=-50, streak=-1, gamma_base=1.0
        )
    # First -24 LP are full strength; the remaining -26 LP apply at 50% efficiency.
    assert price == pytest.approx(14.6276)


def test_price_floor():
    with patch("app.pricing.generate_epsilon", return_value=0.0):
        price = calculate_new_price(
            old_price=2.0, delta_lp=-1000, streak=0, gamma_base=1.0
        )
    assert price == 1.0


def test_new_price_with_win_rate_and_hot_streak_modifiers():
    with patch("app.pricing.generate_epsilon", return_value=0.0):
        price = calculate_new_price(
            old_price=20.0,
            delta_lp=100,
            streak=0,
            gamma_base=1.0,
            win_rate=0.7,
            hot_streak=True,
        )

    assert price == pytest.approx(25.292)


def test_new_price_unchanged_without_lp_change():
    with patch("app.pricing.generate_epsilon", return_value=0.0):
        price = calculate_new_price(
            old_price=20.0,
            delta_lp=0,
            streak=0,
            gamma_base=1.0,
            inactive=True,
        )

    assert price == 20.0


def test_streak_positive():
    assert update_streak(0, 10) == 1
    assert update_streak(1, 10) == 2
    assert update_streak(3, 10) == 4


def test_streak_negative():
    assert update_streak(0, -10) == -1
    assert update_streak(-1, -10) == -2
    assert update_streak(-3, -10) == -4


def test_streak_is_capped_in_both_directions():
    assert update_streak(4, 10) == 4
    assert update_streak(-4, -10) == -4


def test_streak_direction_change():
    assert update_streak(3, -10) == -1
    assert update_streak(-3, 10) == 1


def test_streak_no_change():
    assert update_streak(5, 0) == 0
    assert update_streak(-3, 0) == 0


def test_new_price_uses_capped_streak_multiplier():
    with patch("app.pricing.generate_epsilon", return_value=0.0):
        price = calculate_new_price(
            old_price=20.0,
            delta_lp=100,
            streak=10,
            gamma_base=1.0,
        )

    assert price == pytest.approx(26.72)


def test_new_price_softens_positive_lp_above_threshold_before_pricing():
    with patch("app.pricing.generate_epsilon", return_value=0.0):
        price = calculate_new_price(
            old_price=20.0,
            delta_lp=30,
            streak=0,
            gamma_base=1.0,
        )

    assert price == pytest.approx(22.7)


def test_new_price_softens_negative_lp_above_threshold_before_loss_bias():
    with patch("app.pricing.generate_epsilon", return_value=0.0):
        price = calculate_new_price(
            old_price=20.0,
            delta_lp=-30,
            streak=0,
            gamma_base=1.0,
        )

    assert price == pytest.approx(16.436)


def test_sell_multiplier_short_hold_penalty():
    multiplier = calculate_sell_multiplier(
        held_hours=0,
        short_hold_fee_rate=0.02,
        short_hold_fee_window_hours=6,
        long_hold_bonus_rate=0.02,
        long_hold_bonus_start_hours=12,
    )
    assert multiplier == 0.98


def test_sell_multiplier_no_adjustment_mid_window():
    multiplier = calculate_sell_multiplier(
        held_hours=8,
        short_hold_fee_rate=0.02,
        short_hold_fee_window_hours=6,
        long_hold_bonus_rate=0.02,
        long_hold_bonus_start_hours=12,
    )
    assert multiplier == 1.0


def test_sell_multiplier_long_hold_bonus():
    multiplier = calculate_sell_multiplier(
        held_hours=12,
        short_hold_fee_rate=0.02,
        short_hold_fee_window_hours=6,
        long_hold_bonus_rate=0.02,
        long_hold_bonus_start_hours=12,
    )
    assert multiplier == 1.02
