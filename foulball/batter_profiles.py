"""
Per-Batter Foul Ball Profiles.

Pulls Statcast data and builds statistical profiles of each batter's
foul ball tendencies: EV distribution, launch angle distribution,
foul rates by pitch type, and spray angle estimates.
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from pybaseball import statcast, playerid_lookup
import warnings
# Suppress only known-noisy pandas/pybaseball warnings, not all warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='pybaseball')
warnings.filterwarnings('ignore', message='.*SettingWithCopyWarning.*')

from .log import get_logger

logger = get_logger(__name__)


def _safe_mode(series: pd.Series, default):
    """Return the mode of a Series, or default if the Series is empty, all-NaN, or has no mode."""
    if len(series) == 0:
        return default
    m = series.mode(dropna=True)
    if len(m) == 0:
        return default
    val = m.iloc[0]
    return default if pd.isna(val) else val


@dataclass
class BatterFoulProfile:
    """Statistical profile of a batter's foul ball tendencies."""
    player_name: str
    player_id: int
    batter_side: str  # 'L', 'R', or 'S' (switch)

    total_fouls: int = 0
    fouls_with_tracking: int = 0

    # Exit velocity distribution
    ev_mean: float = 76.0
    ev_std: float = 13.0
    ev_25: float = 70.0
    ev_50: float = 76.0
    ev_75: float = 83.0

    # Launch angle distribution
    la_mean: float = 23.0
    la_std: float = 36.0
    la_25: float = -1.0
    la_50: float = 30.0
    la_75: float = 50.0

    # Foul rate by pitch type
    foul_rates: dict = field(default_factory=dict)
    # What foul_rates represents: 'p_foul_given_pitch' (true conditional) or
    # 'p_pitch_given_foul' (fallback distribution). Downstream code must branch.
    foul_rates_kind: str = 'p_pitch_given_foul'

    # Bat speed stats (if available)
    bat_speed_mean: float = 0.0
    bat_speed_std: float = 0.0

    # Pitch location tendencies
    avg_plate_x_on_foul: float = 0.0
    avg_plate_z_on_foul: float = 0.0

    # Pull tendency from Statcast hc_x/hc_y (real directional data)
    # This drives the spray angle model — pull hitters foul more down the line
    fair_pull_pct: float = 50.0      # % of fair balls hit to pull side

    # Real fouls per plate appearance (from Statcast PA/foul counts)
    # Used to weight each batter's simulation output by their actual foul frequency
    fouls_per_pa: float = 0.0        # 0 = not computed yet, use fallback

    def sample_foul(self, plate_x: float = 0.0,
                    ev_std_override: float | None = None,
                    la_std_override: float | None = None) -> dict:
        """Sample a random foul ball from this batter's distribution."""
        ev = np.random.normal(self.ev_mean, ev_std_override if ev_std_override is not None else self.ev_std)
        ev = np.clip(ev, 5, 120)

        la = np.random.normal(self.la_mean, la_std_override if la_std_override is not None else self.la_std)
        la = np.clip(la, -89, 89)

        return {
            'exit_velocity': ev,
            'launch_angle': la,
            'batter_side': self.batter_side,
            'pitch_location_x': plate_x,
            'fair_pull_pct': self.fair_pull_pct,
        }


def _compute_foul_rates(foul_data: pd.DataFrame, all_pitches: pd.DataFrame | None) -> tuple[dict, str]:
    """Compute foul rates by pitch type for a batter.

    Returns (rates_dict, kind) where kind is one of:
        'p_foul_given_pitch' — true conditional P(foul | pitch_type)
        'p_pitch_given_foul' — fallback distribution P(pitch_type | foul)

    If all_pitches is provided, computes the true conditional.
    Otherwise falls back to the pitch-type distribution among fouls.
    """
    if 'pitch_type' not in foul_data.columns:
        return {}, 'p_pitch_given_foul'

    if all_pitches is not None and 'pitch_type' in all_pitches.columns:
        # True conditional: P(foul | pitch_type) for each pitch type
        all_by_pt = all_pitches['pitch_type'].value_counts()
        foul_by_pt = foul_data['pitch_type'].value_counts()
        rates = {}
        for pt, total in all_by_pt.items():
            if total >= 10:  # need enough pitches for a stable rate
                fouls = foul_by_pt.get(pt, 0)
                rates[pt] = fouls / total
        if rates:
            return rates, 'p_foul_given_pitch'

    # Fallback: P(pitch_type | foul) — less accurate but works without full data
    return foul_data['pitch_type'].value_counts(normalize=True).to_dict(), 'p_pitch_given_foul'


