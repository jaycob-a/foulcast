"""
CALIBRATION: hand-logged foul balls vs model predictions, by zone.

WHAT THIS ANSWERS
=================

For the games in the observation log, which zones does the model send too many
fouls into, and which too few? This is the first check in the project against
data the model did not generate. `backtest.py` compares physics to physics.
`game_backtest.py` compares predicted foul *volume* to Statcast, which records
volume but not location. `AUDIT.md` names section-level accuracy as the open
question and hand-logged fouls as the missing asset. This script consumes them.

WHAT IT DELIBERATELY DOES NOT ANSWER
====================================

**Total foul volume.** A fan logs the fouls they saw, not the fouls that
happened. Logged totals are a sample of unknown rate, so this script compares
the *shape* of the distribution across zones, never the count. Volume is
`game_backtest.py`'s job and it has real ground truth for it.

**Whether the zone boundaries are right.** A zone can take exactly its
predicted share of fouls while being drawn in the wrong place. `AUDIT.md`
(2026-08-09) establishes that the distance and angle bands in `stadium.py` are
estimated for all 31 parks, and that this "cannot be solved by logging" —
closing it needs a survey, CAD/GIS drawings, or Statcast park geometry. What
the log *can* do is accumulate observations keyed to printed section numbers,
which survive a boundary re-cut. Section 4 of the report tracks progress
toward that, and is honest that the current count is nowhere near enough.

HOW THE COMPARISON IS MADE FAIR
===============================

Three corrections, each guarding against a way of manufacturing a result:

1. **Observable zones only.** A zone the observer could not see is dropped, not
   scored as zero. Scoring it as zero would report every unobserved zone as
   "model over-predicts" — the single easiest false finding available here.

2. **Shares, renormalized.** Expected counts are the model's share of fouls
   *among observable zones*, scaled to the number actually logged. This makes
   the comparison conditional on "a foul was seen and logged", which is what
   the data supports.

3. **A multiple-comparison correction.** Comparing 11-16 zones at p<0.05
   produces roughly one false flag per park by construction. Verdicts use a
   Bonferroni-adjusted threshold, and the raw p-value is shown alongside so the
   adjustment is visible rather than buried.

A known bias this does NOT correct: fans notice balls that come near them.
Logged fouls likely over-represent zones close to the observer's seat, which
would look identical to the model under-predicting there. `observer_section` is
recorded on every session so this can be tested once there are enough sessions
from different seats — it cannot be tested from one vantage point.

Usage:
    python calibrate_log.py                     # every game in the log
    python calibrate_log.py --game 776543       # one game
    python calibrate_log.py --offline           # cached predictions only
    python calibrate_log.py --out report.md --json report.json
"""
import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from foulball import foul_log
from foulball.batter_profiles import BatterFoulProfile, PITCHER_PROFILES
from foulball.live_profiles import enrich_with_spray_profiles
from foulball.log import get_logger
from foulball.matchup_engine import predict_game_fouls
from foulball.seat_map import normalize_label, zone_map_version
from foulball.stadium import STADIUMS

logger = get_logger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '.cache', 'calibration')

SIMS_PER_BATTER = 400
DEFAULT_SEED = 42

# Evidence gates. A zone is only given a verdict when there is enough of it for
# the verdict to mean something; everything else is reported as insufficient
# rather than quietly rendered as a near-1.0 ratio.
MIN_EXPECTED = 5.0     # expected count below this -> no verdict
MIN_OBSERVED = 3       # observed count below this -> no verdict unless E is large
ALPHA = 0.05

# Rough target for boundary work, stated so Section 4 has a denominator rather
# than a vibe. Fitting a single boundary between two adjacent printed sections
# to +/-1 section needs on the order of 30 observations either side of it; a
# park with ~12 boundaries therefore needs several hundred. This is an
# order-of-magnitude planning figure, not a power calculation.
BOUNDARY_TARGET_PER_SECTION = 30


