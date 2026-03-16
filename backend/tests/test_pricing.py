import pytest

from app.pricing import (
    calculate_ipo_price,
    calculate_lp_abs,
    calculate_new_price,
    calculate_win_rate,
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


def test_new_price_positive_delta():
    price = calculate_new_price(old_price=20.0, delta_lp=100, streak=0)
    # First +20 LP full; remaining +80 at 25% = 20+20=40 effective.
    # Default dampener 0.85 applied: 40 * 0.85 = 34.
    # 34 * 0.12 * 1.0 = 4.08
    assert price == pytest.approx(24.08)


def test_new_price_negative_delta():
    price = calculate_new_price(old_price=20.0, delta_lp=-50, streak=-1)
    # First -24 full; remaining -26 at 50% = -24 + -13 = -37 effective.
    # Negative: no dampener. streak=-1 -> effective_streak=0 -> mult=1.0.
    # -37 * 0.12 * 1.0 * 1.10 = -4.884
    assert price == pytest.approx(15.116)


def test_price_floor():
    price = calculate_new_price(old_price=2.0, delta_lp=-1000, streak=0)
    assert price == 1.0


def test_new_price_unchanged_without_lp_change():
    price = calculate_new_price(old_price=20.0, delta_lp=0, streak=0)
    assert price == 20.0


def test_streak_positive():
    assert update_streak(0, 10) == 1
    assert update_streak(1, 10) == 2
    assert update_streak(9, 10) == 10


def test_streak_negative():
    assert update_streak(0, -10) == -1
    assert update_streak(-1, -10) == -2
    assert update_streak(-9, -10) == -10


def test_streak_is_capped_in_both_directions():
    assert update_streak(10, 10) == 10
    assert update_streak(-10, -10) == -10


def test_streak_direction_change():
    assert update_streak(3, -10) == -1
    assert update_streak(-3, 10) == 1


def test_streak_no_change():
    assert update_streak(5, 0) == 0
    assert update_streak(-3, 0) == 0


def test_new_price_uses_capped_streak_multiplier():
    price = calculate_new_price(old_price=20.0, delta_lp=100, streak=10)
    # Effective delta: 40, dampener: 0.85 -> 34.
    # Streak=10 -> mult=1+(0.1*10)=2.0.
    # 34 * 0.12 * 2.0 = 8.16
    assert price == pytest.approx(28.16)


def test_new_price_gain_dampener_scales_positive_delta():
    price = calculate_new_price(
        old_price=20.0,
        delta_lp=100,
        streak=10,
        avg_lp_loss_on_loss=10.0,
        avg_lp_gain_on_win=30.0,
    )
    # Effective delta: 40, dampener: clamp(10/30, 0.3, 1.0) = 0.333...
    # 40 * 0.333 = 13.333. Streak mult 2.0. 13.333 * 0.12 * 2.0 = 3.2
    assert price == pytest.approx(23.2)


def test_new_price_gain_dampener_clamped_to_minimum():
    price = calculate_new_price(
        old_price=20.0,
        delta_lp=100,
        streak=10,
        avg_lp_loss_on_loss=2.0,
        avg_lp_gain_on_win=100.0,
    )
    # ratio=0.02, clamped to 0.3. Effective delta: 40 * 0.3 = 12.
    # Streak mult 2.0. 12 * 0.12 * 2.0 = 2.88
    assert price == pytest.approx(22.88)


def test_new_price_gain_dampener_not_applied_to_losses():
    # Losses should NOT be dampened by the gain dampener.
    price_no_avg = calculate_new_price(old_price=20.0, delta_lp=-20, streak=0)
    price_with_avg = calculate_new_price(
        old_price=20.0,
        delta_lp=-20,
        streak=0,
        avg_lp_loss_on_loss=10.0,
        avg_lp_gain_on_win=30.0,
    )
    assert price_no_avg == price_with_avg


def test_new_price_softens_positive_lp_above_threshold_before_pricing():
    price = calculate_new_price(old_price=20.0, delta_lp=30, streak=0)
    # First 20 full + 10 * 0.25 = 22.5 effective. Dampener 0.85 -> 19.125.
    # 19.125 * 0.12 = 2.295
    assert price == pytest.approx(22.295)


def test_new_price_softens_negative_lp_above_threshold_before_loss_bias():
    price = calculate_new_price(old_price=20.0, delta_lp=-30, streak=0)
    # First -24 full + -6 * 0.50 = -27 effective. No dampener on losses.
    # -27 * 0.12 * 1.10 = -3.564
    assert price == pytest.approx(16.436)


def test_new_price_bootstrap_gain_only():
    # Only gain average known; loss bootstrapped as gain - 5.
    price = calculate_new_price(
        old_price=20.0,
        delta_lp=20,
        streak=0,
        avg_lp_gain_on_win=25.0,
    )
    # Bootstrapped loss = 25 - 5 = 20. Ratio = 20/25 = 0.8.
    # 20 * 0.8 = 16. 16 * 0.12 = 1.92
    assert price == pytest.approx(21.92)


def test_new_price_bootstrap_loss_only():
    # Only loss average known; gain bootstrapped as loss + 5.
    price = calculate_new_price(
        old_price=20.0,
        delta_lp=20,
        streak=0,
        avg_lp_loss_on_loss=15.0,
    )
    # Bootstrapped gain = 15 + 5 = 20. Ratio = 15/20 = 0.75.
    # 20 * 0.75 = 15. 15 * 0.12 = 1.8
    assert price == pytest.approx(21.8)
