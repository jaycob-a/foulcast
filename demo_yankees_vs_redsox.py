"""
FOUL BALL PREDICTOR DEMO
========================
Yankees vs Red Sox at Yankee Stadium

Simulates a full game's foul ball distribution based on:
- Each batter's historical foul ball tendencies (EV, launch angle distributions)
- The opposing pitcher's pitch mix
- 3D ballistic trajectory physics (gravity, drag, altitude)
- Yankee Stadium's actual geometry and seat sections

Outputs:
1. Console report: top sections ranked by foul ball probability
2. Stadium heatmap visualization
3. Per-batter foul ball tendency chart
4. Section-by-section breakdown with ticket price context
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Arc, FancyBboxPatch, Wedge
from matplotlib.collections import PatchCollection

from foulball.batter_profiles import (
    YANKEES_2024_PROFILES, RED_SOX_2024_PROFILES, PITCHER_PROFILES
)
from foulball.stadium import yankee_stadium, fenway_park
from foulball.matchup_engine import predict_game_fouls, GamePrediction
from foulball.trajectory import simulate_foul_ball

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

np.random.seed(42)

def print_header(text, char='='):
    print(f"\n{char * 70}")
    print(text)
    print(char * 70)


def run_game_prediction(
    lineup_profiles: dict,
    pitcher_name: str,
    stadium_fn,
    home_team: str,
    away_team: str,
    sims_per_batter: int = 500,
) -> GamePrediction:
    """Run a full game prediction."""
    pitcher = PITCHER_PROFILES[pitcher_name]
    stadium = stadium_fn()
    lineup = list(lineup_profiles.values())

    prediction = predict_game_fouls(
        lineup=lineup,
        pitcher_name=pitcher_name,
        pitcher_pitch_mix=pitcher['pitch_mix'],
        pitcher_hand=pitcher['hand'],
        stadium=stadium,
        simulations_per_batter=sims_per_batter,
    )
    prediction.away_team = away_team
    return prediction


def print_prediction_report(pred: GamePrediction):
    """Print a detailed console report."""
    print_header(f"FOUL BALL FORECAST: {pred.away_team} @ {pred.home_team}")
    print(f"Stadium: {pred.stadium_name}")
    print(f"Opposing Pitcher: {pred.pitcher_name}")
    print(f"Simulated foul balls: {pred.total_simulated_fouls:,}")

    expected_total = sum(p.expected_fouls for p in pred.section_predictions)
    print(f"Expected fouls reaching stands: ~{expected_total:.0f}")

    # Top 10 sections
    print_header("TOP 10 SECTIONS — Best Seats for Catching a Foul Ball", '-')
    print(f"{'Rank':<5} {'Section':<30} {'Side':<5} {'Level':<8} "
          f"{'Expected':>9} {'Catch%':>7} {'AvgEV':>7} {'Danger':>7} {'Price':>7}")
    print("-" * 88)

    for i, sp in enumerate(pred.top_sections[:10], 1):
        sec = sp.section
        catch_pct = sp.catchable_fouls / sp.expected_fouls * 100 if sp.expected_fouls > 0 else 0
        danger_bar = '!' * int(sp.danger_rating)
        price_str = f"${sec.avg_ticket_price}" if sec.avg_ticket_price > 0 else "N/A"

        print(f"{i:<5} {sec.name:<30} {sec.side:<5} {sec.level:<8} "
              f"{sp.expected_fouls:>8.1f} {catch_pct:>6.0f}% {sp.avg_exit_velocity:>6.1f} "
              f"{danger_bar:<7} {price_str:>7}")

    # Best value (fouls per dollar)
    print_header("BEST VALUE — Most Fouls Per Dollar", '-')
    valued = [sp for sp in pred.section_predictions
              if sp.section.avg_ticket_price > 0 and sp.expected_fouls > 0.05]
    valued.sort(key=lambda sp: sp.catchable_fouls / sp.section.avg_ticket_price, reverse=True)

    print(f"{'Section':<30} {'Price':>7} {'Fouls':>7} {'Catchable':>10} {'Fouls/$':>10}")
    print("-" * 68)
    for sp in valued[:8]:
        sec = sp.section
        ratio = sp.catchable_fouls / sec.avg_ticket_price * 1000
        print(f"{sec.name:<30} ${sec.avg_ticket_price:>5.0f} {sp.expected_fouls:>6.1f} "
              f"{sp.catchable_fouls:>9.1f} {ratio:>9.2f}")

    # Per-batter breakdown
    print_header("PER-BATTER FOUL BALL BREAKDOWN", '-')
    batter_events: dict[str, list] = {}
    for e in pred.all_events:
        if e.batter_name not in batter_events:
            batter_events[e.batter_name] = []
        batter_events[e.batter_name].append(e)

    print(f"{'Batter':<25} {'Side':>4} {'Fouls':>6} {'AvgEV':>7} {'AvgLA':>7} "
          f"{'1B%':>5} {'3B%':>5} {'Catchable%':>11}")
    print("-" * 75)
    for name, events in sorted(batter_events.items(), key=lambda x: -len(x[1])):
        evs = [e.exit_velocity for e in events]
        las = [e.launch_angle for e in events]
        pct_1b = sum(1 for e in events if e.landing_side == '1B') / len(events) * 100
        pct_3b = sum(1 for e in events if e.landing_side == '3B') / len(events) * 100
        pct_catch = sum(1 for e in events if e.is_catchable) / len(events) * 100
        side = events[0].batter_side
        print(f"{name:<25} {side:>4} {len(events):>6} {np.mean(evs):>6.1f} {np.mean(las):>6.1f} "
              f"{pct_1b:>4.0f}% {pct_3b:>4.0f}% {pct_catch:>10.0f}%")

    # Danger zones warning
    print_header("DANGER ZONES — Watch Out for Line Drives!", '-')
    dangerous = [sp for sp in pred.section_predictions if sp.danger_rating > 7]
    dangerous.sort(key=lambda sp: sp.danger_rating, reverse=True)
    if dangerous:
        for sp in dangerous[:5]:
            print(f"  {sp.section.name}: avg {sp.avg_exit_velocity:.0f} mph "
                  f"(danger: {'!' * int(sp.danger_rating)})")
    else:
        print("  No extremely dangerous sections identified.")
    print("  TIP: Bring a glove to field-level seats. Fouls off fastballs")
    print("  can reach 100+ mph with under 2 seconds of reaction time.")


def plot_stadium_heatmap(pred: GamePrediction, filename: str):
    """Generate a stadium overhead heatmap showing foul ball hot zones."""
    fig, ax = plt.subplots(figsize=(14, 14))

    # Draw field
    theta = np.linspace(-np.pi/4, np.pi/4, 100)
    wall_r = 330

    # Outfield wall
    ax.plot(wall_r * np.sin(theta), wall_r * np.cos(theta), 'k-', linewidth=2)
    # Foul lines
    ax.plot([0, 330*np.sin(np.pi/4)], [0, 330*np.cos(np.pi/4)], 'k-', linewidth=1.5)
    ax.plot([0, -330*np.sin(np.pi/4)], [0, 330*np.cos(np.pi/4)], 'k-', linewidth=1.5)
    # Infield diamond
    bases = [(0, 0), (63.6, 63.6), (0, 127.3), (-63.6, 63.6), (0, 0)]
    bx, by = zip(*bases)
    ax.plot(bx, by, 'k-', linewidth=1)
    # Infield arc
    arc_theta = np.linspace(-np.pi/4, np.pi/4, 50)
    ax.plot(95 * np.sin(arc_theta), 95 * np.cos(arc_theta), 'k-', linewidth=0.5, alpha=0.5)

    # Stand boundary arcs
    for r in [50, 100, 150, 200, 250, 300, 350]:
        stand_theta = np.linspace(-np.pi/2 - 0.3, np.pi/2 + 0.3, 100)
        ax.plot(r * np.sin(stand_theta), r * np.cos(stand_theta), 'gray', linewidth=0.3, alpha=0.2)

    # Plot all simulated foul balls
    xs_1b, ys_1b, evs_1b = [], [], []
    xs_3b, ys_3b, evs_3b = [], [], []

    for event in pred.all_events:
        traj = event.trajectory
        dist = event.landing_distance
        if dist < 5 or dist > 400:
            continue

        # Convert to overhead coordinates
        angle_from_foul_line = np.arctan2(abs(traj.landing_y), abs(traj.landing_x))
        # Push into foul territory (past the foul line)
        if event.landing_side == '1B':
            total_angle = np.pi/4 + angle_from_foul_line * 0.8
            x = dist * np.sin(total_angle)
            y = dist * np.cos(total_angle)
            xs_1b.append(x)
            ys_1b.append(y)
            evs_1b.append(event.exit_velocity)
        else:
            total_angle = np.pi/4 + angle_from_foul_line * 0.8
            x = -dist * np.sin(total_angle)
            y = dist * np.cos(total_angle)
            xs_3b.append(x)
            ys_3b.append(y)
            evs_3b.append(event.exit_velocity)

    # Plot with color by EV
    all_xs = xs_1b + xs_3b
    all_ys = ys_1b + ys_3b
    all_evs = evs_1b + evs_3b

    if all_xs:
        scatter = ax.scatter(all_xs, all_ys, c=all_evs, cmap='YlOrRd',
                           alpha=0.35, s=10, vmin=40, vmax=110, zorder=3)
        cbar = plt.colorbar(scatter, ax=ax, shrink=0.5, label='Exit Velocity (mph)')

    # Highlight top sections
    for i, sp in enumerate(pred.top_sections[:5]):
        sec = sp.section
        # Draw approximate section boundary
        mid_dist = (sec.distance_min + sec.distance_max) / 2
        mid_angle = (sec.angle_min + sec.angle_max) / 2

        if sec.side == '1B':
            total_angle = np.pi/4 + np.radians(mid_angle) * 0.8
            sx = mid_dist * np.sin(total_angle)
            sy = mid_dist * np.cos(total_angle)
        elif sec.side == '3B':
            total_angle = np.pi/4 + np.radians(mid_angle) * 0.8
            sx = -mid_dist * np.sin(total_angle)
            sy = mid_dist * np.cos(total_angle)
        else:  # HOME
            sx = 0
            sy = -mid_dist * 0.3

        ax.annotate(f"#{i+1}\n{sec.name}\n({sp.expected_fouls:.1f} fouls)",
                   xy=(sx, sy), fontsize=7, ha='center', fontweight='bold',
                   color='darkred',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.85, edgecolor='red'))

    # Labels
    ax.annotate('HOME', xy=(0, -8), fontsize=9, ha='center', fontweight='bold')
    ax.annotate('1B SIDE\n(LHB fouls here more)', xy=(220, 30), fontsize=9,
               ha='center', color='darkred', fontweight='bold')
    ax.annotate('3B SIDE\n(RHB fouls here more)', xy=(-220, 30), fontsize=9,
               ha='center', color='darkblue', fontweight='bold')

    ax.set_xlim(-420, 420)
    ax.set_ylim(-80, 420)
    ax.set_aspect('equal')

    title_lines = [
        f"Foul Ball Hot Zone Forecast",
        f"{pred.away_team} @ {pred.home_team} | {pred.stadium_name}",
        f"vs {pred.pitcher_name} | {len(pred.all_events):,} simulated fouls"
    ]
    ax.set_title('\n'.join(title_lines), fontsize=13, fontweight='bold')
    ax.set_xlabel('Feet (negative = 3rd base side, positive = 1st base side)')
    ax.set_ylabel('Feet from home plate')
    ax.grid(True, alpha=0.15)

    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {filename}")


def plot_batter_breakdown(pred: GamePrediction, filename: str):
    """Generate per-batter foul ball visualization."""
    batter_events: dict[str, list] = {}
    for e in pred.all_events:
        if e.batter_name not in batter_events:
            batter_events[e.batter_name] = []
        batter_events[e.batter_name].append(e)

    batters = sorted(batter_events.keys(), key=lambda n: -len(batter_events[n]))
    n_batters = len(batters)

    fig, axes = plt.subplots(3, 3, figsize=(18, 16))
    axes = axes.flatten()

    for i, name in enumerate(batters[:9]):
        ax = axes[i]
        events = batter_events[name]
        evs = [e.exit_velocity for e in events]
        las = [e.launch_angle for e in events]
        sides = [e.landing_side for e in events]

        colors = ['#e74c3c' if s == '3B' else '#3498db' for s in sides]
        ax.scatter(las, evs, c=colors, alpha=0.25, s=8)

        ax.set_xlim(-90, 90)
        ax.set_ylim(0, 120)
        ax.set_xlabel('Launch Angle')
        ax.set_ylabel('Exit Velocity (mph)')

        side = events[0].batter_side
        pct_1b = sum(1 for e in events if e.landing_side == '1B') / len(events) * 100
        pct_3b = 100 - pct_1b
        catchable = sum(1 for e in events if e.is_catchable) / len(events) * 100

        ax.set_title(f"{name} ({side}HB)\n"
                    f"3B: {pct_3b:.0f}% | 1B: {pct_1b:.0f}% | Catchable: {catchable:.0f}%",
                    fontsize=10, fontweight='bold')
        ax.axvline(x=0, color='gray', linestyle='--', alpha=0.3)

    # Hide unused axes
    for i in range(len(batters), 9):
        axes[i].set_visible(False)

    # Legend
    legend_elements = [
        mpatches.Patch(facecolor='#e74c3c', alpha=0.5, label='3B side (RHB pull)'),
        mpatches.Patch(facecolor='#3498db', alpha=0.5, label='1B side (LHB pull)'),
    ]
    fig.legend(handles=legend_elements, loc='lower center', ncol=2, fontsize=11)

    plt.suptitle(f"Per-Batter Foul Ball Profiles — {pred.away_team} @ {pred.home_team}",
                fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {filename}")


def plot_section_rankings(pred: GamePrediction, filename: str):
    """Bar chart of top sections."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))

    top = pred.top_sections[:12]

    # Left: Expected catchable fouls
    names = [f"{sp.section.name}\n({sp.section.side})" for sp in top]
    values = [sp.catchable_fouls for sp in top]
    colors = ['#e74c3c' if '3B' in sp.section.side else '#3498db' if '1B' in sp.section.side else '#2ecc71'
              for sp in top]

    bars = ax1.barh(range(len(top)-1, -1, -1), values, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)
    ax1.set_yticks(range(len(top)-1, -1, -1))
    ax1.set_yticklabels(names, fontsize=9)
    ax1.set_xlabel('Expected Catchable Fouls Per Game')
    ax1.set_title('Top Sections by Catchable Foul Balls', fontweight='bold')

    # Add value labels
    for bar, val in zip(bars, values):
        ax1.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height()/2,
                f'{val:.2f}', va='center', fontsize=9)

    # Right: Value (fouls per dollar)
    valued = [sp for sp in pred.section_predictions
              if sp.section.avg_ticket_price > 0 and sp.catchable_fouls > 0.01]
    valued.sort(key=lambda sp: sp.catchable_fouls / sp.section.avg_ticket_price, reverse=True)
    valued = valued[:12]

    names2 = [f"{sp.section.name}\n(${sp.section.avg_ticket_price:.0f})" for sp in valued]
    values2 = [sp.catchable_fouls / sp.section.avg_ticket_price * 1000 for sp in valued]
    colors2 = ['#e74c3c' if '3B' in sp.section.side else '#3498db' if '1B' in sp.section.side else '#2ecc71'
               for sp in valued]

    bars2 = ax2.barh(range(len(valued)-1, -1, -1), values2, color=colors2, alpha=0.8,
                     edgecolor='black', linewidth=0.5)
    ax2.set_yticks(range(len(valued)-1, -1, -1))
    ax2.set_yticklabels(names2, fontsize=9)
    ax2.set_xlabel('Catchable Fouls per $1,000 Spent')
    ax2.set_title('Best Value Seats for Foul Balls', fontweight='bold')

    for bar, val in zip(bars2, values2):
        ax2.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height()/2,
                f'{val:.2f}', va='center', fontsize=9)

    legend_elements = [
        mpatches.Patch(facecolor='#e74c3c', alpha=0.8, label='3rd Base Side'),
        mpatches.Patch(facecolor='#3498db', alpha=0.8, label='1st Base Side'),
        mpatches.Patch(facecolor='#2ecc71', alpha=0.8, label='Behind Home Plate'),
    ]
    fig.legend(handles=legend_elements, loc='lower center', ncol=3, fontsize=11)

    plt.suptitle(f"Section Rankings — {pred.away_team} @ {pred.home_team} (vs {pred.pitcher_name})",
                fontsize=13, fontweight='bold')
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {filename}")


