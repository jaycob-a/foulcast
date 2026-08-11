#!/usr/bin/env python3
"""
FOUL BALL PREDICTOR — Predict any MLB game.

Usage:
    python predict.py                          # Show today's games, pick one
    python predict.py --date 2024-07-04        # Show games for a specific date
    python predict.py --teams NYY BOS          # Predict Yankees vs Red Sox
    python predict.py --game-id 745726         # Predict a specific game
    python predict.py --live                   # Pull real Statcast data (slower, more accurate)
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from foulball.mlb_api import (
    get_todays_games, get_projected_lineup, get_player_info,
    get_pitcher_info, TEAM_IDS, TEAM_ID_TO_ABBREV, TEAM_STADIUM_MAP, GameInfo,
)
from foulball.stadium import STADIUMS
from foulball.batter_profiles import BatterFoulProfile, PITCHER_PROFILES
from foulball.matchup_engine import predict_game_fouls, GamePrediction
from foulball.trajectory import simulate_foul_ball
from foulball.live_profiles import enrich_with_spray_profiles

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def print_header(text, char='=', width=72):
    print(f"\n{char * width}")
    print(text)
    print(char * width)


def show_games(games: list[GameInfo]) -> GameInfo | None:
    """Display available games and let user pick one."""
    if not games:
        print("No games found for this date.")
        return None

    print_header("AVAILABLE GAMES")
    for i, g in enumerate(games, 1):
        status = f"[{g.status}]" if g.status != 'Scheduled' else ''
        print(f"  {i:>2}. {g.away_team:<25} @ {g.home_team:<25} {status}")
        print(f"      Pitchers: {g.away_pitcher} vs {g.home_pitcher}")
        print(f"      Venue: {g.venue_name}")
        print()

    while True:
        try:
            choice = input(f"Pick a game (1-{len(games)}), or 'q' to quit: ").strip()
            if choice.lower() == 'q':
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(games):
                return games[idx]
        except (ValueError, EOFError):
            return games[0] if games else None


def build_lineup_profiles(team_id: int, use_live: bool = False) -> list[BatterFoulProfile]:
    """Build batter profiles for a team's lineup."""
    print(f"\n  Building lineup for team {team_id}...")
    lineup_players = get_projected_lineup(team_id)

    if use_live:
        # Pull real Statcast data
        from foulball.live_profiles import pull_live_profiles
        player_ids = [p.mlb_id for p in lineup_players]
        player_names = {p.mlb_id: p.name for p in lineup_players}
        player_sides = {p.mlb_id: p.bats for p in lineup_players}

        profiles_dict = pull_live_profiles(
            player_ids=player_ids,
            player_names=player_names,
            player_sides=player_sides,
        )
        return [profiles_dict[pid] for pid in player_ids if pid in profiles_dict]
    else:
        # Build quick profiles from player metadata
        profiles = []
        profiles_by_id = {}
        for p in lineup_players[:9]:
            profile = BatterFoulProfile(
                player_name=p.name,
                player_id=p.mlb_id,
                batter_side=p.bats if p.bats != 'S' else 'L',  # Switch hitters default to L side
            )
            # Adjust EV slightly by batting side tendencies
            if p.bats == 'L':
                profile.la_mean = 21.0
            profiles.append(profile)
            profiles_by_id[p.mlb_id] = profile
            print(f"    {p.batting_order}. {p.name} ({p.bats}HB) - {p.position}")

        # Enrich with per-batter spray angle data from cache
        enrich_with_spray_profiles(profiles_by_id)
        return profiles


def get_pitcher_pitch_mix(pitcher_name: str, pitcher_team_id: int, use_live: bool = False) -> tuple[dict, str]:
    """Get pitcher's pitch mix and throwing hand."""
    # Check hardcoded profiles first
    if pitcher_name in PITCHER_PROFILES:
        p = PITCHER_PROFILES[pitcher_name]
        return p['pitch_mix'], p['hand']

    if use_live:
        # Try to build from Statcast
        from foulball.live_profiles import build_pitcher_profile_from_statcast
        info = get_pitcher_info(pitcher_name, pitcher_team_id)
        if info.get('id'):
            profile = build_pitcher_profile_from_statcast(pitcher_name, info['id'])
            return profile['pitch_mix'], profile['hand']

    # Default pitch mix
    info = get_pitcher_info(pitcher_name, pitcher_team_id)
    hand = info.get('throws', 'R')
    default_mix = {'FF': 0.30, 'SL': 0.20, 'CH': 0.15, 'SI': 0.15, 'CU': 0.10, 'FC': 0.10}
    print(f"  Using default pitch mix for {pitcher_name} ({hand}HP)")
    return default_mix, hand


