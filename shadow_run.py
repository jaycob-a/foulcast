"""
Shadow Run — Offline validation of FoulCast predictions.

Runs predict_game_fouls() across parks and performs post-run sanity checks.

Usage:
    python shadow_run.py --demo          # Quick test with 3 parks
    python shadow_run.py --parks all     # All 30 parks
    python shadow_run.py --seed 123      # Custom seed
"""
import sys
import os
import json
import argparse
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from foulball.log import get_logger, enable_file_logging
from foulball.batter_profiles import YANKEES_2024_PROFILES, RED_SOX_2024_PROFILES, PITCHER_PROFILES
from foulball.stadium import STADIUMS
from foulball.matchup_engine import predict_game_fouls

logger = get_logger(__name__)

DEMO_PARKS = ['yankee_stadium', 'fenway_park', 'dodger_stadium']

# Park-specific expected distance ranges (mean distance in ft)
PARK_DISTANCE_HINTS = {
    'coors_field': (80, 200),   # high altitude → longer distances
    'fenway_park': (60, 180),   # compact but foul territory extends far
}


def _get_lineup_and_pitcher(park_key):
    """Pick a lineup and pitcher for the given park."""
    # Alternate between two lineups for variety
    if hash(park_key) % 2 == 0:
        lineup = list(YANKEES_2024_PROFILES.values())
        pitcher_name = 'Brayan Bello'
    else:
        lineup = list(RED_SOX_2024_PROFILES.values())
        pitcher_name = 'Gerrit Cole'
    pitch_mix = PITCHER_PROFILES[pitcher_name]['pitch_mix']
    return lineup, pitcher_name, pitch_mix


def run_park(park_key, seed, sims_per_batter=300):
    """Run prediction for a single park. Returns result dict or error."""
    lineup, pitcher_name, pitch_mix = _get_lineup_and_pitcher(park_key)

    np.random.seed(seed)
    stadium = STADIUMS[park_key]()

    t0 = time.time()
    try:
        pred = predict_game_fouls(lineup, pitcher_name, pitch_mix, stadium, sims_per_batter)
    except Exception as e:
        return {'park': park_key, 'error': str(e), 'crashed': True}

    elapsed = time.time() - t0
    events = pred.all_events

    if not events:
        return {'park': park_key, 'error': 'No events produced', 'crashed': False}

    distances = [e.landing_distance for e in events]
    n_1b = sum(1 for e in events if e.landing_side == '1B')
    n_3b = sum(1 for e in events if e.landing_side == '3B')
    n_home = sum(1 for e in events if e.section and e.section.side == 'HOME')
    total = len(events)

    # Section concentration check
    section_counts = {}
    for e in events:
        if e.section:
            sid = e.section.section_id
            section_counts[sid] = section_counts.get(sid, 0) + 1
    max_section_pct = max(section_counts.values()) / total * 100 if section_counts else 0

    return {
        'park': park_key,
        'stadium_name': stadium.name,
        'seed': seed,
        'total_events': total,
        'mean_distance': round(np.mean(distances), 1),
        'max_distance': round(max(distances), 1),
        'n_1b': n_1b,
        'n_3b': n_3b,
        'n_home': n_home,
        'pct_1b': round(n_1b / total * 100, 1),
        'pct_3b': round(n_3b / total * 100, 1),
        'max_section_pct': round(max_section_pct, 1),
        'n_sectioned': sum(1 for e in events if e.section is not None),
        'elapsed_s': round(elapsed, 2),
        'crashed': False,
        'error': None,
    }


