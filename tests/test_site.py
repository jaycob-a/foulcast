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
   say fans behind netting remain exposed; this model has been tested against
   real foul balls only in four broad bands. Neither supports the word.
4. **No accuracy claims**, and the one test the model has had stated on every
   page in one line, no more and no less than it found.

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

Step 26 replaced the per-area netting marks with the club's own sentence,
quoted, and made the one exception constraint 1 has: a section number may
appear inside a quotation from the club (`<q class="quote">`,
`<blockquote class="quote">`) and nowhere else. The section-number checks
strip exactly those elements first, and `test_club_quotes_are_the_clubs_words`
holds everything inside them to the club's text, so the exception cannot be
used to carry anything of this site's own. The same step put bands in the
table where figures to a tenth of a ball used to be, added a line under the
table at the 27 parks whose own map disagrees with the model, dated the pages
by when the model ran rather than when they were rendered, and fixed three
factual errors, each with its own test below.

Step 30 rebuilt the park pages around what has been tested. FiveThirtyEight's
906 foul balls, folded into four bands by distance along the foul line, are
the only real data this model has been compared with, so the drawing and the
table above the fold are those four bands, with the observed share beside the
model's; the seating areas and decks went under Details, labelled as untested.
The old "never checked against a real foul ball" copy was replaced everywhere
with what the test found, and the tests that pinned the old layout and wording
pin the new ones.

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
import math
import os
import re
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from foulball.stadium import STADIUMS, PARK_PARAMS, exposed_bands
from foulball.seat_map import build_printed_index, printed_range_display
import site_build
import site_diagram
from site_data import (
    PARK_SOURCES, ZONE_WORDS, MAP_READS, NO_MAP_READ, SIDE_STATE_WORDS,
    MODEL_LIMITS, CLUB_NETTING, VALIDATION_SHARES,
)
# Constraints 3 and 4 as patterns. They are in `tests/conftest.py` because
# `tests/test_endpoints.py` holds every public URL to the same two, and one
# rule with two definitions is two rules.
from tests.conftest import ACCURACY_CLAIM, SAFE_WORD

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
                   'into_seats': 1.0, 'total_fouls': 2.0, 'unmatched': 1.0,
                   'run_on': '2026-01-01',
                   'bands': {'Z1': 1.0, 'Z23': 0.5, 'Z45': 0.5, 'Z67': 0.0}}
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
    undated = sorted(k for k, e in cache.items() if not e.get('run_on'))
    assert not undated, f'cached runs that do not say when they ran: {undated}'


