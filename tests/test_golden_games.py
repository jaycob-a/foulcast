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

    # Top 10 sections by catchable fouls
    top10 = [sp.section.section_id for sp in pred.top_sections[:10]]

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
        'mean_dist': round(mean_dist, 1),
        'mean_angle': round(mean_angle, 1),
        'n_1b': n_1b,
        'n_3b': n_3b,
        'no_section': no_section,
    }


# ========== Baselines (locked 2026-08-07 after P1 landing-intersection fix) ==========
_BASELINES = {
    'yanks_vs_cole_yankee': {
        'total': 2503,
        'top10': ['1B-DUG', '1B-LR', '3B-LR', '1B-LB1', '3B-DUG', '3B-LB1', '1B-FB1', '3B-FB1', '1B-UB', '3B-UB'],
        'mean_dist': 154.4,
        'mean_angle': 72.9,
        'n_1b': 1317,
        'n_3b': 1186,
        'no_section': 899,
    },
    'sox_vs_bello_fenway': {
        'total': 2501,
        'top10': ['3B-LB1', '1B-LB1', '1B-DUG', '3B-DUG', '1B-FB1', '3B-FB1', 'HOME-F', 'HOME-B', 'HOME-U'],
        'mean_dist': 149.9,
        'mean_angle': 69.4,
        'n_1b': 1215,
        'n_3b': 1286,
        'no_section': 1206,
    },
    'yanks_vs_houck_fenway': {
        'total': 2499,
        'top10': ['1B-LB1', '3B-LB1', '1B-DUG', '3B-DUG', '3B-FB1', '1B-FB1', 'HOME-B', 'HOME-F', 'HOME-U'],
        'mean_dist': 154.2,
        'mean_angle': 69.5,
        'n_1b': 1311,
        'n_3b': 1188,
        'no_section': 1275,
    },
    'sox_vs_cortes_yankee': {
        'total': 2483,
        'top10': ['3B-DUG', '1B-DUG', '1B-LR', '1B-FB1', '1B-LB1', '3B-LB1', '3B-LR', '3B-FB1', '1B-UB', '3B-UB'],
        'mean_dist': 148.4,
        'mean_angle': 70.2,
        'n_1b': 1209,
        'n_3b': 1274,
        'no_section': 893,
    },
    'yanks_vs_bello_dodger': {
        'total': 2533,
        'top10': ['1B-FB1', '3B-FB1', '1B-DUG', '3B-DUG', '1B-UB', '3B-UB', 'HOME-DC', '3B-LB1', 'HOME-B', '1B-LB1'],
        'mean_dist': 155.7,
        'mean_angle': 71.1,
        'n_1b': 1327,
        'n_3b': 1206,
        'no_section': 1003,
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


def pytest_addoption(parser):
    parser.addoption("--regen-golden", action="store_true", default=False)


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
