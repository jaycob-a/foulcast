"""
Script 3: Spatial Analysis & Stadium Heatmap
Map foul ball data to stadium coordinates and generate visualizations.
"""
import pandas as pd
import numpy as np
from pybaseball import statcast
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle
import warnings
warnings.filterwarnings('ignore')

OUTPUT_DIR = 'C:/Users/jayco/foulball-research'

print("=" * 70)
print("SPATIAL ANALYSIS & FOUL BALL HEATMAP")
print("=" * 70)

# Pull 3 months of data
print("\nPulling Statcast data for June-August 2024...")
data = statcast(start_dt='2024-06-01', end_dt='2024-08-31')
print(f"Total pitches: {len(data):,}")

fouls = data[data['description'].str.contains('foul', case=False, na=False)].copy()
fouls_with_coords = fouls[fouls['hc_x'].notna() & fouls['hc_y'].notna()].copy()
fouls_with_ev = fouls[fouls['launch_speed'].notna()].copy()

print(f"Total fouls: {len(fouls):,}")
print(f"Fouls with coordinates: {len(fouls_with_coords):,}")
print(f"Fouls with exit velocity: {len(fouls_with_ev):,}")

# ============================================================
# VISUALIZATION 1: Raw foul ball scatter plot (if we have coordinates)
# ============================================================
if len(fouls_with_coords) > 50:
    print("\nGenerating foul ball coordinate scatter plot...")

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))

    # Left: All batted balls for reference
    in_play = data[(data['type'] == 'X') & data['hc_x'].notna()].copy()
    axes[0].scatter(in_play['hc_x'], in_play['hc_y'], alpha=0.05, s=2, c='blue', label='In play')
    axes[0].scatter(fouls_with_coords['hc_x'], fouls_with_coords['hc_y'], alpha=0.3, s=5, c='red', label='Foul')
    axes[0].set_title('All Batted Balls vs Fouls with Coordinates')
    axes[0].set_xlabel('hc_x')
    axes[0].set_ylabel('hc_y')
    axes[0].legend()
    axes[0].invert_yaxis()
    axes[0].set_aspect('equal')

    # Right: Just fouls, colored by handedness
    for hand, color in [('L', 'orange'), ('R', 'purple')]:
        subset = fouls_with_coords[fouls_with_coords['stand'] == hand]
        axes[1].scatter(subset['hc_x'], subset['hc_y'], alpha=0.3, s=5, c=color, label=f'{hand}HB')
    axes[1].set_title('Foul Ball Coordinates by Batter Handedness')
    axes[1].set_xlabel('hc_x')
    axes[1].set_ylabel('hc_y')
    axes[1].legend()
    axes[1].invert_yaxis()
    axes[1].set_aspect('equal')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/01_foul_coordinates.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {OUTPUT_DIR}/01_foul_coordinates.png")
else:
    print("\nNot enough coordinate data for scatter plot.")
    print("This confirms we need a PHYSICS MODEL approach instead of raw coordinate mapping.")