def sanity_check(result):
    """Run post-run sanity checks on a park result. Returns list of violations."""
    violations = []

    if result.get('crashed'):
        violations.append(f"CRASH: {result['error']}")
        return violations

    if result.get('error'):
        violations.append(f"ERROR: {result['error']}")
        return violations

    park = result['park']
    mean_d = result['mean_distance']
    max_d = result['max_distance']
    total = result['total_events']
    max_sec_pct = result['max_section_pct']
    pct_1b = result['pct_1b']
    pct_3b = result['pct_3b']

    # No crashes (already checked above)

    # No single section > 50% of all fouls
    if max_sec_pct > 50:
        violations.append(f"Section concentration too high: {max_sec_pct:.1f}%")

    # Mean distance in [20, 200] ft
    if not (20 <= mean_d <= 200):
        violations.append(f"Mean distance out of range: {mean_d:.1f} ft")

    # 1B + 3B should account for most fouls
    side_pct = pct_1b + pct_3b
    if side_pct < 50:
        violations.append(f"1B+3B only {side_pct:.0f}% — expected >50%")

    # Both sides should get some fouls
    if pct_1b < 5:
        violations.append(f"1B side very low: {pct_1b:.0f}%")
    if pct_3b < 5:
        violations.append(f"3B side very low: {pct_3b:.0f}%")

    # Park-specific checks
    if park in PARK_DISTANCE_HINTS:
        lo, hi = PARK_DISTANCE_HINTS[park]
        if not (lo <= mean_d <= hi):
            violations.append(f"Park-specific distance check failed for {park}: "
                              f"{mean_d:.1f} not in [{lo}, {hi}]")

    return violations


def main():
    parser = argparse.ArgumentParser(description='FoulCast Shadow Run')
    parser.add_argument('--demo', action='store_true', help='Quick demo with 3 parks')
    parser.add_argument('--parks', default='demo', help='"all" for 30 parks, or comma-separated keys')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--sims', type=int, default=300, help='Simulations per batter')
    parser.add_argument('--log-file', default=None, help='Write logs to file')
    args = parser.parse_args()

    if args.demo:
        parks = DEMO_PARKS
    elif args.parks == 'all':
        parks = list(STADIUMS.keys())
    elif args.parks == 'demo':
        parks = DEMO_PARKS
    else:
        parks = [p.strip() for p in args.parks.split(',')]

    # Set up file logging
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache', 'shadow_runs')
    os.makedirs(cache_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = args.log_file or os.path.join(cache_dir, f'{timestamp}.log')
    jsonl_path = os.path.join(cache_dir, f'{timestamp}.jsonl')
    enable_file_logging(log_path)

    logger.info("=" * 60)
    logger.info("FOULCAST SHADOW RUN")
    logger.info("Parks: %d | Seed: %d | Sims/batter: %d", len(parks), args.seed, args.sims)
    logger.info("=" * 60)

    results = []
    total_violations = 0

    for park_key in parks:
        if park_key not in STADIUMS:
            logger.error("Unknown park: %s", park_key)
            continue

        logger.info("Running %s...", park_key)
        result = run_park(park_key, args.seed, args.sims)
        results.append(result)

        # Write to JSONL
        with open(jsonl_path, 'a') as f:
            f.write(json.dumps(result) + '\n')

        violations = sanity_check(result)
        if violations:
            total_violations += len(violations)
            for v in violations:
                logger.error("  VIOLATION [%s]: %s", park_key, v)
        else:
            logger.info("  OK: %d events, mean_dist=%.1f, 1B/3B=%.0f%%/%.0f%%, %.1fs",
                        result.get('total_events', 0),
                        result.get('mean_distance', 0),
                        result.get('pct_1b', 0),
                        result.get('pct_3b', 0),
                        result.get('elapsed_s', 0))

    # Summary
    logger.info("=" * 60)
    logger.info("SUMMARY: %d parks, %d violations", len(results), total_violations)
    crashed = [r for r in results if r.get('crashed')]
    if crashed:
        logger.error("CRASHED: %s", [r['park'] for r in crashed])
    if total_violations == 0:
        logger.info("ALL SANITY CHECKS PASSED")
    else:
        logger.error("%d TOTAL VIOLATIONS — review log for details", total_violations)
    logger.info("Results: %s", jsonl_path)
    logger.info("Log: %s", log_path)

    return 1 if total_violations > 0 or crashed else 0


if __name__ == '__main__':
    sys.exit(main())