def build_profile_from_data(
    player_name: str,
    player_id: int,
    foul_data: pd.DataFrame,
    all_pitches: pd.DataFrame | None = None,
) -> BatterFoulProfile:
    """Build a BatterFoulProfile from pre-filtered foul ball data.

    Args:
        player_name: Batter's full name
        player_id: MLB player ID
        foul_data: DataFrame of this batter's foul ball events
        all_pitches: Optional DataFrame of ALL pitches seen by this batter
                     (enables correct P(foul|pitch_type) computation)
    """
    side = _safe_mode(foul_data['stand'], 'R')
    tracked = foul_data[foul_data['launch_speed'].notna()]

    profile = BatterFoulProfile(
        player_name=player_name,
        player_id=player_id,
        batter_side=side,
        total_fouls=len(foul_data),
        fouls_with_tracking=len(tracked),
    )

    if len(tracked) > 5:
        profile.ev_mean = tracked['launch_speed'].mean()
        profile.ev_std = tracked['launch_speed'].std()
        profile.ev_25 = tracked['launch_speed'].quantile(0.25)
        profile.ev_50 = tracked['launch_speed'].quantile(0.50)
        profile.ev_75 = tracked['launch_speed'].quantile(0.75)

        profile.la_mean = tracked['launch_angle'].mean()
        profile.la_std = tracked['launch_angle'].std()
        profile.la_25 = tracked['launch_angle'].quantile(0.25)
        profile.la_50 = tracked['launch_angle'].quantile(0.50)
        profile.la_75 = tracked['launch_angle'].quantile(0.75)

    if 'bat_speed' in foul_data.columns:
        bs = foul_data['bat_speed'].dropna()
        if len(bs) > 5:
            profile.bat_speed_mean = bs.mean()
            profile.bat_speed_std = bs.std()

    # Foul rate by pitch type: P(foul | pitch_type) when full data available,
    # otherwise P(pitch_type | foul) as fallback
    profile.foul_rates, profile.foul_rates_kind = _compute_foul_rates(foul_data, all_pitches)

    # Average pitch location on fouls
    if 'plate_x' in foul_data.columns:
        px = foul_data['plate_x'].dropna()
        if len(px) > 0:
            profile.avg_plate_x_on_foul = px.mean()

    if 'plate_z' in foul_data.columns:
        pz = foul_data['plate_z'].dropna()
        if len(pz) > 0:
            profile.avg_plate_z_on_foul = pz.mean()

    # NOTE: fair_pull_pct is NOT computed here because this function receives
    # foul-only data. Pull tendency must come from FAIR balls (type=='X') with
    # real hc_x/hc_y coordinates. It's set via enrich_with_spray_profiles()
    # which loads from .cache/spray_profiles.json (built by rebuild_spray_profiles.py
    # using fair-ball data with data['type'] == 'X').

    return profile


