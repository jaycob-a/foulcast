"""
Build `foulball/league_lineup.py`: eighteen real batters who stand for the
league, chosen from `.cache/spray_profiles.json` by a rule written down here.

Why this exists
---------------
The site used to simulate the 2024 Yankees and Red Sox from eighteen profiles
typed by hand into `batter_profiles.py`. Nothing could regenerate them, their
fouls-per-plate-appearance ran a fifth above the computed 2025-26 figures for
the same players, and every one of them carried the 50% default for pull
tendency, so the per-batter spray data played no part in the site's figures
(LIMITATIONS.md 2.4). This script replaces them with profiles computed from
Statcast and picks the batters by a rule rather than by club.

The population
--------------
`.cache/spray_profiles.json` is built by `rebuild_spray_profiles.py` from the
2025 season and 2026 to date; each entry carries the batter's tracked-foul
count, fouls per plate appearance, exit-velocity and launch-angle moments on
fouls, and fair-ball pull share from `hc_x`. The population here is every
batter who appeared in the file's latest season and has at least
`MIN_TRACKED_FOULS` tracked fouls — about a season's worth for a regular — so
every figure used is estimated from a few hundred balls.

The rule
--------
Each batter is weighted by plate appearances in the window, reconstructed as
tracked fouls divided by fouls per plate appearance (the two figures the file
carries; tracking coverage is near-uniform across batters, so the proxy is
proportional to real plate appearances). The league is the PA-weighted mean of
each statistic over the population.

Nine right-handed and nine left-handed batters are taken, because the
population's plate appearances split within a point of 50/50 by the side the
batter actually stood on (`stand` is the modal side in the window, which puts
a switch-hitter on the side they bat most — left, against the right-handed
pitch mix the site simulates). Within each side the batters are sorted by
fouls per plate appearance and cut into nine strata of equal plate-appearance
share, so the lineup spans the league's distribution of the one statistic that
sets how many fouls a game produces, rather than clustering at its centre. In
each stratum the batter chosen is the one whose exit velocity, launch angle
(mean and spread of each) and pull share sit nearest the league's PA-weighted
means, in units of the between-batter standard deviation. No batter is used
twice.

The eighteen are dealt into two lineups of nine by alternating strata, so each
lineup carries both hands and the full range of foul rates; the two lineups
sum to one game and the split between them changes nothing but the order the
random draws are consumed in.

What the profiles do not carry
------------------------------
The cache has no per-pitch-type foul rates, no plate-location tendency and no
quartiles, so `foul_rates` is left empty (the engine then uses the league
pitch-type rates), `avg_plate_x_on_foul` stays at the centre of the plate and
the quartile fields are set to NaN rather than left at the class defaults,
which look like data and are not.

Run `python build_league_lineup.py` after `rebuild_spray_profiles.py` to
regenerate; the output module records the cache it was built from and the
residuals between the lineup and the league.
"""
import json
import os
import sys
from datetime import date

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, '.cache', 'spray_profiles.json')
OUT = os.path.join(ROOT, 'foulball', 'league_lineup.py')

MIN_TRACKED_FOULS = 200
PER_SIDE = 9
STATS = ('fouls_per_pa', 'ev_mean', 'ev_std', 'la_mean', 'la_std', 'fair_pull_pct')
MATCH_ON = ('ev_mean', 'ev_std', 'la_mean', 'la_std', 'fair_pull_pct')


def load_population(path: str = CACHE) -> list[dict]:
    with open(path, encoding='utf-8') as fh:
        raw = json.load(fh)
    latest = max(v['last_game'] for v in raw.values())[:4]
    pop = []
    for pid, v in raw.items():
        if v['fouls_per_pa'] <= 0 or v['ev_mean'] is None or v['la_mean'] is None:
            continue
        if v['last_game'][:4] != latest or v['n_fouls'] < MIN_TRACKED_FOULS:
            continue
        pop.append(dict(v, player_id=int(pid), pa=v['n_fouls'] / v['fouls_per_pa']))
    return pop


def league_means(pop: list[dict]) -> tuple[dict, dict]:
    w = np.array([b['pa'] for b in pop])
    mu, sd = {}, {}
    for f in STATS:
        x = np.array([b[f] for b in pop], dtype=float)
        mu[f] = float(np.average(x, weights=w))
        sd[f] = float(np.sqrt(np.average((x - mu[f]) ** 2, weights=w)))
    return mu, sd