# ============================================================
# Poisson helpers (no scipy — this script runs on the deploy deps)
# ============================================================

def _log_pmf(k: int, lam: float) -> float:
    return -lam + k * math.log(lam) - math.lgamma(k + 1)


def poisson_cdf(k: int, lam: float) -> float:
    """P(X <= k) for X ~ Poisson(lam)."""
    if lam <= 0:
        return 1.0
    total = 0.0
    for i in range(0, k + 1):
        total += math.exp(_log_pmf(i, lam))
    return min(1.0, total)


def poisson_two_sided_p(observed: int, expected: float) -> float:
    """Two-sided p-value by the doubled-tail convention.

    Exact rather than normal-approximated: expected counts here are often
    under 10, where the normal approximation is wrong in the direction that
    invents findings.
    """
    if expected <= 0:
        return 1.0 if observed == 0 else 0.0
    lower = poisson_cdf(observed, expected)
    upper = 1.0 - poisson_cdf(observed - 1, expected) if observed > 0 else 1.0
    return min(1.0, 2.0 * min(lower, upper))


# ============================================================
# Log loading
# ============================================================

def load_log(db_path: str | None, min_confidence: str = 'approx') -> dict:
    """Read the observation log, grouped by game.

    `min_confidence` drops rows the observer flagged as guesses. A guessed
    section is not an observation of a section.
    """
    rank = {'guess': 0, 'approx': 1, 'exact': 2}
    floor = rank.get(min_confidence, 1)

    conn = foul_log.connect(db_path)
    try:
        fouls = foul_log.list_fouls(conn)
        sessions = foul_log.list_sessions(conn)
        totals = foul_log.counts(conn)
    finally:
        conn.close()

    kept, dropped_conf = [], 0
    for f in fouls:
        conf = f.get('location_confidence') or 'approx'
        if rank.get(conf, 1) < floor:
            dropped_conf += 1
            continue
        kept.append(f)

    by_game = defaultdict(list)
    for f in kept:
        by_game[f.get('game_pk')].append(f)

    sessions_by_game = defaultdict(list)
    for s in sessions:
        sessions_by_game[s.get('game_pk')].append(s)

    return {
        'fouls': kept,
        'by_game': dict(by_game),
        'sessions_by_game': dict(sessions_by_game),
        'all_sessions': sessions,
        'totals': totals,
        'dropped_low_confidence': dropped_conf,
    }


def game_observable_zones(stadium, sessions: list[dict]) -> set[str]:
    """Union of what the sessions on this game could see.

    Union, not intersection: two observers on opposite sides between them cover
    both, and a zone is comparable if *someone* was watching it.
    """
    zones = set()
    for s in sessions:
        zones |= foul_log.observable_zones(stadium, s.get('scope'))
    return zones


# ============================================================
# Model predictions for a logged game
# ============================================================

def _profiles_for(game_pk: int, team_id: int, pitcher_hand: str,
                  offline: bool) -> list:
    if offline or not team_id:
        return []
    try:
        from foulball.mlb_api import get_lineup
        players = get_lineup(game_pk, team_id)[:9]
    except Exception as e:
        logger.warning("Lineup unavailable for team %s in game %s: %s",
                       team_id, game_pk, e)
        return []

    profiles, by_id = [], {}
    for p in players:
        side = p.bats
        if side == 'S':
            side = 'L' if pitcher_hand == 'R' else 'R'
        prof = BatterFoulProfile(player_name=p.name, player_id=p.mlb_id,
                                 batter_side=side)
        profiles.append(prof)
        by_id[p.mlb_id] = prof
    enrich_with_spray_profiles(by_id)
    return profiles


