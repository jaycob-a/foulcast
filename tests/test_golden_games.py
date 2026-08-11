"""
Golden-game regression tests.

5 matchups across different parks, handedness mixes, pitch mixes.
Fixed seed (42), snapshots locked as baselines.

To regenerate baselines after intentional changes:
    pytest tests/test_golden_games.py --regen-golden
"""
import numpy as np
import pytest

from foulball.batter_profiles import (
    BatterFoulProfile,
    YANKEES_2024_PROFILES,
    RED_SOX_2024_PROFILES,
    PITCHER_PROFILES,
)
from foulball.stadium import STADIUMS
from foulball.matchup_engine import predict_game_fouls


def _run_golden(lineup, pitcher_name, pitch_mix, stadium_key, sims=300):
    """Run a prediction and extract snapshot metrics."""
    np.random.seed(42)
    stadium = STADIUMS[stadium_key]()
    pred = predict_game_fouls(lineup, pitcher_name, pitch_mix, stadium, sims)

    events = pred.all_events
    total = len(events)

    # Top 10 sections by catchable fouls. Sections published as fully behind
    # netting are not in `top_sections` at all (Step 10), so this list can be
    # shorter than 10 at a park whose netting is mapped.
    top10 = [sp.section.section_id for sp in pred.top_sections[:10]]

    # Sections held out of the ranking by netting, locked separately so a
    # change in the netting join shows up as its own diff rather than as an
    # unexplained reshuffle of top10.
    netted = sorted(sp.section.section_id for sp in pred.netted_sections)

    # Mean distance and spray angle
    distances = [e.landing_distance for e in events]
    angles = [abs(e.trajectory.landing_y) for e in events]
    mean_dist = np.mean(distances) if distances else 0
    mean_angle = np.mean(angles) if angles else 0

    # 1B/3B split
    n_1b = sum(1 for e in events if e.landing_side == '1B')
    n_3b = sum(1 for e in events if e.landing_side == '3B')

    # Fail count from section = None
    no_section = sum(1 for e in events if e.section is None)

    return {
        'total': total,
        'top10': top10,
        'netted': netted,
        'mean_dist': round(mean_dist, 1),
        'mean_angle': round(mean_angle, 1),
        'n_1b': n_1b,
        'n_3b': n_3b,
        'no_section': no_section,
    }


