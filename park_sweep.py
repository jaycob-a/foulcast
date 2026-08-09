"""
Park Sweep — run one standard lineup through every park and map where the
fouls land.

This is a debugging instrument, not a product surface. It exists to answer a
geometry question the backtest cannot: whether each park's zone layout turns a
physically smooth landing distribution into a sensible per-zone prediction, or
whether the zones themselves are inventing structure.

Three outputs:

  1. Per-park zone totals and a plan-view heat map (park_heatmaps.html).
  2. Implausibility flags — hard edges, unexplained left/right asymmetry, dead
     zones, and outlier totals — computed numerically rather than eyeballed.
  3. A handedness experiment: the same park run with an all-RHB and an all-LHB
     lineup, to size how much the 1B/3B split actually moves.

The lineup is held identical across parks so that park geometry is the only
variable. "One game" is both lineups summed, the way webapp_v2 sums them;
a single predict_game_fouls() call is half a game.

Usage:
    python park_sweep.py                    # everything, writes to .cache/park_sweep/
    python park_sweep.py --parks fenway_park,oakland_coliseum
    python park_sweep.py --sims 200         # faster, noisier
    python park_sweep.py --seeds 3          # noise band for the flags
"""
import argparse
import json
import math
import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from foulball.batter_profiles import YANKEES_2024_PROFILES, RED_SOX_2024_PROFILES
from foulball.matchup_engine import predict_game_fouls
from foulball.stadium import STADIUMS, exposed_bands

# Matches the configuration BEFORE.md and tests/test_plausibility.py use, so
# numbers here are comparable with the Step 3 park sweep.
STANDARD_RHP_MIX = {'FF': 0.30, 'SL': 0.20, 'CH': 0.15, 'SI': 0.15, 'CU': 0.10, 'FC': 0.10}

# Dead behind the catcher, in the engine's angle convention: 0 = down the foul
# line, 90 = square to the plate. Mirrors trajectory.BEHIND_PLATE_ANGLE.
BEHIND_PLATE_ANGLE = 135.0

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache', 'park_sweep')


def standard_lineups():
    """The two lineups that make up one standard game, in a fixed order."""
    return [list(RED_SOX_2024_PROFILES.values()), list(YANKEES_2024_PROFILES.values())]


def handed_lineups(side: str):
    """The same 18 batters with handedness forced to `side`.

    Everything else — exit velocity, launch angle, per-pitch foul rates,
    fouls_per_pa, pull tendency — is left untouched, so the only thing that
    changes between the R and L runs is the direction model. fair_pull_pct is
    defined relative to the batter's own pull side, so it stays meaningful
    under the flip rather than needing to be mirrored too.
    """
    return [[replace(p, batter_side=side) for p in lineup]
            for lineup in standard_lineups()]


# ============================================================
# Running a park
# ============================================================

def _landing_angle(landing_x: float, landing_y: float) -> float:
    """Reproduce matchup_engine's angle convention from a landing point."""
    ly = abs(landing_y)
    if landing_x >= 0:
        return float(np.degrees(np.arctan2(ly, landing_x)))
    return float(90.0 + np.degrees(np.arctan2(-landing_x, max(ly, 0.01))))


def run_park(park_key: str, lineups, seed: int = 42, sims: int = 400) -> dict:
    """Simulate one full game at a park. Returns zone totals plus raw landings.

    Both lineups are summed: a single predict_game_fouls() call covers one
    team's plate appearances and is half a game.
    """
    np.random.seed(seed)
    stadium = STADIUMS[park_key]()

    zone_fouls: dict[str, float] = {}
    side_weight = {'1B': 0.0, '3B': 0.0, 'HOME': 0.0}
    landings = []          # (side, angle, distance, weight, matched)
    total_weight = 0.0     # every foul the lineup produces, matched or not
    matched_weight = 0.0

    for lineup in lineups:
        pred = predict_game_fouls(lineup, 'Standard RHP', STANDARD_RHP_MIX,
                                  stadium, simulations_per_batter=sims)
        for e in pred.all_events:
            angle = _landing_angle(e.trajectory.landing_x, e.trajectory.landing_y)
            matched = e.section is not None
            landings.append((e.landing_side, angle, e.landing_distance,
                             e.weight, matched))
            total_weight += e.weight
            if matched:
                matched_weight += e.weight
                sid = e.section.section_id
                zone_fouls[sid] = zone_fouls.get(sid, 0.0) + e.weight
                side_weight[e.section.side] += e.weight

    # Zones that exist in the geometry but were never reached.
    for sec in stadium.sections:
        zone_fouls.setdefault(sec.section_id, 0.0)

    sided = side_weight['1B'] + side_weight['3B']

    return {
        'park': park_key,
        'stadium_name': stadium.name,
        'seed': seed,
        'sims': sims,
        'zone_fouls': zone_fouls,
        'side_weight': side_weight,
        # Behind-plate zones are shared between the two sides, so the split is
        # taken over sided fouls only.
        'pct_1b_of_sided': side_weight['1B'] / sided * 100 if sided else float('nan'),
        'total_into_stands': matched_weight,
        'total_fouls': total_weight,
        'unmatched': total_weight - matched_weight,
        'landings': landings,
        'stadium': stadium,
    }


