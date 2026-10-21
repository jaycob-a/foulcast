#!/usr/bin/env python3
"""
validate_538.py — the model against FiveThirtyEight's 906 observed foul balls.

The method is fixed in VALIDATION_PLAN.md, written and committed before this
script was first run. This file implements that plan and nothing else: it
runs the site's standard game at each park, bins every simulated foul into
FiveThirtyEight's zones by where the model says it came down, and scores the
result against the observed zone counts and the three baselines.

Usage:
    python validate_538.py                    # seed 42, 400 sims, all settings
    python validate_538.py --seeds 42 1 2 3   # extra seeds for the noise band
    python validate_538.py --out results.json --report tables.txt

No model code is touched. See VALIDATION.md for the results.
"""
import argparse
import csv
import json
import math
import os
import sys
import time

import numpy as np
from scipy.stats import chi2 as chi2_dist

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from foulball.stadium import STADIUMS                       # noqa: E402
from foulball.matchup_engine import predict_game_fouls      # noqa: E402
from site_build import standard_lineups, STANDARD_RHP_MIX, SEED, SIMS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data', 'fivethirtyeight_foul_balls.csv')

# (matchup as spelled in the CSV, 2019 venue per the MLB schedule API,
#  registry key or None, status). Only 'compared' parks enter the verdict.
PARKS = [
    ('Seattle Mariners VS Minnesota Twins', 'T-Mobile Park', 'tmobile_park', 'compared'),
    ('Baltimore Orioles VS Minnesota Twins', 'Oriole Park at Camden Yards', 'camden_yards', 'compared'),
    ('Pittsburgh Pirates VS Milwaukee Brewers', 'PNC Park', 'pnc_park', 'compared'),
    ("Oakland A's vs Houston Astros", 'Oakland Coliseum', None, 'no model'),
    ('Texas Rangers vs Toronto Blue Jays', 'Globe Life Park in Arlington', 'globe_life', 'different building'),
    ('Los Angeles Dodgers vs Arizona Diamondsbacks', 'Dodger Stadium', 'dodger_stadium', 'compared'),
    ('Milwaukee Brewers vs New York Mets', 'Miller Park', 'american_family', 'compared'),
    ('Philadelphia Phillies vs Miami Marlins', 'Citizens Bank Park', 'citizens_bank', 'compared'),
    ('Atlanta Braves vs New York Mets', 'SunTrust Park', 'truist_park', 'compared'),
    ('New York Yankees vs Baltimore Orioles', 'Yankee Stadium', 'yankee_stadium', 'compared'),
]
TEXAS = 'Texas Rangers vs Toronto Blue Jays'

GROUPS = ['Z1', 'Z23', 'Z45', 'Z67']
ZONE_TO_GROUP = {'1': 'Z1', '2': 'Z23', '3': 'Z23', '4': 'Z45',
                 '5': 'Z45', '6': 'Z67', '7': 'Z67'}
ZONES = ['1', '2', '3', '4', '5', '6', '7']

# Dugout ends along the foul line, feet from the plate. (50, 130) is the
# verdict setting; the other two are the pre-registered sensitivity runs.
DUGOUT_SETTINGS = [(50.0, 130.0), (40.0, 110.0), (60.0, 150.0)]
FLOOR = 0.005   # share floor before taking logs, applied to model and baselines

BASELINE_EVEN4 = {g: 0.25 for g in GROUPS}
BASELINE_EVEN7 = {'Z1': 1 / 7, 'Z23': 2 / 7, 'Z45': 2 / 7, 'Z67': 2 / 7}


# ------------------------------------------------------------------
# Observed
# ------------------------------------------------------------------

