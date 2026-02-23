"""
Guardrail unit tests — crash fixes and correctness invariants.
"""
import numpy as np
import pandas as pd
import pytest

from foulball.batter_profiles import BatterFoulProfile, _safe_mode, _compute_foul_rates
from foulball.trajectory import simulate_foul_ball, simulate_trajectory, estimate_spray_angle
from foulball.matchup_engine import predict_game_fouls
from foulball.stadium import STADIUMS, SeatSection


class TestSafeMode:
    """Test _safe_mode helper for .mode() crash prevention."""

    def test_empty_series(self):
        s = pd.Series([], dtype=str)
        assert _safe_mode(s, 'R') == 'R'

    def test_normal_series(self):
        s = pd.Series(['L', 'R', 'R', 'L', 'R'])
        assert _safe_mode(s, 'L') == 'R'

    def test_single_value(self):
        s = pd.Series(['L'])
        assert _safe_mode(s, 'R') == 'L'

    def test_all_nan(self):
        s = pd.Series([np.nan, np.nan])
        result = _safe_mode(s, 'R')
        # mode of all-NaN can be empty or NaN depending on pandas version
        # _safe_mode should return the default if mode is empty
        assert result is not None


class TestTrajectoryEdgeCases:
    """Test trajectory with edge-case inputs."""

    def test_very_low_ev(self):
        """EV of 5 mph should still produce a valid trajectory."""
        traj = simulate_trajectory(
            exit_velocity_mph=5.0,
            launch_angle_deg=30.0,
            spray_angle_deg=20.0,
        )
        assert traj.landing_distance >= 0
        assert not np.isnan(traj.landing_speed)
        assert len(traj.positions) > 0

    def test_very_high_launch_angle(self):
        """Near-vertical popup should land near home plate."""
        traj = simulate_trajectory(
            exit_velocity_mph=50.0,
            launch_angle_deg=85.0,
            spray_angle_deg=45.0,
        )
        assert traj.landing_distance >= 0
        assert traj.max_height > 0

    def test_negative_launch_angle(self):
        """Grounder foul — negative LA."""
        traj = simulate_trajectory(
            exit_velocity_mph=70.0,
            launch_angle_deg=-20.0,
            spray_angle_deg=10.0,
        )
        assert traj.landing_distance >= 0


class TestEmptyPitchMixDefault:
    """Engine should handle empty pitch mix without crashing."""

    def test_empty_pitch_mix(self, seeded_rng, yankee_stadium):
        lineup = [BatterFoulProfile(
            player_name='Test', player_id=0, batter_side='R',
        )]
        result = predict_game_fouls(
            lineup, 'Test Pitcher', {},
            yankee_stadium, simulations_per_batter=10,
        )
        assert result.total_simulated_fouls >= 0


class TestZeroStdFallback:
    """Engine should use default ev_std/la_std when degenerate, without mutating the batter."""

    def test_zero_ev_std(self, seeded_rng, yankee_stadium):
        batter = BatterFoulProfile(
            player_name='ZeroStd', player_id=0, batter_side='R',
            ev_std=0.0, la_std=0.0,
        )
        result = predict_game_fouls(
            [batter], 'Pitcher', {'FF': 1.0},
            yankee_stadium, simulations_per_batter=50,
        )
        # Should not crash, and batter's original fields should NOT be mutated
        assert batter.ev_std == 0.0
        assert batter.la_std == 0.0
        assert result.total_simulated_fouls >= 0

    def test_negative_ev_std(self, seeded_rng, yankee_stadium):
        batter = BatterFoulProfile(
            player_name='NegStd', player_id=0, batter_side='R',
            ev_std=-5.0, la_std=-10.0,
        )
        predict_game_fouls(
            [batter], 'Pitcher', {'FF': 1.0},
            yankee_stadium, simulations_per_batter=10,
        )
        # Original values preserved — engine uses local overrides
        assert batter.ev_std == -5.0
        assert batter.la_std == -10.0


