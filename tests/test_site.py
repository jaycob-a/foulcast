"""
Tests for the public site — the four hard constraints, enforced rather than
trusted.

The constraints come out of `AUDIT.md` and `NOTES.md`, and each one exists
because getting it wrong would put a claim on a public page that this project
cannot support:

1. **No printed section numbers.** Nineteen of the 31 zone tables in
   `stadium.py` are suspect on their numbering (`AUDIT.md`, Step 10 update).
2. **Netting leads, the model follows.** Netting is sourced; the model is an
   estimate, and the page order has to say so.
3. **The word "safe" never appears**, in any form. The clubs' own netting pages
   say fans behind netting remain exposed; this model has never seen a real
   foul ball. Neither supports the word.
4. **No accuracy claims**, and the absence of validation stated on every page.

The site is rebuilt into a temporary directory at a low simulation count, so
these test the *generator* rather than whatever happens to be committed. A
second group then tests what *is* committed, because the generator being right
is worth nothing if the pages being served came out of an older one: the
committed pages have to match a fresh render, and the cached model run they
were rendered from has to carry the current model's fingerprint.

Known limit of the section-number test, stated rather than hidden: the
substring check only runs on printed labels of three characters or more.
Labels like "9" or "26" — real at Fenway, Globe Life and Truist — cannot be
distinguished from ordinary prose by substring search. Those parks are covered
by the pattern checks instead, which catch every mechanism by which a number
could actually leak: a raw section name, a printed range, or the word "section"
followed by a digit.
"""
import ast
import json
import os
import re
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from foulball.stadium import STADIUMS
from foulball.netting import join_park
from foulball.seat_map import build_printed_index, printed_range_display
import site_build
from site_data import (
    PARK_SOURCES, ZONE_WORDS, MAP_READS, NO_MAP_READ, SIDE_STATE_WORDS,
)

# Low enough to keep the suite quick; the constraints under test are properties
# of the copy and the layout, not of the simulation count.
TEST_SIMS = 8

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMITTED_SITE = os.path.join(REPO, 'site')
COMMITTED_CACHE = os.path.join(REPO, '.cache', 'site', 'park_stats.json')


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    """A complete build, in a temp dir with its own cache."""
    out = tmp_path_factory.mktemp('site')
    cache = tmp_path_factory.mktemp('cache') / 'park_stats.json'
    parks = site_build.build(str(out), base_url='', sims=TEST_SIMS,
                             cache_path=str(cache))
    pages = {}
    for p in parks:
        with open(out / p['slug'] / 'index.html', encoding='utf-8') as fh:
            pages[p['slug']] = fh.read()
    with open(out / 'index.html', encoding='utf-8') as fh:
        pages[''] = fh.read()
    return {'dir': str(out), 'parks': {p['slug']: p for p in parks},
            'pages': pages}


# ============================================================
# Shape
# ============================================================

def test_thirty_one_park_pages_plus_a_home_page(built):
    assert len(built['parks']) == 31
    assert len(built['pages']) == 32
    assert set(built['parks']) == {s['slug'] for s in PARK_SOURCES.values()}


def test_every_registry_park_has_a_page(built):
    keys = {p['key'] for p in built['parks'].values()}
    assert keys == set(STADIUMS)


def test_committed_build_covers_every_park():
    """What the web app serves, not what the test just built."""
    if not os.path.isdir(COMMITTED_SITE):
        pytest.skip('site/ not built in this checkout')
    assert os.path.exists(os.path.join(COMMITTED_SITE, 'index.html'))
    for src in PARK_SOURCES.values():
        page = os.path.join(COMMITTED_SITE, src['slug'], 'index.html')
        assert os.path.exists(page), f'missing built page for {src["slug"]}'


# ============================================================
# The cache, the committed build, and the model behind both
# ============================================================
#
# Two staleness holes, both found by inspection rather than by a failing test,
# which is why they are tests now:
#
# 1. The model cache keyed on park + sims + seed only. Halving Fenway's foul
#    territory in `PARK_PARAMS` and running the normal build reproduced the
#    pages byte for byte without simulating anything, because the cache
#    entries still looked current.
# 2. Nothing compared the committed `site/` with what the generator would
#    produce today, so the pages served to the public sat five commits behind
#    the copy that generated them.


