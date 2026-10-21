"""
What the server answers on, and what it is allowed to say there.

Step 25 retired the interactive demo and the prediction endpoints it called.
The tests that were here tested those endpoints — that `/api/predict` rejected
a missing team id, that `/` returned HTML, that the rate limiter fired after
ten predictions. They tested a surface the project has decided not to publish,
so they are replaced rather than kept:

1. **The public route list is exactly the routes below.** Not "contains" —
   equals. The demo was not wrong because of what it computed; it was wrong
   because it was reachable, and a list that only checks for absences cannot
   catch the next thing that becomes reachable. Adding a public URL now means
   editing this list, which is a decision somebody makes on purpose.
2. **The retired URLs are gone**, and gone means 404 rather than a redirect to
   somewhere polite — there is nothing at the other end to redirect to.
3. **Nothing a visitor can reach makes a claim this project cannot support.**
   The same two patterns `tests/test_site.py` holds the 33 built pages to, run
   against every public page the server serves.

The foul log joined the list on 20 October 2026, shelved rather than retired —
its season ended on 27 September and it made no claims, so what it gets is the
same treatment for a different reason: the views are all still in the file, on
a blueprint nobody registers, and a test below says so in both directions.

The model is untouched; `foulball/` is where it lives and the rest of the
suite still exercises it. What is retired is the publishing of it.
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from webapp_v2 import app
from tests.conftest import ACCURACY_CLAIM, SAFE_WORD


@pytest.fixture
def client():
    """Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


# Every URL rule the app registers, with what it is for. The whole list.
#
# Flask's own `/static/<path>` is absent deliberately: the app is constructed
# with `static_folder=None`, because there is no static directory and a public
# URL that exists only to return 404 is still a public URL.
PUBLIC_ROUTES = {
    '/',                                  # redirect to the site
    '/parks/',                            # the site's home page
    '/parks/<slug>/',                     # the 31 park pages and /about/
    '/robots.txt',
    '/sitemap.xml',
}

# What Step 25 took down. The first six answered with section-level
# predictions, a recommended side to sit on, a named best section and a
# confidence rating, or fed the page that displayed them. The rest are the
# foul log, shelved on 20 October 2026 — a different reason for the same
# treatment: its views are all still in the file, on a blueprint nobody
# registers.
RETIRED = [
    '/api/predict',
    '/api/predict?away=147&home=111',
    '/api/live/747123',
    '/api/today',
    '/api/teams',
    '/api/stadiums',
    '/log',
    '/api/log/games',
    '/api/log/entries',
    '/api/log/context/747123',
    '/api/log/export.csv',
    '/api/log/export.jsonl',
]

# Every page a visitor can read. It is the site, and that is the point.
VISITOR_PAGES = ['/parks/', '/parks/about/', '/parks/fenway-park/']


def test_the_public_route_list_is_exactly_this():
    """A new public URL cannot appear without somebody deciding it should."""
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert rules == PUBLIC_ROUTES, (
        f'unlisted public route(s): {sorted(rules - PUBLIC_ROUTES)}; '
        f'missing: {sorted(PUBLIC_ROUTES - rules)}')


def test_the_root_url_goes_to_the_site(client):
    """It used to be the demo. It is the front door to the site now."""
    resp = client.get('/')
    assert resp.status_code in (301, 302, 307, 308)
    assert resp.headers['Location'].endswith('/parks/')

    landed = client.get('/parks/')
    assert landed.status_code == 200
    assert b'Where foul balls land, ballpark by ballpark' in landed.data
    assert b'<ul class="grid">' in landed.data


@pytest.mark.parametrize('url', RETIRED)
def test_the_demo_and_its_prediction_endpoints_are_gone(client, url):
    resp = client.get(url)
    assert resp.status_code == 404, \
        f'{url} still answers with {resp.status_code}'


def test_the_shelved_foul_log_is_kept_but_unregistered(client):
    """Shelved is not deleted, and not reachable either.

    The eight views are on `log_api`, which nothing registers, so the URLs
    404 — that part is covered by `RETIRED` above. What this checks is the
    other half of the bargain: the code is still there, still carrying all
    eight views, and still importable, so the day somebody registers the
    blueprint they get the tool back rather than a rewrite. POST routes are
    checked here rather than in `RETIRED` because a POST to a missing rule and
    a POST to a rule that refuses POSTs are different failures.
    """
    import webapp_v2
    assert len(webapp_v2.log_api.deferred_functions) == 8, \
        'the shelved log blueprint has lost views'
    assert webapp_v2.log_api.name not in app.blueprints, \
        'the shelved log blueprint is registered after all'
    assert callable(webapp_v2._resolve_zone)
    assert webapp_v2.LOG_TEMPLATE

    for url in ('/api/log/session', '/api/log/foul', '/api/log/void'):
        assert client.post(url, json={}).status_code == 404, \
            f'{url} still accepts a write'