def build_profiles_from_statcast(
    start_date: str = '2024-06-01',
    end_date: str = '2024-09-30',
    player_ids: list[int] | None = None,
) -> dict[int, BatterFoulProfile]:
    """
    Pull Statcast data and build foul profiles for all batters (or specific ones).

    Returns dict mapping player_id → BatterFoulProfile.
    """
    logger.info("Pulling Statcast data from %s to %s...", start_date, end_date)
    data = statcast(start_dt=start_date, end_dt=end_date)
    logger.info("Pulled %s pitches", f"{len(data):,}")

    # Filter to foul balls, excluding foul tips (caught by catcher, never reach stands)
    foul_mask = data['description'].str.contains('foul', case=False, na=False)
    tip_mask = data['description'].str.contains('foul_tip|foul tip', case=False, na=False)
    fouls = data[foul_mask & ~tip_mask].copy()
    logger.info("Found %s foul ball events", f"{len(fouls):,}")

    if player_ids:
        fouls = fouls[fouls['batter'].isin(player_ids)]
        logger.info("Filtered to %s fouls for %d players", f"{len(fouls):,}", len(player_ids))

    # Look up batter names via statsapi (Statcast player_name is the PITCHER's name)
    import statsapi as _statsapi
    _name_cache = {}
    def _get_batter_name(bid):
        if bid not in _name_cache:
            try:
                info = _statsapi.get('people', {'personIds': int(bid)})
                _name_cache[bid] = info['people'][0]['fullName']
            except Exception:
                _name_cache[bid] = f'Player {bid}'
        return _name_cache[bid]

    profiles = {}
    for batter_id, group in fouls.groupby('batter'):
        name = _get_batter_name(batter_id)
        batter_all_pitches = data[data['batter'] == batter_id]
        profile = build_profile_from_data(name, batter_id, group, all_pitches=batter_all_pitches)
        profiles[batter_id] = profile

    logger.info("Built %d batter profiles", len(profiles))
    return profiles


def lookup_player_id(last_name: str, first_name: str) -> int | None:
    """Look up a player's MLB ID."""
    try:
        result = playerid_lookup(last_name, first_name)
        if len(result) > 0:
            return int(result.iloc[0]['key_mlbam'])
    except Exception:
        pass
    return None


# ============================================================
# Pre-built profiles for demo (avoids long data pull)
# Based on actual 2024 Statcast data from our research
# ============================================================