def run_prediction(game: GameInfo, use_live: bool = False, sims: int = 500) -> tuple[GamePrediction, GamePrediction]:
    """Run full prediction for both halves of a game."""
    # Get stadium
    stadium_key = game.stadium_key
    if stadium_key not in STADIUMS:
        print(f"  Stadium '{stadium_key}' not found, using Yankee Stadium as default")
        stadium_key = 'yankee_stadium'
    stadium_fn = STADIUMS[stadium_key]
    stadium = stadium_fn()

    print_header(f"PREDICTING: {game.away_team} @ {game.home_team}")
    print(f"Venue: {game.venue_name} ({stadium.name})")
    print(f"Altitude: {stadium.altitude_ft} ft | Avg temp: {stadium.avg_temperature_f}°F")

    # === TOP OF INNINGS: Away team batting ===
    print(f"\n--- Away team batting ({game.away_team}) vs {game.home_pitcher} ---")
    away_lineup = build_lineup_profiles(game.away_team_id, use_live)
    home_pitch_mix, home_hand = get_pitcher_pitch_mix(game.home_pitcher, game.home_team_id, use_live)

    pred_away = predict_game_fouls(
        lineup=away_lineup,
        pitcher_name=game.home_pitcher,
        pitcher_pitch_mix=home_pitch_mix,
        pitcher_hand=home_hand,
        stadium=stadium,
        simulations_per_batter=sims,
    )
    pred_away.away_team = game.away_team
    pred_away.home_team = game.home_team

    # === BOTTOM OF INNINGS: Home team batting ===
    print(f"\n--- Home team batting ({game.home_team}) vs {game.away_pitcher} ---")
    home_lineup = build_lineup_profiles(game.home_team_id, use_live)
    away_pitch_mix, away_hand = get_pitcher_pitch_mix(game.away_pitcher, game.away_team_id, use_live)

    pred_home = predict_game_fouls(
        lineup=home_lineup,
        pitcher_name=game.away_pitcher,
        pitcher_pitch_mix=away_pitch_mix,
        pitcher_hand=away_hand,
        stadium=stadium,
        simulations_per_batter=sims,
    )
    pred_home.away_team = game.away_team
    pred_home.home_team = game.home_team

    return pred_away, pred_home