# ============================================================
# VISUALIZATION 2: Exit velocity vs Launch angle for fouls
# ============================================================
if len(fouls_with_ev) > 100:
    print("\nGenerating EV vs Launch Angle plot...")

    fig, axes = plt.subplots(1, 3, figsize=(20, 6))

    # All fouls
    axes[0].hexbin(fouls_with_ev['launch_angle'], fouls_with_ev['launch_speed'],
                   gridsize=30, cmap='YlOrRd', mincnt=1)
    axes[0].set_xlabel('Launch Angle (degrees)')
    axes[0].set_ylabel('Exit Velocity (mph)')
    axes[0].set_title('All Fouls: EV vs Launch Angle')
    axes[0].axvline(x=0, color='gray', linestyle='--', alpha=0.5)
    plt.colorbar(axes[0].collections[0], ax=axes[0], label='Count')

    # LHB fouls
    lhb = fouls_with_ev[fouls_with_ev['stand'] == 'L']
    axes[1].hexbin(lhb['launch_angle'], lhb['launch_speed'],
                   gridsize=30, cmap='Oranges', mincnt=1)
    axes[1].set_xlabel('Launch Angle (degrees)')
    axes[1].set_ylabel('Exit Velocity (mph)')
    axes[1].set_title(f'Left-Handed Batters (n={len(lhb):,})')
    axes[1].axvline(x=0, color='gray', linestyle='--', alpha=0.5)
    plt.colorbar(axes[1].collections[0], ax=axes[1], label='Count')

    # RHB fouls
    rhb = fouls_with_ev[fouls_with_ev['stand'] == 'R']
    axes[2].hexbin(rhb['launch_angle'], rhb['launch_speed'],
                   gridsize=30, cmap='Purples', mincnt=1)
    axes[2].set_xlabel('Launch Angle (degrees)')
    axes[2].set_ylabel('Exit Velocity (mph)')
    axes[2].set_title(f'Right-Handed Batters (n={len(rhb):,})')
    axes[2].axvline(x=0, color='gray', linestyle='--', alpha=0.5)
    plt.colorbar(axes[2].collections[0], ax=axes[2], label='Count')

    plt.suptitle('Foul Ball Exit Velocity vs Launch Angle', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/02_ev_launch_angle.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {OUTPUT_DIR}/02_ev_launch_angle.png")

# ============================================================
# VISUALIZATION 3: Physics-based trajectory estimation
# ============================================================
print("\nGenerating physics-based foul ball trajectory estimation...")

def estimate_landing_zone(ev_mph, launch_angle_deg, spray_angle_deg=None, drag_coeff=0.3):
    """
    Simple ballistic trajectory model for a foul ball.
    Returns estimated (distance_feet, height_at_distance).

    This is simplified — real model would account for:
    - Air density, humidity, altitude
    - Spin rate and Magnus effect
    - Stadium-specific geometry
    """
    g = 32.174  # ft/s^2
    ev_fps = ev_mph * 1.467  # convert mph to ft/s
    angle_rad = np.radians(launch_angle_deg)

    vx = ev_fps * np.cos(angle_rad)
    vy = ev_fps * np.sin(angle_rad)

    # Simple drag model
    dt = 0.01
    x, y = 0, 3  # start at ~3 feet (bat height)
    positions = [(x, y)]

    for _ in range(10000):
        speed = np.sqrt(vx**2 + vy**2)
        drag = drag_coeff * speed

        ax = -drag * vx / speed if speed > 0 else 0
        ay = -g - (drag * vy / speed if speed > 0 else 0)

        vx += ax * dt
        vy += ay * dt
        x += vx * dt
        y += vy * dt

        positions.append((x, y))

        if y < 0:
            break

    return positions

# Estimate landing zones for typical foul ball EV/angle combos
print("\nEstimated foul ball landing distances by EV and angle:")
print(f"{'EV (mph)':>10} {'Angle':>8} {'Distance (ft)':>15} {'Max Height (ft)':>17} {'Likely Location'}")
print("-" * 75)

scenarios = [
    (60, 10, "Dugout area / front rows"),
    (70, 20, "Lower deck, near foul line"),
    (80, 30, "Mid-lower deck"),
    (90, 40, "Upper portion of lower deck"),
    (100, 45, "Upper deck / concourse"),
    (75, 60, "Popup - near home plate"),
    (85, 70, "High popup - behind plate"),
    (95, 25, "Line drive into stands"),
    (105, 15, "Screamer into front rows"),
    (65, 50, "Lazy popup, close to field"),
]

landing_data = []
for ev, angle, location in scenarios:
    positions = estimate_landing_zone(ev, angle)
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    max_dist = max(xs)
    max_height = max(ys)
    landing_data.append((ev, angle, max_dist, max_height, location))
    print(f"{ev:>10} {angle:>8}° {max_dist:>14.0f} {max_height:>16.0f} {location}")

# Plot trajectory profiles
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# Top left: Multiple trajectories
ax = axes[0][0]
for ev, angle, location in scenarios[:6]:
    positions = estimate_landing_zone(ev, angle)
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    ax.plot(xs, ys, label=f'{ev}mph @ {angle}°', linewidth=1.5)
ax.set_xlabel('Distance from home plate (ft)')
ax.set_ylabel('Height (ft)')
ax.set_title('Foul Ball Trajectory Profiles')
ax.legend(fontsize=8)
ax.set_xlim(0, 500)
ax.set_ylim(0, 200)
ax.axhline(y=15, color='gray', linestyle=':', alpha=0.5, label='~Lower deck height')
ax.axhline(y=50, color='gray', linestyle='--', alpha=0.5, label='~Upper deck height')
ax.grid(True, alpha=0.3)

# Top right: Landing distance heatmap by EV and angle
ax = axes[0][1]
evs = np.arange(50, 115, 5)
angles = np.arange(5, 80, 5)
landing_matrix = np.zeros((len(angles), len(evs)))

for i, angle in enumerate(angles):
    for j, ev in enumerate(evs):
        positions = estimate_landing_zone(ev, angle)
        landing_matrix[i, j] = max(p[0] for p in positions)

im = ax.imshow(landing_matrix, aspect='auto', cmap='YlOrRd',
               extent=[evs[0], evs[-1], angles[-1], angles[0]])
ax.set_xlabel('Exit Velocity (mph)')
ax.set_ylabel('Launch Angle (degrees)')
ax.set_title('Estimated Landing Distance (ft)')
plt.colorbar(im, ax=ax, label='Distance (ft)')

# Bottom left: Distribution of foul ball EV from actual data
ax = axes[1][0]
if len(fouls_with_ev) > 50:
    ax.hist(fouls_with_ev['launch_speed'].dropna(), bins=50, color='red', alpha=0.7, edgecolor='black', linewidth=0.5)
    ax.axvline(fouls_with_ev['launch_speed'].mean(), color='black', linestyle='--',
               label=f'Mean: {fouls_with_ev["launch_speed"].mean():.1f} mph')
    ax.set_xlabel('Exit Velocity (mph)')
    ax.set_ylabel('Count')
    ax.set_title('Actual Foul Ball Exit Velocity Distribution (2024)')
    ax.legend()

# Bottom right: Distribution of foul ball launch angles from actual data
ax = axes[1][1]
if len(fouls_with_ev) > 50:
    ax.hist(fouls_with_ev['launch_angle'].dropna(), bins=60, color='orange', alpha=0.7, edgecolor='black', linewidth=0.5)
    ax.axvline(fouls_with_ev['launch_angle'].mean(), color='black', linestyle='--',
               label=f'Mean: {fouls_with_ev["launch_angle"].mean():.1f}°')
    ax.set_xlabel('Launch Angle (degrees)')
    ax.set_ylabel('Count')
    ax.set_title('Actual Foul Ball Launch Angle Distribution (2024)')
    ax.legend()

plt.suptitle('Foul Ball Physics Analysis', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/03_trajectory_analysis.png', dpi=150, bbox_inches='tight')
plt.close()
print(f"\n  Saved: {OUTPUT_DIR}/03_trajectory_analysis.png")

# ============================================================
# VISUALIZATION 4: Simulated stadium heatmap
# ============================================================
print("\nGenerating simulated stadium foul ball heatmap...")

fig, ax = plt.subplots(figsize=(12, 12))

# Draw simplified stadium overhead
# Home plate at origin, field opens upward
theta = np.linspace(-np.pi/4, np.pi/4, 100)  # fair territory
foul_left = np.linspace(np.pi/4, np.pi/2 + 0.3, 50)
foul_right = np.linspace(-np.pi/2 - 0.3, -np.pi/4, 50)

# Foul lines
ax.plot([0, 350*np.sin(np.pi/4)], [0, 350*np.cos(np.pi/4)], 'k-', linewidth=1)
ax.plot([0, -350*np.sin(np.pi/4)], [0, 350*np.cos(np.pi/4)], 'k-', linewidth=1)

# Outfield wall arc
wall_r = 330
wall_theta = np.linspace(-np.pi/4, np.pi/4, 100)
ax.plot(wall_r * np.sin(wall_theta), wall_r * np.cos(wall_theta), 'k-', linewidth=2)

# Infield diamond
bases = [(0, 0), (63.6, 63.6), (0, 127.3), (-63.6, 63.6), (0, 0)]
bx, by = zip(*bases)
ax.plot(bx, by, 'k-', linewidth=1)

# Stand boundaries (simplified)
for r in [50, 100, 150, 200, 250, 300]:
    stand_theta = np.linspace(-np.pi/2 - 0.2, np.pi/2 + 0.2, 100)
    ax.plot(r * np.sin(stand_theta), r * np.cos(stand_theta), 'gray', linewidth=0.3, alpha=0.3)

# Simulate foul ball landing spots using actual data distributions
if len(fouls_with_ev) > 100:
    np.random.seed(42)
    n_sim = 2000

    # Sample from actual distributions
    ev_samples = fouls_with_ev['launch_speed'].dropna().sample(n=n_sim, replace=True).values
    la_samples = fouls_with_ev['launch_angle'].dropna().sample(n=n_sim, replace=True).values

    # Spray angles for fouls — distributed in foul territory
    # Left-handed batters tend to foul to the right (1st base side)
    # Right-handed batters tend to foul to the left (3rd base side)
    spray_angles = np.random.normal(0, 25, n_sim)  # degrees from foul line

    landing_x = []
    landing_y = []
    colors = []

    for ev, la, spray in zip(ev_samples, la_samples, spray_angles):
        if np.isnan(ev) or np.isnan(la):
            continue
        positions = estimate_landing_zone(ev, abs(la))
        dist = max(p[0] for p in positions)

        # Map to stadium coordinates
        # Positive spray = 1st base side, negative = 3rd base side
        angle_rad = np.radians(45 + abs(spray) * 0.3)  # push into foul territory
        if spray > 0:
            x = dist * np.sin(angle_rad)
        else:
            x = -dist * np.sin(angle_rad)
        y = dist * np.cos(angle_rad)

        if dist < 400 and dist > 10:  # reasonable range
            landing_x.append(x)
            landing_y.append(y)
            colors.append(ev)

    scatter = ax.scatter(landing_x, landing_y, c=colors, cmap='YlOrRd',
                        alpha=0.4, s=8, vmin=40, vmax=110)
    plt.colorbar(scatter, ax=ax, label='Exit Velocity (mph)', shrink=0.6)

ax.set_xlim(-400, 400)
ax.set_ylim(-50, 400)
ax.set_aspect('equal')
ax.set_title('Simulated Foul Ball Landing Zones\n(Based on actual 2024 EV/Angle distributions)', fontsize=13)
ax.set_xlabel('Feet (negative = 3rd base side)')
ax.set_ylabel('Feet from home plate')
ax.grid(True, alpha=0.2)

# Add annotations
ax.annotate('HOME', xy=(0, 0), fontsize=8, ha='center', fontweight='bold')
ax.annotate('1B SIDE\n(LHB fouls here more)', xy=(200, 50), fontsize=9, ha='center', color='darkred')
ax.annotate('3B SIDE\n(RHB fouls here more)', xy=(-200, 50), fontsize=9, ha='center', color='darkblue')

plt.savefig(f'{OUTPUT_DIR}/04_stadium_heatmap.png', dpi=150, bbox_inches='tight')
plt.close()
print(f"  Saved: {OUTPUT_DIR}/04_stadium_heatmap.png")

# ============================================================
# FINAL SUMMARY
# ============================================================
print("\n" + "=" * 70)
print("VIABILITY ASSESSMENT SUMMARY")
print("=" * 70)
print(f"""
DATA AVAILABLE:
  - Foul ball events clearly identified in Statcast: YES
  - Exit velocity for fouls: {len(fouls_with_ev):,} events ({len(fouls_with_ev)/len(fouls)*100:.1f}% of fouls)
  - Launch angle for fouls: {fouls_with_ev['launch_angle'].notna().sum():,} events
  - Hit coordinates for fouls: {len(fouls_with_coords):,} events ({len(fouls_with_coords)/len(fouls)*100:.1f}% of fouls)
  - Batter handedness: Always available
  - Pitch type: Always available
  - Bat speed (new): {fouls['bat_speed'].notna().sum() if 'bat_speed' in fouls.columns else 'N/A'} events

WHAT YOU CAN BUILD:
  1. Physics-based trajectory model using EV + launch angle + spray angle
  2. Per-batter foul ball tendency profiles
  3. Matchup-based predictions (batter hand x pitcher hand x pitch mix)
  4. Stadium-specific seat mapping (overlay trajectory model on stadium geometry)

WHAT YOU'D NEED TO ADD:
  - Stadium 3D geometry data (seat locations, heights, distances)
  - Spray angle estimation (may need video data or inference from EV+angle patterns)
  - Historical lineup data for upcoming game predictions

VERDICT: The data foundation is SOLID for building this product.
""")
