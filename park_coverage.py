"""
Park Coverage — what each park's zone layout can and cannot catch.

Separates geometry from physics. `park_sweep.py` reports how many fouls a park
receives, which mixes the zone layout with that park's altitude and
temperature. This asks a narrower question with no simulation in it at all:
given the partition `exposed_bands()` actually matches against, which parts of
foul territory does a park own, and which parts can a ball land in and match
nothing?

Then it replays ONE shared sample of landing points — the same physics for
every park — through each park's geometry, so differences in capture rate are
attributable to the zones alone.

Usage:
    python park_coverage.py
    python park_coverage.py --parks fenway_park,oakland_coliseum --verbose
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from foulball.stadium import STADIUMS
from park_sweep import (owned_bands, standard_lineups, STANDARD_RHP_MIX,
                        _landing_angle)


def coverage_profile(stadium, side: str, angle_step: float = 1.0,
                     r_max: float = 300.0):
    """Per-angle radial coverage: (angle, first_owned, last_owned, gap_ft).

    `gap_ft` counts unowned distance *between* owned bands only. Space in
    front of the first band is reported separately as `first_owned`, because
    the two are different failures: a gap is a hole in the bowl, while a large
    first_owned means the bowl does not start until far down the line.
    """
    rows = []
    for i in range(int(180.0 / angle_step)):
        angle = (i + 0.5) * angle_step
        bands = sorted(((b0, b1) for _, b0, b1 in owned_bands(stadium, side, angle)))
        if not bands:
            rows.append((angle, None, None, 0.0))
            continue
        gap = 0.0
        cursor = bands[0][1]
        for b0, b1 in bands[1:]:
            if b0 > cursor:
                gap += b0 - cursor
            cursor = max(cursor, b1)
        rows.append((angle, bands[0][0], min(cursor, r_max), gap))
    return rows


def shared_landing_sample(seed: int = 7, sims: int = 400) -> list[tuple]:
    """One landing sample generated once, replayed through every park.

    Uses a mid-league park's air (Citi Field, 54 ft, 75 F) so that altitude and
    temperature are held constant. Returns (side, angle, distance, height,
    horiz_dists, heights, weight) per event.
    """
    from foulball.matchup_engine import predict_game_fouls
    np.random.seed(seed)
    stadium = STADIUMS['citi_field']()
    out = []
    for lineup in standard_lineups():
        pred = predict_game_fouls(lineup, 'Standard RHP', STANDARD_RHP_MIX,
                                  stadium, simulations_per_batter=sims)
        for e in pred.all_events:
            t = e.trajectory
            horiz = np.sqrt(t.positions[:, 0] ** 2 + t.positions[:, 1] ** 2)
            out.append((
                e.landing_side,
                _landing_angle(t.landing_x, t.landing_y),
                e.landing_distance,
                horiz,
                t.positions[:, 2],
                e.weight,
            ))
    return out


def capture_rate(stadium, sample) -> dict:
    """Fraction of a shared landing sample this park's geometry catches."""
    from foulball.stadium import find_landing_section
    by_side = {'1B': [], '3B': [], 'HOME': []}
    for sec in stadium.sections:
        if sec.side in by_side:
            by_side[sec.side].append(sec)

    caught_w = lost_w = total_w = 0.0
    lost = []
    for side, angle, dist, horiz, heights, w in sample:
        cands = by_side.get(side, []) + by_side['HOME']
        sec = find_landing_section(cands, angle, horiz, heights)
        total_w += w
        if sec is None:
            lost_w += w
            lost.append((side, angle, dist, w))
        else:
            caught_w += w
    return {
        'caught': caught_w, 'lost': lost_w, 'total': total_w,
        'capture_pct': caught_w / total_w * 100 if total_w else 0.0,
        'lost_points': lost,
    }


def _envelope(stadium) -> dict:
    """(side, angle bin) -> (first owned distance, last owned distance)."""
    env = {}
    for side in ('1B', '3B'):
        for angle, first, last, _gap in coverage_profile(stadium, side):
            env[(side, int(angle))] = (first, last)
    return env


def classify_losses(stadium, lost_points) -> dict:
    """Why each uncaught ball was uncaught, against that ball's own side.

    Three outcomes, and they are different bugs:
      short  — came down in front of where the bowl starts at that angle
      past   — carried beyond the outermost deck at that angle
      over   — landed within the covered radial span but still matched nothing,
               which can only be a height/trajectory interaction
    """
    counts = {'short': 0, 'past': 0, 'over': 0, 'no_coverage': 0}
    env = _envelope(stadium)

    for side, angle, dist, _w in lost_points:
        first, last = env.get((side, int(angle)), (None, None))
        if first is None:
            counts['no_coverage'] += 1
        elif dist < first:
            counts['short'] += 1
        elif dist > last:
            counts['past'] += 1
        else:
            counts['over'] += 1
    return counts