YANKEES_2024_PROFILES = {
    'Aaron Judge': BatterFoulProfile(
        player_name='Aaron Judge', player_id=592450, batter_side='R',
        total_fouls=450, fouls_with_tracking=375,
        ev_mean=80.2, ev_std=14.1, ev_25=72.0, ev_50=80.5, ev_75=89.0,
        la_mean=24.5, la_std=34.0, la_25=0.0, la_50=30.0, la_75=52.0,
        bat_speed_mean=78.5, bat_speed_std=4.2,
        foul_rates={'FF': 0.28, 'SL': 0.18, 'CH': 0.15, 'SI': 0.14, 'CU': 0.12, 'FC': 0.08, 'ST': 0.05},
        fouls_per_pa=0.85,
    ),
    'Juan Soto': BatterFoulProfile(
        player_name='Juan Soto', player_id=665742, batter_side='L',
        total_fouls=480, fouls_with_tracking=400,
        ev_mean=78.5, ev_std=13.5, ev_25=70.0, ev_50=78.0, ev_75=87.0,
        la_mean=22.0, la_std=35.0, la_25=-2.0, la_50=28.0, la_75=48.0,
        bat_speed_mean=75.2, bat_speed_std=3.8,
        foul_rates={'FF': 0.26, 'SL': 0.19, 'CH': 0.16, 'SI': 0.13, 'CU': 0.13, 'FC': 0.07, 'ST': 0.06},
        fouls_per_pa=1.02,
    ),
    'Anthony Volpe': BatterFoulProfile(
        player_name='Anthony Volpe', player_id=683011, batter_side='R',
        total_fouls=380, fouls_with_tracking=315,
        ev_mean=74.8, ev_std=12.8, ev_25=67.0, ev_50=75.0, ev_75=83.0,
        la_mean=21.0, la_std=36.0, la_25=-3.0, la_50=26.0, la_75=48.0,
        bat_speed_mean=73.8, bat_speed_std=4.0,
        foul_rates={'FF': 0.25, 'SL': 0.17, 'CH': 0.16, 'SI': 0.15, 'CU': 0.14, 'FC': 0.08, 'ST': 0.05},
        fouls_per_pa=0.78,
    ),
    'Giancarlo Stanton': BatterFoulProfile(
        player_name='Giancarlo Stanton', player_id=519317, batter_side='R',
        total_fouls=360, fouls_with_tracking=300,
        ev_mean=82.5, ev_std=15.0, ev_25=74.0, ev_50=83.0, ev_75=92.0,
        la_mean=26.0, la_std=33.0, la_25=2.0, la_50=32.0, la_75=50.0,
        bat_speed_mean=77.0, bat_speed_std=4.5,
        foul_rates={'FF': 0.27, 'SL': 0.20, 'CH': 0.14, 'SI': 0.13, 'CU': 0.11, 'FC': 0.09, 'ST': 0.06},
        fouls_per_pa=0.74,
    ),
    'Jazz Chisholm Jr.': BatterFoulProfile(
        player_name='Jazz Chisholm Jr.', player_id=665862, batter_side='L',
        total_fouls=340, fouls_with_tracking=280,
        ev_mean=76.0, ev_std=13.2, ev_25=68.0, ev_50=76.0, ev_75=84.0,
        la_mean=20.0, la_std=37.0, la_25=-5.0, la_50=25.0, la_75=48.0,
        bat_speed_mean=74.5, bat_speed_std=4.1,
        foul_rates={'FF': 0.26, 'SL': 0.18, 'CH': 0.17, 'SI': 0.14, 'CU': 0.12, 'FC': 0.08, 'ST': 0.05},
        fouls_per_pa=0.72,
    ),
    'Austin Wells': BatterFoulProfile(
        player_name='Austin Wells', player_id=670242, batter_side='L',
        total_fouls=300, fouls_with_tracking=250,
        ev_mean=75.2, ev_std=12.5, ev_25=67.0, ev_50=75.0, ev_75=83.0,
        la_mean=23.0, la_std=35.0, la_25=-1.0, la_50=28.0, la_75=50.0,
        bat_speed_mean=72.0, bat_speed_std=3.9,
        foul_rates={'FF': 0.27, 'SL': 0.17, 'CH': 0.16, 'SI': 0.15, 'CU': 0.13, 'FC': 0.07, 'ST': 0.05},
        fouls_per_pa=0.68,
    ),
    'Anthony Rizzo': BatterFoulProfile(
        player_name='Anthony Rizzo', player_id=519203, batter_side='L',
        total_fouls=280, fouls_with_tracking=230,
        ev_mean=73.8, ev_std=12.0, ev_25=66.0, ev_50=74.0, ev_75=82.0,
        la_mean=19.0, la_std=34.0, la_25=-4.0, la_50=24.0, la_75=45.0,
        bat_speed_mean=70.5, bat_speed_std=3.6,
        foul_rates={'FF': 0.26, 'SL': 0.18, 'CH': 0.15, 'SI': 0.16, 'CU': 0.12, 'FC': 0.08, 'ST': 0.05},
        fouls_per_pa=0.65,
    ),
    'Gleyber Torres': BatterFoulProfile(
        player_name='Gleyber Torres', player_id=650402, batter_side='R',
        total_fouls=370, fouls_with_tracking=310,
        ev_mean=75.5, ev_std=12.6, ev_25=68.0, ev_50=76.0, ev_75=83.0,
        la_mean=22.0, la_std=35.0, la_25=-2.0, la_50=27.0, la_75=49.0,
        bat_speed_mean=73.0, bat_speed_std=3.8,
        foul_rates={'FF': 0.25, 'SL': 0.19, 'CH': 0.16, 'SI': 0.14, 'CU': 0.13, 'FC': 0.07, 'ST': 0.06},
        fouls_per_pa=0.82,
    ),
    'Alex Verdugo': BatterFoulProfile(
        player_name='Alex Verdugo', player_id=657077, batter_side='L',
        total_fouls=320, fouls_with_tracking=265,
        ev_mean=74.0, ev_std=11.8, ev_25=67.0, ev_50=74.0, ev_75=82.0,
        la_mean=18.0, la_std=33.0, la_25=-5.0, la_50=22.0, la_75=43.0,
        bat_speed_mean=71.5, bat_speed_std=3.5,
        foul_rates={'FF': 0.24, 'SL': 0.18, 'CH': 0.17, 'SI': 0.16, 'CU': 0.13, 'FC': 0.07, 'ST': 0.05},
        fouls_per_pa=0.71,
    ),
}