def choose(pop: list[dict], mu: dict, sd: dict) -> list[dict]:
    """Nine per side, one per fouls-per-PA stratum, nearest the league."""
    chosen = []
    for hand in ('R', 'L'):
        side = sorted((b for b in pop if b['stand'] == hand),
                      key=lambda b: (b['fouls_per_pa'], b['player_id']))
        w = np.array([b['pa'] for b in side])
        mid = (np.cumsum(w) - w / 2.0) / w.sum()         # each batter's PA midpoint
        for i in range(PER_SIDE):
            lo, hi = i / PER_SIDE, (i + 1) / PER_SIDE
            stratum = [b for b, m in zip(side, mid) if lo <= m < hi]
            assert stratum, f'{hand} stratum {i} is empty'
            best = min(stratum, key=lambda b: (
                sum(((b[f] - mu[f]) / sd[f]) ** 2 for f in MATCH_ON), b['player_id']))
            best = dict(best, stratum=i)
            chosen.append(best)
    assert len({b['player_id'] for b in chosen}) == len(chosen), 'a batter was picked twice'
    return chosen


def deal(chosen: list[dict]) -> tuple[list[dict], list[dict]]:
    """Two lineups by alternating strata: even R and odd L to the first."""
    first, second = [], []
    for b in chosen:
        even = b['stratum'] % 2 == 0
        to_first = even if b['stand'] == 'R' else not even
        (first if to_first else second).append(b)
    return first, second


def render(chosen, first, second, mu, pop, cache_stamp) -> str:
    lineup_mu = {f: float(np.mean([b[f] for b in chosen])) for f in STATS}
    lines = []
    for b in chosen:
        lines.append(f"""    {b['name']!r}: BatterFoulProfile(
        player_name={b['name']!r}, player_id={b['player_id']}, batter_side={b['stand']!r},
        total_fouls={b['n_fouls']}, fouls_with_tracking={b['n_fouls']},
        ev_mean={b['ev_mean']}, ev_std={b['ev_std']},
        ev_25=_NAN, ev_50=_NAN, ev_75=_NAN,
        la_mean={b['la_mean']}, la_std={b['la_std']},
        la_25=_NAN, la_50=_NAN, la_75=_NAN,
        fair_pull_pct={b['fair_pull_pct']},
        fouls_per_pa={b['fouls_per_pa']},
    ),""")
    resid = '\n'.join(
        f"#   {f:14s} league {mu[f]:7.2f}   lineup {lineup_mu[f]:7.2f}   diff {lineup_mu[f] - mu[f]:+6.2f}"
        for f in STATS)
    names_first = ', '.join(b['name'] for b in first)
    names_second = ', '.join(b['name'] for b in second)
    return f'''"""
GENERATED by build_league_lineup.py on {date.today().isoformat()} — do not edit by hand.

Eighteen batters who stand for the league, computed from Statcast 2025-26 via
`.cache/spray_profiles.json` ({cache_stamp}). The rule that picked them is in
`build_league_lineup.py`; in short: every batter active in the file's latest
season with at least {MIN_TRACKED_FOULS} tracked fouls ({len(pop)} batters), nine from each
side of the plate, one from each of nine plate-appearance-weighted strata of
fouls per plate appearance, each the batter in their stratum whose exit
velocity, launch angle and pull share sit nearest the league's
plate-appearance-weighted means.

How close the eighteen sit to the league (simple means over the eighteen
against the PA-weighted population means):
{resid}

Lineup one: {names_first}.
Lineup two: {names_second}.

Every figure here is computed, dated and regenerable, which is what the
hand-typed 2024 profiles in `batter_profiles.py` were not. `fair_pull_pct` is
the batter's real fair-ball pull share, so the spray model's pull term is
active for the first time on the site. There are no per-pitch-type foul rates
in the cache, so `foul_rates` is empty and the engine falls back to the league
rates; the quartile fields are NaN because the cache carries moments only.
"""
from .batter_profiles import BatterFoulProfile

_NAN = float('nan')

LEAGUE_LINEUP_2025_26: dict[str, BatterFoulProfile] = {{
{chr(10).join(lines)}
}}

_FIRST = {[b['name'] for b in first]!r}
_SECOND = {[b['name'] for b in second]!r}


def league_lineups() -> list[list[BatterFoulProfile]]:
    """The two lineups that make one standard game, in a fixed order."""
    return [[LEAGUE_LINEUP_2025_26[n] for n in _FIRST],
            [LEAGUE_LINEUP_2025_26[n] for n in _SECOND]]
'''


def main() -> None:
    pop = load_population()
    mu, sd = league_means(pop)
    chosen = choose(pop, mu, sd)
    first, second = deal(chosen)
    stamp = f"{len(json.load(open(CACHE, encoding='utf-8')))} batters, " \
            f"latest game {max(b['last_game'] for b in pop)}"
    text = render(chosen, first, second, mu, pop, stamp)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    print(f'wrote {OUT}')
    for b in chosen:
        print(f"  {b['stand']} {b['stratum']} {b['name']:22s} fpa {b['fouls_per_pa']:.3f} "
              f"ev {b['ev_mean']:5.1f} la {b['la_mean']:5.1f} pull {b['fair_pull_pct']:5.1f}")
    for f in STATS:
        print(f"  {f:14s} league {mu[f]:7.2f} lineup {np.mean([b[f] for b in chosen]):7.2f}")


if __name__ == '__main__':
    main()
