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

Step 23 rebuilt the pages around the drawings and added a fifth kind of
check, the one that now matters most: a **word budget**. The home page is a
gallery of the 31 schematics and may carry at most 40 words of prose outside
the tiles; a park page is its drawing, one sentence, the table and one line,
and may carry at most 60 words visible without opening a disclosure, not
counting the table and the drawing's own labels. Every explanation the site
has moved to `/about/`, and the tests that used to read those explanations
off the home page or off every park page now read them there.

Known limit of the section-number test, stated rather than hidden: the
substring check only runs on printed labels of three characters or more.
Labels like "9" or "26" — real at Fenway, Globe Life and Truist — cannot be
distinguished from ordinary prose by substring search. Those parks are covered
by the pattern checks instead, which catch every mechanism by which a number
could actually leak: a raw section name, a printed range, or the word "section"
followed by a digit.
"""
import ast
import html
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
import site_diagram
from site_data import (
    PARK_SOURCES, ZONE_WORDS, MAP_READS, NO_MAP_READ, SIDE_STATE_WORDS,
    MODEL_LIMITS,
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
    with open(out / 'about' / 'index.html', encoding='utf-8') as fh:
        pages['about'] = fh.read()
    return {'dir': str(out), 'parks': {p['slug']: p for p in parks},
            'pages': pages}


PARK_SLUGS = sorted(s['slug'] for s in PARK_SOURCES.values())
ALL_PAGES = PARK_SLUGS + ['', 'about']


# ============================================================
# Shape
# ============================================================

def test_thirty_one_park_pages_plus_home_and_about(built):
    assert len(built['parks']) == 31
    assert len(built['pages']) == 33
    assert set(built['parks']) == {s['slug'] for s in PARK_SOURCES.values()}


def test_every_registry_park_has_a_page(built):
    keys = {p['key'] for p in built['parks'].values()}
    assert keys == set(STADIUMS)


def test_committed_build_covers_every_park():
    """What the web app serves, not what the test just built."""
    if not os.path.isdir(COMMITTED_SITE):
        pytest.skip('site/ not built in this checkout')
    assert os.path.exists(os.path.join(COMMITTED_SITE, 'index.html'))
    assert os.path.exists(os.path.join(COMMITTED_SITE, 'about', 'index.html'))
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
# The schematic above each distribution table — and, since Step 23, the 31
# small copies of it on the home page — and the attributes inside it that
# carry drawing coordinates rather than words. See `_strip_numeric_prose`.
SCHEMATIC = re.compile(r'<figure class="dia[^"]*">.*?</figure>', re.S)
SVG_GEOMETRY = re.compile(r'\s(?:d|x|y|transform|viewBox)="[^"]*"')


def _strip_numeric_prose(text: str) -> str:
    """Remove figures that legitimately carry digit runs, so the label search
    does not trip over '22,900 sq ft', a year, or Tropicana Field's 100% upper
    deck cover — which collides with a real printed label at that park.

    The schematic's coordinates go with them, for the same reason and no
    other: this is a search for a seat label a *reader* could see, and the
    numbers inside a `d` or an `x` attribute are never rendered as characters.
    A drawing that puts a wedge corner at 134 feet is not printing Wrigley's
    section 134, and before Step 21 blanked them, at 30 of the 31 parks it
    looked exactly like it was.

    The blanking is as narrow as it can be made: geometry attributes, inside
    the schematic figure, and nowhere else on the page. Every part of the
    drawing a reader can actually read — its alt text, its two foul-line
    labels, its legend, its caption — stays in the text and is searched like
    any other prose.
    """
    text = SCHEMATIC.sub(lambda m: SVG_GEOMETRY.sub(' G="" ', m.group(0)), text)
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


@pytest.mark.parametrize('slug', ['', 'about'])
def test_no_section_numbers_on_the_home_or_about_page(built, slug):
    text = built['pages'][slug]
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


def netting_sentence(text: str) -> str:
    """The one sentence above the fold that says where the net is."""
    assert 'id="netting"' in text, 'no netting statement on this page'
    return text.split('id="netting"')[1].split('</p>')[0]


@pytest.mark.parametrize('slug', sorted(s['slug'] for s in PARK_SOURCES.values()))
def test_the_answer_stands_above_everything_that_qualifies_it(built, slug):
    """Step 22, tightened by Step 23. Five things on the visible page, in
    this order, and nothing else.

    Two passes before Step 22 shortened the copy at the top of a park page
    and it still opened with three paragraphs of caveats, because the problem
    was never length: the page was organised around this project's
    epistemology instead of around the reader's question. So the order is
    enforced here rather than trusted, including the two things that would
    slide back up first — a panel of working above the table, and the standing
    caveat above the drawing it does not qualify. Step 23 put every panel of
    working behind one closed Details disclosure under the caveat, and that
    is enforced here too.
    """
    text = built['pages'][slug]
    order = [('the ballpark', text.index('<h1')),
             ('the schematic', text.index('<figure class="dia">')),
             ('where the netting runs', text.index('id="netting"')),
             ('the distribution table', text.index('<table>')),
             ('the standing caveat',
              text.index('Model estimate, not observed data')),
             ('the Details disclosure',
              text.index('<details class="more"><summary>Details</summary>'))]
    for (before, a), (after, b) in zip(order, order[1:]):
        assert a < b, f'{slug}: {after} is above {before}'
    assert text.index('<section class="panel') > order[-1][1], \
        f'{slug}: a panel of working stands outside the Details disclosure'
    assert text.count('<details') == 1, \
        f'{slug}: more than one disclosure on the page'
    assert text.index('id="netting"') < text.index('id="netting-source"'), \
        f'{slug}: the netting sourcing is above the netting statement'
    # The caveat line is also the one link off the page, to where the caveat
    # is stated in full.
    assert re.search(r'Model estimate, not observed data\.</b> '
                     r'<a href="\.\./about/">How this works', text), \
        f'{slug}: the caveat line does not link to the explanatory page'


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_netting_state_is_stated_either_way(built, key):
    """A gap is stated as a gap, not left blank; a sourced extent names its
    source and the date it was read.

    Both halves are read off the sentence at the top of the page rather than
    off the page as a whole. Step 22 moved the netting statement above the
    fold and its sourcing below, and a gap stated only four screens down would
    satisfy a whole-page substring check while the top of the page still read
    as though the netting were known.
    """
    slug = PARK_SOURCES[key]['slug']
    text = built['pages'][slug]
    said = netting_sentence(text)
    stadium = STADIUMS[key]()
    join = join_park(stadium, key)
    if join.status == 'mapped':
        assert said.startswith(">Netting "), \
            f'{slug}: the sentence above the fold does not say where the net is'
        # Lead with the fact. Who published it, how many parks match and what
        # the club's coverage hedge says are all true, all on this page, and
        # none of them belongs in the sentence that answers the question.
        for word in ('publish', 'source', 'club', 'of the 31', 'matches'):
            assert word not in said.lower(), \
                f'{slug}: the netting sentence leads with "{word}", not the net'
        assert 'behind netting' in text
        assert join.park.source in text
        assert join.park.retrieved in text
    else:
        assert 'no area below is marked as behind netting' in said, \
            f'{slug}: gap not stated above the fold'
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
    assert 'At the other 24 it is a gap' in flat(built['pages']['about'])


def test_the_about_page_splits_gaps_by_whose_they_are(built):
    """The larger group of gaps is this project's own defects, and the page has
    to be built so that a reader sees that without reading the copy.

    `join.status` already draws the line — `join_gap` is a park whose club
    published something usable and whose *model* could not use it — and this
    test holds the page to it, including the claim that it is the larger of
    the two, which is the whole reason the split is worth making.

    The grouped listing was the home page's until Step 23 made the home page
    a gallery; it is on the explanatory page now, unchanged.
    """
    home = flat(built['pages']['about'])
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
        listed = set(re.findall(r'href="\.\./([^"]+)/"',
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
    assert '16 of the 31 parks have one' in flat(built['pages']['about'])


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
    assert 'twenty-seven of them disagreed' in flat(built['pages']['about'])


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
    `side_counts()`, so it cannot go stale in one place and not another.

    The limits used to be on every park page; since Step 23 they are stated
    once, on the explanatory page."""
    unnamed = site_build.side_counts()['unnamed']
    assert unnamed == sum(1 for p in built['parks'].values()
                          if not p['sides']['named'])
    text = flat(built['pages']['about'])
    assert f'at {unnamed} of the 31 parks nothing available establishes' \
        in text, 'stale or missing side count in the limits'