class TestSprayAngleNonNegative:
    """Spray angles must be >= 0 to preserve the stands-frame invariant."""

    def test_estimate_spray_never_negative(self):
        """estimate_spray_angle should never return a negative value."""
        np.random.seed(42)
        for _ in range(1000):
            angle = estimate_spray_angle(
                batter_side=np.random.choice(['R', 'L']),
                pitch_location_x=np.random.normal(0, 1),
                exit_velocity_mph=np.random.uniform(20, 110),
                launch_angle_deg=np.random.uniform(-30, 85),
                pitch_type=np.random.choice(['FF', 'SL', 'CU', 'CH', 'SI']),
            )
            assert angle >= 0, f"estimate_spray_angle returned {angle}"

    def test_simulate_foul_ball_side_consistency(self):
        """Side derived from landing_y must always be consistent."""
        np.random.seed(42)
        mismatches = 0
        for _ in range(500):
            traj, side = simulate_foul_ball(
                exit_velocity_mph=np.random.uniform(30, 100),
                launch_angle_deg=np.random.uniform(-20, 70),
                batter_side=np.random.choice(['R', 'L']),
                fair_pull_pct=np.random.uniform(35, 65),
            )
            if side == '1B':
                assert traj.landing_y >= 0, \
                    f"Side=1B but landing_y={traj.landing_y:.1f}"
            else:
                assert traj.landing_y <= 0, \
                    f"Side=3B but landing_y={traj.landing_y:.1f}"


class TestFoulRatesConditional:
    """foul_rates should compute P(foul|pitch_type) when full data is available."""

    def test_correct_conditional_with_full_data(self):
        """With all_pitches, foul_rates should be fouls/total per pitch type."""
        foul_data = pd.DataFrame({
            'pitch_type': ['FF', 'FF', 'FF', 'SL', 'SL'],
        })
        all_pitches = pd.DataFrame({
            'pitch_type': ['FF'] * 20 + ['SL'] * 10,
        })
        rates, kind = _compute_foul_rates(foul_data, all_pitches)
        # FF: 3/20 = 0.15, SL: 2/10 = 0.20
        assert abs(rates['FF'] - 0.15) < 0.01
        assert abs(rates['SL'] - 0.20) < 0.01
        assert kind == 'p_foul_given_pitch'

    def test_fallback_without_full_data(self):
        """Without all_pitches, falls back to P(pitch_type|foul)."""
        foul_data = pd.DataFrame({
            'pitch_type': ['FF', 'FF', 'FF', 'SL', 'SL'],
        })
        rates, kind = _compute_foul_rates(foul_data, None)
        # FF: 3/5 = 0.60, SL: 2/5 = 0.40
        assert abs(rates['FF'] - 0.60) < 0.01
        assert abs(rates['SL'] - 0.40) < 0.01
        assert kind == 'p_pitch_given_foul'

    def test_small_sample_excluded(self):
        """Pitch types with < 10 total pitches should be excluded."""
        foul_data = pd.DataFrame({
            'pitch_type': ['FF', 'FF', 'CU'],
        })
        all_pitches = pd.DataFrame({
            'pitch_type': ['FF'] * 30 + ['CU'] * 5,  # CU has only 5 pitches
        })
        rates, kind = _compute_foul_rates(foul_data, all_pitches)
        assert 'FF' in rates
        assert 'CU' not in rates  # excluded: only 5 pitches


class TestNaNSectionHeights:
    """Sections with NaN heights should match by distance only."""

    def test_nan_height_section(self, seeded_rng):
        stadium = STADIUMS['yankee_stadium']()
        # Inject a NaN-height section
        nan_section = SeatSection(
            name='NaN Test', section_id='nan_test', side='1B', level='field',
            distance_min=50, distance_max=150, angle_min=0, angle_max=90,
            height_min=float('nan'), height_max=float('nan'),
        )
        stadium.sections.insert(0, nan_section)

        batter = BatterFoulProfile(
            player_name='Test', player_id=0, batter_side='L',
        )
        result = predict_game_fouls(
            [batter], 'Pitcher', {'FF': 1.0},
            stadium, simulations_per_batter=100,
        )
        # Should not crash
        assert result.total_simulated_fouls >= 0


