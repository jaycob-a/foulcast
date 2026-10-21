#!/usr/bin/env python3
"""
calibrate_back_rate.py — fit BACK_FOUL_BASE_RATE to FiveThirtyEight's fouls,
leave-one-park-out, and score the held-out predictions.

The method is fixed in CALIBRATION_PLAN.md, written and committed before this
script was first run. This file implements that plan and nothing else:

  1. run the site's standard game at each of the eight compared parks at every
     rate on a grid (0.06 to 0.36 by 0.01), binning each simulated foul into
     FiveThirtyEight's zones exactly as validate_538.py does;
  2. for each park, fit the rate on the other seven (multinomial maximum
     likelihood on the four-group counts of the full set) and predict the
     held-out park at that rate;
  3. score the eight held-out predictions against the original model (0.28),
     the even splits and the leave-one-out league average, with the metrics
     and the "beats" rule of VALIDATION_PLAN.md;
  4. fit on all eight parks, which is the value the model would take if the
     held-out results say to change it;
  5. run seeds 1-5 at the original and the fitted rate for the noise band.

Nothing in validate_538.py or the model is edited; the rate is set at run time
in each worker before it simulates.

Usage:
    python calibrate_back_rate.py                       # full grid, 7 workers
    python calibrate_back_rate.py --workers 4
    python calibrate_back_rate.py --out results.json --report tables.txt
"""
import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import foulball.trajectory as trajectory                     # noqa: E402
from foulball.stadium import STADIUMS                        # noqa: E402
import validate_538 as v                                     # noqa: E402
from site_build import SEED, SIMS                            # noqa: E402

ORIGINAL_RATE = 0.28
GRID = [round(0.06 + 0.01 * i, 2) for i in range(31)]        # 0.06 .. 0.36
VERDICT_DUG = '50_130'
BAND_SEEDS = [1, 2, 3, 4, 5]
GROUPS = v.GROUPS


def dug_tag(near: float, far: float) -> str:
    return f'{int(near)}_{int(far)}'


# ------------------------------------------------------------------
# One simulation job (runs in a worker process)
# ------------------------------------------------------------------

def job(rate: float, seed: int, key: str, sims: int) -> tuple:
    """One standard game at one park at one rate, binned at every dugout
    setting. The rate is set on the trajectory module here, in the worker,
    before anything is simulated; back_foul_probability reads it at call time."""
    trajectory.BACK_FOUL_BASE_RATE = rate
    t = time.time()
    landings = v.simulate_landings(key, seed, sims)
    stadium = STADIUMS[key]()
    total = sum(w for _, _, w, _ in landings)
    out = {'total': total,
           'seated': sum(w for _, _, w, m in landings if m) / total,
           'behind_plane': sum(w for x, _, w, _ in landings if x < 0) / total,
           'seconds': time.time() - t}
    for near, far in v.DUGOUT_SETTINGS:
        b = v.bin_landings(landings, stadium, near, far)
        out[dug_tag(near, far)] = {'groups': v.shares(b['groups']),
                                   'zone7': v.shares(b['zone7'])}
    return rate, seed, key, out


def run_jobs(jobs: list[tuple], workers: int, sims: int, label: str) -> dict:
    """{(rate, seed, key): out} for every job, in parallel."""
    t0 = time.time()
    done: dict = {}
    print(f'{label}: {len(jobs)} park-runs on {workers} workers', flush=True)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(job, r, s, k, sims) for r, s, k in jobs]
        for i, f in enumerate(futures, 1):
            rate, seed, key, out = f.result()
            done[(rate, seed, key)] = out
            if i % 8 == 0 or i == len(jobs):
                print(f'  {i:4d}/{len(jobs)}  rate {rate:.2f} seed {seed} '
                      f'{key:18} {time.time() - t0:6.0f}s elapsed', flush=True)
    return done


# ------------------------------------------------------------------
# The fit
# ------------------------------------------------------------------

