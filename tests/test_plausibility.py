"""
Physical plausibility tests for section assignment and foul volume.

These encode the real-world foul ball distribution that the original
mid-flight matching inverted (AUDIT.md P1): the lower bowl and the area
behind home plate receive most fouls; upper decks down the lines receive
few. Any regression that re-inverts the geometry fails here.

Configuration matches the BEFORE.md baseline: Yankee Stadium, the standard
Yankees lineup, a league-average RHP pitch mix, seed 42, 400 sims/batter.

Note on units: predict_game_fouls() takes ONE lineup, so a single call is
half a game. Anything compared against the real-world 30-40 fouls per game
has to sum both halves — see the `yankee_game` fixture.
"""
import collections

import numpy as np
import pytest

from foulball.batter_profiles import YANKEES_2024_PROFILES, RED_SOX_2024_PROFILES
from foulball.stadium import STADIUMS
from foulball.matchup_engine import predict_game_fouls

STANDARD_RHP_MIX = {'FF': 0.30, 'SL': 0.20, 'CH': 0.15, 'SI': 0.15, 'CU': 0.10, 'FC': 0.10}

# Yankee Stadium section groups
LOWER_BOWL = ['1B-DUG', '3B-DUG', '1B-FB1', '3B-FB1',
              '1B-LB1', '3B-LB1', '1B-LR', '3B-LR']
UPPER_DOWN_LINES = ['1B-UB', '3B-UB', '1B-UR', '3B-UR']
BEHIND_HOME = ['HOME-F', 'HOME-B', 'HOME-U', 'HOME-G']
GRANDSTAND_LINES = ['1B-UR', '3B-UR']


@pytest.fixture(scope='module')
def yankee_prediction():
    """One shared full-size prediction run (matches the BEFORE.md config)."""
    np.random.seed(42)
    stadium = STADIUMS['yankee_stadium']()
    lineup = list(YANKEES_2024_PROFILES.values())
    return predict_game_fouls(lineup, 'Standard RHP', STANDARD_RHP_MIX,
                              stadium, simulations_per_batter=400)


@pytest.fixture(scope='module')
def yankee_game():
    """A whole game at Yankee Stadium: both lineups, summed the way webapp_v2
    sums them. This is the object to compare against real-world foul counts."""
    np.random.seed(42)
    stadium = STADIUMS['yankee_stadium']()
    totals: collections.Counter = collections.Counter()
    for lineup in (list(RED_SOX_2024_PROFILES.values()),
                   list(YANKEES_2024_PROFILES.values())):
        pred = predict_game_fouls(lineup, 'Standard RHP', STANDARD_RHP_MIX,
                                  stadium, simulations_per_batter=400)
        for sp in pred.section_predictions:
            totals[sp.section.section_id] += sp.expected_fouls
    return totals


def _fouls_by_section(pred):
    return {sp.section.section_id: sp.expected_fouls
            for sp in pred.section_predictions}


class TestLowerBowlDominates:
    """The P1 inversion killer: upper decks must never outdraw the lower bowl."""

    def test_every_lower_bowl_section_beats_every_upper_section(self, yankee_prediction):
        fouls = _fouls_by_section(yankee_prediction)
        for upper_id in UPPER_DOWN_LINES:
            for lower_id in LOWER_BOWL:
                assert fouls.get(upper_id, 0.0) < fouls.get(lower_id, 0.0), (
                    f"Upper deck {upper_id} ({fouls.get(upper_id, 0.0):.2f}) received at "
                    f"least as many fouls as lower bowl {lower_id} "
                    f"({fouls.get(lower_id, 0.0):.2f}) — geometry inverted again?"
                )

    def test_top_five_sections_are_all_lower_bowl(self, yankee_prediction):
        top5 = yankee_prediction.top_sections[:5]
        for sp in top5:
            assert sp.section.level in ('field', 'lower'), (
                f"{sp.section.section_id} (level={sp.section.level}) ranked in the "
                f"top 5 with {sp.expected_fouls:.2f} expected fouls — upper decks "
                f"must not lead the rankings"
            )

    def test_upper_deck_share_is_minor(self, yankee_prediction):
        """Lower bowl + behind home must dwarf the upper decks down the lines."""
        fouls = _fouls_by_section(yankee_prediction)
        upper = sum(fouls.get(sid, 0.0) for sid in UPPER_DOWN_LINES)
        lower_and_home = (sum(fouls.get(sid, 0.0) for sid in LOWER_BOWL)
                          + sum(fouls.get(sid, 0.0) for sid in BEHIND_HOME))
        assert lower_and_home > 5 * upper, (
            f"Lower bowl + behind home ({lower_and_home:.2f}) should be at least "
            f"5x the upper decks down the lines ({upper:.2f})"
        )