def test_the_committed_site_matches_a_fresh_render(tmp_path):
    """The hole that let `site/` sit five commits behind its own generator.

    Rendered from the committed cache rather than simulated, so this takes a
    second rather than eight minutes: the cache is checked against the model by
    `test_the_committed_cache_came_from_the_current_model`, and the pages are
    checked against the cache here, byte for byte.

    Byte for byte with nothing normalised out, since Step 26. This used to
    blank a "rebuilt <date>" line first, because the pages printed the day
    they were rendered and so changed every time anyone rendered them — which
    meant the date could drift forever without this test noticing. The pages
    now print the date the model run itself carries, and a render reproduces
    them exactly.
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
            new = fh.read()
        with open(os.path.join(COMMITTED_SITE, rel), encoding='utf-8') as fh:
            old = fh.read()
        if new != old:
            stale.append(rel)
    assert not stale, (f'{len(stale)} committed page(s) differ from a fresh '
                       f'render, starting with {stale[0]}; rebuild with '
                       f'`python site_build.py` and commit site/')


ISO_DATE = re.compile(r'\b\d{4}-\d{2}-\d{2}\b')


def test_the_pages_are_dated_by_the_model_run_not_the_render(tmp_path):
    """Step 26: "Model figures rebuilt <today>" said the figures were made the
    day the HTML was rendered. They were made when the simulation ran, which
    the audit found had been six weeks earlier.

    So the committed cache is rendered here with every entry's `run_on`
    rewritten to a date nobody could mistake for today, and the pages have to
    print that date — and no date at all that is not one of the dated sources
    this site names.
    """
    if not os.path.exists(COMMITTED_CACHE):
        pytest.skip('no committed model cache in this checkout')
    with open(COMMITTED_CACHE, encoding='utf-8') as fh:
        cache = json.load(fh)
    for entry in cache.values():
        entry['run_on'] = '2001-02-03'
    fake = tmp_path / 'park_stats.json'
    with open(fake, 'w', encoding='utf-8') as fh:
        json.dump(cache, fh)

    out = tmp_path / 'site'
    site_build.build(str(out), base_url='', sims=site_build.SIMS,
                     no_model=True, cache_path=str(fake))

    from site_data import (CLUB_NETTING_READ, RESEARCH_DATE, MAP_READ_DATE,
                           LATER_READ_DATE)
    named = {'2001-02-03', CLUB_NETTING_READ, RESEARCH_DATE, MAP_READ_DATE,
             LATER_READ_DATE} | {mr.get('read_on', MAP_READ_DATE)
                                 for mr in MAP_READS.values()}
    for rel in ('fenway-park', 'wrigley-field', 'about'):
        with open(out / rel / 'index.html', encoding='utf-8') as fh:
            text = flat(fh.read())
        assert 'Model run on 2001-02-03' in text, \
            f'{rel}: the page does not carry the date the model ran'
        assert 'rebuilt' not in text, f'{rel}: still dated by its render'
        stray = set(ISO_DATE.findall(text)) - named
        assert not stray, f'{rel}: dates no source accounts for: {stray}'


def test_a_cache_entry_that_cannot_say_when_it_ran_is_re_simulated(
        tmp_path, monkeypatch):
    """The date on the page comes from the entry, so an entry without one is
    not reused — it would have to be dated by guesswork."""
    cache = tmp_path / 'park_stats.json'
    _fake_cache(cache, site_build.model_fingerprint(), TEST_SIMS)
    with open(cache, encoding='utf-8') as fh:
        entries = json.load(fh)
    for entry in entries.values():
        entry['run_on'] = '2026-01-01'
    del entries['fenway_park']['run_on']
    with open(cache, 'w', encoding='utf-8') as fh:
        json.dump(entries, fh)

    ran = []

    def fake_run(key, sims, fingerprint=None):
        ran.append(key)
        return {'park': key, 'sims': sims, 'model': fingerprint,
                'run_on': '2026-01-02'}

    monkeypatch.setattr(site_build, 'run_park', fake_run)
    site_build.load_stats(refresh=False, sims=TEST_SIMS, cache_path=str(cache))
    assert ran == ['fenway_park']


def test_a_cache_entry_without_the_four_bands_is_re_simulated(
        tmp_path, monkeypatch):
    """Step 30: the page's main table is built from each entry's `bands`, and
    an entry made before them cannot supply it, however current its model."""
    cache = tmp_path / 'park_stats.json'
    _fake_cache(cache, site_build.model_fingerprint(), TEST_SIMS)
    with open(cache, encoding='utf-8') as fh:
        entries = json.load(fh)
    del entries['wrigley_field']['bands']
    with open(cache, 'w', encoding='utf-8') as fh:
        json.dump(entries, fh)

    ran = []

    def fake_run(key, sims, fingerprint=None):
        ran.append(key)
        return {'park': key, 'sims': sims, 'model': fingerprint}

    monkeypatch.setattr(site_build, 'run_park', fake_run)
    site_build.load_stats(refresh=False, sims=TEST_SIMS, cache_path=str(cache))
    assert ran == ['wrigley_field']


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
# A quotation from the club: the one place a section number may appear.
# `test_club_quotes_are_the_clubs_words` holds what is inside to the club's
# text, which is what makes stripping it here safe.
CLUB_QUOTE = re.compile(r'<q class="quote">(.*?)</q>'
                        r'|<blockquote class="quote">(.*?)</blockquote>', re.S)


def _without_club_quotes(text: str) -> str:
    return CLUB_QUOTE.sub(' ', text)


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
    text = _without_club_quotes(built['pages'][slug])
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
    text = _without_club_quotes(built['pages'][slug])
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
    text = _strip_numeric_prose(_without_club_quotes(built['pages'][slug]))
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
    model = text.index('id="model"')
    assert net < zones < model, f'{slug}: model output is above the netting'


def netting_sentence(text: str) -> str:
    """The one sentence above the fold that says where the net is."""
    assert 'id="netting"' in text, 'no netting statement on this page'
    return text.split('id="netting">')[1].split('</p>')[0]


@pytest.mark.parametrize('slug', sorted(s['slug'] for s in PARK_SOURCES.values()))
def test_the_answer_stands_above_everything_that_qualifies_it(built, slug):
    """Step 22, tightened by Steps 23 and 26. The things on the visible page,
    in this order, and nothing else.

    Two passes before Step 22 shortened the copy at the top of a park page
    and it still opened with three paragraphs of caveats, because the problem
    was never length: the page was organised around this project's
    epistemology instead of around the reader's question. So the order is
    enforced here rather than trusted, including the two things that would
    slide back up first — a panel of working above the table, and the standing
    caveat above the drawing it does not qualify. Step 23 put every panel of
    working behind one closed Details disclosure under the caveat, and that
    is enforced here too. Step 26 added one line between the table and the
    caveat at the parks whose own map disagrees with the model; Step 30 moved
    it under Details with the seating areas it is about, and made the caveat
    the one line saying what the test against real fouls found.
    """
    text = built['pages'][slug]
    order = [('the ballpark', text.index('<h1')),
             ('the schematic', text.index('<figure class="dia">')),
             ('where the netting runs', text.index('id="netting"')),
             ('the distribution table', text.index('<table>')),
             ('the line on the test', text.index(site_build.TESTED_LINE)),
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
    # The line on the test is also the link to where the test is reported.
    assert (f'{site_build.TESTED_LINE} <a href="../about/#validation">'
            f'Results &rarr;</a>') in text, \
        f'{slug}: the line on the test does not link to the full results'


# ------------------------------------------------------------
# Step 26: the club's own words, instead of marks on this model's seats
# ------------------------------------------------------------

SOURCED_DATA = os.path.join(REPO, 'SOURCED_DATA.md')


def _record_text() -> str:
    """`SOURCED_DATA.md` as running text: quote markers and wrapping gone."""
    with open(SOURCED_DATA, encoding='utf-8') as fh:
        lines = [re.sub(r'^>\s?', '', ln) for ln in fh.read().splitlines()]
    return re.sub(r'\s+', ' ', ' '.join(lines))


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_the_netting_sentence_quotes_the_club_and_links_to_it(built, key):
    """One sentence per park: the club's own words, and the club's page.

    The sentence is this park's `CLUB_NETTING` line with its quotations in
    place, and nothing else — so a reader sees what the club said rather than
    this site's reading of it onto seat labels the parks' own maps say are in
    the wrong place. Every park links to the page it quotes, including the
    parks where that page says nothing usable, so a reader can check that too.
    """
    slug = PARK_SOURCES[key]['slug']
    club = CLUB_NETTING[key]
    said = netting_sentence(built['pages'][slug])
    quoted = [html.unescape(q) for q in
              re.findall(r'<q class="quote">(.*?)</q>', said, re.S)]
    assert quoted == list(club['quotes']), \
        f'{slug}: the sentence does not quote the club as recorded'
    assert f'href="{html.escape(club["page"], quote=True)}"' in said, \
        f'{slug}: the sentence does not link to the club page it quotes'
    if club['kind'] in ('states', 'conflicts', 'declines'):
        assert quoted, f'{slug}: the club published words and none are quoted'
    words = html.unescape(re.sub(r'<[^>]+>', '', CLUB_QUOTE.sub('', said)))
    assert 'behind netting' not in words and 'not verified' not in words, \
        f'{slug}: the sentence still reads the netting onto seats'


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_club_quotes_are_the_clubs_words(built, key):
    """The exception to constraint 1 cannot carry anything of this site's.

    Inside a quotation element a section number is allowed, so everything
    inside one has to be the club's: each inline quotation is one of this
    park's recorded quotations, each paragraph of the long quotation under
    Details is one of its recorded paragraphs, every quotation is part of the
    club's recorded statement, and every recorded paragraph is written out in
    `SOURCED_DATA.md` Part 2b, which is the dated record of the read.
    """
    slug = PARK_SOURCES[key]['slug']
    club = CLUB_NETTING[key]
    text = built['pages'][slug]
    for inline, block in CLUB_QUOTE.findall(text):
        if inline:
            assert html.unescape(inline) in club['quotes'], \
                f'{slug}: a quotation the club did not make: {inline[:60]!r}'
        else:
            paras = [html.unescape(x) for x in
                     re.findall(r'<p>(.*?)</p>', block, re.S)]
            assert paras == list(club['full']), \
                f'{slug}: the long quotation is not the club\'s statement'
            assert re.sub(r'<p>.*?</p>', '', block, flags=re.S) == '', \
                f'{slug}: something other than the club\'s words is inside it'
    whole = ' '.join(club['full'])
    for q in club['quotes']:
        assert q in whole, f'{slug}: {q[:60]!r} is not in the club\'s statement'
    record = _record_text()
    for para in club['full']:
        assert re.sub(r'\s+', ' ', para) in record, \
            f'{slug}: {para[:60]!r} is not in SOURCED_DATA.md Part 2b'


def test_wrigley_and_comerica_quote_the_club(built):
    """Both were filed under "nothing usable is published" (`LIMITATIONS.md`
    3.5). The Cubs say where their netting runs, in words; the Tigers give
    both ends of it. Both pages now quote them, and both parks are in the
    group of clubs that say where their netting runs."""
    for key, words in (('wrigley_field', 'outfield edge of each dugout'),
                       ('comerica_park', 'through section 116')):
        slug = PARK_SOURCES[key]['slug']
        said = netting_sentence(built['pages'][slug])
        assert '<q class="quote">' in said and words in said, \
            f'{slug}: the club\'s own words are not above the table'
        assert 'Nothing published' not in said
        assert CLUB_NETTING[key]['kind'] == 'states'
    about = flat(built['pages']['about'])
    states = about.split('The club says where its netting runs')[1] \
                  .split('</ul>')[0]
    for slug in ('wrigley-field', 'comerica-park'):
        assert f'href="../{slug}/"' in states, \
            f'{slug} is not listed among the clubs that say where it runs'


@pytest.mark.parametrize('slug', PARK_SLUGS)
def test_no_page_marks_an_area_behind_or_outside_netting(built, slug):
    """The per-area netting marks are gone, and so is everything built on them.

    They were this model's seat labels read against the club's numbers, and
    the parks' own seating maps put those labels in the wrong place at 27 of
    30 parks. The red "not behind netting" was worse — an inference from
    silence, printed in the site's loudest colour. None of the words, tags or
    drawing marks that carried them may come back, and every page still
    carries the clubs' own warning that netting is not protection.
    """
    text = built['pages'][slug]
    for gone in ('not behind netting', 'partly netted', 'netting not verified',
                 'differs by foul line', 'tag-open', 'tag-part', 'class="nm"',
                 'If you want to catch a ball', 'id="readings"'):
        assert gone not in text, f'{slug}: "{gone}" is back on the page'
    assert flat(site_build.NETTING_CLUB_CAVEAT) in flat(text), \
        f'{slug}: the clubs\' own warning is missing'


def test_the_about_page_groups_parks_by_what_the_club_says(built):
    """Three groups, read off `CLUB_NETTING`, each listing exactly its own
    parks: the clubs that say where their netting runs, the one whose page
    contradicts itself, and the ones whose pages say nothing usable."""
    about = flat(built['pages']['about'])
    seen = []
    for kinds, heading, _ in site_build.NETTING_GROUPS:
        members = {p['slug'] for p in built['parks'].values()
                   if p['club']['kind'] in kinds}
        marked = (f'{flat(heading.replace(chr(39), "&#x27;"))} '
                  f'<span class="sub">({len(members)})</span>')
        if marked not in about:
            marked = f'{heading} <span class="sub">({len(members)})</span>'
        assert marked in about, f'about page is missing the {kinds} group'
        listed = set(re.findall(r'href="\.\./([^"]+)/"',
                                about.split(marked)[1].split('</ul>')[0]))
        assert listed == members, f'{kinds} group does not list its own parks'
        seen += sorted(members)
    assert sorted(seen) == PARK_SLUGS, 'a park is in no group, or in two'
    counts = {k: sum(1 for c in CLUB_NETTING.values() if c['kind'] == k)
              for k in ('states', 'conflicts', 'declines', 'silent')}
    assert counts == {'states': 25, 'conflicts': 1, 'declines': 1, 'silent': 4}


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

@pytest.mark.parametrize('slug', ALL_PAGES)
def test_the_word_safe_never_appears(built, slug):
    hit = SAFE_WORD.search(built['pages'][slug])
    assert hit is None, f'{slug or "home"}: "{hit.group(0)}" at {hit.start()}'


# ============================================================
# Constraint 4 — no accuracy claims
# ============================================================

@pytest.mark.parametrize('slug', ALL_PAGES)
def test_no_accuracy_claim_anywhere(built, slug):
    hit = ACCURACY_CLAIM.search(built['pages'][slug])
    assert hit is None, f'{slug or "home"}: accuracy language "{hit.group(0)}"'


def flat(text: str) -> str:
    """Collapse the line wrapping so prose assertions do not depend on it."""
    return re.sub(r'\s+', ' ', text)


# What the test found, in the words every park page uses. Each clause is one
# finding of `VALIDATION.md` and `CALIBRATION.md`, and none may be dropped:
# a line that kept the first and lost the last would be an accuracy claim.
TEST_FINDINGS = ('Tested once against FiveThirtyEight',
                 'gets the general shape roughly right',
                 'slightly too few fouls far down the lines',
                 'does not reliably tell parks apart')

# What the site said before Steps 28 and 29, and may not say again: the model
# has been checked against real fouls, and the back-foul rate is calibrated.
RETIRED_COPY = ('never been checked against a real foul',
                'never checked against real fouls',
                'No foul ball has ever been checked against it',
                'has never seen a real foul ball',
                'nothing on this site has ever checked',
                'nothing has ever checked it',
                'never been validated',
                'is a guess')


@pytest.mark.parametrize('slug', sorted(s['slug'] for s in PARK_SOURCES.values()))
def test_every_park_page_says_what_the_test_found(built, slug):
    """One short line on every park page, and the full results one link
    away. It is visible without opening anything —
    `test_park_page_word_budget` counts it in the sixty — and the seating-area
    figures under Details still say what they are."""
    text = flat(built['pages'][slug])
    outside = text[:text.index('<details')]
    for clause in TEST_FINDINGS:
        assert clause in outside.replace('&#x27;', "'"), \
            f'{slug}: the line on the test has lost "{clause}"'
    assert 'href="../about/#validation"' in outside
    assert 'a model estimate, not a count of anything observed' in text


@pytest.mark.parametrize('slug', ALL_PAGES)
def test_no_page_says_the_model_was_never_checked(built, slug):
    """Step 30: "never checked against a real foul ball" stopped being true
    when Step 28 compared the model with FiveThirtyEight's count, and "the
    rate of balls hit straight back is a guess" when Step 29 calibrated it."""
    text = flat(built['pages'][slug])
    for gone in RETIRED_COPY:
        assert gone not in text, f'{slug or "home"}: "{gone}" is back'


