"""
The league-representative lineup the site simulates (Step 27).

`foulball/league_lineup.py` is generated from `.cache/spray_profiles.json` by
`build_league_lineup.py`. These hold the generated module to the rule that is
supposed to have produced it, so that a hand edit, a stale regeneration or a
drifted cache shows up as a failure rather than as a quietly different lineup.
"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import build_league_lineup as gen
from foulball.league_lineup import LEAGUE_LINEUP_2025_26, league_lineups


@pytest.fixture(scope='module')
def population():
    return gen.load_population()


@pytest.fixture(scope='module')
def rule_choice(population):
    mu, sd = gen.league_means(population)
    return gen.choose(population, mu, sd), mu, sd


def test_eighteen_batters_nine_a_side():
    sides = [b.batter_side for lu in league_lineups() for b in lu]
    assert len(sides) == 18
    assert sides.count('R') == sides.count('L') == 9
    assert all(len(lu) == 9 for lu in league_lineups())


def test_both_lineups_carry_both_hands():
    for lu in league_lineups():
        assert {b.batter_side for b in lu} == {'L', 'R'}


def test_the_module_is_what_the_rule_produces(rule_choice):
    """Regenerating from the committed cache must give the committed module."""
    chosen, _, _ = rule_choice
    assert [b['name'] for b in chosen] == list(LEAGUE_LINEUP_2025_26)
    for b in chosen:
        prof = LEAGUE_LINEUP_2025_26[b['name']]
        assert prof.player_id == b['player_id']
        assert prof.batter_side == b['stand']
        for src, dst in (('fouls_per_pa', 'fouls_per_pa'), ('ev_mean', 'ev_mean'),
                         ('ev_std', 'ev_std'), ('la_mean', 'la_mean'),
                         ('la_std', 'la_std'), ('fair_pull_pct', 'fair_pull_pct')):
            assert getattr(prof, dst) == b[src], (b['name'], src)


def test_every_profile_is_computed_not_defaulted():
    """The point of the switch: no 50% pull default, no class-default moments,
    and a foul rate for every batter."""
    for name, p in LEAGUE_LINEUP_2025_26.items():
        assert p.fair_pull_pct != 50.0, f'{name}: pull tendency is the default'
        assert 0.3 <= p.fouls_per_pa <= 2.0, f'{name}: fouls_per_pa {p.fouls_per_pa}'
        assert p.total_fouls >= gen.MIN_TRACKED_FOULS, name
        assert (p.ev_mean, p.ev_std, p.la_mean, p.la_std) != (76.0, 13.0, 23.0, 36.0), \
            f'{name}: moments are the class defaults'
        # The cache carries moments only; the quartile fields must not look
        # like data.
        assert all(math.isnan(v) for v in (p.ev_25, p.ev_50, p.ev_75,
                                            p.la_25, p.la_50, p.la_75)), name


def test_the_lineup_sits_on_the_league(rule_choice):
    """Simple means over the eighteen against the PA-weighted population means,
    within a fraction of the between-batter spread on every statistic."""
    _, mu, sd = rule_choice
    for f in gen.STATS:
        lineup_mean = np.mean([getattr(p, f) for p in LEAGUE_LINEUP_2025_26.values()])
        assert abs(lineup_mean - mu[f]) < 0.5 * sd[f], (
            f'{f}: lineup {lineup_mean:.2f} vs league {mu[f]:.2f} '
            f'(between-batter sd {sd[f]:.2f})')


def test_the_lineup_spans_the_foul_rate_range(rule_choice):
    """One batter per stratum means the lineup's range of fouls per PA covers
    most of the league's, rather than all eighteen sitting at the median."""
    _, mu, sd = rule_choice
    rates = sorted(p.fouls_per_pa for p in LEAGUE_LINEUP_2025_26.values())
    assert rates[0] < mu['fouls_per_pa'] - sd['fouls_per_pa']
    assert rates[-1] > mu['fouls_per_pa'] + sd['fouls_per_pa']


def test_no_batter_is_used_twice():
    ids = [p.player_id for p in LEAGUE_LINEUP_2025_26.values()]
    assert len(ids) == len(set(ids))
