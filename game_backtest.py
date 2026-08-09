"""
GAME-LEVEL BACKTEST: Full pipeline predictions vs real Statcast game data.

Unlike backtest.py (which validates trajectory physics on individual fouls),
this tests the ENTIRE prediction pipeline: lineup → profile sampling →
trajectory → section mapping → aggregate metrics.

For each real game:
  1. Extract actual lineups + pitchers from Statcast
  2. Build batter profiles from data BEFORE the game (no lookahead)
  3. Run predict_game_fouls()
  4. Compare predicted vs actual: total foul count, distance distribution,
     per-batter foul count, pitch-type distribution

What can and cannot be validated here:

  CAN — total fouls per game. Statcast logs every foul, so the predicted total
  (sum of per-batter weights = fouls_per_pa x PA) has a real observed
  counterpart. This is the only external check on the volume model.

  CAN — per-batter foul counts, joined on MLB player ID.

  CAN — the distance distribution of tracked fouls, with the caveat that
  hit_distance_sc is itself partly a model output (AUDIT.md P3).

  CANNOT — which side (1B/3B/behind the plate) a foul landed on, and which
  section it reached. Statcast records neither. A side-split metric used to
  live here; it manufactured its "actual" value by assuming RHB fouls go 72%
  to 3B, which compared the model against an assumption rather than data.
  It has been deleted. Section-level accuracy needs hand-logged ground truth.

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

# Simulation settings. PLATE_APPEARANCES_PER_BATTER is the model's assumption
# about game length; it is passed to predict_game_fouls and also reported so a
# total-foul error can be attributed to it rather than to the foul rate.
SIMS_PER_BATTER = 300
PLATE_APPEARANCES_PER_BATTER = 4.0

# The model's own floor: matchup_engine drops any simulation landing under 5 ft
# as "didn't go anywhere meaningful", so it cannot produce a foul below this.
# Statcast can and does — 17% of tracked fouls carry hit_distance_sc <= 5 ft,
# and those rows have a mean launch angle of -36 degrees: balls chopped straight
# into the ground. Comparing the model against them scores it on a category it
# deliberately excludes, and inflated the mean distance error by ~28 ft.
# The floor is applied to BOTH sides or neither.
MIN_DISTANCE_FT = 5.0

# Statcast data range for backtest. Covers the 2025 season and 2026 to date, so
# the same cached pull also feeds rebuild_spray_profiles.py.
DATA_START = '2025-04-01'
DATA_END = '2026-08-08'
# Games are selected from July 2026; profiles are built from DATA_START to the
# day before each game, so there are 15 months of pre-game data and no lookahead.
GAME_MONTH_START = '2026-07-01'
GAME_MONTH_END = '2026-07-31'

# Columns actually used downstream. Statcast returns 119; keeping all of them
# makes a 1.4M-row pull cost several GB of RAM for no benefit.
KEEP_COLUMNS = [
    'game_pk', 'game_date', 'game_type', 'home_team', 'away_team',
    'inning_topbot', 'at_bat_number', 'batter', 'pitcher', 'player_name',
    'description', 'type', 'events', 'pitch_type', 'release_speed',
    'stand', 'p_throws', 'plate_x', 'plate_z', 'hc_x', 'hc_y',
    'launch_speed', 'launch_angle', 'hit_distance_sc', 'bat_speed',
]

# Map Statcast home_team abbreviations to our team IDs
# Statcast uses slightly different abbreviations than statsapi
_SC_ABBREV_MAP = {
    'ARI': 109, 'ATL': 144, 'BAL': 110, 'BOS': 111, 'CHC': 112,
    'CWS': 145, 'CIN': 113, 'CLE': 114, 'COL': 115, 'DET': 116,
    'HOU': 117, 'KC': 118, 'LAA': 108, 'LAD': 119, 'MIA': 146,
    'MIL': 158, 'MIN': 142, 'NYM': 121, 'NYY': 147, 'OAK': 133,
    'PHI': 143, 'PIT': 134, 'SD': 135, 'SF': 137, 'SEA': 136,
    'STL': 138, 'TB': 139, 'TEX': 140, 'TOR': 141, 'WSH': 120,
    # Statcast renamed two clubs. From 2025 the Athletics are 'ATH' (they
    # dropped the city when they left Oakland) and Arizona is 'AZ'. The old
    # codes are kept so pre-2025 pulls still map; an unmapped home team is
    # dropped silently by select_games, which would have removed every
    # Athletics and Diamondbacks home game from a 2025-26 backtest.
    'ATH': 133, 'AZ': 109,
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
                # Regular season only. A 2025-2026 window would otherwise pull
                # spring training and postseason, which do not belong in either
                # the game sample or the batter profiles.
                if 'game_type' in chunk.columns:
                    chunk = chunk[chunk['game_type'] == 'R']
                keep = [c for c in KEEP_COLUMNS if c in chunk.columns]
                chunk = chunk[keep]
                if len(chunk) > 0:
                    all_chunks.append(chunk)
                print(f"    Got {len(chunk):,} regular-season pitches")
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


def foul_flag(df: pd.DataFrame) -> pd.Series:
    """Boolean mask of fouls, excluding foul tips (caught by the catcher).

    Uses the precomputed `is_foul` column when present. Over a 1.4M-row pull the
    str.contains pair costs a couple of seconds, and build_profiles_for_game
    would otherwise redo it once per lineup.
    """
    if 'is_foul' in df.columns:
        return df['is_foul']
    desc = df['description']
    return (desc.str.contains('foul', case=False, na=False) &
            ~desc.str.contains('foul_tip|foul tip', case=False, na=False))


def add_foul_flag(data: pd.DataFrame) -> pd.DataFrame:
    """Compute the foul mask once for the whole dataset."""
    if 'is_foul' not in data.columns:
        data['is_foul'] = foul_flag(data)
    return data


def neutral_site_game_pks(start: str, end: str) -> set[int]:
    """game_pks played somewhere other than the home team's usual park.

    MLB schedules a handful of these every year — Mexico City, the Little
    League Classic, Field of Dreams — and Statcast still labels one club as the
    home team. Simulating them against that club's home geometry would be
    plainly wrong, so they are dropped from the sample.

    Detected by comparing each game's venue against the home team's modal venue
    for the season, which is robust to sponsorship renames (the Dodgers' park
    is listed as "UNIQLO Field at Dodger Stadium" in 2026).
    """
    try:
        import statsapi as _statsapi
        games = _statsapi.schedule(start_date=start, end_date=end)
    except Exception as exc:
        print(f"  WARNING: could not check for neutral-site games ({exc}); keeping all")
        return set()

    from collections import Counter, defaultdict
    by_team: dict[int, Counter] = defaultdict(Counter)
    rows = []
    for g in games:
        if g.get('game_type') != 'R':
            continue
        venue = g.get('venue_name', '?')
        by_team[g['home_id']][venue] += 1
        rows.append((g['game_id'], g['home_id'], venue))

    home_venue = {tid: c.most_common(1)[0][0] for tid, c in by_team.items()}
    return {gpk for gpk, tid, venue in rows if venue != home_venue.get(tid)}


def select_games(data: pd.DataFrame, max_games: int = 20) -> list[dict]:
    """Select diverse games from Statcast data for backtesting."""
    # Filter to the game-selection month
    month_data = data[
        (data['game_date'] >= GAME_MONTH_START) &
        (data['game_date'] <= GAME_MONTH_END)
    ]
    fouls = month_data[foul_flag(month_data)]
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

    neutral = neutral_site_game_pks(GAME_MONTH_START, GAME_MONTH_END)
    dropped_neutral = [g for g in eligible_games if int(g) in neutral]
    if dropped_neutral:
        print(f"Dropping {len(dropped_neutral)} neutral-site game(s): {dropped_neutral}")
    eligible_games = [g for g in eligible_games if int(g) not in neutral]

    unmapped = set()

    # Get game metadata
    games = []
    for gpk in eligible_games:
        game_pitches = month_data[month_data['game_pk'] == gpk]
        game_date = str(game_pitches['game_date'].iloc[0])
        home_team = game_pitches['home_team'].iloc[0]
        away_team = game_pitches['away_team'].iloc[0]

        home_id = _SC_ABBREV_MAP.get(home_team)
        away_id = _SC_ABBREV_MAP.get(away_team)
        if home_id is None or away_id is None:
            # Loudly, not silently: an abbreviation change (OAK -> ATH in 2025)
            # would otherwise quietly delete a club from every backtest.
            unmapped.update(t for t in (home_team, away_team)
                            if t not in _SC_ABBREV_MAP)
            continue

        stadium_key = TEAM_STADIUM_MAP.get(home_id)
        if stadium_key is None or stadium_key not in STADIUMS:
            unmapped.add(f'{home_team} (no stadium geometry)')
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

    if unmapped:
        print(f"WARNING: dropped games for unmapped teams: {sorted(unmapped)}")

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
    fouls = game[foul_flag(game)].copy()
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


_BATTER_NAME_CACHE: dict[int, str] = {}


def lookup_batter_name(bid: int) -> str:
    """Resolve a batter's name via statsapi, once per player per run.

    Statcast's `player_name` is the PITCHER's name, so batters have to be looked
    up. The same nine batters recur across games, and this is a network call.
    """
    bid = int(bid)
    if bid not in _BATTER_NAME_CACHE:
        try:
            import statsapi as _statsapi
            info = _statsapi.get('people', {'personIds': bid})
            _BATTER_NAME_CACHE[bid] = info['people'][0]['fullName']
        except Exception:
            _BATTER_NAME_CACHE[bid] = f'Player {bid}'
    return _BATTER_NAME_CACHE[bid]


def build_profiles_for_game(
    data: pd.DataFrame,
    batter_ids: list[int],
    game_date: str,
) -> list[BatterFoulProfile]:
    """Build batter profiles from data BEFORE the game date (no lookahead)."""
    cutoff = (pd.to_datetime(game_date) - timedelta(days=1)).strftime('%Y-%m-%d')
    # Read-only slice — no .copy(), which on a 1.4M-row pull duplicates a few
    # hundred MB once per lineup for nothing.
    pre_game = data[data['game_date'] <= cutoff]
    all_fouls = pre_game[foul_flag(pre_game)]

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

        name = lookup_batter_name(bid)

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


def safe_pearson(x, y) -> float | None:
    """Pearson r, or None when it is undefined (too few points, no variance)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 3 or len(x) != len(y):
        return None
    if np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(scipy_stats.pearsonr(x, y)[0])


