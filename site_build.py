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

1. **No printed section numbers, except inside a quotation from the club.**
   Every seating map this project holds has now been read against the zone
   tables in `stadium.py` (`MAP_FINDINGS.md`, Steps 11-16): thirty maps
   covering thirty of the 31 parks, and twenty-seven of them disagree with
   their table. Zones are named in words. The numbers that are wrong are this
   model's; a club's own sentence about its own sections is quoted as it
   stands (Step 26), inside `<q class="quote">` or `<blockquote class="quote">`
   and nowhere else, and the tests strip exactly those before looking for a
   number. A quotation may name a foul line, too, at a park where this page
   may not: it names the club's sections, not this model's areas.
2. **Netting leads; the model follows.** The club's netting statement is above
   the distribution table on every page, because netting is sourced and the
   model is an estimate. Where nothing usable is published the page says so in
   the same position, at the same size.
3. **The word "safe" never appears**, even inside a quotation. Netting is not
   safety — the clubs' own pages say fans in netted sections remain exposed to
   balls leaving the field. No seat on the site is described as protected.
4. **No accuracy claims.** The model has been compared with observed foul
   landings once, coarsely, in four bands (`VALIDATION.md`, `CALIBRATION.md`):
   it gets the general shape roughly right, puts slightly too few fouls far
   down the lines, and does not reliably tell parks apart. Every park page
   says exactly that in one line, and nothing on the site says more.
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
Every number on these pages comes out of estimated geometry, tested once and
coarsely, and a drawn length puts it on a scale and says it was measured to
that scale. Label left, figure right-aligned, hairline between,
and nothing else. `rows()` is the only thing that lays a figure out.

**The page is built around what has been tested, and since Step 30 that is
four bands, not seating areas.** FiveThirtyEight's count of real fouls places
each ball in one of four bands by distance along the foul line — behind the
plate, near the dugout, dugout to foul pole, past the pole — and that is the
only resolution at which this model has been compared with anything. So the
drawing is cut into those bands and the table above the fold gives the
model's share in each beside the observed share, to the whole per cent the
test read them at. The seating areas and decks the page used to lead with are
under Details, in a panel whose heading says no real data has tested them.
`site_diagram.py` puts the plan-view schematic above the table. The lengths in
it — how deep the bowl sits, how far the stands stand off the plate — are the
two *sourced* measurements this site already prints, so drawing them as
distances claims nothing the page does not already claim in words. The
model's shares are carried by shade, in four steps against the busiest band at
the same park, and never by a length. That file's docstring is where the rest
of the argument lives.

**There is no red.** Red used to belong to one state: a seating area this site
said was "not behind netting". That state was this project's inference from
the edge of a club's sentence, attached to seat labels the parks' own maps say
are in the wrong place, and Step 26 took it down with the rest of the
per-area netting marks. One accent teal does the section headings, links and
structural marks; everything else is ink on white.

**The site is built around the drawings, and the words are rationed.** Three
passes trimmed and rearranged the prose and the site still read as a methods
document, because a page organised around its own caveats is a document
whatever its length. So the pages are now three kinds, and two of them carry a
word budget that `tests/test_site.py` enforces:

* **The home page is a gallery.** One headline, two sentences, and a grid of
  all 31 ballparks — each tile the park's own schematic, small, with its name
  and its team, the whole tile a link. At most 40 words of prose outside the
  tiles, and nothing else on the page.
* **A park page is the drawing.** The park's name and team, then the schematic
  large, cropped to that park and directly under its name, then one sentence
  quoting the club on where its netting runs, with a link to the club's page,
  then the distribution table — four bands, the model's share in each, and
  FiveThirtyEight's observed share beside it, with one footer line saying what
  that sample is — then one line saying what the test found, with the link to
  the full results on the explanatory page, and the home page's own footer
  under it so the page ends rather than stops. At most 60 words visible
  without opening anything, not counting the table, the drawing's own labels
  and the club's own words — the budget is on this site's prose, and a
  quotation is the source, not the prose. Everything that is about *this* park
  and not on that list — the club's statement at length and where it was read,
  how the figures were produced, what share was dropped, the seating areas
  and decks with each one's figure, share and speed off the bat, the line
  saying the park's own map puts those areas elsewhere, the sourced figures,
  the seating-map read — is behind one closed "Details" disclosure at the foot
  of the page. Nothing honest is removed; it is one click down.
* **`/about/` is where the site explains itself.** Every explanation that used
  to be on the home page or repeated on all 31 park pages — what is sourced
  and what is not, what each club says and which parks are in each group, why
  most pages will not name a foul line, why no section number is printed
  outside a quotation, how the drawing is to be read, the methodology, the
  model's limits, the one test the model has had and what it found — is on
  that page once, in full, and linked from the test line of every park page.

**Whitespace goes to the drawing, and nowhere else.** The schematic gets the
width of the column and air on all four sides; the table under it is tight,
the caveat is one line, and the Details disclosure is a hairline and a word.
One column at every width, because the page is a picture with a table under
it and there is nothing to set beside either. The home grid reflows by tile.

**Prose never runs past 72 characters a line, at any width.** The cap is in
`ch` and not in `rem`, because these pages set text at several sizes and one
rem cap gives the small type a hundred-character line.
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

from foulball.league_lineup import league_lineups
from foulball.matchup_engine import predict_game_fouls
from foulball.stadium import STADIUMS, PARK_PARAMS
from foulball.netting import PARK_NETTING, PDL_RULE
from foulball.seat_map import check_side_anchors
from site_diagram import (
    park_diagram, park_tile, shade_of, band_edges, drawn_bands, BANDS,
    SHADE_WORDS, CSS as DIAGRAM_CSS,
)
from site_data import (
    PARK_SOURCES, ZONE_WORDS, PAIR_ZONE_WORDS, AREA_WORDS, CLUB_NETTING,
    CLUB_NETTING_READ, COVER_WORDS, COVER_APPLIED, MODEL_LIMITS, RESEARCH_DATE,
    SIDE_STATE_WORDS, MAP_READS, MAP_READ_DATE, LATER_READ_DATE, NO_MAP_READ,
    FOUL_AREA_CAVEAT, BACKSTOP_CAVEAT, OVERHANG_CAVEAT,
    CLEM_TABLE, CLEM_BASE, CLEM_OVERHANG_SNAPSHOT, SEAMHEADS_BASE,
    VALIDATION_SHARES,
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

# There is no build date. The pages used to print "Model figures rebuilt" and
# the day they were rendered, which was not the day the figures were made:
# a render reuses the cached run, so the audit's rebuild on 2026-10-20 dated
# figures simulated on 2026-09-08, and the committed-site test had to ignore
# the line to pass at all. The date on a page is now the `run_on` the cache
# entry carries, so rendering twice produces the same bytes.

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
    the only thing varying between pages is the park.

    Eighteen real batters chosen to stand for the league — nine from each side
    of the plate, spanning the league's range of fouls per plate appearance,
    with computed 2025-26 exit velocity, launch angle and pull share. They
    replaced the hand-typed 2024 Yankees and Red Sox in Step 27; the rule that
    picked them is `build_league_lineup.py`, and the fingerprint below covers
    their values, so a regenerated lineup re-simulates every park.
    """
    return league_lineups()


def run_park(park_key: str, sims: int, fingerprint: str | None = None) -> dict:
    """One full game at one park: both lineups, summed.

    A single `predict_game_fouls` call covers one team's plate appearances and
    is half a game — the units error `NOTES.md` records at the top.

    Every foul is also put in one of the four bands FiveThirtyEight's count is
    folded into, by where it came down along the foul line, with the test's
    own functions and dugout ends (`validate_538`), so a page's band shares
    are the figures the test scored and not a second reading of them. They
    count every foul, seated or not, because the observed zones do.
    """
    # Imported here, not at the top: `validate_538` imports this module for
    # the lineup and seed, and it is the record of the test, so it is reused
    # rather than copied.
    from validate_538 import (along_line_at_contact, zone_of, ZONE_TO_GROUP,
                              GROUPS, DUGOUT_SETTINGS)
    near, far = DUGOUT_SETTINGS[0]

    np.random.seed(SEED)
    stadium = STADIUMS[park_key]()
    pole = {'1B': float(stadium.rf_distance), '3B': float(stadium.lf_distance)}

    fouls: dict[str, float] = {}
    ev_weight: dict[str, float] = {}
    bands = {g: 0.0 for g in GROUPS}
    total = 0.0
    matched = 0.0

    for lineup in standard_lineups():
        pred = predict_game_fouls(lineup, 'Standard RHP', STANDARD_RHP_MIX,
                                  stadium, simulations_per_batter=sims)
        for e in pred.all_events:
            total += e.weight
            zone = zone_of(along_line_at_contact(e), e.landing_side,
                           pole[e.landing_side], near, far)
            bands[ZONE_TO_GROUP[zone]] += e.weight
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
        # The day this simulation ran, which is the date the page prints. The
        # page used to print the day it was *rendered*, and a render reuses
        # this cache: the figures dated 2026-10-20 by the audit had been
        # simulated on 2026-09-08.
        'run_on': date.today().isoformat(),
        'zone_fouls': fouls,
        'zone_ev': {sid: (ev_weight.get(sid, 0.0) / w if w > 0 else 0.0)
                    for sid, w in fouls.items()},
        'into_seats': matched,
        'total_fouls': total,
        'unmatched': total - matched,
        'bands': bands,
    }


def load_stats(refresh: bool, sims: int, cache_path: str = CACHE) -> dict:
    """Model stats for every park, from cache where possible.

    An entry is reused only when its simulation count and its model
    fingerprint both match the current ones, so a change anywhere in
    `MODEL_SOURCES` re-simulates every park without anyone having to remember
    to pass `--refresh`. An entry with no `run_on` is re-simulated too: the
    page prints that date, and an entry that cannot say when it ran cannot be
    dated honestly. So is one with no `bands`, which the page's main table is
    built from and which entries made before Step 30 do not carry.
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
                and entry.get('model') == fingerprint
                and entry.get('run_on') and entry.get('bands')
                and not refresh):
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