def test_the_test_is_reported_in_full_on_the_about_page(built):
    text = flat(built['pages']['about']).replace('&#x27;', "'")
    section = text.split('id="validation"')[1].split('<h2')[0]
    assert 'The model has been tested once against real foul balls' in section
    for clause in ('tested once against FiveThirtyEight',
                   'gets the general shape roughly right',
                   'slightly too few fouls far down the lines',
                   'does not reliably tell parks apart'):
        assert clause in section, f'the about page has lost "{clause}"'
    # The fit, and why the in-sample figures are not the measure of it.
    assert 'calibrated to these same fouls' in section
    assert 'predict the eighth' in section
    assert 'Anything finer than the four bands' in section
    assert 'No seating area, deck or section' in section
    assert 'no page here puts a single number on how often the model' \
        in section.lower()
    # The table of results, as `CALIBRATION.md` records them.
    for _, vals in VALIDATION_SHARES:
        row = ''.join(f'<td class="n">{v:.0f}%</td>' for v in vals)
        assert row in section, f'the results table is missing {row}'
    limits = dict(MODEL_LIMITS)
    assert 'It has been tested once, and only coarsely' in limits
    assert 'The rate of balls hit straight back is fitted to one sample' \
        in limits


def test_the_results_on_the_about_page_are_calibration_md_s():
    """`VALIDATION_SHARES` is copied from `CALIBRATION.md`, because the site
    build does not repeat the fit; this holds the copy to the record."""
    with open(os.path.join(REPO, 'CALIBRATION.md'), encoding='utf-8') as fh:
        record = fh.read().split('### Pooled over the eight parks')[1]
    rows = {}
    for label in ('**Observed, all 710**', '**Held-out model**',
                  'Original model (0.28)'):
        line = next(ln for ln in record.splitlines()
                    if ln.startswith(f'| {label} |'))
        rows[label] = [float(c.strip().rstrip('%'))
                       for c in line.split('|')[2:6]]
    for i, (_, vals) in enumerate(VALIDATION_SHARES):
        assert vals == (rows['**Observed, all 710**'][i],
                        rows['**Held-out model**'][i],
                        rows['Original model (0.28)'][i])


