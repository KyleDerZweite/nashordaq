"""Unit tests for _attribute_lp_to_matches (LP attribution logic)."""

from app.models import PlayerMatchLpSource
from app.riot import MatchSummary
from app.scheduler import _attribute_lp_to_matches


def _make_summary(match_id: str, win: bool, ts: int = 0) -> MatchSummary:
    return MatchSummary(
        match_id=match_id,
        queue_id=420,
        win=win,
        game_duration_seconds=1800,
        game_end_timestamp=ts,
    )


def test_single_match_observed():
    result = _attribute_lp_to_matches(
        20,
        [_make_summary("M1", True)],
        avg_lp_gain=None,
        avg_lp_loss=None,
    )
    assert len(result) == 1
    assert result[0][1] == 20
    assert result[0][2] == PlayerMatchLpSource.OBSERVED


def test_two_wins_split_evenly():
    result = _attribute_lp_to_matches(
        40,
        [_make_summary("M1", True), _make_summary("M2", True)],
        avg_lp_gain=None,
        avg_lp_loss=None,
    )
    assert len(result) == 2
    assert result[0][1] == 20
    assert result[1][1] == 20
    assert all(r[2] == PlayerMatchLpSource.ESTIMATED for r in result)


def test_two_losses_split_evenly():
    result = _attribute_lp_to_matches(
        -36,
        [_make_summary("M1", False), _make_summary("M2", False)],
        avg_lp_gain=None,
        avg_lp_loss=None,
    )
    assert len(result) == 2
    assert result[0][1] == -18
    assert result[1][1] == -18


def test_odd_split_distributes_remainder():
    result = _attribute_lp_to_matches(
        41,
        [_make_summary("M1", True), _make_summary("M2", True)],
        avg_lp_gain=None,
        avg_lp_loss=None,
    )
    assert result[0][1] + result[1][1] == 41
    assert result[0][1] == 21  # first gets remainder
    assert result[1][1] == 20


def test_mixed_direction_uses_averages():
    # 1 win + 1 loss, total delta +5, avg_gain=22, avg_loss=17
    result = _attribute_lp_to_matches(
        5,
        [_make_summary("M1", False, 100), _make_summary("M2", True, 200)],
        avg_lp_gain=22.0,
        avg_lp_loss=17.0,
    )
    assert len(result) == 2
    # Loss should be negative, win should be positive
    assert result[0][1] < 0  # loss
    assert result[1][1] > 0  # win
    # Sum should equal total delta
    assert result[0][1] + result[1][1] == 5


def test_empty_summaries_returns_empty():
    result = _attribute_lp_to_matches(
        20,
        [],
        avg_lp_gain=None,
        avg_lp_loss=None,
    )
    assert result == []
