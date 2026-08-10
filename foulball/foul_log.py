"""
Foul ball observation log — storage layer.

WHAT THIS IS
============

Every other data source in this project is either a physics model or a
published number. `AUDIT.md` (2026-08-09 correction) establishes that the
per-section geometry in `stadium.py` is estimated, that no public source
publishes stadium seating coordinates, and that nobody publishes foul ball
landing data either. Rows in this database are the only first-party spatial
observations FoulCast has. They cannot be re-collected after the season ends
on 2026-09-27.

That scarcity drives three schema decisions that would otherwise look like
over-engineering for a form with six fields.

1. PRINTED SECTION IS THE ANCHOR, ZONE ID IS DERIVED
----------------------------------------------------
`printed_section` holds what is painted on the stadium sign — a fact about the
building. `model_zone_id` holds the zone that fact currently maps into — an
estimate, resolved at log time by `foulball/seat_map.py` and stamped with
`zone_map_version`.

If only the zone were stored, every observation would inherit the boundary
estimate it exists to test, and re-cutting a boundary would silently rewrite
history. Storing the printed label means a future analysis can throw away all
current zone assignments, re-derive them from surveyed geometry, and re-score
the entire log without re-collecting anything. That is the difference between
a log that can *correct* zone boundaries and one that can only *score* them.

2. COVERAGE IS RECORDED, NOT ASSUMED
------------------------------------
A zone with zero logged fouls is ambiguous between "the model over-predicts
here" and "the observer could not see it / was in line for a hot dog." Without
coverage, under-prediction and inattention are the same measurement.

So `sessions` records which innings were watched and what the observer could
actually see (`scope`). A fan in a 3B seat cannot observe the 1B upper deck;
`calibrate_log.py` restricts every comparison to the zones a session could
observe and renormalizes the model's shares over exactly those zones.

3. NOTHING IS DELETED, AND RETRIES ARE IDEMPOTENT
-------------------------------------------------
`entry_uid` is generated on the phone. The write is INSERT-OR-IGNORE on it, so
an offline queue can retry a submission any number of times without
double-counting a foul. Mis-taps are voided (`voided_at`, `void_reason`), never
removed — a voided row still proves an observer was watching that inning.

WHAT A ROW HERE DOES NOT ESTABLISH
==================================

A logged foul locates a ball in a *printed section*, and printed sections are
about as coarse as the zones. It does not measure the distance or angle bands
those zones are built from. `AUDIT.md` is explicit that the geometry gap
"cannot be solved by logging" — closing it needs a survey, CAD/GIS drawings or
Statcast park geometry. What logging can do is show *which* zones the model
sends too many or too few balls into, and accumulate a printed-section
histogram that a later re-cut can be fitted against.

Storage is SQLite via the standard library — no new dependency, one file, and
a file is easy to copy off a server before a redeploy destroys it.
"""
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from .log import get_logger

logger = get_logger(__name__)

SCHEMA_VERSION = 1

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Override with FOULCAST_LOG_DB. On a container with an ephemeral filesystem
# this MUST point at a mounted volume or every logged foul dies at redeploy.
DEFAULT_DB_PATH = os.path.join(_REPO_ROOT, "data", "foul_log.db")

# --- Controlled vocabularies -------------------------------------------------
# Kept as plain tuples rather than DB constraints so that a value added here
# does not require a migration, but an unknown value still fails validation
# before it reaches storage.

SIDES = ("1B", "3B", "HOME", "UNKNOWN")

# What the ball hit. 'seats' and 'netting' are the two the form asks for;
# the rest exist so an observer is never forced into a wrong answer.
LANDING_TYPES = ("seats", "netting", "concourse", "field_or_wall", "unknown")

# How sure the observer is about *where*, which is the only field a later
# boundary fit can be weighted by. 'guess' rows are stored and excluded by
# default from geometry work.
CONFIDENCES = ("exact", "approx", "guess")

VANTAGES = ("in_park", "broadcast")

# What the observer could actually see. Determines which zones a session's
# absence-of-fouls is evidence about.
SCOPES = ("full_bowl", "1b_side", "3b_side", "home_plate", "broadcast_frame")

HALVES = ("top", "bot")

# Zones observable from each scope, as a predicate on SeatSection.side.
_SCOPE_SIDES = {
    "full_bowl": ("1B", "3B", "HOME"),
    "1b_side": ("1B", "HOME"),
    "3b_side": ("3B", "HOME"),
    "home_plate": ("HOME",),
    # A broadcast centre-field camera shows the backstop and both infield
    # corners, but cuts off the upper decks and the deep foul corners. Side is
    # not the limiting factor; level is, and that is applied separately.
    "broadcast_frame": ("1B", "3B", "HOME"),
}