def print_combined_report(pred_away: GamePrediction, pred_home: GamePrediction, game: GameInfo):
    """Print combined report for the full game."""
    print_header(f"FOUL BALL FORECAST: {game.away_team} @ {game.home_team}")
    print(f"Stadium: {pred_away.stadium_name}")
    print(f"Matchup: {game.away_pitcher} vs {game.home_pitcher}")

    # Combine section predictions from both halves
    combined_sections: dict[str, dict] = {}
    for pred, label in [(pred_away, 'away'), (pred_home, 'home')]:
        for sp in pred.section_predictions:
            sid = sp.section.section_id
            if sid not in combined_sections:
                combined_sections[sid] = {
                    'section': sp.section,
                    'expected_fouls': 0,
                    'catchable_fouls': 0,
                    'total_ev': 0,
                    'ev_count': 0,
                    'danger': 0,
                    'batters': set(),
                    'netting': sp.netting,
                }
            combined_sections[sid]['expected_fouls'] += sp.expected_fouls
            combined_sections[sid]['catchable_fouls'] += sp.catchable_fouls
            combined_sections[sid]['total_ev'] += sp.avg_exit_velocity * sp.expected_fouls
            combined_sections[sid]['ev_count'] += sp.expected_fouls
            combined_sections[sid]['danger'] = max(combined_sections[sid]['danger'], sp.danger_rating)
            combined_sections[sid]['batters'].update(sp.top_batters)

    # Sort by catchable fouls. Sections published as fully behind netting are
    # split out first: they still take fouls, but not catchable ones, so they
    # belong in the safety block below and nowhere in this ranking.
    def _netted(r):
        return r['netting'] is not None and r['netting'].blocks_catch

    netted_rows = [r for r in combined_sections.values() if _netted(r)]
    ranked = sorted((r for r in combined_sections.values() if not _netted(r)),
                    key=lambda x: x['catchable_fouls'], reverse=True)
    netted_rows.sort(key=lambda r: r['expected_fouls'], reverse=True)

    total_fouls = sum(r['expected_fouls'] for r in combined_sections.values())
    total_catchable = sum(r['catchable_fouls'] for r in ranked)
    total_netted = sum(r['expected_fouls'] for r in netted_rows)

    print(f"\nExpected fouls reaching stands: ~{total_fouls:.0f}")
    print(f"Expected catchable fouls: ~{total_catchable:.0f}")
    if netted_rows:
        print(f"Of which into netting (not catchable): ~{total_netted:.0f}")

    # Netting leads, and the ranking follows it. Where the net is, is
    # published; where the fouls go is this model's estimate. Nothing below
    # calls a section "safe" — the two statuses are behind netting and not
    # behind netting, and neither is a promise about a seat.
    _print_netting_block(pred_away, netted_rows)

    # Top sections
    print_header("TOP SEATS FOR CATCHING A FOUL BALL", '-')
    print(f"{'Rank':<5} {'Section':<30} {'Side':<5} {'Level':<8} "
          f"{'Fouls':>7} {'Catchable':>10} {'AvgEV':>7} {'Price':>7}  Netting")
    print("-" * 100)

    for i, r in enumerate(ranked[:12], 1):
        sec = r['section']
        avg_ev = r['total_ev'] / r['ev_count'] if r['ev_count'] > 0 else 0
        price_str = f"${sec.avg_ticket_price:.0f}"
        net = r['netting']
        if net is None or net.status == 'unknown':
            net_str = 'unpublished — cannot verify'
        elif net.status == 'partially_netted':
            net_str = 'PARTLY NETTED — upper bound'
        else:
            net_str = 'not netted'
        print(f"{i:<5} {sec.name:<30} {sec.side:<5} {sec.level:<8} "
              f"{r['expected_fouls']:>6.1f} {r['catchable_fouls']:>9.1f} "
              f"{avg_ev:>6.1f} {price_str:>7}  {net_str}")

    # Best value
    print_header("BEST VALUE — Most Foul Ball Chance Per Dollar", '-')
    valued = [r for r in ranked if r['section'].avg_ticket_price > 0 and r['catchable_fouls'] > 0.01]
    valued.sort(key=lambda r: r['catchable_fouls'] / r['section'].avg_ticket_price, reverse=True)

    print(f"{'Section':<30} {'Price':>7} {'Catchable':>10} {'Value Score':>12}")
    print("-" * 62)
    for r in valued[:8]:
        sec = r['section']
        value = r['catchable_fouls'] / sec.avg_ticket_price * 1000
        print(f"{sec.name:<30} ${sec.avg_ticket_price:>5.0f} {r['catchable_fouls']:>9.1f} {value:>11.1f}")

    # Side breakdown
    side_1b = sum(r['catchable_fouls'] for r in ranked if r['section'].side == '1B')
    side_3b = sum(r['catchable_fouls'] for r in ranked if r['section'].side == '3B')
    side_home = sum(r['catchable_fouls'] for r in ranked if r['section'].side == 'HOME')

    print_header("WHICH SIDE TO SIT ON?", '-')
    total_side = side_1b + side_3b + side_home
    if total_side > 0:
        print(f"  1st Base side: {side_1b:.1f} catchable fouls ({side_1b/total_side*100:.0f}%)")
        print(f"  3rd Base side: {side_3b:.1f} catchable fouls ({side_3b/total_side*100:.0f}%)")
        print(f"  Behind plate:  {side_home:.1f} catchable fouls ({side_home/total_side*100:.0f}%)")

        # Count lefties and righties
        away_lefties = sum(1 for e in pred_away.all_events[:100] if e.batter_side == 'L')
        home_lefties = sum(1 for e in pred_home.all_events[:100] if e.batter_side == 'L')
        total_sample = min(100, len(pred_away.all_events)) + min(100, len(pred_home.all_events))
        pct_lefty = (away_lefties + home_lefties) / total_sample * 100 if total_sample > 0 else 50

        if side_1b > side_3b * 1.15:
            print(f"\n  >>> RECOMMENDATION: Sit on the 1st BASE SIDE")
            print(f"      The lineups are {pct_lefty:.0f}% left-handed, pushing more fouls to 1B side")
        elif side_3b > side_1b * 1.15:
            print(f"\n  >>> RECOMMENDATION: Sit on the 3rd BASE SIDE")
            print(f"      The lineups are {100-pct_lefty:.0f}% right-handed, pushing more fouls to 3B side")
        else:
            print(f"\n  >>> Both sides are roughly equal for this matchup")

    # Danger zones. Netted sections are read the opposite way here from the
    # ranking above: excluded there because no one catches a ball through a
    # screen, listed first here because the screen is the safety story.
    print_header("DANGER ZONES — Bring a Glove!", '-')
    dangerous = [r for r in ranked if r['danger'] > 7 and r['section'].level == 'field']
    for r in dangerous[:5]:
        sec = r['section']
        avg_ev = r['total_ev'] / r['ev_count'] if r['ev_count'] > 0 else 0
        net = r['netting']
        tail = '' if net is not None and net.status != 'unknown' \
            else '  [netting at this section is unpublished]'
        print(f"  {sec.name}: avg {avg_ev:.0f} mph — reaction time < 2 sec{tail}")