@pytest.mark.parametrize('slug', sorted(s['slug'] for s in PARK_SOURCES.values()))
def test_every_park_page_states_its_unmatched_share(built, slug):
    """The share of fouls the model drops is on the page, not hidden."""
    assert 'land where it has no seating area' in flat(built['pages'][slug])


# ============================================================
# The schematic
# ============================================================
#
# The drawing above each distribution table is the one thing on this site that
# is not words or a right-aligned figure, so every claim it can make silently —
# a shade, a mark, a label, a size — is checked here rather than reviewed.

DIA_PATH = re.compile(r'<path class="([a-z0-9]+)" d="([^"]+)"')
SEATS = re.compile(r'<mask id="([^"]+)"><path d="([^"]+)"/></mask>')


def diagram(text: str) -> str:
    m = SCHEMATIC.search(text)
    assert m, 'no schematic on this page'
    return m.group(0)


def drawn_shades(text: str) -> list[int]:
    """The shade of each band the drawing puts on the page, in order."""
    return [int(cls[1:]) for cls, _ in DIA_PATH.findall(diagram(text))
            if re.fullmatch(r'z\d', cls)]


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_every_park_page_carries_a_schematic_above_its_table(built, key):
    slug = PARK_SOURCES[key]['slug']
    text = built['pages'][slug]
    assert text.index('<figure class="dia">') < text.index('<table>'), \
        f'{slug}: the schematic is not above the distribution table'
    assert 'Schematic, not to scale' in flat(diagram(text))
    assert 'role="img"' in text and 'aria-label="Schematic plan' in text


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_the_schematic_draws_the_seating_and_the_bands_the_table_lists(
        built, key):
    """Step 30: the drawing is the four bands, not the seating areas.

    The seating is one outline, the park's own drawn seats with the decks
    folded together, and every band the table lists is drawn across it if
    any drawn seat lies in it. At every park that is the first three: no drawn
    seat reaches a foul pole, so the band past the pole is in the table and
    not on the drawing, and its row carries no swatch.
    """
    slug = PARK_SOURCES[key]['slug']
    p = built['parks'][slug]
    fig = diagram(built['pages'][slug])
    masks = SEATS.findall(fig)
    assert len(masks) == 1, f'{slug}: the seating is not one outline'
    uid, seats = masks[0]
    assert seats == site_diagram.footprint(p['stadium'])
    assert uid == f'{slug}-seats' and f'mask="url(#{uid})"' in fig
    assert [b['key'] for b in p['bands']] == [k for k, _ in site_diagram.BANDS]
    assert [b['key'] for b in p['bands'] if b['drawn']] == ['Z1', 'Z23', 'Z45']
    assert len(drawn_shades(built['pages'][slug])) == 3
    # No class on the outline: nothing in it may carry a seating area's id.
    assert 'section' not in fig and 'LB' not in fig


def test_the_seating_outline_folds_the_decks_together():
    """A deck boundary inside a band would be a line between two things
    nothing has tested, so the outline has one ring per wedge wherever the
    decks touch: never more pieces than the old area-by-area drawing had, and
    far fewer across the fleet."""
    rings_all = pieces_all = 0
    for key in STADIUMS:
        stadium = STADIUMS[key]()
        rings = site_diagram.footprint(stadium).count('M')
        # The old drawing: one piece per deck per wedge, on both sides of the
        # plate, except a piece reaching straight back, drawn once.
        pieces = sum(len(bands) * (1 if a1 >= 90.0 else 2)
                     for _, a1, bands in site_diagram.wedges(stadium))
        assert rings <= pieces, f'{key}: the outline has extra pieces'
        rings_all, pieces_all = rings_all + rings, pieces_all + pieces
    assert rings_all < 0.7 * pieces_all, 'the decks are still drawn one by one'


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_the_schematic_shades_by_the_shares_the_table_prints(built, key):
    """The invariant the whole drawing rests on: a band's shade is where the
    share the table prints for it falls against the busiest band here, and
    the table's swatch for the band is the same shade."""
    slug = PARK_SOURCES[key]['slug']
    p = built['parks'][slug]
    top = max(b['share'] for b in p['bands'])
    for b in p['bands']:
        assert b['shade'] == site_diagram.shade_of(b['share'], top)
    assert drawn_shades(built['pages'][slug]) \
        == [b['shade'] for b in p['bands'] if b['drawn']], \
        f'{slug}: shaded in shades the table beside it does not give'
    assert max(b['shade'] for b in p['bands']) == 3

    table = TABLE.search(built['pages'][slug]).group(0)
    labels = re.findall(r'<td class="k">(.*?)</td>', table, re.S)
    assert len(labels) == 4
    for b, cell in zip(p['bands'], labels):
        if b['drawn']:
            assert f'<i class="z{b["shade"]}"></i>' in cell, \
                f'{slug}: {b["key"]}\'s swatch is not its shade'
        else:
            assert '<i class="nil"></i>' in cell and 'class="z' not in cell


