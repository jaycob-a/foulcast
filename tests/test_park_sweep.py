"""
Tests for the park sweep instrumentation.

The sweep's conclusions — which parks are implausible, and how much the
handedness split moves — rest on a handful of pure-geometry helpers. These
test those helpers directly, with no simulation, so a wrong conclusion cannot
be blamed on Monte Carlo noise.
"""
import math

import numpy as np
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dataclasses import replace

from foulball.stadium import STADIUMS, SeatSection
from park_sweep import (
    _xy, _CX, _CY, owned_bands, zone_owned_area, geometry_mirror_delta,
    coverage_gaps, handed_lineups, standard_lineups, _landing_angle,
)
from park_coverage import coverage_profile, classify_losses


class TestPlanViewMapping:
    """The heat map unrolls a per-side angle frame onto a real plan view.

    If this mapping is wrong every map is wrong in a way that still looks
    plausible, so it is pinned rather than eyeballed.
    """

    def test_foul_lines_are_ninety_degrees_apart(self):
        origin = np.array([_CX, _CY])
        v1 = np.array(_xy('1B', 0, 100)) - origin
        v3 = np.array(_xy('3B', 0, 100)) - origin
        cos = v1.dot(v3) / (np.linalg.norm(v1) * np.linalg.norm(v3))
        assert math.degrees(math.acos(cos)) == pytest.approx(90.0, abs=0.01)

    def test_both_sides_converge_dead_behind_the_plate(self):
        """Angle 135 is dead back for both sides; the backstop must close up."""
        x1, y1 = _xy('1B', 135, 120)
        x3, y3 = _xy('3B', 135, 120)
        assert (x1, y1) == pytest.approx((x3, y3), abs=1e-9)

    def test_the_two_sides_are_mirrored_about_the_centre_line(self):
        for angle in (0, 30, 60, 90, 120):
            x1, y1 = _xy('1B', angle, 90)
            x3, y3 = _xy('3B', angle, 90)
            assert x1 - _CX == pytest.approx(_CX - x3, abs=1e-9)
            assert y1 == pytest.approx(y3, abs=1e-9)

    def test_distance_from_home_is_preserved(self):
        for side in ('1B', '3B'):
            for angle in (0, 45, 90, 135):
                x, y = _xy(side, angle, 137.0)
                assert math.hypot(x - _CX, y - _CY) == pytest.approx(137.0, abs=1e-9)

    def test_down_the_line_is_toward_the_outfield(self):
        """SVG y grows downward, so a ball down the line is above home plate."""
        _, y_line = _xy('1B', 0, 100)
        _, y_back = _xy('1B', 135, 100)
        assert y_line < _CY < y_back


class TestOwnedBands:
    """The map draws the partition the engine matches against, not raw
    section rectangles — those overlap heavily before exposed_bands resolves
    them."""

    @pytest.mark.parametrize('park', list(STADIUMS))
    def test_bands_never_overlap(self, park):
        stadium = STADIUMS[park]()
        for side in ('1B', '3B'):
            for i in range(0, 180, 7):
                spans = sorted((b0, b1) for _, b0, b1 in
                               owned_bands(stadium, side, i + 0.5))
                for (_, a1), (b0, _) in zip(spans, spans[1:]):
                    assert b0 >= a1 - 1e-6, (
                        f'{park} {side} at {i}: bands overlap {a1} > {b0}')

    @pytest.mark.parametrize('park', list(STADIUMS))
    def test_only_same_side_and_home_sections_are_offered(self, park):
        stadium = STADIUMS[park]()
        for side in ('1B', '3B'):
            other = '3B' if side == '1B' else '1B'
            for i in range(0, 180, 11):
                for sec, _, _ in owned_bands(stadium, side, i + 0.5):
                    assert sec.side != other, (
                        f'{park}: a {other} section was offered on the {side} side')

    @pytest.mark.parametrize('park', list(STADIUMS))
    def test_behind_the_plate_is_covered(self, park):
        """Past 90 degrees a ball is behind the plate; something must own it.

        Step 3 made a quarter of all fouls land here. A park with no coverage
        past 90 would silently discard them.
        """
        stadium = STADIUMS[park]()
        for side in ('1B', '3B'):
            assert owned_bands(stadium, side, 120.0), (
                f'{park} {side}: nothing owns the ground dead behind the plate')


class TestZoneArea:
    def test_area_of_a_single_full_wedge_matches_the_annulus_formula(self):
        """One section spanning every angle owns the whole annulus."""
        secs = [SeatSection(name='x', section_id='1B-X', side='1B', level='field',
                            distance_min=100, distance_max=200,
                            angle_min=0, angle_max=180,
                            height_min=0, height_max=10)]
        stadium = STADIUMS['citi_field']()
        stadium.sections = secs
        got = zone_owned_area(stadium, '1B')['1B-X']
        expected = 0.5 * (200 ** 2 - 100 ** 2) * math.pi   # half-disc annulus
        assert got == pytest.approx(expected, rel=0.01)

    def test_a_section_hidden_under_a_lower_deck_is_credited_nothing(self):
        """Density is fouls per owned square foot, so double-counting the
        overlap would make every upper deck look artificially sparse."""
        stadium = STADIUMS['citi_field']()
        stadium.sections = [
            SeatSection(name='low', section_id='1B-LOW', side='1B', level='field',
                        distance_min=50, distance_max=200,
                        angle_min=0, angle_max=180, height_min=0, height_max=8),
            SeatSection(name='high', section_id='1B-HIGH', side='1B', level='upper',
                        distance_min=60, distance_max=190,
                        angle_min=0, angle_max=180, height_min=40, height_max=70),
        ]
        areas = zone_owned_area(stadium, '1B')
        assert areas.get('1B-HIGH', 0.0) == pytest.approx(0.0, abs=1.0)
        assert areas['1B-LOW'] > 0


