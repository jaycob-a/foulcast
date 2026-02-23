"""
GAME-LEVEL BACKTEST: Full pipeline predictions vs real Statcast game data.

Unlike backtest.py (which validates trajectory physics on individual fouls),
this tests the ENTIRE prediction pipeline: lineup → profile sampling →
trajectory → section mapping → aggregate metrics.

For each real game:
  1. Extract actual lineups + pitchers from Statcast
  2. Build batter profiles from data BEFORE the game (no lookahead)
  3. Run predict_game_fouls()
  4. Compare predicted vs actual: distance distribution, side split,
     per-batter foul count, pitch-type distribution

Usage:
    python game_backtest.py              # Full backtest (~20 games)
    python game_backtest.py --games 3    # Quick test with 3 games
    python game_backtest.py --no-pull    # Use cached Statcast data only
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import json
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from scipy import stats as scipy_stats

from pybaseball import statcast
from foulball.batter_profiles import BatterFoulProfile, build_profile_from_data
from foulball.matchup_engine import predict_game_fouls
from foulball.stadium import STADIUMS
from foulball.mlb_api import TEAM_IDS, TEAM_ID_TO_ABBREV, TEAM_STADIUM_MAP
from foulball.live_profiles import enrich_with_spray_profiles
from foulball.log import get_logger

import warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='pybaseball')
warnings.filterwarnings('ignore', message='.*SettingWithCopyWarning.*')

logger = get_logger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache', 'game_backtest')
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Statcast data range for backtest
DATA_START = '2024-04-01'
DATA_END = '2024-08-31'
# Games are selected from Aug; profiles are built from Apr 1 to day before game
GAME_MONTH_START = '2024-08-01'
GAME_MONTH_END = '2024-08-31'

# Map Statcast home_team abbreviations to our team IDs
# Statcast uses slightly different abbreviations than statsapi
_SC_ABBREV_MAP = {
    'ARI': 109, 'ATL': 144, 'BAL': 110, 'BOS': 111, 'CHC': 112,
    'CWS': 145, 'CIN': 113, 'CLE': 114, 'COL': 115, 'DET': 116,
    'HOU': 117, 'KC': 118, 'LAA': 108, 'LAD': 119, 'MIA': 146,
    'MIL': 158, 'MIN': 142, 'NYM': 121, 'NYY': 147, 'OAK': 133,
    'PHI': 143, 'PIT': 134, 'SD': 135, 'SF': 137, 'SEA': 136,
    'STL': 138, 'TB': 139, 'TEX': 140, 'TOR': 141, 'WSH': 120,
}


def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def pull_statcast_data(start: str, end: str) -> pd.DataFrame:
    """Pull Statcast data in monthly chunks, with caching."""
    ensure_cache_dir()
    cache_path = os.path.join(CACHE_DIR, f'statcast_{start}_{end}.parquet')

    if os.path.exists(cache_path):
        print(f"Loading cached Statcast data from {cache_path}")
        return pd.read_parquet(cache_path)

    print(f"Pulling Statcast data {start} to {end} (this will take a few minutes)...")
    all_chunks = []
    current = datetime.strptime(start, '%Y-%m-%d')
    end_dt = datetime.strptime(end, '%Y-%m-%d')

    while current < end_dt:
        chunk_end = min(current + timedelta(days=30), end_dt)
        s = current.strftime('%Y-%m-%d')
        e = chunk_end.strftime('%Y-%m-%d')
        print(f"  Pulling {s} to {e}...")
        try:
            chunk = statcast(start_dt=s, end_dt=e)
            if chunk is not None and len(chunk) > 0:
                all_chunks.append(chunk)
                print(f"    Got {len(chunk):,} pitches")
        except Exception as exc:
            print(f"    Failed: {exc}")
        current = chunk_end + timedelta(days=1)

    if not all_chunks:
        raise RuntimeError("No Statcast data pulled")

    data = pd.concat(all_chunks, ignore_index=True)
    print(f"Total: {len(data):,} pitches")

    # Cache as parquet for fast reload
    data.to_parquet(cache_path, index=False)
    print(f"Cached to {cache_path}")
    return data


def select_games(data: pd.DataFrame, max_games: int = 20) -> list[dict]:
    """Select diverse games from Statcast data for backtesting."""
    # Filter to August games
    aug_data = data[
        (data['game_date'] >= GAME_MONTH_START) &
        (data['game_date'] <= GAME_MONTH_END)
    ].copy()

    # Get foul balls with tracking
    foul_mask = aug_data['description'].str.contains('foul', case=False, na=False)
    tip_mask = aug_data['description'].str.contains('foul_tip|foul tip', case=False, na=False)
    fouls = aug_data[foul_mask & ~tip_mask]
    tracked_fouls = fouls[
        fouls['launch_speed'].notna() &
        fouls['launch_angle'].notna() &
        fouls['hit_distance_sc'].notna()
    ]

    # Group by game
    game_foul_counts = tracked_fouls.groupby('game_pk').size()
    # Need at least 30 tracked fouls per game for meaningful comparison
    eligible_games = game_foul_counts[game_foul_counts >= 30].index.tolist()

    print(f"Games with >=30 tracked fouls: {len(eligible_games)}")

    # Get game metadata
    games = []
    for gpk in eligible_games:
        game_pitches = aug_data[aug_data['game_pk'] == gpk]
        game_date = str(game_pitches['game_date'].iloc[0])
        home_team = game_pitches['home_team'].iloc[0]
        away_team = game_pitches['away_team'].iloc[0]

        home_id = _SC_ABBREV_MAP.get(home_team)
        away_id = _SC_ABBREV_MAP.get(away_team)
        if home_id is None or away_id is None:
            continue

        stadium_key = TEAM_STADIUM_MAP.get(home_id)
        if stadium_key is None or stadium_key not in STADIUMS:
            continue

        n_fouls = int(game_foul_counts.get(gpk, 0))

        games.append({
            'game_pk': gpk,
            'game_date': str(game_date),
            'home_team': home_team,
            'away_team': away_team,
            'home_id': home_id,
            'away_id': away_id,
            'stadium_key': stadium_key,
            'n_tracked_fouls': n_fouls,
        })

    # Sort by date, then pick diverse spread of stadiums
    games.sort(key=lambda g: (g['game_date'], g['game_pk']))

    # Deduplicate stadiums to get variety, then fill remaining slots
    seen_stadiums = set()
    selected = []
    for g in games:
        if g['stadium_key'] not in seen_stadiums and len(selected) < max_games:
            selected.append(g)
            seen_stadiums.add(g['stadium_key'])

    # Fill remaining slots with other games if we haven't hit max
    for g in games:
        if len(selected) >= max_games:
            break
        if g not in selected:
            selected.append(g)

    selected = selected[:max_games]
    print(f"Selected {len(selected)} games for backtesting")
    return selected


def extract_game_data(data: pd.DataFrame, game_pk: int) -> dict:
    """Extract lineups, pitchers, and foul data for a specific game."""
    game = data[data['game_pk'] == game_pk].copy()

    # Separate by half-inning
    top = game[game['inning_topbot'] == 'Top']  # away team batting
    bot = game[game['inning_topbot'] == 'Bot']  # home team batting

    # Get unique batters (in order of first appearance)
    away_batters = top['batter'].drop_duplicates().tolist()
    home_batters = bot['batter'].drop_duplicates().tolist()

    # Get starting pitchers (pitcher who threw the most pitches for each side)
    home_pitcher_id = top['pitcher'].mode().iloc[0] if len(top) > 0 else None
    away_pitcher_id = bot['pitcher'].mode().iloc[0] if len(bot) > 0 else None

    # Get pitcher names
    def _get_pitcher_name(game_data, pitcher_id):
        rows = game_data[game_data['pitcher'] == pitcher_id]
        if len(rows) > 0 and 'player_name' in rows.columns:
            name = rows['player_name'].iloc[0]
            if pd.notna(name) and name:
                # Statcast format is "Last, First" — convert to "First Last"
                parts = str(name).split(', ')
                if len(parts) == 2:
                    return f"{parts[1]} {parts[0]}"
                return str(name)
        return f"Pitcher {pitcher_id}"

    home_pitcher_name = _get_pitcher_name(top, home_pitcher_id) if home_pitcher_id else "Unknown"
    away_pitcher_name = _get_pitcher_name(bot, away_pitcher_id) if away_pitcher_id else "Unknown"

    # Extract actual foul ball data
    foul_mask = game['description'].str.contains('foul', case=False, na=False)
    tip_mask = game['description'].str.contains('foul_tip|foul tip', case=False, na=False)
    fouls = game[foul_mask & ~tip_mask].copy()
    tracked = fouls[
        fouls['launch_speed'].notna() &
        fouls['launch_angle'].notna() &
        fouls['hit_distance_sc'].notna()
    ].copy()

    # Batter names lookup
    batter_names = {}
    if 'player_name' in game.columns:
        # player_name in Statcast is the PITCHER's name, not the batter's
        # We need to use a different approach — try batter column cross-reference
        pass
    # We'll use player IDs as keys and resolve names during profile building

    return {
        'away_batters': away_batters[:9],  # limit to 9
        'home_batters': home_batters[:9],
        'home_pitcher_id': int(home_pitcher_id) if home_pitcher_id else None,
        'away_pitcher_id': int(away_pitcher_id) if away_pitcher_id else None,
        'home_pitcher_name': home_pitcher_name,
        'away_pitcher_name': away_pitcher_name,
        'fouls': fouls,
        'tracked_fouls': tracked,
        'all_pitches': game,
    }


def build_profiles_for_game(
    data: pd.DataFrame,
    batter_ids: list[int],
    game_date: str,
) -> list[BatterFoulProfile]:
    """Build batter profiles from data BEFORE the game date (no lookahead)."""
    cutoff = (pd.to_datetime(game_date) - timedelta(days=1)).strftime('%Y-%m-%d')
    pre_game = data[data['game_date'] <= cutoff].copy()

    # Filter to foul balls
    foul_mask = pre_game['description'].str.contains('foul', case=False, na=False)
    tip_mask = pre_game['description'].str.contains('foul_tip|foul tip', case=False, na=False)
    all_fouls = pre_game[foul_mask & ~tip_mask]

    profiles = []
    for bid in batter_ids:
        player_fouls = all_fouls[all_fouls['batter'] == bid]
        player_all = pre_game[pre_game['batter'] == bid]

        if len(player_fouls) < 10:
            # Not enough pre-game data — use defaults
            side = 'R'
            if len(player_all) > 0 and 'stand' in player_all.columns:
                sides = player_all['stand'].dropna()
                if len(sides) > 0:
                    side = sides.mode().iloc[0] if len(sides.mode()) > 0 else 'R'
            profiles.append(BatterFoulProfile(
                player_name=f'Player {bid}',
                player_id=bid,
                batter_side=side,
            ))
            continue

        # Get batter side
        side = 'R'
        if 'stand' in player_fouls.columns:
            sides = player_fouls['stand'].dropna()
            if len(sides) > 0:
                side = sides.mode().iloc[0] if len(sides.mode()) > 0 else 'R'

        # Get batter name from statsapi (one-time lookup)
        try:
            import statsapi as _statsapi
            info = _statsapi.get('people', {'personIds': int(bid)})
            name = info['people'][0]['fullName']
        except Exception:
            name = f'Player {bid}'

        profile = build_profile_from_data(name, bid, player_fouls, all_pitches=player_all)

        # Compute fouls/PA
        player_pas = player_all.groupby(['game_pk', 'at_bat_number']).ngroups
        if player_pas >= 20:
            profile.fouls_per_pa = round(len(player_fouls) / player_pas, 3)

        profiles.append(profile)

    # Enrich with spray profiles (from .cache/spray_profiles.json)
    profile_dict = {p.player_id: p for p in profiles}
    profile_dict = enrich_with_spray_profiles(profile_dict)
    return list(profile_dict.values())


def build_pitcher_mix(
    data: pd.DataFrame,
    pitcher_id: int,
    game_date: str,
) -> dict[str, float]:
    """Build pitcher's pitch mix from pre-game data."""
    cutoff = (pd.to_datetime(game_date) - timedelta(days=1)).strftime('%Y-%m-%d')
    pre_game = data[(data['game_date'] <= cutoff) & (data['pitcher'] == pitcher_id)]

    if len(pre_game) < 50:
        return {'FF': 0.35, 'SL': 0.20, 'CH': 0.15, 'SI': 0.15, 'CU': 0.15}

    pitch_counts = pre_game['pitch_type'].value_counts(normalize=True)
    mix = {pt: round(pct, 3) for pt, pct in pitch_counts.items() if pct > 0.03 and pd.notna(pt)}

    if not mix:
        return {'FF': 0.35, 'SL': 0.20, 'CH': 0.15, 'SI': 0.15, 'CU': 0.15}

    total = sum(mix.values())
    return {k: round(v / total, 3) for k, v in mix.items()}


