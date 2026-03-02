"""
Live Batter Profile Builder.

Pulls real Statcast data for specific players and builds accurate
foul ball profiles. Caches results to avoid repeated API calls.
"""
import os
import json
import hashlib
import numpy as np
import pandas as pd
from datetime import datetime
from pybaseball import statcast
from .batter_profiles import BatterFoulProfile, build_profile_from_data, PITCHER_PROFILES, _safe_mode
from .log import get_logger
import warnings
# Suppress only known-noisy pandas/pybaseball warnings, not all warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='pybaseball')
warnings.filterwarnings('ignore', message='.*SettingWithCopyWarning.*')

logger = get_logger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.cache')


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_key(player_ids: list[int], start_date: str, end_date: str) -> str:
    key = f"{sorted(player_ids)}_{start_date}_{end_date}"
    return hashlib.md5(key.encode()).hexdigest()


def _save_cache(key: str, data: dict):
    _ensure_cache_dir()
    path = os.path.join(CACHE_DIR, f"{key}.json")
    serializable = {}
    for pid, profile in data.items():
        serializable[str(pid)] = {
            'player_name': profile.player_name,
            'player_id': profile.player_id,
            'batter_side': profile.batter_side,
            'total_fouls': profile.total_fouls,
            'fouls_with_tracking': profile.fouls_with_tracking,
            'ev_mean': profile.ev_mean, 'ev_std': profile.ev_std,
            'ev_25': profile.ev_25, 'ev_50': profile.ev_50, 'ev_75': profile.ev_75,
            'la_mean': profile.la_mean, 'la_std': profile.la_std,
            'la_25': profile.la_25, 'la_50': profile.la_50, 'la_75': profile.la_75,
            'foul_rates': profile.foul_rates,
            'foul_rates_kind': profile.foul_rates_kind,
            'bat_speed_mean': profile.bat_speed_mean, 'bat_speed_std': profile.bat_speed_std,
            'avg_plate_x_on_foul': profile.avg_plate_x_on_foul,
            'avg_plate_z_on_foul': profile.avg_plate_z_on_foul,
            'fair_pull_pct': profile.fair_pull_pct,
            'fouls_per_pa': profile.fouls_per_pa,
        }
    with open(path, 'w') as f:
        json.dump(serializable, f)


def _load_cache(key: str) -> dict[int, BatterFoulProfile] | None:
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        profiles = {}
        # Filter out keys that no longer exist on BatterFoulProfile
        valid_fields = {f.name for f in BatterFoulProfile.__dataclass_fields__.values()}
        for pid_str, d in data.items():
            filtered = {k: v for k, v in d.items() if k in valid_fields}
            profiles[int(pid_str)] = BatterFoulProfile(**filtered)
        return profiles
    except Exception as e:
        logger.warning("Cache load failed for %s: %s", key, e)
        return None