def _print_netting_block(pred, netted_rows):
    """The netting panel. Printed before the ranking, on purpose.

    Netted sections are read here the opposite way from the ranking: excluded
    there because no one catches a ball through a screen, listed here because
    the screen is what is stopping those balls.
    """
    print_header("BEHIND PROTECTIVE NETTING", '-')
    if not netted_rows:
        print(f"  {pred.netting_note}")
        return

    park = netted_rows[0]['netting'].park
    print(f"  Published: {park.published}")
    print(f"  Height:    {park.height or 'not published'}")
    print(f"  Source:    {park.source} ({park.source_kind}, "
          f"{park.year if park.year is not None else 'undated'}, retrieved "
          f"{park.retrieved})")
    print()
    for r in netted_rows:
        sec = r['section']
        avg_ev = r['total_ev'] / r['ev_count'] if r['ev_count'] > 0 else 0
        print(f"  {sec.name:<32} {r['expected_fouls']:>5.1f} fouls/game, "
              f"avg {avg_ev:>3.0f} mph — behind netting")
    print()
    print(f"  {pred.netting_note}")


def plot_combined_heatmap(pred_away: GamePrediction, pred_home: GamePrediction, game: GameInfo, filename: str):
    """Combined heatmap from both halves of the game."""
    fig, ax = plt.subplots(figsize=(14, 14))

    # Draw field
    theta = np.linspace(-np.pi/4, np.pi/4, 100)
    wall_r = 330
    ax.plot(wall_r * np.sin(theta), wall_r * np.cos(theta), 'k-', linewidth=2)
    ax.plot([0, 330*np.sin(np.pi/4)], [0, 330*np.cos(np.pi/4)], 'k-', linewidth=1.5)
    ax.plot([0, -330*np.sin(np.pi/4)], [0, 330*np.cos(np.pi/4)], 'k-', linewidth=1.5)
    bases = [(0, 0), (63.6, 63.6), (0, 127.3), (-63.6, 63.6), (0, 0)]
    bx, by = zip(*bases)
    ax.plot(bx, by, 'k-', linewidth=1)
    for r in [50, 100, 150, 200, 250, 300, 350]:
        stand_theta = np.linspace(-np.pi/2 - 0.3, np.pi/2 + 0.3, 100)
        ax.plot(r * np.sin(stand_theta), r * np.cos(stand_theta), 'gray', linewidth=0.3, alpha=0.2)

    all_x, all_y, all_ev, all_side = [], [], [], []
    for pred in [pred_away, pred_home]:
        for event in pred.all_events:
            traj = event.trajectory
            dist = event.landing_distance
            if dist < 5 or dist > 400:
                continue
            angle = np.arctan2(abs(traj.landing_y), abs(traj.landing_x))
            total_angle = np.pi/4 + angle * 0.8
            if event.landing_side == '1B':
                x = dist * np.sin(total_angle)
            else:
                x = -dist * np.sin(total_angle)
            y = dist * np.cos(total_angle)
            all_x.append(x)
            all_y.append(y)
            all_ev.append(event.exit_velocity)

    if all_x:
        scatter = ax.scatter(all_x, all_y, c=all_ev, cmap='YlOrRd',
                           alpha=0.3, s=8, vmin=40, vmax=110, zorder=3)
        plt.colorbar(scatter, ax=ax, shrink=0.5, label='Exit Velocity (mph)')

    ax.annotate('HOME', xy=(0, -8), fontsize=9, ha='center', fontweight='bold')
    ax.annotate('1B SIDE', xy=(220, 30), fontsize=10, ha='center', color='darkred', fontweight='bold')
    ax.annotate('3B SIDE', xy=(-220, 30), fontsize=10, ha='center', color='darkblue', fontweight='bold')

    ax.set_xlim(-420, 420)
    ax.set_ylim(-80, 420)
    ax.set_aspect('equal')
    ax.set_title(f"Foul Ball Hot Zone Forecast\n"
                f"{game.away_team} @ {game.home_team} | {pred_away.stadium_name}\n"
                f"{game.away_pitcher} vs {game.home_pitcher}",
                fontsize=13, fontweight='bold')
    ax.set_xlabel('Feet (negative = 3rd base side)')
    ax.set_ylabel('Feet from home plate')
    ax.grid(True, alpha=0.15)

    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {filename}")