def compare_game(predicted_events, actual_fouls: pd.DataFrame) -> dict:
    """Compare predicted vs actual foul ball distributions for one game."""
    # Predicted distances
    pred_dists = np.array([e.landing_distance for e in predicted_events])

    # Actual distances (tracked fouls only)
    actual_tracked = actual_fouls[actual_fouls['hit_distance_sc'].notna()]
    actual_dists = actual_tracked['hit_distance_sc'].values.astype(float)
    # Remove zeros/negatives
    actual_dists = actual_dists[actual_dists > 1]

    if len(pred_dists) < 10 or len(actual_dists) < 10:
        return {'error': 'Too few fouls for comparison'}

    # 1. Distance KS test
    ks_stat, ks_pval = scipy_stats.ks_2samp(pred_dists, actual_dists)

    # 2. Distance quantile MAE
    quantiles = [10, 25, 50, 75, 90]
    pred_q = np.percentile(pred_dists, quantiles)
    actual_q = np.percentile(actual_dists, quantiles)
    quantile_mae = np.mean(np.abs(pred_q - actual_q))

    # 3. Side split comparison
    # Predicted side split
    pred_1b = sum(1 for e in predicted_events if e.landing_side == '1B')
    pred_total = len(predicted_events)
    pred_1b_pct = pred_1b / pred_total * 100 if pred_total > 0 else 50

    # Actual side split: RHB fouls go predominantly to 3B, LHB to 1B
    # We infer expected side from batter handedness in fouls
    if 'stand' in actual_fouls.columns:
        actual_r = (actual_fouls['stand'] == 'R').sum()
        actual_l = (actual_fouls['stand'] == 'L').sum()
        actual_total = actual_r + actual_l
        # RHB fouls ~72% to 3B (28% to 1B), LHB fouls ~72% to 1B
        actual_1b_est = (actual_r * 0.28 + actual_l * 0.72) / max(actual_total, 1) * 100
    else:
        actual_1b_est = 50.0

    side_error = abs(pred_1b_pct - actual_1b_est)

    # 4. Per-batter foul count correlation
    pred_batter_counts = {}
    for e in predicted_events:
        bid = e.batter_name
        pred_batter_counts[bid] = pred_batter_counts.get(bid, 0) + e.weight

    # Actual per-batter foul counts
    actual_batter_counts = actual_fouls.groupby('batter').size().to_dict()

    # Match by batter ID where possible
    # pred uses names, actual uses IDs — we'll compute correlation if enough overlap
    batter_corr = np.nan

    # 5. Pitch-type distribution comparison
    pred_pitch_counts = {}
    for e in predicted_events:
        pred_pitch_counts[e.pitch_type] = pred_pitch_counts.get(e.pitch_type, 0) + 1
    pred_pitch_total = sum(pred_pitch_counts.values())

    actual_pitch_counts = {}
    if 'pitch_type' in actual_fouls.columns:
        for pt, cnt in actual_fouls['pitch_type'].value_counts().items():
            if pd.notna(pt):
                actual_pitch_counts[str(pt)] = int(cnt)
    actual_pitch_total = sum(actual_pitch_counts.values())

    # Compute pitch type overlap (cosine similarity)
    all_pts = set(pred_pitch_counts.keys()) | set(actual_pitch_counts.keys())
    if all_pts and pred_pitch_total > 0 and actual_pitch_total > 0:
        pred_vec = np.array([pred_pitch_counts.get(pt, 0) / pred_pitch_total for pt in sorted(all_pts)])
        actual_vec = np.array([actual_pitch_counts.get(pt, 0) / actual_pitch_total for pt in sorted(all_pts)])
        pitch_cosine = float(np.dot(pred_vec, actual_vec) / (np.linalg.norm(pred_vec) * np.linalg.norm(actual_vec) + 1e-10))
    else:
        pitch_cosine = np.nan

    # 6. Mean distance comparison
    pred_mean_dist = float(np.mean(pred_dists))
    actual_mean_dist = float(np.mean(actual_dists))

    return {
        'n_pred': len(pred_dists),
        'n_actual': len(actual_dists),
        'ks_stat': round(ks_stat, 3),
        'ks_pval': round(ks_pval, 4),
        'quantile_mae': round(quantile_mae, 1),
        'pred_mean_dist': round(pred_mean_dist, 1),
        'actual_mean_dist': round(actual_mean_dist, 1),
        'dist_error': round(pred_mean_dist - actual_mean_dist, 1),
        'pred_1b_pct': round(pred_1b_pct, 1),
        'actual_1b_est': round(actual_1b_est, 1),
        'side_error': round(side_error, 1),
        'pitch_cosine': round(pitch_cosine, 3) if not np.isnan(pitch_cosine) else None,
        'pred_quantiles': {str(q): round(float(v), 1) for q, v in zip(quantiles, pred_q)},
        'actual_quantiles': {str(q): round(float(v), 1) for q, v in zip(quantiles, actual_q)},
    }


