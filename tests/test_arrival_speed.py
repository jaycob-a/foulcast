"""
Step 27: the ball's speed where it reaches the seat, and the Magnus force.

Catchability used to read `landing_speed`, the speed at ground level, for a
ball that had stopped in a deck well above the ground. These pin the
per-step speeds the trajectory now carries and the contact row
`find_landing_contact` returns, through the two cases that go opposite ways:
a fly ball arrives at an upper deck slower than it would reach the ground, a
line drive arrives in the field boxes faster.
"""
import numpy as np
import pytest

from foulball.stadium import STADIUMS, find_landing_contact, find_landing_section
from foulball.trajectory import simulate_trajectory, simulate_foul_ball


def _contact(ev, la, spray=30.0, park='yankee_stadium', side='1B'):
    traj = simulate_trajectory(ev, la, spray)
    stadium = STADIUMS[park]()
    cands = [s for s in stadium.sections if s.side in (side, 'HOME')]
    d = np.hypot(traj.positions[:, 0], traj.positions[:, 1])
    sec, idx = find_landing_contact(cands, spray, d, traj.positions[:, 2])
    return traj, sec, idx


class TestSpeedsAlongTheFlight:
    def test_one_speed_per_position_and_the_ends_agree(self):
        traj = simulate_trajectory(85.0, 40.0, 30.0)
        assert traj.speeds is not None
        assert len(traj.speeds) == len(traj.positions)
        assert traj.speeds[0] == pytest.approx(85.0)
        assert traj.speeds[-1] == pytest.approx(traj.landing_speed)

    def test_speed_falls_to_the_apex_then_rises(self):
        traj = simulate_trajectory(85.0, 40.0, 30.0)
        apex = int(np.argmax(traj.positions[:, 2]))
        assert traj.speeds[apex] < traj.speeds[0]
        assert traj.speeds[-1] > traj.speeds[apex]


class TestArrivalAtTheSeat:
    def test_contact_row_is_above_ground_and_before_the_end(self):
        traj, sec, idx = _contact(90.0, 20.0)
        assert sec is not None
        assert 0 < idx < len(traj.positions) - 1
        assert traj.positions[idx, 2] > 1.0

    def test_contact_row_agrees_with_the_section_finder(self):
        traj, sec, idx = _contact(75.0, 35.0)
        stadium = STADIUMS['yankee_stadium']()
        cands = [s for s in stadium.sections if s.side in ('1B', 'HOME')]
        d = np.hypot(traj.positions[:, 0], traj.positions[:, 1])
        found = find_landing_section(cands, 30.0, d, traj.positions[:, 2])
        assert found.section_id == sec.section_id

    def test_a_fly_ball_arrives_at_the_upper_deck_slower_than_at_the_ground(self):
        traj, sec, idx = _contact(75.0, 35.0)
        assert sec is not None and sec.level == 'upper'
        assert traj.speeds[idx] < traj.landing_speed - 3.0

    def test_a_line_drive_arrives_in_the_field_boxes_faster_than_at_the_ground(self):
        traj, sec, idx = _contact(100.0, 12.0)
        assert sec is not None and sec.level == 'field'
        assert traj.speeds[idx] > traj.landing_speed + 3.0

    def test_no_seat_means_no_contact_row(self):
        traj, sec, idx = _contact(85.0, 40.0)   # ~300 ft: past the last deck
        assert sec is None and idx is None


class TestMagnusDirection:
    """The lift is perpendicular to the velocity about an axis fixed at
    contact. Two consequences a fixed vertical lift cannot reproduce."""

    def test_sidespin_does_not_push_a_vertical_popup_sideways(self):
        """With the lateral force proportional to horizontal speed, a ball
        launched almost straight up barely moves off its line."""
        up = simulate_trajectory(70.0, 88.0, 30.0)
        flat = simulate_trajectory(70.0, 20.0, 30.0)
        # lateral drift off the launch azimuth, per foot of horizontal travel
        def drift(t):
            x, y = t.landing_x, t.landing_y
            along = x * np.cos(np.radians(30)) + y * np.sin(np.radians(30))
            across = -x * np.sin(np.radians(30)) + y * np.cos(np.radians(30))
            return abs(across), along
        up_across, up_along = drift(up)
        flat_across, flat_along = drift(flat)
        assert up_across < 1.0
        assert flat_across / flat_along > up_across / max(up_along, 1e-6)

    def test_distances_are_close_to_the_pre_fix_model(self):
        """The direction moved, not the magnitude: a 40-degree 95 mph foul
        lands within 2% of where the fixed-lift model put it (349 ft)."""
        d = simulate_trajectory(95.0, 40.0, 30.0).landing_distance
        assert 340.0 < d < 349.0
