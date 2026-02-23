"""
FOUL BALL PREDICTOR — Web App
==============================
A Flask web app that lets you pick any MLB matchup and see
foul ball predictions with interactive visualizations.

Run: python webapp.py
Then open: http://localhost:5000
"""
import sys
import os
import io
import base64
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from flask import Flask, render_template_string, request, jsonify

from foulball.mlb_api import (
    get_todays_games, get_projected_lineup, TEAM_IDS,
    TEAM_ID_TO_ABBREV, TEAM_STADIUM_MAP, GameInfo,
)
from foulball.stadium import STADIUMS
from foulball.batter_profiles import BatterFoulProfile, PITCHER_PROFILES
from foulball.matchup_engine import predict_game_fouls, GamePrediction
from foulball.live_profiles import enrich_with_spray_profiles

app = Flask(__name__)

# Cache predictions to avoid recomputing
prediction_cache = {}


def fig_to_base64(fig):
    """Convert matplotlib figure to base64 string for embedding in HTML."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_str


def build_quick_lineup(team_id: int) -> list[BatterFoulProfile]:
    """Build lineup profiles quickly from MLB API, enriched with spray data."""
    try:
        lineup_players = get_projected_lineup(team_id)
    except Exception:
        lineup_players = []

    profiles = []
    profiles_by_id = {}
    for p in lineup_players[:9]:
        side = p.bats if p.bats != 'S' else 'L'
        prof = BatterFoulProfile(
            player_name=p.name, player_id=p.mlb_id, batter_side=side,
        )
        profiles.append(prof)
        profiles_by_id[p.mlb_id] = prof

    # Enrich with per-batter spray angle data from cache
    enrich_with_spray_profiles(profiles_by_id)
    return profiles


def get_pitch_mix(pitcher_name: str) -> tuple[dict, str]:
    """Get pitcher's pitch mix."""
    if pitcher_name in PITCHER_PROFILES:
        p = PITCHER_PROFILES[pitcher_name]
        return p['pitch_mix'], p['hand']
    return {'FF': 0.30, 'SL': 0.20, 'CH': 0.15, 'SI': 0.15, 'CU': 0.10, 'FC': 0.10}, 'R'


def run_game_prediction(away_id: int, home_id: int):
    """Run full game prediction and return results."""
    cache_key = f"{away_id}_{home_id}"
    if cache_key in prediction_cache:
        return prediction_cache[cache_key]

    # Get stadium
    stadium_key = TEAM_STADIUM_MAP.get(home_id, 'yankee_stadium')
    if stadium_key not in STADIUMS:
        stadium_key = 'yankee_stadium'
    stadium = STADIUMS[stadium_key]()

    # Get team names
    import statsapi
    teams_data = statsapi.get('teams', {'sportIds': 1})
    team_names = {t['id']: t['name'] for t in teams_data['teams']}
    home_name = team_names.get(home_id, 'Home')
    away_name = team_names.get(away_id, 'Away')

    # Build lineups
    away_lineup = build_quick_lineup(away_id)
    home_lineup = build_quick_lineup(home_id)

    away_mix, away_hand = get_pitch_mix('TBD')
    home_mix, home_hand = get_pitch_mix('TBD')

    np.random.seed(42)

    # Away batting
    pred_away = predict_game_fouls(
        lineup=away_lineup, pitcher_name='Starter',
        pitcher_pitch_mix=home_mix, pitcher_hand=home_hand,
        stadium=stadium, simulations_per_batter=300,
    )
    pred_away.away_team = away_name
    pred_away.home_team = home_name

    # Home batting
    pred_home = predict_game_fouls(
        lineup=home_lineup, pitcher_name='Starter',
        pitcher_pitch_mix=away_mix, pitcher_hand=away_hand,
        stadium=stadium, simulations_per_batter=300,
    )
    pred_home.away_team = away_name
    pred_home.home_team = home_name

    result = {
        'pred_away': pred_away,
        'pred_home': pred_home,
        'stadium': stadium,
        'home_name': home_name,
        'away_name': away_name,
        'away_lineup': away_lineup,
        'home_lineup': home_lineup,
    }
    prediction_cache[cache_key] = result
    return result