# ============================================================
# Constraint 3 — the word "safe" never appears
# ============================================================

# Word-bounded, so it catches safe/safer/safest/safety and does not fire on
# "SafecoField.html" — the filename of Clem's T-Mobile Park page, which is a
# real source URL and stays.
SAFE_WORD = re.compile(r'(?i)\bsafe(?:r|st|ty|ly|guard(?:ed|s)?)?\b')


@pytest.mark.parametrize('slug', ALL_PAGES)
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


@pytest.mark.parametrize('slug', ALL_PAGES)
def test_no_accuracy_claim_anywhere(built, slug):
    hit = ACCURACY_CLAIM.search(built['pages'][slug])
    assert hit is None, f'{slug or "home"}: accuracy language "{hit.group(0)}"'


def flat(text: str) -> str:
    """Collapse the line wrapping so prose assertions do not depend on it."""
    return re.sub(r'\s+', ' ', text)


@pytest.mark.parametrize('slug', sorted(s['slug'] for s in PARK_SOURCES.values()))
def test_every_park_page_says_it_was_never_validated(built, slug):
    """One short line on every park page, and the full statement one link
    away. The line is the shortest form that is still the caveat, and it is
    visible without opening anything — `test_park_page_word_budget` counts
    it in the sixty."""
    text = flat(built['pages'][slug])
    assert 'Model estimate, not observed data' in text     # visible
    assert 'a model estimate, not a count of anything observed' in text