class TestGameTotalIsRealistic:
    """AUDIT.md P2: absolute foul counts must be usable, not just rankings.

    A real MLB game puts roughly 30-40 foul balls into the stands. These bound
    the model to that, wide enough that ordinary run-to-run variation and a
    change of park or lineup will not trip them, tight enough that another 4x
    error cannot hide.
    """

    def test_total_fouls_into_stands_in_realistic_range(self, yankee_game):
        total = sum(yankee_game.values())
        assert 25.0 <= total <= 45.0, (
            f"A full game predicts {total:.1f} fouls into the stands. Real games "
            f"put 30-40 there. Below 25 means balls are being dropped (unmatched "
            f"sections, over-tight filters); above 45 means they are being "
            f"double-counted or the geometry is claiming balls that never "
            f"reached the seats."
        )

    def test_each_half_is_about_half_the_game(self, yankee_game):
        """Guards the units: one predict_game_fouls() call is half a game, and
        anyone reading its total as a game total is off by 2x."""
        np.random.seed(42)
        stadium = STADIUMS['yankee_stadium']()
        pred = predict_game_fouls(list(YANKEES_2024_PROFILES.values()),
                                  'Standard RHP', STANDARD_RHP_MIX, stadium,
                                  simulations_per_batter=400)
        half = sum(sp.expected_fouls for sp in pred.section_predictions)
        assert 12.0 <= half <= 23.0, (
            f"One lineup produced {half:.1f} fouls into the stands; a half-game "
            f"should be roughly half of 30-40"
        )


class TestBehindHomeReceivesFouls:
    """Behind-home seating must draw real foul traffic (it was ~0.2 pre-fix).

    The seats behind the plate take the straight-back fouls — foul tips, nicks
    and late swings — which is the single busiest direction a foul goes. Before
    the spray model could produce backward fouls at all these sections ranked
    last; they belong at the top.
    """

    def test_behind_home_is_the_busiest_group(self, yankee_game):
        home_total = sum(yankee_game.get(sid, 0.0) for sid in BEHIND_HOME)
        lower_total = sum(yankee_game.get(sid, 0.0) for sid in LOWER_BOWL)
        upper_total = sum(yankee_game.get(sid, 0.0) for sid in UPPER_DOWN_LINES)
        assert home_total > upper_total, (
            f"Behind home ({home_total:.2f}) drew fewer fouls than the upper "
            f"decks down the lines ({upper_total:.2f})"
        )
        # The lower bowl is eight sections against four, so it can out-total
        # behind-home; it must not dwarf it.
        assert home_total > lower_total * 0.4, (
            f"Behind home ({home_total:.2f}) is small next to the lower bowl "
            f"({lower_total:.2f}) — the straight-back wedge is under-populated"
        )

    def test_a_behind_home_section_ranks_in_the_top_three(self, yankee_game):
        top3 = [sid for sid, _ in yankee_game.most_common(3)]
        assert any(sid in BEHIND_HOME for sid in top3), (
            f"No behind-home section in the top three ({top3}) — the busiest "
            f"seats in the park are behind the plate"
        )

    def test_behind_home_beats_grandstand_down_lines(self, yankee_prediction):
        fouls = _fouls_by_section(yankee_prediction)
        home_total = sum(fouls.get(sid, 0.0) for sid in BEHIND_HOME)
        for sid in GRANDSTAND_LINES:
            assert home_total > fouls.get(sid, 0.0), (
                f"Behind-home group ({home_total:.2f}) received fewer fouls than "
                f"grandstand line section {sid} ({fouls.get(sid, 0.0):.2f})"
            )


