"""
Rebuild spray_profiles.json with correct BATTER IDs.

The previous version was keyed by pitcher ID (fouls hit OFF those pitchers).
This version keys by BATTER ID (each batter's own foul ball spray tendencies).
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from pybaseball import statcast
# trajectory import no longer needed (arccos back-solve removed)
import warnings
warnings.filterwarnings('ignore')

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache')
os.makedirs(CACHE_DIR, exist_ok=True)

def main():
    print("=" * 60)
    print("REBUILDING SPRAY PROFILES (Batter-keyed)")
    print("=" * 60)

    # Pull 3 months of 2024 data (Jun-Aug for good sample size)
    all_data = []
    months = [
        ('2024-06-01', '2024-06-30'),
        ('2024-07-01', '2024-07-31'),
        ('2024-08-01', '2024-08-31'),
    ]

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

    data = pd.concat(all_data, ignore_index=True)
    print(f"\nTotal pitches: {len(data):,}")

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

    # Look up batter names via statsapi (player_name in Statcast = pitcher name)
    import statsapi
    _name_cache = {}
    def _get_batter_name(bid):
        if bid not in _name_cache:
            try:
                info = statsapi.get('people', {'personIds': int(bid)})
                _name_cache[bid] = info['people'][0]['fullName']
            except Exception:
                _name_cache[bid] = f'Player {bid}'
        return _name_cache[bid]

    for batter_id, group in batter_groups:
        if len(group) < 10:
            continue

        name = _get_batter_name(batter_id)
        stand_mode = group['stand'].mode()
        stand = stand_mode.iloc[0] if len(stand_mode) > 0 else 'R'

        # Compute fair ball pull tendency from hc_x/hc_y (real directional data).
        # This is the primary input to the spray angle model.
        # hc_x: 0=left, 125=center, 250=right (catcher's view)
        fair_balls = data[
            (data['batter'] == batter_id) &
            (data['type'] == 'X') &
            data['hc_x'].notna()
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
        batter_all_pitches = data[data['batter'] == batter_id]
        batter_pas = batter_all_pitches.groupby(['game_pk', 'at_bat_number']).ngroups
        batter_foul_mask = batter_all_pitches['description'].str.contains('foul', case=False, na=False)
        batter_tip_mask = batter_all_pitches['description'].str.contains('foul_tip|foul tip', case=False, na=False)
        batter_foul_count = (batter_foul_mask & ~batter_tip_mask).sum()
        fouls_per_pa = round(batter_foul_count / batter_pas, 3) if batter_pas >= 20 else 0.0

        profiles[str(batter_id)] = {
            'name': name,
            'stand': stand,
            'n_fouls': len(group),
            'fair_pull_pct': fair_pull_pct,
            'fouls_per_pa': fouls_per_pa,
        }

    print(f"\nBuilt {len(profiles)} batter spray profiles")

    # Save
    out_path = os.path.join(CACHE_DIR, 'spray_profiles.json')
    # Backup old file
    if os.path.exists(out_path):
        backup = out_path + '.bak_pitcher_keyed'
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
              f"fouls/pa={prof['fouls_per_pa']}")


if __name__ == '__main__':
    main()