# ============================================================
# Geometry introspection
# ============================================================

def owned_bands(stadium, side: str, angle: float):
    """Distance bands owned by each section at one angle, for one side.

    Mirrors what matchup_engine actually searches: same-side sections plus the
    shared behind-plate group. Drawing raw section rectangles instead would
    misrepresent the engine, because exposed_bands() resolves the heavy
    overlap in the raw data before anything is matched.
    """
    candidates = [s for s in stadium.sections if s.side in (side, 'HOME')]
    return exposed_bands(candidates, angle)


def zone_owned_area(stadium, side: str, angle_step: float = 1.0,
                    angle_max: float = 180.0) -> dict[str, float]:
    """Ground area in square feet each section actually owns on one side.

    Integrated over the same partition the engine matches against, so a
    section whose raw rectangle is mostly hidden under a lower deck is
    credited only with the sliver it really owns.
    """
    areas: dict[str, float] = {}
    dtheta = math.radians(angle_step)
    for i in range(int(angle_max / angle_step)):
        angle = (i + 0.5) * angle_step
        for sec, r0, r1 in owned_bands(stadium, side, angle):
            # Area of an annular sector: (r1^2 - r0^2) * dtheta / 2
            areas[sec.section_id] = areas.get(sec.section_id, 0.0) + \
                0.5 * (r1 * r1 - r0 * r0) * dtheta
    return areas


def geometry_mirror_delta(stadium) -> dict:
    """How far a park's 1B-side geometry is from being a mirror of its 3B side.

    Sections are paired by section_id with the side prefix stripped, which is
    the convention every park in stadium.py follows. Returns the count of
    unpaired sections and the largest per-parameter difference across pairs,
    so a left/right split in the results can be attributed to the park rather
    than to the lineup.
    """
    def strip(sid):
        for prefix in ('1B-', '3B-'):
            if sid.startswith(prefix):
                return sid[len(prefix):]
        return None

    left = {strip(s.section_id): s for s in stadium.sections if s.side == '3B'}
    right = {strip(s.section_id): s for s in stadium.sections if s.side == '1B'}
    unpaired = sorted((set(left) | set(right)) - (set(left) & set(right)))

    worst = 0.0
    worst_field = None
    for key in set(left) & set(right):
        a, b = left[key], right[key]
        for fld in ('distance_min', 'distance_max', 'angle_min', 'angle_max',
                    'height_min', 'height_max'):
            va, vb = getattr(a, fld), getattr(b, fld)
            if np.isnan(va) or np.isnan(vb):
                continue
            if abs(va - vb) > worst:
                worst = abs(va - vb)
                worst_field = f'{key}.{fld}'

    return {
        'symmetric': not unpaired and worst < 1e-9,
        'unpaired': unpaired,
        'max_param_delta': round(worst, 2),
        'max_param_field': worst_field,
    }