# ===== Baselines =====
# ===== Relocked 2026-08-10 (Step 10) after the netting layer =====
# Sections published as fully behind protective netting are excluded from the
# souvenir ranking: a ball into a net is not a souvenir. They are held in
# `pred.netted_sections` instead, where the safety view reads the same fouls as
# the hazard the net exists to stop. See `foulball/netting.py`.
#
# Nothing about the physics, the spray model or the geometry moved, and the
# numbers show it: `total`, `mean_dist`, `mean_angle`, `n_1b`, `n_3b` and
# `no_section` are byte-identical to the Step 9b lock at all five games. The
# balls land exactly where they landed before. Only what a landing *means*
# changed.
#
# Three of the five games moved, and the third did not, for a reason worth
# recording:
#
#   - Both Fenway games drop from 10 ranked sections to 7. The Red Sox publish
#     netting from Field Box 79 round to Field Box 9, which covers four of
#     Fenway's five field-box zones outright — including HOME-F, which had led
#     both rankings. The new leader is 3B-LB1, a Loge zone behind and above the
#     net. 3B-DUG stays in at rank 4 as `partially_netted` (FB71-79 of FB71-82
#     are netted), flagged as an upper bound rather than dropped.
#   - The Dodger game drops from 10 to 9, losing HOME-F, 1B-FB1 and 3B-FB1.
#     HOME-DC keeps the top rank: the Dugout Club is a DG-series product the
#     club's netting page never names, so it is `unknown`, and an unknown zone
#     stays in the ranking flagged rather than being excluded on a guess.
#   - Neither Yankee game moves at all. The Yankees publish the most detailed
#     netting page in the league (011 → 029, with five separate heights), and
#     none of it can be joined: the club numbers the infield field level
#     011-029 and this park's zone table numbers it 109-131. The join is
#     rejected, every Yankee zone is `unknown`, and nothing is excluded. That
#     is the intended behaviour — a park with data the model cannot place shows
#     a gap, not an assumption — and the identical baselines are the proof.
#
# ===== Relocked 2026-08-10 (Step 9b) after the cover flag and backstop anchor =====
# Two follow-ups to the sourced-parameter layer, both in `stadium.py`:
#
#   1. The flat 0.60 overhang cap is gone, replaced by a per-park `upper_cover`
#      classification. Where the published upper-deck percentage is shade from
#      a dome or retractable roof 150+ ft up (6 parks), it is discarded — a
#      foul pop flies under it. Where it is a deck or a grandstand canopy (21
#      parks), it is applied in full, uncapped. Making 100% mean 100% also
#      required resolving decks front-to-back rather than all against the
#      un-overhung bowl; see the step-3 comment in `_sourced_bands`.
#   2. The behind-plate bowl front is anchored to the park's backstop at all 31
#      parks. The template put it 2.7-23.0 ft in front of the backstop
#      everywhere (median 6.8), which is physically impossible. The anchor
#      targets `backstop_ft + 1.0`, not `backstop_ft`: Clem's figure measures
#      to the rear fence, and seats stand behind a fence rather than on it.
#      See `_SEAT_SETBACK_FT` for why the clearance is 1 ft.
#
# Still a geometry-only change, and still visible as one: `total`, `mean_dist`,
# `mean_angle`, `n_1b` and `n_3b` are byte-identical to the previous lock at all
# five games. Only section assignment and `no_section` moved.
#
# `no_section` rose at all five (1009 -> 1025, 937 -> 992, 994 -> 1045,
# 973 -> 987, 914 -> 980), which is the anchor doing what it should: pushing the
# behind-plate bowl back off the plate opens a genuine annulus of foul ground
# between the plate and the front row, and fouls that die in it now correctly
# match nothing instead of being caught by seats that cannot exist there. The
# Dodger game moves most (+66) because its anchor shift is the largest in the
# fleet at 23 ft, and its HOME-DC dugout club consequently overtakes HOME-B for
# the top rank.
#
# The 1 ft seat setback accounts for 1 to 7 of those, on its own: it was added
# after the anchor and cost +1, +7, +5, +3 and +5 respectively. That is the
# intended scale — it fixes the sign of a definitional error, not its size.
#
# Fenway is the one park here with a blocking upper cover (60% canopy) now
# applied uncapped, and its two games' `HOME-U` slips one rank in each top-10.
# Yankee Stadium's 55% is a split-deck figure, below the old cap, so nothing
# there changed on that account.
#
# ===== Relocked 2026-08-09 (Step 9) after the sourced park parameters =====
# `stadium.py` gained a sourced-parameter layer: each park's distance bands are
# now scaled by its published foul-territory area and Clem's backstop distance,
# and pulled in at the rear by Clem's 2016 deck-overhang percentages. See
# PARK_PARAMS.md and the "Sourced per-park physical parameters" block.
#
# This is a geometry-only change and the numbers show it: `total`, `mean_dist`,
# `mean_angle`, `n_1b` and `n_3b` are byte-identical at all five games, because
# nothing about the physics or the spray model moved. Only section assignment
# and `no_section` changed.
#
# `no_section` moved in both directions, which is the expected signature of
# replacing hand-tuned scales with sourced ones. Both Fenway games improved
# sharply (1060 -> 937 and 1144 -> 994): the old hand-tuned `scale = 0.85`
# left gaps between decks, and Fenway's sourced area scale of 0.889 closes
# them. The three unscaled parks lost a little (Yankee 957 -> 1009 and
# 916 -> 973, Dodger 876 -> 914) because their bands now sit slightly deeper
# or shallower than the one-size template they shared.
#
# ===== Relocked 2026-08-09 after the *-UB angle fix =====
# The two Yankee Stadium games were relocked 2026-08-09 after *-UB angle_max
# was corrected from 55 to 45 to match the 28 parks that use 10-45 (Step 7).
# Only section assignment moved: total, mean_dist, mean_angle, n_1b and n_3b
# are byte-identical, which is the signature of a geometry-only change.
# `no_section` rose (921 -> 957, 878 -> 916) because the 45-55 wedge lost a
# candidate deck, and 1B-FB1/3B-FB1 swapped ranks with 1B-LB1/3B-LB1, which
# were already adjacent.
#
# ===== Relocked 2026-08-07 after the straight-back spray mode =====
# Previous lock was taken right after the P1 landing-intersection fix, when the
# spray model still clamped every foul in front of the plate. Adding the
# backward-deflection mode moved roughly a fifth of all fouls into the backstop
# wedge, so every metric here shifted: mean distance dropped (backward fouls
# come off the bat slower and land nearer the plate) and the behind-home
# sections moved from the bottom of the rankings to the top.
_BASELINES = {
    'yanks_vs_cole_yankee': {
        'total': 2504,
        'top10': ['HOME-F', 'HOME-B', '3B-LR', '1B-DUG', '1B-LR', '3B-FB1', '1B-FB1', '1B-LB1', '3B-DUG', '3B-LB1'],
        'netted': [],
        'mean_dist': 131.0,
        'mean_angle': 73.3,
        'n_1b': 1329,
        'n_3b': 1175,
        'no_section': 1025,
    },
    'sox_vs_bello_fenway': {
        'total': 2476,
        'top10': ['3B-LB1', '1B-LB1', 'HOME-B', '3B-DUG', 'HOME-U', '1B-UB', '3B-UB'],
        'netted': ['1B-DUG', '1B-FB1', '3B-FB1', 'HOME-F'],
        'mean_dist': 129.4,
        'mean_angle': 71.0,
        'n_1b': 1204,
        'n_3b': 1272,
        'no_section': 992,
    },
    'yanks_vs_houck_fenway': {
        'total': 2487,
        'top10': ['3B-LB1', '1B-LB1', 'HOME-B', '3B-DUG', 'HOME-U', '1B-UB', '3B-UB'],
        'netted': ['1B-DUG', '1B-FB1', '3B-FB1', 'HOME-F'],
        'mean_dist': 134.2,
        'mean_angle': 73.3,
        'n_1b': 1279,
        'n_3b': 1208,
        'no_section': 1045,
    },
    'sox_vs_cortes_yankee': {
        'total': 2502,
        'top10': ['HOME-F', 'HOME-B', '3B-LR', '1B-FB1', '3B-DUG', '1B-DUG', '3B-FB1', '1B-LB1', '1B-LR', '3B-LB1'],
        'netted': [],
        'mean_dist': 128.9,
        'mean_angle': 72.2,
        'n_1b': 1207,
        'n_3b': 1295,
        'no_section': 987,
    },
    'yanks_vs_bello_dodger': {
        'total': 2477,
        'top10': ['HOME-DC', 'HOME-B', '1B-DUG', '3B-DUG', '1B-LB1', '1B-UB', '3B-UB', '3B-LB1', 'HOME-U'],
        'netted': ['1B-FB1', '3B-FB1', 'HOME-F'],
        'mean_dist': 137.4,
        'mean_angle': 75.1,
        'n_1b': 1253,
        'n_3b': 1224,
        'no_section': 980,
    },
}


