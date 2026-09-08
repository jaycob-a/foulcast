"""
site_build.py — generate the public FoulCast site: 31 park pages plus a home
page, as static HTML.

Static because the pages have to be fast on a phone on stadium wifi and have to
be indexable, and because nothing on them changes between requests: the model
run is deterministic (fixed lineup, fixed seed) and the sources behind the
netting and park figures were read on one day and are dated on the page.

    python site_build.py                     # build into ./site
    python site_build.py --sims 100          # faster, noisier model run
    python site_build.py --base-url https://example.com   # emit canonical tags
    python site_build.py --no-model          # re-render copy from the cache

The model run is the slow part (about 15 seconds a park), so it is cached to
`.cache/site/park_stats.json` and reused unless `--refresh` is passed. Copy
changes rebuild in under a second.

A cache entry is only reused when it was produced by the same model: every
entry carries `model_fingerprint()`, a hash of the source files the simulation
reads, and an entry whose fingerprint no longer matches is re-simulated. Before
that, the key was park + sims + seed alone, so halving Fenway's foul territory
in `PARK_PARAMS` and running the normal build produced byte-identical pages
without running a single simulation.

WHAT THIS FILE IS NOT ALLOWED TO DO
-----------------------------------
Four constraints come out of `AUDIT.md` and `NOTES.md` and are enforced by
`tests/test_site.py` rather than by care:

1. **No printed section numbers.** Every seating map this project holds has
   now been read against the zone tables in `stadium.py` (`MAP_FINDINGS.md`,
   Steps 11-16): thirty maps covering thirty of the 31 parks, and twenty-seven
   of them disagree with their table. Zones are named in words.
2. **Netting leads; the model follows.** The netting section is above the model
   section on every page, because netting is sourced and the model is an
   estimate. Where netting is a gap the page says so in the same position, at
   the same size.
3. **The word "safe" never appears.** Netting is not safety — the clubs' own
   pages say fans in netted sections remain exposed to balls leaving the field.
   The site says "behind netting" / "not behind netting" and "higher risk" /
   "lower risk".
4. **No accuracy claims.** The model has never been compared with observed foul
   landings, and every page has to be readable by someone who knows that.
5. **No foul line is named at a park whose sides are not established.** Sixteen
   of the 31 parks have a deciding source that names a side alongside a section
   number (`seat_map.SIDE_ANCHORS`); at the other fifteen, a reversal of the two
   sides would be invisible to every check this project has, and one park —
   Oriole Park — was reversed, mapped and cited for the whole of Step 10. So at
   those fifteen the two foul lines are folded into one row per matching pair,
   described as both lines at once. `_merge_foul_lines` does the folding and
   `PAIR_ZONE_WORDS` supplies the words. Do not write that count out again: it
   has moved five times and `side_counts()` computes it.

HOW IT IS ALLOWED TO LOOK
-------------------------
The visual language carries two of the constraints above rather than merely
decorating them, so it is written down here and not left to whoever edits the
CSS next.

**No figure is ever drawn as a length.** No bars, no filled shares, no meters.
Every number on these pages comes out of estimated geometry that has never been
compared with a foul ball, and a drawn length puts it on a scale and says it
was measured to that scale. Label left, figure right-aligned, hairline between,
and nothing else. `rows()` is the only thing that lays a figure out.

**Red belongs to one state and nothing else**: a seating area the club's own
statement places outside its netting. Not to gaps, not to disagreements, not to
this project's own defects — those are grey and ink, because a reader who sees
the same red on a missing source and on an unnetted seat learns nothing from
either. One accent teal does the section headings, links and structural marks;
everything else is ink on white.

The park page runs park and team, netting, distribution, the two readings, the
sourced figures, the seating-map read, and the limits, in that order. The
netting verdict is the largest type below the `h1` because it is the only
sourced thing on the page. The standing "never checked against a foul ball"
caveat is a hairline strip above it rather than a block, so that it states
itself without out-shouting the one fact somebody published.

**Prose never runs past 72 characters a line, at any width.** The cap is in
`ch` and not in `rem`, because these pages set text at four sizes and one rem
cap gave the 16px prose eighty characters and the .8rem strip a hundred and
twenty-eight. Everything wider than the cap is a table, a listing or a column,
never a paragraph.

Three widths, and the layout is checked at all three:

* **Below 34rem** — one column, 15px, edge to edge.
* **34rem to 64rem** — one column capped at 42rem. A 768px tablet reads a
  672px column, which is the measure, not the viewport.
* **64rem and up** — a two-column grid capped at 69rem (1104px). Panels pair
  in DOM order, so the reading sequence above survives: netting across both
  columns, then the distribution beside its two readings, then the sourced
  figures beside the seating-map read, then the limits across both. The two
  full-width panels fill the width rather than sitting in it: the netting
  verdict takes one column with its source beside it (`split_cols`), the
  seating listings run two-up, and the limits flow into two columns a block
  at a time. Rows are start-aligned, so a short panel leaves its column short
  rather than stretching a hairline box around empty space.
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from foulball.batter_profiles import YANKEES_2024_PROFILES, RED_SOX_2024_PROFILES
from foulball.matchup_engine import predict_game_fouls
from foulball.stadium import STADIUMS, PARK_PARAMS
from foulball.netting import join_park, PDL_RULE
from foulball.seat_map import check_side_anchors
from site_data import (
    PARK_SOURCES, ZONE_WORDS, PAIR_ZONE_WORDS, AREA_WORDS, GAP_WORDS,
    NET_HEIGHT_WORDS, COVER_WORDS, COVER_APPLIED, MODEL_LIMITS, RESEARCH_DATE,
    SIDE_STATE_WORDS, MAP_READS, MAP_READ_DATE, NO_MAP_READ,
    FOUL_AREA_CAVEAT, BACKSTOP_CAVEAT, OVERHANG_CAVEAT,
    CLEM_TABLE, CLEM_BASE, CLEM_OVERHANG_SNAPSHOT, SEAMHEADS_BASE,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, 'site')
CACHE = os.path.join(ROOT, '.cache', 'site', 'park_stats.json')

# Same configuration as tests/test_plausibility.py and park_sweep.py, so the
# numbers on the site are the numbers the rest of the repo checks.
STANDARD_RHP_MIX = {'FF': 0.30, 'SL': 0.20, 'CH': 0.15,
                    'SI': 0.15, 'CU': 0.10, 'FC': 0.10}
SEED = 42
SIMS = 400

BUILT = date.today().isoformat()

# The files whose contents decide the model's numbers. `run_park` calls
# `predict_game_fouls`, which reaches `trajectory`, `stadium` (park geometry
# and `PARK_PARAMS` both live there), `batter_profiles`, `validators` and
# `log`, and nothing else in the package.
#
# `netting` and `seat_map` are deliberately absent. They are in the import
# closure — `stadium` attaches a park's netting to the Stadium, and `netting`
# reads printed labels out of `seat_map` — but neither is consulted while
# fouls are being simulated or matched to a zone: they decide what the page
# says about a zone, not how many balls reach it. Including them would make
# every map read invalidate an eight-minute simulation for nothing.
# `tests/test_site.py::test_model_sources_cover_the_model_imports` walks the
# imports and fails if a new one appears that is not listed or excluded here.
MODEL_SOURCES = ('batter_profiles', 'log', 'matchup_engine', 'stadium',
                 'trajectory', 'validators')
DISPLAY_ONLY_SOURCES = ('netting', 'seat_map')


def model_fingerprint() -> str:
    """A hash of everything that decides the model's numbers.

    The cache key used to be park + sims + seed, which meant an edit to
    `stadium.py`, `trajectory.py`, `matchup_engine.py` or `PARK_PARAMS` left
    the cached run in place and the site kept serving the old numbers with no
    sign anything was wrong. Halving Fenway's foul territory and running the
    normal build rebuilt the pages byte for byte and never simulated. The
    fingerprint goes into every cache entry, so a model edit invalidates the
    cache by itself.
    """
    h = hashlib.sha256()
    for name in MODEL_SOURCES:
        with open(os.path.join(ROOT, 'foulball', f'{name}.py'), 'rb') as fh:
            # Line endings are normalised because this repo is worked on
            # under `core.autocrlf`: the same file is CRLF in one checkout
            # and LF in the next, and that must not read as a model change.
            h.update(name.encode() + b':' + fh.read().replace(b'\r\n', b'\n'))
    # The run configuration this file holds rather than imports: the seed, the
    # pitch mix, and which two lineups take the plate appearances.
    h.update(json.dumps({
        'seed': SEED,
        'mix': STANDARD_RHP_MIX,
        'lineups': [[repr(b) for b in side] for side in standard_lineups()],
    }, sort_keys=True).encode())
    return h.hexdigest()[:16]


# ============================================================
# The model run
# ============================================================

def standard_lineups():
    """The two lineups that make one game. Held identical across all parks so
    the only thing varying between pages is the park."""
    return [list(RED_SOX_2024_PROFILES.values()),
            list(YANKEES_2024_PROFILES.values())]


def run_park(park_key: str, sims: int, fingerprint: str | None = None) -> dict:
    """One full game at one park: both lineups, summed.

    A single `predict_game_fouls` call covers one team's plate appearances and
    is half a game — the units error `NOTES.md` records at the top.
    """
    np.random.seed(SEED)
    stadium = STADIUMS[park_key]()

    fouls: dict[str, float] = {}
    ev_weight: dict[str, float] = {}
    total = 0.0
    matched = 0.0

    for lineup in standard_lineups():
        pred = predict_game_fouls(lineup, 'Standard RHP', STANDARD_RHP_MIX,
                                  stadium, simulations_per_batter=sims)
        for e in pred.all_events:
            total += e.weight
            if e.section is None:
                continue
            matched += e.weight
            sid = e.section.section_id
            fouls[sid] = fouls.get(sid, 0.0) + e.weight
            ev_weight[sid] = ev_weight.get(sid, 0.0) + e.weight * e.exit_velocity

    for sec in stadium.sections:
        fouls.setdefault(sec.section_id, 0.0)

    return {
        'park': park_key,
        'sims': sims,
        'seed': SEED,
        'model': fingerprint if fingerprint is not None else model_fingerprint(),
        'zone_fouls': fouls,
        'zone_ev': {sid: (ev_weight.get(sid, 0.0) / w if w > 0 else 0.0)
                    for sid, w in fouls.items()},
        'into_seats': matched,
        'total_fouls': total,
        'unmatched': total - matched,
    }


def load_stats(refresh: bool, sims: int, cache_path: str = CACHE) -> dict:
    """Model stats for every park, from cache where possible.

    An entry is reused only when its simulation count and its model
    fingerprint both match the current ones, so a change anywhere in
    `MODEL_SOURCES` re-simulates every park without anyone having to remember
    to pass `--refresh`.
    """
    cached: dict = {}
    if os.path.exists(cache_path) and not refresh:
        with open(cache_path, encoding='utf-8') as fh:
            cached = json.load(fh)

    fingerprint = model_fingerprint()
    keys = list(STADIUMS)
    out = dict(cached)
    stale = [k for k, e in cached.items()
             if isinstance(e, dict) and e.get('model') != fingerprint]
    if stale and not refresh:
        print(f'  model has changed since {len(stale)} cached park(s) were '
              f'run; re-simulating those.')
    for i, key in enumerate(keys, 1):
        entry = cached.get(key)
        if (entry and entry.get('sims') == sims
                and entry.get('model') == fingerprint and not refresh):
            continue
        print(f'  [{i}/{len(keys)}] simulating {key} ...', flush=True)
        out[key] = run_park(key, sims, fingerprint)

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=1)
    return out


# ============================================================
# Turning a zone into words
# ============================================================

_PAREN = re.compile(r'\s*\(.*\)\s*$')
_SIDE_PREFIX = re.compile(r'^(1B|3B|Behind Plate)\s*')


def area_word(section) -> str:
    """The seating-area word from this park's own label, numbers stripped.

    `AUDIT.md`'s revised claim is that the section names track real seating
    charts "at the level of grouping and deck level" and that their numeric
    ranges are unverified everywhere and wrong at nine parks. This function
    keeps the first half and discards the second: the parenthesised section
    range goes, the product word stays, and only product words that carry
    location meaning survive `AREA_WORDS`.
    """
    name = _SIDE_PREFIX.sub('', _PAREN.sub('', section.name)).strip()
    return AREA_WORDS.get(name, '')


def zone_words(section) -> tuple[str, str, str]:
    """(heading, level phrase, area word) for one zone."""
    heading, level = ZONE_WORDS[section.section_id]
    return heading, level, area_word(section)


# ============================================================
# Assembling one park
# ============================================================

NETTING_CLUB_CAVEAT = (
    'Read the clubs literally: there is "some amount of netting or screening" '
    'in front of the listed seats, its "height and coverage will vary by '
    'section", and fans behind it "are still exposed to objects leaving the '
    'field of play". Behind netting is not fully protected, and no seat here '
    'is described as protected outright.'
)

# The one word per netting state, and the tag class that carries it. `split`
# is not a state `netting.py` produces — it is what a folded pair becomes when
# its two halves disagree, which can only happen at a park where the page
# cannot say which half is which.
STATUS_WORDS = {
    'netted': ('behind netting', 'tag-net'),
    'partially_netted': ('partly netted', 'tag-part'),
    'not_netted': ('not behind netting', 'tag-open'),
    'unknown': ('netting not verified', 'tag-unk'),
    'split': ('differs by foul line', 'tag-part'),
}


# How a netting source is named in the one line that credits it. The URL is
# the href; printing it as the link text as well wrapped to three lines on a
# phone, directly under the verdict it belongs to.
SOURCE_KIND_WORDS = {
    'primary': "the club's own page",
    'secondary_unverified': 'a second-hand source, never verified',
    'none': 'what was checked',
}

# The one-line form of each side verdict, for the disclosure summary. The full
# statement is `SIDE_STATE_WORDS`, inside the section.
SIDE_SHORT = {
    'confirmed': 'Which foul line is which is established here.',
    'untested': 'Which foul line is which has never been tested here.',
    'flipped': 'This model has the two foul lines reversed here.',
    'inconsistent': "This model's foul-line labels contradict their source.",
}

_COUNTS: dict[str, int] = {}


def netting_counts() -> dict[str, int]:
    """How many parks sit in each join state, over the whole registry.

    Several sentences on a park page quote a fleet-wide count ("that is true at
    ten of the 31 parks"). Those were hand-maintained and went stale the moment
    a guard changed, so they are computed here instead. Cached: the joins are
    cheap but there are 31 of them and every page asks.
    """
    if not _COUNTS:
        tally: dict[str, int] = {}
        for key in STADIUMS:
            j = join_park(STADIUMS[key](), key)
            tally[j.status] = tally.get(j.status, 0) + 1
        tally['gaps'] = sum(n for k, n in tally.items() if k != 'mapped')
        _COUNTS.update(tally)
    return _COUNTS


_SIDES: dict[str, int] = {}


def side_counts() -> dict[str, int]:
    """How many parks may name a foul line, and how many may not.

    Same reason as `netting_counts`, and the same lesson learned twice: this
    number was written out in prose in three places and moved five times
    between Step 11 and Step 16 as the seating maps were read. `named` is the
    count of parks where a deciding source establishes which line is which;
    `unnamed` is the count whose two foul lines are folded into one row.
    """
    if not _SIDES:
        named = 0
        for key in STADIUMS:
            sc = check_side_anchors(STADIUMS[key](), key)
            if sc.status == 'ok' and sc.deciding:
                named += 1
        _SIDES.update(named=named, unnamed=len(STADIUMS) - named)
    return _SIDES


def split_phrase(z: dict) -> str:
    """What a folded pair whose two halves disagree can honestly be said to be.

    This is the case the old side hedge was written for, and it is better said
    as a fact than as a warning: one line is covered, the other is not, and
    nothing in this project establishes which of the two you would be sitting
    on.
    """
    a, b = z['split']
    return (f'{STATUS_WORDS[a][0]} on one foul line and {STATUS_WORDS[b][0]} '
            f'on the other, with nothing to say which of the two is which')


def _merge_foul_lines(zones: list[dict]) -> list[dict]:
    """Fold each matching pair of foul-line zones into one row.

    For the parks where nothing establishes which line is which — fifteen of
    the 31 as of Step 16, and `side_counts()` is where that number lives.
    The alternative considered and rejected was to keep two rows and rename
    them "one foul line" and "the other" — which reads as an ordering the
    figures cannot support, and which still invites a reader to believe the
    two rows are telling them something different. They are not: the model
    builds every park as an exact mirror, so the pair differs only by noise.

    The folded figure is the **mean** of the two, not the sum. A row on this
    page is one seating area, and the row beside it — the seats behind the
    plate — is one seating area too. Summing the pair would make the foul-line
    rows twice the size of everything they sit next to and would reverse the
    ordering at most parks, on nothing but the fact that there are two of them.
    """
    singles, pairs = [], {}
    for z in zones:
        if z['id'][:3] in ('1B-', '3B-') and z['id'][3:] in PAIR_ZONE_WORDS:
            pairs.setdefault(z['id'][3:], []).append(z)
        else:
            singles.append(z)

    for suffix, pair in pairs.items():
        if len(pair) != 2:
            # No counterpart to fold into. Nothing here can name a side, so
            # leaving it alone would leak one; this never fires on the current
            # registry and is a guard rather than a case.
            raise SystemExit(f'unpaired foul-line zone {suffix!r}')
        a, b = pair
        heading, level = PAIR_ZONE_WORDS[suffix]
        statuses = tuple(sorted({a['status'], b['status']}))
        weight = a['fouls'] + b['fouls']
        singles.append({
            'id': 'LINES-' + suffix,
            'heading': heading,
            'level': level,
            # Two products with different names on the two lines cannot be
            # named without naming a line. Citizens Bank and Oracle Park each
            # have one such pair.
            'area': a['area'] if a['area'] == b['area'] else '',
            'fouls': weight / 2,
            'share': (a['share'] + b['share']) / 2,
            'ev': ((a['ev'] * a['fouls'] + b['ev'] * b['fouls']) / weight
                   if weight > 0 else 0.0),
            'status': statuses[0] if len(statuses) == 1 else 'split',
            'split': statuses if len(statuses) == 2 else (),
            # A ball cannot be caught through a net, and half a pair being
            # netted does not stop the other half being catchable — so a split
            # pair stays on the catching list, carrying its own caveat.
            'blocks_catch': a['blocks_catch'] and b['blocks_catch'],
        })

    singles.sort(key=lambda z: -z['fouls'])
    return singles


def build_park(park_key: str, stats: dict) -> dict:
    """Everything one page needs, resolved from the model and the sources."""
    stadium = STADIUMS[park_key]()
    src = PARK_SOURCES[park_key]
    join = join_park(stadium, park_key)
    params = PARK_PARAMS[park_key]
    st = stats[park_key]

    by_id = {s.section_id: s for s in stadium.sections}
    missing = set(by_id) - set(ZONE_WORDS)
    if missing:
        raise SystemExit(f'{park_key}: no plain-words phrase for {sorted(missing)}')

    into = st['into_seats']
    zones = []
    for sid, fouls in st['zone_fouls'].items():
        sec = by_id[sid]
        heading, level, area = zone_words(sec)
        zn = stadium.zone_netting.get(sid)
        zones.append({
            'id': sid,
            'heading': heading,
            'level': level,
            'area': area,
            'fouls': fouls,
            'share': (fouls / into * 100) if into else 0.0,
            'ev': st['zone_ev'].get(sid, 0.0),
            'status': zn.status if zn else 'unknown',
            'split': (),
            'blocks_catch': bool(zn and zn.blocks_catch),
        })
    zones.sort(key=lambda z: -z['fouls'])

    # Which foul line is which — and whether this page is allowed to say.
    #
    # `check_side_anchors` returns 'ok' from an unverified compilation as
    # readily as from a club page, and an 'ok' resting on a source
    # `SOURCED_DATA.md` itself could not confirm is not enough to put a foul
    # line's name on a public page. `deciding` is what separates the two.
    sc = check_side_anchors(stadium, park_key)
    state = {'ok': 'confirmed', 'flipped': 'flipped',
             'inconsistent': 'inconsistent'}.get(sc.status, 'untested')
    if not sc.deciding:
        # A verdict of any kind resting only on evidence this repo marks as
        # unconfirmed is not a verdict. It reads as untested, which is what it
        # is.
        state = 'untested'
    sides_named = state == 'confirmed'
    sides = {'state': state, 'named': sides_named}
    if not sides_named:
        zones = _merge_foul_lines(zones)

    # Netting, in the three states a reader has to be able to tell apart.
    net = {'state': join.status, 'park': join.park}
    if join.status == 'mapped':
        net['netted'] = [z for z in zones if z['status'] == 'netted']
        net['partial'] = [z for z in zones if z['status'] == 'partially_netted']
        net['open'] = [z for z in zones if z['status'] == 'not_netted']
        net['unknown'] = [z for z in zones if z['status'] == 'unknown']
        net['split'] = [z for z in zones if z['status'] == 'split']
        # Where the published extent lands differently on the two foul lines,
        # the page is asserting which line is which. At a park whose sides are
        # folded, that assertion is not made at all — the pair comes out as a
        # single `split` row saying the two differ and nothing says which is
        # which. It survives only at the parks that name their sides, where
        # what is at stake is no longer the mirror but where the boundaries
        # between areas fall, and it is hedged on that.
        by_side = {}
        for z in zones:
            if z['id'][:3] in ('1B-', '3B-'):
                by_side.setdefault(z['id'][:2], {})[z['id'][3:]] = z['status']
        net['sides_differ'] = (len(by_side) == 2
                               and by_side['1B'] != by_side['3B'])
    else:
        net['gap_label'], net['gap_text'] = GAP_WORDS[join.gap_kind]

    height = None
    if park_key in NET_HEIGHT_WORDS:
        height = NET_HEIGHT_WORDS[park_key][0]
    elif join.park.height and join.park.height != 'varies by section':
        height = join.park.height
    elif join.park.height == 'varies by section':
        height = 'published only as varying by section'

    return {
        'key': park_key,
        'slug': src['slug'],
        'name': stadium.name,
        'city': stadium.city,
        'team': stadium.team,
        'src': src,
        'params': params,
        'join': join,
        'net': net,
        'sides': sides,
        'map_read': MAP_READS.get(park_key),
        'net_height': height,
        'zones': zones,
        'into_seats': into,
        'total_fouls': st['total_fouls'],
        'unmatched_pct': (st['unmatched'] / st['total_fouls'] * 100)
                         if st['total_fouls'] else 0.0,
        'sims': st['sims'],
    }


# ============================================================
# Formatting helpers
# ============================================================

# Small counts read better spelled out in prose, and spelling them out also
# keeps them clear of the section-number checks in tests/test_site.py.
WORD_COUNT = ['None', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
              'Eight', 'Nine', 'Ten']


def count_word(n: int) -> str:
    """A small count in words, lowercase, falling back to the digits."""
    return WORD_COUNT[n].lower() if n < len(WORD_COUNT) else str(n)


def comma_list(bits) -> str:
    """`a`, `a and b`, `a, b and c` — for the one-line disclosure summaries."""
    bits = [b for b in bits if b]
    if len(bits) < 3:
        return ' and '.join(bits)
    return ', '.join(bits[:-1]) + ' and ' + bits[-1]


def fouls_str(x: float) -> str:
    # An area the model never reaches is worth saying plainly: at a couple of
    # parks it is a finding about the zone table rather than about the park.
    if x <= 0.0:
        return 'none'
    if x < 0.05:
        return 'under 0.1'
    return f'{x:.1f}'


def share_str(x: float) -> str:
    # Escaped, because this goes straight into a table cell: a bare "<1%"
    # opens what a parser is entitled to read as a tag.
    if x < 0.5:
        return '&lt;1%'
    return f'{x:.0f}%'


def zone_label(z: dict) -> str:
    """Heading plus the park's own area word, where it adds something."""
    if z['area']:
        return f"{z['heading']} <span class=\"area\">&mdash; {z['area']}</span>"
    return z['heading']


def e(s) -> str:
    return html.escape(str(s), quote=True)


# ============================================================
# The page shell
# ============================================================

CSS = """
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:#fff;color:#16181d;word-wrap:break-word;
 font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,
 "Helvetica Neue",sans-serif}
header,main,footer{max-width:42rem;margin:0 auto;padding:0 .85rem}
a{color:#0b6a74;text-decoration:underline;text-underline-offset:.12em}
a:hover{color:#084950}
p{margin:.55rem 0}
.crumb{font-size:.7rem;letter-spacing:.09em;text-transform:uppercase;
 margin:1rem 0 0;font-weight:700}
.crumb a{text-decoration:none}
h1{font-size:1.45rem;line-height:1.15;letter-spacing:-.02em;font-weight:700;
 margin:.3rem 0 .3rem}
.club{font-size:.72rem;letter-spacing:.09em;text-transform:uppercase;
 color:#5b6270;margin:0;padding-bottom:.75rem;border-bottom:2px solid #16181d}
.club b{color:#16181d;font-weight:700;border-left:3px solid #0b6a74;
 padding-left:.42rem;margin-right:.15rem}
.strip{font-size:.8rem;line-height:1.45;color:#4a505c;padding:.6rem 0;
 border-bottom:1px solid #dcdfe4;margin:0;max-width:72ch}
.strip b{color:#16181d}
.panel{border:1px solid #d5d9df;margin:1.15rem 0}
.panel>h2{margin:0;padding:.45rem .65rem;font-size:.74rem;font-weight:700;
 letter-spacing:.09em;text-transform:uppercase;color:#0b6a74;
 border-bottom:1px solid #d5d9df}
summary{cursor:pointer;display:block;list-style:none}
summary::-webkit-details-marker{display:none}
.panel>details>summary{padding:.45rem .65rem .5rem}
.panel>details[open]>summary{border-bottom:1px solid #d5d9df}
.dh{display:flex;justify-content:space-between;gap:.6rem;font-size:.74rem;
 font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:#0b6a74}
.dh::after{content:"+";font-size:.9rem;line-height:1.1}
details[open]>summary .dh::after{content:"\\2212"}
summary:hover .dh{color:#084950}
.ds{display:block;font-size:.83rem;line-height:1.45;color:#4a505c;
 margin-top:.22rem;max-width:72ch}
details.in{border-top:1px solid #d5d9df;margin:.95rem 0 0}
details.in>summary{padding:.5rem 0 .45rem}
.db{padding:.15rem 0 .1rem}
.db>:first-child{margin-top:.4rem}
.db>:last-child{margin-bottom:0}
.pb{padding:.7rem .65rem .85rem}
.pb>:first-child{margin-top:0}
.pb>:last-child{margin-bottom:0}
.pb p,.verdict,.warn,.ok,.gap{max-width:72ch}
h3{font-size:.94rem;font-weight:700;letter-spacing:-.01em;margin:1.2rem 0 .3rem}
h3.hs{border-left:3px solid #7b828e;padding-left:.5rem}
h3.hs-net{border-left-color:#0b6a74}
h3.hs-part,h3.hs-unk{border-left-color:#7b828e}
h3.hs-open{border-left-color:#a01523;color:#a01523}
ul.areas{list-style:none;padding:0;margin:.5rem 0 .2rem}
ul.areas li{padding:.4rem .1rem;border-bottom:1px solid #e4e7eb;font-weight:600}
ul.areas li:last-child{border-bottom:1px solid #b9bfc8}
.verdict{border:1px solid #c8ced6;border-top:3px solid #0b6a74;
 padding:.65rem .7rem;margin:0 0 .9rem}
.verdict .vl{font-size:1.14rem;line-height:1.28;font-weight:700;
 letter-spacing:-.015em;margin:0 0 .3rem}
.verdict.vgap{border-top-color:#16181d;background:#f4f5f7}
table{width:100%;border-collapse:collapse;margin:.6rem 0;font-size:.9rem}
th,td{text-align:left;vertical-align:top;padding:.4rem .1rem;
 border-bottom:1px solid #e4e7eb;line-height:1.4}
thead th{font-size:.66rem;letter-spacing:.07em;text-transform:uppercase;
 color:#5b6270;font-weight:700;border-bottom:1px solid #b9bfc8;
 padding-bottom:.2rem}
tbody tr:last-child td{border-bottom:1px solid #b9bfc8}
td.k{font-weight:600}
.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;
 width:1%;padding-left:.7rem}
.sub2{display:block;color:#5b6270;font-size:.78rem;line-height:1.35;
 font-weight:400;margin-top:.12rem}
.sub2+.sub2{margin-top:.35rem}
.area{color:#5b6270;font-weight:400}
.note{font-size:.83rem;line-height:1.45;color:#4a505c;
 border-left:2px solid #d5d9df;padding-left:.65rem;margin:.75rem 0;
 max-width:72ch}
.warn,.ok,.gap{border:1px solid #d5d9df;padding:.55rem .65rem;margin:.8rem 0;
 font-size:.88rem;line-height:1.45}
.warn{border-left:3px solid #7b828e}
.ok{border-left:3px solid #0b6a74}
.gap{border-left:3px solid #16181d;background:#f4f5f7}
.warn p,.ok p,.gap p{margin:.3rem 0}
.warn p:first-child,.ok p:first-child,.gap p:first-child{margin-top:0}
.warn p:last-child,.ok p:last-child,.gap p:last-child{margin-bottom:0}
.tag{display:inline-block;font-size:.63rem;font-weight:700;letter-spacing:.05em;
 text-transform:uppercase;line-height:1.55;padding:0 .28rem;white-space:nowrap;
 border:1px solid currentColor}
.tag-net{color:#0b6a74}
.tag-part{color:#4a505c}
.tag-open{color:#a01523}
.tag-unk{color:#767d89}
.tag-flag{color:#16181d}
ol.ranked{padding-left:1.15rem;margin:.5rem 0;font-size:.9rem}
ol.ranked li{margin:.32rem 0;line-height:1.45}
ul.parklist{list-style:none;padding:0;margin:.3rem 0 1.3rem}
ul.parklist li{border-bottom:1px solid #e4e7eb;padding:.48rem 0}
ul.parklist a{font-weight:700;text-decoration:none}
ul.parklist a:hover{text-decoration:underline}
.lhead{display:flex;justify-content:space-between;gap:.7rem;
 font-size:.66rem;letter-spacing:.07em;text-transform:uppercase;color:#5b6270;
 font-weight:700;border-bottom:1px solid #b9bfc8;padding-bottom:.2rem;
 margin-top:.7rem}
.row{display:flex;gap:.7rem;align-items:baseline;justify-content:space-between}
.rk{min-width:0}
.rn{flex:0 0 auto;text-align:right;font-variant-numeric:tabular-nums;
 font-weight:700}
.sub{color:#5b6270;font-size:.8rem;line-height:1.4}
.lede{font-size:.98rem}
.big{font-size:1rem;font-weight:700;font-variant-numeric:tabular-nums}
footer{border-top:2px solid #16181d;margin-top:1.7rem;padding-top:.8rem;
 padding-bottom:2rem;color:#5b6270;font-size:.8rem;line-height:1.45}
footer p{margin:.4rem 0}
hr{border:0;border-top:1px solid #d5d9df;margin:1.5rem 0}
@media (min-width:34rem){
 body{font-size:16px}
 header,main,footer{padding:0 1.1rem}
 .pb{padding:.85rem .85rem 1rem}
 .panel>h2{padding:.5rem .85rem}
}
@media (min-width:64rem){
 header,main,footer{max-width:69rem;padding:0 1.5rem}
 main{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);
  column-gap:1.4rem;align-items:start}
 main>.strip,main>.wide{grid-column:1/-1}
 .panel{margin:1.4rem 0 0}
 .wide .pb>h3{max-width:72ch}
 .split{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);
  column-gap:1.6rem;align-items:start}
 .split .verdict{max-width:none}
 .wide ul.areas{columns:2;column-gap:2.2rem;margin-top:.2rem}
 .wide ul.areas li{break-inside:avoid}
 .cols{columns:2;column-gap:2.2rem}
 .cols>div{break-inside:avoid;padding-bottom:.15rem}
 .cols>div>h3{margin-top:0}
 .cols>div+div>h3{margin-top:1.15rem}
 ul.parklist .rk{display:flex;flex-wrap:wrap;align-items:baseline;
  gap:.1rem .6rem}
 ul.parklist .rk .sub2{display:inline;margin-top:0}
}
@media (prefers-color-scheme:dark){
 body{background:#101216;color:#e4e7ee}
 a{color:#4fb6c0}a:hover{color:#7fd0d8}
 .club,.strip,.sub,.sub2,.area,.note,footer,thead th,.lhead{color:#98a0b0}
 .club{border-bottom-color:#e4e7ee}
 .club b{color:#e4e7ee;border-left-color:#4fb6c0}
 .strip{border-bottom-color:#262b34}
 .strip b{color:#e4e7ee}
 .panel,.verdict,.warn,.ok,.gap{border-color:#2b313b}
 .panel>h2,.dh{color:#4fb6c0}
 .panel>h2{border-bottom-color:#2b313b}
 .panel>details[open]>summary,details.in{border-color:#2b313b}
 summary:hover .dh{color:#7fd0d8}
 .ds{color:#98a0b0}
 h3,.verdict .vl{color:#e4e7ee}
 th,td{border-bottom-color:#232830}
 thead th,tbody tr:last-child td{border-bottom-color:#3a414d}
 .verdict{border-top-color:#4fb6c0}
 .verdict.vgap{border-top-color:#8891a0;background:#171a20}
 .note{border-left-color:#2b313b}
 .warn{border-left-color:#6d7482}
 .ok{border-left-color:#4fb6c0}
 .gap{border-left-color:#8891a0;background:#171a20}
 .tag-net{color:#4fb6c0}
 .tag-part{color:#a8b0be}
 .tag-open{color:#ef8189}
 .tag-unk{color:#8891a0}
 .tag-flag{color:#e4e7ee}
 h3.hs{border-left-color:#6d7482}
 h3.hs-net{border-left-color:#4fb6c0}
 h3.hs-part,h3.hs-unk{border-left-color:#6d7482}
 h3.hs-open{border-left-color:#ef8189;color:#ef8189}
 ul.areas li{border-bottom-color:#232830}
 ul.areas li:last-child{border-bottom-color:#3a414d}
 ul.parklist li{border-bottom-color:#232830}
 .lhead{border-bottom-color:#3a414d}
 footer{border-top-color:#e4e7ee}
 hr{border-top-color:#2b313b}
}
"""

# Whitespace is not free on a phone, and this is served static.
CSS_MIN = re.sub(r'\s*\n\s*', '', CSS).strip()


def page(title: str, description: str, body: str, canonical: str | None,
         base_url: str) -> str:
    head = [
        '<!doctype html>',
        '<html lang="en">',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f'<title>{e(title)}</title>',
        f'<meta name="description" content="{e(description)}">',
    ]
    if base_url and canonical is not None:
        head.append(f'<link rel="canonical" href="{e(base_url + canonical)}">')
    head.append(f'<style>{CSS_MIN}</style>')
    return '\n'.join(head) + '\n' + body + '\n</html>\n'


def panel(anchor: str, heading: str, body: str, wide: bool = False) -> str:
    """A hairline box with its heading in the one accent colour this site has.

    Every block on a park page is one of these, so the page reads as a stack
    of equal-weight panels and nothing inside them competes with the netting
    verdict at the top. The anchor stays on the `h2`, because
    `tests/test_site.py` reads the section order off those ids.

    `wide` puts a panel across both columns of the desktop grid. It is for the
    two that are about the whole page rather than one part of it — the netting
    verdict at the top and the limits at the foot — and it does nothing at all
    below 64rem, where there is one column and every panel is already the
    width of the page.
    """
    cls = 'panel wide' if wide else 'panel'
    return (f'<section class="{cls}"><h2 id="{anchor}">{e(heading)}</h2>'
            f'<div class="pb">\n{body}\n</div></section>')


def fold(anchor: str, heading: str, summary: str, body: str,
         wide: bool = False) -> str:
    """A panel whose body is closed until the reader asks for it.

    The reason a park page has these at all: the answer a reader came for is
    the netting verdict and the distribution, and everything else on the page
    is the working behind them. The working has to stay — none of it is
    removed — but it was standing between the reader and the answer, four
    screens of it.

    `summary` is the one line that stays visible when the section is shut, and
    it is not a label. It carries the finding, so that a reader who never
    opens the section still gets what the section concluded: the figures, the
    map's verdict, which side is which. Opening it gets the evidence.

    Native `<details>`, because this site is one request per page with no
    scripts, and it has to keep being one.
    """
    cls = 'panel wide' if wide else 'panel'
    return (f'<section class="{cls}"><details><summary id="{anchor}">'
            f'<span class="dh">{e(heading)}</span>'
            f'<span class="ds">{summary}</span></summary>'
            f'<div class="pb">\n{body}\n</div></details></section>')


def infold(heading: str, summary: str, body: str) -> str:
    """The same disclosure, nested inside a panel that stays open.

    For the two panels above the fold. The netting verdict is the answer and
    stays; the area-by-area listing that backs it is one click below it. The
    distribution table is the answer and stays; what qualifies it sits under
    a summary line that states the qualification rather than hiding it.
    """
    return (f'<details class="in"><summary>'
            f'<span class="dh">{e(heading)}</span>'
            f'<span class="ds">{summary}</span></summary>'
            f'<div class="db">\n{body}\n</div></details>')


def split_cols(lead: str, rest: str) -> str:
    """Two columns of a panel body on a wide screen, a stack on a narrow one.

    It exists for the netting panel at a park where the netting is a gap.
    That panel is full width because the verdict has to be, and at a gap park
    there is no seating listing to fill the second column — so on a 1440 the
    panel was a thousand pixels of border around six hundred of text. The
    statement takes one column and what kind of gap it is takes the other.
    """
    return (f'<div class="split"><div>\n{lead}\n</div>'
            f'<div>\n{rest}\n</div></div>')


def rows(pairs, head=None) -> str:
    """A label-left, figure-right table with a hairline between rows.

    The only presentation the figures on this site can carry. A bar, a filled
    share or anything else with a drawn length would put the numbers on a
    scale and imply they were measured to it; they come out of estimated
    geometry that has never been checked against a foul ball, and a plain
    right-aligned column claims nothing.
    """
    thead = (f'<thead><tr><th>{head[0]}</th><th class="n">{head[1]}</th></tr>'
             f'</thead>' if head else '')
    body = ''.join(f'<tr><td class="k">{k}</td><td class="n">{v}</td></tr>'
                   for k, v in pairs)
    return f'<table>{thead}<tbody>{body}</tbody></table>'


# ============================================================
# The park page
# ============================================================

def netting_section(p: dict) -> str:
    """Netting first, on every page, whatever its state.

    Three states, and a reader has to be able to tell them apart at a glance:
    the club published an extent and it fits this model's seating areas; the
    club published one and it does not fit; nobody published one at all. The
    verdict is the largest type on the page below the ballpark's name, because
    it is the only thing here that is sourced.

    The verdict and its source stay open. The area-by-area listing that backs
    it is a disclosure below them, with the tally of what came out where on
    the line that stays visible — a reader who never opens it still learns how
    many areas the netting covers and how many it leaves.
    """
    net, join, name = p['net'], p['join'], p['name']
    counts = netting_counts()

    src_line = (f'<p class="sub">Source: <a href="{e(join.park.source)}" '
                f'rel="nofollow">{e(SOURCE_KIND_WORDS.get(join.park.source_kind, "the source"))}'
                f'</a>, {e(join.park.year) if join.park.year else "undated"}, '
                f'read {e(join.park.retrieved)}.</p>')
    club_caveat = f'<p class="note">{NETTING_CLUB_CAVEAT}</p>'

    out = []

    if net['state'] == 'mapped':
        lead = (f'<div class="verdict"><p class="vl">Published, and it matches '
                f'the seating areas on this page.</p>'
                f'<p>The club states where its netting runs, and the areas it '
                f'names line up with the ones this model carries for '
                f'{e(name)} &mdash; true at {counts["mapped"]} of the 31 '
                f'parks here.</p></div>')

        def listing(zs, mark, head):
            """One netting state, its areas under it.

            The state is carried by the heading rather than repeated as a tag
            on every row: the rows under a heading are all in the same state
            by construction, and on a phone the repeated tag took a third of
            the row away from the only thing that varies, which is the name of
            the seating area. It is also where the one red on this site
            belongs — a whole block of seats the club's own statement leaves
            outside the netting, rather than a chip at the end of a line.
            """
            if not zs:
                return ''
            items = ''.join(
                f'<li>{zone_label(z)}<span class="sub2">{e(z["level"])}'
                + (f' &middot; {split_phrase(z)}' if z['split'] else '')
                + '</span></li>'
                for z in zs)
            return f'<h3 class="hs {mark}">{head}</h3><ul class="areas">{items}</ul>'

        out.append(listing(net['netted'], 'hs-net', 'Behind netting'))
        out.append(listing(net['partial'], 'hs-part', 'Partly behind netting'))
        if net['partial']:
            out.append(
                '<p class="note">Partly means the published extent covers some '
                'of the area and not the rest. Nobody publishes where the edge '
                'falls within it, so this model cannot split the area in two '
                'and treats the whole of it as reachable.</p>')
        out.append(listing(net['split'], 'hs-part',
                           'Covered on one foul line and not the other'))
        if net['split']:
            out.append(
                '<div class="warn"><p><strong>The club\'s netting reaches one '
                'of the two foul lines further than the other, and nothing '
                'says which line is which at this ballpark.</strong> The '
                'club\'s statement is sourced and is not in doubt; what is in '
                'doubt is this model\'s own labelling of the two sides, which '
                'no source here can check &mdash; and at one park that '
                'labelling turned out to be reversed. So these areas are '
                'shown as a matched pair, one covered and one not, rather '
                'than as a claim this page cannot stand behind.</p></div>')
        out.append(listing(net['open'], 'hs-open', 'Not behind netting'))
        out.append(listing(net['unknown'], 'hs-unk', 'Not mentioned either way'))
        if net['unknown']:
            out.append(
                '<p class="note">The club\'s statement does not name these '
                'areas at all. Not mentioned is not the same as not netted, so '
                'nothing is claimed about them here.</p>')
        if net['sides_differ']:
            # Only worth saying where the map actually moved the plate. Every
            # park but one now has a map read, and three of those reads agree
            # with the model, so the test can no longer be "is there a read".
            mr = p['map_read']
            tail = (' &mdash; and here the map puts the seats behind home '
                    'plate somewhere other than this model does, so the edge '
                    'of the netted run is softer than the lists look'
                    if mr and mr['outcome'] == 'disagrees' else '')
            out.append(
                '<div class="warn"><p><strong>The netting comes out different '
                'on the two foul lines here, so the two lines are named '
                'separately above.</strong> That naming is sourced at this '
                'ballpark, which is more than exists at '
                f'{side_counts()["unnamed"]} of the 31 parks. But what it '
                f'establishes is only which line is which, not where the '
                f'boundary between one area and the next falls{tail}.</p>'
                '</div>')

        if p['net_height']:
            out.append(f'<h3>Published net height</h3>'
                       f'<p>{e(p["net_height"])}.</p>')
            if p['key'] in NET_HEIGHT_WORDS:
                out.append('<p class="note">The club states these heights '
                           'against section numbers. This site does not print '
                           'section numbers, for the reason at the foot of the '
                           'page, so the same statement is given by position '
                           'instead.</p>')

        tally = [(len(net['netted']), 'behind netting'),
                 (len(net['partial']), 'partly behind it'),
                 (len(net['split']), 'covered on one foul line only'),
                 (len(net['open']), 'not behind netting'),
                 (len(net['unknown']), 'not mentioned either way')]
        summary = ('Areas on this page: '
                   + comma_list([f'{count_word(n)} {w}' for n, w in tally if n])
                   + '.')
        body = (split_cols(lead, src_line + '\n' + club_caveat)
                + infold('Every area, and where the netting leaves off',
                         summary, '\n'.join(x for x in out if x)))
        return panel('netting', 'Protective netting', body, wide=True)

    # A gap park. The verdict is that there is no verdict, and the sentence a
    # reader actually needs off it — that nothing below is marked as netted —
    # sits beside it rather than inside the disclosure.
    lead = (f'<div class="verdict vgap"><p class="vl">Not verified at '
            f'{e(name)}. {e(net["gap_label"])}.</p>'
            f'<p>{net["gap_text"]}</p></div>')
    beside = ('<p class="note">Nothing on this page is marked as behind '
              'netting. Read everything below knowing that some of the areas '
              'the model puts fouls into may be entirely behind a net.</p>')

    # Whose gap it is. `join.status` already separates the two and the page has
    # to as well: a reader told only "not verified" will read it as the club's
    # failing at every one of these parks, and at most of them it is this
    # model's.
    if join.status == 'join_gap':
        whose = (f'<strong>This one is this model\'s fault, not the '
                 f'club\'s.</strong> The club does publish where its netting '
                 f'runs; the seat labels this model carries cannot be '
                 f'reconciled with it. That is the case at '
                 f'{counts["join_gap"]} of the {counts["gaps"]}.')
    else:
        whose = (f'Here the gap is in what exists to read. At '
                 f'{counts["join_gap"]} of the {counts["gaps"]} it is the '
                 f'other way round &mdash; the club publishes an extent and '
                 f'this model\'s own seat labels cannot carry it.')
    out.append(f'<p>A gap is the normal case here: {counts["gaps"]} of the 31 '
               f'parks have no netting that can be attached to specific '
               f'seats. {whose}</p>')

    if join.park.source_kind == 'none':
        out.append(f'<p class="sub">Checked {e(join.park.retrieved)}: '
                   f'{e(join.park.source)}</p>')
        if join.gap_kind == 'no_source_at_all':
            out.append(f'<p class="note">The only rule that reaches this '
                       f'park: {e(PDL_RULE)}.</p>')
    else:
        out.append(src_line)

    if p['net_height']:
        out.append(f'<h3>Published net height</h3><p>{e(p["net_height"])}.</p>')
        if p['key'] in NET_HEIGHT_WORDS:
            out.append('<p class="note">The club states these heights against '
                       'section numbers. This site does not print section '
                       'numbers, for the reason at the foot of the page, so '
                       'the same statement is given by position instead.</p>')
    out.append(club_caveat)

    body = (split_cols(lead, beside)
            + infold('Whose gap this is, and what was checked',
                     f'{counts["gaps"]} of the 31 parks here are gaps, and at '
                     f'{counts["join_gap"]} of those the failure is this '
                     f'model\'s rather than the club\'s.',
                     '\n'.join(x for x in out if x)))
    return panel('netting', 'Protective netting', body, wide=True)


def zones_section(p: dict) -> str:
    """The distribution, as a plain table and nothing else.

    Label left, figure right, a hairline between. No bar and no filled share:
    the figures rest on estimated geometry, and a drawn length would put them
    on a scale and claim a precision none of it has.

    What qualifies the table is a disclosure under it, and the disclosure's
    visible line carries the qualification that matters — the share of fouls
    the model drops — rather than a label promising it somewhere inside.
    """
    table = rows([
        (zone_label(z)
         + f'<span class="sub2">{e(z["level"])} &middot; '
         + f'{share_str(z["share"])} of the fouls that reach seats'
         + (f' &middot; leaving the bat at about {z["ev"]:.0f} mph'
            if z['fouls'] >= 0.05 else '')
         + f' &middot; <span class="tag {STATUS_WORDS[z["status"]][1]}">'
         + f'{STATUS_WORDS[z["status"]][0]}</span>'
         + (f' &middot; {split_phrase(z)}' if z['split'] else '')
         + '</span>',
         fouls_str(z['fouls']))
        for z in p['zones']], head=('Seating area', 'Fouls a game'))

    notes = [f'''<div class="warn"><p><strong>About {p['unmatched_pct']:.0f}% of
the fouls this model produces at {e(p['name'])} land where it has no seating
area to put them</strong> &mdash; deep down the lines near the poles, in the gap
in front of the first row, or under a covered deck. They are counted in the
park's total and then dropped, which is why the figures above are a shape rather
than a census.</p></div>''']
    summary = (f'About {p["unmatched_pct"]:.0f}% of the fouls this model '
               f'produces here land where it has no seating area to put them.')
    if not p['sides']['named']:
        notes.append('''<p class="note">The two foul lines are one area each
rather than a first-base area and a third-base one, because nothing says which
line is which here. A figure on one of those rows is what reaches <em>one</em> of
the two lines, which keeps it comparable with the behind-plate rows beside it.
The model builds both lines identically, so the pair would differ only by
simulation noise in any case.</p>''')
        summary += ' The two foul lines are one row here, not two.'

    inner = f'''<p>One full game, both lineups, the same 18 batters at every park on this site,
so the park is the only thing that changes. Foul balls per game reaching each
area, largest first.</p>
{table}
<p class="sub">Model estimate. {p['sims']} simulations per batter, fixed seed.
Not a count of anything observed.</p>
{infold('How to read these figures', summary, chr(10).join(notes))}'''
    return panel('zones', 'Where the model puts the fouls', inner)


def readings_section(p: dict) -> str:
    """The same field, read two opposite ways.

    A netted zone is worth nothing to someone who wants a ball and is the best
    seat in the house to someone who does not want to be hit by one. Both
    readings come off `ZoneNetting.status`; neither is derived from the other.
    """
    mapped = p['net']['state'] == 'mapped'
    zones = p['zones']

    catchable = [z for z in zones if not z['blocks_catch'] and z['fouls'] >= 0.05]
    excluded = [z for z in zones if z['blocks_catch']]

    def caveat(z):
        """The reason a zone that stayed on the catching list is not clean."""
        if z['status'] == 'split':
            return (' <span class="tag tag-part">differs by foul line</span> '
                    '&mdash; netted on one of the two lines and not the other, '
                    'and nothing says which')
        if z['status'] == 'partially_netted':
            return ' <span class="tag tag-part">partly netted</span>'
        if z['status'] == 'unknown':
            return ' <span class="tag tag-unk">netting not verified</span>'
        return ''

    souvenir = ''.join(
        f'<li>{zone_label(z)} &mdash; about {fouls_str(z["fouls"])} a game'
        + caveat(z) + '</li>'
        for z in catchable[:6])

    if mapped:
        if excluded:
            exc = ''.join(f'<li>{zone_label(z)} &mdash; about '
                          f'{fouls_str(z["fouls"])} a game arrive here, and a '
                          f'net stands in front of them</li>' for z in excluded)
            note = (f'<p>Left out above because the club\'s netting covers '
                    f'them. Balls still arrive; they just cannot be caught:</p>'
                    f'<ol class="ranked">{exc}</ol>')
        else:
            note = ('<p>Nothing is excluded here: the club\'s published netting '
                    'does not fully cover any area this model tracks at this '
                    'park.</p>')
    else:
        note = ('<div class="gap"><p><strong>Nothing is excluded from this '
                'list, because this park\'s netting could not be '
                'verified.</strong> Where the netting is known, the areas '
                'behind it come off this list entirely. Here they cannot, so '
                'read the top of the list as where balls arrive, not where '
                'they can be caught.</p></div>')

    def mark(z):
        tag, cls = STATUS_WORDS[z['status']]
        chip = f'<span class="tag {cls}">{tag}</span>'
        return f'{chip} &mdash; {split_phrase(z)}' if z['split'] else chip

    risk = ''.join(
        f'<li>{zone_label(z)} &mdash; about {fouls_str(z["fouls"])} a game, '
        f'leaving the bat at about {z["ev"]:.0f} mph. ' + mark(z) + '</li>'
        for z in zones[:6] if z['fouls'] >= 0.05)

    if mapped:
        risk_note = (
            '<p>A netted area carries the same modelled foul traffic as it '
            'would without a net &mdash; the net stops balls reaching the '
            'seats, not being hit there. Read the marking as lower risk, not '
            'no risk: the clubs themselves say fans behind netting remain '
            'exposed to balls leaving the field.</p>')
    else:
        risk_note = (
            '<p>Every area is marked unverified, because this park\'s netting '
            'could not be attached to specific seats. Most of these parks '
            'certainly have a net; this site cannot tell you which areas it '
            'stands in front of, and so cannot tell you which of them is lower '
            'risk than the order above suggests.</p>')

    inner = f'''<p>Whether a net in front of a seat is good news depends on why you are asking.
One field decides both readings, and they point opposite ways.</p>

<h3>If you want to catch a ball</h3>
<p>Ranked by modelled foul traffic, with anything the sources place fully behind
netting removed &mdash; a ball cannot be caught through a net.</p>
<ol class="ranked">{souvenir}</ol>
{note}

<h3>If you want to know what is coming at you</h3>
<p>The same areas in the same order, with the netting shown rather than removed.
Speeds are how fast the ball left the bat, not how fast it arrives &mdash; it
slows on the way, by an amount this model computes and has never checked against
a measured landing.</p>
<ol class="ranked">{risk}</ol>
{risk_note}'''
    return panel('readings', 'The same figures, read two ways', inner)


def figures_section(p: dict) -> str:
    """The two published measurements, and the one that gates the upper deck.

    A figure left, the published number right, and everything that qualifies
    it — basis, conflicts, what the model does with it — under the label
    rather than beside the number, so nothing implies the number is more
    settled than its own footnote.

    Folded, because a reader who came for the netting and the distribution has
    not come for the provenance of a foul-territory estimate. The three
    numbers themselves are on the summary line, so folding costs them nothing.
    """
    src, params = p['src'], p['params']
    name = p['name']
    pairs = []

    def cell(label, *lines):
        """A figure's label with its qualifiers stacked under it.

        One line each: where the number came from, what disagrees with it,
        what the model does with it, and what it is worth. Run together they
        read as a single hedge, and the basis gets lost in the middle of it.
        """
        return label + ''.join(f'<span class="sub2">{x}</span>'
                               for x in lines if x)

    if src['foul_area']:
        val = f'<span class="big">{src["foul_area"]:,}</span> sq ft'
        head = e(src['foul_area_basis'])
        used = ('In the model: it scales how far this park\'s seating bands '
                'sit from home plate down the lines, against a fleet-median '
                'park of 22,900 sq ft.')
    else:
        val = '<span class="big">&mdash;</span>'
        head = f'<strong>Not published.</strong> {e(src["foul_area_basis"])}'
        used = ''
    pairs.append((cell('Foul territory area', head, used, FOUL_AREA_CAVEAT),
                  val))

    if src['backstop']:
        val = f'<span class="big">{src["backstop"]}</span> ft'
        head = ('Home plate to the fence behind it. '
                + e(src['backstop_basis']))
        conflict = (f'<strong>Sources disagree.</strong> '
                    f'{e(src["backstop_conflict"])}'
                    if src.get('backstop_conflict') else '')
        used = ('In the model: the front row behind the plate is pinned one '
                'foot beyond this figure &mdash; seats stand behind a fence, '
                'not on it. That foot is the smallest increment the sources '
                'can express, not a measurement of this park.')
    else:
        val = '<span class="big">&mdash;</span>'
        head = (f'Home plate to the fence behind it. '
                f'<strong>Not published.</strong> {e(src["backstop_basis"])}')
        conflict = used = ''
    pairs.append((cell('Backstop distance', head, conflict, used,
                       BACKSTOP_CAVEAT), val))

    if params.upper_overhang is not None:
        applied = COVER_APPLIED.get(params.upper_cover, False)
        cast = COVER_WORDS.get(params.upper_cover, 'something unidentified')
        # Both figures are equally published, so neither is set in the
        # muted sub-line type — they stack in the value column as they are.
        val = (f'<span class="big">{params.lower_overhang:.0f}%</span> lower'
               f'<br><span class="big">{params.upper_overhang:.0f}%</span> '
               f'upper')
        head = (f'<a href="{e(CLEM_OVERHANG_SNAPSHOT)}" rel="nofollow">Andrew '
                f'Clem\'s overhang columns</a>.')
        if applied:
            used = (f'In the model: the upper deck\'s cover is treated as '
                    f'{cast}, which a high foul ball would hit, so the covered '
                    f'part of that deck receives nothing here.')
        else:
            used = (f'In the model: the upper deck\'s cover is treated as '
                    f'{cast} &mdash; a foul pop flies underneath it &mdash; so '
                    f'the figure is <em>not</em> applied and the whole deck '
                    f'stays reachable.')
        caveat = OVERHANG_CAVEAT
    else:
        val = '<span class="big">&mdash;</span>'
        head = ('<strong>Not published.</strong> No cover figure exists for '
                'this park, so none is applied.')
        used = caveat = ''
    pairs.append((cell('Deck under cover', head, used, caveat), val))

    out = ['<p>Two published measurements place this park\'s seating in the '
           'model, and a third decides whether its upper deck can be reached '
           'at all. Each is given with where it came from and what disagrees '
           'with it.</p>',
           rows(pairs, head=('Figure', 'Published'))]

    if src.get('extra'):
        out.append(f'<div class="note"><p>{src["extra"]}</p></div>')

    links = [f'<a href="{e(CLEM_TABLE)}" rel="nofollow">Clem, Stadium '
             f'Statistics</a>']
    if src.get('clem_page'):
        links.append(f'<a href="{e(CLEM_BASE + src["clem_page"])}" '
                     f'rel="nofollow">Clem, {e(name)}</a>')
    if src.get('seamheads'):
        links.append(f'<a href="{e(SEAMHEADS_BASE + src["seamheads"])}" '
                     f'rel="nofollow">Seamheads ballpark database</a>')
    # A park with nothing published still gets its sources listed, but as
    # places that were checked rather than places a figure came from.
    lead = ('Checked on' if src['foul_area'] is None and src['backstop'] is None
            else 'Read')
    out.append(f'<p class="sub">{lead} {e(RESEARCH_DATE)}: '
               f'{" &middot; ".join(links)}.</p>')

    # The summary line carries the three numbers, so a shut section still
    # answers the question it exists to answer.
    bits = [f'{src["foul_area"]:,} sq ft of foul territory' if src['foul_area']
            else 'no published foul territory',
            f'a {src["backstop"]} ft backstop' if src['backstop']
            else 'no published backstop',
            f'{params.upper_overhang:.0f}% of the upper deck under cover'
            if params.upper_overhang is not None else 'no cover figure']
    listed = comma_list(bits)
    tail = ('The sources that were checked, and what they do not carry.'
            if src['foul_area'] is None and src['backstop'] is None
            and params.upper_overhang is None
            else 'Where each came from, and what disagrees with it.')
    return fold('figures', 'The sourced figures behind this park',
                f'{listed[0].upper()}{listed[1:]}. {tail}', '\n'.join(out))


def labels_section(p: dict) -> str:
    """What is known about the seat labels the areas on this page come from.

    It is the check on the model output: the netting listing is a join onto
    these labels and the distribution is attached to them, and neither is
    better than they are. `MAP_FINDINGS.md` made it necessary — thirty maps
    read, twenty-seven of them disagreeing with the table.

    Folded, with the verdict on the summary line. The three agreements are
    rendered differently and say so: an agreement that looks like a
    disagreement is as misleading as the reverse.
    """
    label, para = SIDE_STATE_WORDS[p['sides']['state']]
    out = ['<p>Every area on this page is a group of the ballpark\'s own '
           'printed seat labels. Nothing in this model measured them; they '
           'were written down from seating charts, and everything above is '
           'only as good as they are.</p>',
           '<h3>Which foul line is which</h3>']

    box = 'ok' if p['sides']['named'] else 'gap'
    out.append(f'<div class="{box}"><p><strong>{e(label)}.</strong> {para}</p>'
               f'</div>')

    mr = p['map_read']
    out.append('<h3>What this ballpark\'s own seating map shows</h3>')
    if mr:
        agrees = mr['outcome'] == 'agrees'
        verdict = ('It agrees with this model on both of the questions a map '
                   'can settle &mdash; which foul line is which, and where the '
                   'seats behind home plate are. It is one of three of the '
                   'thirty read that does.'
                   if agrees else
                   'It disagrees with this model in the following ways.')
        out.append(
            f'<p>{e(mr["map_of"][0].upper() + mr["map_of"][1:])} was read at '
            f'magnification on {e(mr.get("read_on", MAP_READ_DATE))} against '
            f'the labels this model carries. It is {e(mr["landmark"])}. As a '
            f'source it is {e(mr["quality"])}. {verdict}</p>')
        box = 'ok' if agrees else 'gap'
        for head, body in mr['findings']:
            out.append(f'<div class="{box}"><p><strong>{e(head)}.</strong> '
                       f'{e(body)}</p></div>')
        out.append(
            '<p class="note">None of this has been corrected in the model. '
            'Correcting it means rebuilding this park\'s seating table against '
            'the map, which is a change to the model and not to this page, and '
            'it has not been done.</p>'
            if not agrees else
            '<p class="note">Nothing here was corrected in the model, because '
            'nothing needed correcting on the two questions this map settles. '
            'That says nothing about the figures above: the map fixes which '
            'foul line is which and where the plate sits, and says nothing at '
            'all about how many foul balls reach any of these seats, which '
            'nothing on this site has ever checked.</p>')
        n = len(mr['findings'])
        map_bit = ('Its own seating map agrees on both questions a map can '
                   'settle.' if agrees else
                   f'Its own seating map disagrees with the labels in '
                   f'{count_word(n)} place{"" if n == 1 else "s"}.')
    else:
        out.append(f'<p>{NO_MAP_READ}</p>')
        map_bit = 'Its seating map has never been read.'

    return fold('labels', 'The seat labels these areas are built from',
                f'{SIDE_SHORT[p["sides"]["state"]]} {map_bit}',
                '\n'.join(out))


def limits_section(p: dict) -> str:
    # One of the limits quotes the fleet-wide count of parks whose two foul
    # lines cannot be told apart. It moved five times as the seating maps were
    # read, so it is substituted here rather than written out in the copy.
    # Each limit is its own block, so that on a wide screen the set can flow
    # into two columns without a heading parting company with its paragraph.
    items = ''.join(
        f'<div><h3>{e(t)}</h3>'
        f'<p>{body.replace("{unnamed_sides}", str(side_counts()["unnamed"]))}'
        f'</p></div>'
        for t, body in MODEL_LIMITS)
    inner = f'''<p>Written out rather than buried, because a reader who does not know these
things will read the figures above as more than they are.</p>
<div class="cols">{items}
<div><h3>Why there are no section numbers on this page</h3>
<p>This model carries a printed seat label for every area it tracks. At nine of
the 31 parks the club's own netting page contradicts them outright; at ten more,
the labels cannot describe a continuous seating bowl. Thirty seating maps have
since been read against them label by label, and <strong>twenty-seven of the
thirty disagreed</strong> &mdash; four with their foul lines cleanly reversed,
nine more crossed in a way no single swap would fix, twenty-four with the seats
behind home plate attached to a block somewhere else, several naming decks that
are not there. Three agreed. So areas here are described by where they are, and
no seat number is printed anywhere on this site.</p></div></div>'''
    return fold('limits', 'What this model does not know',
                f'It has never been checked against a foul ball, the seating '
                f'shape is not surveyed, and the two foul lines cannot be told '
                f'apart. {count_word(len(MODEL_LIMITS)).capitalize()} limits, '
                f'plus why no section number appears here.',
                inner, wide=True)


def park_page(p: dict, base_url: str) -> str:
    net_state = p['net']['state']
    if net_state == 'mapped':
        net_phrase = 'netting sourced from the club'
    else:
        net_phrase = 'netting not verified'

    title = f"{p['name']} foul balls by zone | FoulCast"
    desc = (f"Where foul balls land at {p['name']}, {p['city']} — a zone-by-zone "
            f"model estimate, {net_phrase}, and the park's sourced foul "
            f"territory and backstop figures. Never checked against real fouls.")
    if len(desc) > 300:
        desc = desc[:297] + '...'

    # The standing caveat is a hairline strip rather than a block, so that the
    # netting verdict below it is the largest thing on the page. It says the
    # same words it always did; it is the netting that has to lead the eye,
    # because the netting is the part of this page anybody sourced.
    body = f'''<body>
<header>
<p class="crumb"><a href="../">FoulCast</a></p>
<h1>Foul balls at {e(p['name'])}</h1>
<p class="club"><b>{e(p['team'])}</b> &middot; {e(p['city'])}</p>
</header>
<main>
<p class="strip"><b>Never checked against a real foul ball.</b> No public
record of where fouls land exists anywhere. The netting below is sourced from the
club; everything under it is a physics model that has never been validated
against an observed landing.</p>

{netting_section(p)}

{zones_section(p)}

{readings_section(p)}

{figures_section(p)}

{labels_section(p)}

{limits_section(p)}
</main>
<footer>
<p><a href="../">All 31 ballparks</a></p>
<p>Netting read from club pages on {e(RESEARCH_DATE)}. Park dimensions from
Andrew Clem's stadium statistics, cross-checked against the Seamheads ballpark
database. Model figures rebuilt {e(BUILT)}.</p>
</footer>
</body>'''
    return page(title, desc, body, f'/{p["slug"]}/', base_url)


# ============================================================
# The home page
# ============================================================

# The three groups the home page splits the 31 parks into, and the whole point
# of the split: `join.status` already distinguishes a park whose *source* is
# missing from a park whose source is fine and whose **model** cannot use it.
# The old page did not — it had one list of parks with netting and one list of
# parks without, which reads as a ranking of ballparks when the larger group is
# a list of this project's own defects.
GROUPS = [
    ('mapped',
     'Netting sourced, and this model\'s seating areas can carry it',
     'The club states where its netting runs and the areas it names line up '
     'with the areas this model carries, so these pages mark which areas are '
     'behind it. {confirmed_here} of them have had which foul line is which '
     'established by something outside this model. The rest have not, and '
     'their pages say so rather than naming a line.'),
    ('join_gap',
     'The club publishes its netting and this model cannot use it',
     '<strong>These are this model\'s failures, not the clubs\'.</strong> '
     'Every club in this group publishes where its netting runs. The seat '
     'labels this model carries cannot be reconciled with what they publish: '
     'the netting would have to miss the seats behind home plate, or skip a '
     'near area and resume at a further one, or run down a line this model has '
     'on the wrong side of the field. Netting does not do any of those things, '
     'so the model is the side of the disagreement that is wrong. This is the '
     'largest of the three groups, and it is a list of defects in this '
     'project.'),
    ('source_gap',
     'Nothing usable is published about the netting',
     'Here the gap is in what exists. Some clubs publish nothing about their '
     'netting at all; one declines on principle, stating that its own map '
     'cannot show where the netting is; one club\'s page contradicts itself; '
     'and at one park the club gives the two ends of the run while nothing '
     'published says where the seat numbering wraps behind home plate. '
     'Nothing on these pages is marked as behind netting, and that is a '
     'statement about the sources, not about the ballpark.'),
]

# Red belongs to one state on this site — a seating area the sources place
# outside the netting — so the two side verdicts that used to borrow it carry
# the plain ink mark instead. A reversed pair of foul lines is a defect in this
# project, not a fact about the ballpark, and it should not read as the same
# kind of thing as a ball arriving at an unnetted seat.
SIDE_TAGS = {
    'confirmed': ('sides established', 'tag-net'),
    'untested': ('sides untested', 'tag-unk'),
    'flipped': ('sides reversed', 'tag-flag'),
    'inconsistent': ('sides contradicted', 'tag-flag'),
}


def home_page(parks: list[dict], base_url: str) -> str:
    parks = sorted(parks, key=lambda p: p['name'])
    by_group = {k: [p for p in parks if p['join'].status == k]
                for k, _, _ in GROUPS}
    mapped = by_group['mapped']
    gaps = by_group['join_gap'] + by_group['source_gap']
    confirmed = [p for p in parks if p['sides']['named']]

    def row(p):
        tag, cls = SIDE_TAGS[p['sides']['state']]
        return (f'<li><div class="row"><div class="rk">'
                f'<a href="{e(p["slug"])}/">{e(p["name"])}</a> '
                f'<span class="tag {cls}">{tag}</span>'
                f'<span class="sub2">{e(p["city"])} &middot; '
                f'{e(p["team"])}</span></div>'
                f'<div class="rn">{p["into_seats"]:.0f}</div></div></li>')

    def group(key, heading, lead):
        listed = ''.join(row(p) for p in by_group[key])
        lead = lead.format(
            confirmed_here=WORD_COUNT[sum(1 for p in by_group[key]
                                          if p['sides']['named'])])
        return (f'<h3>{heading} <span class="sub">({len(by_group[key])})</span>'
                f'</h3><p>{lead}</p>'
                f'<div class="lhead"><span>Ballpark</span>'
                f'<span>Fouls a game reaching seats</span></div>'
                f'<ul class="parklist">{listed}</ul>')

    groups = '\n'.join(group(*g) for g in GROUPS)

    title = 'Foul balls by ballpark — where they land, and what the netting covers | FoulCast'
    desc = ('Foul ball estimates for all 31 major and minor league ballparks: '
            'where they land by seating area, what each club publishes about '
            'its protective netting, and where that netting is unknown.')

    body = f'''<body>
<header>
<p class="crumb">FoulCast</p>
<h1>Where foul balls land, ballpark by ballpark</h1>
<p class="club">31 ballparks &middot; netting first, model second</p>
</header>
<main>
<p class="strip"><b>The model has never been checked against a real foul
ball.</b> There is no public record of where foul balls actually land &mdash;
Statcast logs that a foul happened, not where it came down. So the
distributions on these pages are estimates from physics and published park
dimensions, and no page here puts a number on how often the model gets it
right, because there is nothing to compute one from.</p>

<section class="panel"><h2 id="sourced">What is sourced and what is not</h2>
<div class="pb">
<p class="lede">Every page here does two things: it says what the club publishes
about the protective netting in front of a given set of seats, and it estimates
how many foul balls a game reach those seats. The first is sourced. The second
is a model.</p>
<p><strong>Netting is sourced.</strong> Each club's own current netting or
seating page was read in a browser on {e(RESEARCH_DATE)}. Where the club
publishes an extent that can be matched to specific seating areas, those areas
are marked. That is true at <strong>{len(mapped)} of the 31 parks</strong>.</p>
<p><strong>At the other {len(gaps)} it is a gap</strong>, and the pages say so
in the same place, at the same size, rather than leaving a blank. But the two
kinds of gap are not the same thing, and the list below keeps them apart: at
<strong>{len(by_group['source_gap'])} parks nothing usable is
published</strong>, and at <strong>{len(by_group['join_gap'])} the club
publishes perfectly good netting information that this model's own seat labels
cannot be reconciled with</strong>. The second group is larger than the first
and it is a list of this project's defects, not a list of clubs that fell
short.</p>
<p><strong>The park dimensions are sourced</strong> &mdash; foul territory area
and backstop distance, from Andrew Clem's stadium statistics, cross-checked
against the Seamheads ballpark database, with the disagreements between them
stated on each page. They place each park's seating. They do not shape it: no
public source gives the angle of a seating area off the foul line or the height
of a deck in feet, for any ballpark, so every park here shares one bowl shape
and every park is modelled as an exact left-right mirror.</p>
<p>One consequence is visible from the list below and worth saying out loud: the
seats at field level behind home plate come out busiest at all 31 parks. That is
partly a real effect &mdash; balls deflected back over the catcher have to land
somewhere, and it is why there is a screen there &mdash; and partly an artefact
of every park sharing one bowl shape. It is not a finding about any individual
ballpark.</p>
</div></section>

<section class="panel"><h2 id="sides">Which foul line is which, and why most
pages will not say</h2>
<div class="pb">
<p>Every ballpark on this site is modelled as an exact left-right mirror, which
means a park with its two sides written down the wrong way round produces
figures identical to one with them the right way round. This model cannot see
the difference from the inside, and neither can a published netting range: it
gives the two ends of the run, not which foul line each end is on. Only a
source that names a side alongside specific seats can settle it, and
<strong>{len(confirmed)} of the 31 parks have one</strong>.</p>
<p>This is not a hypothetical. At one ballpark the two sides <em>were</em>
written down backwards, and it sat in the sourced-netting group below, cited and
apparently matched, until its own seating map was read. So at the parks with
nothing to check against, the two foul lines are shown as a single seating area
each and no area is called first-base or third-base. Every park page states its
own position on this, in the same place, whichever of the four it is in.</p>
</div></section>

<section class="panel"><h2 id="numbers">Why there are no section numbers
here</h2>
<div class="pb">
<p>This model carries printed seat labels for every area it tracks. The first
check on them was against the clubs' netting pages alone: nine parks' labels are
contradicted outright there, and ten more cannot describe a continuous seating
bowl. Every seating map this project holds has since been read directly, at
magnification, and compared label by label &mdash; a far stronger check, and one
the netting pages could not make. <strong>Thirty maps, covering thirty of the 31
parks, and twenty-seven of them disagreed with the model.</strong></p>
<p>Four ballparks have their two foul lines cleanly reversed, and at nine more
the two lines are crossed in a way no single swap would fix &mdash; an area the
model calls third base sitting out in right field, or a ballpark that numbers
one foul line odd and the other even, so every area the model draws there is
half one line and half the other. At twenty-four the seats behind home plate are
not the seats this model calls the seats behind home plate, in one case eighteen
positions away at a corner of the ballpark. Several name whole decks that are
not in the building.</p>
<p>Three ballparks agreed, on both questions a map can settle. They are stated
on their own pages in the same place and at the same length as the twenty-seven,
because they were checked the same way, and an agreement nobody publishes reads
as an absence of evidence. The thirty-first park has no map to read at all, and
its page says so. So seating is described by position &mdash; the lower bowl
behind the plate, the dugout boxes down the foul lines &mdash; and no seat
number appears anywhere on this site.</p>
</div></section>

<section class="panel"><h2 id="readings">The same figures read two ways</h2>
<div class="pb">
<p>A net in front of a seat means opposite things depending on why you are
asking. If you want to take a ball home, a netted area is worth nothing and
comes off the list. If you want to know what is coming at you, the same area is
the one with something standing in front of it. Every park page gives both
readings off the same field, and neither is derived from the other.</p>
<p>No seat on this site is described as protected outright, and none of them is
called a good bet either. The clubs' own netting pages say fans sitting behind
netting "are still exposed to objects leaving the field of play", and this model
has never seen a real foul ball. Seats are described as behind netting or not
behind netting; risk is described as higher or lower.</p>
</div></section>

<section class="panel wide"><h2 id="parks">All 31 ballparks</h2>
<div class="pb">
<p>Grouped by what is actually known, not by how good the ballpark is. The tag
against each park is whether anything establishes which of its two foul lines is
which &mdash; a separate question from netting, and one where the answer is no
at most of them. The figure on the right is this model's estimate of how many
foul balls a game reach seats at all, and nothing has ever checked it against
one.</p>

{groups}
</div></section>
</main>
<footer>
<p>Netting read from club pages on {e(RESEARCH_DATE)}. Park dimensions from
Andrew Clem's stadium statistics and the Seamheads ballpark database. Model
figures rebuilt {e(BUILT)}.</p>
<p>FoulCast is a model of foul ball flight. It is not affiliated with Major
League Baseball or with any club, and nothing on it will keep a ball from
reaching you.</p>
</footer>
</body>'''
    return page(title, desc, body, '/', base_url)


# ============================================================
# Build
# ============================================================

def write(path: str, text: str) -> int:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    return len(text.encode('utf-8'))


def build(out_dir: str, base_url: str, sims: int, refresh: bool = False,
          no_model: bool = False, cache_path: str = CACHE) -> list[dict]:
    if no_model and not os.path.exists(cache_path):
        raise SystemExit('--no-model needs a cache; run once without it first.')
    if no_model:
        print('Using the cached model run as-is.')
        with open(cache_path, encoding='utf-8') as fh:
            stats = json.load(fh)
        missing = set(STADIUMS) - set(stats)
        if missing:
            raise SystemExit(f'cache is missing {sorted(missing)}')
        # --no-model is an explicit instruction not to simulate, so this warns
        # rather than refusing — but it says so, because the numbers it is
        # about to render came out of a model that no longer exists.
        fingerprint = model_fingerprint()
        behind = sorted(k for k, e in stats.items()
                        if e.get('model') != fingerprint)
        if behind:
            print(f'  WARNING: the model has changed since {len(behind)} of '
                  f'these {len(stats)} entries were run, starting with '
                  f'{behind[0]}. These pages will carry the old numbers. '
                  f'Rebuild without --no-model to fix them.')
    else:
        print('Model run:')
        stats = load_stats(refresh=refresh, sims=sims, cache_path=cache_path)

    parks = [build_park(k, stats) for k in STADIUMS]

    total = 0
    for p in parks:
        total += write(os.path.join(out_dir, p['slug'], 'index.html'),
                       park_page(p, base_url))
    total += write(os.path.join(out_dir, 'index.html'),
                   home_page(parks, base_url))

    if base_url:
        urls = ''.join(
            f'<url><loc>{e(base_url)}/{e(p["slug"])}/</loc></url>'
            for p in sorted(parks, key=lambda x: x['name']))
        total += write(os.path.join(out_dir, 'sitemap.xml'),
                       '<?xml version="1.0" encoding="UTF-8"?>\n'
                       '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                       f'<url><loc>{e(base_url)}/</loc></url>{urls}</urlset>\n')

    print(f'\n{len(parks) + 1} pages, {total / 1024:.0f} KB total, '
          f'{total / (len(parks) + 1) / 1024:.1f} KB average.')
    if not base_url:
        print('No --base-url given: canonical tags and sitemap.xml were '
              'skipped. webapp_v2 serves a sitemap off the live host instead.')
    return parks


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', default=OUT_DIR)
    ap.add_argument('--base-url', default=os.environ.get('FOULCAST_SITE_URL', ''),
                    help='absolute site root, e.g. https://foulcast.example')
    ap.add_argument('--sims', type=int, default=SIMS)
    ap.add_argument('--refresh', action='store_true',
                    help='re-run the model even if the cache is current')
    ap.add_argument('--no-model', action='store_true',
                    help='render copy from the cache without simulating')
    args = ap.parse_args()

    build(args.out, args.base_url.rstrip('/'), args.sims,
          args.refresh, args.no_model)


if __name__ == '__main__':
    main()