def pull_live_profiles(
    player_ids: list[int],
    player_names: dict[int, str] | None = None,
    player_sides: dict[int, str] | None = None,
    start_date: str = '2024-04-01',
    end_date: str = '2024-10-01',
    use_cache: bool = True,
) -> dict[int, BatterFoulProfile]:
    """
    Pull real Statcast data and build foul profiles for specific players.

    Args:
        player_ids: List of MLB player IDs
        player_names: Optional dict of id → name (for display)
        player_sides: Optional dict of id → batting side
        start_date: Start of data range
        end_date: End of data range
        use_cache: Whether to use cached results

    Returns:
        Dict of player_id → BatterFoulProfile
    """
    cache_key = _cache_key(player_ids, start_date, end_date)

    if use_cache:
        cached = _load_cache(cache_key)
        if cached:
            # Check if all requested players are in cache
            if all(pid in cached for pid in player_ids):
                logger.info("Loaded %d profiles from cache", len(player_ids))
                return {pid: cached[pid] for pid in player_ids}

    # Pull Statcast data in monthly chunks to avoid timeouts
    logger.info("Pulling Statcast data for %d players...", len(player_ids))
    all_data = []

    # Parse dates
    from datetime import datetime, timedelta
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')

    current = start
    while current < end:
        chunk_end = min(current + timedelta(days=30), end)
        start_str = current.strftime('%Y-%m-%d')
        end_str = chunk_end.strftime('%Y-%m-%d')
        logger.info("Pulling %s to %s...", start_str, end_str)

        try:
            chunk = statcast(start_dt=start_str, end_dt=end_str)
            if chunk is not None and len(chunk) > 0:
                # Filter to our players early to save memory
                chunk = chunk[chunk['batter'].isin(player_ids)]
                all_data.append(chunk)
        except Exception as e:
            logger.warning("Failed to pull %s-%s: %s", start_str, end_str, e)

        current = chunk_end + timedelta(days=1)

    if not all_data:
        logger.warning("No data pulled. Using league-average defaults.")
        return _default_profiles(player_ids, player_names, player_sides)

    data = pd.concat(all_data, ignore_index=True)
    logger.info("Total pitches for these players: %s", f"{len(data):,}")

    # Filter to foul balls, excluding foul tips (caught by catcher, never reach stands)
    foul_mask = data['description'].str.contains('foul', case=False, na=False)
    tip_mask = data['description'].str.contains('foul_tip|foul tip', case=False, na=False)
    fouls = data[foul_mask & ~tip_mask].copy()
    logger.info("Total foul events: %s", f"{len(fouls):,}")

    # Build profiles
    profiles = {}
    for pid in player_ids:
        player_fouls = fouls[fouls['batter'] == pid]

        if len(player_fouls) < 10:
            # Not enough data — use defaults with available info
            name = (player_names or {}).get(pid, f'Player {pid}')
            side = (player_sides or {}).get(pid, 'R')
            profiles[pid] = BatterFoulProfile(
                player_name=name, player_id=pid, batter_side=side,
            )
            logger.info("%s: only %d fouls, using defaults", name, len(player_fouls))
            continue

        # Statcast player_name is the PITCHER's name, not the batter's.
        # Use caller-provided name, or look up via statsapi.
        if player_names and pid in player_names:
            name = player_names[pid]
        else:
            try:
                import statsapi as _statsapi
                info = _statsapi.get('people', {'personIds': int(pid)})
                name = info['people'][0]['fullName']
            except Exception:
                name = f'Player {pid}'

        # Full pitch data for this batter (needed for P(foul|pitch_type) and fouls/PA)
        player_all_pitches = data[data['batter'] == pid]

        profile = build_profile_from_data(name, pid, player_fouls, all_pitches=player_all_pitches)

        # Override side if provided (handles switch hitters)
        if player_sides and pid in player_sides:
            profile.batter_side = player_sides[pid]

        # Compute real fouls per PA from full data (not just foul-filtered data)
        player_pas = player_all_pitches.groupby(['game_pk', 'at_bat_number']).ngroups
        if player_pas >= 20:
            profile.fouls_per_pa = round(len(player_fouls) / player_pas, 3)

        profiles[pid] = profile
        tracked = profile.fouls_with_tracking
        logger.info("%s: %d fouls, %d tracked, EV=%.1f, LA=%.1f, fouls/PA=%.2f",
                    profile.player_name, profile.total_fouls, tracked,
                    profile.ev_mean, profile.la_mean, profile.fouls_per_pa)

    # Enrich with per-batter spray angle data from spray_profiles.json
    profiles = enrich_with_spray_profiles(profiles)

    # Cache results
    if use_cache:
        _save_cache(cache_key, profiles)
        logger.info("Cached %d profiles", len(profiles))

    return profiles


def load_spray_profiles() -> dict[int, dict]:
    """Load cached spray profiles from .cache/spray_profiles.json."""
    path = os.path.join(CACHE_DIR, 'spray_profiles.json')
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        return {int(pid): profile for pid, profile in data.items()}
    except Exception as e:
        logger.warning("Failed to load spray profiles from %s: %s", path, e)
        return {}