# Deck levels a broadcast frame reliably shows. Upper-deck landings are usually
# off-camera or ambiguous, so a broadcast session is not evidence about them.
_BROADCAST_LEVELS = ("field", "lower")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_uid     TEXT    NOT NULL UNIQUE,
    game_pk         INTEGER,
    game_date       TEXT,
    park_key        TEXT,
    home_team_id    INTEGER,
    away_team_id    INTEGER,
    home_team       TEXT,
    away_team       TEXT,
    observer        TEXT,
    vantage         TEXT,
    observer_section TEXT,
    scope           TEXT,
    first_inning    INTEGER,
    last_inning     INTEGER,
    innings_watched TEXT,
    started_at      TEXT,
    ended_at        TEXT,
    zone_map_version TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fouls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_uid       TEXT    NOT NULL UNIQUE,
    session_uid     TEXT,
    game_pk         INTEGER,
    game_date       TEXT,
    park_key        TEXT,

    inning          INTEGER,
    half            TEXT,
    batter_name     TEXT,
    batter_mlb_id   INTEGER,
    bat_side        TEXT,

    side            TEXT NOT NULL,
    printed_section TEXT,
    printed_row     TEXT,
    level           TEXT,

    -- model_zone_id is DERIVED and disposable; printed_section above is the
    -- durable record. zone_source says how it was arrived at:
    --   'printed_section' the fan read the sign and it mapped cleanly
    --   'tapped_zone'     the fan tapped a zone; coarser, still real
    --   'none'            no zone claims that printed section
    --   'conflict'        printed section and tapped side disagree; no zone
    --                     is stored, because guessing which tap was wrong
    --                     would fabricate a location
    model_zone_id   TEXT,
    zone_source     TEXT,
    zone_map_version TEXT,

    landing_type    TEXT NOT NULL,
    catchable       INTEGER,
    caught          INTEGER,
    location_confidence TEXT,

    observed_at     TEXT,
    logged_at       TEXT NOT NULL,
    client_ts       TEXT,

    voided_at       TEXT,
    void_reason     TEXT,
    notes           TEXT,
    app_version     TEXT,
    created_at      TEXT NOT NULL

    -- Deliberately NO foreign key on session_uid.
    --
    -- A phone that starts the game offline queues fouls whose session row the
    -- server has never seen. With a foreign key those inserts fail, the queue
    -- can never drain, and an entire game sits on a handset until someone
    -- notices. An orphaned session_uid costs a bit of metadata; a rejected
    -- foul costs an observation that cannot be re-collected. The observation
    -- wins. Calibration already skips games whose coverage is unknown, so an
    -- orphan degrades to "not comparable" rather than to a wrong comparison.
);

CREATE INDEX IF NOT EXISTS idx_fouls_game     ON fouls(game_pk);
CREATE INDEX IF NOT EXISTS idx_fouls_zone     ON fouls(park_key, model_zone_id);
CREATE INDEX IF NOT EXISTS idx_fouls_printed  ON fouls(park_key, printed_section);
CREATE INDEX IF NOT EXISTS idx_fouls_session  ON fouls(session_uid);
CREATE INDEX IF NOT EXISTS idx_sessions_game  ON sessions(game_pk);
"""


def utc_now() -> str:
    """Server-side UTC timestamp. Phones lie about their clocks; this doesn't."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db_path(path: str | None = None) -> str:
    return path or os.environ.get("FOULCAST_LOG_DB") or DEFAULT_DB_PATH


_init_lock = threading.Lock()
_initialized: set[str] = set()

BUSY_TIMEOUT_MS = 30_000


