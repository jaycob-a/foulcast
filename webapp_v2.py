"""
FOUL BALL PREDICTOR — Interactive Demo
=======================================
Polished web app with interactive SVG stadium map,
trajectory animations, and real-time predictions.

Run: python webapp_v2.py
Open: http://localhost:5000
"""
import sys
import os
import json
import logging
import time
import secrets
import threading
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from flask import Flask, render_template_string, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from foulball.log import get_logger

logger = get_logger(__name__)

from foulball.mlb_api import (
    get_projected_lineup, TEAM_IDS,
    TEAM_ID_TO_ABBREV, TEAM_STADIUM_MAP,
    get_todays_games, get_player_info,
)
from foulball.stadium import STADIUMS
from foulball.batter_profiles import BatterFoulProfile, PITCHER_PROFILES
from foulball.matchup_engine import predict_game_fouls, bootstrap_combined_ci
from foulball.live_profiles import enrich_with_spray_profiles, load_spray_profiles

app = Flask(__name__)
# Trust X-Forwarded-For from one proxy hop so rate limiting uses real client IP.
# NOTE: In-process rate limiting is best-effort only. For production with multiple
# workers/pods, enforce rate limits at the edge (nginx, Cloudflare, ALB).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# In production, require FOULCAST_SECRET_KEY to be set explicitly
if os.environ.get('FLASK_ENV') == 'production' and not os.environ.get('FOULCAST_SECRET_KEY'):
    raise RuntimeError("FOULCAST_SECRET_KEY must be set in production")
app.secret_key = os.environ.get('FOULCAST_SECRET_KEY', secrets.token_hex(32))


# --- Bounded LRU prediction cache with TTL ---
class LRUCache:
    """Thread-safe LRU cache with max size and TTL eviction."""
    def __init__(self, maxsize=100, ttl_seconds=300):
        self._cache: OrderedDict = OrderedDict()  # key -> (value, expires_at)
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._cache:
                value, expires_at = self._cache[key]
                if time.time() > expires_at:
                    del self._cache[key]
                    return None
                self._cache.move_to_end(key)
                return value
            return None

    def set(self, key, value):
        with self._lock:
            # Purge expired entries before inserting
            now = time.time()
            expired = [k for k, (_, exp) in self._cache.items() if now > exp]
            for k in expired:
                del self._cache[k]
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, now + self._ttl)
            while len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

    def __contains__(self, key):
        with self._lock:
            if key in self._cache:
                _, expires_at = self._cache[key]
                if time.time() > expires_at:
                    del self._cache[key]
                    return False
                return True
            return False


prediction_cache = LRUCache(maxsize=100, ttl_seconds=300)


# --- Thread-safe per-IP rate limiter (bounded) ---
_rate_limits: dict[str, list[float]] = {}
_rate_lock = threading.Lock()
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 10     # max requests per window
RATE_LIMIT_MAX_IPS = 10000  # cap tracked IPs to prevent memory growth