def test_the_never_validated_caveat_is_stated_in_full_on_the_about_page(built):
    text = flat(built['pages']['about'])
    assert 'never been checked against a real foul ball' in text
    assert 'never been validated' in text
    assert 'never been compared' in text                  # the limits
    assert 'no page here puts a number on how often the model gets it right' \
        in text


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
# The schematic
# ============================================================
#
# The drawing above each distribution table is the one thing on this site that
# is not words or a right-aligned figure, so every claim it can make silently —
# a shade, a mark, a label, a size — is checked here rather than reviewed.

DIA_PATH = re.compile(r'<path class="([a-z0-9]+)" d="([^"]+)"')


def diagram(text: str) -> str:
    m = SCHEMATIC.search(text)
    assert m, 'no schematic on this page'
    return m.group(0)


def drawn_steps(text: str) -> set:
    """Which of the five shading steps this page's drawing actually uses."""
    return {int(cls[1:]) for cls, _ in DIA_PATH.findall(diagram(text))
            if re.fullmatch(r'z\d', cls)}


def zone_rows(p: dict) -> dict:
    return {z['id']: z for z in p['zones']}


def drawn_rows(p: dict):
    """Every (section id, row) pair the drawing puts ground on."""
    rows = zone_rows(p)
    for _, _, bands in site_diagram.wedges(p['stadium']):
        for sid, _, _ in bands:
            yield sid, site_diagram._row_for(sid, rows)


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_every_park_page_carries_a_schematic_above_its_table(built, key):
    slug = PARK_SOURCES[key]['slug']
    text = built['pages'][slug]
    assert text.index('<figure class="dia">') < text.index('<table>'), \
        f'{slug}: the schematic is not above the distribution table'
    assert 'Schematic, not to scale' in flat(diagram(text))
    assert 'role="img"' in text and 'aria-label="Schematic plan' in text


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_the_schematic_draws_every_area_the_table_lists(built, key):
    """A row with no ground on the drawing would read as an area that does not
    exist, and a shape with no row would be an area nobody can look up."""
    slug = PARK_SOURCES[key]['slug']
    p = built['parks'][slug]
    rows = zone_rows(p)
    covered = set()
    for sid, row in drawn_rows(p):
        assert row is not None, f'{slug}: {sid} is drawn with no row behind it'
        # Only the first-base half is computed; the third-base half is that
        # half mirrored, so a first-base wedge covers its counterpart row and
        # the folded row a pair may have become.
        covered |= {i for i in (sid, '3B-' + sid[3:], 'LINES-' + sid[3:])
                    if i in rows} if sid[:3] == '1B-' else {sid}
    assert covered == set(rows), \
        f'{slug}: the drawing and the table list different areas'


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_the_schematic_shades_from_the_figures_the_table_prints(built, key):
    """The invariant the whole drawing rests on.

    A shade that disagreed with the row under it would be worse than no
    drawing at all, because a reader has no way to check it. The steps the
    page emits have to be exactly the steps its own printed figures fall in.
    """
    slug = PARK_SOURCES[key]['slug']
    expected = {site_diagram.step_of(row['fouls'])
                for _, row in drawn_rows(built['parks'][slug])}
    assert drawn_steps(built['pages'][slug]) == expected, \
        f'{slug}: shaded from figures the table beneath it does not print'


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_the_schematic_shades_the_two_foul_lines_alike(built, key):
    """Every park here is built as an exact mirror, so a left-right difference
    in the drawing would be simulation noise presented as ground — and at the
    fifteen folded parks it would leak a side as well."""
    p = built['parks'][PARK_SOURCES[key]['slug']]
    rows = zone_rows(p)
    for z in p['zones']:
        if z['id'][:3] not in ('1B-', '3B-'):
            continue
        a = site_diagram._row_for('1B-' + z['id'][3:], rows)
        b = site_diagram._row_for('3B-' + z['id'][3:], rows)
        assert site_diagram.step_of(a['fouls']) \
            == site_diagram.step_of(b['fouls']), \
            f'{key}: the two foul lines would draw in different shades'


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_the_schematic_names_no_foul_line_where_nothing_establishes_one(
        built, key):
    """Constraint 5, in the one place on the page that is not prose."""
    slug = PARK_SOURCES[key]['slug']
    fig = diagram(built['pages'][slug])
    named = built['parks'][slug]['sides']['named']
    for word in ('First base', 'Third base'):
        assert (word in fig) is named, \
            f'{slug}: schematic labels "{word}" but sides-named is {named}'


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_the_schematic_marks_netting_only_where_it_is_sourced(built, key):
    """A mark means a club places those seats fully behind netting.

    No mark means no source, and the drawing has to say which of the two a
    reader is looking at rather than leaving an unmarked arc to be read as an
    open one.
    """
    slug = PARK_SOURCES[key]['slug']
    p = built['parks'][slug]
    fig = diagram(built['pages'][slug])
    marked = 'class="nm" d=' in fig
    netted = any(row['status'] == 'netted' for _, row in drawn_rows(p))
    assert marked == netted, f'{slug}: netting mark does not match the sources'
    if p['net']['state'] != 'mapped':
        assert not marked, f'{slug}: netting marked at a park with no join'
    if not marked:
        assert 'No netting is marked here' in flat(fig)
        assert 'a missing source, not a missing net' in flat(fig)


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_the_schematic_emits_no_negative_coordinate(built, key):
    """`_n` clamps, and this is why.

    A minus sign between two path coordinates is indistinguishable from a
    printed seat range to `test_no_section_numbers_on_any_park_page`, so a
    regression here would surface as a baffling failure in a test about
    something else. It surfaces here instead.
    """
    fig = diagram(built['pages'][PARK_SOURCES[key]['slug']])
    for _, d in DIA_PATH.findall(fig):
        assert '-' not in d, f'{key}: negative coordinate in path data'


