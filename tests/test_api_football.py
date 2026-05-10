"""
Tests unitarios para scrapers.api_football.client.

NO hace requests reales: todo va contra mocks de requests.Session.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scrapers.api_football.client import (  # noqa: E402
    APIFootballClient,
    APIFootballError,
    APIFootballRateLimitError,
    BACKOFF_BASE,
)


def _make_response(status=200, json_data=None, headers=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.headers = headers or {}
    r.text = text or json.dumps(json_data or {})
    if json_data is None:
        json_data = {}
    r.json.return_value = json_data
    return r


class FakeSession:
    """Session mock que devuelve respuestas pre-armadas en orden."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        if not self._responses:
            raise AssertionError("Sin respuestas mock restantes")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


# ─────────────────────────────────────────────────────── construcción

class TestConstruction(unittest.TestCase):
    def test_requires_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(APIFootballError):
                APIFootballClient()

    def test_sets_auth_header(self):
        sess = FakeSession([])
        c = APIFootballClient(api_key="xyz", session=sess)
        self.assertEqual(c.session.headers["x-apisports-key"], "xyz")
        self.assertEqual(c.api_key, "xyz")


# ───────────────────────────────────────────── parsing y endpoints

class TestEndpointConstruction(unittest.TestCase):
    def _ok(self, payload=None):
        return _make_response(
            200,
            json_data={"response": payload or [], "errors": [], "results": 0},
            headers={
                "x-ratelimit-requests-remaining": "7400",
                "x-ratelimit-remaining": "440",
            },
        )

    def test_get_status_path(self):
        sess = FakeSession([self._ok({"account": {"email": "a@b.com"}})])
        c = APIFootballClient(api_key="k", session=sess)
        out = c.get_status()
        self.assertIn("response", out)
        self.assertTrue(sess.calls[0]["url"].endswith("/status"))

    def test_get_fixtures_by_date_params(self):
        sess = FakeSession([self._ok([])])
        c = APIFootballClient(api_key="k", session=sess)
        c.get_fixtures_by_date("2026-05-15", league=39, season=2025)
        call = sess.calls[0]
        self.assertTrue(call["url"].endswith("/fixtures"))
        self.assertEqual(call["params"]["date"], "2026-05-15")
        self.assertEqual(call["params"]["league"], 39)
        self.assertEqual(call["params"]["season"], 2025)

    def test_get_h2h_param_format(self):
        sess = FakeSession([self._ok([])])
        c = APIFootballClient(api_key="k", session=sess)
        c.get_h2h(33, 50, last=10)
        call = sess.calls[0]
        self.assertEqual(call["params"]["h2h"], "33-50")
        self.assertEqual(call["params"]["last"], 10)

    def test_get_team_statistics_params(self):
        sess = FakeSession([self._ok([])])
        c = APIFootballClient(api_key="k", session=sess)
        c.get_team_statistics(team=33, league=39, season=2025)
        call = sess.calls[0]
        self.assertEqual(call["params"]["team"], 33)
        self.assertEqual(call["params"]["league"], 39)
        self.assertEqual(call["params"]["season"], 2025)

    def test_rate_limit_headers_parsed(self):
        sess = FakeSession([self._ok([])])
        c = APIFootballClient(api_key="k", session=sess)
        c.get_status()
        self.assertEqual(c.requests_remaining, 7400)
        self.assertEqual(c.minute_remaining, 440)


# ───────────────────────────────────────────── manejo de errores

class TestErrorHandling(unittest.TestCase):
    def test_429_raises_rate_limit_error(self):
        resp = _make_response(429, text="too many", headers={
            "x-ratelimit-requests-remaining": "0"
        })
        sess = FakeSession([resp])
        c = APIFootballClient(api_key="k", session=sess)
        with self.assertRaises(APIFootballRateLimitError):
            c.get_status()
        self.assertEqual(c.requests_remaining, 0)

    @patch("scrapers.api_football.client.time.sleep", return_value=None)
    def test_5xx_retries_then_succeeds(self, _sleep):
        resps = [
            _make_response(503, text="busy"),
            _make_response(503, text="busy"),
            _make_response(200, json_data={"response": [], "errors": []}),
        ]
        sess = FakeSession(resps)
        c = APIFootballClient(api_key="k", session=sess)
        out = c.get_status()
        self.assertIn("response", out)
        self.assertEqual(len(sess.calls), 3)

    @patch("scrapers.api_football.client.time.sleep", return_value=None)
    def test_5xx_exhausts_retries(self, _sleep):
        resps = [_make_response(500, text="boom") for _ in range(3)]
        sess = FakeSession(resps)
        c = APIFootballClient(api_key="k", session=sess)
        with self.assertRaises(APIFootballError):
            c.get_status()
        self.assertEqual(len(sess.calls), 3)

    @patch("scrapers.api_football.client.time.sleep", return_value=None)
    def test_connection_error_retries(self, _sleep):
        import requests as _r
        sess = FakeSession([
            _r.ConnectionError("netfail"),
            _make_response(200, json_data={"response": [], "errors": []}),
        ])
        c = APIFootballClient(api_key="k", session=sess)
        out = c.get_status()
        self.assertIn("response", out)

    def test_semantic_errors_raise(self):
        resp = _make_response(200, json_data={
            "response": [],
            "errors": {"plan": "Endpoint no incluido en tu plan"},
        })
        sess = FakeSession([resp])
        c = APIFootballClient(api_key="k", session=sess)
        with self.assertRaises(APIFootballError):
            c.get_status()

    def test_semantic_errors_quota_raises_rate_limit(self):
        resp = _make_response(200, json_data={
            "response": [],
            "errors": {"requests": "You have reached the request limit"},
        })
        sess = FakeSession([resp])
        c = APIFootballClient(api_key="k", session=sess)
        with self.assertRaises(APIFootballRateLimitError):
            c.get_status()

    def test_empty_errors_dict_is_ok(self):
        resp = _make_response(200, json_data={"response": [1, 2], "errors": []})
        sess = FakeSession([resp])
        c = APIFootballClient(api_key="k", session=sess)
        out = c.get_status()
        self.assertEqual(out["response"], [1, 2])

    def test_4xx_other_raises(self):
        resp = _make_response(401, text="unauthorized")
        sess = FakeSession([resp])
        c = APIFootballClient(api_key="k", session=sess)
        with self.assertRaises(APIFootballError):
            c.get_status()


if __name__ == "__main__":
    unittest.main()