def pooled_loglik(observed: dict, parks: list[str], model: dict[str, dict], which: str) -> float:
    """(1/N) sum over parks and groups of n * ln q, q floored as validate_538 floors."""
    n_total = 0.0
    ll = 0.0
    for m in parks:
        counts = observed[m][which]
        q = v.floored(model[m])
        for g in GROUPS:
            ll += counts[g] * math.log(q[g])
        n_total += sum(counts.values())
    return ll / n_total


def pooled_tvd(observed: dict, parks: list[str], model: dict[str, dict], which: str) -> float:
    weights = {m: sum(observed[m][which].values()) for m in parks}
    pooled_counts = {g: sum(observed[m][which][g] for m in parks) for g in GROUPS}
    mp = v.pooled_shares({m: model[m] for m in parks}, weights)
    return v.tvd(mp, v.shares(pooled_counts))


def fit(observed: dict, parks: list[str], shares_by_rate: dict[float, dict[str, dict]],
        rates: list[float], which: str = 'all') -> dict:
    """The grid rate maximising the pooled training log-likelihood. Ties go to
    the value nearer ORIGINAL_RATE, then to the lower value. The TVD-minimising
    rate is recorded for information."""
    scores = {r: pooled_loglik(observed, parks, shares_by_rate[r], which) for r in rates}
    tvds = {r: pooled_tvd(observed, parks, shares_by_rate[r], which) for r in rates}
    best_ll = max(scores.values())
    tied = [r for r in rates if abs(scores[r] - best_ll) < 1e-12]
    r_ll = sorted(tied, key=lambda r: (abs(r - ORIGINAL_RATE), r))[0]
    best_tvd = min(tvds.values())
    tied_t = [r for r in rates if abs(tvds[r] - best_tvd) < 1e-12]
    r_tvd = sorted(tied_t, key=lambda r: (abs(r - ORIGINAL_RATE), r))[0]
    return {'rate': r_ll, 'rate_by_tvd': r_tvd,
            'on_grid_edge': r_ll in (min(rates), max(rates)),
            'loglik_by_rate': {f'{r:.2f}': scores[r] for r in rates},
            'tvd_by_rate': {f'{r:.2f}': tvds[r] for r in rates}}


# ------------------------------------------------------------------
# Scoring the held-out predictions
# ------------------------------------------------------------------

def score_set(observed: dict, compared: list[str], which: str,
              candidates: dict[str, dict[str, dict]]) -> dict:
    """Per-park and pooled scores for every candidate (held-out model, M0,
    B1, B2, B3) on one observed set, plus the three-condition verdicts of the
    held-out model against each of the others."""
    weights = {m: sum(observed[m][which].values()) for m in compared}
    base3 = {m: v.leave_one_out(observed, compared, m, which) for m in compared}
    cands = dict(candidates)
    cands['B1'] = {m: v.BASELINE_EVEN4 for m in compared}
    cands['B2'] = {m: v.BASELINE_EVEN7 for m in compared}
    cands['B3'] = base3

    per = {m: {'observed_share': v.shares(observed[m][which]), 'n': weights[m]} for m in compared}
    for name, per_park in cands.items():
        for m in compared:
            per[m][name] = v.score(observed[m][which], per_park[m])
            per[m][name]['share'] = per_park[m]

    pooled_counts = {g: sum(observed[m][which][g] for m in compared) for g in GROUPS}
    pooled = {'counts': pooled_counts, 'observed_share': v.shares(pooled_counts)}
    for name, per_park in cands.items():
        ps = v.pooled_shares(per_park, weights)
        pooled[name] = v.score(pooled_counts, ps)
        pooled[name]['share'] = ps

    verdicts = {}
    for name in cands:
        if name == 'heldout':
            continue
        verdicts[name] = v.verdict({m: per[m]['heldout'] for m in compared},
                                   {m: per[m][name] for m in compared},
                                   pooled['heldout'], pooled[name], compared)
    verdicts['word'] = v.overall_word(verdicts['B1']['word'], verdicts['B3']['word'])
    # The original model's own verdicts, for the side-by-side.
    m0 = {}
    for name in ('B1', 'B2', 'B3'):
        m0[name] = v.verdict({m: per[m]['M0'] for m in compared},
                             {m: per[m][name] for m in compared},
                             pooled['M0'], pooled[name], compared)
    m0['word'] = v.overall_word(m0['B1']['word'], m0['B3']['word'])
    return {'per_park': per, 'pooled': pooled, 'verdicts': verdicts, 'M0_verdicts': m0}