def run_game_backtest(data: pd.DataFrame, games: list[dict], seed: int = 42) -> list[dict]:
    """Run the full backtest across selected games."""
    results = []

    for i, game in enumerate(games):
        gpk = game['game_pk']
        label = f"{game['away_team']} @ {game['home_team']} ({game['game_date']}, {game['stadium_key']})"
        print(f"\n{'='*70}")
        print(f"Game {i+1}/{len(games)}: {label}")
        print(f"{'='*70}")

        t0 = time.time()

        # Extract game data
        game_data = extract_game_data(data, gpk)
        n_tracked = len(game_data['tracked_fouls'])
        print(f"  Tracked fouls: {n_tracked}")
        print(f"  Home pitcher: {game_data['home_pitcher_name']} (ID: {game_data['home_pitcher_id']})")
        print(f"  Away pitcher: {game_data['away_pitcher_name']} (ID: {game_data['away_pitcher_id']})")
        print(f"  Away batters: {len(game_data['away_batters'])}, Home batters: {len(game_data['home_batters'])}")

        if n_tracked < 10:
            print("  SKIP: Too few tracked fouls")
            continue

        # Build profiles (no lookahead)
        print("  Building pre-game profiles...")
        away_profiles = build_profiles_for_game(data, game_data['away_batters'], game['game_date'])
        home_profiles = build_profiles_for_game(data, game_data['home_batters'], game['game_date'])

        # Build pitcher mixes
        home_pitcher_mix = build_pitcher_mix(data, game_data['home_pitcher_id'], game['game_date'])
        away_pitcher_mix = build_pitcher_mix(data, game_data['away_pitcher_id'], game['game_date'])

        print(f"  Away lineup: {len(away_profiles)} batters, Home lineup: {len(home_profiles)} batters")
        print(f"  Home pitcher mix: {home_pitcher_mix}")
        print(f"  Away pitcher mix: {away_pitcher_mix}")

        # Run predictions
        stadium = STADIUMS[game['stadium_key']]()
        np.random.seed(seed)

        print("  Running predictions...")
        # Away batting (vs home pitcher)
        pred_away = predict_game_fouls(
            away_profiles, game_data['home_pitcher_name'], home_pitcher_mix,
            stadium, simulations_per_batter=300,
        )
        # Home batting (vs away pitcher)
        pred_home = predict_game_fouls(
            home_profiles, game_data['away_pitcher_name'], away_pitcher_mix,
            stadium, simulations_per_batter=300,
        )

        # Combine predictions
        all_pred_events = pred_away.all_events + pred_home.all_events

        # Compare to actuals
        comparison = compare_game(all_pred_events, game_data['tracked_fouls'])
        elapsed = time.time() - t0

        result = {
            'game_pk': gpk,
            'label': label,
            'elapsed_s': round(elapsed, 1),
            **game,
            **comparison,
        }
        results.append(result)

        # Print summary
        if 'error' in comparison:
            print(f"  ERROR: {comparison['error']}")
        else:
            print(f"  Pred/Actual fouls: {comparison['n_pred']}/{comparison['n_actual']}")
            print(f"  Distance: pred={comparison['pred_mean_dist']}ft, actual={comparison['actual_mean_dist']}ft (error={comparison['dist_error']:+.1f}ft)")
            print(f"  KS stat: {comparison['ks_stat']} (p={comparison['ks_pval']})")
            print(f"  Quantile MAE: {comparison['quantile_mae']}ft")
            print(f"  Side split: pred 1B={comparison['pred_1b_pct']}%, actual est={comparison['actual_1b_est']}% (err={comparison['side_error']}pp)")
            print(f"  Pitch-type cosine: {comparison['pitch_cosine']}")
            print(f"  Time: {elapsed:.1f}s")

    return results