def coverage_gaps(stadium, side: str, r_max: float = 260.0,
                  angle_step: float = 2.0, r_step: float = 4.0) -> list[tuple]:
    """(angle, r0, r1) wedges inside the bowl footprint that no section owns.

    Only gaps *between* owned bands and out to the deepest owned band are
    counted. Space in front of the bowl and beyond the last deck is not a gap
    — there are genuinely no seats there.
    """
    gaps = []
    for i in range(int(180.0 / angle_step)):
        angle = (i + 0.5) * angle_step
        bands = owned_bands(stadium, side, angle)
        if not bands:
            continue
        spans = sorted((b0, b1) for _, b0, b1 in bands)
        outer = min(max(b1 for _, b1 in spans), r_max)
        cursor = spans[0][0]
        for b0, b1 in spans:
            if b0 - cursor > r_step:
                gaps.append((angle, cursor, min(b0, outer)))
            cursor = max(cursor, b1)
            if cursor >= outer:
                break
    return gaps


# ============================================================
# Implausibility flags
# ============================================================

def hard_edge_report(result, side_key: str = 'both') -> list[dict]:
    """Adjacent zones whose per-square-foot foul density jumps by a big factor.

    A physically smooth landing field over sensible zones produces a density
    that varies gradually from zone to zone. A large jump across a shared
    boundary means the boundary itself, not the physics, is deciding the
    answer — which is exactly the "hard edge" an eye picks out of the map.

    Zones that own almost no area are excluded: a 40-square-foot sliver has a
    meaningless density and would dominate every ratio.
    """
    stadium = result['stadium']
    zone_fouls = result['zone_fouls']
    MIN_AREA = 500.0     # sq ft; below this the density is noise
    MIN_FOULS = 0.05     # ignore zones the model barely uses

    edges = []
    for side in ('1B', '3B'):
        areas = zone_owned_area(stadium, side)
        density = {}
        for sid, area in areas.items():
            if area >= MIN_AREA:
                density[sid] = zone_fouls.get(sid, 0.0) / area

        # Neighbours are zones that share a band boundary at some angle.
        neighbours = set()
        for i in range(180):
            bands = owned_bands(stadium, side, i + 0.5)
            ordered = sorted(bands, key=lambda b: b[1])
            for (a, _, a1), (b, b0, _) in zip(ordered, ordered[1:]):
                if abs(a1 - b0) < 1e-6 and a.section_id != b.section_id:
                    neighbours.add(tuple(sorted((a.section_id, b.section_id))))

        for x, y in neighbours:
            if x not in density or y not in density:
                continue
            hi, lo = max(density[x], density[y]), min(density[x], density[y])
            if zone_fouls.get(x, 0) < MIN_FOULS and zone_fouls.get(y, 0) < MIN_FOULS:
                continue
            ratio = hi / lo if lo > 1e-12 else float('inf')
            edges.append({
                'side': side, 'zones': [x, y],
                'density_ratio': round(ratio, 1) if ratio != float('inf') else None,
                'fouls': [round(zone_fouls.get(x, 0), 2), round(zone_fouls.get(y, 0), 2)],
            })

    edges.sort(key=lambda e: (e['density_ratio'] is None, -(e['density_ratio'] or 0)))
    return edges


def section_convention_audit(parks: list[str], min_share: float = 0.8) -> list[str]:
    """Section IDs whose geometry breaks the convention the other parks follow.

    Every park uses the same section_id vocabulary, so a given ID should mean
    roughly the same place at every park. Where an overwhelming majority agree
    on an angular range and one park does not, that park's entry is far more
    likely to be a data-entry slip than a real architectural quirk — and it
    will quietly move that park's numbers without ever looking wrong on its
    own map.
    """
    from collections import defaultdict, Counter
    ranges: dict[str, Counter] = defaultdict(Counter)
    where: dict[tuple, list[str]] = defaultdict(list)
    for pk in parks:
        for s in STADIUMS[pk]().sections:
            key = (s.angle_min, s.angle_max)
            ranges[s.section_id][key] += 1
            where[(s.section_id, key)].append(pk)

    msgs = []
    for sid, counter in sorted(ranges.items()):
        total = sum(counter.values())
        if total < 5:
            continue
        (common, n), = counter.most_common(1)
        if n / total < min_share:
            continue
        for key, cnt in counter.items():
            if key == common:
                continue
            msgs.append(
                f"SECTION CONVENTION: {sid} is angle {key[0]:.0f}-{key[1]:.0f} at "
                f"{', '.join(where[(sid, key)])} but {common[0]:.0f}-{common[1]:.0f} "
                f"at {n}/{total} parks"
            )
    return msgs