def plot_combined_rankings(pred_away: GamePrediction, pred_home: GamePrediction, game: GameInfo, filename: str):
    """Combined section ranking chart."""
    combined: dict[str, dict] = {}
    for pred in [pred_away, pred_home]:
        for sp in pred.section_predictions:
            sid = sp.section.section_id
            if sid not in combined:
                combined[sid] = {'section': sp.section, 'catchable': 0, 'expected': 0,
                                 'ev_sum': 0, 'n': 0, 'netting': sp.netting}
            combined[sid]['catchable'] += sp.catchable_fouls
            combined[sid]['expected'] += sp.expected_fouls
            combined[sid]['ev_sum'] += sp.avg_exit_velocity * sp.expected_fouls
            combined[sid]['n'] += sp.expected_fouls

    # Netted sections are not plottable as catch chances; they are dropped
    # here for the same reason they leave the printed ranking.
    rankable = [r for r in combined.values()
                if r['netting'] is None or not r['netting'].blocks_catch]
    ranked = sorted(rankable, key=lambda x: x['catchable'], reverse=True)[:12]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))

    names = [f"{r['section'].name}\n({r['section'].side})" for r in ranked]
    vals = [r['catchable'] for r in ranked]
    colors = ['#e74c3c' if '3B' in r['section'].side else '#3498db' if '1B' in r['section'].side else '#2ecc71'
              for r in ranked]

    bars = ax1.barh(range(len(ranked)-1, -1, -1), vals, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)
    ax1.set_yticks(range(len(ranked)-1, -1, -1))
    ax1.set_yticklabels(names, fontsize=9)
    ax1.set_xlabel('Expected Catchable Fouls Per Game')
    ax1.set_title('Top Sections — Full Game', fontweight='bold')
    for bar, val in zip(bars, vals):
        ax1.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height()/2, f'{val:.2f}', va='center', fontsize=9)

    # Value chart
    valued = [r for r in rankable if r['section'].avg_ticket_price > 0 and r['catchable'] > 0.01]
    valued.sort(key=lambda r: r['catchable'] / r['section'].avg_ticket_price, reverse=True)
    valued = valued[:12]

    names2 = [f"{r['section'].name}\n(${r['section'].avg_ticket_price:.0f})" for r in valued]
    vals2 = [r['catchable'] / r['section'].avg_ticket_price * 1000 for r in valued]
    colors2 = ['#e74c3c' if '3B' in r['section'].side else '#3498db' if '1B' in r['section'].side else '#2ecc71'
               for r in valued]

    bars2 = ax2.barh(range(len(valued)-1, -1, -1), vals2, color=colors2, alpha=0.8, edgecolor='black', linewidth=0.5)
    ax2.set_yticks(range(len(valued)-1, -1, -1))
    ax2.set_yticklabels(names2, fontsize=9)
    ax2.set_xlabel('Catchable Fouls per $1,000 Spent')
    ax2.set_title('Best Value Seats', fontweight='bold')
    for bar, val in zip(bars2, vals2):
        ax2.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height()/2, f'{val:.1f}', va='center', fontsize=9)

    legend_elements = [
        mpatches.Patch(facecolor='#e74c3c', alpha=0.8, label='3rd Base Side'),
        mpatches.Patch(facecolor='#3498db', alpha=0.8, label='1st Base Side'),
        mpatches.Patch(facecolor='#2ecc71', alpha=0.8, label='Behind Home'),
    ]
    fig.legend(handles=legend_elements, loc='lower center', ncol=3, fontsize=11)
    plt.suptitle(f"{game.away_team} @ {game.home_team} — {pred_away.stadium_name}",
                fontsize=13, fontweight='bold')
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {filename}")