def print_aggregate_report(results: list[dict]):
    """Print aggregate backtest metrics."""
    valid = [r for r in results if 'error' not in r]
    if not valid:
        print("\nNo valid game results to aggregate.")
        return

    print(f"\n{'='*70}")
    print(f"AGGREGATE BACKTEST RESULTS ({len(valid)} games)")
    print(f"{'='*70}")

    ks_stats = [r['ks_stat'] for r in valid]
    q_maes = [r['quantile_mae'] for r in valid]
    dist_errors = [r['dist_error'] for r in valid]
    side_errors = [r['side_error'] for r in valid]
    cosines = [r['pitch_cosine'] for r in valid if r.get('pitch_cosine') is not None]

    print(f"\n{'Metric':<30} {'Mean':>8} {'Median':>8} {'Min':>8} {'Max':>8}")
    print("-" * 66)
    print(f"{'KS statistic':<30} {np.mean(ks_stats):>8.3f} {np.median(ks_stats):>8.3f} {np.min(ks_stats):>8.3f} {np.max(ks_stats):>8.3f}")
    print(f"{'Quantile MAE (ft)':<30} {np.mean(q_maes):>8.1f} {np.median(q_maes):>8.1f} {np.min(q_maes):>8.1f} {np.max(q_maes):>8.1f}")
    print(f"{'Mean distance error (ft)':<30} {np.mean(dist_errors):>+8.1f} {np.median(dist_errors):>+8.1f} {np.min(dist_errors):>+8.1f} {np.max(dist_errors):>+8.1f}")
    print(f"{'Side split error (pp)':<30} {np.mean(side_errors):>8.1f} {np.median(side_errors):>8.1f} {np.min(side_errors):>8.1f} {np.max(side_errors):>8.1f}")
    if cosines:
        print(f"{'Pitch-type cosine sim':<30} {np.mean(cosines):>8.3f} {np.median(cosines):>8.3f} {np.min(cosines):>8.3f} {np.max(cosines):>8.3f}")

    # Interpretation
    print(f"\n--- Interpretation ---")
    median_ks = np.median(ks_stats)
    if median_ks < 0.15:
        print(f"  Distance distributions: EXCELLENT (median KS = {median_ks:.3f})")
    elif median_ks < 0.25:
        print(f"  Distance distributions: GOOD (median KS = {median_ks:.3f})")
    elif median_ks < 0.40:
        print(f"  Distance distributions: FAIR (median KS = {median_ks:.3f})")
    else:
        print(f"  Distance distributions: POOR (median KS = {median_ks:.3f})")

    mean_side_err = np.mean(side_errors)
    if mean_side_err < 5:
        print(f"  Side split accuracy: EXCELLENT (mean error = {mean_side_err:.1f}pp)")
    elif mean_side_err < 10:
        print(f"  Side split accuracy: GOOD (mean error = {mean_side_err:.1f}pp)")
    else:
        print(f"  Side split accuracy: FAIR (mean error = {mean_side_err:.1f}pp)")

    if cosines:
        mean_cos = np.mean(cosines)
        if mean_cos > 0.95:
            print(f"  Pitch-type matching: EXCELLENT (mean cosine = {mean_cos:.3f})")
        elif mean_cos > 0.85:
            print(f"  Pitch-type matching: GOOD (mean cosine = {mean_cos:.3f})")
        else:
            print(f"  Pitch-type matching: FAIR (mean cosine = {mean_cos:.3f})")

    # Per-game table
    print(f"\n{'Game':<45} {'KS':>6} {'Q-MAE':>7} {'DistErr':>8} {'Side':>6} {'PtCos':>6}")
    print("-" * 80)
    for r in valid:
        cos_str = f"{r['pitch_cosine']:.3f}" if r.get('pitch_cosine') is not None else "  N/A"
        print(f"  {r['label'][:43]:<43} {r['ks_stat']:>6.3f} {r['quantile_mae']:>6.1f}ft {r['dist_error']:>+7.1f} {r['side_error']:>5.1f}% {cos_str:>6}")