# A foul pole is 320-350 ft from the plate, and the stands wrap the foul
# territory the whole way. A ball coming down inside this radius is somewhere a
# real park has seats or field; past it, it has left the premises.
PLAUSIBLE_STANDS_FT = 330.0

# How close to the bowl front counts as "the answer depends on where the bowl
# front is." Fenway's front is misplaced by roughly this much (NOTES_STEP7.md),
# so balls inside this band are the ones a geometry correction would flip.
BOWL_FRONT_MARGIN_FT = 15.0


def loss_breakdown(stadium, cap: dict) -> dict:
    """Weighted fouls per game in each loss bucket, with the sub-splits that
    decide what the bucket means.

    `short` is subdivided because not all of it is a defect. A ball that comes
    down well in front of the stands is on the field and the model is right to
    credit it to nobody; a ball that comes down just short of the bowl front is
    only "on the field" if the bowl front is in the right place.

    `past` is subdivided because "carried beyond the last modelled deck" and
    "left the stadium" are different claims. A foul landing 200 ft into foul
    territory is in the seats at every real park — that is missing geometry.
    One landing past a foul pole is a trajectory that went too far.
    """
    env = _envelope(stadium)
    out = {k: 0.0 for k in ('short_field', 'short_marginal', 'past_inside',
                            'past_outside', 'over', 'no_coverage')}
    past_dists = []

    for side, angle, dist, w in cap['lost_points']:
        first, last = env.get((side, int(angle)), (None, None))
        if first is None:
            out['no_coverage'] += w
        elif dist < first:
            if dist < first - BOWL_FRONT_MARGIN_FT:
                out['short_field'] += w
            else:
                out['short_marginal'] += w
        elif dist > last:
            past_dists.append(dist)
            if dist <= PLAUSIBLE_STANDS_FT:
                out['past_inside'] += w
            else:
                out['past_outside'] += w
        else:
            out['over'] += w

    out['short'] = out['short_field'] + out['short_marginal']
    out['past'] = out['past_inside'] + out['past_outside']
    out['caught'] = cap['caught']
    out['total'] = cap['total']
    out['past_median_ft'] = float(np.median(past_dists)) if past_dists else float('nan')
    out['past_p90_ft'] = float(np.percentile(past_dists, 90)) if past_dists else float('nan')
    out['past_max_ft'] = float(max(past_dists)) if past_dists else float('nan')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--parks', default='all')
    ap.add_argument('--sims', type=int, default=400)
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    parks = list(STADIUMS) if args.parks == 'all' else \
        [p.strip() for p in args.parks.split(',')]

    print('Building one shared landing sample (Citi Field air, held constant)...')
    sample = shared_landing_sample(sims=args.sims)
    print('  %d events\n' % len(sample))

    rows = []
    for pk in parks:
        s = STADIUMS[pk]()
        cap = capture_rate(s, sample)

        gaps_1b = coverage_profile(s, '1B')
        gaps_3b = coverage_profile(s, '3B')
        # Where the bowl starts, averaged over the angles that own anything
        starts = [r[1] for r in gaps_1b + gaps_3b if r[1] is not None]
        ends = [r[2] for r in gaps_1b + gaps_3b if r[2] is not None]
        interior_gap = sum(r[3] for r in gaps_1b + gaps_3b)
        blind = sum(1 for r in gaps_1b + gaps_3b if r[1] is None)

        loss = classify_losses(s, cap['lost_points'])
        n_lost = max(sum(loss.values()), 1)

        rows.append({
            'park': pk, 'name': s.name, 'capture_pct': cap['capture_pct'],
            'loss': loss, 'n_lost': n_lost, 'lb': loss_breakdown(s, cap),
            'short_pct': loss['short'] / n_lost * 100,
            'past_pct': loss['past'] / n_lost * 100,
            'over_pct': loss['over'] / n_lost * 100,
            'bowl_front_mean': float(np.mean(starts)) if starts else float('nan'),
            'bowl_front_max': float(np.max(starts)) if starts else float('nan'),
            'bowl_back_mean': float(np.mean(ends)) if ends else float('nan'),
            'interior_gap_ft_deg': interior_gap,
            'blind_rays': blind,
            'n_sections': len(s.sections),
            'levels': len({x.level for x in s.sections}),
        })

        if args.verbose:
            print('=== %s (%s) ===' % (pk, s.name))
            print('  capture %.1f%% | sections %d | levels %d'
                  % (cap['capture_pct'], len(s.sections),
                     len({x.level for x in s.sections})))
            for side, prof in (('1B', gaps_1b), ('3B', gaps_3b)):
                # Collapse consecutive angles with the same coverage signature
                prev, start = None, None
                for angle, f, l, g in prof + [(None, 'END', None, None)]:
                    key = (None if f is None else round(f, 1),
                           None if l is None else round(l, 1), round(g or 0, 1))
                    if key != prev:
                        if prev is not None:
                            fs = 'none' if prev[0] is None else '%.0f-%.0f ft' % (prev[0], prev[1])
                            gs = '' if prev[2] == 0 else '  GAP %.0f ft' % prev[2]
                            print('    %s %3.0f-%3.0f deg: %s%s'
                                  % (side, start, angle if angle else 180, fs, gs))
                        prev, start = key, angle
            print()

    rows.sort(key=lambda r: r['capture_pct'])
    print('%-22s %-22s %7s %9s %8s %7s %6s %6s %6s %5s' % (
        'park', 'name', 'capture', 'bowlfront', 'bowlback', 'gapftd',
        'short%', 'past%', 'over%', 'sect'))
    for r in rows:
        print('%-22s %-22s %6.1f%% %9.1f %8.1f %7.0f %6.0f %6.0f %6.0f %5d' % (
            r['park'], r['name'][:22], r['capture_pct'], r['bowl_front_mean'],
            r['bowl_back_mean'], r['interior_gap_ft_deg'],
            r['short_pct'], r['past_pct'], r['over_pct'], r['n_sections']))
    print('\nshort = came down in front of the bowl; past = carried beyond the '
          'last deck;\nover  = inside the covered span but still matched nothing.')

    # --- Where the unmatched fouls go, in fouls per game ---
    print('\n\n' + '=' * 104)
    print('UNMATCHED FOULS PER GAME, BY CAUSE')
    print('=' * 104)
    print('short = on the field per the park\'s own bowl front (correct to drop)')
    print('  .field    = more than %.0f ft in front of the stands, unambiguously on the field'
          % BOWL_FRONT_MARGIN_FT)
    print('  .marginal = within %.0f ft of the bowl front, so a misplaced front flips it'
          % BOWL_FRONT_MARGIN_FT)
    print('past  = beyond the outermost modelled deck at that angle')
    print('  .inside   = still within %.0f ft of the plate, where a real park has seats'
          % PLAUSIBLE_STANDS_FT)
    print('  .outside  = past %.0f ft, genuinely out of the stadium'
          % PLAUSIBLE_STANDS_FT)
    print()
    print('%-22s %6s %6s | %6s %6s %6s | %6s %6s %6s | %s' % (
        'park', 'fouls', 'caught', 'short', '.field', '.marg', 'past',
        '.insid', '.outsd', 'past dist med/p90/max'))
    for r in sorted(rows, key=lambda x: -x['lb']['past']):
        b = r['lb']
        print('%-22s %6.1f %6.1f | %6.1f %6.1f %6.1f | %6.1f %6.1f %6.1f | %5.0f %5.0f %5.0f'
              % (r['park'], b['total'], b['caught'], b['short'], b['short_field'],
                 b['short_marginal'], b['past'], b['past_inside'], b['past_outside'],
                 b['past_median_ft'], b['past_p90_ft'], b['past_max_ft']))

    agg = {k: sum(r['lb'][k] for r in rows) / len(rows)
           for k in ('total', 'caught', 'short', 'short_field', 'short_marginal',
                     'past', 'past_inside', 'past_outside')}
    print('-' * 104)
    print('%-22s %6.1f %6.1f | %6.1f %6.1f %6.1f | %6.1f %6.1f %6.1f'
          % ('MEAN', agg['total'], agg['caught'], agg['short'], agg['short_field'],
             agg['short_marginal'], agg['past'], agg['past_inside'], agg['past_outside']))
    lost = agg['total'] - agg['caught']
    print('\nof the %.1f unmatched fouls per game at the average park: '
          '%.0f%% short, %.0f%% past.' % (lost, agg['short'] / lost * 100,
                                          agg['past'] / lost * 100))
    print('of the "past" fouls, %.0f%% come down inside %.0f ft — where a real '
          'park has seats.' % (agg['past_inside'] / max(agg['past'], 1e-9) * 100,
                               PLAUSIBLE_STANDS_FT))

    caps = [r['capture_pct'] for r in rows]
    print('\ncapture rate: min %.1f%%  median %.1f%%  max %.1f%%'
          % (min(caps), float(np.median(caps)), max(caps)))


if __name__ == '__main__':
    main()