class TestBallsLandWhereTheyComeDown:
    """Direct checks on the landing-section geometry, independent of the sim."""

    def test_high_fly_to_lower_bowl_not_assigned_upper_deck(self):
        """A fly ball descending into the lower bowl must not be claimed by the
        upper deck band it passed through mid-flight (the original P1 bug)."""
        from foulball.stadium import find_landing_section
        stadium = STADIUMS['yankee_stadium']()
        candidates = [s for s in stadium.sections if s.side in ('1B', 'HOME')]

        # Synthetic high fly: apex 120 ft, comes down at ~150 ft from the
        # plate at 20 degrees off the line — heart of the main level.
        d = np.linspace(0, 160, 80)
        z = 120 * np.sin(np.pi * d / 160)  # 0 at launch, apex 120, descending
        section = find_landing_section(candidates, angle=20.0,
                                       horiz_dists=d, heights=z)
        assert section is not None, "High fly to the lower bowl matched nothing"
        assert section.level in ('field', 'lower'), (
            f"High fly descending at 150 ft was assigned {section.section_id} "
            f"(level={section.level}) — mid-flight altitude matching is back"
        )

    def test_towering_deep_foul_can_reach_upper_deck(self):
        """A ball descending through ~65 ft at 200 ft horizontal, where no
        lower deck extends, belongs to the upper deck."""
        from foulball.stadium import find_landing_section
        stadium = STADIUMS['yankee_stadium']()
        candidates = [s for s in stadium.sections if s.side in ('1B', 'HOME')]

        # Parabolic arc: apex 115 ft at 120 ft out, still ~64 ft up at 200 ft.
        # At 45 degrees the main level ends at 180 ft; beyond is upper deck.
        d = np.linspace(0, 215, 80)
        z = 115 - 115 * ((d - 120) / 120) ** 2
        section = find_landing_section(candidates, angle=45.0,
                                       horiz_dists=d, heights=z)
        assert section is not None, "Towering deep foul matched nothing"
        assert section.level == 'upper', (
            f"Towering deep foul was assigned {section.section_id} "
            f"(level={section.level}), expected an upper deck"
        )

    def test_short_foul_over_infield_matches_nothing(self):
        """A popup coming down 40 ft from the plate lands in foul ground,
        not in any section."""
        from foulball.stadium import find_landing_section
        stadium = STADIUMS['yankee_stadium']()
        candidates = [s for s in stadium.sections if s.side in ('3B', 'HOME')]

        d = np.linspace(0, 42, 60)
        z = 80 * np.sin(np.pi * d / 44)
        section = find_landing_section(candidates, angle=30.0,
                                       horiz_dists=d, heights=z)
        assert section is None, (
            f"Popup landing 40 ft from the plate was assigned "
            f"{section.section_id if section else None} — foul ground has no seats"
        )

    def test_exposed_bands_are_a_partition(self):
        """At every angle, exposed bands must not overlap (true partition)."""
        from foulball.stadium import exposed_bands
        for key in ('yankee_stadium', 'fenway_park', 'dodger_stadium'):
            stadium = STADIUMS[key]()
            for side in ('1B', '3B'):
                candidates = [s for s in stadium.sections if s.side in (side, 'HOME')]
                for angle in np.arange(0.0, 121.0, 2.5):
                    bands = exposed_bands(candidates, float(angle))
                    for (_, a0, a1), (_, b0, b1) in zip(bands, bands[1:]):
                        assert a1 <= b0 + 1e-6, (
                            f"{stadium.name} {side} angle={angle}: bands "
                            f"[{a0:.1f},{a1:.1f}] and [{b0:.1f},{b1:.1f}] overlap"
                        )