def test_two_parks_with_different_foul_territory_draw_differently(built):
    """The drawing responds to the sourced figures, or it is decoration.

    Every park shares one generic bowl and one viewBox, so the only thing that
    can separate two drawings is what `stadium.py` did to the radii with the
    park's published foul-territory area and backstop. Wrigley has the
    smallest foul ground in the registry and Rogers Centre the largest; they
    must not come out the same size, and no two parks may come out identical.
    """
    geom = {key: site_diagram.wedges(built['parks'][
                PARK_SOURCES[key]['slug']]['stadium'])
            for key in STADIUMS}
    outer = {k: max(b1 for _, _, bands in w for _, _, b1 in bands)
             for k, w in geom.items()}
    assert outer['wrigley_field'] < outer['rogers_centre'], \
        'the park with more published foul ground does not draw larger'
    shapes = [repr(w) for w in geom.values()]
    assert len(set(shapes)) == len(shapes), \
        'two parks produce identical drawings'


def test_the_step_legend_matches_the_step_boundaries(built):
    """The legend is the only thing telling a reader what a shade is worth, so
    it is generated from `STEPS` rather than written out beside them."""
    assert len(site_diagram.STEP_WORDS) == len(site_diagram.STEPS) + 1
    fig = flat(diagram(built['pages']['fenway-park']))
    for word in site_diagram.STEP_WORDS:
        assert word in fig
    assert site_diagram.step_of(0.9) == 0 and site_diagram.step_of(1.0) == 1
    assert site_diagram.step_of(3.99) == 3 and site_diagram.step_of(4.0) == 4