class TestMirrorDetection:
    """Left/right asymmetry is only a finding if the park's own geometry does
    not already explain it."""

    @pytest.mark.parametrize('park', list(STADIUMS))
    def test_every_shipped_park_is_mirror_symmetric(self, park):
        m = geometry_mirror_delta(STADIUMS[park]())
        assert m['symmetric'], (
            f'{park}: 1B and 3B geometry differ — unpaired {m["unpaired"]}, '
            f'largest delta {m["max_param_delta"]} at {m["max_param_field"]}')

    def test_an_asymmetric_park_is_detected(self):
        stadium = STADIUMS['citi_field']()
        stadium.sections = [replace(s, distance_max=s.distance_max + 30)
                            if s.side == '1B' else s for s in stadium.sections]
        m = geometry_mirror_delta(stadium)
        assert not m['symmetric']
        assert m['max_param_delta'] == pytest.approx(30.0)

    def test_an_unpaired_section_is_reported(self):
        stadium = STADIUMS['citi_field']()
        stadium.sections = [s for s in stadium.sections if s.section_id != '1B-DUG']
        m = geometry_mirror_delta(stadium)
        assert not m['symmetric']
        assert 'DUG' in m['unpaired']


class TestCoverageProfile:
    @pytest.mark.parametrize('park', list(STADIUMS))
    def test_no_park_has_an_interior_hole(self, park):
        """A gap *between* owned bands would be a ball falling through the
        bowl. Losses in front of the stands and beyond the last deck are a
        different matter and are measured separately."""
        assert not coverage_gaps(STADIUMS[park](), '1B')
        assert not coverage_gaps(STADIUMS[park](), '3B')

    def test_profile_covers_every_angle_bin(self):
        prof = coverage_profile(STADIUMS['citi_field'](), '1B', angle_step=1.0)
        assert len(prof) == 180

    def test_first_owned_never_exceeds_last_owned(self):
        for park in STADIUMS:
            for side in ('1B', '3B'):
                for _angle, first, last, _gap in coverage_profile(STADIUMS[park](), side):
                    if first is not None:
                        assert first <= last


class TestLossClassification:
    def test_a_ball_short_of_the_bowl_is_classified_short(self):
        stadium = STADIUMS['citi_field']()
        counts = classify_losses(stadium, [('1B', 20.5, 5.0, 1.0)])
        assert counts['short'] == 1

    def test_a_ball_past_the_last_deck_is_classified_past(self):
        stadium = STADIUMS['citi_field']()
        counts = classify_losses(stadium, [('1B', 20.5, 900.0, 1.0)])
        assert counts['past'] == 1


class TestHandednessLineups:
    """The handedness experiment must change handedness and nothing else,
    or the swing it measures is not attributable to handedness."""

    def test_every_batter_is_forced_to_the_requested_side(self):
        for hand in ('R', 'L'):
            for lineup in handed_lineups(hand):
                assert all(b.batter_side == hand for b in lineup)

    def test_nothing_but_handedness_changes(self):
        base = [b for lu in standard_lineups() for b in lu]
        rhb = [b for lu in handed_lineups('R') for b in lu]
        assert len(base) == len(rhb) == 18
        for a, b in zip(base, rhb):
            assert a.player_id == b.player_id
            for fld in ('ev_mean', 'ev_std', 'la_mean', 'la_std',
                        'fouls_per_pa', 'fair_pull_pct', 'avg_plate_x_on_foul',
                        'foul_rates', 'foul_rates_kind'):
                assert getattr(a, fld) == getattr(b, fld), fld

    def test_the_source_profiles_are_not_mutated(self):
        """replace() must copy: mutating the module-level profiles would
        silently contaminate every later run in the same process."""
        before = [b.batter_side for lu in standard_lineups() for b in lu]
        handed_lineups('R')
        handed_lineups('L')
        after = [b.batter_side for lu in standard_lineups() for b in lu]
        assert before == after
        assert set(before) == {'L', 'R'}, 'the standard lineup should be mixed'

    def test_the_standard_lineup_is_handedness_balanced(self):
        """The asymmetry flag assumes a balanced lineup lands near 50/50."""
        sides = [b.batter_side for lu in standard_lineups() for b in lu]
        assert sides.count('R') == sides.count('L') == 9


class TestLandingAngle:
    def test_matches_the_engine_convention(self):
        assert _landing_angle(100.0, 50.0) == pytest.approx(
            math.degrees(math.atan2(50.0, 100.0)))

    def test_behind_the_plate_exceeds_ninety(self):
        assert _landing_angle(-30.0, 20.0) > 90.0

    def test_side_sign_does_not_change_the_angle(self):
        assert _landing_angle(80.0, 40.0) == pytest.approx(_landing_angle(80.0, -40.0))