def _mirrored(d: str, w: float) -> bool:
    """Whether every point of a path has its mirror image in the same path,
    to within the foot the drawing rounds to."""
    pts = [(float(x), float(y)) for x, y in
           re.findall(r'(?<![\d.])([\d.]+) ([\d.]+)(?=[LAZM]|$)', d)]
    return all(any(abs(w - x - u) <= 1 and abs(y - v) <= 1 for u, v in pts)
               for x, y in pts)


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_the_schematic_shades_the_two_foul_lines_alike(built, key):
    """Every park here is built as an exact mirror, so a left-right difference
    in the drawing would be simulation noise presented as ground — and at the
    fifteen folded parks it would leak a side as well. A band is pooled over
    both lines and drawn on both, so every shape is its own mirror image."""
    fig = diagram(built['pages'][PARK_SOURCES[key]['slug']])
    w = site_diagram.frame()['w']
    for cls, d in DIA_PATH.findall(fig):
        if re.fullmatch(r'z\d', cls):
            assert _mirrored(d, w), f'{key}: a band is drawn on one side only'
    assert _mirrored(SEATS.search(fig).group(2).replace('A', 'L'), w)


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
def test_the_schematic_marks_no_netting(built, key):
    """Step 26 took the netting mark off the drawing.

    It ran along the front of the areas the table called behind netting, so
    it was drawn on this model's template at the position of this model's
    seat labels — which the parks' own maps put in the wrong place at most of
    the parks it appeared on. The club's own sentence, directly under the
    drawing, is where the netting is now, and the drawing says nothing about
    it either way.
    """
    fig = diagram(built['pages'][PARK_SOURCES[key]['slug']])
    assert 'class="nm"' not in fig and 'netting' not in flat(fig).lower()


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_the_schematic_emits_no_negative_coordinate(built, key):
    """`_n` clamps, and this is why.

    A minus sign between two path coordinates is indistinguishable from a
    printed seat range to `test_no_section_numbers_on_any_park_page`, so a
    regression here would surface as a baffling failure in a test about
    something else. It surfaces here instead.
    """
    fig = diagram(built['pages'][PARK_SOURCES[key]['slug']])
    for d in re.findall(r'\sd="([^"]*)"', fig):
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


# ------------------------------------------------------------
# The window, the labels, and what the crop is not allowed to cut off
# ------------------------------------------------------------
#
# A park page now crops its drawing to that park instead of carrying the whole
# fleet's frame, which is the one change to this drawing that can go wrong
# silently in the worst way: a crop that is a few feet tight does not look
# like an error, it looks like a ballpark whose upper deck ends sooner than it
# does. So the crop is not eyeballed. Every point the emitted path data can
# reach is reconstructed here — endpoints, and the extremes of the arcs
# between them — and every one of them has to be inside the window.

VIEWBOX = re.compile(r'<svg[^>]*viewBox="([\d. ]+)"')
PATH_STEP = re.compile(r'([MLAZ])([\d. ]*)')


def view_box(svg: str) -> tuple[float, ...]:
    return tuple(float(v) for v in VIEWBOX.search(svg).group(1).split())


def arc_extremes(origin, a, b, r):
    """Where a concentric arc from `a` to `b` reaches furthest out.

    Every arc this drawing emits is centred on home plate, so the points that
    can leave the window are its two endpoints and whichever of due up, down,
    left and right the arc sweeps past on its way. Nothing here spans a half
    turn, so the short way round is the way it was drawn.
    """
    ox, oy = origin
    t0 = math.atan2(a[1] - oy, a[0] - ox)
    span = (math.atan2(b[1] - oy, b[0] - ox) - t0 + math.pi) % (2 * math.pi) \
        - math.pi
    out = []
    for k in range(-4, 5):
        t = k * math.pi / 2
        step = (t - t0 + math.pi) % (2 * math.pi) - math.pi
        if min(0.0, span) <= step <= max(0.0, span):
            out.append((ox + r * math.cos(t), oy + r * math.sin(t)))
    return out


def path_points(d: str, origin) -> list[tuple[float, float]]:
    """Every point one `d` attribute puts ink on, arcs included."""
    pts, here, start = [], None, None
    for cmd, args in PATH_STEP.findall(d):
        n = [float(v) for v in args.split()]
        if cmd == 'Z':
            here = start
            continue
        here_next = (n[-2], n[-1])
        if cmd == 'A':
            pts += arc_extremes(origin, here, here_next, n[0])
        if cmd == 'M':
            start = here_next
        pts.append(here_next)
        here = here_next
    return pts


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_a_park_page_crops_its_drawing_to_its_own_park(built, key):
    """The park page's window is that park's; the home page's is the fleet's.

    Both are the same paths in the same feet — `test_the_home_page_is_a_gallery`
    checks that path for path — so the only thing that separates them is the
    viewBox, and it has to separate them the right way round. A park page that
    kept the fleet frame is a drawing sitting in the largest park's margins;
    a tile that lost it is 31 pictures normalised to one size, which is the
    comparison the grid exists to make.
    """
    slug = PARK_SOURCES[key]['slug']
    p = built['parks'][slug]
    f = site_diagram.frame()
    box = site_diagram.park_box(p['stadium'], p['sides']['named'])

    page = view_box(diagram(built['pages'][slug]))
    assert page == tuple(round(box[k]) for k in ('x', 'y', 'w', 'h'))
    assert page[2] < f['w'] and page[3] < f['h'], \
        f'{slug}: the park page is not cropped at all'

    tile = re.search(r'<a href="%s/">.*?(<svg class="mini".*?</svg>)' % slug,
                     built['pages'][''], re.S).group(1)
    assert view_box(tile) == (0.0, 0.0, f['w'], f['h']), \
        f'{slug}: the home-page tile does not carry the fleet frame'


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_the_crop_cuts_nothing_off_the_drawing(built, key):
    """Nothing the drawing shows may fall outside the window it is drawn in.

    The band shapes run past the seating on purpose and are masked to it, so
    what is held to the window is what can show: the seating outline, the
    foul lines, the plate and the labels.
    """
    slug = PARK_SOURCES[key]['slug']
    fig = diagram(built['pages'][slug])
    x, y, w, h = view_box(fig)
    f = site_diagram.frame()
    origin = (f['ox'], f['oy'])

    shown = [d for cls, d in DIA_PATH.findall(fig) if cls in ('fl', 'hp')]
    shown.append(SEATS.search(fig).group(2))
    pts = [p for d in shown for p in path_points(d, origin)]
    assert pts
    for tx, ty in re.findall(r'<text[^>]* x="([\d.]+)" y="([\d.]+)"', fig):
        pts.append((float(tx), float(ty)))
    for px, py in pts:
        assert x <= px <= x + w and y <= py <= y + h, \
            f'{slug}: the crop cuts off ({px:.0f}, {py:.0f})'


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_the_home_plate_label_stands_clear_of_both_foul_lines(built, key):
    """The label was set seventeen feet above the plate and the two foul lines
    ran through the word. It is fair territory it has to stand in, and fair
    territory is a wedge: how much room there is depends on how far up it the
    label sits, so the position is computed from the width of the word and
    checked here against the lines the drawing actually emitted.
    """
    slug = PARK_SOURCES[key]['slug']
    fig = diagram(built['pages'][slug])
    f = site_diagram.frame()
    ox, oy = f['ox'], f['oy']

    lx, ly = (float(v) for v in re.search(
        r'<text class="pl" x="([\d.]+)" y="([\d.]+)"', fig).groups())
    half = site_diagram._text_half(site_diagram._PLATE_LABEL,
                                  site_diagram._FS_PLATE,
                                  site_diagram._PLATE_TRACK)
    # The four corners of the word, baseline at `ly` and the capitals above it.
    corners = [(lx + sx * half, ly - sy * site_diagram._FS_PLATE)
               for sx in (-1, 1) for sy in (0, 1)]

    lines = [d for cls, d in DIA_PATH.findall(fig) if cls == 'fl']
    assert len(lines) == 1
    tips = [(float(a), float(b)) for a, b in
            re.findall(r'L([\d.]+) ([\d.]+)', lines[0])]
    assert len(tips) == 2, 'the drawing does not carry two foul lines'

    for tip in tips:
        ux, uy = tip[0] - ox, tip[1] - oy
        length = math.hypot(ux, uy)
        for cx, cy in corners:
            px, py = cx - ox, cy - oy
            along = (px * ux + py * uy) / length
            off = abs(px * uy - py * ux) / length
            # Beyond the plate end of the line the distance to the line is not
            # what matters — the word is simply past it. Everywhere else it is.
            assert along <= 0 or off >= 8.0, \
                (f'{slug}: "{site_diagram._PLATE_LABEL}" passes within '
                 f'{off:.1f} ft of a foul line')