def _pitchers_for(game_pk: int, offline: bool) -> tuple[str, str]:
    if offline:
        return 'TBD', 'TBD'
    try:
        import statsapi
        rows = statsapi.schedule(game_id=game_pk)
        if rows:
            r = rows[0]
            return (r.get('away_probable_pitcher') or 'TBD',
                    r.get('home_probable_pitcher') or 'TBD')
    except Exception as e:
        logger.warning("Pitcher lookup failed for game %s: %s", game_pk, e)
    return 'TBD', 'TBD'


def _mix(name: str) -> tuple[dict, str]:
    if name in PITCHER_PROFILES:
        p = PITCHER_PROFILES[name]
        return p['pitch_mix'], p['hand']
    return {'FF': .30, 'SL': .20, 'CH': .15, 'SI': .15, 'CU': .10, 'FC': .10}, 'R'


def predict_zone_shares(game_pk: int, park_key: str, away_id: int, home_id: int,
                        sims: int = SIMS_PER_BATTER, seed: int = DEFAULT_SEED,
                        offline: bool = False, use_cache: bool = True) -> dict | None:
    """Model's expected fouls per zone for one game.

    Cached to disk keyed by everything that changes the answer, including the
    park's zone-map fingerprint — so an edit to stadium.py invalidates stale
    predictions instead of silently reusing them.
    """
    if park_key not in STADIUMS:
        logger.error("Unknown park_key %r for game %s", park_key, game_pk)
        return None
    stadium = STADIUMS[park_key]()
    zmv = zone_map_version(stadium)

    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(
        CACHE_DIR, f"pred_{game_pk}_{park_key}_{sims}_{seed}_{zmv.split(':')[-1]}.json")
    if use_cache and os.path.exists(cache_file):
        with open(cache_file, encoding='utf-8') as fh:
            return json.load(fh)
    if offline:
        logger.warning("No cached prediction for game %s and --offline is set", game_pk)
        return None

    away_p, home_p = _pitchers_for(game_pk, offline)
    home_mix, home_hand = _mix(home_p)
    away_mix, away_hand = _mix(away_p)

    away_profiles = _profiles_for(game_pk, away_id, home_hand, offline)
    home_profiles = _profiles_for(game_pk, home_id, away_hand, offline)
    if not away_profiles and not home_profiles:
        logger.error("No lineups for game %s — cannot predict", game_pk)
        return None

    np.random.seed(seed)
    zone_expected: dict[str, float] = defaultdict(float)
    zone_catchable: dict[str, float] = defaultdict(float)

    for profiles, pitcher, mix in ((away_profiles, home_p, home_mix),
                                   (home_profiles, away_p, away_mix)):
        if not profiles:
            continue
        pred = predict_game_fouls(profiles, pitcher, mix, stadium, sims)
        for sp in pred.section_predictions:
            zone_expected[sp.section.section_id] += sp.expected_fouls
            zone_catchable[sp.section.section_id] += sp.catchable_fouls

    out = {
        'game_pk': game_pk,
        'park_key': park_key,
        'zone_map_version': zmv,
        'sims_per_batter': sims,
        'seed': seed,
        'away_pitcher': away_p,
        'home_pitcher': home_p,
        'n_away_batters': len(away_profiles),
        'n_home_batters': len(home_profiles),
        'expected': dict(zone_expected),
        'catchable': dict(zone_catchable),
    }
    with open(cache_file, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=1)
    return out


# ============================================================
# Comparison
# ============================================================