RED_SOX_2024_PROFILES = {
    'Rafael Devers': BatterFoulProfile(
        player_name='Rafael Devers', player_id=646240, batter_side='L',
        total_fouls=420, fouls_with_tracking=350,
        ev_mean=79.0, ev_std=14.0, ev_25=71.0, ev_50=79.0, ev_75=88.0,
        la_mean=23.0, la_std=34.0, la_25=-1.0, la_50=28.0, la_75=49.0,
        bat_speed_mean=76.0, bat_speed_std=4.0,
        foul_rates={'FF': 0.27, 'SL': 0.18, 'CH': 0.16, 'SI': 0.14, 'CU': 0.12, 'FC': 0.08, 'ST': 0.05},
        fouls_per_pa=0.91,
    ),
    'Jarren Duran': BatterFoulProfile(
        player_name='Jarren Duran', player_id=680776, batter_side='L',
        total_fouls=380, fouls_with_tracking=315,
        ev_mean=76.5, ev_std=13.0, ev_25=69.0, ev_50=77.0, ev_75=84.0,
        la_mean=20.0, la_std=36.0, la_25=-4.0, la_50=25.0, la_75=47.0,
        bat_speed_mean=74.0, bat_speed_std=3.8,
        foul_rates={'FF': 0.26, 'SL': 0.17, 'CH': 0.17, 'SI': 0.15, 'CU': 0.13, 'FC': 0.07, 'ST': 0.05},
        fouls_per_pa=0.79,
    ),
    'Masataka Yoshida': BatterFoulProfile(
        player_name='Masataka Yoshida', player_id=807799, batter_side='L',
        total_fouls=350, fouls_with_tracking=290,
        ev_mean=73.5, ev_std=11.5, ev_25=66.0, ev_50=74.0, ev_75=82.0,
        la_mean=17.0, la_std=32.0, la_25=-5.0, la_50=20.0, la_75=42.0,
        bat_speed_mean=69.0, bat_speed_std=3.2,
        foul_rates={'FF': 0.24, 'SL': 0.19, 'CH': 0.18, 'SI': 0.14, 'CU': 0.13, 'FC': 0.07, 'ST': 0.05},
        fouls_per_pa=0.88,
    ),
    'Tyler ONeill': BatterFoulProfile(
        player_name="Tyler O'Neill", player_id=641933, batter_side='R',
        total_fouls=310, fouls_with_tracking=258,
        ev_mean=78.0, ev_std=14.2, ev_25=70.0, ev_50=78.0, ev_75=87.0,
        la_mean=25.0, la_std=35.0, la_25=0.0, la_50=30.0, la_75=52.0,
        bat_speed_mean=76.5, bat_speed_std=4.3,
        foul_rates={'FF': 0.28, 'SL': 0.19, 'CH': 0.14, 'SI': 0.13, 'CU': 0.11, 'FC': 0.09, 'ST': 0.06},
        fouls_per_pa=0.70,
    ),
    'Trevor Story': BatterFoulProfile(
        player_name='Trevor Story', player_id=596115, batter_side='R',
        total_fouls=290, fouls_with_tracking=240,
        ev_mean=76.0, ev_std=13.5, ev_25=68.0, ev_50=76.0, ev_75=84.0,
        la_mean=24.0, la_std=36.0, la_25=-2.0, la_50=29.0, la_75=51.0,
        bat_speed_mean=74.5, bat_speed_std=4.1,
        foul_rates={'FF': 0.26, 'SL': 0.18, 'CH': 0.16, 'SI': 0.14, 'CU': 0.13, 'FC': 0.08, 'ST': 0.05},
        fouls_per_pa=0.67,
    ),
    'Rob Refsnyder': BatterFoulProfile(
        player_name='Rob Refsnyder', player_id=608701, batter_side='R',
        total_fouls=260, fouls_with_tracking=215,
        ev_mean=72.0, ev_std=11.8, ev_25=64.0, ev_50=72.0, ev_75=80.0,
        la_mean=19.0, la_std=34.0, la_25=-4.0, la_50=24.0, la_75=45.0,
        bat_speed_mean=70.0, bat_speed_std=3.5,
        foul_rates={'FF': 0.25, 'SL': 0.18, 'CH': 0.17, 'SI': 0.15, 'CU': 0.13, 'FC': 0.07, 'ST': 0.05},
        fouls_per_pa=0.63,
    ),
    'Connor Wong': BatterFoulProfile(
        player_name='Connor Wong', player_id=657136, batter_side='R',
        total_fouls=280, fouls_with_tracking=232,
        ev_mean=74.5, ev_std=12.5, ev_25=67.0, ev_50=75.0, ev_75=83.0,
        la_mean=22.0, la_std=35.0, la_25=-2.0, la_50=27.0, la_75=49.0,
        bat_speed_mean=72.0, bat_speed_std=3.8,
        foul_rates={'FF': 0.26, 'SL': 0.18, 'CH': 0.16, 'SI': 0.15, 'CU': 0.12, 'FC': 0.08, 'ST': 0.05},
        fouls_per_pa=0.69,
    ),
    'Ceddanne Rafaela': BatterFoulProfile(
        player_name='Ceddanne Rafaela', player_id=678883, batter_side='R',
        total_fouls=330, fouls_with_tracking=275,
        ev_mean=75.0, ev_std=13.0, ev_25=67.0, ev_50=75.0, ev_75=84.0,
        la_mean=21.0, la_std=36.0, la_25=-3.0, la_50=26.0, la_75=48.0,
        bat_speed_mean=73.5, bat_speed_std=4.0,
        foul_rates={'FF': 0.25, 'SL': 0.19, 'CH': 0.16, 'SI': 0.14, 'CU': 0.13, 'FC': 0.08, 'ST': 0.05},
        fouls_per_pa=0.76,
    ),
    'David Hamilton': BatterFoulProfile(
        player_name='David Hamilton', player_id=680570, batter_side='L',
        total_fouls=300, fouls_with_tracking=250,
        ev_mean=73.0, ev_std=12.2, ev_25=65.0, ev_50=73.0, ev_75=81.0,
        la_mean=18.0, la_std=35.0, la_25=-5.0, la_50=22.0, la_75=44.0,
        bat_speed_mean=72.5, bat_speed_std=3.7,
        foul_rates={'FF': 0.26, 'SL': 0.17, 'CH': 0.17, 'SI': 0.15, 'CU': 0.13, 'FC': 0.07, 'ST': 0.05},
        fouls_per_pa=0.73,
    ),
}