_SIDES: dict[str, int] = {}


def side_counts() -> dict[str, int]:
    """How many parks may name a foul line, and how many may not.

    Computed rather than written out, because this
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
            'covered': a['covered'] and b['covered'],
        })

    singles.sort(key=lambda z: -z['fouls'])
    return singles


_OBSERVED: dict = {}


def observed_bands() -> dict:
    """FiveThirtyEight's foul balls in the four bands, pooled over the sample.

    All 906, from all ten parks and the zone FiveThirtyEight used for each
    ball, read with the test's own loader. Pooled because a page sets the
    model's shares for its park beside the only real distribution there is:
    eight of the 31 parks are in the sample, each for one day, and a single
    day's hundred balls at one park is too few to set beside anything. The
    eight compared parks are what `VALIDATION.md` scores; the two others
    (Oakland Coliseum, and Arlington's old park) are in the sample, so they
    are in its shares.
    """
    if not _OBSERVED:
        from validate_538 import load_observed, GROUPS
        games = load_observed()
        counts = {g: sum(m['all'][g] for m in games.values()) for g in GROUPS}
        n = sum(counts.values())
        _OBSERVED.update(n=int(n), parks=len(games),
                         share={g: counts[g] / n for g in GROUPS})
    return _OBSERVED


def build_park(park_key: str, stats: dict) -> dict:
    """Everything one page needs, resolved from the model and the sources."""
    stadium = STADIUMS[park_key]()
    src = PARK_SOURCES[park_key]
    params = PARK_PARAMS[park_key]
    st = stats[park_key]
    if not st.get('run_on'):
        raise SystemExit(f'{park_key}: the cached run does not say when it ran; '
                         f'rebuild without --no-model')
    if not st.get('bands'):
        raise SystemExit(f'{park_key}: the cached run predates the four bands; '
                         f'rebuild without --no-model')

    by_id = {s.section_id: s for s in stadium.sections}
    missing = set(by_id) - set(ZONE_WORDS)
    if missing:
        raise SystemExit(f'{park_key}: no plain-words phrase for {sorted(missing)}')

    into = st['into_seats']
    zones = []
    for sid, fouls in st['zone_fouls'].items():
        sec = by_id[sid]
        heading, level, area = zone_words(sec)
        zones.append({
            'id': sid,
            'heading': heading,
            'level': level,
            'area': area,
            'fouls': fouls,
            'share': (fouls / into * 100) if into else 0.0,
            'ev': st['zone_ev'].get(sid, 0.0),
            'covered': sec.fully_covered,
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

    # The four bands the model has been tested at, which are the page's main
    # table and its drawing. A band's share is of every foul the model
    # produces here, seated or not, as the observed share is; its shade is
    # where that share falls against the busiest band at this park; and it is
    # drawn only if some drawn seat lies in it.
    from validate_538 import DUGOUT_SETTINGS
    near, far = DUGOUT_SETTINGS[0]
    drawn = drawn_bands(stadium, band_edges(stadium, near, far))
    seen = sum(st['bands'].values())
    observed = observed_bands()['share']
    bands = [{'key': k, 'name': name,
              'share': st['bands'][k] / seen if seen else 0.0,
              'observed': observed[k], 'drawn': k in drawn}
             for k, name in BANDS]
    top = max(b['share'] for b in bands)
    for b in bands:
        b['shade'] = shade_of(b['share'], top)

    return {
        'key': park_key,
        'slug': src['slug'],
        'name': stadium.name,
        # The finished section table, for the schematic above the distribution
        # table. It is the same object the zone figures were simulated
        # against, so the drawing cannot fall out of step with them.
        'stadium': stadium,
        'city': stadium.city,
        'team': stadium.team,
        'src': src,
        'params': params,
        # What the club says about its netting, in its own words. Nothing on
        # the page is joined to this model's seating areas any more; the join
        # in `foulball/netting.py` is still the model's, and the page is not.
        'club': CLUB_NETTING[park_key],
        'netting': PARK_NETTING[park_key],
        'sides': sides,
        'map_read': MAP_READS.get(park_key),
        'bands': bands,
        'dugout': (near, far),
        'zones': zones,
        'into_seats': into,
        'total_fouls': st['total_fouls'],
        'unmatched_pct': (st['unmatched'] / st['total_fouls'] * 100)
                         if st['total_fouls'] else 0.0,
        'sims': st['sims'],
        'run_on': st['run_on'],
    }


# ============================================================
# Formatting helpers
# ============================================================

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


def band_label(b: dict) -> str:
    """One band's name, as the table above the fold prints it.

    Beside a swatch in the shade the drawing gives the same band, so a reader
    can go from a row to its place on the drawing. The band past the pole has
    no seat drawn in it at any park, so it has no place on the drawing and
    carries no swatch.
    """
    # The empty swatch is a placeholder that keeps the four names aligned.
    swatch = (f'<i class="z{b["shade"]}"></i>' if b['drawn']
              else '<i class="nil"></i>')
    return f'<span class="band">{swatch}{e(b["name"])}</span>'


def e(s) -> str:
    return html.escape(str(s), quote=True)


# ============================================================
# The page shell
# ============================================================

CSS = r"""
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:#fff;color:#16181d;word-wrap:break-word;
 font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,
 "Helvetica Neue",sans-serif}