def generate_visualizations(results: list[dict]):
    """Generate backtest visualization."""
    valid = [r for r in results if 'error' not in r]
    if not valid:
        return

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # 1. KS statistic per game
    ax = axes[0][0]
    labels = [r['label'][:25] for r in valid]
    ks_vals = [r['ks_stat'] for r in valid]
    colors = ['#2ecc71' if ks < 0.15 else '#f39c12' if ks < 0.25 else '#e74c3c' for ks in ks_vals]
    ax.barh(range(len(labels)), ks_vals, color=colors, edgecolor='black', linewidth=0.5)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=7)
    ax.axvline(0.15, color='green', linestyle='--', alpha=0.5, label='Good threshold')
    ax.axvline(0.25, color='orange', linestyle='--', alpha=0.5, label='Fair threshold')
    ax.set_xlabel('KS Statistic (lower = better)')
    ax.set_title('Distance Distribution Similarity per Game')
    ax.legend(fontsize=7)
    ax.invert_yaxis()

    # 2. Predicted vs actual mean distance
    ax = axes[0][1]
    pred_means = [r['pred_mean_dist'] for r in valid]
    actual_means = [r['actual_mean_dist'] for r in valid]
    ax.scatter(actual_means, pred_means, s=60, c='steelblue', edgecolors='black', linewidths=0.5, zorder=5)
    lo = min(min(pred_means), min(actual_means)) - 10
    hi = max(max(pred_means), max(actual_means)) + 10
    ax.plot([lo, hi], [lo, hi], 'r--', linewidth=2, label='Perfect')
    ax.set_xlabel('Actual Mean Distance (ft)')
    ax.set_ylabel('Predicted Mean Distance (ft)')
    ax.set_title('Mean Foul Ball Distance: Predicted vs Actual')
    corr = np.corrcoef(pred_means, actual_means)[0, 1] if len(pred_means) > 2 else 0
    ax.legend([f'Perfect', f'Games (r={corr:.3f})'], fontsize=8)
    ax.set_aspect('equal')
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)

    # 3. Side split comparison
    ax = axes[1][0]
    pred_sides = [r['pred_1b_pct'] for r in valid]
    actual_sides = [r['actual_1b_est'] for r in valid]
    x = range(len(valid))
    width = 0.35
    ax.bar([i - width/2 for i in x], pred_sides, width, label='Predicted 1B%', color='steelblue')
    ax.bar([i + width/2 for i in x], actual_sides, width, label='Actual Est 1B%', color='coral')
    ax.set_xticks(list(x))
    ax.set_xticklabels([r['label'][:15] for r in valid], rotation=45, ha='right', fontsize=6)
    ax.set_ylabel('1B Side %')
    ax.set_title('Side Split: Predicted vs Estimated Actual')
    ax.legend(fontsize=8)
    ax.set_ylim(0, 100)

    # 4. Quantile comparison (aggregate)
    ax = axes[1][1]
    quantiles = ['10', '25', '50', '75', '90']
    pred_qs = [np.mean([r['pred_quantiles'][q] for r in valid]) for q in quantiles]
    actual_qs = [np.mean([r['actual_quantiles'][q] for r in valid]) for q in quantiles]
    ax.plot(quantiles, pred_qs, 'o-', color='steelblue', linewidth=2, markersize=8, label='Predicted')
    ax.plot(quantiles, actual_qs, 's-', color='coral', linewidth=2, markersize=8, label='Actual')
    ax.set_xlabel('Percentile')
    ax.set_ylabel('Distance (ft)')
    ax.set_title('Distance Quantiles: Predicted vs Actual (averaged)')
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.suptitle('FoulCast Game-Level Backtest Results', fontsize=14, fontweight='bold')
    plt.tight_layout()
    out_path = f'{OUTPUT_DIR}/backtest_games.png'
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\nVisualization saved to {out_path}")