def connect(path: str | None = None) -> sqlite3.Connection:
    """Open (creating if needed) the log database.

    Setup runs once per process per file, not once per connection. This is not
    an optimisation: `PRAGMA journal_mode=WAL` needs an exclusive lock and
    returns SQLITE_BUSY *without* consulting the busy handler, so re-issuing it
    on every connection makes concurrent requests fail outright with "database
    is locked". The phone fires a session update, a foul write and an entry
    fetch within a few hundred milliseconds of each other, which is exactly the
    collision that produced.
    """
    p = db_path(path)
    if p != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    conn = sqlite3.connect(p, timeout=BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_initialized(conn, p)
    return conn


def _ensure_initialized(conn: sqlite3.Connection, key: str) -> None:
    # An in-memory database is private to its connection and is always new.
    in_memory = key == ":memory:"
    if not in_memory and key in _initialized:
        return
    with _init_lock:
        if not in_memory and key in _initialized:
            return
        if not in_memory:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            if str(mode).lower() != "wal":
                conn.execute("PRAGMA journal_mode=WAL")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version != SCHEMA_VERSION:
            init_db(conn)
        if not in_memory:
            _initialized.add(key)


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    conn.commit()


# --- Validation --------------------------------------------------------------

def validate_foul(payload: dict) -> list[str]:
    """Return a list of violation strings (empty = pass).

    Follows the `foulball/validators.py` convention: report every problem, do
    not raise. A phone that submits one bad field should be told what to fix,
    not have the whole batch rejected.
    """
    v = []

    if not payload.get("entry_uid"):
        v.append("entry_uid is required (client-generated, makes retries idempotent)")

    side = payload.get("side")
    if side not in SIDES:
        v.append(f"side {side!r} not in {SIDES}")

    lt = payload.get("landing_type")
    if lt not in LANDING_TYPES:
        v.append(f"landing_type {lt!r} not in {LANDING_TYPES}")

    conf = payload.get("location_confidence")
    if conf is not None and conf not in CONFIDENCES:
        v.append(f"location_confidence {conf!r} not in {CONFIDENCES}")

    half = payload.get("half")
    if half not in (None, "") and half not in HALVES:
        v.append(f"half {half!r} not in {HALVES}")

    inning = payload.get("inning")
    if inning is not None and inning != "":
        try:
            n = int(inning)
            if not 1 <= n <= 30:
                v.append(f"inning out of range 1-30: {n}")
        except (TypeError, ValueError):
            v.append(f"inning not an integer: {inning!r}")

    for flag in ("catchable", "caught"):
        val = payload.get(flag)
        if val not in (None, "", 0, 1, True, False):
            v.append(f"{flag} must be 0/1/None (unsure), got {val!r}")

    # A ball that hit the netting was by definition not catchable. Letting both
    # through would put a contradiction in the only real dataset here.
    if lt == "netting" and payload.get("catchable") in (1, True):
        v.append("landing_type='netting' cannot be catchable=1")
    if payload.get("caught") in (1, True) and payload.get("catchable") in (0, False):
        v.append("caught=1 contradicts catchable=0")

    return v


def validate_session(payload: dict) -> list[str]:
    v = []
    if not payload.get("session_uid"):
        v.append("session_uid is required")
    vantage = payload.get("vantage")
    if vantage is not None and vantage not in VANTAGES:
        v.append(f"vantage {vantage!r} not in {VANTAGES}")
    scope = payload.get("scope")
    if scope is not None and scope not in SCOPES:
        v.append(f"scope {scope!r} not in {SCOPES}")
    return v


def _as_int_flag(val):
    if val in (None, ""):
        return None
    return 1 if val in (1, True, "1", "true", "True", "yes") else 0


def _as_int(val):
    if val in (None, ""):
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


# --- Writes ------------------------------------------------------------------

def upsert_session(conn: sqlite3.Connection, payload: dict) -> str:
    """Create or update a logging session. Returns the session_uid.

    Sessions are updated in place as the observer keeps watching (last_inning
    creeps forward, ended_at gets set at the end), so this is an upsert rather
    than an insert.
    """
    violations = validate_session(payload)
    if violations:
        raise ValueError("; ".join(violations))

    uid = payload["session_uid"]
    now = utc_now()
    innings = payload.get("innings_watched")
    if isinstance(innings, (list, tuple)):
        innings = json.dumps(sorted({int(i) for i in innings}))

    cols = {
        "session_uid": uid,
        "game_pk": _as_int(payload.get("game_pk")),
        "game_date": payload.get("game_date"),
        "park_key": payload.get("park_key"),
        "home_team_id": _as_int(payload.get("home_team_id")),
        "away_team_id": _as_int(payload.get("away_team_id")),
        "home_team": payload.get("home_team"),
        "away_team": payload.get("away_team"),
        "observer": payload.get("observer"),
        "vantage": payload.get("vantage"),
        "observer_section": payload.get("observer_section"),
        "scope": payload.get("scope"),
        "first_inning": _as_int(payload.get("first_inning")),
        "last_inning": _as_int(payload.get("last_inning")),
        "innings_watched": innings,
        "started_at": payload.get("started_at") or now,
        "ended_at": payload.get("ended_at"),
        "zone_map_version": payload.get("zone_map_version"),
        "notes": payload.get("notes"),
    }

    existing = conn.execute(
        "SELECT id FROM sessions WHERE session_uid = ?", (uid,)
    ).fetchone()

    if existing is None:
        cols["created_at"] = now
        cols["updated_at"] = now
        fields = ", ".join(cols)
        marks = ", ".join("?" for _ in cols)
        conn.execute(f"INSERT INTO sessions ({fields}) VALUES ({marks})",
                     tuple(cols.values()))
    else:
        # Only overwrite fields the caller actually supplied, so a heartbeat
        # that carries just `last_inning` does not blank out the vantage.
        updates = {k: val for k, val in cols.items()
                   if val is not None and k != "session_uid"}
        updates["updated_at"] = now
        sets = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(f"UPDATE sessions SET {sets} WHERE session_uid = ?",
                     (*updates.values(), uid))
    conn.commit()
    return uid


def record_foul(conn: sqlite3.Connection, payload: dict) -> tuple[str, bool]:
    """Store one observed foul. Returns (entry_uid, created).

    `created=False` means this entry_uid was already stored — a retry from the
    phone's offline queue, not a second foul. The caller should treat that as
    success.
    """
    violations = validate_foul(payload)
    if violations:
        raise ValueError("; ".join(violations))

    uid = payload["entry_uid"]
    now = utc_now()

    cols = {
        "entry_uid": uid,
        "session_uid": payload.get("session_uid"),
        "game_pk": _as_int(payload.get("game_pk")),
        "game_date": payload.get("game_date"),
        "park_key": payload.get("park_key"),
        "inning": _as_int(payload.get("inning")),
        "half": payload.get("half") or None,
        "batter_name": payload.get("batter_name") or None,
        "batter_mlb_id": _as_int(payload.get("batter_mlb_id")),
        "bat_side": payload.get("bat_side") or None,
        "side": payload["side"],
        "printed_section": payload.get("printed_section") or None,
        "printed_row": payload.get("printed_row") or None,
        "level": payload.get("level") or None,
        "model_zone_id": payload.get("model_zone_id") or None,
        "zone_source": payload.get("zone_source") or None,
        "zone_map_version": payload.get("zone_map_version") or None,
        "landing_type": payload["landing_type"],
        "catchable": _as_int_flag(payload.get("catchable")),
        "caught": _as_int_flag(payload.get("caught")),
        "location_confidence": payload.get("location_confidence") or None,
        "observed_at": payload.get("observed_at") or None,
        "logged_at": now,
        "client_ts": payload.get("client_ts") or None,
        "notes": payload.get("notes") or None,
        "app_version": payload.get("app_version") or None,
        "created_at": now,
    }

    fields = ", ".join(cols)
    marks = ", ".join("?" for _ in cols)
    cur = conn.execute(
        f"INSERT OR IGNORE INTO fouls ({fields}) VALUES ({marks})",
        tuple(cols.values()),
    )
    conn.commit()
    return uid, cur.rowcount == 1


def void_foul(conn: sqlite3.Connection, entry_uid: str, reason: str = "") -> bool:
    """Mark an entry void. Nothing is ever deleted — see module docstring."""
    cur = conn.execute(
        "UPDATE fouls SET voided_at = ?, void_reason = ? "
        "WHERE entry_uid = ? AND voided_at IS NULL",
        (utc_now(), reason or "user undo", entry_uid),
    )
    conn.commit()
    return cur.rowcount == 1


def new_uid() -> str:
    return uuid.uuid4().hex


# --- Reads -------------------------------------------------------------------

def list_fouls(conn, game_pk: int | None = None, park_key: str | None = None,
               include_voided: bool = False, limit: int | None = None) -> list[dict]:
    where, params = [], []
    if game_pk is not None:
        where.append("game_pk = ?")
        params.append(int(game_pk))
    if park_key:
        where.append("park_key = ?")
        params.append(park_key)
    if not include_voided:
        where.append("voided_at IS NULL")
    sql = "SELECT * FROM fouls"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [dict(r) for r in conn.execute(sql, params)]


def list_sessions(conn, game_pk: int | None = None) -> list[dict]:
    sql = "SELECT * FROM sessions"
    params = []
    if game_pk is not None:
        sql += " WHERE game_pk = ?"
        params.append(int(game_pk))
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql, params)]