header,main,footer{max-width:46rem;margin:0 auto;padding:0 1rem}
a{color:#0b6a74;text-decoration:underline;text-underline-offset:.14em}
a:hover{color:#084950}
p{margin:.55rem 0}
.wm{font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;
 font-weight:800;margin:1.1rem 0 0;color:#16181d}
.wm a{text-decoration:none;color:inherit}
.wm a:hover{color:#0b6a74}
h1{font-size:1.8rem;line-height:1.08;letter-spacing:-.025em;font-weight:800;
 margin:.55rem 0 .15rem}
.club{font-size:.78rem;letter-spacing:.07em;text-transform:uppercase;
 color:#5b6270;margin:0}
.club b{color:#0b6a74;font-weight:700}
.hero{text-align:center;padding-top:1.6rem}
.hero h1{font-size:2rem;margin:.7rem auto .45rem;max-width:22ch}
.hero .lede{color:#4a505c;font-size:1rem;line-height:1.5;max-width:46ch;
 margin:0 auto 1.7rem}
.hero .lede+.tested{color:#5b6270;font-size:.86rem;line-height:1.45;
 max-width:52ch;margin:-1.2rem auto 1.7rem}
.grid{list-style:none;padding:0;margin:0 0 2rem;display:grid;gap:.7rem;
 grid-template-columns:repeat(auto-fill,minmax(9.5rem,1fr))}
.grid a{display:block;height:100%;text-decoration:none;color:inherit;
 background:#f3f5f7;border:1px solid transparent;border-radius:12px;
 padding:.8rem .8rem .75rem;transition:border-color .12s,transform .12s}
.grid a:hover{border-color:#0b6a74;transform:translateY(-2px)}
.grid .dia{margin:0 0 .55rem}
.tn{display:block;font-weight:700;font-size:.95rem;line-height:1.2;
 letter-spacing:-.01em}
.tt{display:block;color:#5b6270;font-size:.74rem;margin-top:.18rem}
.park main{padding-top:.2rem}
/* The drawing is the answer, so it sits under the park's name with
   nothing between them. It used to carry the whole fleet's frame and
   therefore the widest park's blank margin at the top of it; cropped
   to its own park, the top of the drawing is the top of the drawing. */
.park .dia{margin:.45rem 0 1.5rem}
.netline{font-size:1.1rem;line-height:1.38;font-weight:600;
 letter-spacing:-.012em;margin:0 0 1.15rem;max-width:58ch}
.netline q{font-weight:400}
.netline .src{font-size:.8rem;font-weight:600;white-space:nowrap;
 letter-spacing:0;margin-left:.2rem}
.mislabel{font-size:.84rem;line-height:1.45;color:#4a505c;margin:.9rem 0 0;
 padding-left:.6rem;border-left:3px solid #16181d}
.mislabel b{color:#16181d}
.band{display:inline-flex;align-items:center;gap:.4rem;font-weight:600}
.band i{display:block;width:.9rem;height:.62rem;border-radius:2px;
 border:1px solid rgba(22,24,29,.14)}
.band i.nil{visibility:hidden}
tfoot td{border-bottom:0;padding-top:.5rem;font-size:.77rem;line-height:1.4;
 color:#5b6270}
tfoot tr+tr td{padding-top:.15rem}
th.obs{white-space:normal;width:8.5rem}
th.obs span{display:block;font-weight:600;letter-spacing:.04em}
blockquote.quote{margin:.6rem 0;padding:.05rem 0 .05rem .75rem;
 border-left:2px solid #b9bfc8;font-size:.86rem;line-height:1.5}
blockquote.quote p{margin:.35rem 0;max-width:72ch}
table{width:100%;border-collapse:collapse;margin:0;font-size:.9rem}
caption{text-align:left;font-size:.68rem;font-weight:700;letter-spacing:.1em;
 text-transform:uppercase;color:#0b6a74;padding:0 0 .5rem}
th,td{text-align:left;vertical-align:top;padding:.42rem .1rem;
 border-bottom:1px solid #e4e7eb;line-height:1.4}
thead th{font-size:.64rem;letter-spacing:.08em;text-transform:uppercase;
 color:#5b6270;font-weight:700;border-bottom:1px solid #b9bfc8;
 padding-bottom:.25rem}
tbody tr:last-child td{border-bottom:1px solid #b9bfc8}
td.k{font-weight:600}
.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;
 width:1%;padding-left:.7rem}
.sub2{display:block;color:#5b6270;font-size:.77rem;line-height:1.35;
 font-weight:400;margin-top:.12rem}
.sub2+.sub2{margin-top:.35rem}
.area{color:#5b6270;font-weight:400}
.caveat{font-size:.84rem;line-height:1.45;color:#4a505c;margin:.9rem 0 2rem}
.caveat b{color:#16181d}
.caveat a{white-space:nowrap;font-weight:600}
.more{border-top:1px solid #dcdfe4;margin:0 0 1rem}
.more>summary{cursor:pointer;list-style:none;display:flex;
 justify-content:space-between;align-items:center;padding:.85rem 0;
 font-size:.72rem;font-weight:700;letter-spacing:.12em;
 text-transform:uppercase;color:#5b6270}
.more>summary::-webkit-details-marker{display:none}
.more>summary::after{content:"+";font-size:1rem;line-height:1}
.more[open]>summary::after{content:"\2212"}
.more>summary:hover{color:#0b6a74}
.panel{border:1px solid #d5d9df;margin:0 0 1rem}
.panel>h2{margin:0;padding:.45rem .7rem;font-size:.72rem;font-weight:700;
 letter-spacing:.09em;text-transform:uppercase;color:#0b6a74;
 border-bottom:1px solid #d5d9df}
.pb{padding:.7rem .7rem .85rem}
.pb>:first-child{margin-top:0}
.pb>:last-child{margin-bottom:0}
.pb p,.warn,.ok,.gap,.note,.about p,.about li{max-width:72ch}
.lede{font-size:.98rem}
h3{font-size:.94rem;font-weight:700;letter-spacing:-.01em;margin:1.2rem 0 .3rem}
.note{font-size:.83rem;line-height:1.45;color:#4a505c;
 border-left:2px solid #d5d9df;padding-left:.65rem;margin:.75rem 0}
.warn,.ok,.gap{border:1px solid #d5d9df;padding:.55rem .65rem;margin:.8rem 0;
 font-size:.88rem;line-height:1.45}
.warn{border-left:3px solid #7b828e}
.ok{border-left:3px solid #0b6a74}
.gap{border-left:3px solid #16181d;background:#f4f5f7}
.warn p,.ok p,.gap p{margin:.3rem 0}
.warn p:first-child,.ok p:first-child,.gap p:first-child{margin-top:0}
.warn p:last-child,.ok p:last-child,.gap p:last-child{margin-bottom:0}
.tag{display:inline-flex;align-items:baseline;gap:.34rem;white-space:nowrap;
 color:#4a505c}
.tag::before{content:"";flex:0 0 auto;width:.44rem;height:.44rem;
 border-radius:50%;background:#767d89;transform:translateY(-.06rem)}
.tag-net::before{background:#0b6a74}
.tag-unk::before{background:#c2c8d0;box-shadow:inset 0 0 0 1px #a8afba}
.tag-flag::before{background:#16181d}
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
.big{font-size:1rem;font-weight:700;font-variant-numeric:tabular-nums}
.credit{font-size:.78rem;line-height:1.45;color:#5b6270;margin:.2rem 0 0;
 max-width:72ch}
footer{border-top:1px solid #dcdfe4;margin-top:.5rem;padding-top:.9rem;
 padding-bottom:2.4rem;color:#5b6270;font-size:.8rem}
footer a{font-weight:700;text-decoration:none}
footer a:hover{text-decoration:underline}
.about h1{margin-bottom:.5rem}
.about h2{font-size:1.15rem;line-height:1.25;letter-spacing:-.015em;
 margin:2.2rem 0 .45rem;padding-top:1.3rem;border-top:1px solid #dcdfe4}
.about h2+p{margin-top:.3rem}
.about .lede{font-size:1.05rem;color:#4a505c}
@media (min-width:34rem){
 body{font-size:16px}
 header,main,footer{padding:0 1.25rem}
 .grid{grid-template-columns:repeat(auto-fill,minmax(11rem,1fr));gap:.85rem}
}
@media (min-width:64rem){
 .home header,.home main,.home footer{max-width:74rem;padding:0 2rem}
 .hero{padding-top:2.4rem}
 .hero h1{font-size:2.4rem}
 .grid{grid-template-columns:repeat(auto-fill,minmax(12.5rem,1fr));gap:1rem}
 .park header,.park main,.park footer,
 .about header,.about main,.about footer{max-width:50rem;padding:0 1.5rem}
 .park h1{font-size:2.15rem}
 .park .dia{margin:.6rem 0 1.8rem}
 .netline{font-size:1.18rem}
}
@media (prefers-color-scheme:dark){
 body{background:#101216;color:#e4e7ee}
 a{color:#4fb6c0}a:hover{color:#7fd0d8}
 .wm,.club b{color:#e4e7ee}
 .wm a:hover{color:#4fb6c0}
 .club,.sub,.sub2,.area,.note,footer,thead th,tfoot td,.lhead,.tt,.caveat,.credit,
 .hero .lede,.hero .tested,.about .lede{color:#98a0b0}
 .club b,.caveat b{color:#e4e7ee}
 .grid a{background:#171a20}
 .grid a:hover{border-color:#4fb6c0}
 caption,.panel>h2{color:#4fb6c0}
 .more{border-top-color:#2b313b}
 .more>summary{color:#98a0b0}
 .more>summary:hover{color:#4fb6c0}
 .panel,.warn,.ok,.gap{border-color:#2b313b}
 .panel>h2{border-bottom-color:#2b313b}
 h3{color:#e4e7ee}
 th,td{border-bottom-color:#232830}
 thead th,tbody tr:last-child td{border-bottom-color:#3a414d}
 .note{border-left-color:#2b313b}
 .warn{border-left-color:#6d7482}
 .ok{border-left-color:#4fb6c0}
 .gap{border-left-color:#8891a0;background:#171a20}
 .tag{color:#98a0b0}
 .tag::before{background:#8891a0}
 .tag-net::before{background:#4fb6c0}
 .tag-unk::before{background:#3a414d;box-shadow:inset 0 0 0 1px #6d7482}
 .tag-flag::before{background:#e4e7ee}
 .mislabel{color:#98a0b0;border-left-color:#e4e7ee}
 .mislabel b{color:#e4e7ee}
 .band i{border-color:rgba(228,231,238,.14)}
 blockquote.quote{border-left-color:#3a414d}
 ul.parklist li{border-bottom-color:#232830}
 .lhead{border-bottom-color:#3a414d}
 footer,.about h2{border-top-color:#2b313b}
}
"""

# Whitespace is not free on a phone, and this is served static.
def _min(css: str) -> str:
    return re.sub(r'\s*\n\s*', '', css).strip()


# One stylesheet for every page. The schematic's styling used to be served
# only on the 31 pages that carried a drawing; the home page now carries all
# 31 as tiles, and the 1.7 KB it costs the one page without a drawing is not
# worth a second stylesheet.
CSS_MIN = _min(CSS) + _min(DIAGRAM_CSS)


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


def panel(anchor: str, heading: str, body: str) -> str:
    """A hairline box with its heading in the one accent colour this site has.

    Every block inside a park page's Details disclosure is one of these, so
    the receipts read as a stack of equal-weight panels. The anchor stays on
    the `h2`, because `tests/test_site.py` reads the section order off those
    ids.
    """
    return (f'<section class="panel"><h2 id="{anchor}">{e(heading)}</h2>'
            f'<div class="pb">\n{body}\n</div></section>')


def rows(pairs, head=None, caption: str | None = None,
         anchor: str | None = None) -> str:
    """A label-left, figure-right table with a hairline between rows.

    The only presentation the figures on this site can carry. A bar, a filled
    share or anything else with a drawn length would put the numbers on a
    scale and imply they were measured to it; they come out of estimated
    geometry tested once, in four broad bands, and a plain right-aligned
    column claims nothing.

    `caption` is the table's own heading, inside the table, so that it is a
    label of the table rather than a line of prose above it.
    """
    cap = ''
    if caption:
        cap = (f'<caption id="{anchor}">{caption}</caption>' if anchor
               else f'<caption>{caption}</caption>')
    thead = (f'<thead><tr><th>{head[0]}</th><th class="n">{head[1]}</th></tr>'
             f'</thead>' if head else '')
    body = ''.join(f'<tr><td class="k">{k}</td><td class="n">{v}</td></tr>'
                   for k, v in pairs)
    return f'<table>{cap}{thead}<tbody>{body}</tbody></table>'


# ============================================================
# The park page
# ============================================================
#
# The top of a park page answers the question it was opened with and nothing
# else: the ballpark's name, the drawing, the club's own sentence about where
# the net is, and the distribution. Everything that qualifies those four
# things — the club's statement at length, how the figures were produced and
# the figures themselves, what the model cannot do — is below them or behind
# a disclosure. It is all still here; none of it is first.
#
# Step 26 took one thing off the page rather than moving it: the reading of
# the figures "two ways", once for a reader who wants a ball and once for a
# reader who does not want to be hit. Both readings were built on which of
# this model's areas the club's netting covers, which is the join the parks'
# own maps say lands on the wrong seats.


def club_quote(text: str) -> str:
    """One quotation from a club, inline.

    The element is the boundary the section-number rule is drawn at: inside
    `<q class="quote">` a number is the club's, and `tests/test_site.py` holds
    everything inside one to the club's text in `CLUB_NETTING` before it lets
    a number through. Nothing of this site's own goes inside it.
    """
    return f'<q class="quote">{e(text)}</q>'


def netting_line(p: dict) -> str:
    """One sentence, above the fold: what the club says about its netting.

    The club's own words wherever it has published any, quoted, with this
    site's words kept to the few that introduce them, and a link to the page
    they came from. Until Step 26 this sentence was composed out of a join of
    the club's section numbers onto this model's seat labels, and said things
    like "runs out along the third-base line past the dugout and over part of
    the seats beyond" — which were statements about this model's labels, and
    the parks' own maps say those are in the wrong place. A quotation cannot
    be wrong in that way, and a reader with a ticket can find their own
    section in it, which this site was never in a position to do for them.
    """
    club = p['club']
    said = e(club['line']).format(*(club_quote(q) for q in club['quotes']))
    link = club.get('link', "The club's page")
    return (f'{said} <a class="src" href="{e(club["page"])}" '
            f'rel="nofollow">{e(link)} &rarr;</a>')


def netting_source_section(p: dict) -> str:
    """The club's statement at length, where it was read, and what it is not.

    The receipts, not the answer. `netting_line` quotes the sentence that
    says where the net runs; this quotes the club's statement more fully —
    heights where the club gives them, the club's own warning that fans
    behind the net are still exposed — and says when and where it was read.

    It also says, once, what this page no longer does: mark which of its own
    seating areas the netting stands in front of. That was the join this
    site used to print area by area, and the reason it stopped is specific to
    each park's seating-map read, so it is stated here rather than only on
    the explanatory page.

    First inside the Details disclosure, so that the sourced thing stays
    ahead of the estimated one even among the receipts.
    """
    club, name = p['club'], p['name']
    link = club.get('link', "The club's page")
    out = []
    if club['full']:
        paras = ''.join(f'<p>{e(x)}</p>' for x in club['full'])
        out.append(f'<blockquote class="quote">{paras}</blockquote>')
    read = (f'<p class="sub">Read on <a href="{e(club["page"])}" '
            f'rel="nofollow">{e(link[0].lower() + link[1:])}</a> on '
            f'{e(CLUB_NETTING_READ)}.')
    if club.get('same_as_first_read', True):
        read += (f' It said the same when this site first read it, on '
                 f'{e(RESEARCH_DATE)}.')
    out.append(read + '</p>')
    if club.get('note'):
        out.append(f'<p>{e(club["note"])}</p>')
    if p['netting'].gap_kind == 'no_source_at_all':
        out.append(f'<p class="note">The only rule that reaches this park: '
                   f'{e(PDL_RULE)}.</p>')

    # Where the club does give sections, why this page will not say which of
    # its own areas they are. The reason is this park's own map read, so it
    # is said here and not only on the explanatory page.
    if club['kind'] in ('states', 'conflicts'):
        mr = p['map_read']
        if mr and mr['outcome'] == 'disagrees':
            why = ('this ballpark\'s own seating map, read under the last '
                   'heading below, puts this model\'s areas somewhere other '
                   'than where their labels say')
        elif mr:
            why = ('although this ballpark\'s own seating map agrees with '
                   'this model\'s labels, at twenty-seven of the thirty parks '
                   'whose map has been read it does not, and no page does it')
        else:
            why = ('nobody has read a seating map for this ballpark against '
                   'this model\'s labels, so nothing says they are right')
        out.append(f'<p>This page does not say which of its own seating areas '
                   f'that netting stands in front of. Saying so meant reading '
                   f'the club\'s statement onto this model\'s seat labels, and '
                   f'{why}. Find your section in the club\'s own words '
                   f'instead.</p>')
    out.append(f'<p class="note">{NETTING_CLUB_CAVEAT}</p>')
    return panel('netting-source',
                 f'What the club says about netting at {name}', '\n'.join(out))


# The line over the area table at a park whose own seating map disagrees with
# this model's labels. It is the same at all of them, because what it has to
# say is the same — some area names here are not the seats they name — and the
# map read in the last panel says exactly how, park by park. Until Step 30 it
# stood under the table above the fold, because that table named the areas and
# a reader who took it and left took the wrong seats with them (`LIMITATIONS.md`
# P1). The table above the fold now names four bands by distance along the
# foul line and no seats at all, so the line went down with the area names, and
# stands directly over them.
MISLABEL_LINE = ('<b>Some areas may be mislabelled.</b> This ballpark\'s own '
                 'seating map puts some of them somewhere else; the last panel '
                 'below says how.')

# The one line above the fold that says what the model's figures are worth.
# Step 28 compared the model with FiveThirtyEight's count, and the sentence is
# that comparison's result in the fewest words that are still all of it; the
# figures, and the fact that the back-foul rate was then fitted to the same
# count, are on the explanatory page it links to.
TESTED_LINE = ('<b>Tested once against FiveThirtyEight\'s data,</b> it gets '
               'the general shape roughly right, puts slightly too few '
               'fouls far down the lines, and does not reliably tell parks '
               'apart.')


def band_table(p: dict) -> str:
    """The four bands, the model's share in each, and the observed share.

    Three columns, which `rows()` does not lay out: the band, this model's
    share of the park's foul balls in it, and FiveThirtyEight's share in it
    across its whole 2019 sample. Whole per cent, because that is what the
    test read the model at and what six seeds agree to within a point or so
    (`VALIDATION.md`); a tenth would claim more. The column's own heading
    says it is pooled and not this park's, because "observed" with no more
    said would read as observed here, and the footer says what the sample is.

    The footer's second line says why the two columns agree as closely as
    they do: the back-foul rate, which decides the first band, was calibrated
    to these same fouls in Step 29, so agreement here is partly by
    construction. The fair measure is the held-out test, where each park was
    predicted at a rate fitted without it, and the line links to it.
    """
    obs = observed_bands()
    head = ('<thead><tr><th>Band</th><th class="n">This model</th>'
            f'<th class="n obs">FiveThirtyEight <span>{obs["parks"]} parks '
            f'pooled, not this park</span></th></tr></thead>')
    body = ''.join(
        f'<tr><td class="k">{band_label(b)}</td>'
        f'<td class="n">{share_str(b["share"] * 100)}</td>'
        f'<td class="n">{share_str(b["observed"] * 100)}</td></tr>'
        for b in p['bands'])
    foot = (f'<tfoot><tr><td colspan="3">FiveThirtyEight\'s column is '
            f'{obs["n"]} foul balls from {obs["parks"]} parks in 2019, one '
            f'unusually foul-heavy day at each, pooled.</td></tr>'
            f'<tr><td colspan="3">The model\'s back-foul rate was calibrated '
            f'to this data, so close agreement here is expected; the '
            f'<a href="../about/#validation">held-out test</a> on the About '
            f'page is the fair measure.</td></tr></tfoot>')
    return (f'<table><caption id="zones">Where foul balls come down</caption>'
            f'{head}<tbody>{body}</tbody>{foot}</table>')


def answer_section(p: dict) -> str:
    """The whole of the visible page: drawing, one sentence, table, one line.

    Nothing here explains itself first. The drawing is the answer to where
    foul balls land and so it is the first thing on screen; the sentence under
    it is the club's own answer to where the net is; the table is the drawing
    in figures, beside the one real distribution there is. Under the table,
    the one line that says what those figures are worth, carrying the link to
    the page where the test is reported in full. Everything else is in the
    Details disclosure below.

    Since Step 30 the table is the four bands the model was tested at, not the
    seating areas. Nothing finer than those bands has been compared with a
    real foul ball, so the areas and decks went into Details, under a heading
    that says so, and the figures came up: a band's share to the whole per
    cent is what the test checked, which a seating area's figure to a tenth
    of a ball never was.

    Label left, figures right, a hairline between. No bar and no filled share:
    a drawn length would put the figures on a scale and claim a precision
    none of it has.
    """
    tested = (f'<p class="caveat">{TESTED_LINE} '
              f'<a href="../about/#validation">Results &rarr;</a></p>')

    return f'''{park_diagram(p)}
<p class="netline" id="netting">{netting_line(p)}</p>
{band_table(p)}
{tested}'''


def area_figures(p: dict) -> str:
    """The seating areas and decks, and the only place on the site that
    carries them.

    Fouls a game, to a tenth, then the area's share of the fouls that reach
    seats and how fast the ball left the bat, with the deck the area sits on
    under its name. They are the same questions asked of every area, and a
    table is how you compare eleven answers to one question. Busiest first.

    The share is of the fouls that reach *seats*, not of the park's fouls —
    the model drops some of those before this table starts, and the panel
    above says how many.
    """
    head = ('<thead><tr><th>Seating area</th><th class="n">A game</th>'
            '<th class="n">Share</th><th class="n">Off the bat</th></tr>'
            '</thead>')
    def speed(z):
        # An area the model barely reaches has an exit speed averaged over
        # almost nothing, and printing it would dress a rounding error as a
        # measurement.
        return f'{z["ev"]:.0f} mph' if z['fouls'] >= 0.05 else '&mdash;'

    body = ''.join(
        f'<tr><td class="k">{zone_label(z)}'
        f'<span class="sub2">{e(z["level"])}</span></td>'
        f'<td class="n">{fouls_str(z["fouls"])}</td>'
        f'<td class="n">{share_str(z["share"]) if z["fouls"] > 0 else "&mdash;"}'
        f'</td>'
        f'<td class="n">{speed(z)}</td></tr>' for z in p['zones'])
    return (f'<table><caption>Each area in full</caption>{head}'
            f'<tbody>{body}</tbody></table>')


def model_section(p: dict) -> str:
    """How the figures above the fold were produced, and what they drop.

    The band shares first: what a band is, what is counted, and what the
    observed column beside them is. Then the share of fouls the model cannot
    put in a seat, which a reader would be misled without. The general method
    and the test are stated once, on the explanatory page.
    """
    near, far = (f'{x:.0f}' for x in p['dugout'])
    obs = observed_bands()
    inner = f'''<p>One full game, both lineups, the same 18 batters at every park on this site
&mdash; real hitters chosen to stand for the league, not any one club &mdash;
so the park is the only thing that changes. {p['sims']} simulations per batter,
fixed seed, run on {e(p['run_on'])}. Every foul the model produces is put in
one of four bands by how far along the foul line it comes down: behind the
plate up to {near} feet out, near the dugout from {near} to {far} feet, from
there to the foul pole, and past the pole. The dugout ends are an estimate from
the rule-book layout, and moving them by ten feet either way moves the shares
by several points. Every foul counts, whether or not it reaches a seat, because
FiveThirtyEight's zones count balls on the field too.</p>
<p>The FiveThirtyEight column is the {obs['n']} foul balls FiveThirtyEight
logged in 2019, one day at each of {obs['parks']} parks, each ball placed by eye
into one of seven zones, folded here into the same four bands and pooled over
all {obs['parks']} parks. Those days were chosen because they produced unusually
many fouls, and a foul-heavy day may not send balls where an ordinary one does.
It is set beside every park because it is the only public count there is, not
because it is this park's.</p>
<div class="warn"><p><strong>About {p['unmatched_pct']:.0f}% of
the fouls this model produces at {e(p['name'])} land where it has no seating
area to put them</strong> &mdash; deep down the lines near the poles, in the gap
in front of the first row, or under a covered deck. They are in the bands above,
which count every foul, and they are left out of the seating areas in the next
panel, which is why those figures are a shape rather than a census.</p></div>'''
    return panel('model', 'How these figures were produced', inner)


def areas_section(p: dict) -> str:
    """The seating areas and decks, labelled as untested.

    Everything this page used to lead with: which of this model's seating
    areas a foul comes down in, deck by deck. It is here rather than gone
    because it is what the model produces and a reader may want it, and it is
    here rather than above the fold because nothing has ever tested it —
    FiveThirtyEight's count has four bands, and no area, deck or section is
    finer than that. The heading says so before the table does.
    """
    out = []
    mr = p['map_read']
    if mr and mr['outcome'] == 'disagrees':
        out.append(f'<p class="mislabel" id="mislabel">{MISLABEL_LINE}</p>')
    out.append('<p><strong>No real data has tested any figure in this '
               'panel.</strong> The only public count of where foul balls '
               'land puts each ball in one of four broad bands, and that is '
               'the table above. Which seating area or deck a ball comes down '
               'in is finer than anything it records, so these are the '
               'model\'s figures and nothing more: a model estimate, not a '
               'count of anything observed, and not good to the tenth they '
               'are printed to.</p>')
    if not p['sides']['named']:
        out.append('''<p class="note">The two foul lines are one area each
rather than a first-base area and a third-base one, because nothing says which
line is which here. A figure on one of those rows is what reaches <em>one</em> of
the two lines, which keeps it comparable with the behind-plate rows beside it.
The model builds both lines identically, so the pair would differ only by
simulation noise in any case.</p>''')
    out.append(area_figures(p))
    out.append('''<p class="sub">Fouls a game in each area, which deck it sits on, what
share of the fouls that reach seats the model puts in it, and how fast those
balls left the bat &mdash; not how fast they arrive: a ball slows on the way, by
an amount this model computes and has never checked against a measured
landing.</p>''')
    return panel('areas', 'Seating areas and decks: untested by any real data',
                 '\n'.join(out))


def figures_section(p: dict) -> str:
    """The two published measurements, and the one that gates the upper deck.

    A figure left, the published number right, and everything that qualifies
    it — basis, conflicts, what the model does with it — under the label
    rather than beside the number, so nothing implies the number is more
    settled than its own footnote.

    Inside Details, because a reader who came for the netting and the
    distribution has not come for the provenance of a foul-territory estimate.
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
        if applied and params.upper_overhang >= 100:
            # The case that contradicted itself until Step 26: this sentence
            # said "receives nothing" beside a table giving the upper deck
            # nearly three fouls a game. `SeatSection.fully_covered` is what
            # makes it true, and `tests/test_site.py` holds the two together.
            used = (f'In the model: the upper deck\'s cover is treated as '
                    f'{cast}, which a high foul ball would hit, and it covers '
                    f'the whole deck &mdash; so no foul ball reaches the upper '
                    f'deck here, and the table above says none.')
        elif applied:
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

    out = [rows(pairs, head=('Figure', 'Published'))]

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

    return panel('figures', 'The sourced figures behind this park',
                 '\n'.join(out))


def labels_section(p: dict) -> str:
    """What is known about the seat labels the areas on this page come from.

    It is the check on the model output: the netting listing is a join onto
    these labels and the distribution is attached to them, and neither is
    better than they are. `MAP_FINDINGS.md` made it necessary — thirty maps
    read, twenty-seven of them disagreeing with the table.

    The three agreements are rendered differently and say so: an agreement
    that looks like a disagreement is as misleading as the reverse.
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
            'no real data has tested.</p>')
    else:
        out.append(f'<p>{NO_MAP_READ}</p>')

    return panel('labels', 'The seat labels these areas are built from',
                 '\n'.join(out))


# What the search description says about a park's netting, by what the club
# publishes.
NETTING_DESC = {
    'states': "the club's own netting statement",
    'conflicts': "the club's two netting statements, which disagree",
    'declines': 'the club\'s statement that it cannot say where its netting '
                'runs',
    'silent': 'a note that nothing published says where the netting runs',
}


def description(p: dict) -> str:
    """The search snippet for one park page, promising only what is on it.

    It used to promise "the park's sourced foul territory and backstop
    figures" at every park, including Las Vegas Ballpark, where neither is
    published anywhere and the page says so. The figures are named only where
    `PARK_SOURCES` has them.

    Until Step 30 it ended "Never checked against real fouls", which stopped
    being true when Step 28 compared the model with FiveThirtyEight's count.
    The page's table now sets the two side by side, and the snippet says so.
    """
    src = p['src']
    have = [w for w, v in (('foul territory', src['foul_area']),
                           ('backstop', src['backstop'])) if v]
    if len(have) == 2:
        figures = "the park's sourced foul territory and backstop figures"
    elif have:
        figures = f"the park's sourced {have[0]} figure"
    else:
        figures = ('a note that neither its foul territory nor its backstop '
                   'is published')
    return (f"Where foul balls land at {p['name']}, {p['city']}: a model "
            f"estimate in four bands beside FiveThirtyEight's count of real "
            f"fouls, {NETTING_DESC[p['club']['kind']]}, and {figures}.")


def park_page(p: dict, base_url: str) -> str:
    title = f"{p['name']} foul balls by zone | FoulCast"
    desc = description(p)
    if len(desc) > 300:
        desc = desc[:297] + '...'

    # The visible page is the drawing, one sentence, the table and a line or
    # two, and the last line carries the link to the explanatory page.
    # Everything that is about this park and not on that list is behind the
    # one Details disclosure under it, in the order that keeps the sourced
    # thing ahead of the estimated one: the club's statement first, then the
    # model's figures. Everything general is on /about/, where the link goes.
    #
    # The footer is the home page's footer, and it is here because a page that
    # stopped at the closed word "Details" stopped without ending. Its link is
    # back to the 31 rather than on to /about/: the caveat four lines above it
    # already goes to /about/, and a second copy of the same link is not an
    # ending either. The disclosure is shut. It is shut on every page and on
    # every visit — a reader who came for where the net is and how many balls
    # arrive has both above the fold, and `<details open>` would put the whole
    # of the provenance back in front of the answer it qualifies.
    body = f'''<body class="park">
<header>
<p class="wm"><a href="../">FoulCast</a></p>
<h1>{e(p['name'])}</h1>
<p class="club">{e(p['team'])}</p>
</header>
<main>
{answer_section(p)}
<details class="more"><summary>Details</summary>
{netting_source_section(p)}

{model_section(p)}

{areas_section(p)}

{figures_section(p)}

{labels_section(p)}
<p class="credit">Netting quoted from the club's own page as read on
{e(CLUB_NETTING_READ)}. Park dimensions from Andrew Clem's stadium statistics,
cross-checked against the Seamheads ballpark database. Model run on
{e(p['run_on'])}.</p>
</details>
</main>
<footer>
<p><a href="../">All 31 ballparks</a></p>
</footer>
</body>'''
    return page(title, desc, body, f'/{p["slug"]}/', base_url)


# ============================================================
# The home page
# ============================================================

def home_page(parks: list[dict], base_url: str) -> str:
    """A gallery of the 31 drawings, and nothing else.

    Each tile is the park's own schematic at the shared scale, so the grid is
    also a comparison of size: a park with more published foul ground draws
    larger. It is not a comparison of shade — each tile is banded against its
    own busiest area. Alphabetical, because any other order would be a
    ranking, and the figures cannot support one.

    One headline and two sentences above the grid. The second, since Step 30,
    says what the grid can and cannot show: the tiles differ mostly in size,
    which is the parks' published dimensions, and the test against real fouls
    found the model's shading does not reliably tell one park from another.
    `tests/test_site.py` holds the prose outside the tiles to forty words.
    """
    parks = sorted(parks, key=lambda p: p['name'])
    tiles = ''.join(
        f'<li><a href="{e(p["slug"])}/">{park_tile(p)}'
        f'<span class="tn">{e(p["name"])}</span>'
        f'<span class="tt">{e(p["team"])}</span></a></li>'
        for p in parks)

    title = 'Foul balls by ballpark — where they land, and what the netting covers | FoulCast'
    desc = ('Foul ball estimates for all 31 major and minor league ballparks: '
            'where they land by seating area, what each club publishes about '
            'its protective netting, and where that netting is unknown.')

    body = f'''<body class="home">
<header class="hero">
<p class="wm">FoulCast</p>
<h1>Where foul balls land, ballpark by ballpark</h1>
<p class="lede">Each club's netting, and a physics estimate of where foul
balls land.</p>
<p class="tested">Parks differ mostly by published dimensions; tested on real
fouls, the model doesn't reliably tell them apart.</p>
</header>
<main>
<ul class="grid">{tiles}</ul>
</main>
<footer>
<p><a href="about/">How this works</a></p>
</footer>
</body>'''
    return page(title, desc, body, '/', base_url)


# ============================================================
# The explanatory page
# ============================================================
#
# What each club publishes about its netting, in three groups. Grouped by what
# is published, not by how good the ballpark is, and read off
# `CLUB_NETTING[...]['kind']` rather than counted by hand.
#
# Until Step 26 these groups were the states of this model's netting *join*,
# and the largest of them was "the club publishes its netting and this model
# cannot use it". That is still true of the join, which is still in
# `foulball/netting.py`; it is no longer what a page shows, because every page
# now quotes the club directly. Wrigley Field and Comerica Park were filed
# under "nothing usable is published" by that join — the Cubs say where their
# netting runs in words, and the Tigers give both ends of it — and they are in
# the first group here, quoted.
NETTING_GROUPS = [
    (('states',),
     'The club says where its netting runs',
     'Each of these pages quotes the club\'s own statement of where its '
     'netting runs, section numbers and all, with a link to the page it is '
     'quoted from &mdash; find your own section in it. {named} of these parks '
     'have had which foul line is which established by something outside '
     'this model; the rest have not, and their pages say so rather than name '
     'a line.'),
    (('conflicts',),
     'The club\'s page says two things that cannot both be true',
     'Both are quoted, and this site does not choose between them. One of them '
     'is probably text nobody removed, and nothing on the page says which.'),
    (('declines', 'silent'),
     'Nothing the club publishes says where its netting runs',
     'One club says outright that its own map cannot show where its netting '
     'is; the others publish nothing that says where it runs, or show it only '
     'as a picture. Each page says which, in the place the club\'s sentence '
     'would be. That is a statement about what is published, not about the '
     'ballpark.'),
]

# The two side verdicts that are defects in this project carry the plain ink
# mark rather than a colour: a reversed pair of foul lines is something this
# model got wrong, not a fact about the ballpark.
SIDE_TAGS = {
    'confirmed': ('sides established', 'tag-net'),
    'untested': ('sides untested', 'tag-unk'),
    'flipped': ('sides reversed', 'tag-flag'),
    'inconsistent': ('sides contradicted', 'tag-flag'),
}


def run_dates(parks: list[dict]) -> str:
    """When the figures on these pages were simulated, as the cache records it.

    One date when every park was run on the same day, which is the normal
    case; a span when a partial re-run has left them on different days.
    """
    days = sorted({p['run_on'] for p in parks})
    return days[0] if len(days) == 1 else f'between {days[0]} and {days[-1]}'


def busiest_sentence(parks: list[dict]) -> str:
    """Where the busiest area sits, counted from the run rather than asserted.

    Until Step 27 the About page said the field-level seats behind the plate
    came out busiest at all 31 parks, as a fixed sentence. With the computed
    lineup the deck above them overtakes at a third of the parks, so the
    sentence is now computed from the same rows the park tables rank, and
    says so if a park's busiest area is ever not behind the plate at all.
    """
    tops = [p['zones'][0]['id'] for p in parks]
    home = [t for t in tops if t.startswith('HOME-')]
    if len(home) != len(tops):
        return (f'the seats behind home plate come out busiest at {len(home)} of '
                f'the {len(tops)} parks here.')
    field = sum(1 for t in tops if t == 'HOME-F')
    if field == len(tops):
        return (f'the seats at field level behind home plate come out busiest '
                f'at all {len(tops)} parks.')
    return (f'the seats behind home plate come out busiest at all {len(tops)} '
            f'parks &mdash; at field level at {field} of them, and on the deck '
            f'above at the other {len(tops) - field}.')


def about_page(parks: list[dict], base_url: str) -> str:
    """Every explanation the site has, once, in full.

    This is where the prose that used to open the home page and repeat on all
    31 park pages went when the pages were rebuilt around the drawings.
    Nothing was cut in the move: what is sourced and what is not, what each
    club says about its netting and which parks are in each group, why most
    pages will not name a foul line, why no section number is printed outside
    a quotation, how the drawing and its bands are to be read, the method, the
    model's limits, and the one test the model has had, in full. The line
    under every park page's table links here.
    """
    parks = sorted(parks, key=lambda p: p['name'])
    by_group = {kinds: [p for p in parks if p['club']['kind'] in kinds]
                for kinds, _, _ in NETTING_GROUPS}
    states, conflicts, unsaid = (by_group[k] for k, _, _ in NETTING_GROUPS)
    confirmed = [p for p in parks if p['sides']['named']]
    unnamed = side_counts()['unnamed']
    # The run these pages were rendered from, not the default: the tests build
    # at a low count and the page has to say what it was built at.
    sims = {p['sims'] for p in parks}
    assert len(sims) == 1, 'parks simulated at different counts'
    sims = sims.pop()

    def row(p):
        tag, cls = SIDE_TAGS[p['sides']['state']]
        return (f'<li><div class="row"><div class="rk">'
                f'<a href="../{e(p["slug"])}/">{e(p["name"])}</a> '
                f'<span class="tag {cls}">{tag}</span>'
                f'<span class="sub2">{e(p["city"])} &middot; '
                f'{e(p["team"])}</span></div>'
                f'<div class="rn">{p["into_seats"]:.0f}</div></div></li>')

    def group(kinds, heading, lead):
        members = by_group[kinds]
        listed = ''.join(row(p) for p in members)
        lead = lead.format(named=sum(1 for p in members if p['sides']['named']))
        return (f'<h3>{heading} <span class="sub">({len(members)})</span>'
                f'</h3><p>{lead}</p>'
                f'<div class="lhead"><span>Ballpark</span>'
                f'<span>Fouls a game reaching seats</span></div>'
                f'<ul class="parklist">{listed}</ul>')

    groups = '\n'.join(group(*g) for g in NETTING_GROUPS)

    def spelled(n: int) -> str:
        # Small counts read better as words in a sentence.
        words = ('no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
                 'eight', 'nine', 'ten')
        return words[n] if n < len(words) else str(n)

    limits = ''.join(
        f'<h3>{e(t)}</h3>'
        f'<p>{body.replace("{unnamed_sides}", str(unnamed))}</p>'
        for t, body in MODEL_LIMITS)

    near, far = parks[0]['dugout']
    shades = ' '.join(
        f'<span class="band"><i class="z{i}"></i>{SHADE_WORDS[i]}</span>'
        for i in reversed(range(len(SHADE_WORDS))))

    # The test's results, pooled over the eight parks it could compare. The
    # figures are `CALIBRATION.md`'s, which is where the run that made them is
    # recorded; they are not recomputed here because they come from a fit and
    # a held-out run that the site build does not repeat.
    obs = observed_bands()
    names = dict(BANDS)
    tested = ''.join(
        f'<tr><td class="k">{e(names[k])}</td>'
        + ''.join(f'<td class="n">{v:.0f}%</td>' for v in vals)
        + '</tr>' for k, vals in VALIDATION_SHARES)
    tested_table = (
        '<table><caption>The test, pooled over eight parks</caption>'
        '<thead><tr><th>Band</th><th class="n">Observed</th>'
        '<th class="n">Model, park held out</th>'
        '<th class="n">Model before the fit</th></tr></thead>'
        f'<tbody>{tested}</tbody></table>')

    title = 'How this works | FoulCast'
    desc = ('How FoulCast is built: what is sourced and what is a model, what '
            'each club says about its netting, why no section number or foul '
            'line is named where nothing establishes one, and how the model '
            'did in its one test against real foul balls.')

    body = f'''<body class="about">
<header>
<p class="wm"><a href="../">FoulCast</a></p>
<h1>How this works</h1>
</header>
<main>
<p class="lede">Every page here does two things: it quotes what the club
publishes about where its protective netting runs, and it estimates where
foul balls come down, beside the one public count of real ones. The first is
sourced. The second is a model.</p>

<h2 id="validation">The model has been tested once against real foul balls</h2>
<p><strong>The short version.</strong> The model was tested once against
FiveThirtyEight's data. It gets the general shape roughly right, puts slightly
too few fouls far down the lines, and does not reliably tell parks apart. The
line under each park page's table says the same.</p>
<p><strong>The data.</strong> Statcast logs that a foul happened, not where it
came down, so there is no large public record of where foul balls land. The one
public count is FiveThirtyEight's: {obs['n']} foul balls from one day at each
of {obs['parks']} parks in 2019, each placed by eye off camera footage into one
of seven broad zones. Those days were picked because they produced unusually
many fouls. The zones fold into four bands by distance along the foul line:
behind the plate, near the dugout, from the dugout to the foul pole, and past
the pole. Eight of the {obs['parks']} parks could be compared with this model;
Oakland Coliseum is not modelled, and the Rangers' 2019 park has been replaced
by a different building.</p>
<p><strong>What the test found.</strong> As first run, the model was closer to
the observed bands than an even split at all eight parks, but put too many
fouls behind the plate and too few down the lines. The one number that decides
the first of those, the share of fouls that leave the bat travelling backward,
had been set by hand. It has since been calibrated to these same fouls: it was
0.28 and is now 0.17. Because it was fitted to this data, the figures the model
now gives at these eight parks agree with it partly because they were made to.
The fair measure is to fit the rate on seven parks and predict the eighth, for
each park in turn, and that is the middle column below.</p>
{tested_table}
<p>Fitted that way, the model is nearer the observed bands than before at
seven of the eight parks. It still puts too many fouls just past the dugouts
and slightly too few from there to the poles: its forward fouls come down too
close to the plate, which the back-foul rate cannot change. And it does not
tell the parks apart. It puts about the same share behind the plate at every
park, where the observed share runs from about a quarter at some parks to half
at one; the average of the other seven parks predicts each park's bands better
than the model does at six of the eight. Some of the observed spread is each
day's hitters and some is chance on a hundred balls, but the model is not in a
position to show any of it.</p>
<p><strong>What has not been tested.</strong> Anything finer than the four
bands. No seating area, deck or section on this site has been compared with a
real foul ball, so those figures are on each park page under Details, under a
heading that says so. No page here puts a single number on how often the model
is right, because one coarse test on {obs['parks']} days cannot support one.</p>

<h2 id="sourced">What is sourced and what is not</h2>
<p><strong>Netting is sourced, and quoted rather than interpreted.</strong>
Each park page quotes what the club itself publishes about where its netting
runs, word for word, and links to the page the words came from. The clubs'
pages were first read on {e(RESEARCH_DATE)} and read again for the quotations
on {e(CLUB_NETTING_READ)}. At <strong>{len(states)} of the 31 parks</strong>
the club says where its netting runs; at {spelled(len(conflicts))} its page
says two things that cannot both be true, and both are quoted; at the other
{spelled(len(unsaid))} nothing the club publishes says where it runs.</p>
<p>No page says which of this model's own seating areas the netting stands in
front of. Most clubs give section numbers, and putting those onto this model's
areas means reading them against the seat labels this model carries &mdash;
which the parks' own seating maps show are in the wrong place at twenty-seven
of the thirty parks whose map has been read. So the club's sentence is given as
it stands, and a reader holding a ticket with a section number on it can make
the one join this site is not in a position to make.</p>
<p><strong>The park dimensions are sourced</strong> &mdash; foul territory area
and backstop distance, from Andrew Clem's stadium statistics, cross-checked
against the Seamheads ballpark database, with the disagreements between them
stated on each page. They place each park's seating. They do not shape it: no
public source gives the angle of a seating area off the foul line or the height
of a deck in feet, for any ballpark, so every park here shares one bowl shape
and every park is modelled as an exact left-right mirror.</p>
<p>One consequence is visible from the grid of drawings and worth saying out
loud: {busiest_sentence(parks)} That is partly a real effect &mdash; balls
deflected back over the catcher have to land somewhere, and it is why there
is a screen there &mdash; and partly an artefact of every park sharing one
bowl shape. It is not a finding about any individual ballpark.</p>

<h2 id="netting-words">What a club's netting statement means</h2>
<p>{NETTING_CLUB_CAVEAT}</p>
<p>No seat on this site is described as protected outright, and none of them is
called a good bet either. The clubs' own netting pages say fans sitting behind
netting "are still exposed to objects leaving the field of play", and this model
has been tested against real foul balls only in four broad bands, never seat by
seat.</p>

<h2 id="parks">What each club says about its netting</h2>
<p>All 31 ballparks, grouped by what the club publishes, not by how good the
ballpark is. The tag against each park is whether anything establishes which
of its two foul lines is which &mdash; a separate question from netting, and
one where the answer is no at most of them. The figure on the right is this
model's estimate of how many foul balls a game reach seats at all, and no real
data has tested it.</p>
{groups}

<h2 id="sides">Which foul line is which, and why most pages will not say</h2>
<p>Every ballpark on this site is modelled as an exact left-right mirror, which
means a park with its two sides written down the wrong way round produces
figures identical to one with them the right way round. This model cannot see
the difference from the inside, and neither can a published netting range: it
gives the two ends of the run, not which foul line each end is on. Only a
source that names a side alongside specific seats can settle it, and
<strong>{len(confirmed)} of the 31 parks have one</strong>.</p>
<p>This is not a hypothetical. At one ballpark the two sides <em>were</em>
written down backwards, and its netting was marked area by area on this site,
cited and apparently matched, until its own seating map was read. So at the
parks with nothing to check against, the two foul lines are shown as a single
seating area each and no area is called first-base or third-base. Every park
page states its own position on this, under Details, whichever of the four it
is in. A club's own words may still name a foul line on such a page: they name
the club's sections, not this model's areas.</p>

<h2 id="numbers">Why there are no section numbers here, outside a quotation</h2>
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
not in the building. Each of the twenty-seven park pages says so in a line
over its table of seating areas, under Details.</p>
<p>Three ballparks agreed, on both questions a map can settle. They are stated
on their own pages in the same place and at the same length as the twenty-seven,
because they were checked the same way, and an agreement nobody publishes reads
as an absence of evidence. The thirty-first park has no map to read at all, and
its page says so. So seating is described by position &mdash; the lower bowl
behind the plate, the dugout boxes down the foul lines &mdash; and the only
section numbers anywhere on this site are inside a quotation from a club, where
they are the club's own numbers for its own seats and carry none of this
model's errors.</p>

<h2 id="diagram">Reading the drawing and the table</h2>
<p>Home plate at the bottom, the two foul lines running out, and the seating
the model tracks drawn as an arc behind them. It is a schematic,
not to scale and not a seating chart: one generic bowl, its depth set by each
park's published foul territory and backstop. Every park is drawn in the same
feet, so a park with more published foul ground really is a larger drawing
&mdash; the grid on the front page is where that shows, because it is the one
place the 31 are side by side. A park's own page compares it with nothing and
crops the same drawing to that park. The drawing carries no netting: the
club's own sentence, directly under it, is where that is.</p>
<p>The seating is cut into the four bands FiveThirtyEight's count of real
fouls can be compared in, by distance along the foul line: behind the plate,
up to {near:.0f} feet out; near the dugout, from {near:.0f} to {far:.0f} feet; from
there to the foul pole; and past the pole. The dugout ends are an estimate from the rule-book
layout. A seat is in the band a ball landing on it would be counted in. No
drawn seat at any park reaches a foul pole, so the band past the pole is in
the table and not on the drawing. The decks within a band are drawn as one
piece, because nothing finer than a band has been tested; the seating areas
and decks are on each park page under Details, labelled as untested.</p>
<p>Shade carries the model's share of foul balls in each band: {shades}.
Shades are against the busiest band at the same park &mdash; "most" is at
least three quarters of that band's share, "more" at least half, "fewer" at
least a quarter, "fewest" anything less &mdash; and the table under each drawing
gives every band's share to the whole per cent, beside a swatch of its shade
and beside FiveThirtyEight's share for the same band. Both foul lines are
always shaded alike: a band is pooled over both lines, and the model builds
them as exact mirrors.</p>
<p>The shades are relative to the park and not fixed across the 31, because the
parks barely differ: the model puts the same share behind the plate at every
park to within a point, and the same share in each of the other bands to
within a few points, and what difference there is comes mostly from each park's
published dimensions, which also set how big the drawing is. Shading the parks against one another would compare one bowl shape
with itself.</p>
<p>No figure on this site is ever drawn as a length &mdash; no bars, no filled
shares, no meters. The numbers come out of estimated geometry that has been
tested once, coarsely, and a drawn length would put them on a scale and say
they were measured to it. The drawing's own lengths are the two sourced
measurements; the model's figures are carried by shade and printed in the
table, to the whole per cent the test read them at.</p>

<h2 id="method">How the figures were produced</h2>
<p>One full game, both lineups, the same 18 batters at every park on this site,
so the park is the only thing that changes. The eighteen are real hitters chosen
to stand for the league rather than for any club: nine from each side of the
plate, one from each ninth of the league&rsquo;s range of fouls per plate
appearance, each the hitter in that ninth whose exit speed, launch angle and
pull tendency on Statcast for 2025&ndash;26 sit nearest the league average. Those
figures, the hitter&rsquo;s own, are what the model samples from. {sims}
simulations per batter,
fixed seed, run on {e(run_dates(parks))}. The table on each park page gives
the share of every foul the model produces that comes down in each of the four
bands, seated or not, as FiveThirtyEight's zones count them. The seating areas
and decks, in foul balls a game, are under Details &mdash; a model estimate, not
a count of anything observed, and untested by any real data.</p>
<p>A share of the fouls the model produces land where it has no seating area
to put them &mdash; deep down the lines near the poles, in the gap in front of
the first row, or under a covered deck. They are in the bands, which count
every foul, and dropped from the seating areas, and each park page states its
own share, which is why the area figures are a shape rather than a census.</p>
<p>At a park where nothing says which foul line is which, the two foul lines
are one area each rather than a first-base area and a third-base one. A figure
on one of those rows is what reaches <em>one</em> of the two lines, which keeps
it comparable with the behind-plate rows beside it. The model builds both lines
identically, so the pair would differ only by simulation noise in any case.</p>

<h2 id="limits">What this model does not know</h2>
{limits}

<h2 id="sources">Sources and dates</h2>
<p>Netting quoted from each club's own page as read on {e(CLUB_NETTING_READ)},
and first read on {e(RESEARCH_DATE)}; each park page links to the page it
quotes. Park dimensions from Andrew Clem's stadium statistics, cross-checked
against the Seamheads ballpark database. Seating maps read on
{e(MAP_READ_DATE)} and {e(LATER_READ_DATE)}. Model run on
{e(run_dates(parks))}.</p>
<p>FoulCast is a model of foul ball flight. It is not affiliated with Major
League Baseball or with any club, and nothing on it will keep a ball from
reaching you.</p>
</main>
<footer>
<p><a href="../">All 31 ballparks</a></p>
</footer>
</body>'''
    return page(title, desc, body, '/about/', base_url)


# ============================================================
# The page that is not there
# ============================================================

def not_found_page() -> str:
    """The 404, in the site's own look.

    The server used to answer a mistyped park URL with Flask's unstyled
    default, which dropped a visitor out of the site entirely. This is served
    by `webapp_v2` for every path it does not know, at any depth, so its two
    links are absolute rather than relative like every other page here: a
    relative link on a page served at `/parks/fenway/x/` would point nowhere.
    No canonical tag and no place in the sitemap — it is not a page anyone
    should land on on purpose.
    """
    body = '''<body class="about">
<header>
<p class="wm"><a href="/parks/">FoulCast</a></p>
<h1>There is no page here</h1>
</header>
<main>
<p class="lede">Nothing on this site lives at that address. It is 31 ballpark
pages and one page explaining how they were made.</p>
<p><a href="/parks/">All 31 ballparks</a> &middot;
<a href="/parks/about/">How this works</a></p>
</main>
</body>'''
    return page('Page not found | FoulCast',
                'There is no page at this address on FoulCast.', body, None, '')


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
    total += write(os.path.join(out_dir, 'about', 'index.html'),
                   about_page(parks, base_url))
    total += write(os.path.join(out_dir, '404.html'), not_found_page())

    if base_url:
        urls = ''.join(
            f'<url><loc>{e(base_url)}/{e(p["slug"])}/</loc></url>'
            for p in sorted(parks, key=lambda x: x['name']))
        total += write(os.path.join(out_dir, 'sitemap.xml'),
                       '<?xml version="1.0" encoding="UTF-8"?>\n'
                       '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                       f'<url><loc>{e(base_url)}/</loc></url>'
                       f'<url><loc>{e(base_url)}/about/</loc></url>'
                       f'{urls}</urlset>\n')

    print(f'\n{len(parks) + 2} pages, {total / 1024:.0f} KB total, '
          f'{total / (len(parks) + 2) / 1024:.1f} KB average.')
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