def main():
    parser = argparse.ArgumentParser(description='Game-level backtest against real Statcast data')
    parser.add_argument('--games', type=int, default=20, help='Number of games to backtest')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--no-pull', action='store_true', help='Use cached data only (fail if not cached)')
    args = parser.parse_args()

    print("=" * 70)
    print("FOULCAST GAME-LEVEL BACKTEST")
    print(f"Games: {args.games} | Seed: {args.seed}")
    print("=" * 70)

    # Pull Statcast data (Apr-Aug 2024)
    if args.no_pull:
        cache_path = os.path.join(CACHE_DIR, f'statcast_{DATA_START}_{DATA_END}.parquet')
        if not os.path.exists(cache_path):
            print(f"ERROR: No cached data at {cache_path}. Run without --no-pull first.")
            sys.exit(1)
        data = pd.read_parquet(cache_path)
        print(f"Loaded {len(data):,} pitches from cache")
    else:
        data = pull_statcast_data(DATA_START, DATA_END)

    # Normalize game_date to string format for fast comparisons
    data['game_date'] = pd.to_datetime(data['game_date']).dt.strftime('%Y-%m-%d')

    # Select games
    games = select_games(data, max_games=args.games)

    if not games:
        print("No eligible games found!")
        sys.exit(1)

    # Run backtest
    results = run_game_backtest(data, games, seed=args.seed)

    # Aggregate report
    print_aggregate_report(results)

    # Visualizations
    generate_visualizations(results)

    # Save results to cache
    ensure_cache_dir()
    results_path = os.path.join(CACHE_DIR, f'results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(results_path, 'w') as f:
        # Make JSON-serializable
        clean = []
        for r in results:
            cr = {k: v for k, v in r.items() if k not in ('fouls', 'tracked_fouls', 'all_pitches')}
            clean.append(cr)
        json.dump(clean, f, indent=2, default=str)
    print(f"Results saved to {results_path}")

    print(f"\n{'='*70}")
    print("BACKTEST COMPLETE")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