def test_the_shading_uses_every_step_somewhere_and_none_at_only_one_park(built):
    """Five steps that only ever resolve to two would be four steps of
    decoration and one of meaning. Each has to earn its place on the ramp."""
    used = {}
    for key in STADIUMS:
        for step in drawn_steps(built['pages'][PARK_SOURCES[key]['slug']]):
            used[step] = used.get(step, 0) + 1
    assert sorted(used) == [0, 1, 2, 3, 4], f'unused shading step: {used}'
    assert min(used.values()) > 1, f'a step reached by one park only: {used}'

# ============================================================
# The word budgets, and the shape of the three kinds of page — Step 23
# ============================================================
#
# Three passes trimmed and rearranged the prose and the site still read as a
# methods document. The fix was not a fourth edit to the copy but a budget on
# it, enforced here: the pages are built around the drawings, and the words
# that stay visible on them are counted. Everything that came off the pages
# went to /about/ or behind the one Details disclosure, and that is checked
# too — a budget met by deleting something honest would be worse than no
# budget.

HOME_BUDGET = 40      # words of prose outside the tiles
PARK_BUDGET = 60      # words visible without opening anything, less the
                      # table and the drawing's own labels

# A word is a run of characters that starts with a letter or a digit. The
# middle dots and the arrow in the caveat line are not words; "31" is.
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’.\-]*")
HEAD = re.compile(r'<style>.*?</style>|<title>.*?</title>|<meta[^>]*>', re.S)
TABLE = re.compile(r'<table>.*?</table>', re.S)
TILES = re.compile(r'<ul class="grid">.*?</ul>', re.S)
# The body of the disclosure goes; its one-word summary stays, because it is
# visible.
DETAILS_BODY = re.compile(
    r'(<details class="more"><summary>.*?</summary>).*?</details>', re.S)


