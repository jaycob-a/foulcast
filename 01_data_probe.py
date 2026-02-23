"""
Script 1: Foul Ball Data Probe
Pull Statcast data and check what fields are actually populated for foul balls.
This is the critical viability question.
"""
import pandas as pd
from pybaseball import statcast
import warnings
warnings.filterwarnings('ignore')

print("=" * 70)
print("FOUL BALL DATA PROBE — What does Statcast actually give us?")
print("=" * 70)

# Pull a month of 2024 data (recent full season)
print("\nPulling Statcast data for July 2024...")
data = statcast(start_dt='2024-07-01', end_dt='2024-07-31')
print(f"Total pitches pulled: {len(data):,}")

# Identify all foul-related events
foul_descriptions = [d for d in data['description'].unique() if 'foul' in str(d).lower()]
print(f"\nFoul-related description values: {foul_descriptions}")

# Filter to foul balls only
fouls = data[data['description'].str.contains('foul', case=False, na=False)].copy()
print(f"Total foul ball events: {len(fouls):,}")
print(f"Percentage of all pitches: {len(fouls)/len(data)*100:.1f}%")

# Break down by foul type
print("\n--- Foul Event Types ---")
print(fouls['description'].value_counts().to_string())

# THE KEY QUESTION: What fields are populated for fouls?
key_fields = [
    'launch_speed',       # exit velocity
    'launch_angle',       # launch angle
    'hc_x',              # hit coordinate X
    'hc_y',              # hit coordinate Y
    'hit_distance_sc',    # hit distance
    'bb_type',            # batted ball type (ground_ball, fly_ball, etc.)
    'estimated_ba_using_speedangle',  # expected BA
    'estimated_woba_using_speedangle', # expected wOBA
    'launch_speed_angle',  # launch speed/angle bucket
    'stand',              # batter handedness (L/R)
    'p_throws',           # pitcher handedness (L/R)
    'pitch_type',         # pitch type
    'release_speed',      # pitch speed
    'zone',               # pitch zone
    'plate_x',            # pitch horizontal location
    'plate_z',            # pitch vertical location
    'bat_speed',          # bat speed (newer field)
    'swing_length',       # swing length (newer field)
]

print("\n" + "=" * 70)
print("FIELD POPULATION RATES FOR FOUL BALLS")
print("=" * 70)
print(f"{'Field':<45} {'Populated':>10} {'Rate':>8}")
print("-" * 65)

for field in key_fields:
    if field in fouls.columns:
        non_null = fouls[field].notna().sum()
        rate = non_null / len(fouls) * 100
        marker = " <<<" if rate > 50 and field in ['launch_speed', 'launch_angle', 'hc_x', 'hc_y', 'hit_distance_sc'] else ""
        print(f"{field:<45} {non_null:>10,} {rate:>7.1f}%{marker}")
    else:
        print(f"{field:<45} {'NOT IN DATA':>10} {'N/A':>8}")

# Deep dive on the spatial fields specifically
print("\n" + "=" * 70)
print("DEEP DIVE: Foul balls WITH exit velocity data")
print("=" * 70)

fouls_with_ev = fouls[fouls['launch_speed'].notna()]
print(f"Fouls with exit velocity: {len(fouls_with_ev):,} / {len(fouls):,} ({len(fouls_with_ev)/len(fouls)*100:.1f}%)")

if len(fouls_with_ev) > 0:
    print(f"\nExit velocity stats:")
    print(fouls_with_ev['launch_speed'].describe().to_string())

    print(f"\nLaunch angle stats:")
    print(fouls_with_ev['launch_angle'].describe().to_string())

    # Do these fouls also have coordinates?
    has_coords = fouls_with_ev[fouls_with_ev['hc_x'].notna()]
    print(f"\nOf those, have hit coordinates (hc_x/hc_y): {len(has_coords):,} ({len(has_coords)/len(fouls_with_ev)*100:.1f}%)")

    has_distance = fouls_with_ev[fouls_with_ev['hit_distance_sc'].notna()]
    print(f"Of those, have hit distance: {len(has_distance):,} ({len(has_distance)/len(fouls_with_ev)*100:.1f}%)")

    # What batted ball types do fouls register as?
    print(f"\nBatted ball types for fouls with EV:")
    print(fouls_with_ev['bb_type'].value_counts(dropna=False).to_string())

# Compare: balls in play vs fouls
print("\n" + "=" * 70)
print("COMPARISON: Balls in Play vs Foul Balls")
print("=" * 70)
in_play = data[data['type'] == 'X']
print(f"Balls in play: {len(in_play):,}")
print(f"  With exit velocity: {in_play['launch_speed'].notna().sum():,} ({in_play['launch_speed'].notna().mean()*100:.1f}%)")
print(f"  With coordinates:   {in_play['hc_x'].notna().sum():,} ({in_play['hc_x'].notna().mean()*100:.1f}%)")
print(f"  With distance:      {in_play['hit_distance_sc'].notna().sum():,} ({in_play['hit_distance_sc'].notna().mean()*100:.1f}%)")
print(f"\nFoul balls: {len(fouls):,}")
print(f"  With exit velocity: {fouls['launch_speed'].notna().sum():,} ({fouls['launch_speed'].notna().mean()*100:.1f}%)")
print(f"  With coordinates:   {fouls['hc_x'].notna().sum():,} ({fouls['hc_x'].notna().mean()*100:.1f}%)")
print(f"  With distance:      {fouls['hit_distance_sc'].notna().sum():,} ({fouls['hit_distance_sc'].notna().mean()*100:.1f}%)")

# Sample of foul ball data with the most fields populated
print("\n" + "=" * 70)
print("SAMPLE: Foul balls with the most tracking data")
print("=" * 70)
sample_cols = ['player_name', 'stand', 'description', 'launch_speed', 'launch_angle',
               'hc_x', 'hc_y', 'hit_distance_sc', 'bb_type', 'pitch_type', 'release_speed',
               'bat_speed', 'swing_length']
sample_cols = [c for c in sample_cols if c in fouls.columns]
fouls_rich = fouls.dropna(subset=['launch_speed'])
if len(fouls_rich) > 0:
    print(fouls_rich[sample_cols].head(20).to_string())

print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)
ev_rate = fouls['launch_speed'].notna().mean() * 100
coord_rate = fouls['hc_x'].notna().mean() * 100
print(f"Exit velocity available for {ev_rate:.1f}% of fouls")
print(f"Hit coordinates available for {coord_rate:.1f}% of fouls")

if ev_rate > 30:
    print("\n>>> EXIT VELOCITY DATA IS VIABLE for foul ball modeling")
else:
    print("\n>>> EXIT VELOCITY DATA IS SPARSE — may need physics-based estimation")

if coord_rate > 10:
    print(">>> COORDINATE DATA IS VIABLE — can map foul ball landing zones")
else:
    print(">>> COORDINATE DATA IS SPARSE — will need physics model (EV + angle + stadium geometry)")
    print("    This is still very doable but requires building a trajectory simulator")