def compare_game(game_pk: int, fouls: list[dict], sessions: list[dict],
                 prediction: dict, stadium) -> dict:
    """Observed vs expected counts by zone for one game.

    Returns per-zone rows plus the bookkeeping needed to aggregate honestly:
    which zones were comparable, and how many observations fell outside them.
    """
    observable = game_observable_zones(stadium, sessions)
    if not observable:
        # No session, or a session with no declared scope. Comparing anyway
        # would silently assume the observer saw the whole bowl.
        return {
            'game_pk': game_pk,
            'skipped': 'no session scope recorded — coverage unknown',
            'n_fouls': len(fouls),
        }

    zone_of = {s.section_id: s for s in stadium.sections}

    observed = Counter()
    unassigned, outside_scope = 0, 0
    for f in fouls:
        zid = f.get('model_zone_id')
        if not zid or zid not in zone_of:
            unassigned += 1
            continue
        if zid not in observable:
            outside_scope += 1
            continue
        observed[zid] += 1

    n_obs = sum(observed.values())
    expected_raw = {z: v for z, v in prediction['expected'].items() if z in observable}
    total_expected = sum(expected_raw.values())

    rows = []
    if n_obs and total_expected > 0:
        for zid in sorted(observable):
            share = expected_raw.get(zid, 0.0) / total_expected
            rows.append({
                'zone_id': zid,
                'zone_name': zone_of[zid].name if zid in zone_of else zid,
                'side': zone_of[zid].side if zid in zone_of else '?',
                'level': zone_of[zid].level if zid in zone_of else '?',
                'observed': observed.get(zid, 0),
                'expected': share * n_obs,
                'model_share': share,
            })

    return {
        'game_pk': game_pk,
        'park_key': prediction['park_key'],
        'n_fouls': len(fouls),
        'n_compared': n_obs,
        'unassigned': unassigned,
        'outside_scope': outside_scope,
        'n_observable_zones': len(observable),
        'observable': sorted(observable),
        'rows': rows,
        'sessions': len(sessions),
        'zone_map_version': prediction.get('zone_map_version'),
    }


def aggregate(comparisons: list[dict]) -> list[dict]:
    """Sum observed and expected per zone across games.

    Poisson counts add, so summing expectations across games is legitimate.
    Zones are keyed by (park, zone) — two parks' `3B-LB1` are different seats
    and must never be pooled.
    """
    acc: dict[tuple, dict] = {}
    for c in comparisons:
        if c.get('skipped'):
            continue
        for r in c['rows']:
            key = (c['park_key'], r['zone_id'])
            if key not in acc:
                acc[key] = {
                    'park_key': c['park_key'], 'zone_id': r['zone_id'],
                    'zone_name': r['zone_name'], 'side': r['side'],
                    'level': r['level'], 'observed': 0, 'expected': 0.0,
                    'games': 0,
                }
            a = acc[key]
            a['observed'] += r['observed']
            a['expected'] += r['expected']
            a['games'] += 1

    rows = list(acc.values())
    n_tests = sum(1 for r in rows if _has_evidence(r))
    threshold = ALPHA / n_tests if n_tests else ALPHA

    for r in rows:
        r['diff'] = r['observed'] - r['expected']
        r['ratio'] = (r['observed'] / r['expected']) if r['expected'] > 0 else None
        r['p_value'] = poisson_two_sided_p(r['observed'], r['expected'])
        r['adjusted_threshold'] = threshold
        if not _has_evidence(r):
            r['verdict'] = 'insufficient data'
        elif r['p_value'] >= threshold:
            r['verdict'] = 'consistent'
        elif r['observed'] > r['expected']:
            r['verdict'] = 'UNDER-predicted'   # more fouls landed here than modeled
        else:
            r['verdict'] = 'OVER-predicted'

    rows.sort(key=lambda r: (-abs(r['diff']), r['park_key'], r['zone_id']))
    return rows


def _has_evidence(row: dict) -> bool:
    return row['expected'] >= MIN_EXPECTED or row['observed'] >= max(MIN_OBSERVED, 5)


# ============================================================
# Boundary-correction readiness
# ============================================================

