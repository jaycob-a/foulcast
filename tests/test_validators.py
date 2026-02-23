"""
Unit tests for foulball/validators.py.
"""
import math
import numpy as np
import pytest

from foulball.validators import (
    validate_trajectory,
    validate_side_consistency,
    validate_sample,
    validate_monte_carlo_completeness,
)
from foulball.trajectory import TrajectoryResult


def _make_traj(**overrides):
    """Build a minimal valid TrajectoryResult."""
    defaults = dict(
        positions=np.array([[0, 0, 3], [50, 30, 10], [100, 60, 0]]),
        landing_x=100.0,
        landing_y=60.0,
        landing_z=0.0,
        landing_distance=116.6,
        max_height=10.0,
        flight_time=2.5,
        landing_speed=55.0,
    )
    defaults.update(overrides)
    return TrajectoryResult(**defaults)


class TestValidateTrajectory:
    def test_valid(self):
        assert validate_trajectory(_make_traj()) == []

    def test_negative_distance(self):
        v = validate_trajectory(_make_traj(landing_distance=-5.0))
        assert any('negative' in s for s in v)

    def test_nan_speed(self):
        v = validate_trajectory(_make_traj(landing_speed=float('nan')))
        assert any('NaN' in s for s in v)

    def test_negative_max_height(self):
        v = validate_trajectory(_make_traj(max_height=-1.0))
        assert any('max_height' in s for s in v)

    def test_nan_landing_position(self):
        v = validate_trajectory(_make_traj(landing_x=float('nan')))
        assert any('NaN' in s for s in v)

    def test_nan_landing_z(self):
        v = validate_trajectory(_make_traj(landing_z=float('nan')))
        assert any('landing_z' in s for s in v)

    def test_positions_with_nan(self):
        bad_pos = np.array([[0, 0, 3], [float('nan'), 30, 10], [100, 60, 0]])
        v = validate_trajectory(_make_traj(positions=bad_pos))
        assert any('non-finite' in s for s in v)

    def test_positions_with_inf(self):
        bad_pos = np.array([[0, 0, 3], [float('inf'), 30, 10], [100, 60, 0]])
        v = validate_trajectory(_make_traj(positions=bad_pos))
        assert any('non-finite' in s for s in v)

    def test_positions_wrong_shape(self):
        bad_pos = np.array([[0, 0], [50, 30]])  # 2D not 3D
        v = validate_trajectory(_make_traj(positions=bad_pos))
        assert any('wrong shape' in s for s in v)

    def test_unrealistic_speed(self):
        v = validate_trajectory(_make_traj(landing_speed=250.0))
        assert any('unrealistic' in s for s in v)

    def test_unrealistic_distance(self):
        v = validate_trajectory(_make_traj(landing_distance=700.0))
        assert any('unrealistic' in s for s in v)

    def test_unrealistic_height(self):
        v = validate_trajectory(_make_traj(max_height=600.0))
        assert any('unrealistic' in s for s in v)

    def test_negative_flight_time(self):
        v = validate_trajectory(_make_traj(flight_time=-1.0))
        assert any('flight_time' in s for s in v)


class TestValidateSideConsistency:
    def test_consistent_1b(self):
        assert validate_side_consistency(50.0, '1B') == []

    def test_consistent_3b(self):
        assert validate_side_consistency(-50.0, '3B') == []

    def test_inconsistent_positive_3b(self):
        v = validate_side_consistency(50.0, '3B')
        assert len(v) == 1

    def test_inconsistent_negative_1b(self):
        v = validate_side_consistency(-50.0, '1B')
        assert len(v) == 1

    def test_zero_landing(self):
        # y=0 is ambiguous but should not fail
        assert validate_side_consistency(0.0, '1B') == []
        assert validate_side_consistency(0.0, '3B') == []


class TestValidateSample:
    def test_valid(self):
        assert validate_sample({'exit_velocity': 75.0, 'launch_angle': 30.0}) == []

    def test_zero_ev(self):
        v = validate_sample({'exit_velocity': 0.0, 'launch_angle': 30.0})
        assert any('exit_velocity' in s for s in v)

    def test_extreme_launch_angle(self):
        v = validate_sample({'exit_velocity': 75.0, 'launch_angle': 95.0})
        assert any('launch_angle' in s for s in v)

    def test_negative_ev(self):
        v = validate_sample({'exit_velocity': -10.0, 'launch_angle': 30.0})
        assert any('exit_velocity' in s for s in v)


class TestValidateMCCompleteness:
    def test_valid(self):
        assert validate_monte_carlo_completeness(9, 300, 2500, 50, 150) == []

    def test_exact_match(self):
        # All accounted for
        assert validate_monte_carlo_completeness(1, 100, 80, 10, 10) == []

    def test_over_count(self):
        v = validate_monte_carlo_completeness(1, 100, 80, 20, 10)
        assert len(v) == 1
        assert 'accounted' in v[0]

    def test_under_count_ok(self):
        # Some sims unaccounted (e.g. no section match) is fine
        assert validate_monte_carlo_completeness(1, 100, 50, 10, 5) == []
