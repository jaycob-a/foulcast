# Step 8 — Foul ball logging

Shipped on branch `step-8`, 2026-08-09.

The season ends **2026-09-27**. Everything below exists to get observations into
a database before then, in a form that stays useful after the zone boundaries
change. Nothing here is polished, and that was the trade.

---

## What shipped

| File | What it is |
| --- | --- |
| `foulball/foul_log.py` | SQLite store — schema, validation, idempotent writes, export CLI |
| `foulball/seat_map.py` | Printed section label ↔ model zone, per park |
| `templates/foul_log.html` | The mobile form |
| `webapp_v2.py` (`/log`, `/api/log/*`) | Routes |
| `calibrate_log.py` | Logged fouls vs model predictions, over/under by zone |
| `tests/test_foul_log.py` | 43 test functions, 138 cases (3 run against all 31 parks) |

Open `/log` on a phone and bookmark it. No build step, no app store, no
dependency added — SQLite is in the standard library.

### Logging a foul

Four taps while the ball is in the air: **side → zone → what happened → LOG
FOUL**. Those four controls sit in the lower half of the screen, where a thumb
reaches. Game, inning and batter live above them because they are set once per
half-inning, not once per foul.

Only side and outcome are required. A hurried row with nothing else is still a
row, and a row is worth more than a correction that never gets typed.

Everything queues in `localStorage` and flushes when the phone has signal.
Each entry carries a client-generated UUID and the write is INSERT-OR-IGNORE on
it, so a retry after a dropped response stores nothing twice. Verified: two
fouls logged with `fetch` broken were held locally and flushed intact on
reconnect.

### Calibrating

```bash
python calibrate_log.py
```

Reads the log, runs the model for each logged game, and reports observed vs
expected by zone. `--offline` uses cached predictions and makes no API calls.

---

## The schema decision that matters

The brief asked for a schema that could eventually **correct** zone boundaries,
not just score them. That rules out one obvious design.

**Storing the zone ID alone does not work.** Every observation would inherit the
boundary estimate it exists to test. Re-cut a boundary and the whole log
retroactively means something else — the observations would have to be
re-collected, and after 2026-09-27 they cannot be.

**So the printed section number is the anchor.** `foulball/stadium.py`'s
provenance block is explicit that the six geometry numbers per section are
estimated for all 31 parks, but that section *names* track real seating charts.
All 344 of them carry a printed range — `(Sec 109-114)`, `(Sec FB17-FB29)`,
`(Sec 12L-14R)`. `seat_map.py` parses those into 2,956 printed labels across the
fleet and maps a fan's "226" onto a zone at log time.

Each row therefore stores three separate things:

- `printed_section` — a fact about the building
- `model_zone_id` — the current estimate of which zone that is
- `zone_map_version` — `1:<hash of the park's section table>`

A future analysis can discard every `model_zone_id`, re-derive them from
surveyed geometry, and re-score the entire log without re-collecting anything.
The fingerprint means rows logged before a `stadium.py` edit are identifiable as
such rather than silently reinterpreted.

**Contradictions are never resolved.** If the fan taps "3B side" and types a
section number that belongs to a 1B zone, one of those two taps is wrong and
there is no way to tell which. The row stores both raw fields, no zone, and
`zone_source = 'conflict'`, and the form says so immediately — nine innings of
the same mistake is worse than one interrupted tap. The printed section still
counts toward boundary work, where side is not the unit of analysis.

**Ambiguity is never guessed.** Dodger Stadium numbers its field decks
symmetrically, so `FD12` exists on both sides; 80 of the 2,956 labels are
ambiguous fleet-wide. The lookup returns `None` unless the side or level
resolves it — and the form always captures a side, so in practice it does. A
printed section that no zone claims is stored with `model_zone_id = NULL` and
`zone_source = 'none'`. Those rows are the most informative in the log: real
seats the park model does not cover.

## The second schema decision: coverage

A zone with zero logged fouls is ambiguous between "the model over-predicts
here" and "the observer was not looking at it." Without coverage data those are
the same measurement.

So `sessions` records innings watched and **what the observer could see**
(`scope`: whole bowl / 1B side / 3B side / behind home / broadcast). Calibration
restricts every comparison to observable zones and renormalizes the model's
shares over exactly those zones. A zone outside the view is dropped, not scored
as zero — scoring it as zero is the easiest false finding available here, and
there is a test that fails if that regresses.

