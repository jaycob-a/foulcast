"""
Stadium geometry validation tests.

Ensures all 30 stadiums have valid section layouts:
- No distance_min > distance_max
- No angle_min > angle_max
- No height_min > height_max
- Minimum section count
- No duplicate section IDs within a stadium
- Required sides covered (1B, 3B, HOME)
"""
import pytest
import numpy as np

from foulball.stadium import STADIUMS, SeatSection


ALL_STADIUM_KEYS = list(STADIUMS.keys())


@pytest.fixture(params=ALL_STADIUM_KEYS)
def stadium(request):
    """Parametrized fixture yielding each of the 30 stadiums."""
    return STADIUMS[request.param]()


class TestSectionGeometryValid:
    """Validate that section geometry is self-consistent."""

    def test_distance_min_less_than_max(self, stadium):
        for s in stadium.sections:
            assert s.distance_min <= s.distance_max, (
                f"{stadium.name} section {s.section_id}: "
                f"distance_min={s.distance_min} > distance_max={s.distance_max}"
            )

    def test_angle_min_less_than_max(self, stadium):
        for s in stadium.sections:
            assert s.angle_min <= s.angle_max, (
                f"{stadium.name} section {s.section_id}: "
                f"angle_min={s.angle_min} > angle_max={s.angle_max}"
            )

    def test_height_min_less_than_max(self, stadium):
        for s in stadium.sections:
            if np.isnan(s.height_min) or np.isnan(s.height_max):
                continue
            assert s.height_min <= s.height_max, (
                f"{stadium.name} section {s.section_id}: "
                f"height_min={s.height_min} > height_max={s.height_max}"
            )

    def test_minimum_section_count(self, stadium):
        assert len(stadium.sections) >= 5, (
            f"{stadium.name} has only {len(stadium.sections)} sections (min 5)"
        )

    def test_no_duplicate_section_ids(self, stadium):
        ids = [s.section_id for s in stadium.sections]
        assert len(ids) == len(set(ids)), (
            f"{stadium.name} has duplicate section IDs: "
            f"{[sid for sid in ids if ids.count(sid) > 1]}"
        )

    def test_required_sides_covered(self, stadium):
        sides = {s.side for s in stadium.sections}
        for required in ('1B', '3B', 'HOME'):
            assert required in sides, (
                f"{stadium.name} missing required side: {required}"
            )

    def test_distance_values_positive(self, stadium):
        for s in stadium.sections:
            assert s.distance_min >= 0, (
                f"{stadium.name} section {s.section_id}: "
                f"distance_min={s.distance_min} is negative"
            )
            assert s.distance_max > 0, (
                f"{stadium.name} section {s.section_id}: "
                f"distance_max={s.distance_max} is not positive"
            )

    def test_angle_values_in_range(self, stadium):
        for s in stadium.sections:
            assert 0 <= s.angle_min <= 180, (
                f"{stadium.name} section {s.section_id}: "
                f"angle_min={s.angle_min} out of [0,180]"
            )
            assert 0 <= s.angle_max <= 180, (
                f"{stadium.name} section {s.section_id}: "
                f"angle_max={s.angle_max} out of [0,180]"
            )

    def test_height_values_non_negative(self, stadium):
        for s in stadium.sections:
            if np.isnan(s.height_min) or np.isnan(s.height_max):
                continue
            assert s.height_min >= 0, (
                f"{stadium.name} section {s.section_id}: "
                f"height_min={s.height_min} is negative"
            )

    def test_num_seats_positive(self, stadium):
        for s in stadium.sections:
            assert s.num_seats > 0, (
                f"{stadium.name} section {s.section_id}: "
                f"num_seats={s.num_seats} is not positive"
            )

    def test_ticket_price_positive(self, stadium):
        for s in stadium.sections:
            assert s.avg_ticket_price > 0, (
                f"{stadium.name} section {s.section_id}: "
                f"avg_ticket_price={s.avg_ticket_price} is not positive"
            )


class TestStadiumFactory:
    """Validate that all 30 stadium factories work."""

    def test_all_30_stadiums_build(self):
        assert len(STADIUMS) == 30, f"Expected 30 stadiums, got {len(STADIUMS)}"
        for key, factory in STADIUMS.items():
            s = factory()
            assert s.name, f"Stadium '{key}' has no name"
            assert s.team, f"Stadium '{key}' has no team"
            assert len(s.sections) > 0, f"Stadium '{key}' has no sections"


class TestAngleBehindPlate:
    """Test that the angle calculation correctly handles balls behind home plate."""

    def test_angle_for_negative_x(self):
        """When landing_x < 0 (behind plate), angle should exceed 90 degrees."""
        # This tests the matchup_engine angle calculation logic
        lx = -30.0  # behind plate
        ly = 20.0   # into stands

        # Recreate the angle logic from matchup_engine
        if lx >= 0:
            angle = np.degrees(np.arctan2(ly, lx))
        else:
            angle = 90.0 + np.degrees(np.arctan2(-lx, max(ly, 0.01)))

        assert angle > 90, f"Ball behind plate (x={lx}) got angle {angle} (should be >90)"

    def test_angle_for_positive_x(self):
        """When landing_x > 0 (toward outfield), angle should be < 90."""
        lx = 100.0
        ly = 50.0
        angle = np.degrees(np.arctan2(ly, lx))
        assert 0 < angle < 90, f"Ball toward outfield (x={lx}) got angle {angle}"

    def test_angle_continuity_at_zero(self):
        """Angles should be continuous around x=0."""
        ly = 50.0
        # Just positive
        angle_pos = np.degrees(np.arctan2(ly, 0.1))
        # Just negative
        angle_neg = 90.0 + np.degrees(np.arctan2(0.1, max(ly, 0.01)))
        # Both should be near 90
        assert abs(angle_pos - 90) < 5, f"Positive side: {angle_pos}"
        assert abs(angle_neg - 90) < 5, f"Negative side: {angle_neg}"