# ------------------------------------------------------------------
# Driver
# ------------------------------------------------------------------

def run(rates: list[float], seed: int, sims: int, workers: int, band_seeds: list[int],
        out_path: str) -> dict:
    observed = v.load_observed()
    compared = [m for m, _, key, status in v.PARKS if status == 'compared']
    key_of = {m: key for m, _, key, status in v.PARKS if status == 'compared'}

    # ---- 1. the grid ----
    grid_runs = run_jobs([(r, seed, key_of[m]) for r in rates for m in compared],
                         workers, sims, 'grid')
    seconds = sum(o['seconds'] for o in grid_runs.values())

    def shares_at(rate: float, s: int, dug: str) -> dict[str, dict]:
        return {m: grid_runs[(rate, s, key_of[m])][dug]['groups'] for m in compared}

    by_rate = {r: shares_at(r, seed, VERDICT_DUG) for r in rates}

    # Does the 0.28 run reproduce VALIDATION.md?
    repro = None
    prev_path = os.path.join(HERE, '.cache', 'validation_538.json')
    if ORIGINAL_RATE in rates and os.path.exists(prev_path):
        with open(prev_path, encoding='utf-8') as fh:
            prev = json.load(fh)['runs'][f'seed{seed}_dug50_130']['parks']
        repro = max(abs(prev[m]['model_group_share'][g] - by_rate[ORIGINAL_RATE][m][g])
                    for m in compared for g in GROUPS)

    # ---- 2. leave-one-park-out fits ----
    loo = {}
    for h in compared:
        others = [m for m in compared if m != h]
        f = fit(observed, others, by_rate, rates)
        loo[h] = {'key': key_of[h], 'rate': f['rate'], 'rate_by_tvd': f['rate_by_tvd'],
                  'on_grid_edge': f['on_grid_edge'],
                  'training_loglik_by_rate': f['loglik_by_rate']}

    # ---- 4. all-eight fit ----
    all8 = fit(observed, compared, by_rate, rates)

    # ---- 3. score the held-out predictions, every dugout setting, both sets ----
    scored = {}
    for near, far in v.DUGOUT_SETTINGS:
        dug = dug_tag(near, far)
        heldout = {h: grid_runs[(loo[h]['rate'], seed, key_of[h])][dug]['groups'] for h in compared}
        m0 = shares_at(ORIGINAL_RATE, seed, dug)
        insample = shares_at(all8['rate'], seed, dug)
        scored[dug] = {'near': near, 'far': far}
        for which in ('all', 'cam'):
            scored[dug][which] = score_set(observed, compared, which,
                                           {'heldout': heldout, 'M0': m0})
            # In-sample figures at the all-eight rate, for the record only.
            w = {m: sum(observed[m][which].values()) for m in compared}
            pc = {g: sum(observed[m][which][g] for m in compared) for g in GROUPS}
            ps = v.pooled_shares(insample, w)
            scored[dug][which]['insample_all8'] = {
                'pooled': v.score(pc, ps), 'pooled_share': ps,
                'per_park_tvd': {m: v.tvd(insample[m], v.shares(observed[m][which])) for m in compared}}

    # ---- residuals and diagnostics at the fitted and original rates ----
    def diagnostics(rate: float) -> dict:
        w = {m: sum(observed[m]['all'].values()) for m in compared}
        pc = {g: sum(observed[m]['all'][g] for m in compared) for g in GROUPS}
        obs = v.shares(pc)
        ps = v.pooled_shares(shares_at(rate, seed, VERDICT_DUG), w)
        # zone7 pooled by hand (pooled_shares is written for the four groups)
        n = sum(w.values())
        z7 = {z: sum(w[m] * grid_runs[(rate, seed, key_of[m])][VERDICT_DUG]['zone7'][z]
                     for m in compared) / n for z in v.ZONES}
        runs = [grid_runs[(rate, seed, key_of[m])] for m in compared]
        return {
            'rate': rate,
            'pooled_model_share': ps, 'pooled_observed_share': obs,
            'residual_model_minus_observed': {g: ps[g] - obs[g] for g in GROUPS},
            'pooled_zone7_share': z7,
            'forward_bands_ratio_Z23_over_Z45': {'model': ps['Z23'] / ps['Z45'],
                                                 'observed': obs['Z23'] / obs['Z45']},
            'behind_plane_share': {'min': min(r['behind_plane'] for r in runs),
                                   'max': max(r['behind_plane'] for r in runs)},
            'seated_share': {'min': min(r['seated'] for r in runs),
                             'max': max(r['seated'] for r in runs)},
            'fouls_per_game': {'min': min(r['total'] for r in runs),
                               'max': max(r['total'] for r in runs)},
            'per_park_Z1': {key_of[m]: by_rate[rate][m]['Z1'] for m in compared},
        }

    diag = {'original': diagnostics(ORIGINAL_RATE), 'fitted_all8': diagnostics(all8['rate'])}

    # ---- the decision, by the rule in CALIBRATION_PLAN.md ----
    vs_m0 = scored[VERDICT_DUG]['all']['verdicts']['M0']
    decision = {
        'heldout_vs_original_full_set': vs_m0['word'],
        'change_rate': vs_m0['word'] == 'beats',
        'new_rate_if_changed': all8['rate'],
        'any_fit_on_grid_edge': all8['on_grid_edge'] or any(l['on_grid_edge'] for l in loo.values()),
    }

    # ---- 5. seed band at the original and the all-eight rate ----
    band = {}
    if band_seeds:
        band_rates = sorted({ORIGINAL_RATE, all8['rate']})
        band_runs = run_jobs([(r, s, key_of[m]) for r in band_rates for s in band_seeds for m in compared],
                             workers, sims, 'seed band')
        band_runs.update({k: o for k, o in grid_runs.items() if k[0] in band_rates})
        for r in band_rates:
            band[f'{r:.2f}'] = {}
            for s in [seed] + list(band_seeds):
                sh = {m: band_runs[(r, s, key_of[m])][VERDICT_DUG]['groups'] for m in compared}
                entry = {}
                for which in ('all', 'cam'):
                    w = {m: sum(observed[m][which].values()) for m in compared}
                    pc = {g: sum(observed[m][which][g] for m in compared) for g in GROUPS}
                    ps = v.pooled_shares(sh, w)
                    entry[which] = {'pooled_share': ps, 'tvd': v.tvd(ps, v.shares(pc)),
                                    'loglik': v.mean_loglik(pc, ps)}
                band[f'{r:.2f}'][str(s)] = entry

    results = {
        'plan': 'CALIBRATION_PLAN.md', 'sims': sims, 'seed': seed, 'rates': rates,
        'original_rate': ORIGINAL_RATE, 'verdict_dugout': VERDICT_DUG,
        'reproduces_validation_538_max_abs_diff': repro,
        'grid_cpu_seconds': seconds,
        'grid': {f'{r:.2f}': {key_of[m]: grid_runs[(r, seed, key_of[m])] for m in compared} for r in rates},
        'loo': loo, 'all8': all8, 'scored': scored, 'diagnostics': diag,
        'decision': decision, 'seed_band': band,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(results, fh, indent=1)
    return results


# ------------------------------------------------------------------
# Report
# ------------------------------------------------------------------

def pct(x: float) -> str:
    return f'{100 * x:5.1f}'


def four(d: dict[str, float]) -> str:
    return '/'.join(pct(d[g]) for g in GROUPS)


def report(res: dict) -> str:
    L = []
    L.append(f'calibrate_back_rate: grid {res["rates"][0]:.2f}..{res["rates"][-1]:.2f}, '
             f'seed {res["seed"]}, {res["sims"]} sims, '
             f'{res["grid_cpu_seconds"] / 60:.0f} cpu-minutes of simulation')
    if res['reproduces_validation_538_max_abs_diff'] is not None:
        L.append(f'0.28 run vs VALIDATION.md shares: max abs diff '
                 f'{res["reproduces_validation_538_max_abs_diff"]:.2e}')

    L.append('\n===== leave-one-park-out fitted rates (fit on the other seven, full set) =====')
    for h, l in res['loo'].items():
        L.append(f'  held out {l["key"]:18} rate {l["rate"]:.2f}  (by TVD {l["rate_by_tvd"]:.2f})'
                 + ('  [GRID EDGE]' if l['on_grid_edge'] else ''))
    a = res['all8']
    L.append(f'  all eight parks        rate {a["rate"]:.2f}  (by TVD {a["rate_by_tvd"]:.2f})'
             + ('  [GRID EDGE]' if a['on_grid_edge'] else ''))
    L.append('\n  training log-likelihood by rate (all eight parks):')
    for r in res['rates']:
        k = f'{r:.2f}'
        L.append(f'    {k}  LL {a["loglik_by_rate"][k]:.4f}  TVD {a["tvd_by_rate"][k]:.3f}')

    for dug, sc in res['scored'].items():
        L.append(f'\n===== dugout {sc["near"]:.0f}-{sc["far"]:.0f} ft =====')
        for which, label in (('all', 'all fouls by used_zone'), ('cam', 'camera-confirmed')):
            w = sc[which]
            L.append(f'\n--- {label} ---')
            L.append(f'{"park":18} {"n":>4}  {"observed":>23}  {"held-out":>23}  '
                     f'{"original":>23}  TVD held/M0/B1/B2/B3        LL held/M0/B3')
            for m, info in w['per_park'].items():
                key = res['loo'][m]['key']
                L.append(
                    f'{key:18} {int(info["n"]):4}  {four(info["observed_share"])}  '
                    f'{four(info["heldout"]["share"])}  {four(info["M0"]["share"])}  '
                    f'{info["heldout"]["tvd"]:.3f}/{info["M0"]["tvd"]:.3f}/{info["B1"]["tvd"]:.3f}/'
                    f'{info["B2"]["tvd"]:.3f}/{info["B3"]["tvd"]:.3f}  '
                    f'{info["heldout"]["loglik"]:.3f}/{info["M0"]["loglik"]:.3f}/{info["B3"]["loglik"]:.3f}')
            p = w['pooled']
            L.append(f'{"POOLED":18} {int(p["heldout"]["n"]):4}  {four(p["observed_share"])}  '
                     f'{four(p["heldout"]["share"])}  {four(p["M0"]["share"])}  '
                     f'{p["heldout"]["tvd"]:.3f}/{p["M0"]["tvd"]:.3f}/{p["B1"]["tvd"]:.3f}/'
                     f'{p["B2"]["tvd"]:.3f}/{p["B3"]["tvd"]:.3f}  '
                     f'{p["heldout"]["loglik"]:.3f}/{p["M0"]["loglik"]:.3f}/{p["B3"]["loglik"]:.3f}')
            L.append(f'  pooled chi2 p: held-out {p["heldout"]["p"]:.3g}, original {p["M0"]["p"]:.3g}')
            for name in ('M0', 'B1', 'B2', 'B3'):
                vb = w['verdicts'][name]
                L.append(f'  held-out vs {name}: pooled TVD lower={vb["pooled_tvd_lower"]}, '
                         f'pooled LL higher={vb["pooled_loglik_higher"]}, '
                         f'parks with lower TVD={vb["parks_with_lower_tvd"]}/{vb["of"]} -> {vb["word"]}')
            L.append(f'  held-out WORD: {w["verdicts"]["word"]}   (original model: {w["M0_verdicts"]["word"]})')
            ins = w['insample_all8']
            L.append(f'  in-sample at all-eight rate {a["rate"]:.2f}: pooled share {four(ins["pooled_share"])}, '
                     f'TVD {ins["pooled"]["tvd"]:.3f}, LL {ins["pooled"]["loglik"]:.3f}')

    L.append('\n===== diagnostics (dugout 50-130, full set, pooled over eight parks) =====')
    for name, d in res['diagnostics'].items():
        L.append(f'\n  {name} (rate {d["rate"]:.2f})')
        L.append(f'    model    {four(d["pooled_model_share"])}')
        L.append(f'    observed {four(d["pooled_observed_share"])}')
        L.append(f'    residual ' + '/'.join(f'{100 * d["residual_model_minus_observed"][g]:+5.1f}' for g in GROUPS))
        L.append(f'    zone 1..7 ' + ' '.join(pct(d["pooled_zone7_share"][z]) for z in v.ZONES))
        r = d['forward_bands_ratio_Z23_over_Z45']
        L.append(f'    dugout strip / dugout-to-pole: model {r["model"]:.3f}, observed {r["observed"]:.3f}')
        L.append(f'    behind the plane of the plate {pct(d["behind_plane_share"]["min"])}-'
                 f'{pct(d["behind_plane_share"]["max"])}%, reaching a seat '
                 f'{pct(d["seated_share"]["min"])}-{pct(d["seated_share"]["max"])}%, '
                 f'fouls per game {d["fouls_per_game"]["min"]:.1f}-{d["fouls_per_game"]["max"]:.1f}')
        L.append('    behind-plate share by park: ' +
                 ', '.join(f'{k} {pct(x)}' for k, x in d['per_park_Z1'].items()))

    if res['seed_band']:
        L.append('\n===== seed band (dugout 50-130): pooled share, TVD and LL vs full set; TVD vs camera set =====')
        for r, seeds in res['seed_band'].items():
            L.append(f'  rate {r}')
            for s, e in seeds.items():
                L.append(f'    seed {s:>2}  {four(e["all"]["pooled_share"])}  '
                         f'TVD {e["all"]["tvd"]:.3f}  LL {e["all"]["loglik"]:.3f}  cam TVD {e["cam"]["tvd"]:.3f}')

    d = res['decision']
    L.append(f'\n===== decision (CALIBRATION_PLAN.md): held-out vs original on the full set = '
             f'"{d["heldout_vs_original_full_set"]}" -> '
             f'{"CHANGE the rate to " + format(d["new_rate_if_changed"], ".2f") if d["change_rate"] else "LEAVE the model unchanged"}'
             + ('   [a fit sat on the grid edge: extend the grid]' if d['any_fit_on_grid_edge'] else ''))
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--rates', type=float, nargs='+', default=GRID)
    ap.add_argument('--seed', type=int, default=SEED)
    ap.add_argument('--sims', type=int, default=SIMS)
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument('--band-seeds', type=int, nargs='*', default=BAND_SEEDS,
                    help='extra seeds for the noise band; pass none to skip')
    ap.add_argument('--out', default=os.path.join(HERE, '.cache', 'calibration_back_rate.json'))
    ap.add_argument('--report', default=None, help='also write the text tables here')
    args = ap.parse_args()
    rates = sorted(round(r, 2) for r in args.rates)
    results = run(rates, args.seed, args.sims, args.workers, args.band_seeds, args.out)
    text = report(results)
    if args.report:
        with open(args.report, 'w', encoding='utf-8') as fh:
            fh.write(text)
    print(text)


if __name__ == '__main__':
    main()