def logged_games(conn) -> list[dict]:
    """Games with at least one live (non-voided) observation."""
    rows = conn.execute(
        "SELECT game_pk, game_date, park_key, COUNT(*) AS n "
        "FROM fouls WHERE voided_at IS NULL AND game_pk IS NOT NULL "
        "GROUP BY game_pk, game_date, park_key ORDER BY game_date"
    )
    return [dict(r) for r in rows]


def counts(conn) -> dict:
    row = conn.execute(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN voided_at IS NULL THEN 1 ELSE 0 END) AS live, "
        "COUNT(DISTINCT game_pk) AS games "
        "FROM fouls"
    ).fetchone()
    return {"total": row["total"] or 0, "live": row["live"] or 0,
            "games": row["games"] or 0}


def session_innings(session: dict) -> set[int]:
    """Innings a session claims to have watched.

    `innings_watched` (an explicit JSON list) wins when present. Otherwise the
    inclusive first..last span is used. An empty set means "coverage unknown",
    and the calibration script refuses to draw count-based conclusions from
    such a session rather than assuming nine innings.
    """
    raw = session.get("innings_watched")
    if raw:
        try:
            vals = json.loads(raw) if isinstance(raw, str) else raw
            return {int(i) for i in vals}
        except (ValueError, TypeError):
            pass
    lo, hi = session.get("first_inning"), session.get("last_inning")
    if lo and hi and int(hi) >= int(lo):
        return set(range(int(lo), int(hi) + 1))
    return set()