def enrich_with_spray_profiles(profiles: dict[int, 'BatterFoulProfile']) -> dict[int, 'BatterFoulProfile']:
    """Enrich batter profiles with per-batter pull tendency from cache.

    spray_profiles.json contains fair_pull_pct computed from real Statcast
    hc_x/hc_y coordinates (Jun-Aug 2024). This is the primary input to
    the spray angle model — pull hitters foul more down the line, opposite-
    field hitters foul more behind the plate.
    """
    spray = load_spray_profiles()
    if not spray:
        return profiles

    enriched = 0
    for pid, prof in profiles.items():
        if pid in spray:
            sp = spray[pid]
            # Only use fair_pull_pct (computed from real hc_x/hc_y coordinates).
            # Do NOT use foul_spray_mean/std (those were computed from a
            # broken arccos(distance_ratio) back-solve and are invalid).
            prof.fair_pull_pct = sp.get('fair_pull_pct', prof.fair_pull_pct)
            # Real fouls per PA (computed from actual PA counts in rebuild_spray_profiles.py).
            # Only use cached value if NOT already computed from the live pull
            # (which may cover a different date range than the cache's Jun-Aug window).
            fpa = sp.get('fouls_per_pa', 0)
            if fpa > 0 and prof.fouls_per_pa <= 0:
                prof.fouls_per_pa = fpa
            # Per-batter exit velocity and launch angle from real Statcast foul data.
            # Overrides league-average defaults (76.0/23.0) with actual batter stats.
            if sp.get('ev_mean') is not None:
                prof.ev_mean = sp['ev_mean']
            if sp.get('ev_std') is not None:
                prof.ev_std = sp['ev_std']
            if sp.get('la_mean') is not None:
                prof.la_mean = sp['la_mean']
            if sp.get('la_std') is not None:
                prof.la_std = sp['la_std']
            enriched += 1

    return profiles


def _default_profiles(
    player_ids: list[int],
    player_names: dict[int, str] | None,
    player_sides: dict[int, str] | None,
) -> dict[int, BatterFoulProfile]:
    """Create default profiles when data isn't available."""
    profiles = {}
    for pid in player_ids:
        name = (player_names or {}).get(pid, f'Player {pid}')
        side = (player_sides or {}).get(pid, 'R')
        profiles[pid] = BatterFoulProfile(
            player_name=name, player_id=pid, batter_side=side,
        )
    return profiles


def build_pitcher_profile_from_statcast(
    pitcher_name: str,
    pitcher_id: int,
    start_date: str = '2024-04-01',
    end_date: str = '2024-10-01',
) -> dict:
    """
    Build a pitcher's pitch mix profile from Statcast data.
    Returns dict matching PITCHER_PROFILES format.
    """
    cache_key = f"pitcher_{pitcher_id}_{start_date}_{end_date}"
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.json")

    _ensure_cache_dir()
    if os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                return json.load(f)
        except Exception:
            pass

    logger.info("Pulling Statcast data for pitcher %s...", pitcher_name)
    from datetime import datetime as dt, timedelta
    all_data = []
    start = dt.strptime(start_date, '%Y-%m-%d')
    end = dt.strptime(end_date, '%Y-%m-%d')

    current = start
    while current < end:
        chunk_end = min(current + timedelta(days=30), end)
        try:
            chunk = statcast(
                start_dt=current.strftime('%Y-%m-%d'),
                end_dt=chunk_end.strftime('%Y-%m-%d'),
            )
            if chunk is not None and len(chunk) > 0:
                chunk = chunk[chunk['pitcher'] == pitcher_id]
                all_data.append(chunk)
        except Exception:
            pass
        current = chunk_end + timedelta(days=1)

    if not all_data:
        return {'hand': 'R', 'pitch_mix': {'FF': 0.35, 'SL': 0.20, 'CH': 0.15, 'SI': 0.15, 'CU': 0.15}, 'avg_velo': 93.0}

    data = pd.concat(all_data, ignore_index=True)

    # Build pitch mix
    pitch_counts = data['pitch_type'].value_counts(normalize=True)
    pitch_mix = {pt: round(pct, 3) for pt, pct in pitch_counts.items() if pct > 0.03}

    # Normalize
    total = sum(pitch_mix.values())
    pitch_mix = {k: round(v/total, 3) for k, v in pitch_mix.items()}

    # Get hand and velo
    hand = _safe_mode(data['p_throws'], 'R')
    avg_velo = data[data['pitch_type'] == 'FF']['release_speed'].mean()
    if pd.isna(avg_velo):
        avg_velo = data['release_speed'].mean()
    if pd.isna(avg_velo):
        avg_velo = 93.0

    result = {
        'hand': hand,
        'pitch_mix': pitch_mix,
        'avg_velo': round(float(avg_velo), 1),
    }

    # Cache
    with open(cache_path, 'w') as f:
        json.dump(result, f)

    logger.info("%s: %sHP, %.1f mph, mix: %s", pitcher_name, hand, avg_velo, pitch_mix)
    return result