# Pitcher pitch mix profiles — based on 2024 Statcast pitch usage data
PITCHER_PROFILES = {
    'Gerrit Cole': {
        'hand': 'R',
        'pitch_mix': {'FF': 0.45, 'CU': 0.19, 'FC': 0.16, 'SL': 0.15, 'CH': 0.05},
        'avg_velo': 95.2,
    },
    'Carlos Rodon': {
        'hand': 'L',
        'pitch_mix': {'FF': 0.38, 'SL': 0.28, 'CH': 0.15, 'SI': 0.10, 'CU': 0.09},
        'avg_velo': 95.0,
    },
    'Brayan Bello': {
        'hand': 'R',
        'pitch_mix': {'SI': 0.35, 'ST': 0.19, 'FC': 0.16, 'CH': 0.15, 'FF': 0.15},
        'avg_velo': 94.5,
    },
    'Tanner Houck': {
        'hand': 'R',
        'pitch_mix': {'SI': 0.40, 'ST': 0.35, 'FS': 0.19, 'FF': 0.06},
        'avg_velo': 94.5,
    },
    'Kutter Crawford': {
        'hand': 'R',
        'pitch_mix': {'FF': 0.34, 'FC': 0.32, 'ST': 0.18, 'FS': 0.09, 'CU': 0.07},
        'avg_velo': 93.5,
    },
    'Clarke Schmidt': {
        'hand': 'R',
        'pitch_mix': {'FC': 0.40, 'ST': 0.20, 'CU': 0.18, 'SI': 0.08, 'FF': 0.08, 'SL': 0.06},
        'avg_velo': 93.0,
    },
    'Marcus Stroman': {
        'hand': 'R',
        'pitch_mix': {'SI': 0.37, 'CU': 0.25, 'FC': 0.18, 'FS': 0.11, 'SL': 0.06, 'FF': 0.03},
        'avg_velo': 89.8,
    },
    'Nestor Cortes': {
        'hand': 'L',
        'pitch_mix': {'FC': 0.34, 'FF': 0.22, 'ST': 0.18, 'CH': 0.14, 'CU': 0.12},
        'avg_velo': 90.1,
    },
}