def flag_park(result, all_totals: list[float], split_noise_pp: float,
              all_lost_pct: list[float], all_pct_1b: list[float]) -> list[str]:
    """Physical-implausibility flags for one park. Empty list means it looks fine."""
    flags = []
    stadium = result['stadium']
    zone_fouls = result['zone_fouls']
    total = result['total_into_stands']

    # --- Outlier total ---
    med = float(np.median(all_totals))
    mad = float(np.median([abs(t - med) for t in all_totals])) or 1e-9
    z = 0.6745 * (total - med) / mad
    if abs(z) >= 3.5:
        flags.append(
            f"OUTLIER TOTAL: {total:.1f} fouls into stands vs a 30-park median "
            f"of {med:.1f} (robust z = {z:+.1f})"
        )

    # --- Dead zones ---
    dead = sorted(sid for sid, f in zone_fouls.items() if f <= 0.0)
    if dead:
        flags.append(f"DEAD ZONES: {len(dead)} section(s) received nothing: {dead}")
    near_dead = sorted(sid for sid, f in zone_fouls.items() if 0.0 < f < 0.05)
    if near_dead:
        flags.append(f"NEAR-DEAD ZONES: {near_dead} (<0.05 fouls per game)")

    # --- Fouls that landed nowhere ---
    # Judged against the fleet, not an absolute bar. Every park loses about a
    # third of its fouls (see NOTES_STEP7.md); an absolute threshold flags all
    # 31 and so discriminates nothing. What is a park-level finding is losing
    # materially more than everyone else.
    lost_pct = result['unmatched'] / max(result['total_fouls'], 1e-9) * 100
    fleet_lost = np.median(all_lost_pct)
    if lost_pct - fleet_lost > 5.0:
        flags.append(
            f"UNMATCHED: {lost_pct:.0f}% of the lineup's fouls "
            f"({result['unmatched']:.1f} per game) matched no section, against "
            f"a fleet median of {fleet_lost:.0f}%"
        )

    # --- Left/right asymmetry the lineup does not explain ---
    #
    # The reference is the fleet median, not 50/50. The same 18 batters play
    # every park, so whatever lean the lineup itself produces is common to all
    # 31 rows and the median absorbs it exactly — no assumption about the
    # model's pull rate required. 50/50 would be the wrong bar: this lineup is
    # 9 R and 9 L but the left-handers foul more (fouls_per_pa sums to 7.09
    # against 6.64), which alone predicts a lean toward 1B.
    w1b, w3b = result['side_weight']['1B'], result['side_weight']['3B']
    if w1b + w3b > 0:
        pct_1b = w1b / (w1b + w3b) * 100
        mirror = geometry_mirror_delta(stadium)
        result['pct_1b_of_sided'] = pct_1b
        result['mirror'] = mirror
        baseline = float(np.median(all_pct_1b)) if all_pct_1b else 50.0
        if abs(pct_1b - baseline) > max(3.0 * split_noise_pp, 2.0):
            if mirror['symmetric']:
                flags.append(
                    f"UNEXPLAINED ASYMMETRY: {pct_1b:.1f}% of sided fouls to 1B "
                    f"against a fleet median of {baseline:.1f}% for this same "
                    f"lineup, with mirror-symmetric geometry "
                    f"(sampling band +/-{split_noise_pp:.1f} pp)"
                )
            else:
                flags.append(
                    f"ASYMMETRY (park geometry is not mirrored): {pct_1b:.1f}% to 1B "
                    f"against a fleet median of {baseline:.1f}%; largest 1B/3B "
                    f"geometry difference {mirror['max_param_delta']} "
                    f"at {mirror['max_param_field']}, unpaired {mirror['unpaired']}"
                )

    # --- Hard edges ---
    edges = hard_edge_report(result)
    harsh = [e for e in edges if e['density_ratio'] is None or e['density_ratio'] >= 20]
    if harsh:
        worst = harsh[0]
        flags.append(
            f"HARD EDGE: {worst['zones'][0]} / {worst['zones'][1]} "
            f"({worst['side']}) differ by {worst['density_ratio']}x in fouls per "
            f"square foot across a shared boundary "
            f"({worst['fouls'][0]} vs {worst['fouls'][1]} fouls); "
            f"{len(harsh)} such boundary/boundaries in this park"
        )

    # --- Geometry gaps balls can fall into ---
    for side in ('1B', '3B'):
        gaps = coverage_gaps(stadium, side)
        if gaps:
            widest = max(gaps, key=lambda g: g[2] - g[1])
            flags.append(
                f"GEOMETRY GAP ({side}): {len(gaps)} sampled ray(s) have an "
                f"unowned band inside the bowl; widest {widest[2]-widest[1]:.0f} ft "
                f"at {widest[0]:.0f} deg ({widest[1]:.0f}-{widest[2]:.0f} ft)"
            )

    return flags


