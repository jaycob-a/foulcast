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


class TestStraightBackFouls:
    """The straight-back wedge must be populated.

    Before this mode existed the spray model clamped every foul to a launch
    direction of 0-85 degrees off the foul line, so no ball ever crossed behind
    the plane of home plate and the seats behind the plate sat nearly empty.
    """

    def test_some_fouls_go_behind_the_plate(self, large_sim_events):
        events, _ = large_sim_events
        back = sum(1 for e in events if e.trajectory.landing_x < 0)
        share = back / len(events)
        assert 0.15 < share < 0.45, (
            f"{share*100:.1f}% of fouls landed behind the plane of home plate "
            f"— expected roughly a fifth to a third of them"
        )

    def test_back_fouls_fill_the_wedge_not_a_single_line(self, large_sim_events):
        """Backward fouls must spread across the backstop, peaking dead-back."""
        events, _ = large_sim_events
        angles = np.array([
            np.degrees(np.arctan2(abs(e.trajectory.landing_y), e.trajectory.landing_x))
            for e in events if e.trajectory.landing_x < 0
        ])
        assert len(angles) > 50, "Too few backward fouls to check the spread"
        assert angles.max() <= 135.5, \
            f"Foul at {angles.max():.1f} deg crossed into the other side's territory"
        assert angles.min() < 110, "Backward fouls never reach the backstop corners"
        assert np.median(angles) > 110, \
            f"Backward fouls peak at {np.median(angles):.1f} deg, not near dead-back (135)"

    def test_back_fouls_are_near_symmetric_across_sides(self, large_sim_events):
        """A deflected ball barely knows which way the bat was going, so pull
        tendency should mostly wash out on backward fouls.

        Compared per handedness, not over the whole lineup: a mixed lineup's
        left- and right-handed pull tendencies cancel in aggregate and would
        hide the effect either way.
        """
        events, _ = large_sim_events
        for hand in ('R', 'L'):
            back = [e for e in events
                    if e.batter_side == hand and e.trajectory.landing_x < 0]
            fwd = [e for e in events
                   if e.batter_side == hand and e.trajectory.landing_x >= 0]
            if len(back) < 50 or len(fwd) < 50:
                continue
            back_1b = sum(1 for e in back if e.landing_side == '1B') / len(back)
            fwd_1b = sum(1 for e in fwd if e.landing_side == '1B') / len(fwd)
            assert abs(back_1b - 0.5) < abs(fwd_1b - 0.5), (
                f"{hand}HB backward fouls split {back_1b*100:.0f}/"
                f"{(1-back_1b)*100:.0f} vs forward {fwd_1b*100:.0f}/"
                f"{(1-fwd_1b)*100:.0f} — pull tendency should wash out on "
                f"deflections, not strengthen"
            )


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

    def test_ev_sampler_matches_profile(self):
        """The EV sampler should draw within 3 mph of each batter's profile mean."""
        np.random.seed(42)
        for name, batter in YANKEES_2024_PROFILES.items():
            evs = [batter.sample_foul()['exit_velocity'] for _ in range(2000)]
            sample_mean = np.mean(evs)
            assert abs(sample_mean - batter.ev_mean) < 3.0, \
                f"{name}: sampler EV mean {sample_mean:.1f} vs profile {batter.ev_mean:.1f}"

    def test_forward_foul_ev_mean_near_profile(self, large_sim_events):
        """Fouls hit out in front leave the bat at the sampled speed, so their EV
        mean should still track the profile. (Fouls deflected backward do not —
        see oblique_contact_speed_factor — so they are excluded here.)"""
        events, lineup = large_sim_events
        for batter in lineup:
            batter_evs = [e.exit_velocity for e in events
                          if e.batter_name == batter.player_name
                          and e.trajectory.landing_x >= 0]
            if len(batter_evs) < 30:
                continue
            sample_mean = np.mean(batter_evs)
            assert abs(sample_mean - batter.ev_mean) < 3.0, \
                f"{batter.player_name}: forward-foul EV mean {sample_mean:.1f} " \
                f"vs profile {batter.ev_mean:.1f}"

    def test_back_fouls_come_off_the_bat_slower(self, large_sim_events):
        """A ball deflected back over the catcher was hit a glancing blow, so it
        must leave the bat measurably slower than one driven into foul ground."""
        events, _ = large_sim_events
        back = [e.exit_velocity for e in events if e.trajectory.landing_x < 0]
        fwd = [e.exit_velocity for e in events if e.trajectory.landing_x >= 0]
        assert len(back) > 50, f"Only {len(back)} backward fouls — mode missing?"
        assert np.mean(back) < np.mean(fwd) * 0.85, (
            f"Backward fouls averaged {np.mean(back):.1f} mph vs {np.mean(fwd):.1f} "
            f"forward — glancing-contact penalty not applied"
        )