def generate_heatmap(pred_away, pred_home, home_name, away_name, stadium_name):
    """Generate stadium heatmap as base64."""
    fig, ax = plt.subplots(figsize=(10, 10))

    theta = np.linspace(-np.pi/4, np.pi/4, 100)
    ax.plot(330 * np.sin(theta), 330 * np.cos(theta), 'k-', linewidth=2)
    ax.plot([0, 330*np.sin(np.pi/4)], [0, 330*np.cos(np.pi/4)], 'k-', linewidth=1.5)
    ax.plot([0, -330*np.sin(np.pi/4)], [0, 330*np.cos(np.pi/4)], 'k-', linewidth=1.5)
    bases = [(0, 0), (63.6, 63.6), (0, 127.3), (-63.6, 63.6), (0, 0)]
    bx, by = zip(*bases)
    ax.plot(bx, by, 'k-', linewidth=1)
    for r in [50, 100, 150, 200, 250, 300]:
        t = np.linspace(-np.pi/2 - 0.3, np.pi/2 + 0.3, 100)
        ax.plot(r * np.sin(t), r * np.cos(t), 'gray', linewidth=0.3, alpha=0.2)

    all_x, all_y, all_ev = [], [], []
    for pred in [pred_away, pred_home]:
        for event in pred.all_events:
            traj = event.trajectory
            dist = event.landing_distance
            if dist < 5 or dist > 400:
                continue
            angle = np.arctan2(abs(traj.landing_y), abs(traj.landing_x))
            total_angle = np.pi/4 + angle * 0.8
            x = dist * np.sin(total_angle) * (1 if event.landing_side == '1B' else -1)
            y = dist * np.cos(total_angle)
            all_x.append(x)
            all_y.append(y)
            all_ev.append(event.exit_velocity)

    if all_x:
        scatter = ax.scatter(all_x, all_y, c=all_ev, cmap='YlOrRd',
                           alpha=0.35, s=10, vmin=40, vmax=110, zorder=3)
        plt.colorbar(scatter, ax=ax, shrink=0.5, label='Exit Velocity (mph)')

    ax.annotate('HOME', xy=(0, -8), fontsize=9, ha='center', fontweight='bold')
    ax.annotate('1B SIDE', xy=(200, 30), fontsize=10, ha='center', color='#c0392b', fontweight='bold')
    ax.annotate('3B SIDE', xy=(-200, 30), fontsize=10, ha='center', color='#2980b9', fontweight='bold')
    ax.set_xlim(-400, 400)
    ax.set_ylim(-60, 400)
    ax.set_aspect('equal')
    ax.set_title(f'Foul Ball Hot Zones\n{away_name} @ {home_name} | {stadium_name}',
                fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.15)

    return fig_to_base64(fig)