# ============================================================
# Plan-view heat map
# ============================================================
#
# The engine works in a per-side frame: angle 0 is down *that side's* foul
# line, 90 is square to the plate, 135 is dead behind the catcher. To draw a
# recognisable park, that frame is unrolled onto a real plan view by treating
# the angle as a bearing measured away from fair territory:
#
#     1B side:  theta =  (45 + angle)      3B side:  theta = -(45 + angle)
#
# with theta measured from the centre-field axis. angle=0 lands on the foul
# line, angle=135 lands at theta=180, dead behind the plate — which is the
# convention the two sides are mirrored across, so the backstop closes up
# correctly instead of overlapping itself.

R_MAX = 280.0
_PAD = 24.0
_W = 2 * R_MAX + 2 * _PAD
_H = R_MAX * (1 + math.cos(math.radians(45))) + 2 * _PAD
_CX = _W / 2
_CY = R_MAX * math.cos(math.radians(45)) + _PAD


def _xy(side: str, angle: float, r: float) -> tuple[float, float]:
    theta = math.radians((45.0 + angle) * (1 if side == '1B' else -1))
    return _CX + r * math.sin(theta), _CY - r * math.cos(theta)


def _ramp(t: float) -> str:
    """Pale-to-dark sequential ramp. t in [0, 1]. Unstyled on purpose."""
    t = max(0.0, min(1.0, t))
    stops = [(0.00, (247, 251, 255)), (0.25, (198, 219, 239)),
             (0.50, (107, 174, 214)), (0.75, (33, 113, 181)),
             (1.00, (8, 48, 107))]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return '#%02x%02x%02x' % tuple(int(a + f * (b - a)) for a, b in zip(c0, c1))
    return '#08306b'


def _merged_bands(stadium, side: str, step: float = 3.0):
    """Angle ranges over which the band structure is identical.

    Section angle ranges are coarse, so the partition is piecewise constant
    over wide wedges. Merging them keeps the SVG to a few dozen shapes per
    park instead of a few hundred, without changing what is drawn.
    """
    runs = []
    prev_key, start = None, 0.0
    n = int(180.0 / step)
    for i in range(n + 1):
        angle = i * step
        if i == n:
            key, bands = None, []
        else:
            bands = owned_bands(stadium, side, angle + step / 2)
            key = tuple((s.section_id, round(b0, 2), round(b1, 2)) for s, b0, b1 in bands)
        if key != prev_key:
            if prev_key is not None:
                runs.append((start, angle, prev_bands))
            prev_key, prev_bands, start = key, bands, angle
    return runs