def test_the_shade_legend_matches_the_shade_boundaries(built):
    """The legend is the only thing on the page telling a reader what a shade
    is worth, so it is generated from `SHADE_WORDS`, it lists exactly the
    shades the drawing uses, darkest first, and the boundaries are quarters of
    the busiest band."""
    assert len(site_diagram.SHADE_WORDS) == len(site_diagram.SHADE_EDGES) + 1
    for key in STADIUMS:
        slug = PARK_SOURCES[key]['slug']
        leg = re.search(r'<p class="leg">(.*?)</p>',
                        diagram(built['pages'][slug])).group(1)
        assert 'against the busiest band here' in leg
        used = sorted(set(drawn_shades(built['pages'][slug])), reverse=True)
        assert re.findall(r'<i class="z(\d)"></i>(\w+)', leg) \
            == [(str(i), site_diagram.SHADE_WORDS[i]) for i in used]
    shade = site_diagram.shade_of
    assert shade(0.249, 1) == 0 and shade(0.25, 1) == 1
    assert shade(0.749, 1) == 2 and shade(0.75, 1) == 3 and shade(1, 1) == 3


def test_the_committed_band_shares_are_the_tests_own():
    """The site's band shares are not a second reading of the test: pooled
    over the eight parks the test compared, weighted by their observed fouls,
    the committed run gives the in-sample shares `CALIBRATION.md` records for
    the current model, to the tenth it records them at."""
    if not os.path.exists(COMMITTED_CACHE):
        pytest.skip('no committed model cache in this checkout')
    from validate_538 import PARKS, GROUPS, load_observed
    with open(COMMITTED_CACHE, encoding='utf-8') as fh:
        cache = json.load(fh)
    observed = load_observed()
    pooled, n = {g: 0.0 for g in GROUPS}, 0.0
    for matchup, _, key, status in PARKS:
        if status != 'compared':
            continue
        weight = sum(observed[matchup]['all'].values())
        bands = cache[key]['bands']
        seen = sum(bands.values())
        for g in GROUPS:
            pooled[g] += weight * bands[g] / seen
        n += weight
    shares = [round(100 * pooled[g] / n, 1) for g in GROUPS]
    assert shares == [29.2, 24.7, 45.0, 1.0], shares


def test_the_parks_barely_differ_as_the_home_page_says(built):
    """The home page says the parks differ mostly by their published
    dimensions and that the model does not reliably tell them apart. Both are
    visible in the committed run. The share behind the plate is the same at
    every park to within a point, as `VALIDATION.md` found; the forward bands
    move by up to about seven points between parks, because the published
    dimensions move the seats that catch a ball on its way down. The observed
    behind-plate share runs from 24% to 51% across the eight parks compared.
    """
    if not os.path.exists(COMMITTED_CACHE):
        pytest.skip('no committed model cache in this checkout')
    with open(COMMITTED_CACHE, encoding='utf-8') as fh:
        cache = json.load(fh)
    for g, _ in site_diagram.BANDS:
        shares = [e['bands'][g] / sum(e['bands'].values())
                  for e in cache.values()]
        spread = max(shares) - min(shares)
        assert spread < (0.01 if g == 'Z1' else 0.08), \
            f'{g}: the parks differ by {spread:.3f}'
    assert "doesn't reliably tell them apart" in built['pages']['']

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
                      # table, the drawing's own labels and the club's own
                      # words (Step 26): the budget is on this site's prose,
                      # and a quotation is the source, not the prose. What a
                      # quotation may contain is held to the club's text by
                      # `test_club_quotes_are_the_clubs_words`.
CLUB_QUOTES = re.compile(r'<q class="quote">.*?</q>'
                         r'|<blockquote class="quote">.*?</blockquote>', re.S)

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
    words = visible_words(built['pages'][slug], DETAILS_BODY, SCHEMATIC, TABLE,
                          CLUB_QUOTES)
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
    assert rest.count('<p') == 4, \
        'wordmark, one sentence, the line on what the grid shows, one link'
    for tag in ('<h2', '<h3', '<table', '<section', '<details', '<ol', '<ul',
                '<figure'):
        assert tag not in rest, f'{tag} on the home page outside the tiles'


@pytest.mark.parametrize('slug', PARK_SLUGS)
def test_park_specific_detail_is_behind_the_details_disclosure(built, slug):
    """Everything about this park that is not the drawing, the sentence, the
    table or the caveat is one click down, and all of it is still there."""
    text = built['pages'][slug]
    inside = text[text.index('<details class="more">'):text.index('</details>')]
    for anchor in ('netting-source', 'model', 'areas', 'figures', 'labels'):
        assert f'id="{anchor}"' in inside, \
            f'{slug}: the {anchor} section is not inside Details'
    assert re.search(r'Model run on\s+\d{4}-\d{2}-\d{2}', inside), \
        f'{slug}: the date the model ran is not on the page'

    outside = SCHEMATIC.sub(' ', DETAILS_BODY.sub(lambda m: m.group(1), text))
    assert 'id="mislabel"' not in outside
    assert outside.count('<p') == 5, \
        (f'{slug}: wordmark, team, netting sentence, the line on the test, '
         f'footer — and nothing else')
    for tag in ('<section', '<h2', '<h3', '<ol', '<ul', '<div'):
        assert tag not in outside, f'{slug}: {tag} outside Details'