def load_observed(path: str = DATA) -> dict[str, dict]:
    """Per matchup: zone counts for the full set and the camera-confirmed set."""
    out: dict[str, dict] = {}
    with open(path, encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            m = out.setdefault(r['matchup'], {
                'all7': {z: 0 for z in ZONES}, 'cam7': {z: 0 for z in ZONES}})
            m['all7'][r['used_zone']] += 1
            if r['camera_zone']:
                m['cam7'][r['camera_zone']] += 1
    for m in out.values():
        m['all'] = group_counts(m['all7'])
        m['cam'] = group_counts(m['cam7'])
    return out


def group_counts(z7: dict[str, float]) -> dict[str, float]:
    g = {k: 0.0 for k in GROUPS}
    for z, n in z7.items():
        g[ZONE_TO_GROUP[z]] += n
    return g


def shares(counts: dict[str, float]) -> dict[str, float]:
    n = sum(counts.values())
    return {k: (v / n if n else 0.0) for k, v in counts.items()}


# ------------------------------------------------------------------
# Model
# ------------------------------------------------------------------

def along_line_at_contact(e) -> float:
    """Feet along the foul line where this ball came down.

    A ball that reached a seat is placed where its trajectory met the deck:
    the first point after the apex at or below the arrival height the engine
    recorded. A ball that reached no seat is placed at its ground landing.
    """
    traj = e.trajectory
    if e.section is None:
        return float(traj.landing_x)
    z = traj.positions[:, 2]
    apex = int(np.argmax(z))
    below = np.nonzero(z[apex:] <= e.landing_height + 1e-6)[0]
    idx = apex + int(below[0]) if len(below) else len(z) - 1
    return float(traj.positions[idx, 0])


def simulate_landings(park_key: str, seed: int, sims: int) -> list[tuple]:
    """Every foul of one standard game: (x_along_line, side, weight, seated)."""
    np.random.seed(seed)
    stadium = STADIUMS[park_key]()
    landings = []
    for lineup in standard_lineups():
        pred = predict_game_fouls(lineup, 'Standard RHP', STANDARD_RHP_MIX,
                                  stadium, simulations_per_batter=sims)
        for e in pred.all_events:
            landings.append((along_line_at_contact(e), e.landing_side,
                             float(e.weight), e.section is not None))
    return landings


def zone_of(x: float, side: str, pole: float, near: float, far: float) -> str:
    if x < near:
        return '1'
    if x < far:
        return '2' if side == '3B' else '3'
    if x < pole:
        return '4' if side == '3B' else '5'
    return '6' if side == '3B' else '7'


def bin_landings(landings, stadium, near: float, far: float) -> dict:
    pole = {'1B': float(stadium.rf_distance), '3B': float(stadium.lf_distance)}
    z7 = {z: 0.0 for z in ZONES}
    total = seated = 0.0
    for x, side, w, matched in landings:
        z7[zone_of(x, side, pole[side], near, far)] += w
        total += w
        seated += w if matched else 0.0
    return {'zone7': z7, 'groups': group_counts(z7), 'total': total,
            'seated': seated}


# ------------------------------------------------------------------
# Scoring
# ------------------------------------------------------------------

def floored(p: dict[str, float]) -> dict[str, float]:
    q = {g: max(p[g], FLOOR) for g in GROUPS}
    s = sum(q.values())
    return {g: q[g] / s for g in GROUPS}


def tvd(p: dict[str, float], o: dict[str, float]) -> float:
    return 0.5 * sum(abs(p[g] - o[g]) for g in GROUPS)


def mean_loglik(counts: dict[str, float], p: dict[str, float]) -> float:
    n = sum(counts.values())
    q = floored(p)
    return sum(counts[g] * math.log(q[g]) for g in GROUPS) / n if n else float('nan')


def chi_square(counts: dict[str, float], p: dict[str, float]) -> tuple[float, float]:
    n = sum(counts.values())
    q = floored(p)
    stat = sum((counts[g] - n * q[g]) ** 2 / (n * q[g]) for g in GROUPS)
    return stat, float(chi2_dist.sf(stat, len(GROUPS) - 1))


def score(counts: dict[str, float], p: dict[str, float]) -> dict:
    o = shares(counts)
    stat, pval = chi_square(counts, p)
    return {'tvd': tvd(p, o), 'loglik': mean_loglik(counts, p),
            'chi2': stat, 'p': pval, 'n': sum(counts.values())}


def leave_one_out(observed: dict, keys: list[str], skip: str, which: str) -> dict[str, float]:
    pooled = {g: 0.0 for g in GROUPS}
    for k in keys:
        if k == skip:
            continue
        for g in GROUPS:
            pooled[g] += observed[k][which][g]
    return shares(pooled)


def pooled_shares(per_park: dict[str, dict[str, float]], weights: dict[str, float]) -> dict[str, float]:
    n = sum(weights.values())
    return {g: sum(weights[k] * per_park[k][g] for k in per_park) / n for g in GROUPS}


def verdict(model_scores: dict[str, dict], base_scores: dict[str, dict],
            model_pooled: dict, base_pooled: dict, keys: list[str]) -> dict:
    """The pre-registered rule: pooled TVD lower, pooled log-lik higher,
    per-park TVD lower at >= 5 of the 8 parks."""
    c1 = bool(model_pooled['tvd'] < base_pooled['tvd'])
    c2 = bool(model_pooled['loglik'] > base_pooled['loglik'])
    wins = int(sum(model_scores[k]['tvd'] < base_scores[k]['tvd'] for k in keys))
    c3 = wins >= 5
    held = int(c1) + int(c2) + int(c3)
    word = 'beats' if held == 3 else ('mixed' if held >= 1 else 'does not beat')
    return {'pooled_tvd_lower': c1, 'pooled_loglik_higher': c2,
            'parks_with_lower_tvd': wins, 'of': len(keys), 'word': word}


def overall_word(b1: str, b3: str) -> str:
    if b1 == 'beats':
        return 'good' if b3 == 'beats' else 'mixed: better than guessing, no better than a constant'
    if b1 == 'mixed':
        return 'mixed'
    return 'bad'


# ------------------------------------------------------------------
# Driver
# ------------------------------------------------------------------

def run(seeds: list[int], sims: int, out_path: str) -> dict:
    observed = load_observed()
    compared = [m for m, _, key, status in PARKS if status == 'compared']

    t0 = time.time()
    landings: dict[int, dict[str, list]] = {}
    for seed in seeds:
        landings[seed] = {}
        for m, venue, key, status in PARKS:
            if key is None:
                continue
            t = time.time()
            landings[seed][m] = simulate_landings(key, seed, sims)
            print(f'  seed {seed} {key:18} {len(landings[seed][m]):5d} fouls '
                  f'{time.time() - t:5.1f}s', flush=True)
    print(f'simulated in {time.time() - t0:.0f}s', flush=True)

    results: dict = {'sims': sims, 'seeds': seeds, 'verdict_seed': seeds[0],
                     'dugout_settings': DUGOUT_SETTINGS, 'floor': FLOOR,
                     'observed': {m: {'all7': observed[m]['all7'],
                                      'cam7': observed[m]['cam7']} for m in observed},
                     'parks': PARKS, 'runs': {}}

    for seed in seeds:
        for near, far in DUGOUT_SETTINGS:
            tag = f'seed{seed}_dug{int(near)}_{int(far)}'
            run_out: dict = {'seed': seed, 'near': near, 'far': far, 'parks': {}}
            model_groups: dict[str, dict] = {}
            for m, venue, key, status in PARKS:
                if key is None:
                    continue
                stadium = STADIUMS[key]()
                b = bin_landings(landings[seed][m], stadium, near, far)
                model_groups[m] = shares(b['groups'])
                run_out['parks'][m] = {
                    'key': key, 'status': status, 'venue': venue,
                    'model_total': b['total'], 'model_seated': b['seated'],
                    'model_zone7_share': shares(b['zone7']),
                    'model_group_share': model_groups[m],
                }
            for which in ('cam', 'all'):
                per = {}
                weights = {m: sum(observed[m][which].values()) for m in compared}
                base3 = {m: leave_one_out(observed, compared, m, which) for m in compared}
                for m in compared + [TEXAS]:
                    counts = observed[m][which]
                    p = model_groups[m]
                    # Texas is scored against the eight compared parks' pooled
                    # shares (it is not one of them), for its own row only.
                    b3 = base3.get(m) or leave_one_out(observed, compared, m, which)
                    per[m] = {
                        'observed_share': shares(counts),
                        'model': score(counts, p),
                        'B1': score(counts, BASELINE_EVEN4),
                        'B2': score(counts, BASELINE_EVEN7),
                        'B3': score(counts, b3),
                        'B3_share': b3,
                    }
                pooled_counts = {g: sum(observed[m][which][g] for m in compared) for g in GROUPS}
                mp = pooled_shares({m: model_groups[m] for m in compared}, weights)
                b3p = pooled_shares(base3, weights)
                pooled = {
                    'counts': pooled_counts, 'observed_share': shares(pooled_counts),
                    'model_share': mp,
                    'model': score(pooled_counts, mp),
                    'B1': score(pooled_counts, BASELINE_EVEN4),
                    'B2': score(pooled_counts, BASELINE_EVEN7),
                    'B3': score(pooled_counts, b3p), 'B3_share': b3p,
                }
                verdicts = {}
                for bname in ('B1', 'B2', 'B3'):
                    verdicts[bname] = verdict(
                        {m: per[m]['model'] for m in compared},
                        {m: per[m][bname] for m in compared},
                        pooled['model'], pooled[bname], compared)
                verdicts['word'] = overall_word(verdicts['B1']['word'], verdicts['B3']['word'])
                run_out[which] = {'per_park': per, 'pooled': pooled, 'verdicts': verdicts}
            results['runs'][tag] = run_out

    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(results, fh, indent=1)
    return results


def pct(x: float) -> str:
    return f'{100 * x:5.1f}'


def four(d: dict[str, float]) -> str:
    return f'{pct(d["Z1"])}/{pct(d["Z23"])}/{pct(d["Z45"])}/{pct(d["Z67"])}'


def report(results: dict) -> str:
    """Plain-text tables for the verdict run and the sensitivity runs."""
    lines = []
    seed = results['verdict_seed']
    for near, far in results['dugout_settings']:
        tag = f'seed{seed}_dug{int(near)}_{int(far)}'
        r = results['runs'][tag]
        lines.append(f'\n===== seed {seed}, dugout {near:.0f}-{far:.0f} ft =====')
        for which, label in (('cam', 'camera-confirmed'), ('all', 'all 906 by used_zone')):
            w = r[which]
            lines.append(f'\n--- {label} ---')
            lines.append(f'{"park":22} {"n":>4}  {"obs Z1/Z23/Z45/Z67":>24}  {"model":>24}  '
                         f'{"TVD m/B1/B2/B3":>26}  {"LL m/B1/B2/B3":>28}  chi2 p')
            for m, info in w['per_park'].items():
                p = r['parks'][m]
                flag = '' if p['status'] == 'compared' else '  [' + p['status'] + ']'
                lines.append(
                    f'{p["key"]:22} {int(info["model"]["n"]):4}  '
                    f'{four(info["observed_share"])}  {four(p["model_group_share"])}  '
                    f'{info["model"]["tvd"]:.3f}/{info["B1"]["tvd"]:.3f}/{info["B2"]["tvd"]:.3f}/{info["B3"]["tvd"]:.3f}  '
                    f'{info["model"]["loglik"]:.3f}/{info["B1"]["loglik"]:.3f}/{info["B2"]["loglik"]:.3f}/{info["B3"]["loglik"]:.3f}  '
                    f'{info["model"]["p"]:.3g}{flag}')
            pl = w['pooled']
            lines.append(
                f'{"POOLED (8 parks)":22} {int(pl["model"]["n"]):4}  '
                f'{four(pl["observed_share"])}  {four(pl["model_share"])}  '
                f'{pl["model"]["tvd"]:.3f}/{pl["B1"]["tvd"]:.3f}/{pl["B2"]["tvd"]:.3f}/{pl["B3"]["tvd"]:.3f}  '
                f'{pl["model"]["loglik"]:.3f}/{pl["B1"]["loglik"]:.3f}/{pl["B2"]["loglik"]:.3f}/{pl["B3"]["loglik"]:.3f}  '
                f'{pl["model"]["p"]:.3g}')
            lines.append(f'  B3 pooled share {four(pl["B3_share"])}')
            v = w['verdicts']
            for b in ('B1', 'B2', 'B3'):
                vb = v[b]
                lines.append(f'  vs {b}: pooled TVD lower={vb["pooled_tvd_lower"]}, '
                             f'pooled LL higher={vb["pooled_loglik_higher"]}, '
                             f'parks with lower TVD={vb["parks_with_lower_tvd"]}/{vb["of"]} -> {vb["word"]}')
            lines.append(f'  WORD: {v["word"]}')
        lines.append('\n  seven-zone model shares (1..7), total fouls and seated share:')
        for m, p in r['parks'].items():
            z = p['model_zone7_share']
            lines.append(f'    {p["key"]:18} ' + ' '.join(pct(z[k]) for k in ZONES) +
                         f'   total {p["model_total"]:.1f}  seated {p["model_seated"] / p["model_total"]:.0%}')

    if len(results['seeds']) > 1:
        lines.append('\n===== seed band at dugout 50-130 (model group shares Z1/Z23/Z45/Z67) =====')
        first = results['runs'][f'seed{seed}_dug50_130']['parks']
        for m in first:
            row = []
            for s in results['seeds']:
                ms = results['runs'][f'seed{s}_dug50_130']['parks'][m]['model_group_share']
                row.append(four(ms))
            lines.append(f'  {first[m]["key"]:18} ' + '  '.join(row))
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--seeds', type=int, nargs='+', default=[SEED],
                    help="first seed is the verdict seed (default: the site's 42)")
    ap.add_argument('--sims', type=int, default=SIMS)
    ap.add_argument('--out', default=os.path.join(HERE, '.cache', 'validation_538.json'))
    ap.add_argument('--report', default=None, help='also write the text tables here')
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    results = run(args.seeds, args.sims, args.out)
    text = report(results)
    if args.report:
        with open(args.report, 'w', encoding='utf-8') as fh:
            fh.write(text)
    print(text)


if __name__ == '__main__':
    main()