def compare_game(
    predicted_events,
    tracked_fouls: pd.DataFrame,
    all_fouls: pd.DataFrame,
    lineup_batter_ids: list[int],
    plate_appearances: int | None = None,
    predicted_pa: float = 72.0,
) -> dict:
    """Compare predicted vs actual foul balls for one game.

    Two different actual-foul frames are needed and they are not
    interchangeable:

      `tracked_fouls` — fouls with launch_speed/launch_angle/hit_distance_sc.
      Only these have distances, so they drive the distance metrics. They are
      a biased subset: tracking is worst on exactly the weak contact that
      disappears into the backstop.

      `all_fouls` — every foul in the game bar foul tips. Counting metrics
      (game total, per-batter, pitch type) use these, because that is the same
      population `fouls_per_pa` was built from, so the comparison is like for
      like.

    `predicted_pa` is what the prediction assumed (9 batters x 4.0 PA x 2
    lineups), reported alongside the real PA count so a total-foul miss can be
    split into "wrong fouls per PA" and "wrong number of PAs".
    """
    # Predicted distances
    pred_dists = np.array([e.landing_distance for e in predicted_events])

    # Actual distances (tracked fouls only)
    actual_tracked = tracked_fouls[tracked_fouls['hit_distance_sc'].notna()]
    actual_dists_raw = actual_tracked['hit_distance_sc'].values.astype(float)

    # Same floor on both sides — see MIN_DISTANCE_FT.
    n_actual_below_floor = int((actual_dists_raw <= MIN_DISTANCE_FT).sum())
    actual_dists = actual_dists_raw[actual_dists_raw > MIN_DISTANCE_FT]
    pred_dists = pred_dists[pred_dists > MIN_DISTANCE_FT]

    if len(pred_dists) < 10 or len(actual_dists) < 10:
        return {'error': 'Too few fouls for comparison'}

    # 1. Total fouls per game — the volume-model check.
    # Each simulated event carries weight = fouls_per_pa * PA / sims, so the
    # weighted sum is the model's estimate of how many fouls this game
    # produces. Statcast logs every one of them, so this has a real
    # counterpart, unlike anything about where the ball came down.
    pred_total_fouls = float(sum(e.weight for e in predicted_events))
    actual_total_fouls = int(len(all_fouls))
    total_foul_error = pred_total_fouls - actual_total_fouls

    # How many of those the model thinks reach a modelled seating zone. There
    # is no Statcast counterpart — reported as a diagnostic, NOT validated.
    pred_fouls_into_stands = float(
        sum(e.weight for e in predicted_events if e.section is not None)
    )

    actual_pa = int(plate_appearances) if plate_appearances else None
    actual_per_pa = (actual_total_fouls / actual_pa) if actual_pa else None
    pred_per_pa = pred_total_fouls / predicted_pa if predicted_pa else None

    # 2. Distance KS test
    ks_stat, ks_pval = scipy_stats.ks_2samp(pred_dists, actual_dists)

    # 3. Distance quantile MAE
    quantiles = [10, 25, 50, 75, 90]
    pred_q = np.percentile(pred_dists, quantiles)
    actual_q = np.percentile(actual_dists, quantiles)
    quantile_mae = np.mean(np.abs(pred_q - actual_q))

    # 4. Per-batter foul counts, joined on MLB player ID.
    pred_batter_counts: dict[int, float] = {}
    for e in predicted_events:
        bid = getattr(e, 'batter_id', None)
        if bid is None:
            continue
        pred_batter_counts[int(bid)] = pred_batter_counts.get(int(bid), 0.0) + e.weight

    actual_batter_counts = {
        int(bid): int(n) for bid, n in all_fouls.groupby('batter').size().items()
    }

    # Score every batter the model was asked to predict, including any that
    # drew no fouls at all — dropping the zeros would flatter the correlation.
    pairs = [
        (int(bid),
         round(pred_batter_counts.get(int(bid), 0.0), 3),
         actual_batter_counts.get(int(bid), 0))
        for bid in dict.fromkeys(int(b) for b in lineup_batter_ids)
    ]
    batter_corr = safe_pearson([p for _, p, _ in pairs], [a for _, _, a in pairs])
    batter_mae = (
        float(np.mean([abs(p - a) for _, p, a in pairs])) if pairs else None
    )
    # Fouls hit by batters outside the predicted lineups (pinch hitters, and
    # anyone past the ninth distinct batter of a half-inning) are fouls the
    # model never had a chance at. Track the share it could see.
    matched_actual = sum(a for _, _, a in pairs)
    batter_coverage = (
        matched_actual / actual_total_fouls if actual_total_fouls else None
    )

    # 5. Pitch-type distribution comparison (all fouls, not just tracked)
    pred_pitch_counts = {}
    for e in predicted_events:
        pred_pitch_counts[e.pitch_type] = pred_pitch_counts.get(e.pitch_type, 0) + 1
    pred_pitch_total = sum(pred_pitch_counts.values())

    actual_pitch_counts = {}
    if 'pitch_type' in all_fouls.columns:
        for pt, cnt in all_fouls['pitch_type'].value_counts().items():
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
        'n_sim_events': len(pred_dists),
        'n_actual_tracked': len(actual_dists),
        'n_actual_below_floor': n_actual_below_floor,
        'pred_total_fouls': round(pred_total_fouls, 1),
        'actual_total_fouls': actual_total_fouls,
        'total_foul_error': round(total_foul_error, 1),
        'pred_fouls_into_stands': round(pred_fouls_into_stands, 1),
        'actual_pa': actual_pa,
        'predicted_pa': predicted_pa,
        'pred_fouls_per_pa': round(pred_per_pa, 3) if pred_per_pa is not None else None,
        'actual_fouls_per_pa': round(actual_per_pa, 3) if actual_per_pa is not None else None,
        'ks_stat': round(ks_stat, 3),
        'ks_pval': round(ks_pval, 4),
        'quantile_mae': round(quantile_mae, 1),
        'pred_mean_dist': round(pred_mean_dist, 1),
        'actual_mean_dist': round(actual_mean_dist, 1),
        'dist_error': round(pred_mean_dist - actual_mean_dist, 1),
        'batter_corr': round(batter_corr, 3) if batter_corr is not None else None,
        'batter_mae': round(batter_mae, 2) if batter_mae is not None else None,
        'batter_n': len(pairs),
        'batter_coverage': round(batter_coverage, 3) if batter_coverage is not None else None,
        'batter_pairs': [[bid, p, a] for bid, p, a in pairs],
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
            stadium, simulations_per_batter=SIMS_PER_BATTER,
            plate_appearances_per_batter=PLATE_APPEARANCES_PER_BATTER,
        )
        # Home batting (vs away pitcher)
        pred_home = predict_game_fouls(
            home_profiles, game_data['away_pitcher_name'], away_pitcher_mix,
            stadium, simulations_per_batter=SIMS_PER_BATTER,
            plate_appearances_per_batter=PLATE_APPEARANCES_PER_BATTER,
        )

        # Combine predictions. predict_game_fouls() takes one lineup, which is
        # half a game; summing both halves is what a game is.
        all_pred_events = pred_away.all_events + pred_home.all_events

        # Real plate appearances in the game, for splitting a total-foul miss
        # into rate error vs PA error. at_bat_number is unique within a game.
        actual_pa = int(game_data['all_pitches']['at_bat_number'].nunique())
        predicted_pa = (len(away_profiles) + len(home_profiles)) * PLATE_APPEARANCES_PER_BATTER

        # Compare to actuals
        comparison = compare_game(
            all_pred_events,
            game_data['tracked_fouls'],
            game_data['fouls'],
            game_data['away_batters'] + game_data['home_batters'],
            plate_appearances=actual_pa,
            predicted_pa=predicted_pa,
        )
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
            print(f"  Total fouls: pred={comparison['pred_total_fouls']}, actual={comparison['actual_total_fouls']} "
                  f"(error={comparison['total_foul_error']:+.1f})")
            print(f"    fouls/PA: pred={comparison['pred_fouls_per_pa']} over {comparison['predicted_pa']:.0f} assumed PA, "
                  f"actual={comparison['actual_fouls_per_pa']} over {comparison['actual_pa']} real PA")
            print(f"    of which predicted to reach a modelled zone: {comparison['pred_fouls_into_stands']} (no Statcast counterpart)")
            corr_str = comparison['batter_corr'] if comparison['batter_corr'] is not None else 'n/a'
            cov = comparison['batter_coverage']
            cov_str = f", lineup covers {cov:.0%} of actual fouls" if cov is not None else ""
            print(f"  Per-batter fouls: r={corr_str} over {comparison['batter_n']} batters, "
                  f"MAE={comparison['batter_mae']}{cov_str}")
            print(f"  Distance ({comparison['n_sim_events']} sim events vs {comparison['n_actual_tracked']} tracked, "
                  f"{comparison['n_actual_below_floor']} actual below the {MIN_DISTANCE_FT:.0f}ft floor excluded): "
                  f"pred={comparison['pred_mean_dist']}ft, actual={comparison['actual_mean_dist']}ft (error={comparison['dist_error']:+.1f}ft)")
            print(f"  KS stat: {comparison['ks_stat']} (p={comparison['ks_pval']})")
            print(f"  Quantile MAE: {comparison['quantile_mae']}ft")
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
    cosines = [r['pitch_cosine'] for r in valid if r.get('pitch_cosine') is not None]

    pred_totals = [r['pred_total_fouls'] for r in valid]
    actual_totals = [r['actual_total_fouls'] for r in valid]
    total_errors = [r['total_foul_error'] for r in valid]
    total_abs_errors = [abs(e) for e in total_errors]
    total_corr = safe_pearson(pred_totals, actual_totals)
    total_mae = float(np.mean(total_abs_errors))

    # Per-batter pairs pooled across every game. A single game gives 18 points
    # with counts of 0-6 each, which is mostly Poisson noise; pooling is the
    # only way to see whether the per-batter rates carry signal.
    pooled_pred, pooled_actual = [], []
    for r in valid:
        for _, p, a in r.get('batter_pairs', []):
            pooled_pred.append(p)
            pooled_actual.append(a)
    pooled_batter_corr = safe_pearson(pooled_pred, pooled_actual)
    pooled_batter_mae = (
        float(np.mean([abs(p - a) for p, a in zip(pooled_pred, pooled_actual)]))
        if pooled_pred else None
    )
    per_game_batter_corrs = [r['batter_corr'] for r in valid if r.get('batter_corr') is not None]

    # --- The headline check: total fouls per game -------------------------
    print(f"\n--- TOTAL FOULS PER GAME (the volume model) ---")
    print(f"  Games:                    {len(valid)}")
    print(f"  Predicted, mean:          {np.mean(pred_totals):.1f}  (range {np.min(pred_totals):.1f}-{np.max(pred_totals):.1f})")
    print(f"  Actual, mean:             {np.mean(actual_totals):.1f}  (range {np.min(actual_totals)}-{np.max(actual_totals)})")
    print(f"  Correlation (Pearson r):  {total_corr:.3f}" if total_corr is not None
          else "  Correlation (Pearson r):  n/a (needs 3+ games with variation)")
    print(f"  Mean absolute error:      {total_mae:.1f} fouls/game")
    print(f"  Median absolute error:    {np.median(total_abs_errors):.1f} fouls/game")
    print(f"  Mean bias (pred-actual):  {np.mean(total_errors):+.1f} fouls/game")
    pa_rows = [r for r in valid if r.get('actual_pa')]
    if pa_rows:
        print(f"  Assumed PA vs real PA:    {np.mean([r['predicted_pa'] for r in pa_rows]):.0f} vs "
              f"{np.mean([r['actual_pa'] for r in pa_rows]):.1f}")
        print(f"  Fouls/PA, pred vs actual: {np.mean([r['pred_fouls_per_pa'] for r in pa_rows]):.3f} vs "
              f"{np.mean([r['actual_fouls_per_pa'] for r in pa_rows]):.3f}")
    print(f"  Predicted into modelled zones: {np.mean([r['pred_fouls_into_stands'] for r in valid]):.1f}/game "
          f"— NOT validated, Statcast does not record whether a foul reached the seats")

    # --- Per-batter foul counts ------------------------------------------
    print(f"\n--- PER-BATTER FOUL COUNTS (joined on MLB player ID) ---")
    print(f"  Batter-games pooled:      {len(pooled_pred)}")
    if pooled_batter_corr is not None:
        print(f"  Pooled correlation:       {pooled_batter_corr:.3f}")
    else:
        print(f"  Pooled correlation:       n/a")
    if pooled_batter_mae is not None:
        print(f"  Pooled MAE:               {pooled_batter_mae:.2f} fouls/batter/game")
    if per_game_batter_corrs:
        print(f"  Per-game r, median:       {np.median(per_game_batter_corrs):.3f} "
              f"(range {np.min(per_game_batter_corrs):.3f}-{np.max(per_game_batter_corrs):.3f})")
    coverages = [r['batter_coverage'] for r in valid if r.get('batter_coverage') is not None]
    if coverages:
        print(f"  Lineup coverage:          {np.mean(coverages):.0%} of actual fouls came from predicted batters")

    # --- Distance and pitch mix ------------------------------------------
    below = sum(r.get('n_actual_below_floor', 0) for r in valid)
    kept = sum(r['n_actual_tracked'] for r in valid)
    print(f"\n--- DISTANCE ---")
    print(f"  Excluded {below} of {below + kept} tracked fouls ({below / max(below + kept, 1):.0%}) "
          f"under the {MIN_DISTANCE_FT:.0f}ft floor the model itself applies")
    print(f"\n{'Metric':<30} {'Mean':>8} {'Median':>8} {'Min':>8} {'Max':>8}")
    print("-" * 66)
    print(f"{'KS statistic':<30} {np.mean(ks_stats):>8.3f} {np.median(ks_stats):>8.3f} {np.min(ks_stats):>8.3f} {np.max(ks_stats):>8.3f}")
    print(f"{'Quantile MAE (ft)':<30} {np.mean(q_maes):>8.1f} {np.median(q_maes):>8.1f} {np.min(q_maes):>8.1f} {np.max(q_maes):>8.1f}")
    print(f"{'Mean distance error (ft)':<30} {np.mean(dist_errors):>+8.1f} {np.median(dist_errors):>+8.1f} {np.min(dist_errors):>+8.1f} {np.max(dist_errors):>+8.1f}")
    print(f"{'Total foul error (count)':<30} {np.mean(total_errors):>+8.1f} {np.median(total_errors):>+8.1f} {np.min(total_errors):>+8.1f} {np.max(total_errors):>+8.1f}")
    if cosines:
        print(f"{'Pitch-type cosine sim':<30} {np.mean(cosines):>8.3f} {np.median(cosines):>8.3f} {np.min(cosines):>8.3f} {np.max(cosines):>8.3f}")

    # Interpretation
    print(f"\n--- Interpretation ---")
    if total_corr is not None:
        if total_corr > 0.5:
            verdict = "the model tracks which games produce more fouls"
        elif total_corr > 0.2:
            verdict = "weak signal; the model barely distinguishes high- from low-foul games"
        else:
            verdict = "no signal; predicted totals do not track actual totals"
        print(f"  Total foul count: r = {total_corr:.3f}, MAE = {total_mae:.1f} fouls/game — {verdict}")
    else:
        print(f"  Total foul count: MAE = {total_mae:.1f} fouls/game "
              f"(correlation undefined — needs 3+ games with variation in both series)")

    median_ks = np.median(ks_stats)
    if median_ks < 0.15:
        print(f"  Distance distributions: EXCELLENT (median KS = {median_ks:.3f})")
    elif median_ks < 0.25:
        print(f"  Distance distributions: GOOD (median KS = {median_ks:.3f})")
    elif median_ks < 0.40:
        print(f"  Distance distributions: FAIR (median KS = {median_ks:.3f})")
    else:
        print(f"  Distance distributions: POOR (median KS = {median_ks:.3f})")

    if cosines:
        mean_cos = np.mean(cosines)
        if mean_cos > 0.95:
            print(f"  Pitch-type matching: EXCELLENT (mean cosine = {mean_cos:.3f})")
        elif mean_cos > 0.85:
            print(f"  Pitch-type matching: GOOD (mean cosine = {mean_cos:.3f})")
        else:
            print(f"  Pitch-type matching: FAIR (mean cosine = {mean_cos:.3f})")

    print(f"  NOT VALIDATED by any number above: which side a foul goes to, which")
    print(f"  section it lands in, and what share reaches the seats. Statcast does")
    print(f"  not record foul landing locations. That needs hand-logged ground truth.")

    # Per-game table
    print(f"\n{'Game':<45} {'Pred':>6} {'Actual':>7} {'Err':>6} {'KS':>6} {'Q-MAE':>7} {'DistErr':>8} {'PtCos':>6}")
    print("-" * 100)
    for r in valid:
        cos_str = f"{r['pitch_cosine']:.3f}" if r.get('pitch_cosine') is not None else "  N/A"
        print(f"  {r['label'][:43]:<43} {r['pred_total_fouls']:>6.1f} {r['actual_total_fouls']:>7} "
              f"{r['total_foul_error']:>+6.1f} {r['ks_stat']:>6.3f} {r['quantile_mae']:>6.1f}ft "
              f"{r['dist_error']:>+7.1f} {cos_str:>6}")


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
    # Label each artist where it is drawn — passing a bare list to legend()
    # binds labels in artist order, which had them the wrong way round.
    corr = safe_pearson(pred_means, actual_means)
    corr_txt = f"r={corr:.3f}" if corr is not None else "r=n/a"
    ax.scatter(actual_means, pred_means, s=60, c='steelblue', edgecolors='black',
               linewidths=0.5, zorder=5, label=f'Games ({corr_txt})')
    lo = min(min(pred_means), min(actual_means)) - 10
    hi = max(max(pred_means), max(actual_means)) + 10
    ax.plot([lo, hi], [lo, hi], 'r--', linewidth=2, label='Perfect')
    ax.set_xlabel('Actual Mean Distance (ft)')
    ax.set_ylabel('Predicted Mean Distance (ft)')
    ax.set_title('Mean Foul Ball Distance: Predicted vs Actual')
    ax.legend(fontsize=8)
    ax.set_aspect('equal')
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)

    # 3. Total fouls per game: predicted vs actual (the volume-model check)
    ax = axes[1][0]
    pred_totals = [r['pred_total_fouls'] for r in valid]
    actual_totals = [r['actual_total_fouls'] for r in valid]
    r_tot = safe_pearson(pred_totals, actual_totals)
    mae_tot = np.mean([abs(p - a) for p, a in zip(pred_totals, actual_totals)])
    r_txt = f"r={r_tot:.3f}" if r_tot is not None else "r=n/a"
    ax.scatter(actual_totals, pred_totals, s=60, c='seagreen', edgecolors='black',
               linewidths=0.5, zorder=5, label=f'Games ({r_txt}, MAE={mae_tot:.1f})')
    lo = min(min(pred_totals), min(actual_totals)) - 5
    hi = max(max(pred_totals), max(actual_totals)) + 5
    ax.plot([lo, hi], [lo, hi], 'r--', linewidth=2, label='Perfect')
    ax.set_xlabel('Actual Fouls in Game')
    ax.set_ylabel('Predicted Fouls in Game')
    ax.set_title('Total Fouls per Game: Predicted vs Actual')
    ax.legend(fontsize=8)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

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
    # Classify fouls once for the whole dataset rather than per lineup
    add_foul_flag(data)
    print(f"Foul balls in dataset: {int(data['is_foul'].sum()):,}")

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
