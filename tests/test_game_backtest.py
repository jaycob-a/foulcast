"""
Tests for the game-level backtest metrics.

These cover the honest-metrics rewrite: the side-split comparison is gone
(Statcast does not record which side a foul lands on, so its "actual" value
was an assumption), the per-batter correlation is really computed by joining
on MLB player ID, and predicted vs actual total fouls per game exists.

compare_game() is exercised on synthetic events so it runs without a Statcast
pull; the batter_id plumbing is checked against a real prediction run.
"""
import numpy as np
import pandas as pd
import pytest

from foulball.batter_profiles import YANKEES_2024_PROFILES
from foulball.matchup_engine import FoulBallEvent, predict_game_fouls
from foulball.stadium import STADIUMS

from game_backtest import compare_game, safe_pearson

STANDARD_RHP_MIX = {'FF': 0.30, 'SL': 0.20, 'CH': 0.15, 'SI': 0.15, 'CU': 0.10, 'FC': 0.10}


def make_event(batter_id, weight, distance=120.0, pitch_type='FF', section='SEC'):
    """A FoulBallEvent carrying only the fields compare_game reads."""
    return FoulBallEvent(
        batter_name=f'Player {batter_id}',
        batter_side='R',
        pitch_type=pitch_type,
        exit_velocity=75.0,
        launch_angle=25.0,
        trajectory=None,
        landing_side='1B',
        section=section,
        landing_distance=distance,
        landing_height=8.0,
        is_catchable=True,
        weight=weight,
        batter_id=batter_id,
    )


def make_fouls(batter_ids, distances=None, pitch_types=None):
    """A minimal Statcast-shaped foul frame."""
    n = len(batter_ids)
    if distances is None:
        distances = [120.0] * n
    if pitch_types is None:
        pitch_types = ['FF'] * n
    return pd.DataFrame({
        'batter': batter_ids,
        'hit_distance_sc': distances,
        'pitch_type': pitch_types,
        'stand': ['R'] * n,
    })


@pytest.fixture
def simple_comparison():
    """Two batters: 111 predicted 6.0 fouls and hit 8, 222 predicted 2.0 and hit 2."""
    events = ([make_event(111, 0.5, distance=100.0 + i) for i in range(12)] +
              [make_event(222, 0.2, distance=140.0 + i) for i in range(10)])
    fouls = make_fouls([111] * 8 + [222] * 2,
                       distances=[105.0 + i for i in range(8)] + [145.0, 150.0])
    return compare_game(events, fouls, fouls, [111, 222])


class TestTotalFoulsPerGame:
    """The volume-model check: the one external number the model can be graded on."""

    def test_predicted_total_is_the_weighted_event_sum(self, simple_comparison):
        # 12 events at 0.5 + 10 events at 0.2 = 8.0 expected fouls
        assert simple_comparison['pred_total_fouls'] == pytest.approx(8.0)

    def test_actual_total_counts_every_foul_not_just_tracked_ones(self):
        events = [make_event(111, 0.5) for _ in range(20)]
        tracked = make_fouls([111] * 10)
        # Five more fouls with no tracking data at all
        untracked = make_fouls([111] * 5, distances=[np.nan] * 5)
        all_fouls = pd.concat([tracked, untracked], ignore_index=True)

        result = compare_game(events, tracked, all_fouls, [111])
        assert result['actual_total_fouls'] == 15
        assert result['n_actual_tracked'] == 10

    def test_total_error_is_predicted_minus_actual(self, simple_comparison):
        assert simple_comparison['actual_total_fouls'] == 10
        assert simple_comparison['total_foul_error'] == pytest.approx(-2.0)

    def test_fouls_per_pa_is_reported_against_real_pa_count(self):
        events = [make_event(111, 0.5) for _ in range(20)]  # 10.0 predicted fouls
        fouls = make_fouls([111] * 12)
        result = compare_game(events, fouls, fouls, [111],
                              plate_appearances=15, predicted_pa=20.0)
        assert result['actual_pa'] == 15
        assert result['pred_fouls_per_pa'] == pytest.approx(0.5)
        assert result['actual_fouls_per_pa'] == pytest.approx(0.8)

    def test_into_stands_total_is_reported_separately(self):
        """Balls reaching a modelled zone have no Statcast counterpart, so they
        must not be confused with the validated total."""
        events = ([make_event(111, 0.5, section='SEC') for _ in range(10)] +
                  [make_event(111, 0.5, section=None) for _ in range(10)])
        fouls = make_fouls([111] * 12)
        result = compare_game(events, fouls, fouls, [111])
        assert result['pred_total_fouls'] == pytest.approx(10.0)
        assert result['pred_fouls_into_stands'] == pytest.approx(5.0)