def observable_zones(stadium, scope: str | None) -> set[str]:
    """Zone IDs a session with this scope could actually have observed.

    Zones outside this set are excluded from that session's comparison
    entirely — not counted as zero. Counting an unobservable zone as zero is
    the single easiest way to manufacture a false 'model over-predicts here'.
    """
    if not scope or scope not in _SCOPE_SIDES:
        # Unknown scope: assume nothing. Callers decide whether to fall back.
        return set()
    sides = _SCOPE_SIDES[scope]
    out = set()
    for sec in stadium.sections:
        if sec.side not in sides:
            continue
        if scope == "broadcast_frame" and sec.level not in _BROADCAST_LEVELS:
            continue
        out.add(sec.section_id)
    return out


# --- Export ------------------------------------------------------------------

EXPORT_COLUMNS = [
    "entry_uid", "session_uid", "game_pk", "game_date", "park_key",
    "inning", "half", "batter_name", "batter_mlb_id", "bat_side",
    "side", "printed_section", "printed_row", "level",
    "model_zone_id", "zone_source", "zone_map_version",
    "landing_type", "catchable", "caught", "location_confidence",
    "observed_at", "logged_at", "client_ts", "voided_at", "void_reason",
    "notes", "app_version",
]


def export_rows(conn, include_voided: bool = True) -> list[dict]:
    """Flat rows for CSV/JSONL export.

    Voided rows are included by default: an export is a backup, and a backup
    that quietly drops rows is not one.
    """
    return list_fouls(conn, include_voided=include_voided)


def _cli():
    """Backup and status, so neither needs a running web server.

        python -m foulball.foul_log --stats
        python -m foulball.foul_log --export data/foul_log_export.jsonl

    Run the export after every game and commit the result. The .db file is
    gitignored (binary, and it moves every write); the JSONL is the copy that
    survives a lost laptop or a container redeploy.
    """
    import argparse

    ap = argparse.ArgumentParser(description="Foul observation log utilities")
    ap.add_argument("--db", default=None, help="database path")
    ap.add_argument("--export", default=None, help="write JSONL backup here")
    ap.add_argument("--stats", action="store_true", help="print row counts")
    args = ap.parse_args()

    conn = connect(args.db)
    try:
        if args.stats or not args.export:
            c = counts(conn)
            print(f"database   : {db_path(args.db)}")
            print(f"entries    : {c['total']} ({c['live']} live)")
            print(f"games      : {c['games']}")
            for g in logged_games(conn):
                print(f"  game {g['game_pk']}  {g['game_date']}  "
                      f"{g['park_key']}  {g['n']} fouls")
            print(f"sessions   : {len(list_sessions(conn))}")
        if args.export:
            rows = export_rows(conn)
            os.makedirs(os.path.dirname(os.path.abspath(args.export)), exist_ok=True)
            with open(args.export, "w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps({k: r.get(k) for k in EXPORT_COLUMNS}) + "\n")
            print(f"wrote {len(rows)} rows to {args.export}")
    finally:
        conn.close()


if __name__ == "__main__":
    _cli()