def _package_imports(module: str) -> set[str]:
    """The `foulball` modules `module` imports, read out of its source."""
    path = os.path.join(REPO, 'foulball', f'{module}.py')
    with open(path, encoding='utf-8') as fh:
        tree = ast.parse(fh.read())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            found.add(node.module.split('.')[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith('foulball.'):
                    found.add(alias.name.split('.')[1])
    return found


def test_model_sources_cover_the_model_imports():
    """`MODEL_SOURCES` is a hand-kept list, so this walks the imports and fails
    when a module joins the model path without joining the list — which is how
    the fingerprint would quietly stop covering the model."""
    closure, queue = set(), ['matchup_engine', 'stadium']
    while queue:
        mod = queue.pop()
        if mod in closure:
            continue
        closure.add(mod)
        queue.extend(_package_imports(mod) - closure)

    listed = set(site_build.MODEL_SOURCES)
    excluded = set(site_build.DISPLAY_ONLY_SOURCES)
    assert listed <= closure, \
        f'MODEL_SOURCES names modules the model never imports: {listed - closure}'
    assert closure <= listed | excluded, \
        (f'these modules are on the model path but are neither fingerprinted '
         f'nor listed as display-only: {sorted(closure - listed - excluded)}')
    assert not listed & excluded


def _repo_fingerprint() -> str:
    """The fingerprint of this checkout, independent of a patched `ROOT`."""
    root = site_build.ROOT
    site_build.ROOT = REPO
    try:
        return site_build.model_fingerprint()
    finally:
        site_build.ROOT = root


def test_a_park_params_change_moves_the_fingerprint(tmp_path, monkeypatch):
    """The exact edit that used to be invisible: Fenway's foul territory,
    halved. Computed against a copy of the tree, so the real one is untouched.
    """
    shutil.copytree(os.path.join(REPO, 'foulball'), tmp_path / 'foulball',
                    ignore=shutil.ignore_patterns('__pycache__'))
    monkeypatch.setattr(site_build, 'ROOT', str(tmp_path))
    assert site_build.model_fingerprint() == _repo_fingerprint()

    stadium_py = tmp_path / 'foulball' / 'stadium.py'
    text = stadium_py.read_text(encoding='utf-8')
    edited = text.replace("'fenway_park': ParkParams(18_100,",
                          "'fenway_park': ParkParams(9_050,")
    assert edited != text, 'the Fenway PARK_PARAMS line has moved; fix this test'
    stadium_py.write_text(edited, encoding='utf-8')

    assert site_build.model_fingerprint() != _repo_fingerprint()


def _fake_cache(path, fingerprint, sims):
    """A complete, plausible cache stamped with a given fingerprint."""
    entries = {k: {'park': k, 'sims': sims, 'seed': site_build.SEED,
                   'model': fingerprint, 'zone_fouls': {}, 'zone_ev': {},
                   'into_seats': 1.0, 'total_fouls': 2.0, 'unmatched': 1.0}
               for k in STADIUMS}
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(entries, fh)


def test_a_stale_fingerprint_re_simulates_every_park(tmp_path, monkeypatch):
    cache = tmp_path / 'park_stats.json'
    _fake_cache(cache, 'not-the-current-model', TEST_SIMS)

    ran = []

    def fake_run(key, sims, fingerprint=None):
        ran.append(key)
        return {'park': key, 'sims': sims, 'model': fingerprint}

    monkeypatch.setattr(site_build, 'run_park', fake_run)
    site_build.load_stats(refresh=False, sims=TEST_SIMS, cache_path=str(cache))
    assert sorted(ran) == sorted(STADIUMS), \
        'a cache produced by a different model was reused'


def test_a_current_fingerprint_is_reused(tmp_path, monkeypatch):
    """The other half: the fingerprint must not defeat the cache it guards."""
    cache = tmp_path / 'park_stats.json'
    _fake_cache(cache, site_build.model_fingerprint(), TEST_SIMS)

    def refuse(*args, **kwargs):
        pytest.fail('re-simulated a park whose cache entry was current')

    monkeypatch.setattr(site_build, 'run_park', refuse)
    stats = site_build.load_stats(refresh=False, sims=TEST_SIMS,
                                  cache_path=str(cache))
    assert set(stats) == set(STADIUMS)


def test_the_committed_cache_came_from_the_current_model():
    """What the committed pages were rendered from. If this fails, the numbers
    on the public pages come from a model that no longer exists; rebuild with
    `python site_build.py`."""
    if not os.path.exists(COMMITTED_CACHE):
        pytest.skip('no committed model cache in this checkout')
    with open(COMMITTED_CACHE, encoding='utf-8') as fh:
        cache = json.load(fh)
    fingerprint = site_build.model_fingerprint()
    behind = sorted(k for k, e in cache.items() if e.get('model') != fingerprint)
    assert not behind, f'the cached model run is behind the model at: {behind}'
    assert all(e['sims'] == site_build.SIMS for e in cache.values())


# The one thing on a page that moves without anyone editing anything.
_BUILD_DATE = re.compile(r'rebuilt \d{4}-\d{2}-\d{2}')


def test_the_committed_site_matches_a_fresh_render(tmp_path):
    """The hole that let `site/` sit five commits behind its own generator.

    Rendered from the committed cache rather than simulated, so this takes a
    second rather than eight minutes: the cache is checked against the model by
    `test_the_committed_cache_came_from_the_current_model`, and the pages are
    checked against the cache here. The build date in the footer is normalised
    out — it is the only part of a page that changes on its own — and
    everything else has to match byte for byte.
    """
    if not os.path.isdir(COMMITTED_SITE):
        pytest.skip('site/ not built in this checkout')
    if not os.path.exists(COMMITTED_CACHE):
        pytest.skip('no committed model cache in this checkout')

    out = tmp_path / 'site'
    site_build.build(str(out), base_url='', sims=site_build.SIMS,
                     no_model=True, cache_path=COMMITTED_CACHE)

    def files(root):
        return {os.path.relpath(os.path.join(where, name), root).replace(os.sep, '/')
                for where, _, names in os.walk(root) for name in names}

    fresh, committed = files(str(out)), files(COMMITTED_SITE)
    assert fresh == committed, \
        (f'a fresh render and committed site/ hold different files '
         f'(only in site/: {sorted(committed - fresh)}; only in the render: '
         f'{sorted(fresh - committed)}); rebuild with `python site_build.py`')

    stale = []
    for rel in sorted(fresh):
        with open(out / rel, encoding='utf-8') as fh:
            new = _BUILD_DATE.sub('rebuilt <date>', fh.read())
        with open(os.path.join(COMMITTED_SITE, rel), encoding='utf-8') as fh:
            old = _BUILD_DATE.sub('rebuilt <date>', fh.read())
        if new != old:
            stale.append(rel)
    assert not stale, (f'{len(stale)} committed page(s) differ from a fresh '
                       f'render, starting with {stale[0]}; rebuild with '
                       f'`python site_build.py` and commit site/')


# ============================================================
# Constraint 1 — no printed section numbers
# ============================================================

# The word "section" or "sec" immediately followed by a number, in any case.
SECTION_NUMBER = re.compile(r'(?i)\bsecs?(?:tion)?s?\.?\s*\d')
# A printed range: "119-121", "011-029". Four-digit years cannot match.
PRINTED_RANGE = re.compile(r'\b\d{2,3}\s*[-–—]\s*\d{2,3}\b')
# Prefixed labels: FB17, LB101, RS12, FD1, DG1, G5, and the same with a space.
PREFIXED_LABEL = re.compile(r'\b(?:FB|LB|RS|FD|DG|GS|HPPC|EMCC|PB|RFB|COR|HRP)'
                            r'\s?\d+\b')


def _strip_numeric_prose(text: str) -> str:
    """Remove figures that legitimately carry digit runs, so the label search
    does not trip over '22,900 sq ft', a year, or Tropicana Field's 100% upper
    deck cover — which collides with a real printed label at that park."""
    text = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', ' D ', text)      # ISO dates
    text = re.sub(r'\d{1,3}(?:,\d{3})+', ' N ', text)
    text = re.sub(r'\b(?:19|20)\d{2}\b', ' Y ', text)
    text = re.sub(r'\b\d+(?:\.\d+)?\s*'
                  r'(?:%|ft\b|feet\b|foot\b|mph\b|in\b|sq\b|'
                  r'simulations\b|balls\b|parks\b)', ' Q ', text)
    return text


@pytest.mark.parametrize('slug', sorted(s['slug'] for s in PARK_SOURCES.values()))
def test_no_section_numbers_on_any_park_page(built, slug):
    text = built['pages'][slug]
    assert not SECTION_NUMBER.search(text), \
        f'{slug}: page names a section by number'
    assert not PRINTED_RANGE.search(_strip_numeric_prose(text)), \
        f'{slug}: page prints what looks like a section range'
    assert not PREFIXED_LABEL.search(text), \
        f'{slug}: page prints a prefixed section label'


def test_no_section_numbers_on_the_home_page(built):
    text = built['pages']['']
    assert not SECTION_NUMBER.search(text)
    assert not PRINTED_RANGE.search(_strip_numeric_prose(text))
    assert not PREFIXED_LABEL.search(text)


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_no_raw_zone_name_reaches_the_page(built, key):
    """The mechanism a number would actually leak by: printing the model's own
    section name, which carries its printed range in parentheses."""
    slug = PARK_SOURCES[key]['slug']
    text = built['pages'][slug]
    stadium = STADIUMS[key]()
    for sec in stadium.sections:
        assert sec.name not in text, f'{slug}: raw zone name "{sec.name}"'
        disp = printed_range_display(sec)
        if disp:
            assert disp not in text, f'{slug}: printed range "{disp}"'


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_no_printed_label_appears_on_the_page(built, key):
    """Every printed label of three characters or more, checked as a word."""
    slug = PARK_SOURCES[key]['slug']
    text = _strip_numeric_prose(built['pages'][slug])
    stadium = STADIUMS[key]()
    for label in build_printed_index(stadium):
        if len(label) < 3:
            continue
        assert not re.search(rf'\b{re.escape(label)}\b', text), \
            f'{slug}: printed label "{label}" appears on the page'


# ============================================================
# Constraint 2 — netting leads, the model follows
# ============================================================

@pytest.mark.parametrize('slug', sorted(s['slug'] for s in PARK_SOURCES.values()))
def test_netting_section_precedes_the_model_section(built, slug):
    text = built['pages'][slug]
    net = text.index('id="netting"')
    zones = text.index('id="zones"')
    readings = text.index('id="readings"')
    assert net < zones < readings, f'{slug}: model output is above the netting'


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_netting_state_is_stated_either_way(built, key):
    """A gap is stated as a gap, not left blank; a sourced extent names its
    source and the date it was read."""
    slug = PARK_SOURCES[key]['slug']
    text = built['pages'][slug]
    stadium = STADIUMS[key]()
    join = join_park(stadium, key)
    if join.status == 'mapped':
        assert 'behind netting' in text
        assert join.park.source in text
        assert join.park.retrieved in text
    else:
        assert 'Not verified' in text, f'{slug}: gap not stated'
        assert 'gap' in text.lower()


def test_side_specific_netting_claims_are_hedged(built):
    """Where the published extent lands differently on the two foul lines, the
    page is asserting which line is which. That is only allowed at a park whose
    sides are established, and even there it has to carry its own warning: the
    anchors settle the mirror and nothing else, and at all four of these parks
    the club's own map puts the plate somewhere the model does not.
    """
    hedged = 0
    for slug, p in built['parks'].items():
        text = flat(built['pages'][slug])
        asserting = (p['net']['state'] == 'mapped'
                     and p['sides']['named'] and p['net']['sides_differ'])
        if asserting:
            hedged += 1
            assert 'so the two lines are named separately above' in text, \
                f'{slug}: side-specific netting claim is not hedged'
        else:
            assert 'so the two lines are named separately above' not in text, \
                f'{slug}: side hedge shown where no side claim is made'
    assert hedged == 4, f'expected 4 side-asymmetric mapped parks, {hedged}'


def test_twenty_four_parks_are_netting_gaps(built):
    """The counts on the home page have to be the counts in the data.

    Went from 20 to 21 when the side-anchor check (netting G5) rejected
    Oriole Park: its seating map has the lower bowl numbered the opposite way
    round from the zone table. Went from 21 to 24 when the second map read
    (Step 12) did the same to Coors, Progressive and Oracle. See
    MAP_FINDINGS.md.
    """
    gaps = [p for p in built['parks'].values() if p['net']['state'] != 'mapped']
    assert len(gaps) == 24
    assert 'At the other 24 it is a gap' in flat(built['pages'][''])


def test_the_home_page_splits_gaps_by_whose_they_are(built):
    """The larger group of gaps is this project's own defects, and the page has
    to be built so that a reader sees that without reading the copy.

    `join.status` already draws the line — `join_gap` is a park whose club
    published something usable and whose *model* could not use it — and this
    test holds the page to it, including the claim that it is the larger of
    the two, which is the whole reason the split is worth making.
    """
    home = flat(built['pages'][''])
    groups = {}
    for p in built['parks'].values():
        groups.setdefault(p['join'].status, []).append(p)
    assert set(groups) == {'mapped', 'join_gap', 'source_gap'}
    assert len(groups['join_gap']) > len(groups['source_gap']), \
        'the copy calls the model-fault group the largest'
    assert len(groups['join_gap']) > len(groups['mapped'])

    for key, heading, _ in site_build.GROUPS:
        marked = f'{heading} <span class="sub">({len(groups[key])})</span>'
        assert marked in home, f'home page is missing the {key} group'
        # Each group's own parks link from it, and only those — a park quietly
        # dropped from all three, or listed twice, would otherwise pass.
        listed = set(re.findall(r'href="([^"]+)/"',
                                home.split(marked)[1].split('</ul>')[0]))
        assert listed == {p['slug'] for p in groups[key]}, \
            f'{key} group does not list exactly its own parks'


# ============================================================
# Constraint 5 — no foul line is named where nothing establishes it
# ============================================================

# Every heading that names a foul line. These are the phrases a page is only
# allowed to print where a source establishes which line is which.
SIDE_HEADINGS = [words[0] for zid, words in ZONE_WORDS.items()
                 if zid[:3] in ('1B-', '3B-')]


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_no_foul_line_is_named_where_it_is_not_established(built, key):
    """The constraint MAP_FINDINGS.md forced.

    Oriole Park was `mapped` with its two sides swapped and every check in the
    repo passed it, because the geometry is mirror-symmetric. So a page may
    name a foul line only where a side-naming source backs it — twelve parks —
    and at the other nineteen the matching pair is folded into one row.
    """
    slug = PARK_SOURCES[key]['slug']
    p = built['parks'][slug]
    text = built['pages'][slug]
    if p['sides']['named']:
        assert any(h in text for h in SIDE_HEADINGS), \
            f'{slug}: sides are established but no area names one'
        return
    for heading in SIDE_HEADINGS:
        assert heading not in text, \
            f'{slug}: names a foul line ("{heading}") with nothing to back it'
    assert 'down the two foul lines' in text, \
        f'{slug}: sides are unestablished but the pair was not folded'


def test_only_sixteen_parks_may_name_a_foul_line(built):
    """Three parks joined the list in Step 13, off their seating maps:
    Daikin Park, Wrigley Field and Yankee Stadium. Yankee Stadium is the
    instructive one — it always had two club-page anchors, but they name
    sections on a ring this park's zone table does not number, so the park
    was untestable until the map supplied labels the table does carry.

    Step 14 moved three: Target Field and T-Mobile Park joined, because their
    maps confirmed the sides their tables already had, and Comerica Park left.
    Comerica is the instructive one this time — it is the only park so far to
    go the wrong way down this list. Its two club-page anchors (116 on the 1B
    line, 142 on the 3B line) both land right and made it 'ok'; the map read
    adds 101-106 in right field, under the Right Field Balcony the map itself
    labels, and the zone table calls 103-108 "3B Infield". Two anchored
    sections agreeing was never evidence about the other forty.

    Step 15 added two, American Family Field and loanDepot park, and moved
    none off. Both number their bowls monotonically from one foul pole to the
    other with the plate mid-range, so their two side blocks land on the right
    foul lines and only the behind-plate block is misplaced — the shape Target
    Field and T-Mobile Park have. The plate offset is real at both (≈13 at
    American Family, ≈13 at loanDepot) and this list cannot see it; that is
    what `check_side_anchors` says an 'ok' does and does not mean.

    Step 16 added one, Citi Field, and moved none off. It is the last file in
    `seating_maps/` to be read, and it has the same shape again: 101 at the
    right-field pole, 143 at the end of the loop, the plate mid-range, so both
    side blocks land right on all three of the rings its table numbers. The
    behind-plate block is the interesting part — at the field level it is the
    only one in the repo that is already centred, and two rings up it is five
    sections off. An 'ok' cannot see either."""
    named = sorted(p['key'] for p in built['parks'].values()
                   if p['sides']['named'])
    assert named == ['american_family', 'chase_field', 'citi_field',
                     'citizens_bank', 'dodger_stadium', 'fenway_park',
                     'great_american', 'guaranteed_rate', 'loan_depot',
                     'minute_maid', 'rogers_centre', 'target_field',
                     'tmobile_park', 'truist_park', 'wrigley_field',
                     'yankee_stadium']
    assert '16 of the 31 parks have one' in flat(built['pages'][''])


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_every_page_states_its_own_side_position(built, key):
    """Silence about the sides is what let Oriole Park through, so the four
    verdicts are stated on every page, including the twenty-two saying
    nothing was ever tested."""
    slug = PARK_SOURCES[key]['slug']
    text = flat(built['pages'][slug])
    label = SIDE_STATE_WORDS[built['parks'][slug]['sides']['state']][0]
    assert 'id="labels"' in text
    assert label in text, \
        f'{slug}: does not state which foul line is which, or that it cannot'


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_the_map_read_is_on_the_page_where_there_is_one(built, key):
    """Thirty maps read, twenty-seven disagreements. A park with a read has
    every one of its findings stated; the one park without has the absence
    stated, because an unread park has not passed anything."""
    slug = PARK_SOURCES[key]['slug']
    text = flat(built['pages'][slug])
    if key in MAP_READS:
        for head, _ in MAP_READS[key]['findings']:
            assert flat(re.sub(r"'", '&#x27;', head)) in text, \
                f'{slug}: map finding missing from the page'
        assert NO_MAP_READ[:40] not in text
    else:
        assert flat(NO_MAP_READ)[:60] in text, \
            f'{slug}: does not say its seating map has never been read'


def test_thirty_seating_maps_have_been_read(built):
    """Every map in `seating_maps/` is written up for the site.

    The count moved from five to thirty when Steps 12-16 were transcribed into
    `MAP_READS`. Las Vegas Ballpark is the one park with no map in the folder
    at all, and it is the only one that may fall through to `NO_MAP_READ`.
    """
    assert len(MAP_READS) == 30
    assert set(STADIUMS) - set(MAP_READS) == {'las_vegas_ballpark'}
    assert 'twenty-seven of them disagreed' in flat(built['pages'][''])


def test_the_three_agreeing_maps_are_not_dressed_as_failures(built):
    """Three tables came out right, and a page has to be able to say so.

    An agreement rendered in the same red box as a contradiction is as
    misleading as a contradiction rendered as a pass, which is the defect this
    whole section exists to prevent. So the outcome drives the box class and
    the lead sentence, and this test holds both ends of it.
    """
    agreeing = {k for k, v in MAP_READS.items() if v['outcome'] == 'agrees'}
    assert agreeing == {'minute_maid', 'yankee_stadium', 'dodger_stadium'}
    for key, mr in MAP_READS.items():
        text = flat(built['pages'][PARK_SOURCES[key]['slug']])
        labels = text.split('id="labels"')[1].split('id="zones"')[0]
        if mr['outcome'] == 'agrees':
            assert 'It agrees with this model on both of the questions' in labels
            assert 'nothing needed correcting' in labels
        else:
            assert 'It disagrees with this model in the following ways' in labels
            assert 'None of this has been corrected in the model' in labels


def test_the_fleet_wide_side_count_is_computed_not_written_out(built):
    """The count of parks that cannot name a foul line moved five times
    between Step 11 and Step 16. Every place the site states it reads from
    `side_counts()`, so it cannot go stale in one place and not another."""
    unnamed = site_build.side_counts()['unnamed']
    assert unnamed == sum(1 for p in built['parks'].values()
                          if not p['sides']['named'])
    for slug, p in built['parks'].items():
        text = flat(built['pages'][slug])
        assert f'at {unnamed} of the 31 parks nothing available establishes' \
            in text, f'{slug}: stale or missing side count in the limits'


# ============================================================
# Constraint 3 — the word "safe" never appears
# ============================================================

# Word-bounded, so it catches safe/safer/safest/safety and does not fire on
# "SafecoField.html" — the filename of Clem's T-Mobile Park page, which is a
# real source URL and stays.
SAFE_WORD = re.compile(r'(?i)\bsafe(?:r|st|ty|ly|guard(?:ed|s)?)?\b')


@pytest.mark.parametrize('slug', sorted(list({s['slug'] for s in PARK_SOURCES.values()}) + ['']))
def test_the_word_safe_never_appears(built, slug):
    hit = SAFE_WORD.search(built['pages'][slug])
    assert hit is None, f'{slug or "home"}: "{hit.group(0)}" at {hit.start()}'


@pytest.mark.parametrize('slug', sorted(s['slug'] for s in PARK_SOURCES.values()))
def test_risk_is_described_in_relative_terms(built, slug):
    text = built['pages'][slug]
    assert 'not behind netting' in text or 'netting not verified' in text
    assert 'higher risk' in text or 'lower risk' in text or 'no risk' in text


# ============================================================
# Constraint 4 — no accuracy claims
# ============================================================

# "precise" is deliberately absent: one club's own statement, quoted on the
# Kauffman page, is that its map cannot show "the precise location of the
# netting" — which is the opposite of an accuracy claim.
ACCURACY_CLAIM = re.compile(
    r'(?i)\b(accurate|accuracy|proven|guaranteed|reliable|'
    r'correlation|r\s*=\s*0\.\d)\b')


@pytest.mark.parametrize('slug', sorted(list({s['slug'] for s in PARK_SOURCES.values()}) + ['']))
def test_no_accuracy_claim_anywhere(built, slug):
    hit = ACCURACY_CLAIM.search(built['pages'][slug])
    assert hit is None, f'{slug or "home"}: accuracy language "{hit.group(0)}"'


def flat(text: str) -> str:
    """Collapse the line wrapping so prose assertions do not depend on it."""
    return re.sub(r'\s+', ' ', text)


@pytest.mark.parametrize('slug', sorted(s['slug'] for s in PARK_SOURCES.values()))
def test_every_park_page_says_it_was_never_validated(built, slug):
    text = flat(built['pages'][slug])
    assert 'checked against a real foul ball' in text     # top of the page
    assert 'never been validated' in text                 # top of the page
    assert 'never been compared' in text                  # limits section


@pytest.mark.parametrize('slug', sorted(s['slug'] for s in PARK_SOURCES.values()))
def test_every_park_page_states_its_unmatched_share(built, slug):
    """The share of fouls the model drops is on the page, not hidden."""
    assert 'land where it has no seating area' in flat(built['pages'][slug])


# ============================================================
# The two readings
# ============================================================

def test_souvenir_reading_excludes_netted_zones(built):
    """A netted zone is out of the catching list and in the risk list."""
    checked = 0
    for slug, p in built['parks'].items():
        netted = [z for z in p['zones'] if z['blocks_catch']]
        if not netted:
            continue
        checked += 1
        text = built['pages'][slug]
        catch = text.split('If you want to catch a ball')[1]
        catch_list = catch.split('</ol>')[0]
        risk = text.split('If you want to know what is coming at you')[1]
        risk_list = risk.split('</ol>')[0]
        for z in netted:
            assert z['heading'] not in catch_list, \
                f'{slug}: netted zone in the catching list'
        # The busiest netted zone is still shown under the risk reading.
        busiest = max(netted, key=lambda z: z['fouls'])
        if busiest['fouls'] >= 0.05 and busiest is p['zones'][0]:
            assert busiest['heading'] in risk_list
    # Seven parks are mapped after Step 12 (three lost to the second map read).
    assert checked >= 7, 'expected every mapped park to have a netted zone'


def test_gap_parks_exclude_nothing_and_say_so(built):
    for slug, p in built['parks'].items():
        if p['net']['state'] == 'mapped':
            continue
        text = built['pages'][slug]
        assert 'Nothing is excluded from this list' in text
        assert all(not z['blocks_catch'] for z in p['zones'])


# ============================================================
# Search and delivery
# ============================================================

@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_title_and_description_target_the_park(built, key):
    slug = PARK_SOURCES[key]['slug']
    text = built['pages'][slug]
    name = STADIUMS[key]().name
    title = re.search(r'<title>(.*?)</title>', text).group(1)
    desc = re.search(r'<meta name="description" content="(.*?)">', text).group(1)
    assert name in title, f'{slug}: park name missing from <title>'
    assert name in desc, f'{slug}: park name missing from meta description'
    assert 60 <= len(desc) <= 320, f'{slug}: description is {len(desc)} chars'


def test_titles_and_descriptions_are_unique(built):
    titles, descs = set(), set()
    for text in built['pages'].values():
        titles.add(re.search(r'<title>(.*?)</title>', text).group(1))
        descs.add(re.search(r'<meta name="description" content="(.*?)">',
                            text).group(1))
    assert len(titles) == 32
    assert len(descs) == 32


@pytest.mark.parametrize('slug', sorted(list({s['slug'] for s in PARK_SOURCES.values()}) + ['']))
def test_pages_are_mobile_first_and_self_contained(built, slug):
    text = built['pages'][slug]
    assert 'name="viewport"' in text and 'width=device-width' in text
    # One request per page: no scripts, no images, no external stylesheets.
    assert '<script' not in text
    assert '<img' not in text
    assert 'rel="stylesheet"' not in text
    assert len(text.encode('utf-8')) < 40_000, 'page is getting heavy'


def test_canonical_tags_only_when_a_base_url_is_given(built, tmp_path):
    assert 'rel="canonical"' not in built['pages']['fenway-park']
    out = tmp_path / 'site'
    cache = tmp_path / 'park_stats.json'
    site_build.build(str(out), base_url='https://example.test', sims=TEST_SIMS,
                     cache_path=str(cache))
    with open(out / 'fenway-park' / 'index.html', encoding='utf-8') as fh:
        text = fh.read()
    assert 'rel="canonical" href="https://example.test/fenway-park/"' in text
    assert os.path.exists(out / 'sitemap.xml')


# ============================================================
# The sourced figures
# ============================================================

@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_sourced_figures_match_what_the_model_uses(built, key):
    """A figure on the page and a different figure in the model would be the
    worst failure available here, so it is checked rather than reviewed."""
    from foulball.stadium import PARK_PARAMS
    src = PARK_SOURCES[key]
    params = PARK_PARAMS[key]
    assert (src['foul_area'] or None) == (params.foul_area_sqft or None)
    assert (src['backstop'] or None) == (params.backstop_ft or None)


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_unpublished_figures_are_shown_as_gaps(built, key):
    slug = PARK_SOURCES[key]['slug']
    text = built['pages'][slug]
    src = PARK_SOURCES[key]
    if src['foul_area'] is None or src['backstop'] is None:
        assert 'Not published' in text, f'{slug}: unsourced figure not flagged'
    assert 'Clem' in text and ('Seamheads' in text or src['seamheads'] is None)


# ============================================================
# Serving — the routes the web app exposes
# ============================================================

@pytest.fixture
def client():
    from webapp_v2 import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_site_routes_serve_the_built_pages(client):
    if not os.path.isdir(COMMITTED_SITE):
        pytest.skip('site/ not built in this checkout')
    home = client.get('/parks/')
    assert home.status_code == 200
    assert b'Where foul balls land, ballpark by ballpark' in home.data

    park = client.get('/parks/fenway-park/')
    assert park.status_code == 200
    assert b'Foul balls at Fenway Park' in park.data


def test_unknown_slugs_and_traversal_are_refused(client):
    assert client.get('/parks/not-a-ballpark/').status_code == 404
    # The slug is matched against the registry, so nothing reaches a path.
    assert client.get('/parks/..%2f..%2fwebapp_v2.py/').status_code == 404


def test_robots_and_sitemap_are_generated_off_the_live_host(client):
    robots = client.get('/robots.txt')
    assert robots.status_code == 200
    assert b'Sitemap: http://localhost/sitemap.xml' in robots.data

    sitemap = client.get('/sitemap.xml')
    assert sitemap.status_code == 200
    body = sitemap.data.decode()
    assert body.count('<loc>') == 32
    assert 'http://localhost/parks/fenway-park/' in body