def render_park_svg(result, vmax: float, max_dots: int = 400) -> str:
    """One park as an inline SVG: zones shaded by expected fouls, plus the
    landing points that matched nothing drawn on top in red."""
    stadium = result['stadium']
    zone_fouls = result['zone_fouls']
    out = [f'<svg viewBox="0 0 {_W:.0f} {_H:.0f}" width="100%" '
           f'preserveAspectRatio="xMidYMid meet">']
    out.append(f'<rect width="{_W:.0f}" height="{_H:.0f}" fill="#f5f5f5"/>')

    # Shaded zones
    for side in ('1B', '3B'):
        for a0, a1, bands in _merged_bands(stadium, side):
            for sec, r0, r1 in bands:
                if r0 >= R_MAX:
                    continue
                r1 = min(r1, R_MAX)
                p0 = _xy(side, a0, r0)
                p1 = _xy(side, a1, r0)
                p2 = _xy(side, a1, r1)
                p3 = _xy(side, a0, r1)
                fill = _ramp(zone_fouls.get(sec.section_id, 0.0) / vmax if vmax else 0)
                out.append(
                    f'<path d="M{p0[0]:.1f},{p0[1]:.1f} L{p1[0]:.1f},{p1[1]:.1f} '
                    f'L{p2[0]:.1f},{p2[1]:.1f} L{p3[0]:.1f},{p3[1]:.1f} Z" '
                    f'fill="{fill}" stroke="#999" stroke-width="0.4">'
                    f'<title>{sec.section_id} {sec.name} ({side} side)\n'
                    f'{zone_fouls.get(sec.section_id, 0.0):.2f} fouls/game\n'
                    f'{r0:.0f}-{r1:.0f} ft, {a0:.0f}-{a1:.0f} deg</title></path>'
                )

    # Foul lines out to the corner, and a rough outfield arc for orientation
    for side, dist in (('1B', stadium.rf_distance), ('3B', stadium.lf_distance)):
        p = _xy(side, 0, min(dist, R_MAX))
        out.append(f'<line x1="{_CX:.1f}" y1="{_CY:.1f}" x2="{p[0]:.1f}" '
                   f'y2="{p[1]:.1f}" stroke="#333" stroke-width="1.2"/>')
    arc_pts = []
    for k in range(21):
        f = k / 20
        # Interpolate LF -> CF -> RF around the fair wedge (theta -45 .. +45)
        theta = math.radians(-45 + 90 * f)
        d = (stadium.lf_distance * (1 - f) * 2 if f < 0.5 else 0) + \
            (stadium.rf_distance * (f - 0.5) * 2 if f >= 0.5 else 0) + \
            stadium.cf_distance * (1 - abs(f - 0.5) * 2)
        d = min(d, R_MAX)
        arc_pts.append(f'{_CX + d*math.sin(theta):.1f},{_CY - d*math.cos(theta):.1f}')
    out.append(f'<polyline points="{" ".join(arc_pts)}" fill="none" '
               f'stroke="#333" stroke-width="1" stroke-dasharray="3,3"/>')

    # Fouls that matched no section — the balls the model loses
    lost = [l for l in result['landings'] if not l[4]]
    if lost:
        stride = max(1, len(lost) // max_dots)
        for side, angle, dist, _w, _m in lost[::stride]:
            if dist > R_MAX:
                continue
            x, y = _xy(side, angle, dist)
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.6" '
                       f'fill="#d62728" fill-opacity="0.5"/>')

    out.append(f'<circle cx="{_CX:.1f}" cy="{_CY:.1f}" r="3" fill="#000"/>')
    out.append(f'<text x="{_CX:.0f}" y="{_CY+16:.0f}" font-size="10" '
               f'text-anchor="middle" fill="#000">home</text>')
    out.append('</svg>')
    return ''.join(out)


# ============================================================
# Handedness experiment
# ============================================================

def handedness_split(park_key: str, seed: int = 42, sims: int = 400) -> dict:
    """Run one park with an all-RHB and an all-LHB lineup; report the 1B share.

    The two runs use the same 18 batters with only batter_side changed, so any
    movement in the split is the direction model responding to handedness and
    nothing else. Shares are over sided fouls only — behind-plate sections are
    shared between the two sides and would dilute the contrast.
    """
    out = {}
    for hand in ('R', 'L'):
        res = run_park(park_key, handed_lineups(hand), seed=seed, sims=sims)
        w1b, w3b = res['side_weight']['1B'], res['side_weight']['3B']
        sided = w1b + w3b
        out[hand] = {
            'pct_1b': w1b / sided * 100 if sided else float('nan'),
            'fouls_1b': w1b, 'fouls_3b': w3b,
            'total_into_stands': res['total_into_stands'],
            'home_fouls': res['side_weight']['HOME'],
        }
    out['swing_pp'] = out['L']['pct_1b'] - out['R']['pct_1b']
    return out


def split_sampling_noise(park_key: str, seeds: list[int], sims: int) -> float:
    """Standard deviation of the 1B share across seeds, in percentage points.

    Establishes what counts as movement before any handedness claim is made:
    a swing smaller than this band is a rounding error.
    """
    vals = []
    for s in seeds:
        res = run_park(park_key, standard_lineups(), seed=s, sims=sims)
        w1b, w3b = res['side_weight']['1B'], res['side_weight']['3B']
        if w1b + w3b > 0:
            vals.append(w1b / (w1b + w3b) * 100)
    return float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0