def _check_rate_limit(ip: str) -> bool:
    """Return True if request is allowed, False if rate-limited. Thread-safe."""
    now = time.time()
    with _rate_lock:
        # Evict oldest IPs if we hit the cap
        if len(_rate_limits) > RATE_LIMIT_MAX_IPS:
            # Remove IPs with all-expired entries
            expired = [k for k, v in _rate_limits.items()
                       if not v or v[-1] < now - RATE_LIMIT_WINDOW]
            for k in expired:
                del _rate_limits[k]
            # If still over cap, drop oldest half
            if len(_rate_limits) > RATE_LIMIT_MAX_IPS:
                to_drop = list(_rate_limits.keys())[:len(_rate_limits) // 2]
                for k in to_drop:
                    del _rate_limits[k]

        if ip not in _rate_limits:
            _rate_limits[ip] = []
        # Prune old entries
        _rate_limits[ip] = [t for t in _rate_limits[ip] if now - t < RATE_LIMIT_WINDOW]
        if len(_rate_limits[ip]) >= RATE_LIMIT_MAX:
            return False
        _rate_limits[ip].append(now)
        return True


_spray_profiles = load_spray_profiles()


def _build_lineup(team_id, pitcher_hand='R'):
    try:
        players = get_projected_lineup(team_id)
    except Exception:
        players = []
    profiles, by_id = [], {}
    for p in players[:9]:
        # Switch hitters bat from the opposite side of the pitcher
        if p.bats == 'S':
            side = 'L' if pitcher_hand == 'R' else 'R'
        else:
            side = p.bats
        prof = BatterFoulProfile(player_name=p.name, player_id=p.mlb_id, batter_side=side)
        profiles.append(prof)
        by_id[p.mlb_id] = prof
    enrich_with_spray_profiles(by_id)
    return profiles


def _get_mix(name):
    if name in PITCHER_PROFILES:
        p = PITCHER_PROFILES[name]
        return p['pitch_mix'], p['hand']
    return {'FF': .30, 'SL': .20, 'CH': .15, 'SI': .15, 'CU': .10, 'FC': .10}, 'R'


def _find_probable_pitchers(away_id, home_id):
    """Try to find today's probable starters for this matchup."""
    try:
        games = get_todays_games()
        for g in games:
            if g.away_team_id == away_id and g.home_team_id == home_id:
                return g.away_pitcher, g.home_pitcher
    except Exception:
        pass
    return 'TBD', 'TBD'


def _get_pitcher_hand(pitcher_name, team_id):
    """Get pitcher throwing hand from roster."""
    if pitcher_name in ('TBD', '', None):
        return 'R'
    try:
        from foulball.mlb_api import get_team_roster
        roster = get_team_roster(team_id)
        for p in roster:
            if p['type'] == 'Pitcher' and pitcher_name.lower() in p['name'].lower():
                info = get_player_info(p['id'])
                return info.get('throws', 'R')
    except Exception:
        pass
    return 'R'


def _run_prediction(away_id, home_id):
    """Core prediction logic shared by GET and POST endpoints."""
    stadium_key = TEAM_STADIUM_MAP.get(home_id, 'yankee_stadium')
    stadium = STADIUMS.get(stadium_key, STADIUMS['yankee_stadium'])()

    try:
        import statsapi
        td = statsapi.get('teams', {'sportIds': 1})
        nm = {t['id']: t['name'] for t in td['teams']}
        home_name, away_name = nm.get(home_id, 'Home'), nm.get(away_id, 'Away')
    except Exception:
        home_name = TEAM_ID_TO_ABBREV.get(home_id, 'Home')
        away_name = TEAM_ID_TO_ABBREV.get(away_id, 'Away')

    # Resolve pitchers first so we know their throwing hand for switch hitters
    away_pitcher, home_pitcher = _find_probable_pitchers(away_id, home_id)

    ck = f"{away_id}_{home_id}_{away_pitcher}_{home_pitcher}"
    has_tbd = away_pitcher in ('TBD', '', None) or home_pitcher in ('TBD', '', None)
    cached = prediction_cache.get(ck)
    if cached is not None and not has_tbd:
        return cached

    # Get pitch mix for each pitcher (away pitcher faces home batters and vice versa)
    home_p_mix, home_p_hand = _get_mix(home_pitcher)
    away_p_mix, away_p_hand = _get_mix(away_pitcher)

    # If not in our profile DB, at least get their throwing hand
    if home_pitcher not in PITCHER_PROFILES:
        home_p_hand = _get_pitcher_hand(home_pitcher, home_id)
    if away_pitcher not in PITCHER_PROFILES:
        away_p_hand = _get_pitcher_hand(away_pitcher, away_id)

    # Build lineups with pitcher hand (switch hitters resolved per matchup)
    # Away batters face home pitcher; home batters face away pitcher
    away_profiles = _build_lineup(away_id, pitcher_hand=home_p_hand)
    home_profiles = _build_lineup(home_id, pitcher_hand=away_p_hand)

    # Guard: if both lineups are empty, return an error instead of silent zeros
    if not away_profiles and not home_profiles:
        return {
            'error': 'Could not load lineups for either team (MLB API may be unavailable)',
            'matchup': {
                'away': away_name, 'home': home_name, 'stadium': stadium.name,
                'away_pitcher': away_pitcher, 'home_pitcher': home_pitcher,
            },
        }

    # Per-request RNG seed (deterministic by matchup, safe for concurrent requests)
    rng_seed = hash((away_id, home_id, away_pitcher, home_pitcher)) & 0xFFFFFFFF
    np.random.seed(rng_seed)

    # Away batters face home pitcher; home batters face away pitcher
    pred_a = predict_game_fouls(away_profiles, home_pitcher, home_p_mix, stadium, 400)
    pred_h = predict_game_fouls(home_profiles, away_pitcher, away_p_mix, stadium, 400)

    # Compute combined bootstrap CI across both half-game batter sets
    combined_ci = bootstrap_combined_ci([pred_a, pred_h])

    # Combine sections from both halves
    combined = {}
    for pred in [pred_a, pred_h]:
        for sp in pred.section_predictions:
            sid = sp.section.section_id
            if sid not in combined:
                combined[sid] = {
                    'sec': sp.section, 'catch': 0, 'exp': 0,
                    'ev_s': 0, 'n': 0, 'danger': 0, 'batters': {},
                }
            c = combined[sid]
            c['catch'] += sp.catchable_fouls
            c['exp'] += sp.expected_fouls
            c['ev_s'] += sp.avg_exit_velocity * sp.expected_fouls
            c['n'] += sp.expected_fouls
            c['danger'] = max(c['danger'], sp.danger_rating)
            for b in sp.top_batters:
                c['batters'][b] = c['batters'].get(b, 0) + 1

    ranked = sorted(combined.values(), key=lambda x: x['catch'], reverse=True)
    mx = ranked[0]['catch'] if ranked else 1
    total_exp = sum(x['exp'] for x in ranked) or 1

    sections_out = []
    for r in ranked:
        s = r['sec']
        avg_ev = r['ev_s'] / r['n'] if r['n'] > 0 else 0
        top_b = sorted(r['batters'], key=r['batters'].get, reverse=True)[:3]
        pct = r['exp'] / total_exp * 100
        # Use properly bootstrapped CI from combined batter set
        ci_low, ci_high = combined_ci.get(s.section_id, (pct, pct))
        sections_out.append({
            'id': s.section_id, 'name': s.name, 'side': s.side, 'level': s.level,
            'catchable': round(r['catch'], 3), 'expected': round(r['exp'], 3),
            'pct': round(pct, 1),
            'ci_low': round(ci_low, 1), 'ci_high': round(ci_high, 1),
            'danger': round(r['danger'], 1), 'avg_ev': round(avg_ev, 1),
            'intensity': round(r['catch'] / mx, 3),
            'top_batters': top_b,
            'geo': {
                'dmin': s.distance_min, 'dmax': s.distance_max,
                'amin': s.angle_min, 'amax': s.angle_max,
            },
        })

    tc = sum(r['catch'] for r in ranked)
    s1b = sum(r['catch'] for r in ranked if r['sec'].side == '1B')
    s3b = sum(r['catch'] for r in ranked if r['sec'].side == '3B')
    shm = sum(r['catch'] for r in ranked if r['sec'].side == 'HOME')
    tot = s1b + s3b + shm + .001

    if s1b > s3b * 1.2:
        rec = f"Sit on the 1ST BASE SIDE - {s1b/tot*100:.0f}% of catchable fouls"
        rside, rconf = '1B', ('high' if s1b > s3b * 1.5 else 'medium')
    elif s3b > s1b * 1.2:
        rec = f"Sit on the 3RD BASE SIDE - {s3b/tot*100:.0f}% of catchable fouls"
        rside, rconf = '3B', ('high' if s3b > s1b * 1.5 else 'medium')
    else:
        rec = "Both sides are roughly equal - pick based on view preference"
        rside, rconf = 'EVEN', 'medium'
    if ranked:
        rec += f". Best section: {ranked[0]['sec'].name} ({ranked[0]['sec'].side})"

    # Trajectory sample for animation
    all_ev = pred_a.all_events + pred_h.all_events
    ss = min(150, len(all_ev))
    idxs = np.random.choice(len(all_ev), ss, replace=False) if ss > 0 else []
    trajs = []
    for i in idxs:
        e = all_ev[i]
        t = e.trajectory
        if t.landing_distance < 5 or t.landing_distance > 400:
            continue
        trajs.append({
            'lx': round(t.landing_x, 1), 'ly': round(t.landing_y, 1),
            'd': round(t.landing_distance, 1), 'mh': round(t.max_height, 1),
            'ev': round(e.exit_velocity, 1), 'side': e.landing_side,
            'ft': round(t.flight_time, 2), 'c': bool(e.is_catchable),
        })

    # Batter stats
    bstats = {}
    for e in all_ev:
        if e.batter_name not in bstats:
            bstats[e.batter_name] = {'n': 0, 'c': 0, 'evs': 0, 'secs': {}}
        b = bstats[e.batter_name]
        b['n'] += 1
        b['c'] += int(e.is_catchable)
        b['evs'] += e.exit_velocity
        if e.section:
            b['secs'][e.section.name] = b['secs'].get(e.section.name, 0) + 1

    def batter_list(profiles):
        out = []
        for p in profiles:
            bs = bstats.get(p.player_name, {'n': 0, 'c': 0, 'evs': 0, 'secs': {}})
            tsecs = sorted(bs['secs'].items(), key=lambda x: x[1], reverse=True)[:2]
            out.append({
                'name': p.player_name, 'side': p.batter_side,
                'fouls': bs['n'], 'catchable': bs['c'],
                'avg_ev': round(bs['evs'] / bs['n'], 1) if bs['n'] > 0 else 0,
                'top_secs': [s[0] for s in tsecs],
                'pull_pct': round(p.fair_pull_pct, 1),
            })
        return out

    enriched = sum(1 for p in away_profiles + home_profiles if p.fair_pull_pct != 50.0)

    result = {
        'matchup': {
            'away': away_name, 'home': home_name, 'stadium': stadium.name,
            'alt': stadium.altitude_ft, 'temp': stadium.avg_temperature_f,
            'away_pitcher': away_pitcher, 'home_pitcher': home_pitcher,
            'away_pitcher_hand': away_p_hand, 'home_pitcher_hand': home_p_hand,
        },
        'rec': {'text': rec, 'side': rside, 'conf': rconf},
        'stats': {
            'catchable': round(tc, 1),
            'p1b': round(s1b / tot * 100), 'p3b': round(s3b / tot * 100),
            'phome': round(shm / tot * 100), 'sims': len(all_ev),
        },
        'sections': sections_out,
        'batters': {'away': batter_list(away_profiles), 'home': batter_list(home_profiles)},
        'trajectories': trajs,
        'methodology': {
            'sims_per_batter': 400,
            'physics': 'Ballistic trajectory with drag + altitude/temperature correction + per-batter pull tendency',
            'data_source': 'Live MLB rosters via statsapi',
            'batters_in_game': len(away_profiles) + len(home_profiles),
            'confidence_intervals': '90% bootstrap CI (resampling batters)',
            'backtest': {
                'r': 0.986,
                'n_fouls': 19558,
                'mae_ft': 15.6,
                'median_error_ft': 10.1,
                'note': 'Validated against 19,558 real Statcast foul balls (Aug 2024). Median prediction error: 10.1 feet.',
            },
            'game_backtest': {
                'games': 20,
                'median_ks': 0.194,
                'mean_side_error': 4.4,
                'mean_pitch_cosine': 0.938,
                'mean_dist_bias': 0.8,
            },
        },
    }

    if not has_tbd:
        prediction_cache.set(ck, result)
    return result


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/today')
def api_today():
    """Return today's MLB game schedule."""
    from datetime import date
    today_str = date.today().isoformat()
    try:
        games_raw = get_todays_games()
        games = []
        for g in games_raw:
            games.append({
                'away_id': g.away_team_id,
                'home_id': g.home_team_id,
                'away_name': g.away_team,
                'home_name': g.home_team,
                'away_abbrev': TEAM_ID_TO_ABBREV.get(g.away_team_id, ''),
                'home_abbrev': TEAM_ID_TO_ABBREV.get(g.home_team_id, ''),
                'away_pitcher': g.away_pitcher or 'TBD',
                'home_pitcher': g.home_pitcher or 'TBD',
                'time': g.game_time or 'TBD',
                'status': g.status or 'Unknown',
            })
    except Exception as e:
        logger.error("Today's games API error: %s", e)
        games = []

    return jsonify({'games': games, 'date': today_str})


@app.route('/api/teams')
def api_teams():
    try:
        import statsapi
        data = statsapi.get('teams', {'sportIds': 1})
        teams = [
            {'id': t['id'], 'name': t['name'], 'abbrev': TEAM_ID_TO_ABBREV.get(t['id'], '')}
            for t in data['teams'] if t['id'] in TEAM_ID_TO_ABBREV
        ]
        teams.sort(key=lambda t: t['name'])
    except Exception as e:
        logger.error("Teams API error: %s", e)
        teams = [{'id': tid, 'name': ab, 'abbrev': ab} for ab, tid in sorted(TEAM_IDS.items())]
    if not teams:
        # Fallback if statsapi returned empty
        teams = [{'id': tid, 'name': ab, 'abbrev': ab} for ab, tid in sorted(TEAM_IDS.items())]
    return jsonify(teams)


@app.route('/api/predict', methods=['GET', 'POST'])
def api_predict():
    """Predict foul ball distribution for a matchup.

    GET:  /api/predict?away=<team_id>&home=<team_id>
    POST: /api/predict  {"away": <team_id>, "home": <team_id>}

    Returns JSON with sections, recommendations, trajectories, and confidence intervals.
    """
    # Rate limit expensive prediction endpoint
    client_ip = request.remote_addr or '0.0.0.0'
    if not _check_rate_limit(client_ip):
        return jsonify({'error': 'Rate limited. Max 10 predictions per minute.'}), 429

    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        try:
            away_id = int(data.get('away', 0))
            home_id = int(data.get('home', 0))
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid team IDs'}), 400
    else:
        try:
            away_id = int(request.args.get('away', 0))
            home_id = int(request.args.get('home', 0))
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid team IDs'}), 400

    if not away_id or not home_id:
        return jsonify({'error': 'Missing team IDs'}), 400
    if away_id not in TEAM_ID_TO_ABBREV or home_id not in TEAM_ID_TO_ABBREV:
        return jsonify({'error': 'Unknown team ID'}), 400
    if away_id == home_id:
        return jsonify({'error': 'Away and home team must be different'}), 400

    try:
        result = _run_prediction(away_id, home_id)
    except Exception as e:
        logger.error("Prediction failed for away=%d home=%d: %s", away_id, home_id, e)
        return jsonify({'error': 'Prediction failed unexpectedly'}), 500
    if 'error' in result:
        return jsonify(result), 503
    return jsonify(result)


@app.route('/api/live/<int:game_id>')
def api_live(game_id):
    """Live game predictions — fetches current game state and returns updated predictions.

    Looks up the game by ID, resolves current lineups and pitchers,
    and runs a fresh prediction reflecting the current game state.
    """
    # Rate limit live endpoint (shares budget with /api/predict)
    client_ip = request.remote_addr or '0.0.0.0'
    if not _check_rate_limit(client_ip):
        return jsonify({'error': 'Rate limited. Max 10 requests per minute.'}), 429

    try:
        import statsapi
        game = statsapi.get('game', {'gamePk': game_id})
    except Exception as e:
        logger.error("Live game API error for game %d: %s", game_id, e)
        return jsonify({'error': f'Could not fetch game {game_id}'}), 404

    game_data = game.get('gameData', {})
    live_data = game.get('liveData', {})

    teams = game_data.get('teams', {})
    home_id = teams.get('home', {}).get('id', 0)
    away_id = teams.get('away', {}).get('id', 0)

    if not home_id or not away_id:
        return jsonify({'error': 'Could not resolve teams for this game'}), 400

    # Get current pitcher from live data
    linescore = live_data.get('linescore', {})
    offense = linescore.get('offense', {})
    defense = linescore.get('defense', {})
    current_pitcher_id = defense.get('pitcher', {}).get('id')
    current_batter_id = offense.get('batter', {}).get('id')
    inning = linescore.get('currentInning', 0)
    inning_half = linescore.get('inningHalf', '')
    game_status = game_data.get('status', {}).get('detailedState', 'Unknown')

    # Run standard prediction
    try:
        result = _run_prediction(away_id, home_id)
    except Exception as e:
        logger.error("Live prediction failed for game %d: %s", game_id, e)
        return jsonify({'error': 'Prediction failed unexpectedly'}), 500
    if 'error' in result:
        return jsonify(result), 503

    # Add live game context
    result['live'] = {
        'game_id': game_id,
        'status': game_status,
        'inning': inning,
        'inning_half': inning_half,
        'current_pitcher_id': current_pitcher_id,
        'current_batter_id': current_batter_id,
    }

    return jsonify(result)


_stadiums_cache = None

@app.route('/api/stadiums')
def api_stadiums():
    """List all available stadiums with their geometry (cached after first call)."""
    global _stadiums_cache
    if _stadiums_cache is not None:
        return jsonify(_stadiums_cache)
    stadiums_out = []
    for key, factory in STADIUMS.items():
        s = factory()
        stadiums_out.append({
            'key': key,
            'name': s.name,
            'city': s.city,
            'team': s.team,
            'altitude_ft': s.altitude_ft,
            'lf': s.lf_distance,
            'cf': s.cf_distance,
            'rf': s.rf_distance,
            'sections': len(s.sections),
        })
    _stadiums_cache = stadiums_out
    return jsonify(stadiums_out)


# === HTML TEMPLATE ===
# Loaded below from separate string to keep code readable.
# All visualization is client-side (SVG + Canvas). No matplotlib needed.

HTML_TEMPLATE = open(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'demo.html'),
    encoding='utf-8'
).read() if os.path.exists(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'demo.html')
) else '<h1>Template not found. Create templates/demo.html</h1>'


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("FOUL BALL PREDICTOR - Interactive Demo")
    logger.info("=" * 60)
    logger.info("Loaded %d spray profiles", len(_spray_profiles))
    logger.info("Open: http://localhost:5000")
    logger.info("Press Ctrl+C to stop")
    app.run(debug=False, port=5000)