def main():
    parser = argparse.ArgumentParser(description='Foul Ball Predictor — Predict foul ball hot zones for any MLB game')
    parser.add_argument('--date', type=str, help='Game date (YYYY-MM-DD or MM/DD/YYYY)')
    parser.add_argument('--teams', nargs=2, metavar=('AWAY', 'HOME'), help='Team abbreviations (e.g., NYY BOS)')
    parser.add_argument('--game-id', type=int, help='Specific MLB game ID')
    parser.add_argument('--live', action='store_true', help='Pull real Statcast data (slower but more accurate)')
    parser.add_argument('--sims', type=int, default=400, help='Simulations per batter (default: 400)')
    parser.add_argument('--output', type=str, default=OUTPUT_DIR, help='Output directory for charts')
    args = parser.parse_args()

    np.random.seed(42)

    print_header("FOUL BALL PREDICTOR v0.2")
    print("Powered by Statcast + MLB Stats API + ballistic trajectory physics")
    if args.live:
        print("MODE: LIVE (pulling real Statcast data — this will take a few minutes)")
    else:
        print("MODE: QUICK (using league-average profiles — fast but less personalized)")
        print("       Use --live for real per-player data")

    # Determine which game to predict
    game = None

    if args.game_id:
        # Find specific game
        import statsapi
        # Search recent dates
        from datetime import datetime, timedelta
        for delta in range(-3, 30):
            d = (datetime.now() + timedelta(days=delta)).strftime('%m/%d/%Y')
            games = get_todays_games(d)
            for g in games:
                if g.game_id == args.game_id:
                    game = g
                    break
            if game:
                break

    elif args.teams:
        # Find game by team matchup
        away_abbrev, home_abbrev = args.teams[0].upper(), args.teams[1].upper()
        if away_abbrev not in TEAM_IDS or home_abbrev not in TEAM_IDS:
            valid = ', '.join(sorted(TEAM_IDS.keys()))
            print(f"Invalid team abbreviation. Valid teams: {valid}")
            return

        date = args.date or None
        if date and '-' in date:
            parts = date.split('-')
            date = f"{parts[1]}/{parts[2]}/{parts[0]}"

        games = get_todays_games(date)
        away_id = TEAM_IDS[away_abbrev]
        home_id = TEAM_IDS[home_abbrev]
        for g in games:
            if g.away_team_id == away_id and g.home_team_id == home_id:
                game = g
                break
            elif g.home_team_id == away_id and g.away_team_id == home_id:
                game = g
                break

        if not game:
            # Create a synthetic game entry for prediction even if no real game is scheduled
            print(f"\nNo scheduled game found for {away_abbrev} @ {home_abbrev}")
            print("Creating hypothetical matchup for prediction...")
            game = GameInfo(
                game_id=0,
                game_date=args.date or 'hypothetical',
                game_time='TBD',
                status='Hypothetical',
                home_team=[t for t in get_todays_games.__code__.co_consts if False][0] if False else '',
                home_team_id=home_id,
                away_team='',
                away_team_id=away_id,
                home_pitcher='TBD',
                away_pitcher='TBD',
                stadium_key=TEAM_STADIUM_MAP.get(home_id, 'yankee_stadium'),
                venue_name='',
            )
            # Get team names from a quick API call
            try:
                import statsapi
                teams = statsapi.get('teams', {'sportIds': 1})
                for t in teams['teams']:
                    if t['id'] == home_id:
                        game.home_team = t['name']
                        game.venue_name = t.get('venue', {}).get('name', 'Unknown')
                    if t['id'] == away_id:
                        game.away_team = t['name']
            except Exception:
                game.home_team = home_abbrev
                game.away_team = away_abbrev
    else:
        # Interactive mode — show today's games
        date = args.date
        if date and '-' in date:
            parts = date.split('-')
            date = f"{parts[1]}/{parts[2]}/{parts[0]}"
        games = get_todays_games(date)
        game = show_games(games)

    if not game:
        print("No game selected. Exiting.")
        return

    # Run prediction
    pred_away, pred_home = run_prediction(game, use_live=args.live, sims=args.sims)

    # Print report
    print_combined_report(pred_away, pred_home, game)

    # Generate visualizations
    safe_name = f"{game.away_team}_{game.home_team}".replace(' ', '_')
    print("\nGenerating visualizations...")
    plot_combined_heatmap(pred_away, pred_home, game, f'{args.output}/predict_{safe_name}_heatmap.png')
    plot_combined_rankings(pred_away, pred_home, game, f'{args.output}/predict_{safe_name}_rankings.png')

    print(f"\nDone! Charts saved to {args.output}/")


if __name__ == '__main__':
    main()