# ============================================================
# Report
# ============================================================

def build_html(results: list[dict], flags: dict, handed: dict,
               noise_pp: float, meta: dict) -> str:
    vmax = max((max(r['zone_fouls'].values()) for r in results if r['zone_fouls']),
               default=1.0)
    totals = [r['total_into_stands'] for r in results]
    med = float(np.median(totals))

    h = ['<title>FoulCast park sweep - zone heat maps</title>',
         '<style>body{font-family:monospace;margin:1rem;max-width:1400px}'
         'table{border-collapse:collapse;font-size:12px}'
         'td,th{border:1px solid #ccc;padding:2px 6px;text-align:right}'
         'th:first-child,td:first-child{text-align:left}'
         '.park{border:1px solid #bbb;margin:1rem 0;padding:.5rem;'
         'display:grid;grid-template-columns:minmax(280px,1fr) 1fr;gap:1rem}'
         '.flag{color:#a00}.ok{color:#070}'
         'ul{margin:.3rem 0;padding-left:1.2rem;font-size:12px}'
         '.wrap{overflow-x:auto}</style>']

    h.append('<h1>Park sweep - %d parks, standard lineup</h1>' % len(results))
    h.append(
        '<p>Same 18 batters at every park (Red Sox + Yankees 2024 profiles), '
        'league-average RHP mix, seed %d, %d sims/batter. One row is a full '
        'game: both lineups summed. Median total into stands <b>%.1f</b>; '
        'colour scale is global, 0 to %.1f fouls/game per zone. Red dots are '
        'simulated fouls that matched no section at all.</p>'
        % (meta['seed'], meta['sims'], med, vmax))

    # Summary table
    h.append('<div class="wrap"><table><tr><th>Park</th><th>Total into stands</th>'
             '<th>vs median</th><th>Unmatched/game</th><th>Lost %</th>'
             '<th>1B%</th><th>Zones</th><th>Dead</th><th>Flags</th></tr>')
    for r in sorted(results, key=lambda x: x['total_into_stands']):
        pk = r['park']
        lost_pct = r['unmatched'] / max(r['total_fouls'], 1e-9) * 100
        dead = sum(1 for f in r['zone_fouls'].values() if f <= 0)
        n_flags = len(flags.get(pk, []))
        cls = 'flag' if n_flags else 'ok'
        h.append(
            '<tr><td><a href="#%s">%s</a></td><td>%.1f</td><td>%+.1f</td>'
            '<td>%.1f</td><td>%.0f%%</td><td>%.1f</td><td>%d</td><td>%d</td>'
            '<td class="%s">%d</td></tr>'
            % (pk, r['stadium_name'], r['total_into_stands'],
               r['total_into_stands'] - med, r['unmatched'], lost_pct,
               r.get('pct_1b_of_sided', float('nan')), len(r['zone_fouls']),
               dead, cls, n_flags))
    h.append('</table></div>')

    # Handedness table
    if handed:
        h.append('<h2>Handedness: all-RHB vs all-LHB</h2>')
        h.append('<p>Same 18 batters, batter_side forced. Share is of sided '
                 'fouls (behind-plate zones excluded). Seed-to-seed sampling '
                 'band on this statistic is +/-%.2f pp (1 sd).</p>' % noise_pp)
        h.append('<div class="wrap"><table><tr><th>Park</th><th>All-RHB 1B%</th>'
                 '<th>All-LHB 1B%</th><th>Swing (pp)</th>'
                 '<th>RHB total</th><th>LHB total</th></tr>')
        for pk, d in sorted(handed.items(), key=lambda kv: -abs(kv[1]['swing_pp'])):
            h.append('<tr><td>%s</td><td>%.1f</td><td>%.1f</td>'
                     '<td><b>%+.1f</b></td><td>%.1f</td><td>%.1f</td></tr>'
                     % (pk, d['R']['pct_1b'], d['L']['pct_1b'], d['swing_pp'],
                        d['R']['total_into_stands'], d['L']['total_into_stands']))
        h.append('</table></div>')

    # Per-park maps
    h.append('<h2>Maps</h2>')
    for r in sorted(results, key=lambda x: x['total_into_stands']):
        pk = r['park']
        h.append('<div class="park" id="%s"><div>%s</div>'
                 % (pk, render_park_svg(r, vmax)))
        h.append('<div><h3>%s <small>(%s)</small></h3>'
                 '<p>%.1f into stands (%+.1f vs median) &middot; '
                 '%.1f unmatched &middot; %.1f%% to 1B</p>'
                 % (r['stadium_name'], pk, r['total_into_stands'],
                    r['total_into_stands'] - med, r['unmatched'],
                    r.get('pct_1b_of_sided', float('nan'))))
        pf = flags.get(pk, [])
        if pf:
            h.append('<ul class="flag">' +
                     ''.join('<li>%s</li>' % f for f in pf) + '</ul>')
        else:
            h.append('<p class="ok">no flags</p>')
        h.append('<table><tr><th>Zone</th><th>Fouls/game</th></tr>' + ''.join(
            '<tr><td>%s</td><td>%.2f</td></tr>' % (sid, v)
            for sid, v in sorted(r['zone_fouls'].items(), key=lambda kv: -kv[1])
        ) + '</table></div></div>')

    return '\n'.join(h)


