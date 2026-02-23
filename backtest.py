"""
BACKTEST: Validate foul ball prediction model against real Statcast data.

Compares predicted foul ball distance distributions against actual
hit_distance_sc values from Statcast. This tells us how well our
physics model matches reality.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats
from pybaseball import statcast
from foulball.trajectory import simulate_trajectory
import warnings
warnings.filterwarnings('ignore')

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_backtest():
    print("=" * 70)
    print("BACKTEST: Physics Model vs Actual Statcast Data")
    print("=" * 70)

    # Pull a month of real data
    print("\nPulling Statcast data for August 2024...")
    data = statcast(start_dt='2024-08-01', end_dt='2024-08-31')
    print(f"Total pitches: {len(data):,}")

    # Get fouls with tracking data
    fouls = data[data['description'].str.contains('foul', case=False, na=False)].copy()
    tracked = fouls[
        fouls['launch_speed'].notna() &
        fouls['launch_angle'].notna() &
        fouls['hit_distance_sc'].notna()
    ].copy()
    print(f"Fouls with full tracking: {len(tracked):,}")

    # Run physics model on each tracked foul ball
    print("\nSimulating trajectories for all tracked fouls...")
    predicted_distances = []
    actual_distances = []
    errors = []

    for _, row in tracked.iterrows():
        ev = row['launch_speed']
        la = row['launch_angle']
        actual_dist = row['hit_distance_sc']

        if pd.isna(ev) or pd.isna(la) or pd.isna(actual_dist):
            continue
        if actual_dist < 1:
            continue

        # Simulate with spray angle = 0 (straight) to get max distance
        try:
            result = simulate_trajectory(ev, la, spray_angle_deg=0)
            pred_dist = result.landing_distance
        except Exception:
            continue

        predicted_distances.append(pred_dist)
        actual_distances.append(actual_dist)
        errors.append(pred_dist - actual_dist)

    predicted = np.array(predicted_distances)
    actual = np.array(actual_distances)
    error = np.array(errors)

    print(f"\nSuccessfully compared: {len(predicted):,} foul balls")

    # === METRICS ===
    print("\n" + "=" * 70)
    print("ACCURACY METRICS")
    print("=" * 70)

    mae = np.mean(np.abs(error))
    rmse = np.sqrt(np.mean(error**2))
    median_error = np.median(np.abs(error))
    corr, pval = stats.pearsonr(predicted, actual)
    mean_bias = np.mean(error)

    print(f"  Mean Absolute Error:  {mae:.1f} feet")
    print(f"  Median Absolute Error: {median_error:.1f} feet")
    print(f"  RMSE:                 {rmse:.1f} feet")
    print(f"  Mean Bias:            {mean_bias:+.1f} feet (positive = model overshoots)")
    print(f"  Correlation:          {corr:.3f} (p < {pval:.2e})")

    # Break down by distance bucket
    print(f"\n{'Distance Bucket':<20} {'Count':>7} {'MAE':>8} {'Bias':>8}")
    print("-" * 45)
    for lo, hi in [(0, 50), (50, 100), (100, 200), (200, 300), (300, 500)]:
        mask = (actual >= lo) & (actual < hi)
        if mask.sum() > 10:
            bucket_mae = np.mean(np.abs(error[mask]))
            bucket_bias = np.mean(error[mask])
            print(f"  {lo}-{hi} ft{'':<10} {mask.sum():>7} {bucket_mae:>7.1f} {bucket_bias:>+7.1f}")

    # Break down by launch angle
    la_values = tracked['launch_angle'].values[:len(predicted)]
    print(f"\n{'Launch Angle':<20} {'Count':>7} {'MAE':>8} {'Bias':>8}")
    print("-" * 45)
    for lo, hi, label in [(-90, 0, 'Negative'), (0, 20, 'Low (0-20)'),
                           (20, 45, 'Mid (20-45)'), (45, 90, 'High (45+)')]:
        mask = (la_values >= lo) & (la_values < hi)
        if mask.sum() > 10:
            bucket_mae = np.mean(np.abs(error[mask]))
            bucket_bias = np.mean(error[mask])
            print(f"  {label:<18} {mask.sum():>7} {bucket_mae:>7.1f} {bucket_bias:>+7.1f}")

    # === VISUALIZATIONS ===
    print("\nGenerating backtest visualizations...")

    fig, axes = plt.subplots(2, 2, figsize=(16, 14))

    # 1. Predicted vs Actual scatter
    ax = axes[0][0]
    ax.scatter(actual, predicted, alpha=0.05, s=3, c='steelblue')
    max_val = max(actual.max(), predicted.max())
    ax.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='Perfect prediction')
    ax.set_xlabel('Actual Distance (Statcast hit_distance_sc)')
    ax.set_ylabel('Predicted Distance (Physics Model)')
    ax.set_title(f'Predicted vs Actual Distance\nr={corr:.3f}, MAE={mae:.1f}ft')
    ax.legend()
    ax.set_xlim(0, 500)
    ax.set_ylim(0, 500)
    ax.set_aspect('equal')

    # 2. Error distribution
    ax = axes[0][1]
    ax.hist(error, bins=80, color='steelblue', alpha=0.7, edgecolor='black', linewidth=0.3)
    ax.axvline(0, color='red', linestyle='--', linewidth=2)
    ax.axvline(mean_bias, color='orange', linestyle='--', linewidth=2, label=f'Mean bias: {mean_bias:+.1f}ft')
    ax.set_xlabel('Prediction Error (feet)')
    ax.set_ylabel('Count')
    ax.set_title('Error Distribution')
    ax.legend()

    # 3. Distance distribution comparison
    ax = axes[1][0]
    bins = np.arange(0, 400, 10)
    ax.hist(actual, bins=bins, alpha=0.6, color='blue', label='Actual (Statcast)', density=True)
    ax.hist(predicted, bins=bins, alpha=0.6, color='red', label='Predicted (Model)', density=True)
    ax.set_xlabel('Distance (feet)')
    ax.set_ylabel('Density')
    ax.set_title('Distance Distribution: Model vs Reality')
    ax.legend()

    # 4. Error by exit velocity
    ax = axes[1][1]
    ev_values = tracked['launch_speed'].values[:len(predicted)]
    ax.scatter(ev_values, error, alpha=0.05, s=3, c='steelblue')
    # Binned trend line
    ev_bins = np.arange(20, 120, 10)
    for i in range(len(ev_bins)-1):
        mask = (ev_values >= ev_bins[i]) & (ev_values < ev_bins[i+1])
        if mask.sum() > 20:
            ax.plot(ev_bins[i] + 5, np.mean(error[mask]), 'ro-', markersize=8)
    ax.axhline(0, color='red', linestyle='--')
    ax.set_xlabel('Exit Velocity (mph)')
    ax.set_ylabel('Prediction Error (feet)')
    ax.set_title('Error vs Exit Velocity')

    plt.suptitle('Foul Ball Physics Model — Backtest Results', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/backtest_results.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {OUTPUT_DIR}/backtest_results.png")

    # === SPRAY ANGLE VALIDATION ===
    print("\n" + "=" * 70)
    print("SPRAY ANGLE INFERENCE VALIDATION")
    print("=" * 70)
    print("Since predicted distance (straight-line) > actual distance for most fouls,")
    print("the difference reveals how much the ball went sideways (spray angle).")

    ratio = actual / np.clip(predicted, 1, None)
    inferred_spray = np.degrees(np.arccos(np.clip(ratio, 0, 1)))

    print(f"\nInferred spray angle distribution:")
    print(f"  Mean:   {np.mean(inferred_spray):.1f} degrees")
    print(f"  Median: {np.median(inferred_spray):.1f} degrees")
    print(f"  Std:    {np.std(inferred_spray):.1f} degrees")
    print(f"  25th:   {np.percentile(inferred_spray, 25):.1f} degrees")
    print(f"  75th:   {np.percentile(inferred_spray, 75):.1f} degrees")

    # By handedness
    stands = tracked['stand'].values[:len(predicted)]
    for hand in ['L', 'R']:
        mask = stands == hand
        if mask.sum() > 50:
            print(f"\n  {hand}HB spray angle: mean={np.mean(inferred_spray[mask]):.1f}, "
                  f"median={np.median(inferred_spray[mask]):.1f}, std={np.std(inferred_spray[mask]):.1f}")

    print("\n" + "=" * 70)
    print("BACKTEST COMPLETE")
    print("=" * 70)
    if corr > 0.7:
        print(f"Model correlation: {corr:.3f} — STRONG. Physics model is well-calibrated.")
    elif corr > 0.5:
        print(f"Model correlation: {corr:.3f} — MODERATE. Room for improvement but viable.")
    else:
        print(f"Model correlation: {corr:.3f} — WEAK. Model needs significant tuning.")

    print(f"Mean error: {mae:.1f} feet — {'Good' if mae < 50 else 'Needs work'}")
    print(f"\nKey insight: The spray angle distribution above can be fed back into")
    print(f"the prediction model to make spray estimates more realistic.")


if __name__ == '__main__':
    run_backtest()