def test_the_demo_template_is_gone():
    """The page itself, not just the route to it."""
    here = os.path.dirname(os.path.abspath(__file__))
    demo = os.path.join(here, '..', 'templates', 'demo.html')
    assert not os.path.exists(demo), 'templates/demo.html is still on disk'
    import webapp_v2
    assert not hasattr(webapp_v2, 'HTML_TEMPLATE')
    assert not hasattr(webapp_v2, '_run_prediction'), \
        'the prediction the demo displayed is still wired into the server'


# Script and style bodies are not read by a visitor. The distinction mattered
# while the foul log was served — its form state carries a field called
# `confidence`, the observer's own confidence in where they saw the ball land,
# which is the opposite of a model claim — and it is kept because the next page
# that gets served here will have scripts in it too.
SCRIPTS = re.compile(r'(?is)<(script|style)\b.*?</\1>')
TAGS = re.compile(r'<[^>]+>')


def visible(body: bytes) -> str:
    return TAGS.sub(' ', SCRIPTS.sub(' ', body.decode('utf-8')))


@pytest.mark.parametrize('url', VISITOR_PAGES)
def test_no_public_page_claims_accuracy(client, url):
    resp = client.get(url)
    assert resp.status_code == 200, f'{url} returned {resp.status_code}'
    hit = ACCURACY_CLAIM.search(visible(resp.data))
    assert hit is None, f'{url}: accuracy language "{hit.group(0)}"'


@pytest.mark.parametrize('url', VISITOR_PAGES)
def test_no_public_page_uses_the_word_safe(client, url):
    resp = client.get(url)
    hit = SAFE_WORD.search(visible(resp.data))
    assert hit is None, f'{url}: "{hit.group(0)}"'


@pytest.mark.parametrize('url', VISITOR_PAGES)
def test_no_public_page_recommends_a_seat(client, url):
    """The demo's actual output: a side to sit on and a best section.

    The site describes where the model puts fouls and what the clubs publish
    about netting, and leaves the reader to decide what to do about it. It
    cannot recommend a seat without claiming the figures are good enough to
    pick one, and nothing here has ever been checked against a foul ball.
    """
    text = re.sub(r'\s+', ' ', visible(client.get(url).data))
    for phrase in ('best section', 'sit on the', 'recommend', 'where to sit',
                   'confidence'):
        assert phrase not in text.lower(), f'{url}: "{phrase}"'


def test_the_sitemap_names_only_the_site(client):
    """Whatever is reachable, this is what is advertised."""
    body = client.get('/sitemap.xml').data.decode('utf-8')
    locs = re.findall(r'<loc>([^<]+)</loc>', body)
    assert locs, 'empty sitemap'
    for loc in locs:
        assert '/parks/' in loc, f'sitemap advertises {loc}'
    assert len(locs) == 33, f'{len(locs)} urls in the sitemap, expected 33'


def test_robots_does_not_point_at_anything_retired(client):
    body = client.get('/robots.txt').data.decode('utf-8')
    assert 'sitemap.xml' in body.lower()
    for url in RETIRED:
        assert url.split('?')[0] not in body


class TestRateLimiting:
    """The limiter outlived the endpoints it was written for.

    It still guards the foul-log writes, which is now the only thing it
    guards, so it is tested there — on the `log` bucket's own budget, which is
    120 a minute rather than the 10 the predictions had.
    """

    def _reset(self):
        import webapp_v2
        webapp_v2._rate_limits.clear()

    def test_requests_under_the_limit_are_allowed(self):
        import webapp_v2
        self._reset()
        for _ in range(10):
            assert webapp_v2._check_rate_limit('203.0.113.7', bucket='log',
                                               max_requests=120)

    def test_the_limit_is_enforced_per_bucket(self):
        import webapp_v2
        self._reset()
        ip = '203.0.113.8'
        for _ in range(3):
            assert webapp_v2._check_rate_limit(ip, bucket='log',
                                               max_requests=3)
        assert not webapp_v2._check_rate_limit(ip, bucket='log',
                                               max_requests=3)
        # A different bucket under the same IP keeps its own counter: a fan
        # clearing a backed-up offline queue must not be throttled by whatever
        # else that address did.
        assert webapp_v2._check_rate_limit(ip, bucket='other', max_requests=3)