@pytest.mark.parametrize('slug', PARK_SLUGS)
def test_a_row_of_the_distribution_table_is_a_band_and_two_shares(built, slug):
    """Step 30: four rows, out from the plate, each a band, the model's share
    of the park's foul balls in it, and FiveThirtyEight's share in it across
    its 2019 sample, to the whole per cent the test read them at.

    The rows used to be seating areas, each with a band word and no figure.
    Everything that left is checked here to be inside Details, under a heading
    that says no real data has tested it, because a page that dropped the
    areas would be hiding what the model produces.
    """
    text = built['pages'][slug]
    p = built['parks'][slug]
    table = TABLE.search(DETAILS_BODY.sub(lambda m: m.group(1), text)).group(0)
    assert 'mph' not in table and 'class="tag' not in table
    assert not TENTHS.search(re.sub(r'<[^>]+>', ' ', table))

    cells = re.findall(r'<tr><td class="k">(.*?)</td><td class="n">(.*?)</td>'
                       r'<td class="n">(.*?)</td></tr>', table, re.S)
    assert len(cells) == 4
    for (label, model, seen), b, (_, name) in zip(cells, p['bands'],
                                                  site_diagram.BANDS):
        assert label == site_build.band_label(b) and name in label
        assert model == site_build.share_str(100 * b['share'])
        assert seen == site_build.share_str(100 * b['observed'])
    assert abs(sum(b['share'] for b in p['bands']) - 1.0) < 1e-9

    # The observed column is all 906 of FiveThirtyEight's fouls, pooled, and
    # the line under the table says so.
    assert [c[2] for c in cells] == ['31%', '19%', '49%', '1%']
    head = flat(re.search(r'<thead>.*?</thead>', table, re.S).group(0))
    assert 'FiveThirtyEight <span>10 parks pooled, not this park</span>' \
        in head, f'{slug}: the observed column does not say it is pooled'
    foot = flat(re.search(r'<tfoot>.*?</tfoot>', table, re.S).group(0))
    for words in ('906 foul balls', '10 parks', '2019',
                  'unusually foul-heavy', 'pooled'):
        assert words in foot, f'{slug}: the sample line has lost "{words}"'
    # Step 29 fitted the back-foul rate to these fouls, so the table says the
    # agreement is partly by construction and points to the held-out test.
    for words in ("back-foul rate was calibrated to this data",
                  'close agreement here is expected',
                  '<a href="../about/#validation">held-out test</a>',
                  'is the fair measure'):
        assert words in foot.replace('&#x27;', "'"), \
            f'{slug}: the calibration note has lost "{words}"'

    inside = flat(text[text.index('<details class="more">'):])
    areas = inside.split('id="areas"')[1].split('<section')[0]
    assert 'Seating areas and decks: untested by any real data' in areas
    assert 'No real data has tested any figure in this panel' in areas
    assert 'Each area in full' in areas and 'mph' in areas
    assert 'of the fouls that reach' in areas
    for z in p['zones']:
        assert f'<td class="n">{site_build.fouls_str(z["fouls"])}</td>' \
            in areas, f'{slug}: {z["id"]}\'s figure is not under Details'


TENTHS = re.compile(r'\d\.\d')


@pytest.mark.parametrize('slug', PARK_SLUGS)
def test_no_figure_to_a_tenth_is_shown_outside_details(built, slug):
    """Step 26: the page above the fold carried every area's figure to a tenth
    of a ball a game, from a model that cannot tell 2.1 from 2.3 and has never
    seen a foul ball. Nothing visible may carry a decimal now — not the table,
    not the drawing's legend, not its description for a screen reader. The
    exact figures are inside Details and only there.
    """
    text = built['pages'][slug]
    outside = DETAILS_BODY.sub(lambda m: m.group(1), HEAD.sub(' ', text))
    outside = SCHEMATIC.sub(lambda m: SVG_GEOMETRY.sub(' ', m.group(0)),
                            outside)
    readable = html.unescape(re.sub(r'<(?!svg)[^>]+>', ' ', outside))
    hit = TENTHS.search(readable)
    assert hit is None, f'{slug}: "{readable[hit.start()-30:hit.end()+5]}"'
    inside = DETAILS_BODY.search(text).group(0)
    assert TENTHS.search(inside), f'{slug}: the exact figures are gone entirely'


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_a_mislabelled_park_says_so_over_its_area_table(built, key):
    """Step 26, from `LIMITATIONS.md` P1: at 27 of the 30 parks whose seating
    map was read, the map puts this model's areas somewhere else — at Truist
    Park the row called "behind home plate" is up the third-base line. A
    reader who takes the area names and leaves takes the wrong seats, so one
    line says so at every park whose map read disagrees, and at no other.

    Step 30 took the area names off the visible page — its table is four
    bands by distance along the foul line and names no seat — so the line
    went with them, and stands at the head of the panel that holds them.
    """
    slug = PARK_SOURCES[key]['slug']
    text = built['pages'][slug]
    mr = MAP_READS.get(key)
    disagrees = bool(mr and mr['outcome'] == 'disagrees')
    line = f'<p class="mislabel" id="mislabel">{site_build.MISLABEL_LINE}</p>'
    assert (line in text) is disagrees, \
        f'{slug}: map read {"disagrees" if disagrees else "does not"}, and ' \
        f'the line is {"missing" if disagrees else "there anyway"}'
    if disagrees:
        panel = text.split('id="areas"')[1]
        assert panel.split('</h2><div class="pb">')[1].lstrip() \
            .startswith(line), f'{slug}: the line does not head the panel'
        assert text.index(line) < text.index('Each area in full'), \
            f'{slug}: the line is under the areas it is about'
    assert sum(1 for k, v in MAP_READS.items() if v['outcome'] == 'disagrees') \
        == 27


def test_no_page_calls_a_park_the_smallest_unless_it_is(built):
    """Step 26: Fenway's page said its 18,100 sq ft was "the smallest foul
    territory in the majors". This site's own figures put Wrigley Field at
    16,500. Any superlative about foul territory anywhere on the site has to
    agree with `PARK_PARAMS`, which is what the page prints and the model
    uses."""
    areas = sorted((p.foul_area_sqft, k) for k, p in PARK_PARAMS.items()
                   if p.foul_area_sqft)
    smallest, second = areas[0][1], areas[1][1]
    assert smallest == 'wrigley_field' and second == 'fenway_park'
    # The parks with a roof over the field, fixed or retractable — the one
    # qualifier a foul-territory superlative on this site uses (Comerica's).
    roofed = {'chase_field', 'minute_maid', 'tropicana_field', 'rogers_centre',
              'loan_depot', 'american_family', 'globe_life', 'tmobile_park'}
    open_air = max((a, k) for a, k in areas if k not in roofed)[1]
    for key in STADIUMS:
        text = flat(built['pages'][PARK_SOURCES[key]['slug']])
        if re.search(r'(?<!second-)smallest foul territory', text):
            assert key == smallest, f'{key} is called the smallest'
        if 'second-smallest foul territory' in text:
            assert key == second, f'{key} is called the second-smallest'
        if 'largest foul territory of any open-air park' in text:
            assert key == open_air, f'{key} is called the largest open-air'
        elif 'largest foul territory' in text:
            assert key == areas[-1][1], f'{key} is called the largest'
    fenway = flat(built['pages']['fenway-park'])
    assert 'smallest foul territory in the majors' not in fenway
    assert 'second-smallest foul territory' in fenway and 'Wrigley' in fenway