def main():
    ap = argparse.ArgumentParser(description='FoulCast park sweep')
    ap.add_argument('--parks', default='all')
    ap.add_argument('--sims', type=int, default=400)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--seeds', type=int, default=4,
                    help='seeds used to size the 1B/3B sampling band')
    ap.add_argument('--no-handedness', action='store_true')
    ap.add_argument('--out', default=OUT_DIR)
    args = ap.parse_args()

    parks = list(STADIUMS) if args.parks == 'all' else \
        [p.strip() for p in args.parks.split(',')]
    os.makedirs(args.out, exist_ok=True)

    # Sampling band first: the asymmetry flag needs it to know what "moved" means.
    noise_park = 'yankee_stadium' if 'yankee_stadium' in parks else parks[0]
    seeds = [args.seed + i for i in range(max(2, args.seeds))]
    print('Sizing the 1B/3B sampling band at %s over %d seeds...'
          % (noise_park, len(seeds)), flush=True)
    noise_pp = split_sampling_noise(noise_park, seeds, args.sims)
    print('  1 sd = %.2f pp' % noise_pp, flush=True)

    results = []
    for pk in parks:
        print('Running %s...' % pk, flush=True)
        results.append(run_park(pk, standard_lineups(), args.seed, args.sims))

    totals = [r['total_into_stands'] for r in results]
    lost_pcts = [r['unmatched'] / max(r['total_fouls'], 1e-9) * 100 for r in results]
    pct_1bs = [r['pct_1b_of_sided'] for r in results
               if not np.isnan(r['pct_1b_of_sided'])]
    flags = {r['park']: flag_park(r, totals, noise_pp, lost_pcts, pct_1bs)
             for r in results}

    for msg in section_convention_audit(parks):
        print('  [fleet] %s' % msg)

    handed = {}
    if not args.no_handedness:
        for pk in parks:
            print('Handedness %s...' % pk, flush=True)
            handed[pk] = handedness_split(pk, args.seed, args.sims)

    meta = {'seed': args.seed, 'sims': args.sims, 'parks': len(parks),
            'split_noise_pp': noise_pp}

    html_path = os.path.join(args.out, 'park_heatmaps.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(build_html(results, flags, handed, noise_pp, meta))

    json_path = os.path.join(args.out, 'park_sweep.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'meta': meta,
            'parks': [{
                'park': r['park'], 'stadium_name': r['stadium_name'],
                'total_into_stands': r['total_into_stands'],
                'total_fouls': r['total_fouls'], 'unmatched': r['unmatched'],
                'pct_1b_of_sided': r.get('pct_1b_of_sided'),
                'mirror': r.get('mirror'),
                'zone_fouls': r['zone_fouls'], 'flags': flags[r['park']],
            } for r in results],
            'handedness': handed,
        }, f, indent=2)

    n_flagged = sum(1 for v in flags.values() if v)
    print('\n%d/%d parks flagged' % (n_flagged, len(results)))
    for pk, fl in flags.items():
        for f in fl:
            print('  [%s] %s' % (pk, f))
    print('\nHTML: %s\nJSON: %s' % (html_path, json_path))


if __name__ == '__main__':
    main()
