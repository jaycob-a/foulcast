"""
Script 2: Batter Foul Ball Tendency Analysis
Do different batters foul balls in predictably different directions?
This is the core question for whether the product can generate per-matchup predictions.
"""
import pandas as pd
from pybaseball import statcast
import warnings
warnings.filterwarnings('ignore')

print("=" * 70)
print("BATTER FOUL BALL TENDENCY ANALYSIS")
print("=" * 70)

# Pull a larger sample — 3 months of 2024 season
print("\nPulling Statcast data for June-August 2024...")
data = statcast(start_dt='2024-06-01', end_dt='2024-08-31')
print(f"Total pitches: {len(data):,}")

fouls = data[data['description'].str.contains('foul', case=False, na=False)].copy()
print(f"Total fouls: {len(fouls):,}")

# ============================================================
# ANALYSIS 1: Handedness matters
# ============================================================
print("\n" + "=" * 70)
print("ANALYSIS 1: Foul Ball Tendencies by Batter Handedness")
print("=" * 70)

for hand in ['L', 'R']:
    subset = fouls[fouls['stand'] == hand]
    with_ev = subset[subset['launch_speed'].notna()]
    print(f"\n{'LEFT' if hand == 'L' else 'RIGHT'}-handed batters:")
    print(f"  Total fouls: {len(subset):,}")
    print(f"  With exit velocity: {len(with_ev):,}")
    if len(with_ev) > 0:
        print(f"  Avg exit velocity: {with_ev['launch_speed'].mean():.1f} mph")
        print(f"  Avg launch angle: {with_ev['launch_angle'].mean():.1f} degrees")

        # Coordinate analysis if available
        with_coords = with_ev[with_ev['hc_x'].notna()]
        if len(with_coords) > 10:
            print(f"  With coordinates: {len(with_coords):,}")
            print(f"  Avg hc_x: {with_coords['hc_x'].mean():.1f} (125 = center)")
            print(f"  Avg hc_y: {with_coords['hc_y'].mean():.1f}")

        # Launch angle distribution — key for estimating stands vs field
        print(f"\n  Launch angle distribution:")
        bins = [(-90, -10), (-10, 10), (10, 30), (30, 50), (50, 90)]
        labels = ['Sharply down (<-10)', 'Low (-10 to 10)', 'Medium (10-30)', 'High (30-50)', 'Popup (>50)']
        for (lo, hi), label in zip(bins, labels):
            count = ((with_ev['launch_angle'] >= lo) & (with_ev['launch_angle'] < hi)).sum()
            pct = count / len(with_ev) * 100
            bar = '#' * int(pct / 2)
            print(f"    {label:<25} {count:>6,} ({pct:>5.1f}%) {bar}")

# ============================================================
# ANALYSIS 2: Top foul ball hitters — do individuals have patterns?
# ============================================================
print("\n" + "=" * 70)
print("ANALYSIS 2: Individual Batter Foul Patterns (Top 20 by volume)")
print("=" * 70)

foul_counts = fouls.groupby('batter').agg(
    player_name=('player_name', 'first'),
    stand=('stand', 'first'),
    total_fouls=('description', 'count'),
    fouls_with_ev=('launch_speed', lambda x: x.notna().sum()),
    avg_ev=('launch_speed', 'mean'),
    avg_angle=('launch_angle', 'mean'),
    avg_hc_x=('hc_x', 'mean'),
    avg_hc_y=('hc_y', 'mean'),
).sort_values('total_fouls', ascending=False)