def _yanks_lineup():
    return list(YANKEES_2024_PROFILES.values())

def _sox_lineup():
    return list(RED_SOX_2024_PROFILES.values())


# 5 matchups:
GOLDEN_GAMES = {
    'yanks_vs_cole_yankee': {
        'lineup': _yanks_lineup,
        'pitcher': 'Gerrit Cole',
        'mix': PITCHER_PROFILES['Gerrit Cole']['pitch_mix'],
        'stadium': 'yankee_stadium',
    },
    'sox_vs_bello_fenway': {
        'lineup': _sox_lineup,
        'pitcher': 'Brayan Bello',
        'mix': PITCHER_PROFILES['Brayan Bello']['pitch_mix'],
        'stadium': 'fenway_park',
    },
    'yanks_vs_houck_fenway': {
        'lineup': _yanks_lineup,
        'pitcher': 'Tanner Houck',
        'mix': PITCHER_PROFILES['Tanner Houck']['pitch_mix'],
        'stadium': 'fenway_park',
    },
    'sox_vs_cortes_yankee': {
        'lineup': _sox_lineup,
        'pitcher': 'Nestor Cortes',
        'mix': PITCHER_PROFILES['Nestor Cortes']['pitch_mix'],
        'stadium': 'yankee_stadium',
    },
    'yanks_vs_bello_dodger': {
        'lineup': _yanks_lineup,
        'pitcher': 'Brayan Bello',
        'mix': PITCHER_PROFILES['Brayan Bello']['pitch_mix'],
        'stadium': 'dodger_stadium',
    },
}


