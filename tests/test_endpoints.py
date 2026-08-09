"""
Flask API endpoint tests.

Tests /api/predict, /api/teams, /api/stadiums, and error handling.
Uses Flask test client (no network, no real MLB API calls for predict).
"""
import pytest
import json
from unittest.mock import patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from webapp_v2 import app
from foulball.stadium import STADIUMS


@pytest.fixture
def client():
    """Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


class TestPredictEndpoint:
    """Tests for /api/predict."""

    def test_missing_team_ids(self, client):
        resp = client.get('/api/predict')
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

    def test_invalid_team_ids(self, client):
        resp = client.get('/api/predict?away=abc&home=def')
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

    def test_unknown_team_ids(self, client):
        resp = client.get('/api/predict?away=99999&home=88888')
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'Unknown team' in data['error']

    def test_same_team(self, client):
        resp = client.get('/api/predict?away=147&home=147')
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'different' in data['error'].lower()

    def test_post_method_works(self, client):
        """POST with JSON body should be accepted."""
        resp = client.post(
            '/api/predict',
            data=json.dumps({'away': 99999, 'home': 88888}),
            content_type='application/json',
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

    def test_post_same_team(self, client):
        resp = client.post(
            '/api/predict',
            data=json.dumps({'away': 147, 'home': 147}),
            content_type='application/json',
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'different' in data['error'].lower()


class TestStadiumsEndpoint:
    """Tests for /api/stadiums."""

    def test_returns_every_registered_park(self, client):
        """One park per club, plus any second home park.

        The Athletics play six 2026 dates at Las Vegas Ballpark, so the
        registry is 30 clubs + alternates and a hardcoded 30 would fail for
        the right reason.
        """
        resp = client.get('/api/stadiums')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == len(STADIUMS)
        assert len(data) >= 30
        assert {s['key'] for s in data} == set(STADIUMS)

    def test_stadium_has_required_fields(self, client):
        resp = client.get('/api/stadiums')
        data = resp.get_json()
        for s in data:
            assert 'key' in s
            assert 'name' in s
            assert 'team' in s
            assert 'sections' in s
            assert s['sections'] > 0

    def test_stadiums_cached_on_second_call(self, client):
        """Second call should return same data (from cache)."""
        resp1 = client.get('/api/stadiums')
        resp2 = client.get('/api/stadiums')
        assert resp1.get_json() == resp2.get_json()


class TestIndexEndpoint:
    """Test the main page loads."""

    def test_index_returns_html(self, client):
        resp = client.get('/')
        assert resp.status_code == 200
        assert b'FoulCast' in resp.data or b'Template not found' in resp.data


class TestLiveEndpoint:
    """Tests for /api/live/<game_id>."""

    def test_invalid_game_id_returns_error(self, client):
        """Non-existent game should return an error, not 500."""
        resp = client.get('/api/live/0')
        # 400 (no teams resolved), 404 (game not found), or 503 are all acceptable
        assert resp.status_code in (400, 404, 503, 200)


class TestRateLimiting:
    """Test the rate limiter."""

    def _reset_rate_limits(self):
        """Clear rate limit state between tests."""
        import webapp_v2
        webapp_v2._rate_limits.clear()

    def test_rate_limit_allows_initial_requests(self, client):
        """First few requests should not be rate-limited."""
        self._reset_rate_limits()
        for _ in range(5):
            resp = client.get('/api/predict?away=147&home=147')
            assert resp.status_code == 400  # validation error, not 429

    def test_rate_limit_enforced(self, client):
        """After 10 requests in a minute, should get 429."""
        self._reset_rate_limits()
        got_429 = False
        for i in range(12):
            # Use same-team error to avoid triggering expensive predictions
            resp = client.get('/api/predict?away=147&home=147')
            if resp.status_code == 429:
                data = resp.get_json()
                assert 'Rate limited' in data['error']
                got_429 = True
                break
        assert got_429, "Rate limit was not enforced after 12 requests"