def boundary_readiness(fouls: list[dict]) -> dict:
    """How far the log is from being able to re-cut zone boundaries.

    The unit that matters is the printed section, not the zone: printed
    sections survive a boundary change, zone IDs do not. A printed section with
    observations either side of a proposed boundary is what a re-cut gets
    fitted to.
    """
    per_park_section = defaultdict(Counter)
    unmapped = defaultdict(Counter)
    no_printed = 0
    conf = Counter()

    for f in fouls:
        conf[f.get('location_confidence') or 'unset'] += 1
        park = f.get('park_key') or 'unknown'
        printed = normalize_label(f.get('printed_section') or '')
        if not printed:
            no_printed += 1
            continue
        per_park_section[park][printed] += 1
        if not f.get('model_zone_id'):
            unmapped[park][printed] += 1

    parks = {}
    for park, counter in per_park_section.items():
        stadium = STADIUMS[park]() if park in STADIUMS else None
        n_zones = len(stadium.sections) if stadium else 0
        # A park's zones meet along roughly (zones - 1) internal boundaries.
        boundaries = max(n_zones - 1, 1)
        need = boundaries * 2 * BOUNDARY_TARGET_PER_SECTION
        parks[park] = {
            'sections_seen': len(counter),
            'observations': sum(counter.values()),
            'zones': n_zones,
            'target_observations': need,
            'pct_of_target': 100.0 * sum(counter.values()) / need if need else 0.0,
            'top_sections': counter.most_common(10),
            'unmapped_sections': sorted(unmapped.get(park, Counter()).items()),
        }

    return {
        'parks': parks,
        'entries_without_printed_section': no_printed,
        'confidence_mix': dict(conf),
    }


def zone_coverage_gaps(comparisons: list[dict]) -> list[tuple]:
    """Observable zones that have never received a single logged foul."""
    seen = Counter()
    observable = defaultdict(set)
    for c in comparisons:
        if c.get('skipped'):
            continue
        for z in c['observable']:
            observable[c['park_key']].add(z)
        for r in c['rows']:
            if r['observed']:
                seen[(c['park_key'], r['zone_id'])] += r['observed']
    gaps = []
    for park, zones in observable.items():
        for z in sorted(zones):
            if not seen.get((park, z)):
                gaps.append((park, z))
    return gaps


# ============================================================
# Report
# ============================================================