print(f"\n{'Player':<25} {'Hand':>4} {'Fouls':>6} {'w/EV':>6} {'AvgEV':>6} {'AvgLA':>7} {'hc_x':>7} {'hc_y':>7}")
print("-" * 75)
for _, row in foul_counts.head(20).iterrows():
    ev_str = f"{row['avg_ev']:.1f}" if pd.notna(row['avg_ev']) else "N/A"
    la_str = f"{row['avg_angle']:.1f}" if pd.notna(row['avg_angle']) else "N/A"
    hcx_str = f"{row['avg_hc_x']:.1f}" if pd.notna(row['avg_hc_x']) else "N/A"
    hcy_str = f"{row['avg_hc_y']:.1f}" if pd.notna(row['avg_hc_y']) else "N/A"
    print(f"{str(row['player_name']):<25} {row['stand']:>4} {row['total_fouls']:>6} {row['fouls_with_ev']:>6} {ev_str:>6} {la_str:>7} {hcx_str:>7} {hcy_str:>7}")

# ============================================================
# ANALYSIS 3: Foul tendency by pitch type
# ============================================================
print("\n" + "=" * 70)
print("ANALYSIS 3: Foul Rates and Characteristics by Pitch Type")
print("=" * 70)

all_pitches = data[data['pitch_type'].notna()]
pitch_summary = []
for pt in all_pitches['pitch_type'].unique():
    pt_data = all_pitches[all_pitches['pitch_type'] == pt]
    pt_fouls = fouls[fouls['pitch_type'] == pt]
    pt_fouls_ev = pt_fouls[pt_fouls['launch_speed'].notna()]

    if len(pt_data) > 500:  # only show pitch types with enough data
        pitch_summary.append({
            'pitch_type': pt,
            'total': len(pt_data),
            'fouls': len(pt_fouls),
            'foul_rate': len(pt_fouls) / len(pt_data) * 100,
            'avg_ev': pt_fouls_ev['launch_speed'].mean() if len(pt_fouls_ev) > 0 else None,
            'avg_la': pt_fouls_ev['launch_angle'].mean() if len(pt_fouls_ev) > 0 else None,
        })

pitch_df = pd.DataFrame(pitch_summary).sort_values('foul_rate', ascending=False)
print(f"\n{'Pitch':>6} {'Total':>8} {'Fouls':>7} {'Foul%':>7} {'AvgEV':>7} {'AvgLA':>7}")
print("-" * 45)
for _, row in pitch_df.iterrows():
    ev_str = f"{row['avg_ev']:.1f}" if pd.notna(row['avg_ev']) else "N/A"
    la_str = f"{row['avg_la']:.1f}" if pd.notna(row['avg_la']) else "N/A"
    print(f"{row['pitch_type']:>6} {row['total']:>8,} {row['fouls']:>7,} {row['foul_rate']:>6.1f}% {ev_str:>7} {la_str:>7}")

# ============================================================
# ANALYSIS 4: Matchup effects — does pitcher handedness change foul direction?
# ============================================================
print("\n" + "=" * 70)
print("ANALYSIS 4: Batter/Pitcher Handedness Matchup Effects")
print("=" * 70)

fouls_with_data = fouls[fouls['launch_speed'].notna()].copy()
for bh in ['L', 'R']:
    for ph in ['L', 'R']:
        subset = fouls_with_data[(fouls_with_data['stand'] == bh) & (fouls_with_data['p_throws'] == ph)]
        if len(subset) > 50:
            with_coords = subset[subset['hc_x'].notna()]
            coord_info = f" | avg hc_x={with_coords['hc_x'].mean():.1f}" if len(with_coords) > 10 else ""
            print(f"  {bh}HB vs {ph}HP: n={len(subset):,}, avg EV={subset['launch_speed'].mean():.1f}, "
                  f"avg LA={subset['launch_angle'].mean():.1f}{coord_info}")

print("\n" + "=" * 70)
print("KEY FINDINGS")
print("=" * 70)
print("""
Questions answered:
1. Do batters have consistent foul ball tendencies? (Check individual variance above)
2. Does handedness predict foul direction? (Compare L vs R hc_x averages)
3. Does pitch type affect foul characteristics? (Check pitch type table)
4. Do matchups matter? (Compare same-side vs opposite-side matchups)

If individual batters show consistent patterns with low variance,
the per-matchup prediction model is VIABLE.
""")