class TestPerBatterCorrelation:
    """Previously hardcoded to np.nan."""

    def test_correlation_is_actually_computed(self):
        events = []
        for bid, total in ((101, 1.0), (102, 2.0), (103, 4.0)):
            events += [make_event(bid, total / 5) for _ in range(5)]
        fouls = make_fouls([101] * 2 + [102] * 4 + [103] * 6)
        result = compare_game(events, fouls, fouls, [101, 102, 103])
        assert result['batter_corr'] is not None
        assert not np.isnan(result['batter_corr'])

    def test_correlation_is_none_rather_than_misleading_when_undefined(self, simple_comparison):
        """Two batters is not a correlation. Reporting one would be theatre."""
        assert simple_comparison['batter_n'] == 2
        assert simple_comparison['batter_corr'] is None
        assert simple_comparison['batter_mae'] is not None

    def test_matches_hand_computed_pearson(self):
        preds = {101: 1.0, 102: 2.0, 103: 3.0, 104: 4.0}
        events = []
        for bid, total in preds.items():
            events += [make_event(bid, total / 4) for _ in range(4)]
        actual_ids = [101] + [102] * 3 + [103] * 2 + [104] * 6
        fouls = make_fouls(actual_ids)

        result = compare_game(events, fouls, fouls, list(preds))
        expected = np.corrcoef([1.0, 2.0, 3.0, 4.0], [1, 3, 2, 6])[0, 1]
        assert result['batter_corr'] == pytest.approx(round(expected, 3), abs=1e-3)
        assert result['batter_n'] == 4

    def test_batters_who_fouled_nothing_are_scored_as_zero(self):
        """Dropping the zeros would flatter the correlation."""
        events = ([make_event(111, 0.5) for _ in range(20)] +
                  [make_event(222, 0.5) for _ in range(20)])
        fouls = make_fouls([111] * 12)  # 222 never fouled
        result = compare_game(events, fouls, fouls, [111, 222, 333])
        pairs = {bid: (p, a) for bid, p, a in result['batter_pairs']}
        assert pairs[222][1] == 0
        assert pairs[333] == (0.0, 0)   # in the lineup, never came up
        assert result['batter_n'] == 3

    def test_join_is_by_id_not_name(self):
        """Two batters with identical generated names must not be merged."""
        events = ([make_event(111, 1.0) for _ in range(6)] +
                  [make_event(222, 1.0) for _ in range(6)])
        for e in events:
            e.batter_name = 'Same Name'
        fouls = make_fouls([111] * 10 + [222] * 2)
        result = compare_game(events, fouls, fouls, [111, 222])
        pairs = {bid: (p, a) for bid, p, a in result['batter_pairs']}
        assert pairs[111][1] == 10
        assert pairs[222][1] == 2

    def test_coverage_flags_fouls_from_batters_outside_the_lineup(self):
        events = [make_event(111, 0.5) for _ in range(20)]
        fouls = make_fouls([111] * 8 + [999] * 2)  # 999 is a pinch hitter
        result = compare_game(events, fouls, fouls, [111])
        assert result['actual_total_fouls'] == 10
        assert result['batter_coverage'] == pytest.approx(0.8)

    def test_events_carry_the_batter_id_through_a_real_prediction(self):
        np.random.seed(42)
        stadium = STADIUMS['yankee_stadium']()
        lineup = list(YANKEES_2024_PROFILES.values())[:3]
        pred = predict_game_fouls(lineup, 'Standard RHP', STANDARD_RHP_MIX,
                                  stadium, simulations_per_batter=25)
        assert pred.all_events
        expected_ids = {b.player_id for b in lineup}
        assert {e.batter_id for e in pred.all_events} <= expected_ids
        assert all(e.batter_id is not None for e in pred.all_events)


class TestSideSplitIsGone:
    """The deleted metric compared the model against an assumption (RHB fouls
    72% to 3B), not against data. It must not come back."""

    def test_no_side_split_keys_are_reported(self, simple_comparison):
        for key in ('pred_1b_pct', 'actual_1b_est', 'side_error'):
            assert key not in simple_comparison

    def test_backtest_source_has_no_side_split_backsolve(self):
        import game_backtest
        with open(game_backtest.__file__, encoding='utf-8') as f:
            src = f.read()
        assert 'actual_1b_est' not in src
        assert 'side_error' not in src


class TestSafePearson:
    def test_returns_none_without_variance(self):
        assert safe_pearson([1, 1, 1, 1], [1, 2, 3, 4]) is None

    def test_returns_none_below_three_points(self):
        assert safe_pearson([1, 2], [3, 4]) is None

    def test_computes_normally(self):
        assert safe_pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