@pytest.fixture(scope="session")
def regen_golden(request):
    return request.config.getoption("--regen-golden", default=False)


@pytest.mark.parametrize("game_key", GOLDEN_GAMES.keys())
def test_golden_game(game_key, regen_golden):
    """Run a golden-game matchup and compare to locked baseline."""
    g = GOLDEN_GAMES[game_key]
    result = _run_golden(g['lineup'](), g['pitcher'], g['mix'], g['stadium'])

    if regen_golden or game_key not in _BASELINES:
        _BASELINES[game_key] = result
        # Print for manual locking
        print(f"\n=== GOLDEN BASELINE: {game_key} ===")
        print(f"  total:      {result['total']}")
        print(f"  mean_dist:  {result['mean_dist']}")
        print(f"  mean_angle: {result['mean_angle']}")
        print(f"  1B/3B:      {result['n_1b']}/{result['n_3b']}")
        print(f"  no_section: {result['no_section']}")
        print(f"  top10:      {result['top10']}")
        if regen_golden:
            pytest.skip("Regenerating baseline")
        return

    baseline = _BASELINES[game_key]
    assert result['total'] == baseline['total'], \
        f"Total events changed: {result['total']} vs {baseline['total']}"
    assert result['top10'] == baseline['top10'], \
        f"Top 10 sections changed"
    assert result['netted'] == baseline.get('netted', []), \
        f"Netting-excluded sections changed: {result['netted']} vs " \
        f"{baseline.get('netted', [])}"
    assert result['mean_dist'] == pytest.approx(baseline['mean_dist'], abs=0.5), \
        f"Mean distance changed: {result['mean_dist']} vs {baseline['mean_dist']}"
    assert result['n_1b'] == baseline['n_1b'], \
        f"1B count changed: {result['n_1b']} vs {baseline['n_1b']}"
    assert result['n_3b'] == baseline['n_3b'], \
        f"3B count changed: {result['n_3b']} vs {baseline['n_3b']}"


@pytest.mark.parametrize("game_key", GOLDEN_GAMES.keys())
def test_golden_game_sanity(game_key):
    """Sanity checks on golden-game outputs (always run, no baseline needed)."""
    g = GOLDEN_GAMES[game_key]
    result = _run_golden(g['lineup'](), g['pitcher'], g['mix'], g['stadium'])

    # Must produce events
    assert result['total'] > 100, f"Too few events: {result['total']}"

    # Mean distance in plausible range
    assert 20 < result['mean_dist'] < 250, \
        f"Mean distance out of range: {result['mean_dist']}"

    # Both sides should get fouls
    assert result['n_1b'] > 0, "No 1B fouls"
    assert result['n_3b'] > 0, "No 3B fouls"

    # Not all fouls should be unsectioned
    sectioned = result['total'] - result['no_section']
    assert sectioned > result['total'] * 0.1, \
        f"Too few sectioned fouls: {sectioned}/{result['total']}"