def generate_rankings_chart(combined_sections, away_name, home_name):
    """Generate section ranking chart as base64."""
    ranked = sorted(combined_sections.values(), key=lambda x: x['catchable'], reverse=True)[:10]

    fig, ax = plt.subplots(figsize=(10, 6))
    names = [f"{r['section'].name} ({r['section'].side})" for r in ranked]
    vals = [r['catchable'] for r in ranked]
    colors = ['#e74c3c' if '3B' in r['section'].side else '#3498db' if '1B' in r['section'].side else '#2ecc71'
              for r in ranked]

    bars = ax.barh(range(len(ranked)-1, -1, -1), vals, color=colors, alpha=0.85, edgecolor='white', linewidth=0.5)
    ax.set_yticks(range(len(ranked)-1, -1, -1))
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel('Expected Catchable Fouls Per Game')
    ax.set_title(f'Best Sections — {away_name} @ {home_name}', fontweight='bold')

    for bar, val in zip(bars, vals):
        ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height()/2,
               f'{val:.2f}', va='center', fontsize=9, fontweight='bold')

    plt.tight_layout()
    return fig_to_base64(fig)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Foul Ball Predictor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a1a;
            color: #e0e0e0;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1a3e 0%, #0d0d2b 100%);
            padding: 30px 40px;
            border-bottom: 2px solid #e74c3c;
        }
        .header h1 {
            font-size: 28px;
            color: #fff;
            margin-bottom: 5px;
        }
        .header .subtitle {
            color: #888;
            font-size: 14px;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 30px; }
        .team-picker {
            display: flex;
            gap: 20px;
            align-items: center;
            justify-content: center;
            margin: 30px 0;
            flex-wrap: wrap;
        }
        select {
            padding: 12px 20px;
            font-size: 16px;
            border: 2px solid #333;
            border-radius: 8px;
            background: #1a1a2e;
            color: #fff;
            cursor: pointer;
            min-width: 200px;
        }
        select:focus { border-color: #e74c3c; outline: none; }
        .at-symbol { font-size: 24px; color: #666; font-weight: bold; }
        .predict-btn {
            padding: 14px 40px;
            font-size: 16px;
            font-weight: bold;
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.1s;
        }
        .predict-btn:hover { transform: scale(1.05); }
        .predict-btn:disabled { opacity: 0.5; cursor: wait; }
        .results { display: none; }
        .results.visible { display: block; }
        .card {
            background: #12122a;
            border: 1px solid #222;
            border-radius: 12px;
            padding: 25px;
            margin: 20px 0;
        }
        .card h2 { color: #fff; margin-bottom: 15px; font-size: 20px; }
        .card img { width: 100%; border-radius: 8px; }
        .recommendation {
            background: linear-gradient(135deg, #1a3a1a 0%, #0d2b0d 100%);
            border: 2px solid #27ae60;
            padding: 20px 25px;
            border-radius: 12px;
            margin: 20px 0;
            font-size: 18px;
        }
        .recommendation .label { color: #27ae60; font-weight: bold; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }
        .recommendation .value { color: #fff; font-size: 22px; margin-top: 5px; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .stat-card {
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }
        .stat-card .number { font-size: 28px; font-weight: bold; color: #e74c3c; }
        .stat-card .label { font-size: 12px; color: #888; margin-top: 5px; text-transform: uppercase; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        th {
            text-align: left;
            padding: 10px 12px;
            background: #1a1a2e;
            color: #888;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #1a1a2e;
        }
        tr:hover td { background: #1a1a3e; }
        .side-3b { color: #e74c3c; }
        .side-1b { color: #3498db; }
        .side-home { color: #2ecc71; }
        .loading {
            text-align: center;
            padding: 60px;
            color: #888;
            font-size: 18px;
            display: none;
        }
        .loading.visible { display: block; }
        .spinner {
            width: 40px; height: 40px;
            border: 4px solid #333;
            border-top: 4px solid #e74c3c;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .lineup-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .lineup-card h3 { color: #888; font-size: 14px; margin-bottom: 10px; text-transform: uppercase; }
        .player { padding: 4px 0; font-size: 14px; }
        .player .hand { color: #888; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Foul Ball Predictor</h1>
        <div class="subtitle">Powered by Statcast data + ballistic trajectory physics | All 30 MLB stadiums</div>
    </div>

    <div class="container">
        <div class="team-picker">
            <select id="away-team">
                <option value="">Select Away Team</option>
            </select>
            <span class="at-symbol">@</span>
            <select id="home-team">
                <option value="">Select Home Team</option>
            </select>
            <button class="predict-btn" onclick="predict()">Predict Foul Balls</button>
        </div>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            Running Monte Carlo simulation...
        </div>

        <div class="results" id="results"></div>
    </div>

    <script>
        const teams = {{ teams_json | safe }};

        // Populate dropdowns
        const awaySelect = document.getElementById('away-team');
        const homeSelect = document.getElementById('home-team');
        teams.forEach(t => {
            awaySelect.add(new Option(t.name, t.id));
            homeSelect.add(new Option(t.name, t.id));
        });

        async function predict() {
            const awayId = document.getElementById('away-team').value;
            const homeId = document.getElementById('home-team').value;
            if (!awayId || !homeId) { alert('Please select both teams'); return; }
            if (awayId === homeId) { alert('Teams must be different'); return; }

            document.getElementById('loading').classList.add('visible');
            document.getElementById('results').classList.remove('visible');
            document.querySelector('.predict-btn').disabled = true;

            try {
                const resp = await fetch(`/predict?away=${awayId}&home=${homeId}`);
                const data = await resp.json();
                renderResults(data);
            } catch (e) {
                alert('Error: ' + e.message);
            } finally {
                document.getElementById('loading').classList.remove('visible');
                document.querySelector('.predict-btn').disabled = false;
            }
        }

        function renderResults(data) {
            const el = document.getElementById('results');
            const sideClass = s => s.includes('3B') ? 'side-3b' : s.includes('1B') ? 'side-1b' : 'side-home';

            let sectionsHTML = data.sections.map((s, i) => `
                <tr>
                    <td>${i+1}</td>
                    <td class="${sideClass(s.side)}">${s.name}</td>
                    <td class="${sideClass(s.side)}">${s.side}</td>
                    <td>${s.level}</td>
                    <td><strong>${s.catchable.toFixed(2)}</strong></td>
                    <td>$${s.price}</td>
                    <td>${s.value.toFixed(1)}</td>
                    <td>${s.avg_ev.toFixed(0)} mph</td>
                </tr>
            `).join('');

            let awayPlayers = data.away_lineup.map(p => `<div class="player">${p.name} <span class="hand">(${p.side}HB)</span></div>`).join('');
            let homePlayers = data.home_lineup.map(p => `<div class="player">${p.name} <span class="hand">(${p.side}HB)</span></div>`).join('');

            el.innerHTML = `
                <div class="recommendation">
                    <div class="label">Recommendation</div>
                    <div class="value">${data.recommendation}</div>
                </div>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="number">${data.total_catchable.toFixed(1)}</div>
                        <div class="label">Catchable Fouls / Game</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">${data.pct_1b}%</div>
                        <div class="label">1st Base Side</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">${data.pct_3b}%</div>
                        <div class="label">3rd Base Side</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">#1: $${data.best_section_price}</div>
                        <div class="label">Best Section Price</div>
                    </div>
                </div>

                <div class="card">
                    <h2>Foul Ball Heat Map — ${data.stadium_name}</h2>
                    <img src="data:image/png;base64,${data.heatmap}" alt="Heatmap">
                </div>

                <div class="card">
                    <h2>Section Rankings</h2>
                    <img src="data:image/png;base64,${data.rankings_chart}" alt="Rankings">
                </div>

                <div class="card">
                    <h2>All Sections — Ranked by Catchable Fouls</h2>
                    <table>
                        <thead>
                            <tr><th>#</th><th>Section</th><th>Side</th><th>Level</th><th>Catchable</th><th>Price</th><th>Value</th><th>Avg EV</th></tr>
                        </thead>
                        <tbody>${sectionsHTML}</tbody>
                    </table>
                </div>

                <div class="card">
                    <h2>Lineups</h2>
                    <div class="lineup-grid">
                        <div class="lineup-card">
                            <h3>${data.away_name} (Batting)</h3>
                            ${awayPlayers}
                        </div>
                        <div class="lineup-card">
                            <h3>${data.home_name} (Batting)</h3>
                            ${homePlayers}
                        </div>
                    </div>
                </div>
            `;
            el.classList.add('visible');
        }
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    teams = sorted([
        {'id': tid, 'abbrev': abbrev, 'name': name}
        for abbrev, tid in TEAM_IDS.items()
        for name in [None]  # placeholder
    ], key=lambda x: x['abbrev'])

    # Get real team names
    try:
        import statsapi
        teams_data = statsapi.get('teams', {'sportIds': 1})
        name_map = {t['id']: t['name'] for t in teams_data['teams']}
        for t in teams:
            t['name'] = name_map.get(t['id'], t['abbrev'])
    except Exception:
        for t in teams:
            t['name'] = t['abbrev']

    teams.sort(key=lambda x: x['name'])
    return render_template_string(HTML_TEMPLATE, teams_json=json.dumps(teams))


@app.route('/predict')
def predict():
    away_id = int(request.args.get('away', 0))
    home_id = int(request.args.get('home', 0))

    if not away_id or not home_id:
        return jsonify({'error': 'Missing team IDs'}), 400

    result = run_game_prediction(away_id, home_id)
    pred_away = result['pred_away']
    pred_home = result['pred_home']
    stadium = result['stadium']

    # Combine sections
    combined = {}
    for pred in [pred_away, pred_home]:
        for sp in pred.section_predictions:
            sid = sp.section.section_id
            if sid not in combined:
                combined[sid] = {
                    'section': sp.section, 'catchable': 0, 'expected': 0,
                    'ev_sum': 0, 'n': 0, 'danger': 0,
                }
            combined[sid]['catchable'] += sp.catchable_fouls
            combined[sid]['expected'] += sp.expected_fouls
            combined[sid]['ev_sum'] += sp.avg_exit_velocity * sp.expected_fouls
            combined[sid]['n'] += sp.expected_fouls
            combined[sid]['danger'] = max(combined[sid]['danger'], sp.danger_rating)

    ranked = sorted(combined.values(), key=lambda x: x['catchable'], reverse=True)

    total_catchable = sum(r['catchable'] for r in ranked)
    side_1b = sum(r['catchable'] for r in ranked if r['section'].side == '1B')
    side_3b = sum(r['catchable'] for r in ranked if r['section'].side == '3B')
    total_side = side_1b + side_3b + 0.001

    if side_1b > side_3b * 1.15:
        rec = f"Sit on the 1st BASE SIDE for best foul ball chances ({side_1b/total_side*100:.0f}% of catchable fouls)"
    elif side_3b > side_1b * 1.15:
        rec = f"Sit on the 3rd BASE SIDE for best foul ball chances ({side_3b/total_side*100:.0f}% of catchable fouls)"
    else:
        rec = "Both sides are roughly equal — pick based on price and view preference"

    best_price = ranked[0]['section'].avg_ticket_price if ranked else 0

    # Generate charts
    heatmap_b64 = generate_heatmap(pred_away, pred_home, result['home_name'], result['away_name'], stadium.name)
    rankings_b64 = generate_rankings_chart(combined, result['away_name'], result['home_name'])

    sections_data = []
    for r in ranked:
        avg_ev = r['ev_sum'] / r['n'] if r['n'] > 0 else 0
        price = r['section'].avg_ticket_price
        value = r['catchable'] / price * 1000 if price > 0 else 0
        sections_data.append({
            'name': r['section'].name,
            'side': r['section'].side,
            'level': r['section'].level,
            'catchable': r['catchable'],
            'price': int(price),
            'value': value,
            'avg_ev': avg_ev,
        })

    away_lineup_data = [{'name': p.player_name, 'side': p.batter_side} for p in result['away_lineup']]
    home_lineup_data = [{'name': p.player_name, 'side': p.batter_side} for p in result['home_lineup']]

    return jsonify({
        'home_name': result['home_name'],
        'away_name': result['away_name'],
        'stadium_name': stadium.name,
        'recommendation': rec,
        'total_catchable': total_catchable,
        'pct_1b': round(side_1b / total_side * 100),
        'pct_3b': round(side_3b / total_side * 100),
        'best_section_price': int(best_price),
        'heatmap': heatmap_b64,
        'rankings_chart': rankings_b64,
        'sections': sections_data,
        'away_lineup': away_lineup_data,
        'home_lineup': home_lineup_data,
    })


if __name__ == '__main__':
    print("=" * 60)
    print("FOUL BALL PREDICTOR — Web App")
    print("=" * 60)
    print("Starting server...")
    print("Open your browser to: http://localhost:5000")
    print("Press Ctrl+C to stop\n")
    app.run(debug=False, port=5000)