def visible_words(text: str, *drop: re.Pattern) -> list[str]:
    """The words a reader sees on the page with nothing opened, less the
    parts of the page the patterns in `drop` describe."""
    text = HEAD.sub(' ', text)
    for pat in drop:
        text = pat.sub(lambda m: m.group(1) if m.groups() else ' ', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    return WORD.findall(html.unescape(text))


def test_home_page_word_budget(built):
    words = visible_words(built['pages'][''], TILES)
    assert len(words) <= HOME_BUDGET, \
        f'{len(words)} words outside the tiles: {" ".join(words)}'


@pytest.mark.parametrize('slug', PARK_SLUGS)
def test_park_page_word_budget(built, slug):
    words = visible_words(built['pages'][slug], DETAILS_BODY, SCHEMATIC, TABLE)
    assert len(words) <= PARK_BUDGET, \
        f'{slug}: {len(words)} words visible: {" ".join(words)}'


def test_the_home_page_is_a_gallery_and_nothing_else(built):
    """A grid of 31 tiles, each the park's own drawing with its name and its
    team, the whole tile a link; above it one headline and one sentence."""
    home = built['pages']['']
    parks = built['parks']
    grid = TILES.search(home).group(0)
    tiles = re.findall(
        r'<li><a href="([^"]+)/"><figure class="dia mini">'
        r'(<svg class="mini" .*?</svg>)</figure>'
        r'<span class="tn">(.*?)</span><span class="tt">(.*?)</span></a></li>',
        grid, re.S)
    assert len(tiles) == 31
    assert [slug for slug, _, _, _ in tiles] \
        == sorted(parks, key=lambda s: parks[s]['name']), \
        'the tiles are not in alphabetical order'
    for slug, svg, name, team in tiles:
        assert html.unescape(name) == parks[slug]['name']
        assert html.unescape(team) == parks[slug]['team']
        # The tile is the park page's drawing, path for path, at the shared
        # scale — so the grid is a comparison and not a set of icons.
        assert DIA_PATH.findall(svg) \
            == DIA_PATH.findall(diagram(built['pages'][slug])), \
            f'{slug}: the tile is not the same drawing as the park page'
        assert '<text' not in svg and 'aria-hidden="true"' in svg

    rest = TILES.sub(' ', home)
    assert rest.count('<h1') == 1
    assert rest.count('<p') == 3, 'wordmark, one sentence, one link'
    for tag in ('<h2', '<h3', '<table', '<section', '<details', '<ol', '<ul',
                '<figure'):
        assert tag not in rest, f'{tag} on the home page outside the tiles'


@pytest.mark.parametrize('slug', PARK_SLUGS)
def test_park_specific_detail_is_behind_the_details_disclosure(built, slug):
    """Everything about this park that is not the drawing, the sentence, the
    table or the caveat is one click down, and all of it is still there."""
    text = built['pages'][slug]
    inside = text[text.index('<details class="more">'):text.index('</details>')]
    for anchor in ('netting-source', 'model', 'readings', 'figures', 'labels'):
        assert f'id="{anchor}"' in inside, \
            f'{slug}: the {anchor} section is not inside Details'
    assert re.search(r'rebuilt \d{4}-\d{2}-\d{2}', inside), \
        f'{slug}: the build date is not on the page'

    outside = SCHEMATIC.sub(' ', DETAILS_BODY.sub(lambda m: m.group(1), text))
    assert outside.count('<p') == 4, \
        f'{slug}: wordmark, team, netting sentence, caveat — and nothing else'
    for tag in ('<section', '<h2', '<h3', '<ol', '<ul', '<div'):
        assert tag not in outside, f'{slug}: {tag} outside Details'


def test_the_about_page_holds_every_explanation(built):
    """Nothing honest was deleted; it moved here. Each explanation the site
    used to carry on the home page or on every park page is on this page,
    under its own anchor."""
    about = flat(built['pages']['about'])
    for anchor in ('validation', 'sourced', 'netting-words', 'parks', 'sides',
                   'numbers', 'diagram', 'readings', 'method', 'limits',
                   'sources'):
        assert f'id="{anchor}"' in about, f'about page has no {anchor} section'
    for heading, _ in MODEL_LIMITS:
        assert flat(html.escape(heading, quote=True)) in about, \
            f'about page is missing the limit "{heading}"'
    assert flat(site_build.NETTING_CLUB_CAVEAT) in about
    assert 'not to scale and not a seating chart' in about
    assert 'No mark is not no net' in about
    assert 'No figure on this site is ever drawn as a length' in about
    assert 'simulations per batter, fixed seed' in about
    assert 'is not affiliated with Major League Baseball' in about
    assert 'nothing on it will keep a ball from reaching you' in about


@pytest.mark.parametrize('slug', PARK_SLUGS + [''])
def test_every_page_links_to_the_about_page(built, slug):
    href = '../about/' if slug else 'about/'
    assert f'<a href="{href}">How this works' in built['pages'][slug], \
        f'{slug or "home"}: no link to the explanatory page'


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
    assert len(titles) == 33
    assert len(descs) == 33


@pytest.mark.parametrize('slug', ALL_PAGES)
def test_pages_are_mobile_first_and_self_contained(built, slug):
    text = built['pages'][slug]
    assert 'name="viewport"' in text and 'width=device-width' in text
    # One request per page: no scripts, no images, no external stylesheets.
    assert '<script' not in text
    assert '<img' not in text
    assert 'rel="stylesheet"' not in text
    # A budget, not a claim. It was 40 KB against a 32.4 KB worst page until
    # Step 21 put an inline SVG schematic on every park page, which cost the
    # heaviest park (Yankee Stadium, 21 drawn wedges) about 5.8 KB — path data,
    # the legend, and the alt text. The ceiling moved by what the drawing cost
    # plus the headroom the old one carried, and not by a byte more, so it
    # still catches drift. Raising it again should mean the same kind of
    # deliberate addition, not room for prose.
    #
    # Step 23 made the home page a gallery of all 31 drawings, which is 31
    # times the path data on one page; it gets its own ceiling, set the same
    # way — what the tiles cost (about 45 KB) plus the old headroom.
    ceiling = 90_000 if slug == '' else 46_000
    assert len(text.encode('utf-8')) < ceiling, 'page is getting heavy'


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
    with open(out / 'sitemap.xml', encoding='utf-8') as fh:
        sitemap = fh.read()
    assert sitemap.count('<loc>') == 33
    assert '<loc>https://example.test/about/</loc>' in sitemap


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
    assert b'<h1>Fenway Park</h1>' in park.data

    about = client.get('/parks/about/')
    assert about.status_code == 200
    assert b'<h1>How this works</h1>' in about.data


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
    assert body.count('<loc>') == 33
    assert 'http://localhost/parks/fenway-park/' in body
    assert 'http://localhost/parks/about/' in body