A broadcast session additionally excludes upper decks; a centre-field camera
does not reliably show them.

---

## What the calibration establishes, and what it does not

**Does:** which zones the model sends too many or too few fouls into, for the
games in the log, among zones someone was watching.

**Does not — total foul volume.** A fan logs the fouls they saw, not the fouls
that happened. Logged totals are a sample of unknown rate, so only the *shape*
across zones is compared. Volume already has real ground truth in
`game_backtest.py`.

**Does not — whether the boundaries are in the right place.** A zone can take
exactly its predicted share while being drawn wrong. `AUDIT.md` is explicit that
the geometry gap "cannot be solved by logging": closing it needs a stadium
survey, CAD/GIS drawings, or Statcast's park geometry files. Section 4 of the
report tracks whether the observations will be there when that arrives, and is
blunt that the current count is nowhere near enough.

**Does not — anything about a zone nobody watched.**

Three guards keep the comparison honest: observable-zones-only, renormalized
shares, and a Bonferroni-adjusted significance threshold (11–16 zones per park
at p<0.05 produces roughly one false flag per park by construction). Zones below
the evidence gate report `insufficient data` rather than a ratio, which is what
almost everything will say until there are 60–100 fouls logged in one park.

**A bias this does not correct:** fans notice balls that come near them. Logged
fouls probably over-represent zones close to the observer's seat, which looks
identical to the model under-predicting there. `observer_section` is recorded on
every session so it can be tested once there are sessions from different seats.
It cannot be tested from one vantage point, and the first several hundred rows
will likely all come from one.

---

## Before deploying

1. **Set `FOULCAST_LOG_DB` to a mounted volume.** The default is
   `./data/foul_log.db`, and a Railway container's filesystem is wiped on every
   redeploy. A redeploy after a logged game destroys the game.
2. **Set `FOULCAST_LOG_TOKEN`.** Without it, `/api/log/foul` is an open write
   endpoint on the only real dataset in this project.
3. **Export after every game:** `/api/log/export.jsonl`, or locally
   `python -m foulball.foul_log --export data/foul_log_export.jsonl`. The `.db`
   is gitignored; the JSONL is meant to be committed.

---

## Three bugs the browser found, and why they mattered

All three were data-loss or data-corruption paths, and none showed up in unit
tests — they only appeared when the real form talked to a real server.

1. **`database is locked` on the very first foul of a game.** `connect()` was
   issuing `PRAGMA journal_mode=WAL` per connection. SQLite returns
   SQLITE_BUSY for a journal-mode change *without consulting the busy
   handler*, so the 10-second retry timeout never applied, and the form's
   three near-simultaneous requests collided. Setup now runs once per process
   per file. Regression test included, and confirmed to fail against the old
   code.
2. **A foreign key stranding an offline game.** `fouls.session_uid` referenced
   `sessions`, so a phone that started the game with no signal produced fouls
   the server rejected forever — the queue could never drain. The foreign key
   is gone; the trade is written into the schema comment. The form also
   re-sends the session before draining the queue.
3. **A section number silently overriding the tapped side.** Nationals Park
   section 130 belongs to a 3B zone; logged as "1B side", it resolved to the
   3B zone anyway, because the side hint is only consulted when the label is
   ambiguous. That wrote a location no observer reported. Now a conflict.

The offline queue held its entries through all of (1) and (2), which is the
one piece of good news in the list.

## Known gaps

- **No netting model.** A ball into the backstop screen is logged as
  `landing_type='netting'`, but the model still assigns it to the zone behind
  the net, so netting hits are compared against a prediction that does not know
  netting exists. Step 9 fixes the model side; the log field is already there
  and will be worth having when it does.
- **Sessions are only as honest as the observer.** Nothing verifies that
  someone who claims innings 1–9 actually watched all nine. `first_inning` /
  `last_inning` update from logged entries, which is a weak check.
- **The log has no notion of a foul that left the park** or landed somewhere no
  zone covers beyond the printed-section escape hatch.
- **One park at a time.** The readiness targets in Section 4 (~900 observations
  for a 16-zone park) are order-of-magnitude planning figures, not a power
  calculation. Logging one park deeply beats logging thirty shallowly.