# ============================================================
# MAIN DEMO
# ============================================================
if __name__ == '__main__':
    print_header("FOUL BALL PREDICTOR v0.1")
    print("Powered by Statcast data + ballistic trajectory physics")

    # ---- GAME 1: Red Sox @ Yankees, Yankee Stadium ----
    # Red Sox batting against Gerrit Cole
    print_header("GAME 1: Red Sox @ Yankees (Yankee Stadium)")
    print("Red Sox lineup batting against Gerrit Cole (RHP)")

    pred1 = run_game_prediction(
        lineup_profiles=RED_SOX_2024_PROFILES,
        pitcher_name='Gerrit Cole',
        stadium_fn=yankee_stadium,
        home_team='New York Yankees',
        away_team='Boston Red Sox',
        sims_per_batter=500,
    )
    print_prediction_report(pred1)

    print("\nGenerating visualizations...")
    plot_stadium_heatmap(pred1, f'{OUTPUT_DIR}/game1_stadium_heatmap.png')
    plot_batter_breakdown(pred1, f'{OUTPUT_DIR}/game1_batter_breakdown.png')
    plot_section_rankings(pred1, f'{OUTPUT_DIR}/game1_section_rankings.png')

    # ---- GAME 2: Yankees @ Red Sox, Fenway Park ----
    # Yankees batting against Brayan Bello
    print_header("GAME 2: Yankees @ Red Sox (Fenway Park)")
    print("Yankees lineup batting against Brayan Bello (RHP)")

    pred2 = run_game_prediction(
        lineup_profiles=YANKEES_2024_PROFILES,
        pitcher_name='Brayan Bello',
        stadium_fn=fenway_park,
        home_team='Boston Red Sox',
        away_team='New York Yankees',
        sims_per_batter=500,
    )
    print_prediction_report(pred2)

    print("\nGenerating visualizations...")
    plot_stadium_heatmap(pred2, f'{OUTPUT_DIR}/game2_stadium_heatmap.png')
    plot_batter_breakdown(pred2, f'{OUTPUT_DIR}/game2_batter_breakdown.png')
    plot_section_rankings(pred2, f'{OUTPUT_DIR}/game2_section_rankings.png')

    # ---- COMPARISON ----
    print_header("HEAD-TO-HEAD COMPARISON: How Stadium Changes the Prediction")
    print(f"\n{'Metric':<35} {'Yankee Stadium':>16} {'Fenway Park':>16}")
    print("-" * 70)

    total1 = sum(p.expected_fouls for p in pred1.section_predictions)
    total2 = sum(p.expected_fouls for p in pred2.section_predictions)
    catch1 = sum(p.catchable_fouls for p in pred1.section_predictions)
    catch2 = sum(p.catchable_fouls for p in pred2.section_predictions)

    print(f"{'Expected fouls into stands':<35} {total1:>15.1f} {total2:>15.1f}")
    print(f"{'Catchable fouls':<35} {catch1:>15.1f} {catch2:>15.1f}")
    print(f"{'Best section (1B side)':<35} {pred1.top_sections[0].section.name:>16} {pred2.top_sections[0].section.name:>16}")

    # Top section for each
    best1 = max(pred1.section_predictions, key=lambda p: p.catchable_fouls)
    best2 = max(pred2.section_predictions, key=lambda p: p.catchable_fouls)
    print(f"{'#1 section fouls':<35} {best1.expected_fouls:>15.1f} {best2.expected_fouls:>15.1f}")
    print(f"{'#1 section price':<35} ${best1.section.avg_ticket_price:>14.0f} ${best2.section.avg_ticket_price:>14.0f}")

    print("\n" + "=" * 70)
    print("ALL VISUALIZATIONS SAVED TO:", OUTPUT_DIR)
    print("=" * 70)
    print("""
Files generated:
  game1_stadium_heatmap.png     — Overhead view: where fouls land (Yankee Stadium)
  game1_batter_breakdown.png    — Per-batter foul tendencies (Red Sox lineup)
  game1_section_rankings.png    — Best sections + best value seats
  game2_stadium_heatmap.png     — Overhead view: where fouls land (Fenway Park)
  game2_batter_breakdown.png    — Per-batter foul tendencies (Yankees lineup)
  game2_section_rankings.png    — Best sections + best value seats
""")
