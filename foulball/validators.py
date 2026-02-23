"""
Runtime invariant validators for FoulCast.

Each function returns a list of violation strings (empty = pass).
"""
import math
import numpy as np


def validate_trajectory(traj) -> list[str]:
    """Validate a TrajectoryResult after simulation."""
    violations = []

    # Scalar field checks
    if traj.landing_distance < 0:
        violations.append(f"landing_distance negative: {traj.landing_distance}")
    if math.isnan(traj.landing_speed):
        violations.append("landing_speed is NaN")
    if traj.max_height < 0:
        violations.append(f"max_height negative: {traj.max_height}")
    if math.isnan(traj.landing_distance):
        violations.append("landing_distance is NaN")
    if math.isnan(traj.landing_x) or math.isnan(traj.landing_y):
        violations.append(f"landing position has NaN: x={traj.landing_x}, y={traj.landing_y}")
    if math.isnan(traj.landing_z):
        violations.append("landing_z is NaN")

    # Positions array checks
    pos = traj.positions
    if pos.ndim != 2 or pos.shape[1] != 3:
        violations.append(f"positions has wrong shape: {pos.shape}, expected (N, 3)")
    elif len(pos) > 0:
        if not np.all(np.isfinite(pos)):
            n_bad = np.count_nonzero(~np.isfinite(pos))
            violations.append(f"positions contains {n_bad} non-finite values (NaN/inf)")

    # Realistic bounds
    if traj.landing_speed > 200:
        violations.append(f"landing_speed unrealistic: {traj.landing_speed:.1f} mph")
    if traj.landing_distance > 600:
        violations.append(f"landing_distance unrealistic: {traj.landing_distance:.1f} ft")
    if traj.max_height > 500:
        violations.append(f"max_height unrealistic: {traj.max_height:.1f} ft")
    if traj.flight_time < 0:
        violations.append(f"flight_time negative: {traj.flight_time}")

    return violations


def validate_side_consistency(landing_y: float, side: str) -> list[str]:
    """Validate that landing_y sign matches the reported side."""
    violations = []
    if landing_y > 0 and side == '3B':
        violations.append(f"landing_y={landing_y:.1f} is positive but side='3B'")
    if landing_y < 0 and side == '1B':
        violations.append(f"landing_y={landing_y:.1f} is negative but side='1B'")
    return violations


def validate_sample(sample: dict) -> list[str]:
    """Validate a batter.sample_foul() output."""
    violations = []
    ev = sample.get('exit_velocity', 0)
    la = sample.get('launch_angle', 0)
    if ev <= 0:
        violations.append(f"exit_velocity <= 0: {ev}")
    if la < -90 or la > 90:
        violations.append(f"launch_angle out of range [-90,90]: {la}")
    return violations


def validate_monte_carlo_completeness(
    n_batters: int,
    sims_per_batter: int,
    n_events: int,
    n_failed: int,
    n_skipped: int,
) -> list[str]:
    """Validate that accounted sims <= attempted sims."""
    violations = []
    attempted = n_batters * sims_per_batter
    accounted = n_events + n_failed + n_skipped
    if accounted > attempted:
        violations.append(
            f"accounted ({accounted}) > attempted ({attempted}): "
            f"events={n_events}, failed={n_failed}, skipped={n_skipped}"
        )
    return violations
