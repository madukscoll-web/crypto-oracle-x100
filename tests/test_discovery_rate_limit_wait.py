import unittest
import urllib.error
from unittest.mock import patch

import crypto_oracle_scanner as scanner
import oracle_http

URL = "https://api.geckoterminal.com/api/v2/networks/base/new_pools?page=1"
HOST = "api.geckoterminal.com"


def too_many():
    return urllib.error.HTTPError(URL, 429, "Too Many Requests", {}, None)


class DiscoveryRateLimitWaitTests(unittest.TestCase):
    def setUp(self):
        scanner._RATE_WAIT["used"] = 0.0
        oracle_http._COOLDOWN_UNTIL.pop(HOST, None)
        self.addCleanup(oracle_http._COOLDOWN_UNTIL.pop, HOST, None)

    def test_short_cooldown_is_waited_out_then_retried_once(self):
        calls, sleeps = [], []
        def fetch(url):
            calls.append(url)
            if len(calls) == 1:
                oracle_http._COOLDOWN_UNTIL[HOST] = oracle_http.time.monotonic() + 60
                raise too_many()
            return {"data": []}
        with patch.object(scanner, "fetch_json", fetch), patch.object(scanner.time, "sleep", sleeps.append):
            self.assertEqual(scanner.fetch_discovery(URL), {"data": []})
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(sleeps), 1)
        self.assertGreater(sleeps[0], 55)

    def test_provider_rate_limited_skip_also_waits_when_cooldown_is_short(self):
        calls, sleeps = [], []
        oracle_http._COOLDOWN_UNTIL[HOST] = oracle_http.time.monotonic() + 30
        def fetch(url):
            calls.append(url)
            if len(calls) == 1:
                raise oracle_http.ProviderRateLimited("cooldown")
            return {"data": []}
        with patch.object(scanner, "fetch_json", fetch), patch.object(scanner.time, "sleep", sleeps.append):
            self.assertEqual(scanner.fetch_discovery(URL), {"data": []})
        self.assertEqual(len(calls), 2)

    def test_long_cooldown_is_deferred_not_waited(self):
        sleeps = []
        oracle_http._COOLDOWN_UNTIL[HOST] = oracle_http.time.monotonic() + 600
        def fetch(url):
            raise oracle_http.ProviderRateLimited("cooldown")
        with patch.object(scanner, "fetch_json", fetch), patch.object(scanner.time, "sleep", sleeps.append):
            with self.assertRaises(oracle_http.ProviderRateLimited):
                scanner.fetch_discovery(URL)
        self.assertEqual(sleeps, [])

    def test_wait_budget_is_bounded_per_run(self):
        sleeps = []
        scanner._RATE_WAIT["used"] = scanner.RATE_LIMIT_WAIT_BUDGET_SECONDS - 10
        oracle_http._COOLDOWN_UNTIL[HOST] = oracle_http.time.monotonic() + 60
        def fetch(url):
            raise oracle_http.ProviderRateLimited("cooldown")
        with patch.object(scanner, "fetch_json", fetch), patch.object(scanner.time, "sleep", sleeps.append):
            with self.assertRaises(oracle_http.ProviderRateLimited):
                scanner.fetch_discovery(URL)
        self.assertEqual(sleeps, [])

    def test_second_failure_after_wait_propagates_without_a_second_wait(self):
        calls, sleeps = [], []
        def fetch(url):
            calls.append(url)
            oracle_http._COOLDOWN_UNTIL[HOST] = oracle_http.time.monotonic() + 60
            raise too_many()
        with patch.object(scanner, "fetch_json", fetch), patch.object(scanner.time, "sleep", sleeps.append):
            with self.assertRaises(urllib.error.HTTPError):
                scanner.fetch_discovery(URL)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(sleeps), 1)

    def test_non_rate_limit_errors_are_never_retried(self):
        calls, sleeps = [], []
        def fetch(url):
            calls.append(url)
            raise urllib.error.HTTPError(URL, 500, "Server Error", {}, None)
        with patch.object(scanner, "fetch_json", fetch), patch.object(scanner.time, "sleep", sleeps.append):
            with self.assertRaises(urllib.error.HTTPError):
                scanner.fetch_discovery(URL)
        self.assertEqual((len(calls), sleeps), (1, []))

    def test_cooldown_remaining_reports_zero_when_inactive(self):
        self.assertEqual(oracle_http.cooldown_remaining("never-seen.example"), 0.0)


if __name__ == "__main__":
    unittest.main()