def format_report(data: dict) -> str:
    L = []
    add = L.append

    add("=" * 74)
    add("FOUL LOG CALIBRATION — logged observations vs model predictions")
    add("=" * 74)
    add("")
    add("What this establishes: which zones the model sends too many or too few")
    add("fouls into, for the games in the log, among zones the observer could see.")
    add("")
    add("What it does NOT establish:")
    add("  - Total foul volume. Logged fouls are a sample of unknown rate; only")
    add("    the shape across zones is compared. Volume is game_backtest.py's job.")
    add("  - Whether the zone boundaries are in the right place. Per AUDIT.md the")
    add("    distance/angle bands are estimated for all 31 parks, and logging")
    add("    cannot fix that. Section 4 tracks progress toward data that could")
    add("    support a re-cut once real seating geometry exists to fit against.")
    add("  - Anything about zones nobody was watching. Those are dropped, not")
    add("    scored as zero.")
    add("")

    t = data['totals']
    add("-" * 74)
    add("1. WHAT IS IN THE LOG")
    add("-" * 74)
    add(f"  Entries stored              : {t['total']}")
    add(f"  Live (not voided)           : {t['live']}")
    add(f"  Games with observations     : {t['games']}")
    add(f"  Dropped as low-confidence   : {data['dropped_low_confidence']}")
    add("")

    if not data['comparisons']:
        add("  Nothing comparable yet.")
        add("")
        add("  To produce a verdict for even one zone, that zone needs an expected")
        add(f"  count of at least {MIN_EXPECTED:.0f}. With ~11-16 zones per park and fouls")
        add("  spread across them, that is roughly 60-100 logged fouls in one park")
        add("  before the busiest zones become testable, and several hundred before")
        add("  the quiet ones do. One well-logged game yields perhaps 20-40.")
        add("")
        add(_readiness_block(data['readiness']))
        return "\n".join(L)

    add("-" * 74)
    add("2. COVERAGE, PER GAME")
    add("-" * 74)
    add(f"  {'game_pk':>10}  {'park':<20} {'logged':>7} {'compared':>9} "
        f"{'unmapped':>9} {'off-scope':>10} {'zones':>6}")
    for c in data['comparisons']:
        if c.get('skipped'):
            add(f"  {c['game_pk']:>10}  SKIPPED — {c['skipped']} ({c['n_fouls']} entries)")
            continue
        add(f"  {c['game_pk']:>10}  {c['park_key'][:20]:<20} {c['n_fouls']:>7} "
            f"{c['n_compared']:>9} {c['unassigned']:>9} {c['outside_scope']:>10} "
            f"{c['n_observable_zones']:>6}")
    add("")
    add("  unmapped  = logged fouls whose printed section maps to no zone, or that")
    add("              carried no zone at all. These are not errors; see Section 4.")
    add("  off-scope = logged fouls in zones the session did not claim to observe.")
    add("")

    rows = data['zone_rows']
    tested = [r for r in rows if r['verdict'] != 'insufficient data']
    add("-" * 74)
    add("3. BY ZONE — OVER- AND UNDER-PREDICTION")
    add("-" * 74)
    if tested:
        add(f"  Bonferroni-adjusted threshold: p < {tested[0]['adjusted_threshold']:.4f} "
            f"({len(tested)} zones tested at alpha={ALPHA})")
    add("")
    add(f"  {'park':<16} {'zone':<9} {'obs':>5} {'exp':>7} {'diff':>7} {'ratio':>6} "
        f"{'p':>8}  verdict")
    for r in rows:
        ratio = f"{r['ratio']:.2f}" if r['ratio'] is not None else "  -  "
        add(f"  {r['park_key'][:16]:<16} {r['zone_id']:<9} {r['observed']:>5} "
            f"{r['expected']:>7.1f} {r['diff']:>+7.1f} {ratio:>6} "
            f"{r['p_value']:>8.4f}  {r['verdict']}")
    add("")
    add("  UNDER-predicted = more fouls landed here than the model expected.")
    add("  OVER-predicted  = fewer.")
    add("  'insufficient data' is the honest answer for a zone with a small")
    add("  expected count; a ratio computed there is noise with a decimal point.")
    add("")

    if data['gaps']:
        add(f"  Observable zones with zero logged fouls ({len(data['gaps'])}):")
        for park, z in data['gaps'][:25]:
            add(f"    {park} {z}")
        if len(data['gaps']) > 25:
            add(f"    ... and {len(data['gaps']) - 25} more")
        add("  A zero here is only evidence against the model once that zone's")
        add("  expected count is meaningful. Until then it means 'not seen yet'.")
        add("")

    add(_readiness_block(data['readiness']))
    return "\n".join(L)


def _readiness_block(readiness: dict) -> str:
    L = []
    add = L.append
    add("-" * 74)
    add("4. BOUNDARY-CORRECTION READINESS")
    add("-" * 74)
    add("  Scoring the current zones needs zone-level counts. CORRECTING them needs")
    add("  observations keyed to printed section numbers, because printed sections")
    add("  survive a boundary re-cut and zone IDs do not.")
    add("")
    add("  Even a full log cannot re-cut boundaries on its own — there is no")
    add("  surveyed geometry to fit against yet (AUDIT.md, SOURCED_DATA.md). What")
    add("  this section tracks is whether the observations will be there when it")
    add("  exists. They cannot be collected after 2026-09-27.")
    add("")
    add(f"  Entries with no printed section: {readiness['entries_without_printed_section']}")
    add(f"  Confidence mix: {readiness['confidence_mix'] or '(none)'}")
    add("")
    if not readiness['parks']:
        add("  No printed sections logged yet. Every entry that carries one is worth")
        add("  more than one that does not — it is the only field here that is a")
        add("  fact about the building rather than an estimate.")
        return "\n".join(L)

    for park, p in sorted(readiness['parks'].items()):
        add(f"  {park}")
        add(f"    distinct printed sections seen : {p['sections_seen']}")
        add(f"    observations                   : {p['observations']}")
        add(f"    order-of-magnitude target      : {p['target_observations']} "
            f"({p['pct_of_target']:.1f}% there)")
        if p['top_sections']:
            top = ", ".join(f"{s}x{n}" for s, n in p['top_sections'])
            add(f"    most-logged sections           : {top}")
        if p['unmapped_sections']:
            um = ", ".join(f"{s}x{n}" for s, n in p['unmapped_sections'][:12])
            add(f"    printed sections no zone claims: {um}")
            add("      ^ these are the most informative rows in the log: real seats")
            add("        the park model does not cover.")
        add("")
    return "\n".join(L)


