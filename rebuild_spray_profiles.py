"""
Rebuild spray_profiles.json with correct BATTER IDs.

The previous version was keyed by pitcher ID (fouls hit OFF those pitchers).
This version keys by BATTER ID (each batter's own foul ball spray tendencies).
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from pybaseball import statcast
# trajectory import no longer needed (arccos back-solve removed)
import warnings
warnings.filterwarnings('ignore')

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache')
os.makedirs(CACHE_DIR, exist_ok=True)

# Default window: the 2025 season plus 2026 to date. The old default was
# Jun-Aug 2024, which by 2026 returned largely retired players.
DEFAULT_MONTHS = (
    [(f'2025-{m:02d}-01', f'2025-{m:02d}-28') for m in range(4, 10)] +
    [(f'2026-{m:02d}-01', f'2026-{m:02d}-28') for m in range(4, 9)]
)


def load_data(parquet: str | None, months) -> pd.DataFrame:
    """Load pitches from a cached parquet if given, else pull from Statcast.

    game_backtest.py caches exactly the columns this script needs, so pointing
    at that file avoids a second multi-minute pull of the same window.
    """
    if parquet:
        print(f"Loading cached pitches from {parquet}")
        data = pd.read_parquet(parquet)
        if 'game_type' in data.columns:
            data = data[data['game_type'] == 'R']
        print(f"  {len(data):,} regular-season pitches")
        return data

    all_data = []
    for start, end in months:
        print(f"\nPulling {start} to {end}...")
        try:
            chunk = statcast(start_dt=start, end_dt=end)
            print(f"  Got {len(chunk):,} pitches")
            all_data.append(chunk)
        except Exception as e:
            print(f"  Error pulling {start}-{end}: {e}")
            # Try smaller chunks (weekly)
            from datetime import datetime, timedelta
            d = datetime.strptime(start, '%Y-%m-%d')
            end_d = datetime.strptime(end, '%Y-%m-%d')
            while d < end_d:
                w_end = min(d + timedelta(days=6), end_d)
                try:
                    chunk = statcast(start_dt=d.strftime('%Y-%m-%d'), end_dt=w_end.strftime('%Y-%m-%d'))
                    print(f"    {d.strftime('%m/%d')}-{w_end.strftime('%m/%d')}: {len(chunk):,}")
                    all_data.append(chunk)
                except Exception as e2:
                    print(f"    {d.strftime('%m/%d')}-{w_end.strftime('%m/%d')}: SKIP ({e2})")
                d = w_end + timedelta(days=1)

    return pd.concat(all_data, ignore_index=True)


def main():
    parser = argparse.ArgumentParser(description='Rebuild batter spray profiles')
    parser.add_argument('--parquet', help='Cached Statcast parquet to use instead of pulling')
    parser.add_argument('--min-fouls', type=int, default=10,
                        help='Minimum tracked fouls for a batter to get a profile')
    args = parser.parse_args()

    print("=" * 60)
    print("REBUILDING SPRAY PROFILES (Batter-keyed)")
    print("=" * 60)

    data = load_data(args.parquet, DEFAULT_MONTHS)
    print(f"\nTotal pitches: {len(data):,}")
    if 'game_date' in data.columns:
        dates = data['game_date'].astype(str)
        print(f"Date range: {dates.min()} to {dates.max()}")

    # Filter to foul balls with tracking data (exclude foul tips — caught by catcher)
    foul_mask = data['description'].str.contains('foul', case=False, na=False)
    tip_mask = data['description'].str.contains('foul_tip|foul tip', case=False, na=False)
    fouls = data[foul_mask & ~tip_mask].copy()
    tracked = fouls[
        fouls['launch_speed'].notna() &
        fouls['launch_angle'].notna() &
        fouls['hit_distance_sc'].notna() &
        (fouls['hit_distance_sc'] > 5)
    ].copy()
    print(f"Fouls with tracking + distance: {len(tracked):,}")

    # Group by BATTER (not pitcher)
    profiles = {}
    batter_groups = tracked.groupby('batter')
    print(f"Unique batters with foul data: {len(batter_groups)}")

    # Look up batter names via statsapi (player_name in Statcast = pitcher name).
    # Batched: one request per 100 players rather than ~700 sequential calls.
    import statsapi
    _name_cache = {}
    _all_ids = [int(b) for b in batter_groups.groups]
    for i in range(0, len(_all_ids), 100):
        batch = _all_ids[i:i + 100]
        try:
            info = statsapi.get('people', {'personIds': ','.join(str(b) for b in batch)})
            for person in info.get('people', []):
                _name_cache[int(person['id'])] = person['fullName']
        except Exception as e:
            print(f"  Name batch {i}-{i+len(batch)} failed ({e}); falling back per player")
    print(f"Resolved {len(_name_cache)}/{len(_all_ids)} batter names")

    def _get_batter_name(bid):
        bid = int(bid)
        if bid not in _name_cache:
            try:
                info = statsapi.get('people', {'personIds': bid})
                _name_cache[bid] = info['people'][0]['fullName']
            except Exception:
                _name_cache[bid] = f'Player {bid}'
        return _name_cache[bid]

    # Partition once. Scanning the full frame per batter was two passes over
    # 1.2M rows each for ~700 batters.
    all_by_batter = {bid: g for bid, g in data.groupby('batter')}

    for batter_id, group in batter_groups:
        if len(group) < args.min_fouls:
            continue

        name = _get_batter_name(batter_id)
        stand_mode = group['stand'].mode()
        stand = stand_mode.iloc[0] if len(stand_mode) > 0 else 'R'

        batter_all_pitches = all_by_batter[batter_id]

        # Compute fair ball pull tendency from hc_x/hc_y (real directional data).
        # This is the primary input to the spray angle model.
        # hc_x: 0=left, 125=center, 250=right (catcher's view)
        fair_balls = batter_all_pitches[
            (batter_all_pitches['type'] == 'X') &
            batter_all_pitches['hc_x'].notna()
        ]
        fair_pull_pct = 50.0
        if len(fair_balls) >= 20:
            if stand == 'R':
                pull_count = (fair_balls['hc_x'] < 125).sum()
            else:
                pull_count = (fair_balls['hc_x'] > 125).sum()
            fair_pull_pct = round(pull_count / len(fair_balls) * 100, 1)

        # Compute real fouls per plate appearance from actual PA counts.
        # A PA = unique (game_pk, at_bat_number) for this batter.
        batter_pas = batter_all_pitches.groupby(['game_pk', 'at_bat_number']).ngroups
        batter_foul_mask = batter_all_pitches['description'].str.contains('foul', case=False, na=False)
        batter_tip_mask = batter_all_pitches['description'].str.contains('foul_tip|foul tip', case=False, na=False)
        batter_foul_count = (batter_foul_mask & ~batter_tip_mask).sum()
        fouls_per_pa = round(batter_foul_count / batter_pas, 3) if batter_pas >= 20 else 0.0

        # Per-batter exit velocity and launch angle from real foul ball data
        ev_data = group['launch_speed'].dropna()
        la_data = group['launch_angle'].dropna()

        # Last appearance in the window, so a stale profile is visible rather
        # than having to be inferred. A window spanning two seasons keeps
        # players who retired after the first one.
        last_game = str(batter_all_pitches['game_date'].astype(str).max())

        profiles[str(batter_id)] = {
            'name': name,
            'last_game': last_game,
            'stand': stand,
            'n_fouls': len(group),
            'fair_pull_pct': fair_pull_pct,
            'fouls_per_pa': fouls_per_pa,
            'ev_mean': round(float(ev_data.mean()), 1) if len(ev_data) >= 10 else None,
            'ev_std': round(float(ev_data.std()), 1) if len(ev_data) >= 10 else None,
            'la_mean': round(float(la_data.mean()), 1) if len(la_data) >= 10 else None,
            'la_std': round(float(la_data.std()), 1) if len(la_data) >= 10 else None,
        }

    print(f"\nBuilt {len(profiles)} batter spray profiles")
    latest_season = max(p['last_game'] for p in profiles.values())[:4]
    current = sum(1 for p in profiles.values() if p['last_game'][:4] == latest_season)
    print(f"  active in {latest_season}: {current}")
    print(f"  last seen earlier:  {len(profiles) - current} "
          f"(kept — harmless, they simply never appear in a live lineup)")

    # Save
    out_path = os.path.join(CACHE_DIR, 'spray_profiles.json')
    # Backup old file
    if os.path.exists(out_path):
        backup = out_path + '.bak'
        if os.path.exists(backup):
            os.remove(backup)
        os.rename(out_path, backup)
        print(f"Backed up old file to {backup}")

    with open(out_path, 'w') as f:
        json.dump(profiles, f, indent=2)
    print(f"Saved to {out_path}")

    # Print some sample entries
    print("\nSample profiles:")
    for pid, prof in list(profiles.items())[:5]:
        print(f"  {pid}: {prof['name']} ({prof['stand']}) "
              f"n={prof['n_fouls']} pull={prof['fair_pull_pct']}% "
              f"fouls/pa={prof['fouls_per_pa']} "
              f"ev={prof.get('ev_mean', 'N/A')} la={prof.get('la_mean', 'N/A')}")


if __name__ == '__main__':
    main()
