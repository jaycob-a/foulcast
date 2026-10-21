"""
FOULCAST — the server
=====================
One thing is served here, and as of Step 25 it is the only thing: **the
public site** (`/`, `/parks/...`) — the 31 park pages, the home-page gallery
and the explanatory page, built ahead of time by `site_build.py` and served
from memory. `/` is the site's front door. Five URL rules, and
`tests/test_endpoints.py` holds the list to exactly those five.

The foul log — the first-party observation tool, which recorded what somebody
saw at a game and claimed nothing — is shelved as of 20 October 2026. Its
views are all still here, on a blueprint that is never registered, so `/log`
and `/api/log/*` answer like any other unknown path. The season it was built
for ended on 27 September. See the logging section for what reviving it takes.

WHAT WAS HERE BEFORE, AND WHY IT IS NOT
---------------------------------------
This file began as an interactive demo: pick two teams, and it answered with a
recommended side to sit on, a named best section, a confidence rating and a
section-level backtest correlation of 0.986. Every one of those is a claim
this project has since established it cannot support — the correlation was
against *Statcast landing coordinates*, not against seats; the section names
it printed disagree with 27 of the 30 seating maps anybody has read; and no
foul ball has ever been compared with this model's distribution. The site
built in Steps 11 to 24 says all of that on its own pages, in those words, and
the demo sat in front of it at the root URL saying the opposite.

So the demo page and the prediction endpoints it called (`/api/predict`,
`/api/live/<id>`, `/api/today`, `/api/teams`, `/api/stadiums`) are gone from
the public surface, and the root URL now goes to the site. The model itself is
untouched and still lives in `foulball/`, where the tests, `predict.py`,
`park_sweep.py`, `game_backtest.py` and `site_build.py` all reach it. What was
retired is the *publishing* of it, not the code — which is the same thing the
shelved foul log gets, for a different reason.

`tests/test_endpoints.py` holds the public route list to exactly the five
rules above, so a new public URL cannot appear without somebody deciding it
should.

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

from flask import Blueprint, Flask, redirect, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from foulball.log import get_logger

logger = get_logger(__name__)

# Only what the two surviving surfaces need. The simulation's own imports went
# with the prediction endpoints; `foulball` is unchanged and the tools and
# tests import it directly.
from foulball.mlb_api import (
    TEAM_ID_TO_ABBREV, resolve_stadium_key, get_todays_games,
)
from foulball.stadium import STADIUMS

# `static_folder=None` removes Flask's default `/static/<path>` route. There
# is no static directory in this repo and never was — the two pages are inline
# HTML and the site's CSS is inside each built page — so the route only ever
# served 404s, and a public URL that exists to serve nothing is one more thing
# `tests/test_endpoints.py` has to hold a list of.
app = Flask(__name__, static_folder=None)
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


# --- Thread-safe per-IP rate limiter (bounded) ---
_rate_limits: dict[str, list[float]] = {}
_rate_lock = threading.Lock()
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 10     # max requests per window
RATE_LIMIT_MAX_IPS = 10000  # cap tracked IPs to prevent memory growth


def _check_rate_limit(ip: str, bucket: str = '', max_requests: int | None = None) -> bool:
    """Return True if request is allowed, False if rate-limited. Thread-safe.

    `bucket` gives a caller its own counter under the same IP. Foul logging
    needs one: a prediction is one request per page view, but a fan clearing a
    backed-up offline queue in the 8th inning can legitimately fire a dozen
    writes in a few seconds, and dropping those loses data that cannot be
    re-collected.
    """
    now = time.time()
    limit = RATE_LIMIT_MAX if max_requests is None else max_requests
    ip = f"{bucket}:{ip}" if bucket else ip
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
        if len(_rate_limits[ip]) >= limit:
            return False
        _rate_limits[ip].append(now)
        return True


# ============================================================
# FOUL BALL LOGGING (Step 8) — SHELVED, and not registered
# ============================================================
# The only first-party spatial data this project has. See the module docstring
# in foulball/foul_log.py for why the schema looks the way it does, and
# AUDIT.md (2026-08-09 correction) for why it is the scarce asset.
#
# Writes are guarded by FOULCAST_LOG_TOKEN when set. A public write endpoint
# with no gate is an invitation to poison the one dataset here that cannot be
# regenerated; the season ended 2026-09-27 and there is no second attempt.
#
# SHELVED 2026-10-20. Every view below hangs off this blueprint, and the
# blueprint is never registered, so none of it answers on any URL: `/log` and
# `/api/log/*` are 404 like any other path. The code is kept and kept working
# — `_resolve_zone` is tested by `tests/test_foul_log.py`, the schema and the
# calibration around it are tested in full, and nothing here has rotted — so
# reviving the surface is one line:
#
#     app.register_blueprint(log_api)
#
# A blueprint rather than a commented-out decorator or an environment flag.
# Commented-out routes stop being syntax, let alone tested. A flag would mean
# the public URL list depends on the environment, and the point of
# `tests/test_endpoints.py` is that the list is a fact about the code and not
# about a deployment.
log_api = Blueprint('log', __name__)

from contextlib import closing

from foulball import foul_log
from foulball.seat_map import (
    zone_catalog, zone_for_printed_section, zone_map_version, normalize_label,
)
from foulball.mlb_api import get_lineup

LOG_RATE_LIMIT_MAX = 120   # per minute per IP, for /api/log/* writes
LOG_TOKEN = os.environ.get('FOULCAST_LOG_TOKEN', '')

log_context_cache = LRUCache(maxsize=60, ttl_seconds=1800)


def _log_token_ok() -> bool:
    """No token configured means open (local dev). Configured means required."""
    if not LOG_TOKEN:
        return True
    supplied = request.headers.get('X-Log-Token') or request.args.get('token', '')
    return secrets.compare_digest(supplied, LOG_TOKEN)


def _log_guard():
    """Shared precondition check for logging endpoints. Returns a response or None."""
    if not _log_token_ok():
        return jsonify({'error': 'invalid or missing log token'}), 403
    # ProxyFix has already resolved X-Forwarded-For to one trusted hop; reading
    # the raw header here would let a client pick its own rate-limit bucket.
    ip = request.remote_addr or '0.0.0.0'
    if not _check_rate_limit(ip, bucket='log', max_requests=LOG_RATE_LIMIT_MAX):
        return jsonify({'error': 'rate limited'}), 429
    return None


@log_api.route('/log')
def log_page():
    """Mobile logging form. Bookmark this on the phone."""
    return LOG_TEMPLATE


@log_api.route('/api/log/games')
def api_log_games():
    """Games available to log, with the park key each resolves to.

    Defaults to today. `?date=YYYY-MM-DD` reaches back for a game logged from
    a recording, which is a normal case — broadcasts work for this.
    """
    from datetime import date as _date
    qdate = request.args.get('date', '').strip()
    try:
        if qdate:
            d = _date.fromisoformat(qdate)
            games_raw = get_todays_games(d.strftime('%m/%d/%Y'))
        else:
            d = _date.today()
            games_raw = get_todays_games()
    except Exception as e:
        logger.error("Log games API error: %s", e)
        return jsonify({'games': [], 'date': qdate, 'error': str(e)})

    games = []
    for g in games_raw:
        games.append({
            'game_pk': g.game_id,
            'game_date': g.game_date,
            'away_id': g.away_team_id,
            'home_id': g.home_team_id,
            'away_name': g.away_team,
            'home_name': g.home_team,
            'away_abbrev': TEAM_ID_TO_ABBREV.get(g.away_team_id, ''),
            'home_abbrev': TEAM_ID_TO_ABBREV.get(g.home_team_id, ''),
            'park_key': g.stadium_key,
            'venue_name': g.venue_name,
            'time': g.game_time,
            'status': g.status,
        })
    return jsonify({'games': games, 'date': d.isoformat()})


@log_api.route('/api/log/context/<int:game_pk>')
def api_log_context(game_pk):
    """Everything the form needs for one game: park zones and both lineups.

    Lineups are best-effort. A missing lineup degrades to "Unknown batter",
    which is an acceptable row — batter identity is optional in the schema,
    section and side are not.
    """
    away_id = request.args.get('away', type=int)
    home_id = request.args.get('home', type=int)
    park_key = request.args.get('park', '')

    ck = f"ctx_{game_pk}_{away_id}_{home_id}_{park_key}"
    cached = log_context_cache.get(ck)
    if cached is not None:
        return jsonify(cached)

    stadium_key = park_key if park_key in STADIUMS else resolve_stadium_key(home_id or 0, None)
    stadium = STADIUMS.get(stadium_key, STADIUMS['yankee_stadium'])()

    def _lineup(team_id):
        if not team_id:
            return []
        try:
            return [{'name': p.name, 'mlb_id': p.mlb_id, 'bats': p.bats,
                     'order': p.batting_order}
                    for p in get_lineup(game_pk, team_id)[:9]]
        except Exception as e:
            logger.warning("Lineup lookup failed for team %s game %s: %s",
                           team_id, game_pk, e)
            return []

    out = {
        'game_pk': game_pk,
        'park_key': stadium_key,
        'park_name': stadium.name,
        'zone_map_version': zone_map_version(stadium),
        'zones': zone_catalog(stadium),
        'away_lineup': _lineup(away_id),
        'home_lineup': _lineup(home_id),
    }
    log_context_cache.set(ck, out)
    return jsonify(out)


@log_api.route('/api/log/session', methods=['POST'])
def api_log_session():
    """Open or update a logging session (who was watching, and what of)."""
    guard = _log_guard()
    if guard:
        return guard
    payload = request.get_json(silent=True) or {}

    park_key = payload.get('park_key')
    if park_key in STADIUMS:
        payload['zone_map_version'] = zone_map_version(STADIUMS[park_key]())

    try:
        with closing(foul_log.connect()) as conn:
            uid = foul_log.upsert_session(conn, payload)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error("Session write failed: %s", e)
        return jsonify({'error': 'storage error'}), 500
    return jsonify({'session_uid': uid})


def _resolve_zone(entry: dict) -> tuple[dict, str | None]:
    """Fill in model_zone_id from the printed section where possible.

    Returns the entry and an optional warning for the observer. `zone_source`
    records how the zone was arrived at, and every value is useful:

      printed_section  — the fan read the sign; the mapping is derived
      tapped_zone      — the fan tapped a zone directly; coarser, still real
      none             — no zone claims that printed section, which is a
                         finding about the park model rather than a bad row
      conflict         — the printed section and the tapped side disagree

    A conflict stores both raw fields and no zone. One of the two taps was
    wrong and there is no way to tell which, so resolving it either way would
    put a fabricated location into the only real spatial data here. The
    printed section still counts toward boundary work, where side is not the
    unit of analysis.
    """
    # Normalize up front so every path below returns the key explicitly rather
    # than leaving "no zone" as an absent key.
    entry['model_zone_id'] = entry.get('model_zone_id') or None

    park_key = entry.get('park_key')
    if park_key not in STADIUMS:
        return entry, None
    stadium = STADIUMS[park_key]()
    entry['zone_map_version'] = zone_map_version(stadium)

    printed = normalize_label(entry.get('printed_section') or '')
    if not printed:
        entry['zone_source'] = 'tapped_zone' if entry.get('model_zone_id') else 'none'
        return entry, None

    entry['printed_section'] = printed
    side = entry.get('side') if entry.get('side') in ('1B', '3B', 'HOME') else None
    zone = zone_for_printed_section(
        stadium, printed, level=entry.get('level') or None, side=side)

    if not zone:
        # Printed section is real but unmapped. Keep any tapped zone as a
        # fallback, and flag the source so calibration can separate the two.
        entry['zone_source'] = 'tapped_zone' if entry.get('model_zone_id') else 'none'
        return entry, None

    zone_side = next((s.side for s in stadium.sections
                      if s.section_id == zone), None)
    if side and zone_side and zone_side != side:
        entry['model_zone_id'] = None
        entry['zone_source'] = 'conflict'
        return entry, (f"Section {printed} is on the {zone_side} side, but you "
                       f"tapped {side}. Stored without a zone — check the number.")

    entry['model_zone_id'] = zone
    entry['zone_source'] = 'printed_section'
    return entry, None


@log_api.route('/api/log/foul', methods=['POST'])
def api_log_foul():
    """Store one or more observed fouls.

    Accepts a single entry or `{"entries": [...]}` so the phone can flush a
    queue built up while offline in one request. Every entry carries a
    client-generated `entry_uid`, so a retry after a timeout stores nothing
    twice — `stored` counts new rows, `duplicates` counts recognised retries,
    and both mean "it is safe to clear this from the queue".
    """
    guard = _log_guard()
    if guard:
        return guard

    body = request.get_json(silent=True) or {}
    entries = body.get('entries') if isinstance(body, dict) else None
    if entries is None:
        entries = [body]
    if not isinstance(entries, list) or not entries:
        return jsonify({'error': 'no entries'}), 400
    if len(entries) > 200:
        return jsonify({'error': 'too many entries in one request (max 200)'}), 400

    stored, duplicates, rejected, accepted_uids, warnings = 0, 0, [], [], []
    try:
        with closing(foul_log.connect()) as conn:
            for raw in entries:
                if not isinstance(raw, dict):
                    rejected.append({'entry_uid': None, 'errors': ['not an object']})
                    continue
                entry, warning = _resolve_zone(dict(raw))
                if warning:
                    warnings.append({'entry_uid': entry.get('entry_uid'),
                                     'message': warning})
                violations = foul_log.validate_foul(entry)
                if violations:
                    rejected.append({'entry_uid': entry.get('entry_uid'),
                                     'errors': violations})
                    continue
                uid, created = foul_log.record_foul(conn, entry)
                accepted_uids.append(uid)
                stored += 1 if created else 0
                duplicates += 0 if created else 1
            total = foul_log.counts(conn)
    except Exception as e:
        logger.error("Foul write failed: %s", e)
        return jsonify({'error': 'storage error'}), 500

    logger.info("Logged fouls: stored=%d duplicate=%d rejected=%d",
                stored, duplicates, len(rejected))
    return jsonify({
        'stored': stored,
        'duplicates': duplicates,
        'accepted': accepted_uids,
        'rejected': rejected,
        'warnings': warnings,
        'total_logged': total['live'],
    })


@log_api.route('/api/log/void', methods=['POST'])
def api_log_void():
    """Undo a mis-tap. Marks the row void; never deletes it."""
    guard = _log_guard()
    if guard:
        return guard
    body = request.get_json(silent=True) or {}
    uid = body.get('entry_uid')
    if not uid:
        return jsonify({'error': 'entry_uid required'}), 400
    try:
        with closing(foul_log.connect()) as conn:
            ok = foul_log.void_foul(conn, uid, body.get('reason', ''))
    except Exception as e:
        logger.error("Void failed: %s", e)
        return jsonify({'error': 'storage error'}), 500
    return jsonify({'voided': ok})


@log_api.route('/api/log/entries')
def api_log_entries():
    """Recent entries, for the on-screen list and undo.

    Voided rows are included so an undo visibly lands — an entry that silently
    vanishes invites the observer to undo the wrong one next. `total_logged`
    still counts only live rows.
    """
    if not _log_token_ok():
        return jsonify({'error': 'invalid or missing log token'}), 403
    game_pk = request.args.get('game_pk', type=int)
    limit = min(request.args.get('limit', default=25, type=int), 200)
    try:
        with closing(foul_log.connect()) as conn:
            rows = foul_log.list_fouls(conn, game_pk=game_pk, limit=limit,
                                       include_voided=True)
            total = foul_log.counts(conn)
    except Exception as e:
        logger.error("Entry list failed: %s", e)
        return jsonify({'error': 'storage error'}), 500
    return jsonify({'entries': rows, 'total_logged': total['live'],
                    'games_logged': total['games']})


@log_api.route('/api/log/export.<fmt>')
def api_log_export(fmt):
    """Full dump of the log as CSV or JSONL.

    Deliberately easy to reach. On a container with an ephemeral filesystem the
    database dies at redeploy unless FOULCAST_LOG_DB points at a mounted
    volume, and a one-URL backup is the cheapest insurance against that.
    """
    if not _log_token_ok():
        return jsonify({'error': 'invalid or missing log token'}), 403
    if fmt not in ('csv', 'jsonl'):
        return jsonify({'error': 'format must be csv or jsonl'}), 400
    try:
        with closing(foul_log.connect()) as conn:
            rows = foul_log.export_rows(conn)
    except Exception as e:
        logger.error("Export failed: %s", e)
        return jsonify({'error': 'storage error'}), 500

    from flask import Response
    if fmt == 'jsonl':
        body = "\n".join(json.dumps({k: r.get(k) for k in foul_log.EXPORT_COLUMNS})
                         for r in rows)
        return Response(body, mimetype='application/x-ndjson', headers={
            'Content-Disposition': 'attachment; filename=foul_log.jsonl'})

    import csv
    import io
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=foul_log.EXPORT_COLUMNS,
                            extrasaction='ignore')
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return Response(buf.getvalue(), mimetype='text/csv', headers={
        'Content-Disposition': 'attachment; filename=foul_log.csv'})


# ============================================================
# Public site (Step 11) — the 31 park pages plus a home page
# ============================================================
#
# Built ahead of time by `site_build.py` into ./site and served from memory.
# Nothing is simulated per request: the model run behind these pages is
# deterministic, and the netting and park figures on them were read from their
# sources on one day and are dated on the page. If ./site is absent the routes
# return 404 and the rest of the app is unaffected.

# Imported defensively: the foul log must keep working in a deployment that
# ships without the public site. With the demo retired, a deployment in that
# shape has nothing at the root but a redirect to a 404, which is a worse
# front page than it looks — `/parks/` says what to run.
try:
    from site_data import PARK_SOURCES as _PARK_SOURCES
    SITE_SLUGS = {s['slug'] for s in _PARK_SOURCES.values()}
except ImportError:            # pragma: no cover - deployment shape only
    logger.warning('site_data not importable; /parks/ will return 404')
    SITE_SLUGS = set()

SITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'site')
_site_cache: dict[str, str] = {}
_site_lock = threading.Lock()


def _site_html(rel_dir: str):
    """Read one built page, cached. `rel_dir` is '' for the home page."""
    with _site_lock:
        if rel_dir in _site_cache:
            return _site_cache[rel_dir]
    path = os.path.join(SITE_DIR, rel_dir, 'index.html') if rel_dir \
        else os.path.join(SITE_DIR, 'index.html')
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        html = fh.read()
    with _site_lock:
        _site_cache[rel_dir] = html
    return html


def _site_response(html: str):
    from flask import Response
    return Response(html, mimetype='text/html; charset=utf-8', headers={
        'Cache-Control': 'public, max-age=3600',
    })


@app.route('/')
def root():
    """The front door, which is the site.

    A redirect rather than a second copy of the home page: the built pages
    link to each other with relative hrefs under `/parks/`, so a home page
    served at `/` would have every tile pointing one directory too high. One
    URL for one page, and the sitemap names that one.

    302 and not 301. A permanent redirect is cached by browsers indefinitely
    and is the kind of thing that outlives the decision behind it; this one is
    a policy about what belongs at the root, and a future step that wants the
    site mounted at `/` outright should not have to fight a year of cached
    301s to do it.
    """
    return redirect('/parks/', code=302)


@app.route('/parks/')
def site_home():
    html = _site_html('')
    if html is None:
        return 'Site not built. Run: python site_build.py', 404
    return _site_response(html)


@app.route('/parks/<slug>/')
def site_park(slug):
    # Slugs are checked against the registry rather than sanitised, so no
    # request-supplied string ever reaches a filesystem path. `about` is the
    # one page under /parks/ that is not a ballpark: the site's explanatory
    # page, which every park page's caveat line links to.
    if slug != 'about' and slug not in SITE_SLUGS:
        return 'No such ballpark', 404
    html = _site_html(slug)
    if html is None:
        return 'Site not built. Run: python site_build.py', 404
    return _site_response(html)


@app.route('/robots.txt')
def robots_txt():
    from flask import Response
    body = ('User-agent: *\nAllow: /\n\n'
            f'Sitemap: {request.url_root.rstrip("/")}/sitemap.xml\n')
    return Response(body, mimetype='text/plain')


@app.route('/sitemap.xml')
def sitemap_xml():
    """Generated off the live host, so the built pages stay host-agnostic."""
    from flask import Response
    root = request.url_root.rstrip('/')
    slugs = sorted(SITE_SLUGS)
    urls = ''.join(f'<url><loc>{root}/parks/{s}/</loc></url>' for s in slugs)
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f'<url><loc>{root}/parks/</loc></url>'
            f'<url><loc>{root}/parks/about/</loc></url>{urls}</urlset>\n')
    return Response(body, mimetype='application/xml')


# === THE ONE TEMPLATE LEFT ===
# The foul log's form, loaded but not served while the log is shelved: one
# file read at import, and the blueprint it belongs to is ready the moment
# somebody registers it. `templates/demo.html` went with the prediction
# endpoints — see the module docstring for what it was publishing.

def _load_template(filename: str, fallback: str) -> str:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', filename)
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            return fh.read()
    return fallback


LOG_TEMPLATE = _load_template(
    'foul_log.html', '<h1>Template not found. Create templates/foul_log.html</h1>')


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("FOULCAST")
    logger.info("=" * 60)
    logger.info("Site: %d park pages from %s",
                len(SITE_SLUGS), SITE_DIR if SITE_SLUGS else '(not built)')
    logger.info("Open: http://localhost:5000")
    logger.info("Press Ctrl+C to stop")
    app.run(debug=False, port=5000)