# ============================================================
# Main
# ============================================================

def run(args) -> dict:
    log = load_log(args.db, min_confidence=args.min_confidence)

    by_game = log['by_game']
    if args.game:
        by_game = {k: v for k, v in by_game.items() if k == args.game}

    comparisons = []
    for game_pk, fouls in sorted(by_game.items(), key=lambda kv: (kv[0] or 0)):
        if not game_pk:
            logger.warning("%d entries carry no game_pk — skipped", len(fouls))
            continue
        sessions = log['sessions_by_game'].get(game_pk, [])
        park_key = (fouls[0].get('park_key')
                    or (sessions[0].get('park_key') if sessions else None))
        if park_key not in STADIUMS:
            comparisons.append({'game_pk': game_pk, 'n_fouls': len(fouls),
                                'skipped': f'unknown park_key {park_key!r}'})
            continue

        away_id = home_id = None
        for s in sessions:
            away_id = away_id or s.get('away_team_id')
            home_id = home_id or s.get('home_team_id')

        pred = predict_zone_shares(
            game_pk, park_key, away_id, home_id,
            sims=args.sims, seed=args.seed,
            offline=args.offline, use_cache=not args.no_cache,
        )
        if pred is None:
            comparisons.append({'game_pk': game_pk, 'n_fouls': len(fouls),
                                'skipped': 'no model prediction available'})
            continue

        stadium = STADIUMS[park_key]()
        comparisons.append(compare_game(game_pk, fouls, sessions, pred, stadium))

    usable = [c for c in comparisons if not c.get('skipped') and c['rows']]
    return {
        'totals': log['totals'],
        'dropped_low_confidence': log['dropped_low_confidence'],
        'comparisons': comparisons if usable else [c for c in comparisons if c.get('skipped')],
        'zone_rows': aggregate(usable),
        'gaps': zone_coverage_gaps(usable),
        'readiness': boundary_readiness(log['fouls']),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--db', default=None, help='log database path (default: data/foul_log.db)')
    ap.add_argument('--game', type=int, default=None, help='limit to one game_pk')
    ap.add_argument('--sims', type=int, default=SIMS_PER_BATTER,
                    help='simulations per batter (default: %(default)s)')
    ap.add_argument('--seed', type=int, default=DEFAULT_SEED)
    ap.add_argument('--offline', action='store_true',
                    help='use cached predictions only, no MLB API calls')
    ap.add_argument('--no-cache', action='store_true', help='recompute predictions')
    ap.add_argument('--min-confidence', default='approx',
                    choices=['guess', 'approx', 'exact'],
                    help='drop entries below this location confidence '
                         '(default: %(default)s, i.e. guesses excluded)')
    ap.add_argument('--out', default=None, help='write the text report here too')
    ap.add_argument('--json', dest='json_out', default=None,
                    help='write machine-readable results here')
    args = ap.parse_args()

    data = run(args)
    report = format_report(data)
    print(report)

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as fh:
            fh.write(report + "\n")
        logger.info("Wrote %s", args.out)
    if args.json_out:
        with open(args.json_out, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=1, default=str)
        logger.info("Wrote %s", args.json_out)


if __name__ == '__main__':
    main()
