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
these test the *generator* rather than whatever happens to be committed. One
extra test checks that the committed build exists and covers every park, which
is what the web app actually serves.

Known limit of the section-number test, stated rather than hidden: the
substring check only runs on printed labels of three characters or more.
Labels like "9" or "26" — real at Fenway, Globe Life and Truist — cannot be
distinguished from ordinary prose by substring search. Those parks are covered
by the pattern checks instead, which catch every mechanism by which a number
could actually leak: a raw section name, a printed range, or the word "section"
followed by a digit.
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from foulball.stadium import STADIUMS
from foulball.netting import join_park
from foulball.seat_map import build_printed_index, printed_range_display
import site_build
from site_data import PARK_SOURCES

# Low enough to keep the suite quick; the constraints under test are properties
# of the copy and the layout, not of the simulation count.
TEST_SIMS = 8

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMITTED_SITE = os.path.join(REPO, 'site')


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
    page is asserting which line is which — off labels `AUDIT.md` holds to be
    unverified at every park. That assertion has to carry its own warning."""
    hedged = 0
    for slug, p in built['parks'].items():
        if p['net']['state'] != 'mapped':
            continue
        text = built['pages'][slug]
        if p['net']['sides_differ']:
            hedged += 1
            assert 'which line is which is the weakest claim' in flat(text), \
                f'{slug}: side-specific netting claim is not hedged'
        else:
            assert 'which line is which is the weakest claim' not in flat(text), \
                f'{slug}: hedge shown where the two sides agree'
    assert hedged == 4, f'expected 4 side-asymmetric parks, found {hedged}'


def test_twenty_parks_are_netting_gaps(built):
    """The count on the home page has to be the count in the data."""
    gaps = [p for p in built['parks'].values() if p['net']['state'] != 'mapped']
    assert len(gaps) == 20
    assert '20 it is a gap' in built['pages']['']


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
    assert checked >= 8, 'expected most mapped parks to have a netted zone'


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