@pytest.mark.parametrize('key', sorted(STADIUMS))
def test_a_description_promises_only_figures_that_are_published(built, key):
    """Step 26: Las Vegas Ballpark's search description promised "the park's
    sourced foul territory and backstop figures", and neither is published
    anywhere; its page says so. A description may name a sourced figure only
    where `PARK_SOURCES` has one."""
    slug = PARK_SOURCES[key]['slug']
    src = PARK_SOURCES[key]
    desc = html.unescape(re.search(r'<meta name="description" content="(.*?)">',
                                   built['pages'][slug]).group(1))
    if src['foul_area'] is None:
        assert 'sourced foul territory' not in desc, f'{slug}: {desc}'
    if src['backstop'] is None:
        assert not re.search(r'sourced[^.]*backstop', desc), f'{slug}: {desc}'
    if src['foul_area'] is None and src['backstop'] is None:
        assert 'sourced' not in desc, f'{slug}: {desc}'
    las_vegas = html.unescape(re.search(
        r'<meta name="description" content="(.*?)">',
        built['pages']['las-vegas-ballpark']).group(1))
    assert 'neither its foul territory nor its backstop is published' \
        in las_vegas


def test_a_fully_covered_deck_receives_no_foul_ball(built):
    """Step 26: Wrigley Field's page printed a 100% upper-deck cover beside
    "the covered part of that deck receives nothing here", and a table giving
    that deck nearly three fouls a game. The cover was pulled in by the deck's
    mean depth, floored at a foot, and enough survived to take balls.

    Now a deck entirely under a blocking cover is `fully_covered`, no ball is
    credited to it, every area on it shows "none", the drawing leaves it off,
    and the page's sentence about the cover says the whole deck receives
    nothing. Wrigley is the only such park, and the check is general.
    """
    full = []
    for key in STADIUMS:
        p = built['parks'][PARK_SOURCES[key]['slug']]
        covered = [z for z in p['zones'] if z['covered']]
        params = PARK_PARAMS[key]
        if covered:
            full.append(key)
            assert params.upper_overhang >= 100 and params.upper_cover in (
                'deck', 'canopy'), f'{key}: a deck is covered with no cover'
            text = flat(built['pages'][p['slug']])
            assert 'covers the whole deck' in text \
                and 'no foul ball reaches the upper deck here' in text
            for z in covered:
                assert z['fouls'] == 0.0, f'{key}: {z["id"]} receives balls'
                assert site_build.fouls_str(z['fouls']) == 'none'
        else:
            assert 'covers the whole deck' not in flat(
                built['pages'][p['slug']])
    assert full == ['wrigley_field']

    # And in the geometry the simulation itself matches against: the deck is
    # still there for the dive-under test, and flagged so nothing lands on it.
    stadium = STADIUMS['wrigley_field']()
    upper = [s for s in stadium.sections if s.level == 'upper']
    assert upper and all(s.fully_covered for s in upper)
    assert not any(s.fully_covered for s in stadium.sections
                   if s.level != 'upper')
    assert any(sec.fully_covered
               for a in range(0, 136, 5)
               for sec, _, _ in exposed_bands(
                   [s for s in stadium.sections if s.side in ('1B', 'HOME')],
                   float(a)))


@pytest.mark.parametrize('slug', PARK_SLUGS)
def test_the_details_disclosure_is_shut(built, slug):
    """Closed on every page and on every visit.

    The whole shape of a park page rests on it: the netting sentence, the
    table and one line of caveat are the page, and everything that qualifies
    them is one click down. An `open` attribute would put a screen and a half
    of provenance back in front of the answer, and it is the kind of attribute
    that gets added for one debugging session and committed.
    """
    text = built['pages'][slug]
    assert '<details class="more"><summary>Details</summary>' in text
    assert '<details' in text and ' open' not in text[text.index('<details'):
                                                      text.index('<summary')], \
        f'{slug}: the Details disclosure is open by default'


@pytest.mark.parametrize('slug', PARK_SLUGS)
def test_every_park_page_ends_with_the_same_footer_as_the_home_page(built,
                                                                    slug):
    """A page that stopped at a closed disclosure stopped without ending.

    The same footer rule the home page keeps: one line, one link, above the
    fold's own hairline. The link differs — back to the 31 rather than on to
    /about/, which the caveat above it already carries — and that is the only
    thing about it that does.
    """
    text = built['pages'][slug]
    assert text.index('</details>') < text.index('<footer>'), \
        f'{slug}: the footer is inside the disclosure'
    foot = text[text.index('<footer>'):text.index('</footer>')]
    assert foot.count('<p') == 1, f'{slug}: the footer is not one line'
    assert '<a href="../">All 31 ballparks</a>' in foot
    home = built['pages']['']
    assert home[home.index('<footer>'):home.index('</footer>')].count('<p') == 1


def test_the_about_page_holds_every_explanation(built):
    """Nothing honest was deleted; it moved here. Each explanation the site
    used to carry on the home page or on every park page is on this page,
    under its own anchor."""
    about = flat(built['pages']['about'])
    for anchor in ('validation', 'sourced', 'netting-words', 'parks', 'sides',
                   'numbers', 'diagram', 'method', 'limits', 'sources'):
        assert f'id="{anchor}"' in about, f'about page has no {anchor} section'
    for heading, _ in MODEL_LIMITS:
        assert flat(html.escape(heading, quote=True)) in about, \
            f'about page is missing the limit "{heading}"'
    assert flat(site_build.NETTING_CLUB_CAVEAT) in about
    assert 'not to scale and not a seating chart' in about
    assert 'No figure on this site is ever drawn as a length' in about
    # Step 26: the bands, their boundaries, and the one exception to the rule
    # against section numbers, each stated where the site explains itself.
    assert '"most" is at least three quarters of that band' in about
    assert 'the band past the pole is in the table and not on the drawing' \
        in about
    assert 'only section numbers anywhere on this site are inside a ' \
        'quotation from a club' in about
    assert 'simulations per batter, fixed seed' in about
    assert 'is not affiliated with Major League Baseball' in about
    assert 'nothing on it will keep a ball from reaching you' in about


@pytest.mark.parametrize('slug', PARK_SLUGS + [''])
def test_every_page_links_to_the_about_page(built, slug):
    """A park page's link goes straight to the test's results (Step 30); the
    home page's goes to the top of the page."""
    link = ('<a href="../about/#validation">Results' if slug
            else '<a href="about/">How this works')
    assert link in built['pages'][slug], \
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
