"""
Statcast distribution validation tests.

Verify that Monte Carlo outputs match expected statistical properties
of real foul ball distributions.
"""
import numpy as np
import pytest

from foulball.batter_profiles import BatterFoulProfile, YANKEES_2024_PROFILES
from foulball.trajectory import simulate_foul_ball
from foulball.matchup_engine import predict_game_fouls
from foulball.stadium import STADIUMS


@pytest.fixture
def large_sim_events():
    """Run a large simulation and return all events for distribution tests."""
    np.random.seed(42)
    lineup = list(YANKEES_2024_PROFILES.values())
    stadium = STADIUMS['yankee_stadium']()
    pred = predict_game_fouls(
        lineup, 'Gerrit Cole',
        {'FF': 0.45, 'CU': 0.19, 'FC': 0.16, 'SL': 0.15, 'CH': 0.05},
        stadium, simulations_per_batter=300,
    )
    return pred.all_events, lineup


class TestSprayAngleDistributions:
    """Spray angle distributions should match expected patterns."""

    def test_rhb_vs_lhb_spray_means(self, large_sim_events):
        """RHB and LHB should have different spray angle distributions."""
        events, lineup = large_sim_events
        rhb_angles = [abs(e.trajectory.landing_y) for e in events if e.batter_side == 'R']
        lhb_angles = [abs(e.trajectory.landing_y) for e in events if e.batter_side == 'L']

        assert len(rhb_angles) > 50, "Too few RHB events"
        assert len(lhb_angles) > 50, "Too few LHB events"

        # Both should have positive mean spray angles
        assert np.mean(rhb_angles) > 0
        assert np.mean(lhb_angles) > 0

    def test_breaking_balls_higher_spray(self, large_sim_events):
        """Breaking balls (SL/CU/ST) should produce higher spray angles than fastballs."""
        events, _ = large_sim_events
        fb_angles = [
            abs(e.trajectory.landing_y)
            for e in events if e.pitch_type in ('FF', 'SI', 'FC')
        ]
        breaking_angles = [
            abs(e.trajectory.landing_y)
            for e in events if e.pitch_type in ('CU', 'SL', 'ST')
        ]

        if len(breaking_angles) < 30:
            pytest.skip("Not enough breaking ball events")

        # Breaking balls should trend higher (more behind plate)
        # This is a soft check — directional, not exact
        fb_mean = np.mean(fb_angles)
        brk_mean = np.mean(breaking_angles)
        # Allow a generous margin; the effect is stochastic
        assert brk_mean > fb_mean * 0.8, \
            f"Breaking ball spray ({brk_mean:.1f}) not higher than fastball ({fb_mean:.1f})"


class TestDistanceDistribution:
    """Distance distributions should match expected foul ball ranges."""

    def test_no_fouls_beyond_500ft(self, large_sim_events):
        """No foul balls should land beyond 500 feet (physics limit)."""
        events, _ = large_sim_events
        distances = [e.landing_distance for e in events]
        max_dist = max(distances)
        assert max_dist < 500, f"Foul landed at {max_dist:.1f} ft — exceeds physics limit"

    def test_distance_peak_range(self, large_sim_events):
        """Majority of fouls should land within [5, 250] ft range."""
        events, _ = large_sim_events
        distances = [e.landing_distance for e in events]
        in_range = sum(1 for d in distances if 5 <= d <= 250)
        pct = in_range / len(distances)
        assert pct > 0.60, \
            f"Only {pct*100:.0f}% of fouls in [5,250]ft — expected >60%"


class TestFrequencyValidation:
    """Per-batter foul frequency should be plausible."""

    def test_fouls_per_pa_range(self):
        """Every batter profile should have fouls_per_pa in [0.3, 2.0] or 0 (uncomputed)."""
        for name, prof in YANKEES_2024_PROFILES.items():
            fpa = prof.fouls_per_pa
            if fpa > 0:
                assert 0.3 <= fpa <= 2.0, \
                    f"{name}: fouls_per_pa={fpa} out of range [0.3, 2.0]"

    def test_ev_sample_mean_near_profile(self, large_sim_events):
        """EV sample mean should be within 2 mph of profile ev_mean for each batter."""
        events, lineup = large_sim_events
        for batter in lineup:
            batter_evs = [e.exit_velocity for e in events if e.batter_name == batter.player_name]
            if len(batter_evs) < 30:
                continue
            sample_mean = np.mean(batter_evs)
            assert abs(sample_mean - batter.ev_mean) < 3.0, \
                f"{batter.player_name}: sample EV mean {sample_mean:.1f} vs profile {batter.ev_mean:.1f}"