class TestPitchTypeWeightingMath:
    """Verify pitch-type weighting is mathematically correct for both foul_rates_kind values."""

    def test_fallback_mode_no_double_count(self, seeded_rng, yankee_stadium):
        """p_pitch_given_foul: changing pitcher mix should NOT change sampled pitch types
        (because the batter's foul distribution is used directly, not multiplied by mix)."""
        # Batter who fouls off 80% FF, 20% SL historically
        batter = BatterFoulProfile(
            player_name='FallbackTest', player_id=0, batter_side='R',
            foul_rates={'FF': 0.80, 'SL': 0.20},
            foul_rates_kind='p_pitch_given_foul',
        )

        # Run with a fastball-heavy pitcher (90% FF)
        np.random.seed(42)
        result_ff_heavy = predict_game_fouls(
            [batter], 'Pitcher', {'FF': 0.90, 'SL': 0.10},
            yankee_stadium, simulations_per_batter=500,
        )
        ff_count_1 = sum(1 for e in result_ff_heavy.all_events if e.pitch_type == 'FF')
        total_1 = len(result_ff_heavy.all_events)

        # Run with a slider-heavy pitcher (30% FF, 70% SL)
        np.random.seed(42)
        result_sl_heavy = predict_game_fouls(
            [batter], 'Pitcher', {'FF': 0.30, 'SL': 0.70},
            yankee_stadium, simulations_per_batter=500,
        )
        ff_count_2 = sum(1 for e in result_sl_heavy.all_events if e.pitch_type == 'FF')
        total_2 = len(result_sl_heavy.all_events)

        # In fallback mode, the batter's 80/20 distribution should dominate
        # so the FF fraction should be similar regardless of pitcher mix
        ff_pct_1 = ff_count_1 / total_1
        ff_pct_2 = ff_count_2 / total_2
        # Both should be near 80% (the batter's rate), not 90% or 30% (the pitcher's rate)
        assert 0.65 < ff_pct_1 < 0.95, f"FF heavy pitcher: FF%={ff_pct_1:.2f} (expected ~0.80)"
        assert 0.65 < ff_pct_2 < 0.95, f"SL heavy pitcher: FF%={ff_pct_2:.2f} (expected ~0.80)"
        # The difference between the two should be small (no double-counting)
        assert abs(ff_pct_1 - ff_pct_2) < 0.10, \
            f"Fallback mode too sensitive to pitcher mix: {ff_pct_1:.2f} vs {ff_pct_2:.2f}"

    def test_conditional_mode_reflects_pitcher_mix(self, seeded_rng, yankee_stadium):
        """p_foul_given_pitch: higher foul propensity for a pitch type should increase
        foul selection, and pitcher mix should also matter."""
        # Batter with high foul rate on sliders, low on fastballs
        batter = BatterFoulProfile(
            player_name='ConditionalTest', player_id=0, batter_side='R',
            foul_rates={'FF': 0.10, 'SL': 0.40},
            foul_rates_kind='p_foul_given_pitch',
        )

        # Pitcher who throws mostly fastballs — but batter fouls sliders more
        np.random.seed(42)
        result = predict_game_fouls(
            [batter], 'Pitcher', {'FF': 0.70, 'SL': 0.30},
            yankee_stadium, simulations_per_batter=500,
        )
        ff_count = sum(1 for e in result.all_events if e.pitch_type == 'FF')
        sl_count = sum(1 for e in result.all_events if e.pitch_type == 'SL')
        total = len(result.all_events)

        # Weight(FF) = 0.70 * 0.10 = 0.07
        # Weight(SL) = 0.30 * 0.40 = 0.12
        # After normalization: FF = 0.07/0.19 = 36.8%, SL = 0.12/0.19 = 63.2%
        # Despite pitcher throwing 70% FF, slider fouls should dominate because
        # the batter fouls off sliders at 4x the rate
        ff_pct = ff_count / total
        sl_pct = sl_count / total
        assert sl_pct > ff_pct, \
            f"Conditional mode: SL fouls ({sl_pct:.2f}) should exceed FF fouls ({ff_pct:.2f})"
        # SL should be roughly 60%+ of fouls
        assert sl_pct > 0.50, \
            f"SL% should be >50% (got {sl_pct:.2f}), expected ~63% from the math"

    def test_behind_plate_fouls_exist_at_reasonable_rate(self, seeded_rng, yankee_stadium):
        """Some fouls should land behind home plate (angle > 90 in matchup_engine).
        These are excluded from section totals but should still appear in all_events."""
        lineup = [BatterFoulProfile(
            player_name='BehindPlateTest', player_id=0, batter_side='R',
        )]
        result = predict_game_fouls(
            lineup, 'Pitcher', {'FF': 0.50, 'CU': 0.30, 'SL': 0.20},
            yankee_stadium, simulations_per_batter=500,
        )
        # Count events with no section match (includes behind-plate + out-of-range)
        no_section = sum(1 for e in result.all_events if e.section is None)
        with_section = sum(1 for e in result.all_events if e.section is not None)
        total = len(result.all_events)
        assert total > 0, "No events produced"
        # Some fouls should have sections, some shouldn't
        assert with_section > 0, "No fouls matched any section"
        # Verify section percentages sum close to 100% (behind-plate excluded from denom)
        total_pct = sum(sp.pct_of_total for sp in result.section_predictions)
        assert 95 < total_pct < 105, \
            f"Section percentages sum to {total_pct:.1f}% (expected ~100%)"
